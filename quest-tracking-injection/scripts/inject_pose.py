#!/usr/bin/env python3
"""Stable, reversible Quest 1 controller pose injection; firmware 49845030443200410 only."""
import argparse
import math
import pathlib
import re
import shlex
import shutil
import struct
import subprocess
import sys
FIRMWARE = '49845030443200410'
REMOTE = '/data/local/tmp/codex-quest-inject'
GUARD = '/data/local/tmp/codex-source-guard'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb', default=shutil.which('adb') or str(pathlib.Path.home() / 'platform-tools/adb'))
    p.add_argument('--serial')
    p.add_argument('--hand', choices=['right', 'left'], default='right')
    p.add_argument('--position', type=float, nargs=3, default=[0.125, -0.25, -0.5], metavar=('X', 'Y', 'Z'))
    p.add_argument('--orientation', type=float, nargs=4, default=[0, 0, 0, 1], metavar=('QX', 'QY', 'QZ', 'QW'))
    p.add_argument('--seconds', type=float, default=3)
    p.add_argument('--hz', type=float, default=90)
    p.add_argument('--stream', action='store_true', help='Read latest X Y Z QX QY QZ QW lines from stdin')
    p.add_argument('--restore', action='store_true', help='Restore the two known pose calls and NORMAL mode, without starting injection')
    a = p.parse_args()
    if not all((math.isfinite(x) for x in [*a.position, *a.orientation, a.seconds, a.hz])):
        p.error('All values must be finite')
    if not 0 < a.seconds <= 55 or not 1 <= a.hz <= 500:
        p.error('seconds must be in (0,55], hz in [1,500]')
    if sum((x * x for x in a.orientation)) < 1e-12:
        p.error('Quaternion must have nonzero length')
    adb = [a.adb] + (['-s', a.serial] if a.serial else [])

    def run(args, timeout=20, raw=False):
        r = subprocess.run(adb + args, input=b'', capture_output=True, timeout=timeout)
        if r.returncode:
            raise RuntimeError((r.stderr + r.stdout).decode(errors='replace'))
        return r.stdout if raw else r.stdout.decode()

    def shell(args):
        return run(['shell', shlex.join(args)])

    def mem(pid, address, size):
        off = address % 4096
        count = (off + size + 4095) // 4096
        command = shlex.join(['dd', f'if=/proc/{pid}/mem', 'bs=4096', f'skip={address // 4096}', f'count={count}']) + ' 2>/dev/null'
        b = run(['exec-out', command], raw=True)
        if len(b) < off + size:
            raise RuntimeError('Cannot read tracking mode; root ADB is required')
        return b[off:off + size]
    if shell(['getprop', 'ro.build.version.incremental']).strip() != FIRMWARE:
        raise RuntimeError('Firmware differs; mode memory layout has not been verified for this build')
    if shell(['id', '-u']).strip() != '0':
        raise RuntimeError('This launcher requires the rooted ADB shell used during validation')
    if shell(['getprop', 'persist.ovr.enabletrackinginjectionsdk']).strip() != 'true':
        raise RuntimeError('persist.ovr.enabletrackinginjectionsdk must already be true')
    binary_dir = pathlib.Path(__file__).resolve().parents[1] / 'bin'
    binary = binary_dir / 'quest-inject'
    guard_binary = binary_dir / 'quest-source-guard'
    if not binary.is_file() or not guard_binary.is_file():
        raise RuntimeError('Native binaries are missing from bin/. Run tools/build.sh or use the binary release')
    if a.restore:
        pid = int(shell(['pidof', 'trackingservice']).strip())
        maps = shell(['cat', f'/proc/{pid}/maps'])
        image = [line for line in maps.splitlines() if '/system/bin/trackingservice' in line and line.split()[2] == '00000000']
        if len(image) != 1:
            raise RuntimeError('Tracking executable mapping is ambiguous')
        bias = int(image[0].split('-')[0], 16)
        recovery = GUARD + '-recover'
        run(['push', str(guard_binary), recovery])
        shell(['chmod', '755', recovery])
        print(shell([recovery, str(pid), hex(bias), '0']), end='', flush=True)
        reply = shell(['service', 'call', 'TrackingDataInjection', '5', 'i32', '0'])
        if not re.search('Parcel\\(00000000\\s+00000001', reply):
            raise RuntimeError('NORMAL mode not accepted: ' + reply)
        for site in [bias + 699212, bias + 694320]:
            if mem(pid, site, 4) != bytes.fromhex('00013fd6'):
                raise RuntimeError('Original instruction not restored')
        shell(['rm', recovery])
        print('Original physical pose calls verified; NORMAL mode restored.', flush=True)
        return
    dump = shell(['dumpsys', 'tracking'])
    blocks = re.split('Controller SharedMemory \\(ossdk\\):', dump)[1:]
    device = None
    for block in blocks:
        idmatch = re.search('#\\d+ Id: ([0-9a-fA-F]+)', block)
        handedness = re.search('Handedness:\\s*(Right|Left)', block)
        if idmatch and handedness and (handedness[1].lower() == a.hand):
            device = '0x' + idmatch[1]
            break
    if not device:
        raise RuntimeError(f'No active {a.hand} controller. Wake the Quest and controller first.')
    pid = int(shell(['pidof', 'trackingservice']).strip())
    maps = shell(['cat', f'/proc/{pid}/maps'])
    image = [line for line in maps.splitlines() if '/system/bin/trackingservice' in line and line.split()[2] == '00000000']
    if len(image) != 1:
        raise RuntimeError('Tracking executable mapping is ambiguous')
    bias = int(image[0].split('-')[0], 16)
    sites = [bias + 699212, bias + 694320]
    for site in sites:
        if mem(pid, site, 4) != bytes.fromhex('00013fd6'):
            raise RuntimeError('Physical call instruction differs or another injection session is active')
    regions = [line for line in maps.splitlines() if '/dev/ashmem/TrackingServiceHeadTracker ' in line]
    if len(regions) != 1:
        raise RuntimeError('Head-tracking memory mapping is ambiguous or missing')
    address = int(regions[0].split('-')[0], 16) + 5552
    original = None
    for _ in range(10):
        counters = struct.unpack('<4I', mem(pid, address, 16))
        if counters[0] == counters[1]:
            original = counters[2 + (counters[1] & 1)]
            break
    if original not in (0, 1):
        raise RuntimeError('Could not determine original tracking mode')
    run(['push', str(binary), REMOTE])
    run(['push', str(guard_binary), GUARD])
    shell(['chmod', '755', REMOTE, GUARD])
    if shell(['pidof', 'trackingservice']).strip() != str(pid):
        raise RuntimeError('Tracking process restarted during preparation; retry')
    args = [REMOTE, device, *map(str, a.position), *map(str, a.orientation), str(a.seconds), str(a.hz), str(original)]
    if a.stream:
        args.append('--stdin')
    print(f'{a.hand}: {device}; {a.seconds:g}s at requested {a.hz:g} Hz; restore mode {original}', flush=True)
    print('Physical pose updates for both controllers are paused during this bounded session.', flush=True)
    guard = None
    guard_pid = None
    injector = None
    injector_pid = None
    try:
        guard_args = [GUARD, str(pid), hex(bias), str(a.seconds + 4)]
        guard = subprocess.Popen(adb + ['shell', shlex.join(guard_args)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ready = guard.stdout.readline()
        match = re.search('SOURCE_GUARD ACTIVE .*guard_pid=(\\d+)', ready)
        if not match:
            raise RuntimeError('Pose guard did not become ready: ' + ready)
        guard_pid = match[1]
        injector = subprocess.Popen(adb + ['shell', '-T', shlex.join(args)], stdin=None if a.stream else subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
        started = injector.stdout.readline()
        print(started, end='', flush=True)
        imatch = re.search('INJECTOR_STARTED pid=(\\d+)', started)
        if not imatch:
            raise RuntimeError('Injector did not become ready')
        injector_pid = imatch[1]
        output, _ = injector.communicate(timeout=a.seconds + 15)
        print(output, end='', flush=True)
        if injector.returncode:
            raise RuntimeError(f'Injector exited with code {injector.returncode}')
        if guard.poll() is not None:
            raise RuntimeError('Pose guard ended before the injector completed')
    finally:
        if injector is not None and injector.poll() is None:
            if injector_pid:
                shell(['kill', '-TERM', injector_pid])
            tail, _ = injector.communicate(timeout=a.seconds + 6)
            print(tail, end='', flush=True)
        if guard is not None:
            if guard.poll() is None and guard_pid:
                shell(['kill', '-TERM', guard_pid])
            gout, gerr = guard.communicate(timeout=a.seconds + 6)
            if guard.returncode or 'SOURCE_GUARD RESTORED result=0' not in gout:
                raise RuntimeError('Pose guard restoration failed: ' + gout + gerr)
        current_pid = shell(['pidof', 'trackingservice']).strip()
        if current_pid != str(pid):
            raise RuntimeError('Tracking process restarted during the session; original process-local patch is gone')
        for site in sites:
            if mem(pid, site, 4) != bytes.fromhex('00013fd6'):
                raise RuntimeError('Original physical pose instruction could not be verified')
        reply = shell(['service', 'call', 'TrackingDataInjection', '5', 'i32', str(original)])
        if not re.search('Parcel\\(00000000\\s+00000001', reply):
            raise RuntimeError('Mode restoration was not accepted: ' + reply)
        if shell(['pidof', 'trackingservice']).strip() == str(pid):
            c = struct.unpack('<4I', mem(pid, address, 16))
            if c[0] != c[1] or c[2 + (c[1] & 1)] != original:
                raise RuntimeError('Mode restoration could not be confirmed in memory')
        print('Original tracking mode restored.', flush=True)
    print('Original physical pose calls restored and verified. Session completed.', flush=True)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except (RuntimeError, subprocess.TimeoutExpired, ValueError, OSError) as exc:
        print('Error:', exc, file=sys.stderr)
        sys.exit(1)
