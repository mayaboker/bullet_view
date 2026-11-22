# Local MAVLink flight protocol interpretation

Goal: Keep the App–View flight-control path on MAVLink without using `bullet_msgs` flight-control or spawn helpers in Bullet View.

Implementation steps: Add View-local flight constants, state, readiness enum, and outgoing-command validation. Update the flight client, worker dispatch, panel, and relevant tests to import these local definitions. Keep unrelated `bullet_msgs` parameter, recording, and status features as they are.

Interface changes: None on the wire. Preserve MAVLink command IDs, parameters, named values, ACK matching, readiness values 0–4, height limits, and UI behavior. Bullet View's flight-control Python imports become local.

Verification: The View suite passed offscreen (90 tests, one skipped), including a flight-source boundary check. The App suite passed (52 tests), including readiness value checks. Both repositories passed `git diff --check`.

Scope/defaults: The separate parameter, recording, and status features remain outside this flight-control refactor. Their existing `bullet_msgs` dependency remains.

Status: Implemented and verified. Implementation commit: `16fa5d69ec40568f7a2378df90da2ad8bdf6192a`.
