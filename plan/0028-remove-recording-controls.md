# Remove View recording controls

Goal: Remove recording Start/Stop UI and recording-specific MAVLink communication from Bullet View.

Implementation steps: Delete the recording panel and client. Remove their signals, queues, request methods, named-value dispatch, and lifecycle handling from the presenter and worker. Remove recording-only tests and update View documentation and the remaining window test.

Interface changes: Bullet View no longer offers `request_recording`, recording snapshots, or `REC_AUTH`/`REC_STATE` decoding. It no longer sends recording `COMMAND_LONG` messages. Flight, telemetry, parameter, and bbox paths remain available as before.

Verification: The View suite passed offscreen (85 tests, one skipped). A new worker test confirms no recording request API or client exists and `REC_AUTH`/`REC_STATE` named values are ignored; the window test confirms no recording panel exists. Source search found no recording handling in `src/bullet_view`, and `git diff --check` passed.

Scope/defaults: Remove View recording controls only; do not alter any external recorder or Bullet App. Preserve the uncommitted local parameter protocol work.

Status: Implemented and verified. Implementation commit: `007da997731b1688616629c9f83e2418b1c85d86`.
