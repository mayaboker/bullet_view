"""View-owned catalog and codecs for MAVLink Extended Parameters.

Numeric extended values are binary, not pymavlink's decoded strings.
"""
from dataclasses import dataclass
from importlib.resources import files
from math import isfinite
import json
import struct

CATALOG_VERSION = 1
CATALOG_ID = 'B_CATALOG_VER'
REVISION_ID = 'B_CFG_REV'
REAL64 = 10
INT64 = 8
CUSTOM = 11
VALUE_BYTES = 128
LIVE_TUNING_FIELDS = frozenset(('yaw_gain_s_inv', 'azimuth_kp', 'azimuth_kd_s',
    'azimuth_ki_s_inv', 'elevation_kp_m_s_rad', 'elevation_kd_m_rad', 'elevation_ki_m_s2_rad'))


@dataclass(frozen=True)
class ParameterDefinition:
    id: str
    path: str
    kind: str
    category: str
    description: str
    units: str
    live: bool
    yaml_key: str
    yaml_scale: float
    yaml_description: str

    @property
    def wire_type(self):
        return {'real': REAL64, 'integer': INT64, 'text': CUSTOM}[self.kind]


CATALOG = tuple(ParameterDefinition(**row) for row in
                json.loads(files('bullet_view').joinpath('parameter_catalog.json').read_text()))
BY_ID = {p.id: p for p in CATALOG}
BY_PATH = {p.path: p for p in CATALOG}
PARAMETER_IDS = (CATALOG_ID, REVISION_ID, *(p.id for p in CATALOG))


def encode_value(value, wire_type):
    if wire_type == REAL64:
        if type(value) not in (int, float) or not isfinite(value):
            raise ValueError('finite numeric value required')
        raw = struct.pack('<d', value)
    elif wire_type == INT64:
        if type(value) is not int:
            raise ValueError('integer required')
        raw = struct.pack('<q', value)
    elif wire_type == CUSTOM:
        if value is not None and not isinstance(value, str):
            raise ValueError('string or null required')
        raw = json.dumps(value, ensure_ascii=True).encode('ascii')
    else:
        raise ValueError('unsupported parameter type')
    if len(raw) > VALUE_BYTES:
        raise ValueError('parameter value exceeds 128-byte MAVLink limit')
    return raw.ljust(VALUE_BYTES, b'\0')


def decode_value(raw, wire_type):
    raw = bytes(raw)
    if wire_type == REAL64:
        if len(raw) < 8:
            raise ValueError('short numeric parameter')
        value = struct.unpack('<d', raw[:8])[0]
        if not isfinite(value):
            raise ValueError('nonfinite parameter')
        return value
    if wire_type == INT64:
        if len(raw) < 8:
            raise ValueError('short integer parameter')
        return struct.unpack('<q', raw[:8])[0]
    if wire_type == CUSTOM:
        value = json.loads(raw.rstrip(b'\0'))
        if value is not None and not isinstance(value, str):
            raise ValueError('string or null required')
        return value
    raise ValueError('unsupported parameter type')


def raw_value(message):
    # pymavlink trims trailing NULs from char arrays, including binary numeric
    # fields. Restore the fixed wire width before unpacking (zero can be b'').
    return message._param_value_raw.ljust(VALUE_BYTES, b'\0')


def profile_values(config_dict):
    result = {}
    for definition in CATALOG:
        value = config_dict
        for key in definition.path.split('.'):
            value = value[int(key)] if isinstance(value, (tuple, list)) else value[key]
        result[definition.id] = value
    return result


def profile_dict(values, *, yaml_units=False):
    """Rebuild a complete profile; arrays are assembled from indexed leaves."""
    result = {}
    for p in CATALOG:
        keys = p.path.split('.')
        if yaml_units:
            keys[-1] = p.yaml_key
        cursor = result
        for key in keys[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[keys[-1]] = values[p.id] / p.yaml_scale if yaml_units and p.yaml_scale != 1 else values[p.id]
    result['camera']['camera_to_body_xyzw'] = [result['camera']['camera_to_body_xyzw'][str(i)] for i in range(4)]
    return result
