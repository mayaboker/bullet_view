# App-only flight control

Status: Implemented; tests and Auto/Manual SITL flight checks passed. Implementation commit: Pending (no commit requested).

Goal: Bullet View talks only to Bullet App, showing its mode and flight state and controlling Auto/Manual flight.

Implementation: Send GCS heartbeat and flight commands to App, receive telemetry/ACK/state, add Manual Land, disable unsupported camera/parameter/recording panels, and remove the direct renderer image subscription.

Interface: Existing loopback MAVLink endpoints remain UDP 14550 telemetry and UDP 14551 control. Auto height is fixed at 10 m; Manual accepts 0.1–100 m in 0.1 m steps.

Verification: 70 View tests passed; one legacy parameter test skips because its panel is disabled. View's MAVLink flight client completed Auto and Manual command/ACK/state flows against App and SITL. An offscreen View process established its heartbeat connection. The direct image worker was removed. No commit requested.
