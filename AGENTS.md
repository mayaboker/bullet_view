# Bullet View project guidance

## Architecture

- Keep the application in MVP form: immutable telemetry models, a PySide6 view,
  and a presenter that owns coordination.
- The MAVLink worker owns the connection and runs outside the GUI thread.
- The view must not import `pymavlink` or perform network I/O.
- Parameter writes use MAVLink 2 Extended Parameters and require a remote
  acknowledgment after control-thread application. Automatic reconnect remains deferred.

## Constants

- Put physical units, polling periods, stale-data limits, and UI dimensions in
  named module-level `UPPER_SNAKE_CASE` constants.
- Do not scatter unexplained numeric literals through widgets or protocol code.

## Libraries and tooling

- Use `uv` for dependencies, lockfile updates, and commands.
- Use PySide6 Essentials for the desktop UI and `pymavlink` for MAVLink input.
- Keep diagnostics separate from telemetry state; use standard `logging` only
  at the application boundary.

## Testing

- Test model updates and protocol-to-model conversion without a display.
- Use the offscreen Qt platform for widget and presenter tests.
- Every new non-trivial conversion or state branch gets a focused test.

## Plans

- Save an implementation plan in `plan/` before authorized implementation.
- Keep `plan/README.md` current, using `Pending` until an implementation commit
  exists and recording the actual commit hash afterward.
