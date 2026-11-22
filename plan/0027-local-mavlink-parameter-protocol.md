# Local MAVLink parameter protocol

Goal: Remove `bullet_msgs` from Bullet View's parameter communication code while keeping MAVLink 2 Extended Parameters and the existing parameter UI behavior.

Implementation steps: Move the parameter catalog metadata and binary value codecs into Bullet View. Move MAVLink 2 connection setup into View-owned code. Update the parameter client, panel, worker, and tests to use local definitions; keep parameter IDs, order, types, limits, and YAML export behavior unchanged.

Interface changes: No wire changes. The View parameter client continues to use `PARAM_EXT_REQUEST_READ`, `PARAM_EXT_REQUEST_LIST`, `PARAM_EXT_SET`, `PARAM_EXT_VALUE`, and `PARAM_EXT_ACK` with the existing catalog IDs. The App still has no parameter responder and the View tab remains disabled.

Verification: View's offscreen suite passed (93 tests, one skipped). New independent tests cover the local catalog, binary value codecs, MAVLink Extended Parameter requests, and the source import boundary. `uv build --wheel` succeeded and the wheel contains the catalog JSON, codec, and MAVLink 2 setup. `git diff --check` passed.

Scope/defaults: Keep the existing static catalog as View-owned metadata because MAVLink Extended Parameters do not carry UI descriptions, categories, YAML paths, or live-edit policy. Leave unrelated recording and status helpers untouched.

Status: Implemented and verified. Implementation commit: Pending (no commit requested).
