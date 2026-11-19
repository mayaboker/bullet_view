# Manual target mission settings

Goal: let an operator set target-hit takeoff height and pre-search hover duration in manual mode.

Implementation: show editable height and hover duration with one Apply settings button; send both in one command and require ACK plus matching App telemetry before reporting confirmation. Keep other missions read-only.

Interfaces: MAVLink command 31012 uses param1=height_m and param2=hover_s. App publishes HOVER_S in NAMED_VALUE_FLOAT. Settings are available while disarmed or armed idle, before Start.

Verification: focused flight-client and offscreen widget tests, then the View suite.

Scope/defaults: height 0.1–100 m; hover 0.1–600 s; default target values 10 m and 10 s. No commit requested.

Status: Superseded by [target altitude slider](0024-target-altitude-slider.md). The interim two-value settings design was implemented and tested before the height-only revision. Implementation commit: `4660e07`.
