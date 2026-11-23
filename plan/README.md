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
- [0023: Manual target mission settings](0023-manual-target-settings.md) — Interim two-value settings design; Superseded by 0024; commit `4660e07`.
- [0024: Target altitude slider](0024-target-altitude-slider.md) — Restore manual target height slider and fixed five-second hover; Implemented, 87 tests passed with one skip; commit `4660e07`.
- [0025: SITL status from App heartbeat](0025-sitl-status.md) — Display App-confirmed Betaflight SITL identity; Implemented, 89 View tests and live heartbeat passed; commit `c6256fc2f3c9e55eb0bb61d7b829ce22b82ba3a7`.
- [0026: Local MAVLink flight protocol interpretation](0026-local-mavlink-flight-protocol.md) — Move App–View flight constants and validation into View while preserving MAVLink values; Implemented, 90 View and 52 App tests passed; commit `16fa5d6`.
- [0027: Local MAVLink parameter protocol](0027-local-mavlink-parameter-protocol.md) — Move View parameter catalog and codecs out of `bullet_msgs` without changing MAVLink fields; Implemented, 93 tests passed; commit `007da99`.
- [0028: Remove View recording controls](0028-remove-recording-controls.md) — Remove recording Start/Stop UI and recording MAVLink paths from View; Implemented, 85 tests passed; commit `007da99`.
- [0029: Local MAVLink status text](0029-local-status-text.md) — Move status parsing and descriptions into View and remove its last `bullet-msgs` dependency; Implemented, 87 tests passed; commit `007da99`.
- [0030: App module reference](0030-app-module-reference.md) — Update the integration guide after the App runtime module rename; Implemented and verified; commit Pending (no commit requested).
- [0031: Red App heartbeat stale status](0031-red-app-heartbeat-stale.md) — Show a red stale status when Bullet App heartbeats time out; Implemented, 90 tests passed and 1 skipped; commit Pending (no commit requested).
- [0032: Status-message-only scrolling](0032-status-message-only-scroll.md) — Show the scrollbar on status messages and keep Auto-scroll following new entries; Implemented, 91 tests passed and 1 skipped; commit Pending (no commit requested).
- [0033: Simulation controls](0033-simulation-controls.md) — Add synchronized launcher Start, Stop, and Reset controls; Pending; commit Pending.
- [0034: Restart Bullet App](0034-app-restart.md) — Restart a manual SITL flight session through MAVLink after simulator reset; Implemented, 97 View tests passed with one skip; commit Pending.
- [0035: Complete App restart from ready epoch](0035-restart-ready-epoch.md) — Keep restart pending across App UDP reopen and confirm a new ready epoch; Implemented, 98 View tests passed with one skip in split runs; commit Pending (no commit requested).
