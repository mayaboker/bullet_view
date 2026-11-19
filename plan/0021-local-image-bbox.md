# Local camera and fid-matched bbox

Status: Implemented; tests and live smoke passed
Implementation commits: `3b76b199fefc31d1d02e0efbe46d3cadd674a7c2` (`bullet_view`), `1ae98872366242be0ec6b1b156b31f8e3dcd149e` (`bullet_ng`)

Goal: Show renderer images in View and overlay only same-fid target detections.

Implementation: Add a local ZMQ/SHM image worker, V2_EXTENSION bbox decoder, bounded image matching, and local camera mode. Enable the image endpoint in both tmux stacks.

Interface: `bullet-view --image-endpoint ENDPOINT` enables `camera/front/image` from the renderer. Bbox uses V2_EXTENSION message_type 32768 on the existing App link.

Verification: Offscreen frame matching and widget tests, wire decoding, and live stack smoke checks.

Scope: Hover/land shows raw camera images; target-hit adds bbox overlay. No direct Visual connection.

Verification outcome: 82 View tests passed (1 skipped), locked dependencies resolved, and live hover and target stacks showed raw and fid-matched camera images respectively.
