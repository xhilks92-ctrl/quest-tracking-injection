#!/usr/bin/env python3
"""Emit a small synthetic controller motion as X Y Z QX QY QZ QW lines."""

import argparse
import math
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--hz", type=float, default=90.0)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 55:
        parser.error("seconds must be in (0, 55]")
    if not math.isfinite(args.hz) or not 1 <= args.hz <= 500:
        parser.error("hz must be in [1, 500]")
    start = time.monotonic()
    for frame in range(math.ceil(args.seconds * args.hz)):
        elapsed = frame / args.hz
        x = 0.125 + 0.05 * math.sin(2 * math.pi * elapsed / 4)
        print(f"{x:.7f} -0.25 -0.5 0 0 0 1", flush=True)
        time.sleep(max(0, start + (frame + 1) / args.hz - time.monotonic()))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass

