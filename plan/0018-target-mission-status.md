# Target mission status

Status: Pending
Implementation commit: Pending

Goal: Show the App-selected target mission, phase, and result in Bullet View.

Implementation: Decode additional App MAVLink named values and status text on the existing socket; keep View Arm/Start actions.

Interfaces: Mission and result named values; appended phase IDs.

Verification: Model and offscreen UI tests.

Verification outcome: Focused flight-control tests passed.

Follow-up: Read the shortened mission field, show detector readiness before Start, and document denied-command status messages. Focused flight-control and worker tests passed.

Scope/defaults: No camera preview or mission switching in View.
