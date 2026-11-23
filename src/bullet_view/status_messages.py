"""View-owned parsing and display metadata for MAVLink status text."""
from dataclasses import dataclass
from math import isfinite
import re


MAV_SEVERITY_ERROR = 3
MAV_SEVERITY_WARNING = 4
MAV_SEVERITY_INFO = 6
STATUSTEXT_MAX_BYTES = 50
STATUS_TIME_DECIMALS = 3
STATUS_COMPACT_TIME_DIGITS = 6
MAX_UTF8_CHARACTER_BYTES = 4
STATUS_INDEX_RE = re.compile(r'^\[(\d+)\]\s*(.*)$', re.DOTALL)
STATUS_CONTEXT_RE = re.compile(
    r'^\[t=(?P<time>-|[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?) '
    r'f=(?P<frame>-|[0-9]+)\]\s*(?P<body>.*)$', re.DOTALL)



@dataclass(frozen=True)
class StatusMessageDefinition:
    index: int
    key: str
    text: str
    description: str
    severity: int = MAV_SEVERITY_INFO


_MESSAGES = (
    ('waiting_app', 'waiting for app readiness', MAV_SEVERITY_INFO),
    ('waiting_applied_arm', 'waiting applied arm', MAV_SEVERITY_INFO),
    ('waiting_betaflight_prearm', 'waiting for Betaflight pre-arm', MAV_SEVERITY_INFO),
    ('awaiting_positive_climb', 'awaiting positive climb', MAV_SEVERITY_INFO),
    ('climbing', 'climbing to takeoff altitude', MAV_SEVERITY_INFO),
    ('climbing_or_settling', 'climbing or settling at takeoff altitude', MAV_SEVERITY_INFO),
    ('settling', 'settling at takeoff altitude', MAV_SEVERITY_INFO),
    ('waiting_for_target', 'waiting for target observations', MAV_SEVERITY_INFO),
    ('searching_target', 'rotating to find a target', MAV_SEVERITY_INFO),
    ('centering_target', 'centering target horizontally with yaw', MAV_SEVERITY_INFO),
    ('settling_centered_target', 'target centered; stopping and settling yaw', MAV_SEVERITY_INFO),
    ('acquiring', 'acquiring target', MAV_SEVERITY_INFO),
    ('tracking', 'tracking target', MAV_SEVERITY_INFO),
    ('committing', 'committing to target approach', MAV_SEVERITY_INFO),
    ('waiting_for_vertical_warmup', 'waiting for altitude and vertical-speed estimates', MAV_SEVERITY_INFO),
    ('no_target', 'no target detected', MAV_SEVERITY_INFO),
    ('stale_image', 'target image is too old', MAV_SEVERITY_WARNING),
    ('feedback_stale', 'physics feedback is too old', MAV_SEVERITY_WARNING),
    ('attitude_stale', 'attitude sample is too old', MAV_SEVERITY_WARNING),
    ('barometer_stale', 'barometer altitude sample is too old', MAV_SEVERITY_WARNING),
    ('sensors_stale', 'attitude or altitude samples are too old', MAV_SEVERITY_WARNING),
    ('search_timeout', 'yaw search exceeded its configured deadline', MAV_SEVERITY_WARNING),
    ('search_exhausted', 'no usable target found in one full yaw circle', MAV_SEVERITY_WARNING),
    ('stop', 'Stop command received', MAV_SEVERITY_INFO),
    ('reset', 'Reset command received', MAV_SEVERITY_INFO),
    ('spawn_applied', 'scenario applied; waiting for Start', MAV_SEVERITY_INFO),
    ('app_not_ready', 'Start rejected because the app was not ready', MAV_SEVERITY_WARNING),
    ('los_acquisition_timeout', 'LOS acquisition timed out', MAV_SEVERITY_ERROR),
    ('fault', 'mission fault', MAV_SEVERITY_ERROR),
    ('completed', 'mission completed', MAV_SEVERITY_INFO),
    ('waiting_operator', 'disarmed idle; waiting for operator Arm', MAV_SEVERITY_INFO),
    ('waiting_mission_start', 'armed idle; waiting for Start mission', MAV_SEVERITY_INFO),
    ('operator_disarmed', 'operator requested disarm; automatic arming disabled', MAV_SEVERITY_INFO),
    ('operator_arm', 'operator Arm requested; waiting for backend confirmation', MAV_SEVERITY_INFO),
    ('operator_emergency_disarm', 'emergency disarm; stop/reset required before rearming', MAV_SEVERITY_ERROR),
)

