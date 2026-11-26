"""MVP presenter connecting MAVLink updates to the view."""
from dataclasses import replace
import os
import signal as _signal
import subprocess
import time

from PySide6 import QtCore
from pymavlink import mavutil

from .model import TelemetrySnapshot
from .parameters import ParameterSnapshot, save_yaml
from .worker import MavlinkWorker
from .image_stream import ImageWorker, FrameMatcher
from .flight_control import FlightSnapshot, flight_action_block_reason, app_restart_block_reason
from .simulation_control import SimulationSnapshot, SimulationWorker, STATE_STALE_S
from bullet_simulation_protocol.state import DEFAULT_CONTROL_ENDPOINT, DEFAULT_STATE_ENDPOINT


STALE_AFTER_S = .75
HEARTBEAT_STALE_S = 3.0
SITL_CONFIRMED_CUSTOM_MODE = 1 << 0
VIEW_REFRESH_PERIOD_MS = 100
VERTICAL_SPEED_FILTER_ALPHA = .25
VERTICAL_SPEED_RESET_GAP_S = 1.


class VerticalSpeedEstimator:
    def __init__(self, *, alpha=VERTICAL_SPEED_FILTER_ALPHA, reset_gap_s=VERTICAL_SPEED_RESET_GAP_S):
        self.alpha = alpha
        self.reset_gap_s = reset_gap_s
        self.previous_altitude_m = None
        self.previous_received_at_s = None
        self.filtered_speed_m_s = None

    def reset(self):
        self.previous_altitude_m = None
        self.previous_received_at_s = None
        self.filtered_speed_m_s = None

    def update(self, altitude_m, received_at_s):
        previous_altitude_m = self.previous_altitude_m
        previous_received_at_s = self.previous_received_at_s
        self.previous_altitude_m = altitude_m
        self.previous_received_at_s = received_at_s
        if previous_altitude_m is None or previous_received_at_s is None:
            self.filtered_speed_m_s = None
            return None
        delta_s = received_at_s - previous_received_at_s
        if delta_s <= 0 or delta_s > self.reset_gap_s:
            self.filtered_speed_m_s = None
            return None
        raw_speed_m_s = (altitude_m - previous_altitude_m) / delta_s
        if self.filtered_speed_m_s is None:
            self.filtered_speed_m_s = raw_speed_m_s
        else:
            self.filtered_speed_m_s += self.alpha * (raw_speed_m_s - self.filtered_speed_m_s)
        return self.filtered_speed_m_s


