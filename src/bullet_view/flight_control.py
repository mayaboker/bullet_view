"""Worker-owned flight protocol client; no widgets or flight inference."""
from dataclasses import dataclass
from math import isfinite
from .flight_protocol import (FlightState, FLIGHT_NAMES, ARM_DISARM_COMMAND,
    MISSION_START_COMMAND, TAKEOFF_HEIGHT_COMMAND, FORCE_DISARM_MAGIC, COMMAND_TIMEOUT_S,
    STATE_STALE_S, HEIGHT_TOLERANCE_M, MIN_TAKEOFF_HEIGHT_M, MAX_TAKEOFF_HEIGHT_M,
    DISARMED_IDLE, ARMED_IDLE, FLYING, RESET_REQUIRED, ACTION_IDS, Readiness, parse_command)
from .flight_protocol import APP_RESTART_COMMAND, APP_STATES
from .parameters import GCS_SYSTEM_ID, GCS_COMPONENT_ID

APP_TARGET = (1, 1)
NO_COMMAND_RESULT = 'No flight command sent'
LAND_COMMAND = 21
VIEW_ACTION_IDS = {**ACTION_IDS, 'land': 6, 'restart': 0}
PHASE_NAMES = ('prearm', 'disarmed', 'arming', 'armed', 'takeoff', 'hover', 'land',
               'disarming', 'fault', 'search', 'center', 'settle', 'los', 'commit')
MISSION_NAMES = {1.: 'hover-land', 2.: 'target-hit'}
RESULT_NAMES = {0.: 'pending', 1.: 'hit', 2.: 'failed'}


@dataclass(frozen=True)
class FlightSnapshot:
    remote: FlightState = FlightState()
    pending: str | None = None
    result: str = NO_COMMAND_RESULT
    control_available: bool = True
    mode: str = 'manual'
    phase: str = 'unknown'
    mission: str = 'unknown'
    mission_result: str = 'pending'
    vision_ready: bool = False
    hover_s: float | None = None
    app_state: str = 'unknown'
    app_epoch: int | None = None
    app_status_at_s: float = float('-inf')


def app_restart_block_reason(snapshot, now):
    if not snapshot.control_available or snapshot.mode != 'manual':
        return 'Manual App connection required'
    if snapshot.pending is not None:
        return 'Flight command pending'
    if snapshot.app_state not in ('ready', 'restart_required', 'restart_failed'):
        return 'App restart unavailable'
    if not 0 <= now - snapshot.app_status_at_s <= STATE_STALE_S:
        return 'App status is stale'
    if snapshot.remote.valid and snapshot.remote.armed:
        return 'Disarm before restart'
    return None


def flight_action_block_reason(snapshot, action, height_m=None, *, now=None):
    """Shared UI/dispatch gate; None means this action is currently available."""
    remote = snapshot.remote
    if not snapshot.control_available:
        return 'Flight control connection unavailable'
    if remote.target != APP_TARGET:
        return 'Waiting for the application target'
    if (not remote.valid or remote.armed is None or
            (now is not None and not 0 <= now - remote.received_at_s <= STATE_STALE_S)):
        return 'Waiting for fresh arming feedback'
    if snapshot.pending is not None:
        return f'Waiting for {snapshot.pending} confirmation'
    if snapshot.mission == 'target-hit' and snapshot.mission_result != 'pending' and action in ('arm', 'start', 'height'):
        return 'Target mission completed; restart App and launcher'
    if remote.readiness == RESET_REQUIRED:
        return 'Stop/reset required before arming'
    if remote.readiness == FLYING and action != 'land':
        return 'Mission already active'
    if snapshot.mode not in ('auto', 'manual'):
        return 'Waiting for App mode'
    if action in ('arm', 'start') and snapshot.mode == 'auto':
        return 'App starts this mission automatically'
    if action == 'arm':
        if remote.armed is not False:
            return 'Vehicle is already armed'
        if remote.readiness != DISARMED_IDLE:
            return 'Waiting for remote prearm readiness'
    elif action == 'start':
        if remote.armed is not True or remote.readiness != ARMED_IDLE:
            return 'Arm and wait for confirmed armed idle'
        if (type(remote.height_m) not in (float, int) or not isfinite(remote.height_m)
                or not MIN_TAKEOFF_HEIGHT_M <= remote.height_m <= MAX_TAKEOFF_HEIGHT_M):
            return 'Mission profile has an invalid height'
    elif action == 'land':
        if remote.readiness != FLYING or snapshot.phase not in ('takeoff', 'hover', 'search',
                                                                 'center', 'settle', 'los', 'commit'):
            return 'Active flight required to land'
    elif action == 'height':
        if snapshot.mode != 'manual' or snapshot.mission != 'target-hit':
            return 'Height requires manual target mission'
        if remote.readiness not in (DISARMED_IDLE, ARMED_IDLE):
            return 'Height requires idle flight before Start'
    else:
        raise ValueError('Unknown flight availability action')
    return None


