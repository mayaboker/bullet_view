# Complete App restart from ready epoch

Status: Implemented. Implementation commit: Pending (no commit requested).

## Goal
Allow Bullet App's UDP source port to change while `main()` retries a View-requested manual FCU session.

## Implementation
- Keep a restart request pending through App connection attempts, including beyond the former 45-second deadline.
- Complete only after a changed `APP_EPOCH`, fresh `APP_STATE=ready`, and fresh disarmed FCU readback. Do not require a final accepted ACK.
- Continue to honor denial/failure ACKs and show reconnecting while pending; use the existing peer-selection behavior for App's new source port.

## Interface
MAVLink command 31013 and `APP_STATE`/`APP_EPOCH` are unchanged. `IN_PROGRESS` remains an acknowledgement of the accepted request.

## Verification
39 focused Flight Control tests passed; the remaining 59 View tests passed with one skip in a separate process. The combined suite reported 98 passed and one skipped, then exited with code 139 during Qt process shutdown. No live SITL run was performed.

## Scope and defaults
Manual TCP SITL restart only. Closing View clears its local pending request.
