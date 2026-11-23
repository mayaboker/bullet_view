# Target altitude slider

Goal: restore the manual target-hit altitude slider and use one height value for takeoff and hover.

Implementation: link a 0–100 m slider and numeric field, require 0.1–100 m to Apply, remove hover-duration editing, and confirm the height-only command from ACK plus TAKEOFF_H telemetry before Start.

Interfaces: command 31012 carries height_m in param1 with every other parameter zero. HOVER_S remains display telemetry for the fixed five-second duration.

Verification: offscreen slider synchronization, zero guard, command feedback, and the View suite.

Scope/defaults: manual target-hit only; other missions retain their profile settings. No commit requested.

Status: Implemented; 87 View tests passed with one skip. Implementation commit: `4660e07`.
