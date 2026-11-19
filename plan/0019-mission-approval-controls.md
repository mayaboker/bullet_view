# Mission approval controls

Status: Pending
Implementation commit: Pending

Goal: Show mission-configured altitude without editing it and make View Arm/Start apply only to manually approved missions.

Implementation: Update flight action gates, remove the target preflight detector gate, make the height display read-only, and retain Land/Disarm as abort controls. Keep MAVLink mission/mode status decoding.

Interface changes: No wire changes; `APP_MODE` now means approval mode. `TAKEOFF_H` remains the configured mission altitude.

Verification: Focused flight-control and offscreen widget tests.

Scope/defaults: Applies to hover-land and target-hit; no new image rendering.

Verification outcome: Full offscreen View suite passed (74 tests, 1 skipped); `git diff --check` passed.
