# Reverse-engineering notes

These addresses describe Quest 1 firmware `49845030443200410`. They are ELF-relative
addresses, not process addresses after ASLR. No original C++ class name is claimed
for the concrete host implementation.

## Resolved injection call

```text
libtrackinginjection-service.so:
  updateRemotePoseField                          0x11d90
    -> updateRemoteSensors(uint64_t, ovrSensorData const&)
                                                 0x12498
    -> host = *(service + 0x28)
    -> x0 = host + 0x28
    -> vptr = *(host + 0x28)
    -> target = *vptr

trackingservice:
  vptr                                          0x13bc90
  target                                        0xe8b18
    sub x0, x0, #0x28
    mov w3, wzr
    b 0xe8774

  concrete pose processing                      0xe8774
```

The effective arguments are the host pointer, numeric device identifier, a
reference to `ovrSensorData`, and a fourth argument of zero. The boolean result
is propagated back to the Binder reply.

`ldr x8, [x0, #0x28]!` also updates `x0`. This is a virtual call through a subobject
at offset `0x28`; the table header at `0x13bc80` contains `-0x28`.

Initialization at `0xe57bc` derives the relevant vtable address from
`0x13bab0 + 0x1e0`. On the investigated construction path, the host begins at the
allocation address plus `0x20`. No further direct writes to `x23/w23` were found
between assigning that pointer and passing it to the injection service.
The relevant vtable and indirect target were also checked in the running process.
Disassembler labels inherited from distant preceding symbols are not reliable
class names for these functions.

## Physical producers and the source guard

A hardware write watchpoint identified the shared-buffer writer at `0xe89d8`.
An execution breakpoint at `0xe8774` then identified the physical producer's
return address at `0xaab50`. Its call instruction is at `0xaab4c`.

```text
Physical Constellation callback:
  transformConstellationTrackingData(...)
  -> physical pose dispatch                     0xaab4c
  -> shared virtual entry
  -> pose processing                            0xe8774

Physical fallback callback:
  construct fallback sensor data
  -> fallback pose dispatch                     0xa9830
  -> shared virtual entry
  -> pose processing                            0xe8774
```

Blocking only the Constellation dispatch was insufficient: the fallback producer
could continue writing zero poses. Both call sites must be suppressed for the
demonstrated stable override.

The finished guard checks each original instruction before writing:

| Site | Original instruction word | Temporary instruction word |
|---|---|---|
| `0xaab4c` | `0xd63f0100` (`blr x8`) | `0xd503201f` (`nop`) |
| `0xa9830` | `0xd63f0100` (`blr x8`) | `0xd503201f` (`nop`) |

Only the running process is patched through `/proc/PID/mem`. The original words
are restored and checked on normal timeout or handled termination signals. The
host launcher also verifies restoration. There is no persistent firmware patch.

The patch affects physical pose updates for both controllers. It does not replace
the nearby button or status calls. Analysis hardware breakpoints were removed;
they are not required for normal use of the final tool.

## Device registration

The identifier is parsed using `strtoull(..., base=0)`. The firmware Java API
prefixes the paired identifier with `0x`. The launcher discovers the active
identifier rather than embedding a tester's identifier.

The host looks up the identifier in a hash table at `host + 0x1018`. Missing
registration causes the update to return `false`. The controller slot is stored
at offset `0x18` in the matching node.

Registration is implemented at `0xe7534`, with the insertion call at `0xe78ac`.
The relevant firmware log format is
`Registering primary controller %016lx in slot %d`.

## Controller pose buffers

```text
buffer = *(host + 0x410)
device = buffer + slot * 0x16b8

device + 0x758: first atomic counter
device + 0x75c: second atomic counter
device + 0x760: sample slot 0
device + 0x810: sample slot 1

Payload size: 0xa8 bytes, plus one extra flag
Sample stride: 0xb0 bytes
Active sample: second counter & 1

Within a sample:
  +0x28: quaternion, four floats
  +0x38: position, three floats
  +0x78: time value, double
  +0xa8: extra flag; zero on the injection path
```

A time-gated ring buffer of 32 entries, each `0xa8` bytes, begins at
`device + 0x8c4`. Reader `0xec714` reads the double buffer and extra flag while
checking the counters. One confirmed call to that reader is at `0xeb71c`.

## Binder interface and fields

Service: `TrackingDataInjection`.
Interface: `oculus.internal.virtual_input.ITrackingDataInjectionService`.

Transaction 1 takes `String16 deviceId`, `int field`, and `float[] values`.
Its reply contains a Binder status header followed by a boolean acceptance value.
Transaction 5 takes the tracking mode as an integer.

The following field names were recovered from the firmware's Java DEX and checked
against the native jump table:

| Field | Name | Float count | Offset in `ovrSensorData` |
|---|---|---|---|
| 0 | WORLD_FROM_IMU_TRANSLATION | 3 | `0x38` |
| 1 | WORLD_FROM_IMU_ROTATION | 4 | `0x28` |
| 2 | RECENTERED_FROM_WORLD_TRANSLATION | 3 | `0x98` |
| 3 | IMU_FROM_CENTER_EYE_TRANSLATION | 3 | `0x18` |

Fields 2 and 3 are translation fields, not velocity fields.

Modes are `0 = NORMAL` and `1 = DATAINJECT`. The headset writer checks this mode;
the investigated controller writer does not provide equivalent exclusion of the
physical controller producers. The final controller tool keeps the original
headset mode and uses the two source-specific call-site patches instead.

## Observed firmware device-ID lifetime bug

At `0x12094`, a temporary `String8` is constructed from the incoming `String16`.
At `0x12098`, its data pointer is retained. The destructor is called at `0x120a0`,
before the parser uses that pointer at `0x120ac`. The parser calls `strtoull` at
`0x13af4`, using the pointer after the temporary string has been freed.

During a high-rate test the service logged a corrupted identifier, attempted an
update for identifier zero, and returned `false`. The client logs rejected calls
and retries each field at most three times. Transport errors end the session.
These bounded retries do not fix the firmware lifetime bug.

## Scope

The original Meta tracking stack remains required. This work identifies and uses
an injection path and source-selection workaround; it does not supply camera,
IMU, graphics, or replacement tracking-engine drivers for a custom operating system.

The successful tests and visual confirmation are documented in
[validation.md](validation.md). Public evidence excludes paired controller IDs,
ADB serials, personal filesystem paths, and live process addresses.

