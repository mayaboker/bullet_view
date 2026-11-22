# Bullet View

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
armed state, mission phase, and status messages. Launch with
`--image-endpoint tcp://127.0.0.1:5556` to show the local renderer image.
For target-hit, Bullet App relays fid-tagged detections over the existing
MAVLink link; View overlays only boxes matching a displayed image fid.

## Desktop launcher

The installed wheel includes a desktop launcher and icon. Register or remove
the launcher with:

```sh
bullet-view --install-launcher
bullet-view --uninstall-launcher
```

Run tests without a display using `QT_QPA_PLATFORM=offscreen uv run --locked
pytest -q`.
