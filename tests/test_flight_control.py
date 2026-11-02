import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
from dataclasses import replace
import pytest
from PySide6 import QtCore, QtWidgets
from bullet_view.flight_control import FlightClient, FlightSnapshot
from bullet_view.flight_view import FlightPanel
from bullet_msgs.flight_control import *


def packet(**fields):
    return SimpleNamespace(get_srcSystem=lambda:1, get_srcComponent=lambda:1, **fields)


def state(client, now, armed=False, height=20., readiness=DISARMED_IDLE, valid=True):
    for name, value in zip(FLIGHT_NAMES, (float(armed), float(valid), readiness, height)):
        client.named(packet(time_boot_ms=round(now*1000),value=value), name, now)


def ack(command, action, result=0, **extra):
    p = packet(command=command, result=result, result_param2=ACTION_IDS[action],
               target_system=255, target_component=190)
    p.__dict__.update(extra)
    return p


def client():
    outputs, sent = [], []
    c = FlightClient(outputs.append)
    mav = SimpleNamespace(command_long_send=lambda *args:sent.append(args))
    return c, mav, outputs, sent


def test_height_requires_ack_and_matching_readback_even_if_readback_first():
    c, mav, outputs, sent = client()
    assert c.remote.height_m is None
    state(c, 1.)
    c.request('height', 5.5, mav, 1.1)
    assert sent[-1][2] == 31012 and sent[-1][4] == 5.5
    c.ack(ack(31012, 'height'), 1.2)
    assert c.pending is not None
    state(c, 1.3, height=5.5)
    assert c.pending is None and c.remote.height_m == 5.5
    c.request('height', 6., mav, 1.4)
    state(c, 1.5, height=6.)
    assert c.pending is not None
    c.ack(ack(31012, 'height'), 1.6)
    assert c.pending is None


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
    with pytest.raises(ValueError): c.request('start',20.,mav,1.1)
    c.request('start',5.5,mav,1.1)
    c.ack(ack(300,'start'),1.2)
    state(c,1.3,True,5.5,FLYING)
    assert c.pending is None
    with pytest.raises(ValueError): c.request('height',6.,mav,1.3)
    with pytest.raises(ValueError): c.request('disarm',None,mav,1.3)


class Presenter(QtCore.QObject):
    flight_changed = QtCore.Signal(object)
    def __init__(self):
        super().__init__(); self.requests=[]
    def request_flight(self,*args): self.requests.append(args)


def test_panel_slider_editor_unknown_pending_and_cancel(monkeypatch):
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    p=Presenter(); panel=FlightPanel(p)
    assert 'unknown' in panel.state_label.text() and not panel.arm.isEnabled()
    panel.set_snapshot(FlightSnapshot(FlightState(False,True,DISARMED_IDLE,20.,1.,(1,1))))
    panel.slider.setValue(55)
    assert panel.height.value()==5.5
    panel.height.setValue(6.)
    assert panel.slider.value()==60
    panel.apply.click()
    assert p.requests==[('height',6.)]
    panel.set_snapshot(FlightSnapshot(FlightState(True,True,ARMED_IDLE,5.5,1.,(1,1))))
    assert not panel.start.isEnabled()
    panel.height.setValue(5.5)
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
    assert len(p.requests)==1 and calls[0][-1]==QtWidgets.QMessageBox.StandardButton.Cancel
    monkeypatch.setattr(QtWidgets.QMessageBox,'warning',lambda *args:QtWidgets.QMessageBox.StandardButton.Yes)
    panel.disarm.click()
    assert p.requests[-1]==('emergency',)
    panel.close()


def test_worker_cleanup_closes_both_connections_and_always_finishes():
    from bullet_view.worker import MavlinkWorker
    calls=[]
    def close_bad():
        calls.append('bad'); raise OSError('socket close failure')
    one=SimpleNamespace(close=close_bad,mav=object())
    two=SimpleNamespace(close=lambda:calls.append('good'),mav=object())
    connections=iter((one,two))
    worker=MavlinkWorker('telemetry',control_endpoint='control',connection_factory=lambda _:next(connections))
    # Initialization fails at use_mavlink2's incomplete fake transport; both acquired sockets still close.
    finished=[];worker.finished.connect(lambda:finished.append(True))
    worker.run()
    assert calls==['bad','good'] and finished==[True]


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


def test_control_connection_failure_keeps_flight_actions_disabled_after_telemetry():
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
