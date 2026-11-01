# Clear log and auto-scroll controls

## Goal
Add Clear log and an Auto-scroll checkbox to the Telemetry status-message header.

## Implementation steps
- Clear stored viewer messages through the presenter and reset rows, selection and details.
- Make the checkbox the single source of auto-scroll state, checked by default.
- Preserve scroll position while unchecked; scroll to newest immediately when checked.
- Remove completion-triggered scrolling overrides. Clearing retains checkbox state.

## Interfaces
Presenter clear_messages() and messages_cleared signal. No MAVLink or remote changes.

## Verification
Offscreen Qt tests for empty/populated clears, subsequent messages, enabled/disabled scrolling,
re-enable and mission completion. Bullet View suite: 23 tests passed. Desktop X11 preview inspected; Clear log and
checkbox interaction checked without opening network connections. Unchecked
scrolling verified both at the middle and at the previous bottom of the log.

## Scope and defaults
Session-local history and checkbox state. Remote logs and MCAP are unaffected.

## Status
Implemented; verification passed

## Implementation commit
`dd84b1a47ca5f5800f8a513dd04ca180f659289b`

## Repository snapshot record
Recorded snapshot: `dd84b1a47ca5f5800f8a513dd04ca180f659289b` (bullet_view repository). This is the new local
baseline containing the current implementation, not a recovered historical commit.
