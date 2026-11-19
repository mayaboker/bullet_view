# Upstream telemetry rates

Goal: show the rates received by Bullet App from SITL for attitude and altitude, and make sustained rate drops visible.

Implementation: decode the App's `ATT_HZ` and `ALT_HZ` named values into immutable telemetry state, show both rates in the Telemetry tab, and display warning/recovery status text from the App.

Interfaces: two new MAVLink named values, each within the ten-byte name limit. Existing flight-control values and commands are unchanged.

Verification: protocol conversion, presenter, and offscreen widget tests.

Scope/defaults: App owns rate measurement and alert thresholds; View only displays received values and warnings.

Status: Implemented; 84 View tests passed with one skip. Implementation commit: `dca2ee8`.
