#!/usr/bin/env python3
"""Create an allowlisted source archive or binary release without private logs."""

import argparse
import hashlib
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = "quest-tracking-injection"
PUBLIC_DIRS = ("src", "scripts", "tools", "docs", "evidence", ".github")
PUBLIC_FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", ".gitignore", ".gitattributes", "bin/README.md")
EXECUTABLES = ("bin/quest-inject", "bin/quest-source-guard")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", action="store_true", help="Include project-built ARM64 executables")
    parser.add_argument("--output", type=pathlib.Path, help="Destination ZIP path")
    args = parser.parse_args()
    files = [ROOT / name for name in PUBLIC_FILES]
    for directory in PUBLIC_DIRS:
        files.extend(
            path for path in (ROOT / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo")
        )
    if (ROOT / "LICENSE").is_file():
        files.append(ROOT / "LICENSE")
    if args.binary:
        for name in EXECUTABLES:
            path = ROOT / name
            if not path.is_file() or path.read_bytes()[:4] != b"\x7fELF":
                parser.error(f"Build the native executables first: {name}")
            files.append(path)
    files = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    for path in files:
        if path.is_symlink() or path.suffix in (".so", ".apk", ".log"):
            parser.error(f"Unexpected file in public package: {path.relative_to(ROOT)}")
    variant = "v0.1.0-arm64" if args.binary else "source"
    destination = args.output or ROOT / "dist" / f"{PROJECT}-{variant}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    hashes = []
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            archive.write(path, f"{PROJECT}/{relative}")
            hashes.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
        archive.writestr(f"{PROJECT}/SHA256SUMS", "\n".join(hashes) + "\n")
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Archive integrity check failed")
    print(f"Created {destination} ({len(files)} files plus SHA256SUMS)")


if __name__ == "__main__":
    main()

