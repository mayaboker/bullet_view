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
