"""Worker-owned recording commands and immutable remote recording state."""
from dataclasses import dataclass, replace
from bullet_msgs.mavlink_control import (RECORDING_CONTROL_COMMAND, RECORDING_NAMES,
    RECORDING_AUTH_MAVLINK, RECORDING_STATES, RECORDING_ACK_START, RECORDING_ACK_STOP,
    RECORDING_TELEMETRY_STALE_S)
from bullet_msgs.recording_control import REQUEST_TIMEOUT_S
from .flight_control import APP_TARGET
from .parameters import GCS_SYSTEM_ID, GCS_COMPONENT_ID


@dataclass(frozen=True)
class RecordingSnapshot:
    authority: int = 0
    state: str = 'unknown'
    online: bool = False
    target: tuple | None = None
    received_at_s: float = float('-inf')
    pending: str | None = None
    result: str = 'Waiting for recording telemetry'
    control_available: bool = True


class RecordingClient:
    def __init__(self, emit):
        self.emit = emit
        self.snapshot = RecordingSnapshot()
        self.pending = None
        self.stamp = None
        self.parts = {}

    def notify(self):
        self.snapshot = replace(self.snapshot,
            pending=None if self.pending is None else self.pending['action'])
        self.emit(self.snapshot)

    def set_available(self, available):
        self.snapshot = replace(self.snapshot, control_available=available)
        self.notify()

    def named(self, message, name, now):
        if (message.get_srcSystem(), message.get_srcComponent()) != APP_TARGET:
            return
        stamp = message.time_boot_ms
        if self.stamp is not None and (stamp - self.stamp) % 2**32 >= 2**31:
            return
        if stamp != self.stamp:
            self.stamp, self.parts = stamp, {}
        self.parts[name] = float(message.value)
        if set(self.parts) != set(RECORDING_NAMES):
            return
        authority, state = self.parts['REC_AUTH'], self.parts['REC_STATE']
        if authority not in (0, 1, 2) or state not in RECORDING_STATES.values():
            return
        state_name = next(key for key, value in RECORDING_STATES.items() if value == state)
        self.snapshot = replace(self.snapshot, authority=int(authority), state=state_name,
                                online=True, target=APP_TARGET, received_at_s=now)
        self._complete(now)
        self.notify()

    def request(self, start, mav, now):
        remote = self.snapshot
        if not remote.control_available or remote.target is None or remote.authority != RECORDING_AUTH_MAVLINK:
            raise ValueError('Recording is not controlled by MAVLink')
        if start:
            if self.pending is not None or not remote.online or now - remote.received_at_s > RECORDING_TELEMETRY_STALE_S:
                raise ValueError('Fresh recording state required; resolve pending command')
            if remote.state not in ('idle', 'error'):
                raise ValueError('Recorder is not idle')
        elif self.pending is not None and self.pending['action'] == 'stop':
            raise ValueError('Recording Stop already pending')
        # Stop replaces Start immediately. Neither command is retried automatically.
        action = 'start' if start else 'stop'
        self.pending = dict(action=action, issued=now, ack=False,
            action_id=RECORDING_ACK_START if start else RECORDING_ACK_STOP)
        self.snapshot = replace(remote, result=f'Recording {action}: waiting for remote confirmation')
        mav.command_long_send(*APP_TARGET, RECORDING_CONTROL_COMMAND, 0, float(start), 0., 0., 0., 0., 0., 0.)
        self.notify()

    def ack(self, message, now):
        pending = self.pending
        if (pending is None or message.command != RECORDING_CONTROL_COMMAND
                or (message.get_srcSystem(), message.get_srcComponent()) != APP_TARGET
                or getattr(message, 'target_system', 0) != GCS_SYSTEM_ID
                or getattr(message, 'target_component', 0) != GCS_COMPONENT_ID):
            return
        action_id = getattr(message, 'result_param2', 0)
        if action_id != pending['action_id'] and not (action_id == 0 and message.result not in (0, 5)):
            return
        if message.result == 5:
            return
        if message.result != 0:
            self.snapshot = replace(self.snapshot, result=f"Recording {pending['action']}: rejected/failed (ACK {message.result})")
            self.pending = None
        else:
            pending['ack'] = True
            self.snapshot = replace(self.snapshot, result='ACK accepted; waiting for recorder state')
            self._complete(now)
        self.notify()

    def _complete(self, now):
        pending, remote = self.pending, self.snapshot
        if (pending is not None and pending['ack'] and remote.online
                and 0 <= now - remote.received_at_s <= RECORDING_TELEMETRY_STALE_S
                and remote.received_at_s > pending['issued']
                and remote.state == ('recording' if pending['action'] == 'start' else 'idle')):
            text = 'Recording started (remote confirmed)' if pending['action'] == 'start' else 'Recording stopped; MCAP finalized (remote confirmed)'
            self.snapshot = replace(remote, result=text)
            self.pending = None

    def poll(self, now):
        changed = False
        if self.snapshot.online and now - self.snapshot.received_at_s > RECORDING_TELEMETRY_STALE_S:
            self.snapshot = replace(self.snapshot, state='unknown', online=False)
            changed = True
        if self.pending is not None and now - self.pending['issued'] >= REQUEST_TIMEOUT_S + RECORDING_TELEMETRY_STALE_S:
            self.snapshot = replace(self.snapshot, result='Recording command timed out; remote outcome unknown')
            self.pending = None
            changed = True
        if changed:
            self.notify()

    def offline(self):
        self.pending = None
        self.snapshot = replace(self.snapshot, online=False, state='unknown',
                                control_available=False, result='Recording control connection unavailable')
        self.notify()
