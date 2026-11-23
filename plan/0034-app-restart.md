# Restart Bullet App after simulator reset

Status: Implemented. Implementation commit: Pending (no commit requested).

## Goal
Let the operator recreate a manual Bullet App flight session from the Simulation tab.

## Implementation
- Add a separate Restart Bullet App control, gated by fresh stopped-ready simulation and App status.
- Send MAVLink command 31013 and wait for final ACK, changed App epoch, and fresh disarmed readiness.
- Show a modal outcome with a 45-second timeout; do not retry automatically.
- Clarify the Reset → Restart App → Start simulation sequence.

## Interface
COMMAND_LONG 31013, COMMAND_ACK progress/final, APP_STATE and APP_EPOCH named values.

## Verification
97 View tests passed with one skip. Live SITL integration was not run during this change.

## Scope and defaults
Only explicit operator action triggers restart.
