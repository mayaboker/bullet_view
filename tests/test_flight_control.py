import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from dataclasses import replace
import pytest
from PySide6 import QtCore, QtWidgets
from bullet_view.flight_control import FlightClient, FlightSnapshot, flight_action_block_reason
from bullet_view.flight_view import FlightPanel
from bullet_view.flight_protocol import *


def packet(**fields):
    return SimpleNamespace(get_srcSystem=lambda:1, get_srcComponent=lambda:1, **fields)


def state(client, now, armed=False, height=20., readiness=DISARMED_IDLE, valid=True):
    client.named(packet(time_boot_ms=round(now*1000), value=1.), 'APP_MODE', now)
    for name, value in zip(FLIGHT_NAMES, (float(armed), float(valid), readiness, height)):
        client.named(packet(time_boot_ms=round(now*1000),value=value), name, now)


def ack(command, action, result=0, **extra):
    p = packet(command=command, result=result, result_param2={**ACTION_IDS, 'land': 6}[action],
               target_system=255, target_component=190)
    p.__dict__.update(extra)
    return p


def client():
    outputs, sent = [], []
    c = FlightClient(outputs.append)
    mav = SimpleNamespace(command_long_send=lambda *args:sent.append(args))
    return c, mav, outputs, sent


def test_restart_completes_from_new_epoch_and_disarmed_readback_without_final_ack():
    c, mav, _, sent = client()
    state(c, 1.)
    c.named(packet(value=2.), 'APP_STATE', 1.)
    c.named(packet(value=7.), 'APP_EPOCH', 1.)
    c.request('restart', None, mav, 1.1)
    assert sent[-1] == (1, 1, APP_RESTART_COMMAND, 0, 0., 0., 0., 0., 0., 0., 0.)
    progress = packet(command=APP_RESTART_COMMAND, result=5, result_param2=0,
                      target_system=255, target_component=190)
    c.ack(progress, 1.2)
    c.named(packet(value=1.), 'APP_STATE', 1.3)
    c.named(packet(value=8.), 'APP_EPOCH', 1.3)
    state(c, 1.3)
    assert c.pending is None and c.result == 'restart: App ready and disarmed'


def test_restart_rejects_stale_status_and_armed_then_waits_for_reconnect():
    c, mav, _, _ = client()
    state(c, 1., armed=True)
    c.named(packet(value=2.), 'APP_STATE', 1.)
    with pytest.raises(ValueError, match='Disarm'):
        c.request('restart', None, mav, 1.1)
    state(c, 1.2)
    with pytest.raises(ValueError, match='stale'):
        c.request('restart', None, mav, 2.1)
    c.named(packet(value=2.), 'APP_STATE', 2.2)
    c.request('restart', None, mav, 2.2)
    c.poll(100.)
    assert c.pending is not None
    c.named(packet(value=8.), 'APP_EPOCH', 100.1)
    c.named(packet(value=1.), 'APP_STATE', 100.1)
    state(c, 100.1, armed=True)
    assert c.pending is not None
    state(c, 100.2)
    assert c.pending is None and c.result == 'restart: App ready and disarmed'


def test_restart_failure_ack_ends_pending_request():
    c, mav, _, _ = client()
    state(c, 1.)
    c.named(packet(value=2.), 'APP_STATE', 1.)
    c.request('restart', None, mav, 1.1)
    failed = packet(command=APP_RESTART_COMMAND, result=4, result_param2=0,
                    target_system=255, target_component=190)
    c.ack(failed, 1.2)
    assert c.pending is None and 'failed' in c.result


def test_height_is_set_by_mission_profile():
    c, mav, outputs, sent = client()
    assert c.remote.height_m is None
    state(c, 1.)
    assert c.remote.readiness is Readiness.DISARMED_IDLE
    with pytest.raises(ValueError, match='manual target mission'):
        c.request('height', 5.5, mav, 1.1)
    assert sent == [] and c.remote.height_m == 20.


