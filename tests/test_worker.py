from bullet_view.model import Bbox, StatusText, TelemetryUpdate
from bullet_view.presenter import Presenter, VerticalSpeedEstimator
from bullet_view.worker import MavlinkWorker
from bullet_view.peer_udp import AppPeerUDP
from bullet_simulation_protocol.view_bbox import MESSAGE_TYPE, encode_bbox
import pytest
import socket
from threading import Thread
from time import monotonic, sleep
from pymavlink import mavutil
from bullet_msgs.parameters import use_mavlink2


class Message:
    def __init__(self, kind, **fields):
        self.kind = kind
        self.__dict__.update(fields)

    def get_type(self):
        return self.kind


def test_app_peer_udp_replies_only_to_selected_sender():
    listener = AppPeerUDP('udpin:127.0.0.1:0')
    app = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    stranger = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    replacement = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        destination = listener.port.getsockname()
        for sender in (app, stranger, replacement):
            sender.bind(('127.0.0.1', 0))
            sender.settimeout(.1)
        with pytest.raises(ConnectionError, match='No Bullet App peer'):
            listener.write(b'early')
        stranger.sendto(b'unknown', destination)
        assert listener.recv() == b'unknown'
        app.sendto(b'app', destination)
        assert listener.recv() == b'app'
        listener.select_sender()
        listener.write(b'reply')
        assert app.recvfrom(100)[0] == b'reply'
        with pytest.raises(TimeoutError):
            stranger.recvfrom(100)
        replacement.sendto(b'restarted', destination)
        assert listener.recv() == b'restarted'
        listener.select_sender()
        listener.write(b'new reply')
        assert replacement.recvfrom(100)[0] == b'new reply'
    finally:
        listener.close()
        app.close()
        stranger.close()
        replacement.close()


def test_worker_uses_one_udp_socket_for_app_stream_command_and_ack():
    listener = AppPeerUDP('udpin:127.0.0.1:0')
    port = listener.port.getsockname()[1]
    worker = MavlinkWorker(f'udpin:127.0.0.1:{port}', connection_factory=lambda _: listener)
    app = mavutil.mavlink_connection(f'udpout:127.0.0.1:{port}')
    use_mavlink2(app, 1, 1)
    thread = Thread(target=worker.run, daemon=True)
    thread.start()
    try:
        deadline = monotonic() + 2
        while monotonic() < deadline and not worker.flight.remote.valid:
            app.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_QUADROTOR,
                                   mavutil.mavlink.MAV_AUTOPILOT_GENERIC, 0, 0,
                                   mavutil.mavlink.MAV_STATE_STANDBY, 3)
            for name, value in (('ARM_MODE', 0.), ('ARM_VALID', 1.),
                                ('MIS_READY', 1.), ('TAKEOFF_H', 10.), ('APP_MODE', 1.)):
                app.mav.named_value_float_send(1000, name.encode(), value)
            sleep(.03)
        assert worker.flight.remote.valid
        assert listener.peer == ('127.0.0.1', app.port.getsockname()[1])
        assert app.recv_match(type='HEARTBEAT', blocking=True, timeout=1) is not None
        worker.request_flight('arm')
        command = app.recv_match(type='COMMAND_LONG', blocking=True, timeout=1)
        assert command is not None and command.command == 400 and command.param1 == 1
        app.mav.command_ack_send(400, mavutil.mavlink.MAV_RESULT_ACCEPTED, 0, 1, 255, 190)
        deadline = monotonic() + 1
        while monotonic() < deadline:
            pending = worker.flight.pending
            if pending is not None and pending['ack']:
                break
            sleep(.01)
        assert worker.flight.pending is not None and worker.flight.pending['ack']
    finally:
        worker.request_stop()
        thread.join(2)
        app.close()
        assert not thread.is_alive()


def test_worker_maps_standard_mavlink_messages_to_updates():
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    worker._emit_message(Message('ATTITUDE', roll=.1, pitch=.2, yaw=.3, time_boot_ms=4), 1.)
    worker._emit_message(Message('ALTITUDE', altitude_local=5., time_usec=6), 2.)
    worker._emit_message(Message('HEARTBEAT'), 3.)
    worker._emit_message(Message('DISTANCE_SENSOR', current_distance=275, time_boot_ms=7), 4.)

    assert [update.kind for update in updates] == ['ATTITUDE', 'ALTITUDE', 'HEARTBEAT', 'DISTANCE_SENSOR']
    assert updates[0].value.roll_rad == .1
    assert updates[1].value.local_m == 5.
    assert updates[3].value.distance_cm == 275.


def test_worker_marks_distance_sensor_sentinel_invalid():
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    worker._emit_message(Message('DISTANCE_SENSOR', current_distance=65535, time_boot_ms=7), 1.)
    assert not updates[0].value.valid
    assert updates[0].value.distance_cm is None


