# Changelog

## 0.1.1 — Head tracking freeze mitigation

- Remove global headset-mode writes from controller sessions.
- Require NORMAL mode and an advancing head counter before patching.
- Restore physical calls on a head counter stall over 500 ms or mode change.
- Stop the injector if the guard exits early.
- Correct earlier reliability claims following user-reported headset freezes.
- User confirmed an eight-second moving-pose test with fluid head tracking.
- The original intermittent freeze cause remains unproven.


## 0.1.0 — Prepared for publication

- Root-based controller pose injection for Quest 1 firmware `49845030443200410`.
- Reversible suppression of the normal and fallback physical pose call sites.
- Fixed-pose and stdin-streaming modes with bounded sessions.
- Original headset tracking mode retained.
- Verified restoration after completion and Ctrl+C.
- Device-side timeout guard and explicit restoration command.
- English documentation, portable build scripts, and anonymized test evidence.

Hardware validation was performed on October 16–17, 2026. Publication of this
repository or a release is a separate step.

