"""Immutable telemetry state shared by the presenter and view."""
from dataclasses import dataclass
from .status_messages import parse_status_text, STATUS_TIME_DECIMALS


@dataclass(frozen=True)
class Attitude:
    roll_rad: float
    pitch_rad: float
    yaw_rad: float
    time_boot_ms: int


@dataclass(frozen=True)
class Heartbeat:
    base_mode: int
    custom_mode: int
    system_status: int
    received_at_s: float


@dataclass(frozen=True)
class Altitude:
    local_m: float
    time_usec: int


@dataclass(frozen=True)
class Rangefinder:
    distance_cm: float | None
    time_boot_ms: int
    valid: bool


@dataclass(frozen=True)
class StatusText:
    index: int
    severity: int
    text: str
    received_at_s: float
    simulation_time_s: float | None = None
    image_sequence: int | None = None

    @property
    def context_text(self):
        stamp = '—' if self.simulation_time_s is None else f'{self.simulation_time_s:.{STATUS_TIME_DECIMALS}f}'
        frame = '—' if self.image_sequence is None else str(self.image_sequence)
        return f'[{stamp} s | frame {frame}]'

    @property
    def display_text(self):
        return f'{self.context_text} {parse_status_text(self.text).body}'


@dataclass(frozen=True)
class Bbox:
    valid: bool
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    fid: int | None = None


@dataclass(frozen=True)
class ImageFrame:
    width: int
    height: int
    encoding: str
    pixels: bytes
    sequence: int
    capture_ns: int
    fid: int | None = None
    session: str = ''


@dataclass(frozen=True)
class TelemetrySnapshot:
    connected: bool = False
    heartbeat_at_s: float | None = None
    last_message_at_s: float | None = None
    attitude: Attitude | None = None
    altitude: Altitude | None = None
    rangefinder: Rangefinder | None = None
    error: str | None = None
    vertical_speed_m_s: float | None = None
    attitude_hz: float | None = None
    altitude_hz: float | None = None
    messages: tuple[StatusText, ...] = ()
    heartbeat: Heartbeat | None = None
    sitl_confirmed: bool | None = None
    mission_stopped: bool = False
    bbox: Bbox | None = None
    image: ImageFrame | None = None


@dataclass(frozen=True)
class TelemetryUpdate:
    kind: str
    value: object
    received_at_s: float
