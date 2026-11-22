"""Worker-owned parameter synchronization, edits and complete profile export."""
from dataclasses import dataclass
import json
from pathlib import Path

from .parameter_protocol import (CATALOG, BY_ID, PARAMETER_IDS, CATALOG_ID, CATALOG_VERSION,
    REVISION_ID, INT64, encode_value, decode_value, raw_value, profile_dict)

PARAMETER_TIMEOUT_S = 1.
PARAMETER_READ_ATTEMPTS = 3
PARAMETER_WRITE_RETRIES = 2
PARAMETER_HEARTBEAT_TIMEOUT_S = 3.
GCS_SYSTEM_ID = 255
GCS_COMPONENT_ID = 190


@dataclass(frozen=True)
class ParameterSnapshot:
    values: tuple = ()
    statuses: tuple = ()
    complete: bool = False
    online: bool = False
    progress: str = 'Waiting for Bullet heartbeat'
    target: tuple | None = None
    pending: bool = False
    failed: bool = False


def parse_edit(definition, text):
    if definition.kind == 'integer':
        value = int(text)
    elif definition.kind == 'real':
        value = float(text)
    else:
        value = None if text == 'null' else text
    encode_value(value, definition.wire_type)
    return value


def yaml_export(snapshot):
    if not snapshot.complete or snapshot.pending or not snapshot.online:
        raise ValueError('Load a complete current profile and resolve pending edits before export')
    values = dict(snapshot.values)
    profile = profile_dict(values, yaml_units=True)
    lines = [f'# Confirmed Bullet mission profile, configuration revision {values[REVISION_ID]}',
             '# Exported values are session settings; the remote file is unchanged.']
    descriptions = {}
    for p in CATALOG:
        parts = p.path.split('.')
        if parts[-1].isdigit():
            parts = parts[:-1]
            description = 'Camera-to-body unit quaternion [x, y, z, w], mapping aligned camera rays into body FLU.'
        else:
            parts[-1] = p.yaml_key
            description = p.yaml_description
        descriptions['.'.join(parts)] = description
    def write(mapping, prefix='', depth=0):
        for key, value in mapping.items():
            path = f'{prefix}.{key}' if prefix else key
            indent = '  ' * depth
            description = descriptions.get(path, key.replace('_', ' ').capitalize())
            lines.append(indent + '# ' + description.replace('\n', ' '))
            if isinstance(value, dict):
                lines.append(indent + key + ':')
                write(value, path, depth + 1)
            else:
                lines.append(indent + key + ': ' + json.dumps(value, allow_nan=False))
    write(profile)
    return '\n'.join(lines) + '\n'


def save_yaml(snapshot, destination):
    text = yaml_export(snapshot)
    Path(destination).write_text(text)