def test_flight_protocol_uses_view_local_mavlink_definitions():
    from pathlib import Path

    source_root = Path(__file__).resolve().parents[1] / 'src' / 'bullet_view'
    for name in ('flight_protocol.py', 'flight_control.py', 'flight_view.py'):
        source = (source_root / name).read_text()
        assert 'bullet_msgs' not in source
    worker_source = (source_root / 'worker.py').read_text()
    assert 'bullet_msgs.flight_control' not in worker_source
    assert 'bullet_msgs.spawn' not in worker_source
    assert tuple(int(value) for value in Readiness) == (0, 1, 2, 3, 4)


def test_target_height_requires_ack_and_observed_value():
    c, mav, _, sent = client()
    state(c, 1., height=10.)
    c.named(packet(time_boot_ms=1000, value=2.), 'APP_MSN', 1.)
    c.named(packet(time_boot_ms=1000, value=5.), 'HOVER_S', 1.)
    c.request('height', 12.5, mav, 1.1)
    assert sent[-1][2:6] == (TAKEOFF_HEIGHT_COMMAND, 0, 12.5, 0.)
    c.ack(ack(TAKEOFF_HEIGHT_COMMAND, 'height'), 1.2)
    assert c.pending is not None
    state(c, 1.3, height=12.5)
    assert c.pending is None
    assert c.snapshot().hover_s == 5.
    state(c, 1.4, height=12.5, readiness=FLYING)
    with pytest.raises(ValueError, match='active'):
        c.request('height', 13., mav, 1.4)


def test_target_height_validates_and_other_missions_reject():
    c, mav, _, sent = client()
    state(c, 1.)
    with pytest.raises(ValueError, match='target mission'):
        c.request('height', 12., mav, 1.1)
    c.named(packet(time_boot_ms=1000, value=2.), 'APP_MSN', 1.)
    for value in (0., 100.1, float('nan')):
        with pytest.raises(ValueError):
            c.request('height', value, mav, 1.1)
    assert sent == []


def test_wrong_target_wrong_command_late_arm_ack_and_disarm_preemption():
    c,mav,_,sent = client()
    state(c, 1.)
    c.request('arm', None, mav, 1.1)
    c.ack(ack(400, 'arm', get_srcSystem=lambda:2), 1.2)
    c.ack(ack(300, 'arm'), 1.2)
    c.ack(ack(400, 'arm', target_component=1), 1.2)
    assert not c.pending['ack']
    c.request('disarm', None, mav, 1.3)
    c.ack(ack(400, 'arm'), 1.4)
    assert not c.pending['ack']
    state(c, 1.5)
    c.ack(ack(400, 'disarm'), 1.6)
    assert c.pending is None


def test_stale_and_unknown_state_disable_actions_but_emergency_keeps_target():
    c,mav,_,sent = client()
    with pytest.raises(ValueError): c.request('arm',None,mav,1.)
    state(c, 1.)
    c.poll(2.)
    assert not c.remote.valid and c.remote.height_m is None
    with pytest.raises(ValueError): c.request('height',5.5,mav,2.)
    c.request('emergency',None,mav,2.)
    assert sent[-1][5] == FORCE_DISARM_MAGIC
    c.poll(8.)
    assert c.pending is None and 'unknown' in c.result


def test_start_and_airborne_height_guards():
    c,mav,_,_=client()
    state(c,1.)
    with pytest.raises(ValueError): c.request('start',20.,mav,1.)
    state(c,1.1,True,5.5,ARMED_IDLE)
    c.request('start',None,mav,1.1)
    c.ack(ack(300,'start'),1.2)
    state(c,1.3,True,5.5,FLYING)
    assert c.pending is None
    with pytest.raises(ValueError): c.request('height',6.,mav,1.3)
    with pytest.raises(ValueError): c.request('disarm',None,mav,1.3)


def test_target_mission_status_and_single_attempt_gate():
    c, mav, _, _ = client()
    state(c, 1.)
    c.named(packet(time_boot_ms=1000, value=2.), 'APP_MSN', 1.)
    c.named(packet(time_boot_ms=1000, value=9.), 'APP_PHASE', 1.)
    assert c.snapshot().mission == 'target-hit'
    assert c.snapshot().phase == 'search'
    state(c, 1.1, True, 10., ARMED_IDLE)
    assert flight_action_block_reason(c.snapshot(), 'start', now=1.1) is None
    c.named(packet(time_boot_ms=1100, value=1.), 'VIS_READY', 1.1)
    assert flight_action_block_reason(c.snapshot(), 'start', 10., now=1.1) is None
    c.named(packet(time_boot_ms=1000, value=1.), 'APP_RESULT', 1.)
    assert c.snapshot().mission_result == 'hit'
    state(c, 1.2, False, 10., DISARMED_IDLE)
    with pytest.raises(ValueError, match='restart'):
        c.request('arm', None, mav, 1.2)


