# Status-message-only scrolling

Goal: Show the vertical scrollbar on status messages instead of the full telemetry tab.

Implementation: Hide the outer telemetry scroll area's bars while preserving wheel access to dashboard content in short split-monitor windows. Show the message list's vertical scrollbar. Reduce gauge minimum height enough for the full dashboard to fit at the normal window size. Preserve the checked Auto-scroll behavior: new messages follow the bottom while enabled; disabling it preserves the reader's position, and re-enabling jumps to the newest message. Update the View guide.

Interface changes: UI layout and scrollbar visibility only; no MAVLink or presenter changes.

Verification: The offscreen View suite passed (91 tests, 1 skipped). Tests confirm the telemetry tab's vertical bar is hidden, the status list's bar is visible, new messages follow the bottom while Auto-scroll is checked, and a short window brings the list into view. Disabling Auto-scroll preserves both scroll positions; re-enabling jumps to the newest message. The normal 1360×900 layout was visually inspected and fits the gauges and message details. `git diff --check` passed.

Scope/defaults: Auto-scroll remains enabled by default. Preserve current message details and clear-log behavior. No commit requested.

Status: Implemented and verified. Implementation commit: Pending (no commit requested).
