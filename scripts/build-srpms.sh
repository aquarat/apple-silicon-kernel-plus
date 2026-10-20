#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Build SRPMs locally in a Fedora 44 container (docker or podman).
#
#   scripts/build-srpms.sh [package...]       default: all packages
#   OUT=dir scripts/build-srpms.sh            default OUT: <repo>/out
#
# Packages: kernel apple-avd apple-ave apple-silicon-thunderbolt mesa-honeykrisp-plus qemu-vmapple
# Downloads and git checkouts are cached in <repo>/.cache (git-ignored).
#
# Environment:
#   CONTAINER=podman        container tool (default: docker, else podman)
#   CPUS=2                  CPU limit for the container (default 2)
#   LINT=1                  also run rpmlint on each SRPM
#   FEDORA_SRPM, ASAHI_GIT, PREP_CHECK: passed to scripts/make-srpm.sh
#   (paths must be inside the repository, which is mounted at /src)
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:-$HERE/out}
IMAGE=askp-tools:44
CPUS=${CPUS:-2}
tool=${CONTAINER:-$(command -v docker >/dev/null && echo docker || echo podman)}
command -v "$tool" >/dev/null || { echo "need docker or podman" >&2; exit 1; }

mapfile -t all < <("$HERE/scripts/make-srpm.sh" --list)
pkgs=("$@")
[ ${#pkgs[@]} -gt 0 ] || pkgs=("${all[@]}")

"$tool" build -q -t "$IMAGE" -f "$HERE/container/Containerfile" "$HERE/container" >/dev/null
mkdir -p "$OUT" "$HERE/.cache"
case $OUT in "$HERE"/*) rel=${OUT#"$HERE"/} ;; *) echo "OUT must be inside the repository" >&2; exit 1 ;; esac

fail=()
for p in "${pkgs[@]}"; do
    echo "=== $p"
    if "$tool" run --rm --cpus="$CPUS" -u "$(id -u):$(id -g)" -e HOME=/tmp \
        -e CARGO_BUILD_JOBS="$CPUS" \
        ${PREP_CHECK:+-e PREP_CHECK="$PREP_CHECK"} \
        ${FEDORA_SRPM:+-e FEDORA_SRPM="$FEDORA_SRPM"} ${ASAHI_GIT:+-e ASAHI_GIT="$ASAHI_GIT"} \
        -v "$HERE:/src" -w /src "$IMAGE" scripts/make-srpm.sh "$p" "$rel"; then
        # The kernel spec is Fedora's; it is not linted here.
        if [ "${LINT:-0}" = 1 ] && [ "$p" != kernel ]; then
            "$tool" run --rm -u "$(id -u):$(id -g)" -v "$HERE:/src" -w /src "$IMAGE" \
                sh -c "rpmlint -c packages/rpmlint.toml $rel/$p-[0-9]*.src.rpm || :"
        fi
    else
        fail+=("$p")
    fi
done
echo "=== SRPMs in $OUT:"
find "$OUT" -maxdepth 1 -name '*.src.rpm' -printf '   %f\n' | sort
[ ${#fail[@]} -eq 0 ] || { echo "failed: ${fail[*]}" >&2; exit 1; }
