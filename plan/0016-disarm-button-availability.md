# Disarm button availability

Status: Implemented; focused tests passed. Implementation commit: Pending (no commit requested).

Goal: Do not show Arm and Disarm as enabled together while the app reports disarmed idle.

Implementation: Enable Disarm only for observed armed state, a pending Arm/Start transition, or unknown state with a known app target. Treat Disarm during pending Arm as an emergency cancellation requiring confirmation.

Interface: No wire or CLI changes; only Bullet View button availability and confirmation behavior change.

Verification: The focused offscreen flight-control suite passed (30 tests). The full suite reported 70 passed and one skipped, then intermittently exited 139 during Qt interpreter shutdown; this test-runner teardown issue remains. No commit requested.
