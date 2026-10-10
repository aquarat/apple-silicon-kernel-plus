#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Create the COPR project and its package definitions (once, by the owner).
#
#   scripts/copr-setup.sh [OWNER/PROJECT]     default: aquarat/apple-silicon-kernel-plus
#   DRY_RUN=1 scripts/copr-setup.sh           print the commands only
#
# Needs copr-cli with a valid ~/.config/copr (https://copr.fedorainfracloud.org/api/).
# Re-running is safe: existing packages are edited, not duplicated.
#
# Every package is an SCM package built with the make_srpm method: COPR clones
# this repository and runs `.copr/Makefile srpm`, which calls
# scripts/make-srpm.sh. That step has network access (downloads, cargo
# vendor); the RPM builds themselves do not need it.
set -euo pipefail
PROJECT=${1:-aquarat/apple-silicon-kernel-plus}
CLONE_URL=${CLONE_URL:-https://github.com/aquarat/apple-silicon-kernel-plus.git}
BRANCH=${BRANCH:-main}
CHROOTS=(fedora-44-aarch64)
run() { echo "+ $*"; [ "${DRY_RUN:-0}" = 1 ] || "$@"; }

# package -> the "spec" path the Makefile derives the package from
declare -A SPEC=(
    [kernel]=packages/kernel/kernel-plus.conf
    [apple-avd]=packages/apple-avd/apple-avd.spec
    [apple-ave]=packages/apple-ave/apple-ave.spec
    [mesa-honeykrisp-plus]=packages/mesa-honeykrisp-plus/mesa-honeykrisp-plus.spec
)
# qemu-vmapple is not built on COPR yet: QEMU (GPL-2.0-only) links Reims and
# metal2vulkan, whose LICENSE files say LGPL-3.0. Build it locally until Reims
# runs as a separate process (see LICENSING.md).

# Build timeouts in seconds (COPR's default is 5 hours).
declare -A TIMEOUT=([kernel]=72000 [qemu-vmapple]=36000 [mesa-honeykrisp-plus]=18000
                    [apple-avd]=3600 [apple-ave]=3600)

name=${PROJECT#*/}
if ! copr-cli get "$PROJECT" >/dev/null 2>&1; then
    chroot_args=()
    for c in "${CHROOTS[@]}"; do chroot_args+=(--chroot "$c"); done
    run copr-cli create "$name" "${chroot_args[@]}" \
        --description "Unofficial packages for Fedora Asahi Remix: the @asahi kernel with KVM patches for macOS guests, AVD/AVE video drivers (DKMS), a patched Honeykrisp Vulkan driver and QEMU with vmapple and Reims. Not affiliated with or endorsed by Asahi Linux, Fedora or Apple." \
        --instructions "See https://github.com/aquarat/apple-silicon-kernel-plus#install. Enabling this repository replaces the stock @asahi kernel with this project's build. Do not report bugs from these packages to Asahi Linux or Fedora." \
        --enable-net off --unlisted-on-hp off --appstream off
fi

for p in "${!SPEC[@]}"; do
    args=(--name "$p" --clone-url "$CLONE_URL" --commit "$BRANCH"
          --spec "${SPEC[$p]}" --method make_srpm --webhook-rebuild off
          --timeout "${TIMEOUT[$p]}")
    if copr-cli get-package "$PROJECT" --name "$p" >/dev/null 2>&1; then
        run copr-cli edit-package-scm "$PROJECT" "${args[@]}"
    else
        run copr-cli add-package-scm "$PROJECT" "${args[@]}"
    fi
done
echo "done: builds are started by .github/workflows (or: copr-cli build-package $PROJECT --name <package>)"
