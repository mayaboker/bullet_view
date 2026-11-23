"""View-local interpretation of the App's MAVLink flight-control fields."""
from dataclasses import dataclass
from enum import IntEnum
from math import isfinite

ARM_DISARM_COMMAND = 400
MISSION_START_COMMAND = 300
TAKEOFF_HEIGHT_COMMAND = 31012
APP_RESTART_COMMAND = 31013
FLIGHT_COMMANDS = frozenset((ARM_DISARM_COMMAND, MISSION_START_COMMAND,
                            TAKEOFF_HEIGHT_COMMAND, APP_RESTART_COMMAND))
FORCE_DISARM_MAGIC = 21196
ACTION_IDS = {'arm': 1, 'disarm': 2, 'emergency': 3, 'start': 4, 'height': 5, 'invalid': 0}
APP_STATES = {0.: 'disabled', 1.: 'ready', 2.: 'restart_required',
              3.: 'restarting', 4.: 'restart_failed'}
COMMAND_TIMEOUT_S = 5.0
STATE_STALE_S = 0.75
HEIGHT_STEP_M = 0.1
HEIGHT_TOLERANCE_M = 0.005
DEFAULT_TAKEOFF_HEIGHT_M = 20.0
MIN_TAKEOFF_HEIGHT_M = 0.1
MAX_TAKEOFF_HEIGHT_M = 100.0
FLIGHT_NAMES = ('ARM_MODE', 'ARM_VALID', 'MIS_READY', 'TAKEOFF_H')


class Readiness(IntEnum):
    """Readiness codes decoded from MAVLink MIS_READY."""

    UNAVAILABLE = 0
    DISARMED_IDLE = 1
    ARMED_IDLE = 2
    FLYING = 3
    RESET_REQUIRED = 4


UNAVAILABLE = Readiness.UNAVAILABLE
DISARMED_IDLE = Readiness.DISARMED_IDLE
ARMED_IDLE = Readiness.ARMED_IDLE
FLYING = Readiness.FLYING
RESET_REQUIRED = Readiness.RESET_REQUIRED


@dataclass(frozen=True)
class FlightState:
    armed: bool | None = None
    valid: bool = False
    readiness: Readiness = Readiness.UNAVAILABLE
    height_m: float | None = None
    received_at_s: float = float('-inf')
    target: tuple[int, int] | None = None


def parse_command(command, params):
    """Validate an outgoing App flight command before sending MAVLink."""
    if len(params) != 7 or not all(isfinite(p) for p in params):
        raise ValueError('Flight parameters must be finite')
    first, second, *rest = params
    if any(p != 0 for p in rest):
        raise ValueError('Unsupported flight parameters')
    if command == ARM_DISARM_COMMAND:
        if first == 1 and second == 0:
            return 'arm', None
        if first == 0 and second in (0, FORCE_DISARM_MAGIC):
            return ('emergency' if second else 'disarm'), None
    elif command == MISSION_START_COMMAND and first == second == 0:
        return 'start', None
    elif command == TAKEOFF_HEIGHT_COMMAND and second == 0:
        if not MIN_TAKEOFF_HEIGHT_M <= first <= MAX_TAKEOFF_HEIGHT_M:
            raise ValueError('takeoff height must be 0.1–100 m')
        if abs(first / HEIGHT_STEP_M - round(first / HEIGHT_STEP_M)) > 0.001:
            raise ValueError('Height requires 0.1 m steps')
        return 'height', round(first, 1)
    elif command == APP_RESTART_COMMAND and first == second == 0:
        return 'restart', None
    raise ValueError('Unsupported flight parameters')