def test_manual_land_requires_ack_and_observed_landing_phase():
    c, mav, _, sent = client()
    state(c, 1., True, 3., FLYING)
    c.named(packet(time_boot_ms=1000, value=5.), 'APP_PHASE', 1.)
    c.request('land', None, mav, 1.1)
    assert sent[-1][2] == 21
    c.ack(ack(21, 'land'), 1.2)
    assert c.pending is not None
    state(c, 1.3, True, 3., FLYING)
    c.named(packet(time_boot_ms=1300, value=6.), 'APP_PHASE', 1.3)
    assert c.pending is None


def test_auto_mode_blocks_arm_but_allows_active_target_abort():
    c, mav, _, sent = client()
    state(c, 1.)
    c.named(packet(time_boot_ms=1000, value=0.), 'APP_MODE', 1.)
    with pytest.raises(ValueError, match='automatically'):
        c.request('arm', None, mav, 1.1)
    state(c, 1.2, True, 10., FLYING)
    c.named(packet(time_boot_ms=1200, value=0.), 'APP_MODE', 1.2)
    c.named(packet(time_boot_ms=1200, value=9.), 'APP_PHASE', 1.2)
    c.request('land', None, mav, 1.3)
    assert sent[-1][2] == 21


class Presenter(QtCore.QObject):
    flight_changed = QtCore.Signal(object)
    def __init__(self):
        super().__init__(); self.requests=[]
    def request_flight(self,*args): self.requests.append(args)


@pytest.fixture(scope='module')
def qt_app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_manual_target_panel_slider_applies_height_before_start(qt_app):
    p = Presenter()
    panel = FlightPanel(p)
    remote = FlightState(True, True, ARMED_IDLE, 10., 1., (1, 1))
    panel.set_snapshot(FlightSnapshot(remote, mode='manual', mission='target-hit', hover_s=5.))
    assert panel.height.isEnabled() and panel.slider.isEnabled()
    assert panel.slider.minimum() == 0 and panel.slider.maximum() == 1000
    panel.slider.setValue(125)
    assert panel.height.value() == 12.5
    panel.height.setValue(0.)
    assert panel.slider.value() == 0 and not panel.apply.isEnabled() and not panel.start.isEnabled()
    panel.height.setValue(12.5)
    assert panel.apply.isEnabled() and not panel.start.isEnabled()
    panel.apply.click()
    assert p.requests[-1] == ('height', 12.5)
    panel.set_snapshot(FlightSnapshot(remote, pending='height', mode='manual', mission='target-hit', hover_s=5.))
    assert not panel.apply.isEnabled() and not panel.start.isEnabled()
    confirmed = FlightState(True, True, ARMED_IDLE, 12.5, 2., (1, 1))
    panel.set_snapshot(FlightSnapshot(confirmed, result='height: ACK accepted and remote state confirmed',
                                      mode='manual', mission='target-hit', hover_s=5.))
    assert panel.start.isEnabled() and not panel.apply.isEnabled()
    panel.close()


