# Plans

| Plan | Description | Status | Implementation commit |
| --- | --- | --- | --- |
| [0001 MAVLink telemetry viewer](0001-mavlink-telemetry-viewer.md) | Build a themed MVP desktop viewer for heartbeat, attitude, and altitude telemetry. | Implemented | `8a28e85` |
| [0002 Bullet View flight instruments](0002-flight-instruments.md) | Add filtered vertical speed, a 0–100 m altitude scale, and attitude degree markings. | Implemented | `8c3b8f1` |
| [0003 MAVLink mission status messages](0003-mavlink-status-messages.md) | Publish indexed severity-aware mission status text and render colored history in Bullet View. | Pending | Pending |
| [0004 Local image view and telemetry layout](0004-local-image-view.md) | Move local ZMQ/SHM camera display into Bullet View with MAVLink bbox overlays and reorganized telemetry instruments. | Pending | Pending |
| [0005 Lower telemetry split](0005-lower-telemetry-split.md) | Split the lower Telemetry area into an R/P/Y summary and a status-message panel. | Pending | Pending |
| [0006 Bullet View AGL gauge](0006-agl-gauge.md) | Display standard MAVLink rangefinder AGL telemetry in the Telemetry tab. | Implemented; focused tests passed | `0493860` |
| [0007 Runtime parameters](0007-runtime-parameters.md) | MAVLink parameter UI, live tuning and remote update logs. | Implemented; tests passed | `dd84b1a47ca5f5800f8a513dd04ca180f659289b` |
| [0008 Log controls](0008-log-controls.md) | Clear local log and explicitly control auto-scroll. | Implemented; 23 tests passed | `dd84b1a47ca5f5800f8a513dd04ca180f659289b` |
| [0009 Status time and frame](0009-status-time-frame.md) | Show simulation seconds and camera sequence in status logs. | Implemented; 361 tests passed | `dd84b1a47ca5f5800f8a513dd04ca180f659289b` |

- [0010: Manual flight controls](0010-manual-flight-controls.md) — Implemented; 31 tests passed; commit `8653377251f426e1f1c6539191e2cd91480e447e`.

- [0011: Manual workspace and recording controls](0011-recording-controls.md) — Implemented; 40 tests passed; commit `8653377251f426e1f1c6539191e2cd91480e447e`.

- [0012: Flight button state](0012-flight-button-state.md) — Implemented; 84 tests passed; commit `8653377251f426e1f1c6539191e2cd91480e447e`.

- [0013: Linux GUI icons and launchers](0013-linux-gui-icons-launchers.md) — Implemented; 78 tests and installed wheel checks passed; commit Pending.

- [0014: VS Code run task](0014-vscode-run-task.md) — Run this checkout of Bullet View from VS Code; Implemented, command verified; commit Pending.

- [0015: App-only flight control](0015-app-only-flight-control.md) — View controls app-owned Auto and Manual flights; Implemented, tests and SITL checks passed; commit Pending.

- [0016: Disarm button availability](0016-disarm-button-availability.md) — Keep Arm and Disarm mutually exclusive in disarmed idle; Implemented, focused tests passed; commit Pending.

- [0017: Single-port Bullet App link](0017-single-port-app-link.md) — Use one UDP socket for App telemetry, View commands, and ACKs; Implemented and verified; commit Pending.
- [0018: Target mission status](0018-target-mission-status.md) — Show target mission, phase and result; Pending, focused tests passed; commit Pending.
- [0019: Mission approval controls](0019-mission-approval-controls.md) — Show configured height and gate Arm/Start by approval mode; Implemented, tests passed; commit `110e0f9f1c496287309ad7b6aff0ab545cc9b874`.
- [0020: Named-monitor launch](0020-named-monitor-launch.md) — Place Bullet View in the lower half of the tmuxp stack's monitor; Implemented, offscreen and live checks passed; commits `78221c8949ba238bcfe0b1cd6aa2ef8187787bb6` (`bullet_view`), `3651d5bfff7d1ac0b92a36252ab1bc5bd7c9ce44` (`bullet_ng`).
- [0021: Local camera and fid-matched bbox](0021-local-image-bbox.md) — Show local renderer frames and App-relayed detections; Implemented, tests and live smoke passed; commits `3b76b199fefc31d1d02e0efbe46d3cadd674a7c2` (`bullet_view`), `1ae98872366242be0ec6b1b156b31f8e3dcd149e` (`bullet_ng`).
- [0022: Upstream telemetry rates](0022-upstream-telemetry-rates.md) — Show App-measured attitude and altitude rates and sustained-drop alerts; Implemented, tests passed; commit `dca2ee8`.
- [0023: Manual target mission settings](0023-manual-target-settings.md) — Apply height and hover time in manual target-hit before Start; Implemented, 87 tests passed with one skip; commit Pending (no commit requested).
- [0024: Target altitude slider](0024-target-altitude-slider.md) — Restore manual target height slider and fixed five-second hover; Implemented, 87 tests passed with one skip; commit Pending (no commit requested).
