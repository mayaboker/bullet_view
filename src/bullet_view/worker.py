"""MAVLink telemetry and parameter worker; no GUI or reconnect policy belongs here."""
from threading import Event
from queue import Queue, Empty, Full
from bullet_msgs.parameters import use_mavlink2
from bullet_msgs.status_messages import parse_status_text
from .parameters import ParameterClient, GCS_SYSTEM_ID, GCS_COMPONENT_ID
from bullet_msgs.flight_control import FLIGHT_NAMES, FLIGHT_COMMANDS
from .flight_control import FlightClient, LAND_COMMAND, APP_TARGET
from bullet_msgs.mavlink_control import RECORDING_NAMES, RECORDING_CONTROL_COMMAND
from .recording_control import RecordingClient
from .peer_udp import AppPeerUDP
import time
from math import isfinite

from PySide6 import QtCore
from pymavlink import mavutil
from bullet_simulation_protocol.view_bbox import MESSAGE_TYPE, decode_bbox

from .model import Attitude, Altitude, Bbox, Heartbeat, Rangefinder, StatusText, TelemetryUpdate


RECEIVE_TIMEOUT_S = .01
GCS_HEARTBEAT_PERIOD_S = 1.0
PARAMETER_COMMAND_CAPACITY = 64
BBOX_NAMES = {'BBOX_VALID', 'BBOX_X', 'BBOX_Y', 'BBOX_W', 'BBOX_H'}
RATE_NAMES = {'ATT_HZ', 'ALT_HZ'}