def test_panel_shows_profile_height_and_keeps_abort_controls(monkeypatch):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    p=Presenter(); panel=FlightPanel(p)
    assert 'unknown' in panel.state_label.text() and not panel.arm.isEnabled()
    panel.set_snapshot(FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1))))
    assert panel.arm.isEnabled() and not panel.disarm.isEnabled()
    assert panel.height.value() == 20. and panel.height.isReadOnly()
    assert not panel.height.isEnabled()
    panel.set_snapshot(FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1)), pending='arm'))
    assert not panel.arm.isEnabled() and panel.disarm.isEnabled()
    monkeypatch.setattr(QtWidgets.QMessageBox, 'warning',
                        lambda *args: QtWidgets.QMessageBox.StandardButton.Cancel)
    panel.disarm.click()
    assert p.requests==[]
    panel.set_snapshot(FlightSnapshot(FlightState(True,True,ARMED_IDLE,5.5,1.,(1,1))))
    assert panel.start.isEnabled()
    panel.set_snapshot(FlightSnapshot(panel.snapshot.remote,'height'))
    assert not panel.start.isEnabled() and panel.disarm.isEnabled()
    panel.set_snapshot(FlightSnapshot(FlightState(True,True,FLYING,5.5,1.,(1,1))))
    assert not panel.height.isEnabled()
    calls=[]
    def cancel(*args):
        calls.append(args)
        return QtWidgets.QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QtWidgets.QMessageBox,'warning',cancel)
    panel.disarm.click()
    assert len(p.requests)==0 and calls[0][-1]==QtWidgets.QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QtWidgets.QMessageBox,'warning',lambda *args:QtWidgets.QMessageBox.StandardButton.Yes)
    panel.disarm.click()
    assert p.requests[-1]==('emergency',)
    panel.set_snapshot(FlightSnapshot(FlightState(True,True,FLYING,5.5,1.,(1,1)),
                                      mode='manual', phase='hover'))
    assert panel.land.isEnabled()
    panel.land.click()
    assert p.requests[-1]==('land',)
    panel.set_snapshot(FlightSnapshot(FlightState(True,True,ARMED_IDLE,10.,1.,(1,1)),
                                      mode='auto', phase='armed'))
    assert not panel.start.isEnabled() and panel.start.text() == 'Start hover mission'
    assert not panel.height.isEnabled() and not panel.land.isEnabled()
    panel.close()


def test_worker_cleanup_closes_single_connection_and_always_finishes():
    from bullet_view.worker import MavlinkWorker
    calls=[]
    def close_bad():
        calls.append('bad'); raise OSError('socket close failure')
    one=SimpleNamespace(close=close_bad,mav=object())
    worker=MavlinkWorker('telemetry',connection_factory=lambda _:one)
    # Initialization fails at use_mavlink2's incomplete fake transport; the acquired socket still closes.
    finished=[];worker.finished.connect(lambda:finished.append(True))
    worker.run()
    assert calls==['bad'] and finished==[True]


@pytest.mark.parametrize('armed,readiness,valid,pending,available,target,expected', [
    (False,DISARMED_IDLE,True,None,True,(1,1),(True,False)),
    (True,ARMED_IDLE,True,None,True,(1,1),(False,True)),
    (True,FLYING,True,None,True,(1,1),(False,False)),
    (False,RESET_REQUIRED,True,None,True,(1,1),(False,False)),
    (False,UNAVAILABLE,True,None,True,(1,1),(False,False)),
    (None,UNAVAILABLE,False,None,True,(1,1),(False,False)),
    (True,DISARMED_IDLE,True,None,True,(1,1),(False,False)),
    (False,ARMED_IDLE,True,None,True,(1,1),(False,False)),
    (None,ARMED_IDLE,True,None,True,(1,1),(False,False)),
    (False,DISARMED_IDLE,True,'arm',True,(1,1),(False,False)),
    (True,ARMED_IDLE,True,'start',True,(1,1),(False,False)),
    (True,ARMED_IDLE,True,'height',True,(1,1),(False,False)),
    (False,DISARMED_IDLE,True,None,False,(1,1),(False,False)),
    (False,DISARMED_IDLE,True,None,True,None,(False,False)),
])
def test_panel_arm_start_state_matrix(armed,readiness,valid,pending,available,target,expected):
    p=Presenter();panel=FlightPanel(p)
    remote=FlightState(armed,valid,readiness,20.,1.,target)
    panel.set_snapshot(FlightSnapshot(remote,pending,control_available=available))
    assert (panel.arm.isEnabled(),panel.start.isEnabled())==expected
    assert not (panel.arm.isEnabled() and panel.disarm.isEnabled())
    assert panel.arm.toolTip() and panel.start.toolTip()
    assert 'Arm:' in panel.availability_label.text() and 'Start:' in panel.availability_label.text()
    panel.close()
    panel.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