_DESCRIPTIONS = {
    'waiting_app': 'The mission runtime is waiting for the application to report readiness.',
    'waiting_applied_arm': 'The simulator has requested arming and is waiting for the applied arm state.',
    'awaiting_positive_climb': 'Takeoff spool is active and the vehicle must show a positive climb.',
    'climbing': 'The dedicated takeoff controller is commanding the target altitude.',
    'searching_target': 'The vehicle is rotating through its configured search arc.',
    'centering_target': 'Yaw is being corrected to place the target on the image centerline.',
    'acquiring': 'The navigator is collecting consistent target observations.',
    'tracking': 'The navigator is following the target with the LOS controller.',
    'committing': 'The vehicle has entered the final target approach decision.',
    'stale_image': 'The latest camera observation is older than the configured freshness limit.',
    'feedback_stale': 'Physics feedback is no longer fresh enough for safe control.',
    'search_timeout': 'The configured search deadline expired before a usable target was found.',
    'search_exhausted': 'The full search arc completed without a usable target.',
    'los_acquisition_timeout': 'LOS acquisition did not collect enough consistent observations in time.',
    'fault': 'The mission entered a fault state and withdrew active control.',
    'completed': 'The mission reached its terminal successful state.',
}

STATUS_MESSAGE_CATALOG = tuple(
    StatusMessageDefinition(index=index, key=key, text=text,
                            description=_DESCRIPTIONS.get(key, text.capitalize() + '.'))
    for index, (key, text, severity) in enumerate(_MESSAGES, start=1)
)
STATUS_MESSAGE_BY_KEY = {message.key: message for message in STATUS_MESSAGE_CATALOG}
STATUS_MESSAGE_BY_INDEX = {message.index: message for message in STATUS_MESSAGE_CATALOG}


@dataclass(frozen=True)
class ParsedStatusText:
    index: int
    body: str
    simulation_time_s: float | None = None
    image_sequence: int | None = None


def parse_status_text(text: str) -> ParsedStatusText:
    """Decode optional context while retaining compatibility with legacy text."""
    text = text.rstrip('\0')
    indexed = STATUS_INDEX_RE.match(text)
    index = int(indexed[1]) if indexed else 0
    body = indexed[2] if indexed else text
    context = STATUS_CONTEXT_RE.match(body)
    if context is not None:
        time_s = None if context['time'] == '-' else float(context['time'])
        frame = None if context['frame'] == '-' else int(context['frame'])
        if time_s is None or isfinite(time_s):
            return ParsedStatusText(index, context['body'], time_s, frame)
    return ParsedStatusText(index, body)


def status_text_chunks(index: int, text: str, *, max_bytes: int = STATUSTEXT_MAX_BYTES,
                       simulation_time_s: float | None = None,
                       image_sequence: int | None = None):
    """Return UTF-8 chunks with the same optional source context on every chunk."""
    if type(index) is not int or index < 0:
        raise ValueError('nonnegative message code required')
    if simulation_time_s is not None and (type(simulation_time_s) not in (int, float)
            or not isfinite(simulation_time_s) or simulation_time_s < 0):
        raise ValueError('finite nonnegative simulation time required')
    if image_sequence is not None and (type(image_sequence) is not int or image_sequence < 0):
        raise ValueError('nonnegative camera image sequence required')
    prefix = f'[{index:02d}] '
    if simulation_time_s is not None or image_sequence is not None:
        stamp = '-' if simulation_time_s is None else f'{simulation_time_s:.{STATUS_TIME_DECIMALS}f}'
        frame = '-' if image_sequence is None else str(image_sequence)
        context = f'[t={stamp} f={frame}] '
        if len((prefix + context).encode('utf-8')) > max_bytes - MAX_UTF8_CHARACTER_BYTES:
            # Keep space for complete UTF-8 characters even at extreme times.
            stamp = '-' if simulation_time_s is None else format(simulation_time_s, f'.{STATUS_COMPACT_TIME_DIGITS}g')
            context = f'[t={stamp} f={frame}] '
        prefix += context
    budget = max_bytes - len(prefix.encode('utf-8'))
    if budget <= 0:
        raise ValueError('status prefix exceeds MAVLink text limit')
    chunks, current = [], ''
    for word in text.split():
        candidate = current + (' ' if current else '') + word
        if len(candidate.encode('utf-8')) <= budget:
            current = candidate
            continue
        if current:
            chunks.append(prefix + current)
            current = ''
        for character in word:
            if len(character.encode('utf-8')) > budget:
                raise ValueError('status prefix leaves no room for a UTF-8 character')
            if len((current + character).encode('utf-8')) > budget:
                chunks.append(prefix + current)
                current = ''
            current += character
    if current:
        chunks.append(prefix + current)
    return tuple(chunks)
