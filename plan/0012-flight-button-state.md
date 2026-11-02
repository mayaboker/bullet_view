# State-based Arm and Start mission buttons

- Status: Implemented; verified 2026-11-02
- Implementation commit: Pending

Gate Arm on fresh, connected, confirmed disarmed/prearm-ready state. Gate Start
on confirmed armed idle and matching applied height. Disable both for unknown,
stale, inconsistent, flying/reset-required states and pending flight commands.
Use the same checks for UI availability and worker dispatch, distinguish a closed
control connection from stale remote telemetry, disable immediately on submission,
and restore from worker-confirmed state. Show disabled styling and clear reasons.
Keep Disarm usable for a known connected target while Arm/Start is pending.
Preserve recording, protocol and backend behavior. These widgets are in
bullet_view; bullet_visual remains the camera/detector process.

Verify state matrix, stale/disconnected state, pending/ACK transitions, conflicting
readiness/armed values, height confirmation and unchanged Disarm/recording controls.
Use uv/shared lockfile and offscreen Qt, no physical flight or process restart.

## Result and verification

One shared policy now checks Arm/Start in the view, presenter and worker: exact
known app target, open command connection, fresh valid feedback, consistent
observed armed/readiness state, no pending command, and confirmed matching valid
height for Start. Arm requires disarmed/prearm ready; Start requires armed idle.
Mission active/reset-required/unknown/stale/inconsistent states disable both.
The worker reports control availability independently from received telemetry.

The presenter marks a request queued immediately, rejects duplicate submissions,
and retains that lock across earlier queued telemetry until a worker receipt.
Disarm can supersede a queued Arm/Start; an older receipt cannot unlock it.
Queue-full and worker-rejection paths restore the appropriate state. Command
ACK/readback semantics and the backend/wire protocols are unchanged.

Disabled buttons are dimmed, enabled buttons have a clear border, and Arm/Start
have visible reasons/tooltips. The initial result now says no command was sent
instead of implying remote feedback is still missing after state arrived.

84 unique tests passed: bullet_view 63 and bullet_app manual flight 21, using uv
and the shared lockfile. The full offscreen viewer suite exited successfully
three consecutive times after fixing matrix-widget cleanup and isolating
presenter unit coordination from unused QThreads. Qt fixture teardown collects
signal cycles while the application is alive. Earlier runs passed assertions
but failed at Qt shutdown; they are not counted as successful runs.
Rendered and visually inspected armed-idle/disarmed-ready windows. Coverage
includes the state matrix, contradictory arming/readiness, missing/invalid height,
pending/old telemetry, request preemption, queue full, worker rejection, stale
state and closed command connection. Existing recording/UI tests pass. Git
whitespace checks passed. No running process or physical motors were actuated.
No commits or pushes; implementation commit remains Pending.