@pytest.mark.parametrize('height',[None,float('nan'),0.,100.1])
def test_start_requires_valid_remote_height(height):
    from bullet_view.flight_control import flight_action_block_reason
    remote=FlightState(True,True,ARMED_IDLE,height,1.,(1,1))
    assert flight_action_block_reason(FlightSnapshot(remote),'start',20.) is not None


def test_client_cannot_arm_or_start_with_conflicting_observed_state():
    c,mav,_,sent=client()
    state(c,1.,True,20.,DISARMED_IDLE)
    with pytest.raises(ValueError,match='already armed'):c.request('arm',None,mav,1.)
    state(c,1.1,False,20.,ARMED_IDLE)
    with pytest.raises(ValueError,match='confirmed armed idle'):c.request('start',20.,mav,1.1)
    assert sent==[]


def test_connection_failure_keeps_flight_actions_disabled_after_telemetry():
    c,mav,_,sent=client();state(c,1.)
    c.offline();state(c,1.1)
    assert c.remote.valid and not c.snapshot().control_available
    with pytest.raises(ValueError,match='connection unavailable'):c.request('arm',None,mav,1.1)
    assert not sent


def flight_presenter():
    # Exercise real presenter coordination without creating an unused QThread.
    from bullet_view.presenter import Presenter as RealPresenter
    from bullet_view.worker import MavlinkWorker
    class Harness(RealPresenter):
        def __init__(self):
            QtCore.QObject.__init__(self)
            self.clock=lambda:1.1
            self.flight_snapshot=FlightSnapshot()
            self._queued_flight_action=None
            self.worker=MavlinkWorker('test',clock=self.clock)
            self.worker.setParent(self)
            self.worker.flight_changed.connect(self._on_flight)
            self.worker.flight_request_handled.connect(self._on_flight_request_handled)
    return Harness()


def test_presenter_locks_immediately_ignores_old_updates_and_worker_releases():
    presenter=flight_presenter()
    idle=FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1)))
    presenter._on_flight(idle)
    presenter.request_flight('arm')
    assert presenter.flight_snapshot.pending=='arm'
    presenter.request_flight('arm')
    assert presenter.worker.flight_commands.qsize()==1
    presenter._on_flight(idle)  # older queued telemetry cannot re-enable Arm
    assert presenter.flight_snapshot.pending=='arm'
    presenter._on_flight_request_handled('arm',replace(idle,pending='arm'))
    assert presenter.flight_snapshot.pending=='arm'
    armed=replace(idle,remote=replace(idle.remote,armed=True,readiness=ARMED_IDLE))
    presenter._on_flight(armed)
    assert presenter.flight_snapshot.pending is None
    presenter.request_flight('start',20.)
    assert presenter.flight_snapshot.pending=='start'
    presenter.request_flight('emergency')
    assert presenter.flight_snapshot.pending=='emergency'
    presenter._on_flight_request_handled('start',replace(armed,pending='start'))
    assert presenter.flight_snapshot.pending=='emergency'
    presenter._on_flight_request_handled('emergency',replace(armed,pending='emergency'))
    assert presenter._queued_flight_action is None


def test_worker_rejection_clears_queued_presenter_action():
    presenter=flight_presenter()
    idle=FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1)))
    presenter._on_flight(idle)
    presenter.request_flight('arm')
    assert presenter.flight_snapshot.pending=='arm'
    # Worker has no control connection; request must be rejected and unlocked.
    presenter.worker._poll_flight()
    assert presenter.flight_snapshot.pending is None
    assert 'unavailable' in presenter.flight_snapshot.result


def test_presenter_queue_full_restores_state_and_stale_requests_never_queue():
    presenter=flight_presenter()
    idle=FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1)))
    presenter._on_flight(idle)
    for _ in range(presenter.worker.flight_commands.maxsize):
        presenter.worker.flight_commands.put_nowait(('height',20.))
    presenter.request_flight('arm')
    assert presenter.flight_snapshot.pending is None and presenter._queued_flight_action is None
    presenter.clock=lambda:3.
    presenter.worker.flight_commands.get_nowait()
    size=presenter.worker.flight_commands.qsize()
    presenter.request_flight('arm')
    assert presenter.worker.flight_commands.qsize()==size
