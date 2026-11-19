# Named-monitor launch

Status: Implemented; offscreen and live checks passed
Implementation commits: `78221c8949ba238bcfe0b1cd6aa2ef8187787bb6` (`bullet_view`), `3651d5bfff7d1ac0b92a36252ab1bc5bd7c9ce44` (`bullet_ng`)

Goal: Let the tmuxp hover/land stack place Bullet View in the bottom half of the same display as Godot.

Implementation steps: Add an optional `--monitor NAME` CLI option, select the matching Qt screen, and size/move the window into its available geometry. Warn and use the primary screen if the name is absent.

Interface changes: `bullet-view --monitor NAME [--monitor-half top|bottom]`; ordinary launches retain current window behavior.

Verification: Focused offscreen Qt tests and CLI invocation.

Scope/defaults: The workspace tmuxp stack requests the bottom half of DP-1-0.

Verification outcome: Three offscreen Qt placement tests passed. The live tmuxp launch placed View at 1940,1017 in the bottom half of DP-1-0; `git diff --check` passed.
