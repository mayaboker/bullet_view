"""Configure the View connection for the MAVLink 2 common dialect."""
from pymavlink import mavutil
from pymavlink.dialects.v20 import common


def use_mavlink2(connection, system_id, component_id):
    """Select a per-connection v2 parser/writer without global dialect changes."""
    if isinstance(connection, mavutil.mavfile):
        connection.source_system = system_id
        connection.source_component = component_id
        connection.mav = common.MAVLink(connection, srcSystem=system_id, srcComponent=component_id)
        connection.mav.robust_parsing = connection.robust_parsing
        connection.WIRE_PROTOCOL_VERSION = '2.0'
        connection.first_byte = False
