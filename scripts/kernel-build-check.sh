#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Compile what this project changes in the kernel, without a full build:
# the directories of every C/Rust file the kernel patches touch, the Apple
# device trees when a patch touches one, and the DKMS modules (apple-avd,
# apple-ave) against the same tree.
#
#   scripts/kernel-build-check.sh out/kernel-<nvr>.src.rpm
#
# The SRPM comes from `scripts/make-srpm.sh kernel out`. Its %prep is run
# (rpmbuild -rp) in a scratch directory outside the repository, the 16k
# config is used as Fedora's %build would use it, then `make prepare`,
# the touched directories and the modules. Needs the kernel's build tools
# (container/install-tools.sh). A full `rpmbuild --rebuild` is still the
# maintainer's step before a release (docs/release-process.md).
#
#   JOBS=N      make -j (default: nproc)
#   WORK=DIR    scratch directory (default: a new one under ${TMPDIR:-/tmp})
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
srpm=$(realpath "${1:?usage: $0 <kernel SRPM>}")
JOBS=${JOBS:-$(nproc)}
WORK=${WORK:-$(mktemp -d "${TMPDIR:-/tmp}/kernel-build-check.XXXXXX")}
log() { echo "== $*" >&2; }

log "prepare the tree (rpmbuild -rp) in $WORK"
# Outside any git checkout: %prep applies patches with `git apply`, which
# would otherwise find the repository around it.
mkdir -p "$WORK/top"
if ! (cd "$WORK" && GIT_CEILING_DIRECTORIES="$WORK" rpmbuild -rp --nodeps --target aarch64 \
        --define "_topdir $WORK/top" "$srpm" > "$WORK/prep.log" 2>&1); then
    tail -40 "$WORK/prep.log" >&2
    echo "kernel-build-check: %prep failed" >&2
    exit 1
fi
tree=$(find "$WORK/top/BUILD" -mindepth 3 -maxdepth 3 -type d -name 'linux-*' | head -1)
[ -n "$tree" ] || { echo "kernel-build-check: no prepared tree" >&2; exit 1; }
config=$(find "$tree/configs" -name 'kernel-*-aarch64-16k.config' ! -name '*debug*' | head -1)
[ -n "$config" ] || { echo "kernel-build-check: no 16k config in $tree/configs" >&2; exit 1; }
log "tree $(basename "$tree"), config $(basename "$config")"

cd "$tree"
cp "$config" .config
make -s olddefconfig
make -s -j"$JOBS" prepare

# Directories of the C and Rust files the patches add or change.
mapfile -t dirs < <(sed -n 's|^+++ b/||p' "$HERE"/packages/kernel/patches/*.patch |
    grep -E '\.(c|rs)$' | xargs -r -n1 dirname | sort -u)
for d in "${dirs[@]}"; do
    log "make $d/"
    make -j"$JOBS" "$d/"
done

# Apple device trees, when a patch touches one.
if sed -n 's|^+++ b/||p' "$HERE"/packages/kernel/patches/*.patch |
        grep -q '^arch/arm64/boot/dts/apple/'; then
    mapfile -t dtbs < <(cd arch/arm64/boot/dts &&
        find apple -maxdepth 1 -name '*.dts' | sed 's/\.dts$/.dtb/' | sort)
    log "make ${#dtbs[@]} Apple device trees"
    make -j"$JOBS" "${dtbs[@]}"
fi

# The DKMS modules, as DKMS builds them, against this tree. There is no
# Module.symvers without a full build, so unresolved symbols only warn.
make -s -j"$JOBS" modules_prepare
export KBUILD_MODPOST_WARN=1
log "apple-avd"
cp -a "$HERE/packages/apple-avd/src" "$WORK/apple-avd"
make -C "$WORK/apple-avd" -j"$JOBS" KDIR="$tree"
log "apple-ave"
cp -a "$HERE/packages/apple-ave/src" "$WORK/apple-ave"
make -C "$WORK/apple-ave/driver" -j"$JOBS" KDIR="$tree"
# The overlays need dtc (dkms-apple-ave requires the dtc package); without
# one installed, use the kernel tree's own.
if ! command -v dtc >/dev/null; then
    make -s -j"$JOBS" scripts_dtc
    export PATH="$tree/scripts/dtc:$PATH"
fi
make -C "$WORK/apple-ave/overlay" -j"$JOBS" KDIR="$tree"

log "all compiled"
