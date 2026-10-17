# Quest Tracking Injection

**Experimental status (0.1.1):** Earlier testing included user-reported freezes
of the headset view. Version 0.1.1 removes global head-tracking mode writes from
controller sessions, requires advancing head tracking in NORMAL mode before
starting, and restores physical controller calls if the head update counter
stops advancing for more than 500 ms. An eight-second moving-pose test was
subsequently confirmed by the user with fluid head tracking. The original freeze
has not been conclusively attributed to a specific cause; long-term reliability
is not established. A counter watchdog does not monitor compositor rendering.


An experimental, root-based controller pose injector for **Meta Quest 1**.

The prototype accepts custom positions and orientations, temporarily suppresses
the physical controller pose producers, and restores the original tracking calls
when the session ends. It uses the original Meta tracking services.

**Tested firmware:** `49845030443200410` · **Android:** 10 / API 29 · **Target:** ARM64

## Demonstrated behavior

- A requested right-controller pose remained fixed for a ten-second test.
- All 22 sampled server and VR-shell snapshots matched the requested pose.
- The headset user confirmed that the virtual controller stayed fixed while the
  physical controller was moved.
- Three externally streamed positions and a changed orientation reached the VR client.
- Headset tracking continued in its original normal mode during the final tests.
- Normal completion and Ctrl+C restored the physical pose calls and tracking mode.

See [validation results](docs/validation.md) and the
[anonymized evidence](evidence/validation.json). The tests cover the Quest system
interface; compatibility with other VR applications and unattended operation has
not been established.

## Requirements

- A Quest 1 running the exact firmware above.
- ADB with an already-rooted shell: `adb shell id -u` must report `0`.
- `persist.ovr.enabletrackinginjectionsdk` already set to `true`.
- An awake headset and an active paired controller.
- Python 3 on the host and ADB on `PATH`, or an explicit `--adb` path.

During a session, the physical pose updates of **both controllers** are paused.
Only the selected controller receives the supplied poses; the other controller
may remain at its last pose. The adjacent button and status call sites are not
patched. Firmware files on disk are not modified.

## Build or use a binary release

The source archive requires a native build. The binary release includes the two
project-built ARM64 executables in `bin/`.

The build was validated with Android NDK r26b. On macOS or Linux:

```sh
export ANDROID_NDK_HOME="/path/to/android-ndk-r26b"
bash tools/build.sh
```

This creates `bin/quest-inject` and `bin/quest-source-guard`. No Meta firmware
libraries or APKs are distributed with the project.

## Run a fixed pose

Run from the repository or extracted release directory:

```sh
python3 scripts/inject_pose.py --hand right --position 0.125 -0.25 -0.5 --seconds 10 --hz 90
```

Supply a quaternion in `QX QY QZ QW` order when needed:

```sh
python3 scripts/inject_pose.py --hand right --position 0.25 -0.25 -0.5 --orientation 0 0 0.38268343 0.92387953 --seconds 5
```

The launcher discovers the active controller identifier and current process
addresses each time. Additional options:

| Option | Purpose |
|---|---|
| `--hand left` | Select the left controller; right is the default. |
| `--seconds N` | Session length, greater than zero and at most 55 seconds. |
| `--hz N` | Requested update rate, 1–500 Hz; default 90 Hz. |
| `--adb PATH` | Select an ADB executable. |
| `--serial SERIAL` | Select a connected device. |
| `--stream` | Read externally supplied poses from standard input. |
| `--restore` | Restore the two known physical call sites and NORMAL mode. |

Actual update rates depend on Binder and device load. Position and orientation
use separate Binder transactions, so a combined pose update is not atomic.

## Stream custom tracking data

Write one space-separated pose per line and flush after each line:

```text
X Y Z QX QY QZ QW
```

Connect an external tracker:

```sh
python3 your_tracker.py | python3 scripts/inject_pose.py --hand right --stream --seconds 30 --hz 90
```

An included synthetic example produces a small horizontal movement:

```sh
python3 scripts/stream_demo.py --seconds 5 | python3 scripts/inject_pose.py --stream --seconds 5
```

The native injector uses the latest complete valid line and normalizes its
quaternion. Invalid lines are counted and discarded. With no new input, it holds
the last valid pose until the bounded session ends, including after stdin closes.
`--position` and `--orientation` provide the initial pose before a streamed update
arrives. The default initial pose is `(0.125, -0.25, -0.5)` with identity orientation.

Data is passed as `WORLD_FROM_IMU_TRANSLATION` and `WORLD_FROM_IMU_ROTATION`.
Coordinate conversion and calibration belong in the external tracker.

## Stop and restore

The launcher restores physical pose calls and verifies NORMAL head mode after completion
or Ctrl+C, and verifies the original instruction bytes. A separate device-side
guard has its own timeout of session duration plus four seconds, at most 59 seconds.

For explicit recovery without starting another injection session:

```sh
python3 scripts/inject_pose.py --restore
```

Recovery sets **NORMAL = 0** and accepts only the known original or temporary NOP
instructions. The launcher refuses unexpected firmware or code. Killing both
device-side helpers with SIGKILL can prevent their cleanup; restarting the tracking
process discards the process-local patches.

The launcher uploads its own helpers to `/data/local/tmp/`. They remain available
there after a session, without a running injection or guard process.

## How it works

The resolved injection call reaches `trackingservice` at ELF address `0xe8774`,
through the adjustment thunk at `0xe8b18`. Physical tracking uses the same virtual
entry point, so source-specific suppression is needed. During a session, the guard
replaces the physical Constellation pose call at `0xaab4c` and the fallback pose
call at `0xa9830` with NOPs in the running process, then restores both instructions.

The controller injector requires NORMAL headset mode and never writes the global mode during a session. `DATAINJECT` is not
required for these controller writes. Analysis hardware breakpoints are not used
by the finished launcher.

Read the [reverse-engineering notes](docs/architecture.md) for addresses, data
layouts, and the observed device-ID lifetime bug. Occasional rejected calls are
logged and retried at most three times. Persistent rejection or transport failure
ends the session. The underlying firmware bug remains present.

## Repository layout

```text
src/                 Native injector and source guard
scripts/             Host launcher and synthetic stream example
tools/               Native build and allowlisted archive packaging
docs/                Architecture and validation notes
evidence/            Anonymized validation data
bin/                 Generated native executables; ignored by Git
```

Create shareable archives:

```sh
python3 tools/package_release.py
python3 tools/package_release.py --binary
```

The generated archives go to `dist/`, include checksums, and exclude private
research logs, firmware files, and local working directories. See
[contribution notes](CONTRIBUTING.md) before sharing logs or device reports.

## License

A license has not been selected yet.

