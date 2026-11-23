# Bullet View

## Overview

Bullet View is the local flight dashboard for Bullet App. It receives app-owned
MAVLink telemetry on `udpin:127.0.0.1:14550`. After App sends its first packet,
View returns its heartbeat and flight commands on that same UDP socket and
receives command ACKs there. It does not connect to Betaflight SITL. With
`--image-endpoint`, it subscribes directly to the local renderer camera;
parameter controls remain unavailable. View has no recording controls.
View interprets App flight-control values with local constants and a local
readiness enum. The App–View flight link carries MAVLink messages only; it does
not exchange `bullet_msgs` objects. View owns its flight, parameter, and status
message interpretation locally. The parameter tab remains disabled because
the current App has no parameter responder. View no longer depends on
`bullet_msgs`.

View shows **SITL confirmed** when App's startup MSP board-info query returned
`SITL`, **SITL not confirmed** when it did not, and **SITL status unknown**
without a fresh App heartbeat. This reports firmware identity, not whether the
physics simulator is exchanging data.
The header shows **Telemetry stale** in red when no App heartbeat arrives for
three seconds, even if other MAVLink packets continue. A new App heartbeat
restores the connected status.

## Features

- MAVLink telemetry and mission controls for Bullet App.
- Optional local camera with matched target bounding boxes.
- A Simulation tab that uses direct ZeroMQ commands and the launcher's state feed.

## Architecture

The presenter coordinates immutable telemetry and simulation snapshots. MAVLink,
image, and simulation workers own their connections outside the GUI thread.
The Simulation tab subscribes to the launcher's state topic for button
availability; command replies determine the result dialogs.

## Requirements

Python 3.12 or newer, uv, and a desktop supported by PySide6 are required.
The launcher and Bullet App are separate processes for a complete flight stack.

## Installation

From this checkout, install the locked development environment with
`uv sync --locked --group dev`.

## Quick Start

Start the Bullet Drone SITL launcher, then `bullet-app --mode auto` or
`bullet-app --mode manual`. Open **bullet_view: Bullet: Run view** from the
multi-root workspace's VS Code tasks, or run:

```sh
cd /home/user/projects/bullet_view
uv sync --locked --group dev
uv run --locked bullet-view
```

The mode is selected when Bullet App starts and shown in View. View cannot
change mode during a flight.

The App–View MAVLink messages, commands, and port layout are documented in
[App–View MAVLink communication](docs/app-view-mavlink.md).

## Usage

### Flight controls

- **Manual approval:** Wait for the app's disarmed ready state, click **Arm**,
  then **Start hover mission** or **Start target mission**. The selected
  mission runs its startup profile. The hover/land default is 20 m above
  launch for 10 continuous seconds before landing.
- **Automatic approval:** App arms and starts one selected mission after SITL
  is ready, without waiting for View. View displays progress if connected.
- The mission profile sets the takeoff height. View displays it read-only.
  **Land** can abort an active flight.
- **Disarm** works on the ground. During flight it asks for emergency
  confirmation, because it immediately stops the motors.

Buttons wait for an app acknowledgment and matching observed flight state.
In manual approval mode, App remains running after a normal landing, ready
for another flight. If View disconnects for more than 3 seconds, App disarms
on the ground or lands if airborne. Automatic mode requires no View connection
and exits after the flight. The app reports a fault when SITL telemetry becomes
stale; restart it before flying again.

The dashboard shows app-relayed attitude and altitude, vertical speed,
armed state, mission phase, and status messages. The visible vertical scrollbar
belongs to the status message list. **Auto-scroll** is enabled by default and
keeps new messages at the bottom; turn it off to read earlier messages without
losing your position, then turn it on to jump to the newest message. In a short
window, Auto-scroll also brings the message list into view. Launch with
`--image-endpoint tcp://127.0.0.1:5556` to show the local renderer image.
For target-hit, Bullet App relays fid-tagged detections over the existing
MAVLink link; View overlays only boxes matching a displayed image fid.

### Simulation controls

The **Simulation** tab shows the launcher's current state and enables Start,
Stop, and Reset only while the state feed is fresh. Its command endpoint defaults
to `tcp://127.0.0.1:5561`; state arrives on `simulation/drone_1/state` from
`tcp://127.0.0.1:5555`. Stop requires Reset before Start. Reset restarts the
launcher's physics, sensors and Betaflight SITL, then leaves the simulation
stopped. Press **Restart Bullet App** after a successful Reset, then **Start simulation**
and use the flight controls for the next mission. Success and failure appear in
modal dialogs. App restart uses MAVLink command `31013`, waits for a final ACK,
a new `APP_EPOCH`, fresh disarmed readiness, and times out after 45 seconds. A
timeout reports an unknown outcome; View does not retry.
No controls are available while the state feed is stale or absent. The state
feed requires the launcher renderer telemetry publisher.

### Desktop launcher

The installed wheel includes a desktop launcher and icon. Register or remove
the launcher with:

```sh
bullet-view --install-launcher
bullet-view --uninstall-launcher
```

## Configuration

`--simulation-control-endpoint` changes the loopback command REQ destination;
`--simulation-state-endpoint` changes the loopback state SUB destination. Set
the matching launcher command endpoint when overriding the default. The local
camera uses `--image-endpoint`; App telemetry uses `--mavlink-endpoint`.

## Project Structure

`src/bullet_view/` contains the UI, presenter, models and I/O workers;
`tests/` contains headless protocol and offscreen widget tests; `plan/` records
implementation plans.

## Development

Use uv for dependency and lockfile changes. Keep network I/O out of widgets.

## Testing

Run tests without a display using `QT_QPA_PLATFORM=offscreen uv run --locked
python -m pytest -q`.

## Documentation

See [App–View MAVLink communication](docs/app-view-mavlink.md) for the flight
protocol and the [Bullet Drone launcher control design](../bullet_drone/docs/design/launcher-simulation-control.md)
for simulation requests and state.

## Troubleshooting

If the Simulation tab reports stale state, check that the launcher is running
with rendering enabled and that View's state endpoint matches the renderer
telemetry endpoint. After Reset, restart Bullet App before another mission.

## Roadmap

No roadmap is specified here.

## Contributing

Follow [AGENTS.md](AGENTS.md) for project conventions.

## License

No license is specified in this repository.