class ParameterClient:
    """One in-flight write, explicit revision verification, bounded loss recovery."""
    def __init__(self, notify=lambda snapshot: None):
        self.notify = notify
        self.target = None
        self.last_heartbeat = None
        self.values = {}
        self.statuses = {}
        self.phase = 'idle'
        self.progress = 'Waiting for Bullet heartbeat'
        self.complete = False
        self.pending = None
        self.last_progress = 0.
        self.attempts = 0
        self.start_revision = None
        self.restarts = 0
        self.online = False

    def snapshot(self):
        unresolved = any(s == 'Unconfirmed' for s in self.statuses.values())
        return ParameterSnapshot(tuple(self.values.items()), tuple(self.statuses.items()), self.complete,
            self.online, self.progress, self.target, self.pending is not None or unresolved,
            self.phase == 'failed')

    def emit(self):
        self.notify(self.snapshot())

    def heartbeat(self, message, now, mav):
        target = (message.get_srcSystem(), message.get_srcComponent())
        if target != (1, 1):
            return  # This service manages the Bullet application, not arbitrary autopilots.
        self.target = target
        was_online = self.online
        self.last_heartbeat, self.online = now, True
        if self.phase == 'idle':
            self.refresh(mav, now)
        elif not was_online:
            self.refresh(mav, now)
        else:
            self.emit()

    def read(self, mav, id):
        mav.param_ext_request_read_send(*self.target, id.encode(), -1)

    def refresh(self, mav, now, *, restart=False):
        if not self.online or self.target is None or self.pending is not None:
            return
        if not restart:
            self.restarts = 0
        self.values.clear()
        self.statuses.clear()
        self.complete = False
        self.phase, self.progress = 'head', 'Reading profile revision…'
        self.last_progress, self.attempts = now, 0
        self.read(mav, REVISION_ID)
        self.emit()

    def set(self, mav, id, value, now):
        if not self.online or not self.complete or self.pending is not None:
            raise ValueError('Wait for a complete profile and previous edit acknowledgment')
        p = BY_ID[id]
        encoded = encode_value(value, p.wire_type)
        self.pending = dict(id=id, value=value, sent=now, retries=0, readback=False)
        self.statuses[id] = 'Pending'
        mav.param_ext_set_send(*self.target, id.encode(), encoded, p.wire_type)
        self.emit()

    def handle(self, message, now, mav):
        if (message.get_srcSystem(), message.get_srcComponent()) != self.target:
            return
        id = message.param_id.rstrip('\0')
        if id not in PARAMETER_IDS:
            return
        p = BY_ID.get(id)
        expected_type = p.wire_type if p else INT64
        try:
            if message.param_type != expected_type:
                raise ValueError('incorrect remote parameter type')
            value = decode_value(raw_value(message), expected_type)
        except (ValueError, TypeError, OverflowError):
            return
        if message.get_type() == 'PARAM_EXT_ACK':
            if self.pending is None or id != self.pending['id']:
                return
            if message.param_result == 3:
                self.pending['sent'] = now
                return
            if message.param_result == 0 and value != self.pending['value']:
                # A delayed success for a preceding write must not reject the
                # current request; bounded retry/readback will resolve it.
                return
            self.values[id] = value
            success = message.param_result == 0 and value == self.pending['value']
            self.statuses[id] = 'Applied' if success else 'Rejected'
            self.pending = None
            # Re-read the whole revision-checked profile after any write response.
            status = dict(self.statuses)
            self.refresh(mav, now)
            self.statuses.update(status)
            self.emit()
            return
        if message.param_count != len(PARAMETER_IDS) or message.param_index != PARAMETER_IDS.index(id):
            self.progress, self.complete, self.phase = 'Remote catalog differs; export disabled', False, 'failed'
            self.emit()
            return
        if self.pending is not None and self.pending['readback'] and id == self.pending['id']:
            self.statuses[id] = ('Confirmed by readback' if value == self.pending['value'] else 'Rejected')
            self.pending = None
            status = dict(self.statuses)
            self.refresh(mav, now)
            self.statuses.update(status)
            self.emit()
            return
        if self.phase == 'head' and id == REVISION_ID:
            self.start_revision = value
            self.phase, self.last_progress, self.attempts = 'list', now, 0
            mav.param_ext_request_list_send(*self.target)
        elif self.phase == 'list':
            if id not in self.values:
                self.last_progress, self.attempts = now, 0
            self.values[id] = value
            self.progress = f'Loaded {len(self.values)}/{len(PARAMETER_IDS)} parameters'
            if len(self.values) == len(PARAMETER_IDS):
                self.phase, self.last_progress, self.attempts = 'verify', now, 0
                self.read(mav, REVISION_ID)
        elif self.phase == 'verify' and id == REVISION_ID:
            if self.values.get(CATALOG_ID) != CATALOG_VERSION:
                self.phase, self.progress = 'failed', 'Unsupported catalog version; export and edits disabled'
            elif value != self.start_revision or self.values[REVISION_ID] != value:
                self.restarts += 1
                if self.restarts <= PARAMETER_READ_ATTEMPTS:
                    self.refresh(mav, now, restart=True)
                else:
                    self.phase, self.progress = 'failed', 'Profile keeps changing; refresh when stable'
            else:
                self.complete, self.phase = True, 'ready'
                self.progress = f'{len(CATALOG)} parameters · revision {value} · synchronized'
        elif self.phase == 'ready':
            # An unsolicited update invalidates export until the next coherent refresh.
            if self.values.get(id) != value:
                self.refresh(mav, now)
        self.emit()

    def poll(self, mav, now):
        if self.last_heartbeat is not None and now - self.last_heartbeat > PARAMETER_HEARTBEAT_TIMEOUT_S:
            if self.online:
                self.online, self.complete = False, False
                self.phase, self.progress = 'failed', 'Target heartbeat stale; refresh after reconnection'
                if self.pending is not None:
                    self.statuses[self.pending['id']] = 'Unconfirmed'
                    self.pending = None
                self.emit()
            return
        if not self.online:
            return
        if self.pending is not None and now - self.pending['sent'] >= PARAMETER_TIMEOUT_S:
            pending = self.pending
            id = pending['id']
            if pending['readback']:
                self.statuses[id] = 'Unconfirmed'
                self.pending = None
                self.emit()
            elif pending['retries'] < PARAMETER_WRITE_RETRIES:
                pending['retries'] += 1
                pending['sent'] = now
                mav.param_ext_set_send(*self.target, id.encode(), encode_value(pending['value'], BY_ID[id].wire_type), BY_ID[id].wire_type)
            else:
                pending['readback'], pending['sent'] = True, now
                self.read(mav, id)
        if self.phase in ('head', 'list', 'verify') and now - self.last_progress >= PARAMETER_TIMEOUT_S:
            if self.attempts >= PARAMETER_READ_ATTEMPTS:
                self.phase, self.progress = 'failed', 'Parameter download incomplete; click Refresh'
                self.emit()
                return
            self.attempts += 1
            self.last_progress = now
            ids = ([id for id in PARAMETER_IDS if id not in self.values] if self.phase == 'list' else [REVISION_ID])
            for id in ids:
                self.read(mav, id)
