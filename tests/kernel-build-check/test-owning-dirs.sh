#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Tests scripts/kernel-build-check.sh --owning-dirs on a synthetic tree laid
# out like the kernel's for the files this project's patches touch.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/../.." && pwd)
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT

mk() { mkdir -p "$t/$1"; : > "$t/$1/${2:-Makefile}"; }
# atlantic: hw_atl/ and hw_atl2/ have no Makefile; atlantic/Makefile lists
# their objects (patch 0003).
mk drivers/net/ethernet/aquantia/atlantic
mkdir -p "$t/drivers/net/ethernet/aquantia/atlantic/hw_atl" \
         "$t/drivers/net/ethernet/aquantia/atlantic/hw_atl2"
# KVM: hyp/vhe has its own Makefile (patch 0001).
mk arch/arm64/kvm; mk arch/arm64/kvm/hyp/vhe
# A directory with a Kbuild file instead of a Makefile.
mk drivers/foo Kbuild; mkdir -p "$t/drivers/foo/sub"

check() {
    local got
    got=$("$HERE/scripts/kernel-build-check.sh" --owning-dirs "$t" "$1")
    if [ "$got" != "$2" ]; then
        echo "FAIL: $1 -> $got (expected $2)" >&2; exit 1
    fi
    echo "ok: $1 -> $got"
}
check drivers/net/ethernet/aquantia/atlantic/hw_atl/hw_atl_b0.c drivers/net/ethernet/aquantia/atlantic
check drivers/net/ethernet/aquantia/atlantic/hw_atl2/hw_atl2.c drivers/net/ethernet/aquantia/atlantic
check drivers/net/ethernet/aquantia/atlantic/aq_main.c drivers/net/ethernet/aquantia/atlantic
check arch/arm64/kvm/hyp/vhe/sysreg-sr.c arch/arm64/kvm/hyp/vhe
check arch/arm64/kvm/sys_regs.c arch/arm64/kvm
check drivers/foo/sub/bar.c drivers/foo
if "$HERE/scripts/kernel-build-check.sh" --owning-dirs "$t" nowhere/x.c 2>/dev/null; then
    echo "FAIL: a file with no Makefile above it was accepted" >&2; exit 1
fi
echo "ok: no Makefile above -> error"
