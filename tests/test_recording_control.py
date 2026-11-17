import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from types import SimpleNamespace
from dataclasses import replace
import pytest
from PySide6 import QtCore, QtWidgets
from bullet_view.recording_control import RecordingClient, RecordingSnapshot
from bullet_view.recording_view import RecordingPanel
from bullet_msgs.mavlink_control import RECORDING_CONTROL_COMMAND


def packet(**fields):
    return SimpleNamespace(get_srcSystem=lambda:1,get_srcComponent=lambda:1,**fields)


def state(c,now,value=0,authority=1):
    for name,value in (('REC_AUTH',authority),('REC_STATE',value)):
        c.named(packet(time_boot_ms=round(now*1000),value=value),name,now)


def ack(action=1,result=0,**extra):
    msg=packet(command=RECORDING_CONTROL_COMMAND,result=result,result_param2=action,
        target_system=255,target_component=190)
    msg.__dict__.update(extra)
    return msg


def setup():
    sent=[];snapshots=[]
    return RecordingClient(snapshots.append),SimpleNamespace(command_long_send=lambda *v:sent.append(v)),sent,snapshots


def test_start_stop_require_ack_and_remote_recorder_state():
    c,mav,sent,_=setup();state(c,1.)
    c.request(True,mav,1.1)
    assert sent[-1]==(1,1,31011,0,1.,0.,0.,0.,0.,0.,0.)
    c.ack(ack(),1.2)
    assert c.pending is not None
    state(c,1.3,1)
    assert c.pending is None and 'started' in c.snapshot.result
    c.request(False,mav,1.4)
    state(c,1.5,2)
    assert c.pending is not None
    state(c,1.6,0)
    assert c.pending is not None
    c.ack(ack(2),1.7)
    assert c.pending is None and 'MCAP finalized' in c.snapshot.result


def test_stop_preempts_start_and_ignores_late_start_ack():
    c,mav,_,_=setup();state(c,1.)
    c.request(True,mav,1.1);c.request(False,mav,1.2)
    c.ack(ack(1,4),1.3);c.ack(ack(1),1.3)
    assert c.pending['action']=='stop' and not c.pending['ack']
    state(c,1.4,0);c.ack(ack(2),1.5)
    assert c.pending is None


def test_wrong_ack_targets_and_commands_cannot_confirm():
    c,mav,_,_=setup();state(c,1.);c.request(True,mav,1.1)
    for message in (ack(get_srcSystem=lambda:2),ack(target_component=1),ack(command=400)):
        c.ack(message,1.2)
    assert not c.pending['ack']
    c.ack(ack(result=2),1.3)
    assert c.pending is None and 'rejected' in c.snapshot.result


def test_authority_stale_unknown_and_timeout():
    c,mav,sent,_=setup()
    with pytest.raises(ValueError):c.request(True,mav,1.)
    state(c,1.,authority=2)
    with pytest.raises(ValueError):c.request(True,mav,1.)
    state(c,1.1);c.poll(2.)
    assert not c.snapshot.online and c.snapshot.state=='unknown'
    with pytest.raises(ValueError):c.request(True,mav,2.)
    c.request(False,mav,2.)  # A known MAVLink target can still receive Stop.
    c.poll(8.)
    assert c.pending is None and 'unknown' in c.snapshot.result
    c.offline();assert not c.snapshot.online


def test_partial_foreign_invalid_and_reordered_telemetry():
    c,_,_,_=setup()
    c.named(packet(time_boot_ms=1000,value=1),'REC_AUTH',1.)
    assert not c.snapshot.online
    foreign=packet(time_boot_ms=1000,value=0);foreign.get_srcSystem=lambda:2
    c.named(foreign,'REC_STATE',1.)
    assert not c.snapshot.online
    state(c,2.,1)
    state(c,1.,0)
    assert c.snapshot.state=='recording'
    state(c,3.,float('nan'))
    assert c.snapshot.received_at_s==2.


class Presenter(QtCore.QObject):
    recording_changed=QtCore.Signal(object)
    def __init__(self):super().__init__();self.requests=[]
    def request_recording(self,start):self.requests.append(start)


def test_panel_buttons_follow_remote_authority_pending_and_actual_state():
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    p=Presenter();panel=RecordingPanel(p)
    assert not panel.start.isEnabled() and not panel.stop.isEnabled()
    snapshot=RecordingSnapshot(1,'idle',True,(1,1),1.)
    p.recording_changed.emit(snapshot)
    panel.start.click();assert p.requests==[True]
    panel.set_snapshot(replace(snapshot,pending='start'))
    assert not panel.start.isEnabled() and panel.stop.isEnabled()
    panel.stop.click();assert p.requests==[True,False]
    panel.set_snapshot(replace(snapshot,state='finalizing',pending='stop'))
    assert not panel.start.isEnabled() and not panel.stop.isEnabled()
    panel.set_snapshot(replace(snapshot,authority=2))
    assert 'Godot' in panel.status.text() and not panel.start.isEnabled() and not panel.stop.isEnabled()
    panel.set_snapshot(replace(snapshot,control_available=False))
    assert not panel.start.isEnabled() and not panel.stop.isEnabled()
    panel.close()


def test_worker_queue_stop_priority_and_presenter_routing():
    from bullet_view.worker import MavlinkWorker
    from bullet_view.presenter import Presenter as RealPresenter
    c,mav,sent,_=setup();state(c,1.)
    worker=MavlinkWorker('test',clock=lambda:1.1)
    worker.connection=SimpleNamespace(mav=mav)
    worker.recording=c
    worker.request_recording(True);worker.request_recording(False);worker._poll_recording()
    assert len(sent)==1 and sent[0][4]==0.
    presenter=RealPresenter('test')
    presenter.request_recording(True)
    assert presenter.worker.recording_commands.get_nowait() is True
    presenter._on_recording(c.snapshot)
    assert presenter.recording_snapshot==c.snapshot


def test_closed_connection_disables_requests_even_with_telemetry():
    c,mav,_,_=setup();state(c,1.)
    c.offline();state(c,1.1)
    assert not c.snapshot.control_available
    with pytest.raises(ValueError):c.request(False,mav,1.1)


def test_worker_converts_recording_named_values_without_touching_flight_state():
    from bullet_view.worker import MavlinkWorker
    worker=MavlinkWorker('test')
    snapshots=[];worker.recording_changed.connect(snapshots.append)
    for name,value in ((b'REC_AUTH',1.),('REC_STATE',1.)):
        message=packet(get_type=lambda:'NAMED_VALUE_FLOAT',name=name,value=value,time_boot_ms=1000)
        worker._emit_message(message,1.)
    assert snapshots[-1].state=='recording' and snapshots[-1].authority==1
    assert worker.flight.remote.armed is None
