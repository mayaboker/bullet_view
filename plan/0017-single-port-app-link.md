# Single-port Bullet App link

Status: Implemented and verified. Implementation commit: Pending (no commit requested).

Goal: Receive App telemetry and return View heartbeat and flight commands on one MAVLink 2 UDP socket bound to port 14550.

Implementation: Use one worker connection for telemetry, outbound commands, and inbound ACKs. Wait for App's first packet before sending View heartbeat. Keep the existing flight state and ACK confirmation behavior. Remove the separate control endpoint option.

Interface: Retire App–View UDP 14551 and `--mavlink-control-endpoint`. Retain `--mavlink-endpoint` with the default `udpin:127.0.0.1:14550`.

Verification: 72 View tests passed with 1 existing skip, including a real UDP stream, command, and ACK regression test. A localhost exchange with App's link confirmed App-first telemetry and one-socket ACK delivery. Updated the README and connection document.
