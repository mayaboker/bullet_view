# App module reference

Goal: Keep the View integration guide's App runtime reference accurate after Bullet App renames its runtime module.

Implementation steps: Point the control-loop reference in `docs/app-view-mavlink.md` to `bullet_app/src/bullet_app/app.py`.

Interface changes: None; documentation only.

Verification: Confirmed the App file exists and `git diff --check` passes.

Scope/defaults: Do not change View runtime or protocol behavior.

Status: Implemented and verified. Implementation commit: Pending (no commit requested).