def test_worker_maps_status_text_and_index():
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    worker._emit_message(Message('STATUSTEXT', severity=4, text='[07] warning'), 1.)
    assert updates[0].kind == 'STATUSTEXT'
    assert updates[0].value.index == 7
    assert updates[0].value.severity == 4
    assert updates[0].value.text == '[07] warning'


def test_worker_accepts_upstream_rates_only_from_app():
    class RateMessage(Message):
        def __init__(self, name, value, source=(1, 1)):
            super().__init__('NAMED_VALUE_FLOAT', name=name.encode(), value=value)
            self.source = source

        def get_srcSystem(self):
            return self.source[0]

        def get_srcComponent(self):
            return self.source[1]

    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    worker._emit_message(RateMessage('ATT_HZ', 49.5), 1.)
    worker._emit_message(RateMessage('ALT_HZ', 48.0), 1.)
    worker._emit_message(RateMessage('ATT_HZ', 20., (9, 9)), 1.)
    assert [(update.kind, update.value) for update in updates] == [
        ('RATE', ('ATT_HZ', 49.5)), ('RATE', ('ALT_HZ', 48.0))]


def test_presenter_keeps_upstream_rates_in_snapshot():
    presenter = Presenter('test')
    presenter._on_update(TelemetryUpdate('RATE', ('ATT_HZ', 49.5), 1.))
    presenter._on_update(TelemetryUpdate('RATE', ('ALT_HZ', 48.), 1.))
    assert presenter.snapshot.attitude_hz == 49.5
    assert presenter.snapshot.altitude_hz == 48.


def test_worker_reassembles_bbox_named_values():
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    for name, value in (('BBOX_VALID', 1.), ('BBOX_X', 10.), ('BBOX_Y', 20.),
                        ('BBOX_W', 30.), ('BBOX_H', 40.)):
        worker._emit_message(Message('NAMED_VALUE_FLOAT', name=name.encode(), value=value), 1.)

    assert updates[-1].kind == 'BBOX'
    assert updates[-1].value == Bbox(True, 10., 20., 30., 40.)


def test_worker_decodes_fid_bbox_extension():
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    payload = encode_bbox(7, {'x': 1, 'y': 2, 'width': 3, 'height': 4})
    worker._emit_message(Message('V2_EXTENSION', target_network=0, target_system=255,
                                 target_component=190, message_type=MESSAGE_TYPE,
                                 payload=payload.ljust(249, b'\0')), 1.)
    assert updates[-1].value == Bbox(True, 1, 2, 3, 4, 7)
    worker._emit_message(Message('V2_EXTENSION', target_network=0, target_system=255,
                                 target_component=190, message_type=MESSAGE_TYPE,
                                 payload=b'bad'), 1.)
    assert len(updates) == 1


def test_worker_does_not_retry_after_connection_failure():
    calls = []

    def fail(endpoint):
        calls.append(endpoint)
        raise OSError('offline')

    worker = MavlinkWorker('test', connection_factory=fail)
    errors = []
    worker.failed.connect(errors.append)
    worker.run()

    assert calls == ['test']
    assert errors == ['offline']


def test_presenter_only_reports_connected_after_a_message():
    presenter = Presenter('test')
    statuses = []
    presenter.status_changed.connect(statuses.append)

    presenter._set_status('Listening for MAVLink telemetry')
    assert not presenter.snapshot.connected
    presenter._on_update(TelemetryUpdate('HEARTBEAT', None, 1.))

    assert presenter.snapshot.connected
    assert statuses[-1] == 'Connected'


def test_presenter_retains_status_messages_in_snapshot():
    presenter = Presenter('test')
    presenter._on_update(TelemetryUpdate('STATUSTEXT', StatusText(2, 4, '[02] warning', 1.), 1.))
    assert presenter.snapshot.messages[0].severity == 4


def test_vertical_speed_estimator_filters_altitude_rate_and_resets_after_gap():
    estimator = VerticalSpeedEstimator()

    assert estimator.update(10., 1.) is None
    assert estimator.update(11., 1.1) == pytest.approx(10.)
    assert estimator.update(11.5, 1.2) == pytest.approx(8.75)
    assert estimator.update(20., 3.) is None


def test_worker_parses_remote_status_context_without_arrival_time_substitution():
    from bullet_msgs.status_messages import status_text_chunks
    worker = MavlinkWorker('test')
    updates = []
    worker.update.connect(updates.append)
    for time_s, frame in [(27.075,4809),(0.,0)]:
        raw = status_text_chunks(7, 'ready', simulation_time_s=time_s,image_sequence=frame)[0].encode()
        worker._emit_message(Message('STATUSTEXT',severity=6,text=raw),1000.)
        status = updates[-1].value
        assert status.index == 7 and status.received_at_s == 1000.
        assert status.simulation_time_s == time_s and status.image_sequence == frame
        assert status.display_text == f'[{time_s:.3f} s | frame {frame}] ready'
    worker._emit_message(Message('STATUSTEXT',severity=6,text='[07] legacy'),1001.)
    assert updates[-1].value.display_text == '[— s | frame —] legacy'
