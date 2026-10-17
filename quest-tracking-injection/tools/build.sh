#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
project_ndk="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-${NDK_HOME:-}}}"

if [[ -z "$project_ndk" ]]; then
    echo "Set ANDROID_NDK_HOME to your Android NDK directory." >&2
    exit 2
fi

case "$(uname -s)" in
    Darwin) project_host="darwin-x86_64" ;;
    Linux) project_host="linux-x86_64" ;;
    *) echo "This build script supports macOS and Linux hosts." >&2; exit 2 ;;
esac

project_cc="$project_ndk/toolchains/llvm/prebuilt/$project_host/bin/aarch64-linux-android29-clang"
if [[ ! -x "$project_cc" ]]; then
    echo "Android ARM64/API 29 compiler not found: $project_cc" >&2
    exit 2
fi

mkdir -p "$project_root/bin"
"$project_cc" -O2 -Wall -Wextra \
    "$project_root/src/quest_inject.c" \
    -o "$project_root/bin/quest-inject" -lbinder_ndk -ldl -lm
"$project_cc" -O2 -Wall -Wextra \
    "$project_root/src/pose_guard.c" \
    -o "$project_root/bin/quest-source-guard"

echo "Built ARM64/API 29 executables in $project_root/bin"

