# Local MAVLink status text support

Goal: Move Bullet View's remaining status-text parser and display metadata into View and remove its `bullet-msgs` dependency.

Implementation steps: Add a View-owned status text module with the current indexed/context parser, chunk helper used by tests, severity constants, and message descriptions. Switch worker, model, view, and tests to it. Remove `bullet-msgs` from `pyproject.toml` and refresh `uv.lock`.

Interface changes: No MAVLink wire changes. Preserve indexed `STATUSTEXT` parsing, context time/frame display, message descriptions, and severity colors. Bullet View has no runtime or dependency import of `bullet_msgs` afterward.

Verification: The View suite passed offscreen with the locked environment (87 tests, one skipped). A new parser test covers indexed/context and legacy text, and an import-boundary test checks View source and declared dependencies. `uv lock --check` and `git diff --check` passed. The built wheel contains the local status module and has no `bullet-msgs` requirement.

Scope/defaults: Preserve the existing uncommitted parameter and recording changes. Do not change Bullet App or the external `bullet_msgs` package.

Status: Implemented and verified. Implementation commit: `007da997731b1688616629c9f83e2418b1c85d86`.
