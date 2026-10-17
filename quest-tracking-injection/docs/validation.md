# Validation

## Follow-up correction and 0.1.1 test — October 17, 2026

The user clarified that earlier apparent controller freezes sometimes included
the entire headset view. The earlier fixed-pose visual confirmation is therefore
ambiguous and does not establish reliable operation. Historical memory snapshots
remain evidence of pose delivery only.

Version 0.1.1 removes global head-mode transactions from normal controller
sessions. It refuses a non-NORMAL mode or an unchanging head counter before
starting. The device-side guard samples the head update counter and mode every
10 ms and restores physical calls after more than 500 ms without an update or
an observed non-NORMAL mode. This is a mitigation, not a proven root-cause fix.

Follow-up hardware tests:

- Three seconds at 30 Hz: 90 accepted pose updates; one rejected field retried.
- Eight seconds of synthetic motion at 60 Hz: 480 accepted updates, 720 input
  poses consumed, no invalid input lines; one rejected field retried.
- A further five-second run completed 300 updates at 60 Hz, consuming 450 input poses; four rejected fields were retried.
- All three runs completed with the original physical call instructions verified and
  NORMAL head mode verified. The head counter watchdog did not fire.
- After the actual moving-pose run, the user explicitly confirmed that the right
  virtual controller moved and the headset view remained fluid while turning.
- An isolated device-side test using synthetic memory, not trackingservice,
  froze a simulated head counter. The guard detected it and restored both
  original instruction words after 0.501 seconds; the test passed.

No claim is made that the original intermittent freeze has been reproduced or
eliminated. Further repeated tests and compositor observations are needed.

## Historical evidence (0.1.0)


## Hardware and scope

Validation was performed on one rooted Meta Quest 1 running Android 10/API 29,
firmware `49845030443200410`, on October 16–17, 2026.

The public results are a curated, anonymized export of the original private
observations. They are not a new independent replication. Device identifiers,
serials, personal paths, live addresses, process IDs, and raw log strings have
been omitted. ELF-relative offsets remain documented for reproducibility.

The artifacts were organized and rebuilt for publication afterward. That cleanup
was checked with native compilation, host-side syntax and command-line checks,
and release-content verification; it did not trigger another headset test.

## Stable-pose test

Requested right-controller pose:

```text
position:    0.125 -0.25 -0.5
orientation: 0 0 0 1
duration:    10 seconds
rate:        requested 90 Hz
```

The injector completed 900 pose updates, requiring at least 1,800 accepted field
transactions. Three temporary rejected field calls were successfully retried.
All 22 sampled snapshots, spanning approximately 0.30–9.46 seconds, matched the
requested pose in both the tracking process and the running VR-shell client.
The snapshot helper checked counters before and after copying each sample.

The headset user was asked whether the virtual right controller stayed fixed
while the real controller was moved. The user confirmed that it did. This is a
human observation, separate from the shared-memory measurements; no demo video
is included in this repository.

The original call instructions were restored after the test. Subsequent samples
contained physical poses again and showed advancing update counters.

## External streaming test

The final launcher accepted three changing poses from an external stdin producer:

| Sample | Position | Quaternion |
|---|---|---|
| 1 | `(0.125, -0.25, -0.5)` | `(0, 0, 0, 1)` |
| 2 | `(0.25, -0.25, -0.5)` | `(0, 0, 0, 1)` |
| 3 | `(0.125, -0.1, -0.5)` | `(0, 0, 0.38268343, 0.92387953)` |

All three matched independently read server and VR-client snapshots within
`1e-6` per component. The final four-second run completed 360 updates, accepted
three input lines, discarded no invalid lines, and recovered from six rejected
field calls. Its exit code was zero. Both physical call sites and the original
mode were restored.

## Headset tracking and interruption

In the interruption test, the headset mode remained NORMAL. Its tracking counter
advanced during controller injection. Sending SIGINT to the host launcher caused
the native injector to stop and the guard to restore both physical pose call
instructions. The host exited with code 130, and the mode and instruction bytes
were read back successfully.

The explicit `--restore` command was also checked on the restored system. The
device's on-disk `trackingservice` hash matched the original firmware executable,
and no injector, guard, or hardware-debug observer process remained running.

## Important limits

- Only the documented Quest 1 firmware and the tested system interface are covered.
- The guard pauses the physical pose producers for both controllers.
- The launcher feeds one selected controller per session.
- Position and orientation are separate field transactions.
- Long-running reliability, every VR application, and other firmware are untested.
- Bounded retries mitigate occasional identifier parsing failures; they do not
  repair the firmware bug.
- Automatic cleanup handles normal completion and tested interruption paths;
  forcibly killing both device-side helpers can bypass it.

See [the anonymized machine-readable evidence](../evidence/validation.json).

