# Bullet View

Bullet View is the local flight dashboard for Bullet App. It receives app-owned
MAVLink telemetry on `udpin:127.0.0.1:14550`. After App sends its first packet,
View returns its heartbeat and flight commands on that same UDP socket and
receives command ACKs there. It does not connect to
Betaflight SITL or to the renderer. The camera, parameter, and recording
panels remain visible but disabled until Bullet App supports them.

## Run

Start the Bullet Drone SITL launcher, then `bullet-app --mode auto` or
`bullet-app --mode manual`. Open **bullet_view: Bullet: Run view** from the
multi-root workspace's VS Code tasks, or run:

```sh
cd /home/user/projects/bullet_view
uv sync --group dev
uv run --locked bullet-view
```

The mode is selected when Bullet App starts and shown in View. View cannot
change mode during a flight.

The App–View MAVLink messages, commands, and port layout are documented in
[App–View MAVLink communication](docs/app-view-mavlink.md).

## Flight controls

- **Auto:** Wait for the app's disarmed ready state, click **Arm**, then
  **Start auto mission**. The app climbs 10 m above launch, holds for 10
  continuous seconds, lands, and disarms.
- **Manual:** Apply a takeoff height from 0.1 to 100 m in 0.1 m steps, click
  **Arm**, then **Takeoff**. The app holds the selected height until **Land**
  is clicked, then lands and disarms.
- **Disarm** works on the ground. During flight it asks for emergency
  confirmation, because it immediately stops the motors.

Buttons wait for an app acknowledgment and matching observed flight state.
The app remains running after a normal landing, ready for another flight.
If View disconnects for more than 3 seconds, the app disarms on the ground
or lands if airborne. The app reports a fault when SITL telemetry becomes
stale; restart it before flying again.

The dashboard shows app-relayed attitude and altitude, vertical speed,
armed state, mission phase, and status messages. The image panel is disabled:
there is no direct renderer image subscription.

## Desktop launcher

The installed wheel includes a desktop launcher and icon. Register or remove
the launcher with:

```sh
bullet-view --install-launcher
bullet-view --uninstall-launcher
```

Run tests without a display using `QT_QPA_PLATFORM=offscreen uv run --locked
pytest -q`.
