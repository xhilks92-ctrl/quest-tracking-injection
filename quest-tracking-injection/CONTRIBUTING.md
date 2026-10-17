# Contributing

## Reports

Include the headset model, exact firmware build, host OS, Python version, ADB
version, command arguments, and whether restoration completed. State whether the
headset and selected controller were awake. The current offsets are validated
only for the documented Quest 1 firmware.

Before posting logs, redact ADB serials, controller identifiers, account details,
local user paths, and live process addresses. ELF-relative addresses documented
by this project may be retained. Prefer a short relevant excerpt to a full dump.

## Source changes

Explain what changed and how it was checked. Distinguish build checks from tests
on a physical headset. Changes to patch sites or restoration should include a
normal-completion test and an interruption test, with original bytes verified
afterward. Keep checks for unexpected firmware and instructions in place.

Build generated executables with `bash tools/build.sh`; keep them out of source
commits. `tools/package_release.py --binary` includes them in a release archive.

Do not add Meta firmware executables, libraries, APKs, raw memory dumps, or private
research logs to this repository. Record references or hashes when necessary.

The project license is currently undecided.