class MavlinkWorker(QtCore.QObject):
    update = QtCore.Signal(object)
    connected = QtCore.Signal()
    failed = QtCore.Signal(str)
    finished = QtCore.Signal()
    command_result = QtCore.Signal(str)
    parameters_changed = QtCore.Signal(object)
    flight_changed = QtCore.Signal(object)
    flight_request_handled = QtCore.Signal(str, object)
    recording_changed = QtCore.Signal(object)

    def __init__(self, endpoint, *, connection_factory=AppPeerUDP, clock=time.monotonic):
        super().__init__()
        self.endpoint = endpoint
        self.connection_factory = connection_factory
        self.clock = clock
        self.stop_requested = Event()
        self.connection = None
        self.reload_requested = Event()
        self.bbox_values = {}
        self.parameter_commands = Queue(maxsize=PARAMETER_COMMAND_CAPACITY)
        self.parameters = ParameterClient(self.parameters_changed.emit)
        self.flight = FlightClient(self.flight_changed.emit)
        self.flight_commands = Queue(maxsize=PARAMETER_COMMAND_CAPACITY)
        self.recording = RecordingClient(self.recording_changed.emit)
        self.recording_commands = Queue(maxsize=PARAMETER_COMMAND_CAPACITY)

    def request_recording(self, start):
        try:
            self.recording_commands.put_nowait(start)
        except Full:
            self.command_result.emit('Recording request queue full')

    def _poll_recording(self):
        requests = []
        while True:
            try:
                requests.append(self.recording_commands.get_nowait())
            except Empty:
                break
        # Stop has priority over queued Start, independently of flight commands.
        selected = [False] if False in requests else requests
        for start in selected:
            try:
                if self.connection is None:
                    raise ValueError('Recording control connection unavailable')
                self.recording.request(start, self.connection.mav, self.clock())
            except ValueError as error:
                self.command_result.emit(str(error))
        self.recording.poll(self.clock())

    def request_flight(self, action, value=None):
        try:
            self.flight_commands.put_nowait((action, value))
        except Full:
            self.command_result.emit('Flight request queue full')
            return False
        return True

    def _poll_flight(self):
        commands = []
        while True:
            try:
                commands.append(self.flight_commands.get_nowait())
            except Empty:
                break
        disarms = [c for c in commands if c[0] in ('disarm', 'emergency')]
        emergencies = [c for c in disarms if c[0] == 'emergency']
        selected = (emergencies or disarms)[-1:] if disarms else commands
        for action, value in selected:
            try:
                if self.connection is None:
                    raise ValueError('Flight control connection unavailable')
                self.flight.request(action, value, self.connection.mav, self.clock())
            except ValueError as error:
                self.command_result.emit(str(error))
                self.flight.result = str(error)
                self.flight.notify()
            self.flight_request_handled.emit(action, self.flight.snapshot())
        self.flight.poll(self.clock())

    def request_stop(self):
        self.stop_requested.set()

    def request_reload(self):
        self.reload_requested.set()

    def request_parameters(self):
        self._queue_parameter_command(('refresh', None, None))

    def set_parameter(self, id, value):
        self._queue_parameter_command(('set', id, value))

    def _queue_parameter_command(self, command):
        try:
            self.parameter_commands.put_nowait(command)
        except Full:
            self.command_result.emit('Parameter request queue full; try again shortly')

    def _poll_parameters(self):
        if self.connection is None:
            return
        mav = self.connection.mav
        try:
            action, id, value = self.parameter_commands.get_nowait()
        except Empty:
            pass
        else:
            try:
                if action == 'refresh':
                    self.parameters.refresh(mav, self.clock())
                else:
                    self.parameters.set(mav, id, value, self.clock())
            except (ValueError, KeyError) as exc:
                self.command_result.emit(str(exc))
        self.parameters.poll(mav, self.clock())

    @QtCore.Slot()
    def run(self):
        try:
            self.connection = self.connection_factory(self.endpoint)
            use_mavlink2(self.connection, GCS_SYSTEM_ID, GCS_COMPONENT_ID)
            self.recording.set_available(False)
            self.flight.set_available(True)
            self.connected.emit()
            next_heartbeat = self.clock()
            while not self.stop_requested.is_set():
                now = self.clock()
                if getattr(self.connection, 'peer', None) is not None and now >= next_heartbeat:
                    self.connection.mav.heartbeat_send(
                        mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                        0, 0, mavutil.mavlink.MAV_STATE_ACTIVE, 3)
                    next_heartbeat = now + GCS_HEARTBEAT_PERIOD_S
                self._poll_flight()
                message = self.connection.recv_match(
                    type=['HEARTBEAT', 'ATTITUDE', 'ALTITUDE', 'DISTANCE_SENSOR', 'STATUSTEXT',
                          'NAMED_VALUE_FLOAT', 'COMMAND_ACK', 'V2_EXTENSION'],
                    blocking=True,
                    timeout=RECEIVE_TIMEOUT_S,
                )
                if message is not None:
                    if (message.get_srcSystem(), message.get_srcComponent()) != APP_TARGET:
                        continue
                    if hasattr(self.connection, 'select_sender'):
                        self.connection.select_sender()
                    received_at = self.clock()
                    if message.get_type() == 'COMMAND_ACK':
                        if message.command in FLIGHT_COMMANDS | {LAND_COMMAND}:
                            self.flight.ack(message, received_at)
                    else:
                        self._emit_message(message, received_at)
        except Exception as error:
            if not self.stop_requested.is_set():
                self.failed.emit(str(error))
        finally:
            self.flight.offline()
            self.recording.offline()
            self.parameters.online = self.parameters.complete = False
            self.parameters.emit()
            try:
                if self.connection is not None:
                    try:
                        self.connection.close()
                    except OSError as error:
                        self.failed.emit(f'MAVLink close failed: {error}')
            finally:
                self.finished.emit()

    def _emit_message(self, message, received_at_s):
        kind = message.get_type()
        if kind == 'HEARTBEAT':
            value = Heartbeat(getattr(message, 'base_mode', 0),
                              getattr(message, 'custom_mode', 0),
                              getattr(message, 'system_status', 0), received_at_s)
        elif kind == 'ATTITUDE':
            value = Attitude(message.roll, message.pitch, message.yaw, message.time_boot_ms)
        elif kind == 'ALTITUDE':
            value = Altitude(message.altitude_local, message.time_usec)
        elif kind == 'DISTANCE_SENSOR':
            # MAVLink names this wire field ``current_distance``; the units are cm.
            distance_cm = getattr(message, 'current_distance',
                                  getattr(message, 'current_distance_cm', 65535))
            value = Rangefinder(None if distance_cm == 65535 else float(distance_cm),
                                message.time_boot_ms, distance_cm != 65535)
        elif kind == 'STATUSTEXT':
            raw_text = message.text.decode('utf-8', errors='replace') if isinstance(message.text, bytes) else message.text
            parsed = parse_status_text(raw_text)
            value = StatusText(parsed.index, message.severity, raw_text, received_at_s,
                               parsed.simulation_time_s, parsed.image_sequence)
        elif kind == 'NAMED_VALUE_FLOAT':
            raw_name = message.name.decode('ascii', errors='ignore') if isinstance(message.name, bytes) else message.name
            name = str(raw_name).rstrip('\0')
            if name in RATE_NAMES:
                if ((message.get_srcSystem(), message.get_srcComponent()) == APP_TARGET
                        and isfinite(float(message.value)) and float(message.value) >= 0):
                    self.update.emit(TelemetryUpdate('RATE', (name, float(message.value)), received_at_s))
                return
            if name in FLIGHT_NAMES or name in ('APP_MODE', 'APP_PHASE', 'APP_MSN', 'APP_RESULT', 'VIS_READY'):
                self.flight.named(message, name, received_at_s)
                return
            if name in RECORDING_NAMES:
                self.recording.named(message, name, received_at_s)
                return
            if name not in BBOX_NAMES:
                return
            self.bbox_values[name] = float(message.value)
            valid = self.bbox_values.get('BBOX_VALID', 0.) > .5
            coordinates = tuple(self.bbox_values.get(name) for name in ('BBOX_X', 'BBOX_Y', 'BBOX_W', 'BBOX_H'))
            value = Bbox(valid, *coordinates) if valid and all(
                item is not None and isfinite(item) for item in coordinates
            ) else Bbox(False)
            kind = 'BBOX'
        elif kind == 'V2_EXTENSION':
            if (message.target_network != 0 or message.target_system != GCS_SYSTEM_ID
                    or message.target_component != GCS_COMPONENT_ID
                    or message.message_type != MESSAGE_TYPE):
                return
            try:
                packet = decode_bbox(message.payload)
            except ValueError:
                return
            box = packet['bbox']
            value = Bbox(False, fid=packet['fid']) if box is None else Bbox(
                True, box['x'], box['y'], box['width'], box['height'], packet['fid'])
            kind = 'BBOX'
        else:
            return
        self.update.emit(TelemetryUpdate(kind, value, received_at_s))
