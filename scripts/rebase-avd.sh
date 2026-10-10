#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Rebase the apple-avd driver onto another Fedora Asahi kernel.
#
#   scripts/rebase-avd.sh [<kernel NVR> | <kernel-*.src.rpm>] [WORKDIR]
#     e.g. scripts/rebase-avd.sh 7.1.14-400.asahi.fc44
#     default NVR: the newest kernel published by @asahi (scripts/asahi-kernel.py)
#     default WORKDIR: <repo>/.cache/rebase-avd
#
# 1. gets the kernel SRPM, extracts linux-<ver>.tar.xz and applies Fedora's
#    patch-<major>-redhat.patch (the Asahi tree is in it);
# 2. writes WORKDIR/apple-avd-<nvr>/ = drivers/media/platform/apple/avd/ plus
#    our out-of-tree Makefile/Kbuild/.gitignore from packages/apple-avd/src,
#    commits that as "pristine", then `git am`s packages/apple-avd/patches/*.
#
# It does not change packages/apple-avd. On success, compare the result with
# packages/apple-avd/src (the script prints the diff summary); if it differs,
# copy it over src/, regenerate patches/ with
#   git -C WORKDIR/apple-avd-<nvr> format-patch --zero-commit --no-signature -o <repo>/packages/apple-avd/patches pristine..HEAD
# and bump Version and base_kernel in apple-avd.spec (docs/maintainer-guide.md).
# If a patch does not apply, git am's state is left in place for a human.
# Needs: rpm2cpio, cpio, patch, git, tar, xz, python3.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
arg=${1:-}
WORK=${2:-$HERE/.cache/rebase-avd}
die() { echo "rebase-avd: $*" >&2; exit 1; }
for c in rpm2cpio cpio patch git tar xz python3; do command -v "$c" >/dev/null || die "missing $c"; done
mkdir -p "$WORK"
WORK=$(cd "$WORK" && pwd)

if [ -f "$arg" ]; then
    srpm=$(cd "$(dirname "$arg")" && pwd)/$(basename "$arg")
else
    srpm=$(python3 "$HERE/scripts/asahi-kernel.py" fetch ${arg:+"$arg"} "$HERE/.cache/asahi-kernel")
fi
nvr=$(basename "$srpm" .src.rpm); nvr=${nvr#kernel-}
ver=${nvr%%-*}                       # 7.1.13
maj=$(echo "$ver" | cut -d. -f1,2)   # 7.1
echo "== kernel $nvr"

cd "$WORK"
rm -rf "srpm-$nvr" "linux-$ver" && mkdir "srpm-$nvr"
(cd "srpm-$nvr" && rpm2cpio "$srpm" | cpio -idm --quiet "*linux-$ver.tar.xz" "*patch-$maj-redhat.patch")
[ -f "srpm-$nvr/linux-$ver.tar.xz" ] || die "no linux-$ver.tar.xz in the SRPM"
# The driver is usually not in the release tarball (the redhat patch adds it).
mkdir -p "linux-$ver"
tar xf "srpm-$nvr/linux-$ver.tar.xz" --wildcards "linux-$ver/drivers/media/platform/apple/avd/*" 2>/dev/null || :
# The redhat patch touches the whole tree; apply only its hunks for the driver.
python3 - "srpm-$nvr/patch-$maj-redhat.patch" > "srpm-$nvr/avd.patch" <<'PY'
import re, sys
keep, out = False, []
for line in open(sys.argv[1], errors="surrogateescape"):
    if line.startswith("diff --git "):
        keep = " a/drivers/media/platform/apple/avd/" in line or " b/drivers/media/platform/apple/avd/" in line
    if keep:
        out.append(line)
sys.stdout.write("".join(out))
PY
if [ -s "srpm-$nvr/avd.patch" ]; then
    (cd "linux-$ver" && patch -p1 -s < "../srpm-$nvr/avd.patch")
fi
src="linux-$ver/drivers/media/platform/apple/avd"
[ -d "$src" ] || die "no AVD driver in $nvr"

D=apple-avd-$nvr
rm -rf "$D" && mkdir "$D"
cp -a "$src/." "$D/"
rm -f "$D/Kconfig" "$D/Makefile"
cp "$HERE/packages/apple-avd/src/Makefile" "$HERE/packages/apple-avd/src/Kbuild" \
   "$HERE/packages/apple-avd/src/.gitignore" "$D/"
cd "$D"
G=(git -c user.name=apple-silicon-kernel-plus -c user.email=noreply@localhost -c commit.gpgsign=false)
"${G[@]}" init -q -b main
"${G[@]}" add -A
"${G[@]}" commit -q -m "pristine kernel-$nvr avd driver + out-of-tree Kbuild"
"${G[@]}" tag pristine
if ! "${G[@]}" am -q --committer-date-is-author-date "$HERE"/packages/apple-avd/patches/*.patch; then
    die "a patch does not apply to $nvr; resolve it in $WORK/$D (git am --show-current-patch)"
fi
git log --oneline pristine..HEAD
echo "== result: $WORK/$D"
if diff -rq -x .git . "$HERE/packages/apple-avd/src" >/dev/null; then
    echo "== identical to packages/apple-avd/src: nothing to do"
else
    echo "== differs from packages/apple-avd/src:"
    diff -rq -x .git . "$HERE/packages/apple-avd/src" || :
fi
