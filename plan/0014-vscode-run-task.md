# VS Code run task

Status: Implemented; task and locked command verified. Implementation commit: Pending (no commit requested).

Goal: Launch this `bullet_view` checkout from the multi-root VS Code workspace.

Implementation: Add a play-icon task using `uv run --locked bullet-view` with the project as its working directory. Replace the stale workspace-only `bullet-msgs` source with the available local package path and create a standalone lockfile so the command resolves.

Interface: `bullet_view: Bullet: Run view` appears under Tasks: Run Task. The viewer's CLI and default endpoints remain unchanged.

Verification: Parsed task JSON, resolved a standalone `uv.lock`, and ran `uv run --locked bullet-view --help` successfully. No commit requested.