class FlightClient:
    def __init__(self, emit):
        self.emit = emit
        self.remote = FlightState()
        self.pending = None
        self.result = NO_COMMAND_RESULT
        self.parts = {}
        self.stamp = None
        self.known_target = None
        self.control_available = True
        self.mode = 'unknown'
        self.phase = 'unknown'
        self.mission = 'unknown'
        self.mission_result = 'pending'
        self.vision_ready = False
        self.hover_s = None
        self.app_state = 'unknown'
        self.app_epoch = None
        self.app_status_at_s = float('-inf')

    def snapshot(self):
        return FlightSnapshot(self.remote, None if self.pending is None else self.pending['action'], self.result,
                              self.control_available, self.mode, self.phase, self.mission, self.mission_result,
                              self.vision_ready, self.hover_s, self.app_state,
                              self.app_epoch, self.app_status_at_s)

    def set_available(self, available):
        self.control_available = available
        self.notify()

    def notify(self):
        self.emit(self.snapshot())

    def named(self, message, name, now):
        target = message.get_srcSystem(), message.get_srcComponent()
        if target != APP_TARGET:
            return
        if name == 'APP_STATE':
            self.app_state = APP_STATES.get(float(message.value), 'unknown')
            self.app_status_at_s = now
            self._complete(now)
            self.notify()
            return
        if name == 'APP_EPOCH':
            value = float(message.value)
            self.app_epoch = int(value) if isfinite(value) and value.is_integer() and value >= 0 else None
            self._complete(now)
            self.notify()
            return
        if name == 'APP_MODE':
            self.mode = {0.: 'auto', 1.: 'manual'}.get(float(message.value), 'unknown')
            self.notify()
            return
        if name == 'APP_MSN':
            self.mission = MISSION_NAMES.get(float(message.value), 'unknown')
            self.notify()
            return
        if name == 'VIS_READY':
            self.vision_ready = float(message.value) == 1.
            self.notify()
            return
        if name == 'APP_RESULT':
            self.mission_result = RESULT_NAMES.get(float(message.value), 'unknown')
            self.notify()
            return
        if name == 'APP_PHASE':
            index = float(message.value)
            self.phase = PHASE_NAMES[int(index)] if index.is_integer() and 0 <= index < len(PHASE_NAMES) else 'unknown'
            self._complete(now)
            self.notify()
            return
        if name == 'HOVER_S':
            value = float(message.value)
            self.hover_s = value if isfinite(value) else None
            self.notify()
            return
        if self.stamp is not None:
            delta = (message.time_boot_ms - self.stamp) % 2**32
            if delta >= 2**31:
                return  # Discard reordered packets, with MAVLink uint32 rollover.
        if message.time_boot_ms != self.stamp:
            self.stamp, self.parts = message.time_boot_ms, {}
        self.parts[name] = float(message.value)
        if set(self.parts) != set(FLIGHT_NAMES):
            return
        p = self.parts
        self.known_target = target
        valid = p['ARM_VALID'] == 1 and p['ARM_MODE'] in (0., 1.)
        readiness = p['MIS_READY']
        if not isfinite(readiness) or readiness not in range(len(Readiness)):
            valid = False
        height = p['TAKEOFF_H']
        self.remote = FlightState(bool(p['ARM_MODE']) if valid else None, valid,
            Readiness(int(readiness)) if valid else Readiness.UNAVAILABLE,
            height if valid and isfinite(height) else None, now, target)
        self._complete(now)
        self.notify()

    def request(self, action, value, mav, now):
        if not self.control_available:
            raise ValueError('Flight control connection unavailable')
        if action == 'restart':
            reason = app_restart_block_reason(self.snapshot(), now)
            if reason is not None:
                raise ValueError(reason)
            self.pending = dict(action=action, command=APP_RESTART_COMMAND,
                                value=None, issued=now, ack=False, readback=False,
                                previous_epoch=self.app_epoch)
            self.result = 'restart: waiting for App confirmation'
            mav.command_long_send(*APP_TARGET, APP_RESTART_COMMAND, 0, *([0.] * 7))
            self.notify()
            return
        if action in ('arm', 'start', 'land', 'height'):
            reason = flight_action_block_reason(self.snapshot(), action, value, now=now)
            if reason is not None:
                raise ValueError(reason)
        disarm = action in ('disarm', 'emergency')
        if disarm:
            if self.known_target is None:
                raise ValueError('No known application target')
            self.pending = None  # No retries; queued Arm/Start are also discarded by worker.
        elif self.pending is not None:
            raise ValueError('Flight command pending')
        remote = self.remote
        if not disarm and (not remote.valid or now - remote.received_at_s > STATE_STALE_S):
            raise ValueError('Fresh remote flight state required')
        if action == 'height' and (type(value) not in (int, float) or not isfinite(value)
                                   or not MIN_TAKEOFF_HEIGHT_M <= value <= MAX_TAKEOFF_HEIGHT_M):
            raise ValueError('Target height must be 0.1–100 m')
        if action == 'disarm' and (not remote.valid or remote.readiness == FLYING):
            raise ValueError('Emergency confirmation required')
        command = (TAKEOFF_HEIGHT_COMMAND if action == 'height' else
                   MISSION_START_COMMAND if action == 'start' else
                   LAND_COMMAND if action == 'land' else ARM_DISARM_COMMAND)
        params = [0.] * 7
        params[0] = value if action == 'height' else float(action == 'arm')
        params[1] = FORCE_DISARM_MAGIC if action == 'emergency' else 0.
        if action != 'land':
            parse_command(command, params)
        self.pending = dict(action=action, command=command, value=value, issued=now, ack=False,
                            readback=False)
        self.result = f'{action}: waiting for ACK and observed state'
        mav.command_long_send(*APP_TARGET, command, 0, *params)
        self.notify()

    def ack(self, message, now):
        p = self.pending
        if p is None or (message.get_srcSystem(), message.get_srcComponent()) != APP_TARGET:
            return
        if (message.command != p['command']
                or getattr(message, 'target_system', 0) != GCS_SYSTEM_ID
                or getattr(message, 'target_component', 0) != GCS_COMPONENT_ID):
            return
        if getattr(message, 'result_param2', 0) not in (0, VIEW_ACTION_IDS[p['action']]):
            return
        if message.result == 5:  # IN_PROGRESS does not confirm application.
            if p['action'] == 'restart':
                self.result = 'restart: App reopening flight session'
                self.notify()
            return
        if message.result != 0:
            self.result = f"{p['action']}: rejected/failed (ACK {message.result})"
            self.pending = None
        else:
            p['ack'] = True
            self.result = f"{p['action']}: ACK accepted; waiting for observed state"
            self._complete(now)
        self.notify()

    def _complete(self, now):
        p, r = self.pending, self.remote
        if p is not None and p['action'] == 'restart':
            if (self.app_epoch is not None and
                    self.app_epoch != p['previous_epoch'] and self.app_state == 'ready' and
                    0 <= now - self.app_status_at_s <= STATE_STALE_S and
                    r.valid and r.armed is False and r.readiness == DISARMED_IDLE and
                    r.received_at_s > p['issued'] and
                    0 <= now - r.received_at_s <= STATE_STALE_S):
                self.result = 'restart: App ready and disarmed'
                self.pending = None
            return
        if (p is None or not r.valid or r.received_at_s <= p['issued']
                or not 0 <= now - r.received_at_s <= STATE_STALE_S):
            return
        action = p['action']
        matches = (abs(r.height_m - p['value']) <= HEIGHT_TOLERANCE_M if action == 'height' and r.height_m is not None
                   else r.readiness == FLYING if action == 'start'
                   else self.phase in ('land', 'disarming', 'disarmed') if action == 'land'
                   else r.armed is True and r.readiness == ARMED_IDLE if action == 'arm'
                   else r.armed is False if action in ('disarm', 'emergency') else False)
        if p['ack'] and matches:
            self.result = f'{action}: ACK accepted and remote state confirmed'
            self.pending = None

    def poll(self, now):
        changed = False
        if self.remote.valid and now - self.remote.received_at_s > STATE_STALE_S:
            self.remote = FlightState(target=self.known_target)
            changed = True
        if (self.pending is not None and self.pending['action'] != 'restart' and
                now - self.pending['issued'] > COMMAND_TIMEOUT_S + STATE_STALE_S):
            self.result = self.pending['action'] + ': timeout; remote outcome unknown'
            self.pending = None
            changed = True
        if changed:
            self.notify()

    def offline(self):
        self.control_available = False
        self.remote = FlightState(target=self.known_target)
        self.pending = None
        self.mode = 'unknown'
        self.phase = 'unknown'
        self.hover_s = None
        self.app_state = 'unknown'
        self.app_epoch = None
        self.result = 'Flight control connection unavailable'
        self.notify()
