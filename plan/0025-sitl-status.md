# SITL status from App heartbeat

Goal: Show whether Bullet App confirmed a Betaflight SITL target at startup.

Implementation: Decode App heartbeat custom_mode bit 0, store the reported status, and show confirmed, not confirmed, or unknown in the telemetry view. Label upstream rates SITL in red, HW in green, or Telemetry in a neutral color for those states. Clear status when the heartbeat becomes stale or the connection fails. Document the wire bit and UI meaning.

Interface: App heartbeat custom_mode bit 0 is SITL_CONFIRMED. A clear bit means not confirmed; absent or stale heartbeat means unknown.

Verification: Worker conversion, presenter staleness, and offscreen UI checks passed; the full View suite passed 89 tests with one skip. A live App-to-View-port heartbeat carried the SITL bit.

Scope/defaults: Display only, no flight-control changes. Status: Implemented and verified. Implementation commit: `c6256fc2f3c9e55eb0bb61d7b829ce22b82ba3a7`.