class _AppResetThread(QtCore.QThread):
    result = QtCore.Signal(str, str)

    def __init__(self, launch_script, mission, current_process, tty_path=None):
        super().__init__()
        self.launch_script = launch_script
        self.mission = mission
        self.current_process = current_process
        self.tty_path = tty_path
        self.new_process = None

    def run(self):
        self.tty_path = self._find_tty() or self.tty_path
        try:
            self._kill_existing()
        except Exception:
            pass
        time.sleep(0.5)
        tty_fd = None
        try:
            if self.tty_path:
                try:
                    tty_fd = os.open(self.tty_path, os.O_WRONLY)
                except OSError:
                    tty_fd = None
            kwargs = {}
            if tty_fd is not None:
                kwargs['stdout'] = tty_fd
                kwargs['stderr'] = tty_fd
            self.new_process = subprocess.Popen(
                ['bash', self.launch_script, self.mission],
                start_new_session=True,
                **kwargs,
            )
            self.result.emit('success', 'App process restarted')
        except Exception as exc:
            self.result.emit('failure', str(exc))
        finally:
            if tty_fd is not None:
                os.close(tty_fd)

    def _find_tty(self):
        if self.current_process is not None and self.current_process.poll() is None:
            try:
                return os.readlink(f'/proc/{self.current_process.pid}/fd/1')
            except OSError:
                pass
        for pattern in ('bullet-app --mode', 'bash.*run_app_after_sitl'):
            try:
                result = subprocess.run(['pgrep', '-f', pattern],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    pid = result.stdout.strip().split('\n')[0]
                    return os.readlink(f'/proc/{pid}/fd/1')
            except (OSError, subprocess.TimeoutExpired, IndexError):
                pass
        return None

    def _kill_existing(self):
        if self.current_process is not None and self.current_process.poll() is None:
            try:
                os.killpg(os.getpgid(self.current_process.pid), _signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
            try:
                self.current_process.wait(timeout=5)
                return
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(self.current_process.pid), _signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
                return
        for pattern in ('bullet-app --mode', 'bash.*run_app_after_sitl'):
            subprocess.run(['pkill', '-f', pattern], capture_output=True, timeout=5)


class Presenter(QtCore.QObject):
    snapshot_changed = QtCore.Signal(object)
    status_changed = QtCore.Signal(str)
    messages_cleared = QtCore.Signal()
    parameters_changed = QtCore.Signal(object)
    flight_changed = QtCore.Signal(object)
    simulation_changed = QtCore.Signal(object)
    simulation_result = QtCore.Signal(str, str, str)
    app_restart_result = QtCore.Signal(str, str)
    app_reset_result = QtCore.Signal(str, str)

    def __init__(self, endpoint, *, image_mode='remote', image_endpoint=None,
                 worker_factory=MavlinkWorker, image_worker_factory=ImageWorker,
                 simulation_control_endpoint=DEFAULT_CONTROL_ENDPOINT,
                 simulation_state_endpoint=DEFAULT_STATE_ENDPOINT,
                 simulation_worker_factory=SimulationWorker,
                 app_launch_script=None, app_mission=None,
                 clock=time.monotonic):
        super().__init__()
        self.endpoint = endpoint
        self._app_launch_script = app_launch_script
        self._app_mission = app_mission
        self._app_process = None
        self._app_tty_path = None
        self._app_reset_thread = None
        self.worker_factory = worker_factory
        self.clock = clock
        self._heartbeat_wait_started_s = clock()
        self._app_heartbeat_stale = False
        self.image_mode = 'local' if image_endpoint else image_mode
        self.matcher = FrameMatcher() if image_endpoint else None
        self.image_thread = QtCore.QThread(self) if image_endpoint else None
        self.image_worker = image_worker_factory(image_endpoint) if image_endpoint else None
        if self.image_worker is not None:
            self.image_worker.moveToThread(self.image_thread)
            self.image_thread.started.connect(self.image_worker.run)
            self.image_worker.frame.connect(self._on_frame)
            self.image_worker.failed.connect(self._set_status)
            self.image_worker.finished.connect(self.image_thread.quit)
            self.image_thread.finished.connect(self.image_worker.deleteLater)
        self.snapshot = TelemetrySnapshot()
        self.parameter_snapshot = ParameterSnapshot()
        self.flight_snapshot = FlightSnapshot()
        self.simulation_snapshot = SimulationSnapshot()
        self._simulation_received_at_s = None
        self.simulation_thread = QtCore.QThread(self)
        self.simulation_worker = simulation_worker_factory(simulation_control_endpoint,
                                                            simulation_state_endpoint)
        self.simulation_worker.moveToThread(self.simulation_thread)
        self.simulation_thread.started.connect(self.simulation_worker.run)
        self.simulation_worker.observed.connect(self._on_simulation_state)
        self.simulation_worker.result.connect(self._on_simulation_result)
        self.simulation_worker.failed.connect(self._on_simulation_failure)
        self.simulation_worker.finished.connect(self.simulation_thread.quit)
        self.simulation_thread.finished.connect(self.simulation_worker.deleteLater)
        self._queued_flight_action = None
        self._app_restart_requested = False
        self._export_destination = None
        self._export_sync_started = False
        self.vertical_speed = VerticalSpeedEstimator()
        self.thread = QtCore.QThread(self)
        self.worker = worker_factory(endpoint)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.update.connect(self._on_update)
        self.worker.connected.connect(lambda: self._set_status('Listening for MAVLink telemetry'))
        self.worker.failed.connect(self._on_failure)
        self.worker.command_result.connect(self._set_status)
        if hasattr(self.worker, 'parameters_changed'):
            self.worker.parameters_changed.connect(self._on_parameters)
        if hasattr(self.worker, 'flight_changed'):
            self.worker.flight_changed.connect(self._on_flight)
        if hasattr(self.worker, 'flight_request_handled'):
            self.worker.flight_request_handled.connect(self._on_flight_request_handled)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(VIEW_REFRESH_PERIOD_MS)
        self.timer.timeout.connect(self._refresh_freshness)

    def start(self):
        self._heartbeat_wait_started_s = self.clock()
        self.thread.start()
        self.simulation_thread.start()
        if self.image_thread is not None:
            self.image_thread.start()
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self.worker.request_stop()
        self.simulation_worker.request_stop()
        if self.image_worker is not None:
            self.image_worker.request_stop()
        if self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(2000)
        if self.simulation_thread.isRunning():
            self.simulation_thread.quit()
            self.simulation_thread.wait(2000)
        if self.image_thread is not None and self.image_thread.isRunning():
            self.image_thread.quit()
            self.image_thread.wait(2000)
        if self._app_reset_thread is not None and self._app_reset_thread.isRunning():
            self._app_reset_thread.wait(2000)

    def set_image_mode(self, mode):
        if mode != self.image_mode:
            raise ValueError('Image mode is fixed by the configured local camera endpoint')

    @QtCore.Slot(object)
    def _on_frame(self, frame):
        result = self.matcher.add_frame(frame, self.clock()) if self.matcher else (frame, None)
        if result is not None:
            self.snapshot = replace(self.snapshot, image=result[0], bbox=result[1])
            self.snapshot_changed.emit(self.snapshot)

    @QtCore.Slot(object)
    def _on_parameters(self, snapshot):
        self.parameter_snapshot = snapshot
        self.parameters_changed.emit(snapshot)
        if self._export_destination is not None:
            if snapshot.failed or not snapshot.online:
                self._export_destination = None
                self._set_status('Export cancelled: profile synchronization failed')
            elif not snapshot.complete:
                self._export_sync_started = True
            elif self._export_sync_started:
                destination, self._export_destination = self._export_destination, None
                try:
                    save_yaml(snapshot, destination)
                except (ValueError, OSError) as exc:
                    self._set_status('Export failed: ' + str(exc))
                else:
                    self._set_status('Confirmed mission profile exported')

    def refresh_parameters(self):
        self.worker.request_parameters()

    @QtCore.Slot(object)
    def _on_flight(self, snapshot):
        if not snapshot.control_available:
            self._queued_flight_action = None
        if self._queued_flight_action is not None:
            # Telemetry queued before the command was processed must not unlock buttons.
            snapshot = replace(snapshot, pending=self._queued_flight_action,
                result=f'{self._queued_flight_action}: request queued; waiting for remote confirmation')
        self.flight_snapshot = snapshot
        self.flight_changed.emit(snapshot)
        if (getattr(self, '_app_restart_requested', False) and snapshot.pending is None and
                self._queued_flight_action is None):
            self._app_restart_requested = False
            self.app_restart_result.emit(
                'success' if snapshot.result == 'restart: App ready and disarmed' else 'failure',
                snapshot.result)

    @QtCore.Slot(str, object)
    def _on_flight_request_handled(self, action, snapshot):
        if self._queued_flight_action == action:
            self._queued_flight_action = None
        self._on_flight(snapshot)

    def request_flight(self, action, value=None):
        if action in ('arm', 'start'):
            reason = flight_action_block_reason(self.flight_snapshot, action, value, now=self.clock())
            if reason is not None:
                self._set_status(reason)
                return
        # Disable conflicting actions immediately; observed vehicle state stays unchanged.
        previous = self.flight_snapshot
        previous_queued = self._queued_flight_action
        self._queued_flight_action = action
        self._on_flight(replace(previous, pending=action,
                               result=f'{action}: request queued; waiting for remote confirmation'))
        if self.worker.request_flight(action, value) is False:
            self._queued_flight_action = previous_queued
            if action == 'restart':
                self._app_restart_requested = False
            self._on_flight(previous)
            return False
        return True

    def request_app_restart(self):
        simulation = self.simulation_snapshot
        if (not simulation.fresh or simulation.pending is not None or
                simulation.state is None or simulation.state.state != 'stopped_ready'):
            return False
        reason = app_restart_block_reason(self.flight_snapshot, self.clock())
        if reason is not None:
            self._set_status(reason)
            return False
        self._app_restart_requested = True
        return self.request_flight('restart')

    @property
    def app_reset_available(self):
        return self._app_launch_script is not None and self._app_mission is not None

    def request_app_reset(self):
        if not self.app_reset_available:
            return False
        if self._app_reset_thread is not None and self._app_reset_thread.isRunning():
            return False
        self._app_reset_thread = _AppResetThread(
            self._app_launch_script, self._app_mission, self._app_process,
            self._app_tty_path)
        self._app_reset_thread.result.connect(self._on_app_reset_result)
        self._app_reset_thread.start()
        return True

    @QtCore.Slot(str, str)
    def _on_app_reset_result(self, outcome, reason):
        if self._app_reset_thread is not None:
            self._app_process = self._app_reset_thread.new_process
            if self._app_reset_thread.tty_path:
                self._app_tty_path = self._app_reset_thread.tty_path
            self._app_reset_thread = None
        self.app_reset_result.emit(outcome, reason)

    def request_simulation(self, action):
        allowed = {'running': ('stop',), 'stopped_reset_required': ('reset',),
                   'stopped_ready': ('start', 'reset'), 'error': ('reset',)}
        snapshot = self.simulation_snapshot
        state = snapshot.state.state if snapshot.state else None
        if not snapshot.fresh or snapshot.pending is not None or action not in allowed.get(state, ()):
            return False
        self.simulation_snapshot = replace(snapshot, pending=action)
        self.simulation_changed.emit(self.simulation_snapshot)
        if not self.simulation_worker.request(action):
            self.simulation_snapshot = replace(snapshot, pending=None)
            self.simulation_changed.emit(self.simulation_snapshot)
            return False
        return True

    @QtCore.Slot(object, float)
    def _on_simulation_state(self, state, received_at_s):
        current = self.simulation_snapshot.state
        if current is not None and current.session_id == state.session_id and state.revision < current.revision:
            return
        self._simulation_received_at_s = received_at_s
        self.simulation_snapshot = replace(self.simulation_snapshot, state=state, fresh=True)
        self.simulation_changed.emit(self.simulation_snapshot)

    @QtCore.Slot(str, str, str)
    def _on_simulation_result(self, action, outcome, reason):
        if self.simulation_snapshot.pending == action:
            # Wait for a new publication before allowing another action.
            self.simulation_snapshot = replace(self.simulation_snapshot, pending=None, fresh=False)
            self.simulation_changed.emit(self.simulation_snapshot)
        self.simulation_result.emit(action, outcome, reason)

    @QtCore.Slot(str)
    def _on_simulation_failure(self, reason):
        pending = self.simulation_snapshot.pending
        self.simulation_snapshot = replace(self.simulation_snapshot, pending=None, fresh=False)
        self.simulation_changed.emit(self.simulation_snapshot)
        if pending is not None:
            self.simulation_result.emit(pending, 'failure', reason)

    def apply_parameter(self, id, value):
        self.worker.set_parameter(id, value)

    def export_parameters(self, path):
        snapshot = self.parameter_snapshot
        if not snapshot.complete or not snapshot.online or snapshot.pending:
            raise ValueError('Load a complete current profile and resolve pending edits before export')
        self._export_destination = path
        self._export_sync_started = False
        self.worker.request_parameters()
        self._set_status('Refreshing remote profile before YAML export…')

    def clear_messages(self):
        """Discard local session history; incoming telemetry continues normally."""
        self.snapshot = replace(self.snapshot, messages=())
        self.messages_cleared.emit()
        self.snapshot_changed.emit(self.snapshot)

    def request_reload(self):
        if self.snapshot.mission_stopped:
            self.worker.request_reload()
        else:
            self._set_status('Profile reload requires stopped mission')

    @QtCore.Slot(object)
    def _on_update(self, update):
        first_message = not self.snapshot.connected
        was_heartbeat_stale = self._app_heartbeat_stale
        if self.snapshot.error is not None:
            self._heartbeat_wait_started_s = update.received_at_s
        values = dict(connected=True, last_message_at_s=update.received_at_s,
                      error=None)
        if update.kind == 'HEARTBEAT':
            self._app_heartbeat_stale = False
            values['heartbeat_at_s'] = update.received_at_s
            values['heartbeat'] = update.value
            values['sitl_confirmed'] = (None if update.value is None else
                                        bool(update.value.custom_mode & SITL_CONFIRMED_CUSTOM_MODE))
            values['mission_stopped'] = (update.value is not None
                                          and update.value.system_status != mavutil.mavlink.MAV_STATE_ACTIVE)
        elif update.kind == 'ATTITUDE':
            values['attitude'] = update.value
        elif update.kind == 'ALTITUDE':
            values['altitude'] = update.value
            values['vertical_speed_m_s'] = self.vertical_speed.update(
                update.value.local_m, update.received_at_s)
        elif update.kind == 'DISTANCE_SENSOR':
            values['rangefinder'] = update.value
        elif update.kind == 'STATUSTEXT':
            values['messages'] = self.snapshot.messages + (update.value,)
        elif update.kind == 'RATE':
            name, hz = update.value
            values['attitude_hz' if name == 'ATT_HZ' else 'altitude_hz'] = hz
        elif update.kind == 'BBOX':
            if self.matcher is not None and update.value.fid is not None:
                result = self.matcher.add_bbox(update.value, update.received_at_s)
                if result is not None:
                    values['image'], values['bbox'] = result
        self.snapshot = replace(self.snapshot, **values)
        if (first_message or was_heartbeat_stale) and update.kind == 'HEARTBEAT':
            self._set_status('Connected')
        elif first_message and not self._app_heartbeat_stale:
            self._set_status('Connected')
        self.snapshot_changed.emit(self.snapshot)

    @QtCore.Slot(str)
    def _on_failure(self, message):
        self.vertical_speed.reset()
        self._app_heartbeat_stale = False
        self.snapshot = replace(self.snapshot, connected=False, error=message, rangefinder=None,
                                attitude_hz=None, altitude_hz=None, sitl_confirmed=None)
        self._set_status('Disconnected: ' + message)
        self.snapshot_changed.emit(self.snapshot)

    def _refresh_freshness(self):
        now = self.clock()
        if (self.simulation_snapshot.fresh and self._simulation_received_at_s is not None
                and now - self._simulation_received_at_s > STATE_STALE_S):
            self.simulation_snapshot = replace(self.simulation_snapshot, fresh=False)
            self.simulation_changed.emit(self.simulation_snapshot)
        heartbeat_reference = (self.snapshot.heartbeat_at_s if self.snapshot.heartbeat_at_s is not None
                               else self._heartbeat_wait_started_s)
        if self.snapshot.error is None and now - heartbeat_reference > HEARTBEAT_STALE_S:
            if not self._app_heartbeat_stale:
                self._app_heartbeat_stale = True
                self._set_status('Telemetry stale')
            if self.snapshot.sitl_confirmed is not None:
                self.snapshot = replace(self.snapshot, sitl_confirmed=None)
                self.snapshot_changed.emit(self.snapshot)
        if self.matcher is not None:
            result = self.matcher.fallback(now)
            if result is not None:
                self.snapshot = replace(self.snapshot, image=result[0], bbox=None)
                self.snapshot_changed.emit(self.snapshot)
        if self.snapshot.last_message_at_s is None:
            return
        age = now - self.snapshot.last_message_at_s
        if age > STALE_AFTER_S and self.snapshot.connected:
            self.vertical_speed.reset()
            self.snapshot = replace(self.snapshot, connected=False, vertical_speed_m_s=None, rangefinder=None,
                                    attitude_hz=None, altitude_hz=None, sitl_confirmed=None)
            self._set_status('Telemetry stale')
            self.snapshot_changed.emit(self.snapshot)

    def _set_status(self, message):
        self.status_changed.emit('Telemetry stale' if getattr(self, '_app_heartbeat_stale', False) else message)
