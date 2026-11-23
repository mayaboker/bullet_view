# Red App heartbeat stale status

Goal: Show a red “Telemetry stale” status in Bullet View when Bullet App heartbeats stop, even if other MAVLink packets continue.

Implementation: Track the first received packet until a heartbeat arrives, and the latest App heartbeat afterward. At the existing three-second heartbeat timeout, emit the stale status once and clear SITL confirmation. Restore Connected when a heartbeat resumes. Style that status red in the View header; leave other status messages at their normal style.

Interface changes: No MAVLink or CLI changes. The header status changes color on the existing stale message.

Verification: The offscreen View suite passed (90 tests, 1 skipped). Focused tests cover missing heartbeats before any App packet, continuing non-heartbeat traffic, recovery on a new heartbeat, and red header styling. `git diff --check` passed.

Scope/defaults: Preserve the existing 0.75-second all-message timeout and connection-failure status. No automatic reconnect.

Status: Implemented and verified. Implementation commit: Pending (no commit requested).
