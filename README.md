# Bullet View

Bullet View is a MAVLink telemetry, parameter management and local camera window for Bullet
flight runs.

Mission `STATUSTEXT` messages are shown in the Telemetry tab with their MAVLink
severity color. **Clear log** removes the viewer's stored messages, selection and
message details; new messages continue arriving. Remote logs and MCAP recordings
are unaffected. **Auto-scroll** starts checked and follows new messages, including
after mission completion. Uncheck it to preserve your reading position; check it
again to jump to the newest message. Clearing the log keeps the checkbox state,
and restarting the viewer restores the checked default.
Each row replaces the message-code prefix with simulation seconds since scenario
start and the associated camera image sequence, for example
`[27.075 s | frame 4809] LOS_ACQUIRE: ...`. The frame is the processed observation
when available; otherwise the app uses the latest received image from the same
physics/episode. It is a camera sequence, not a FlightLens replay ordinal or a
viewer counter. Simulation time resets with each scenario and pauses with it.
Every text chunk carries its own context. Unknown fields, including older remote
applications and unindexed messages without metadata, display `—`; arrival time
is never substituted. Restart both updated applications once to receive metadata.
Click a message to inspect its severity, original message code, source context,
received text and description.
When the vehicle is stopped, use **Reload mission profile** to ask the app to
reread its mission YAML before the next scenario start.
It uses the same dark blue/teal visual theme as FlightLens. Local mode reads
the camera descriptor from ZMQ and pixels from SHM, then overlays bbox values
received through MAVLink named values. Remote mode is telemetry-only until the
v2 stream viewer is implemented.

## Run

```bash
uv run --locked --package bullet-view bullet-view
```

The default input is `udpin:0.0.0.0:14550`. Override it with:

```bash
uv run --locked --package bullet-view bullet-view --mavlink-endpoint udpin:0.0.0.0:14550
```

Local image transport can be overridden with `--image-endpoint` and
`--image-topic`. The Telemetry tab's Image mode selector switches between Local
and the telemetry-only Remote placeholder.

`bullet-app` mission runs publish to that port by default. Start both commands
with the same port, or override the app's `--mavlink-endpoint` output and this
viewer's input together.

The Telemetry tab displays HEARTBEAT, ATTITUDE, ALTITUDE, filtered vertical speed,
local camera frames and bbox overlays. The altitude gauge spans 0–100 m.
Automatic transport reconnect and remote image streaming remain deferred.

## Parameters and runtime tuning

Start an updated `bullet-app` alongside Bullet View. Telemetry defaults to UDP
14550; parameter requests use `--mavlink-control-endpoint udpout:127.0.0.1:14551`
(the app listens on `udpin:0.0.0.0:14551`). The Parameters tab automatically loads
the complete active mission profile through MAVLink 2 Extended Parameters.
Values use runtime SI units; descriptions, categories and edit policies come from
the shared versioned Bullet catalog. This service manages the mission profile,
not Betaflight firmware PID settings.

Search by parameter name, select a category, or check Favorites Only. Mark stars
to retain favorites across viewer restarts. Hover over a description or value to
see the full text/confirmed precision. Edit a value and click its row's Apply;
Pending becomes Applied only after the remote control thread accepts the edit.
Rejected keeps the effective remote value. Unconfirmed means delivery/application
could not be established; click Refresh after connection returns. Writes and
export are unavailable with stale heartbeats or incomplete synchronization.

For a runtime example, during LOS approach search `azimuth_kp`. On the reviewed
heavy-quad profile, change `tuning.azimuth_kp` from `2.2` to experimental value
`1.5`, then Apply. The MAVLink ID is `LOS_AZ_KP`. The next control calculation
uses the new gain without restarting acquisition or clearing the acquired LOS,
estimators, integrals or correction memories. Existing angle/slew limits still
apply. This example is a tuning trial, not a flight-validated setting.

Live fields are yaw heading gain, azimuth proportional/rate/integral gains, and
elevation proportional/rate/integral gains. Other edits require the mission to be
stopped and the whole candidate profile to remain valid and platform-compatible.
Active COMMIT rejects edits because it intentionally freezes its saved demand.

The remote `bullet-app` logs applied/rejected edits, including old/effective
values, requester, mission phase and configuration revision. A concise result
also appears in the Telemetry log. Structured events are published on
`analysis/app/parameters`; the bundled recorder saves them with configuration
snapshots for retrospective analysis.

Edits last for the application session (including subsequent scenario resets).
Restarting the app or reloading its mission YAML replaces them. Export YAML saves
the entire confirmed profile, including hidden/nonfavorite parameters, using the
degree keys accepted by `bullet_app --mission-config <export.yaml>`. It does not
write to the remote mission file. Download/export revision checks prevent mixing
values from different configurations. String fields must fit MAVLink's 128-byte
extended value after JSON encoding; both apps must use a matching catalog version.

### Flight controls

The persistent panel above the tabs provides **Arm**, takeoff-height slider and
numeric editor, **Apply height**, **Start mission**, and **Disarm**. Connect to an
application launched with `--mission-config … --arming-mode manual`; in simulation,
start the physics/Godot session first. Production bringup selects manual mode.

The editable number is a draft (0.1–100.0 m above launch). **Applied height** starts
as unknown and displays remote telemetry only. Apply waits for both the addressed
MAVLink ACK and a matching remote value. Start is enabled only after confirmed
armed idle, with no pending command and draft equal to applied height. Arm alone
holds minimum throttle. Height locks during flight.

Observed arming/readiness and ACK results are shown separately. Stale or missing
flight feedback disables Arm/Apply/Start. Disarm remains available for a known
application target and cancels pending flight actions. During a mission or with
unknown state it asks for emergency confirmation, default **Cancel**; confirmation
aborts mission control and requests backend disarm. Stop/reset before rearming.
No flight command is retried automatically. Use the existing app command endpoint
(default `udpout:127.0.0.1:14551`), not a separate autopilot connection.

Arm/Start availability follows confirmed remote state:

| State | Arm | Start mission |
|---|---|---|
| Disarmed, prearm ready | Enabled | Disabled |
| Armed idle, confirmed height matches editor | Disabled | Enabled |
| Pending command, mission active, reset required, stale/unknown state or closed control connection | Disabled | Disabled |

Conflicting armed/readiness reports also disable both buttons. Disabled buttons
are visibly dimmed; the reason appears below the observed state and in tooltips.
Submitting a command locks conflicting actions immediately, including while the
worker queue is processing it. Disarm remains available for a known connected
target during pending Arm/Start. Confirmed state and command results are separate.

### Recording controls

**Start recording** and **Stop recording** are always visible above the tabs.
The workspace Run all task selects MAVLink recording through
`config/operator_controls.yaml`; production bringup uses
`recorder.control_source: mavlink`. Restart the launcher after changing authority.
The recorder must run with `--control-mode recording`, which both launchers set.

The panel shows actual remote state (idle, recording, finalizing, error, unknown)
and control authority. Start waits for idle/error and fresh app telemetry. Stop
can cancel a pending Start. Both operations wait for an addressed command ACK
and matching recorder telemetry; Stop succeeds after the MCAP is finalized.
Requests time out with an unknown outcome and are not retried automatically.
Stale recording observations become unknown. Godot authority disables these
buttons and displays an explanation. Recording is independent of flight Arm,
Start mission and Disarm, and also works in detection-only sessions.
