# Simulation controls

Status: Pending. Implementation commit: Pending.

## Goal
Provide a Simulation tab with Start, Stop, and Reset controls synchronized to launcher state.

## Implementation
- Send shared command requests to launcher TCP 5561 in a worker, and subscribe to `simulation/drone_1/state` on telemetry TCP 5555.
- Enable controls only from fresh, ordered state. Show modal success/failure/unknown for each command, with no automatic retries.
- Explain that successful reset restarts SITL and requires a manual Bullet App restart before another flight.

## Verification
The full offscreen View suite passed twice: 94 passed, 1 skipped. Tests cover stale/order handling, button/modal behavior and a real ZeroMQ worker round trip. A headless launcher command smoke test passed; live SITL remained occupied by the current mission stack.

## Defaults
Initial launcher run starts automatically. Reset remains stopped. Command and state endpoints are configurable CLI options.
