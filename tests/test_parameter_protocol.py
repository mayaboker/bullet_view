"""MAVLink parameter behavior without the optional legacy profile package."""
from pathlib import Path

from pymavlink.dialects.v20 import common as wire

from bullet_view.parameter_protocol import (
    BY_ID, CATALOG, CATALOG_ID, CATALOG_VERSION, CUSTOM, INT64, PARAMETER_IDS,
    REAL64, REVISION_ID, decode_value, encode_value, raw_value,
)
from bullet_view.parameters import ParameterClient


class Mav:
    def __init__(self):
        self.calls = []

    def param_ext_request_read_send(self, *args):
        self.calls.append(('read', args))

    def param_ext_request_list_send(self, *args):
        self.calls.append(('list', args))

    def param_ext_set_send(self, *args):
        self.calls.append(('set', args))


def _value_message(identifier, value):
    definition = BY_ID.get(identifier)
    kind = definition.wire_type if definition else INT64
    message = wire.MAVLink_param_ext_value_message(
        identifier.encode(), encode_value(value, kind), kind,
        len(PARAMETER_IDS), PARAMETER_IDS.index(identifier),
    )
    return wire.MAVLink(None).parse_char(message.pack(wire.MAVLink(None, srcSystem=1, srcComponent=1)))


def test_local_catalog_and_binary_mavlink_values():
    assert len(CATALOG) == 86
    assert len(PARAMETER_IDS) == 88
    assert len(set(PARAMETER_IDS)) == len(PARAMETER_IDS)
    assert PARAMETER_IDS[:2] == (CATALOG_ID, REVISION_ID)
    assert CATALOG_VERSION == 1
    for value, kind in ((1.25, REAL64), (0, INT64), ('pilot', CUSTOM), (None, CUSTOM)):
        assert decode_value(encode_value(value, kind), kind) == value
    message = _value_message(REVISION_ID, 0)
    assert decode_value(raw_value(message), INT64) == 0


def test_parameter_client_uses_mavlink_extended_requests():
    client, mav = ParameterClient(), Mav()
    client.target = (1, 1)
    client.online = True
    client.refresh(mav, 1.0)
    assert mav.calls[-1] == ('read', (1, 1, REVISION_ID.encode(), -1))
    client.handle(_value_message(REVISION_ID, 0), 1.1, mav)
    assert mav.calls[-1] == ('list', (1, 1))

    client.phase = 'ready'
    client.complete = True
    client.pending = None
    client.set(mav, 'LOS_AZ_KP', 1.5, 1.2)
    assert mav.calls[-1] == ('set', (1, 1, b'LOS_AZ_KP', encode_value(1.5, REAL64), REAL64))


def test_parameter_path_has_no_bullet_msgs_parameter_import():
    root = Path(__file__).resolve().parents[1] / 'src' / 'bullet_view'
    for name in ('parameter_protocol.py', 'parameters.py', 'parameter_view.py',
                 'mavlink_v2.py', 'worker.py'):
        assert 'bullet_msgs.parameters' not in (root / name).read_text()
