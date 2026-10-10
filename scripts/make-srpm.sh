#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Build one package's SRPM. Runs on Fedora: inside the container of
# scripts/build-srpms.sh, in GitHub Actions, or in COPR's make_srpm step
# (.copr/Makefile). Needs network access for the upstream sources.
#
#   scripts/make-srpm.sh <package> <outdir>
#   scripts/make-srpm.sh --list
#
# Packages: kernel apple-avd apple-ave mesa-honeykrisp-plus qemu-vmapple
#
# Environment:
#   CACHE_DIR      downloads and git checkouts (default: <repo>/.cache)
#   KERNEL_NVR     kernel only: the @asahi kernel to rebuild, e.g.
#                  7.1.13-402.asahi.fc44 (default: the newest published one)
#   KERNEL_SRPM    kernel only: use this local SRPM instead of downloading
#   KERNEL_CHROOT  kernel only: @asahi chroot to read (default fedora-44-aarch64)
#   PREP_CHECK=1   kernel only: also run `rpmbuild -bp` (patches apply?) before
#                  writing the SRPM; needs the kernel's build tools, not its
#                  full BuildRequires
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
PACKAGES=(kernel apple-avd apple-ave mesa-honeykrisp-plus qemu-vmapple)
CACHE_DIR=${CACHE_DIR:-$HERE/.cache}

die() { echo "make-srpm: $*" >&2; exit 1; }
log() { echo "== $*" >&2; }

if [ "${1:-}" = --list ]; then printf '%s\n' "${PACKAGES[@]}"; exit 0; fi
pkg=${1:?usage: $0 <package> <outdir> | --list}
out=${2:?usage: $0 <package> <outdir>}
printf '%s\n' "${PACKAGES[@]}" | grep -qx -- "$pkg" || die "unknown package '$pkg' (${PACKAGES[*]})"
for c in rpmbuild rpmspec tar xz sha256sum python3; do command -v "$c" >/dev/null || die "missing $c"; done
mkdir -p "$out" "$CACHE_DIR"
out=$(cd "$out" && pwd)

# Reproducible tarballs: timestamps from the last commit when there is one.
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    SOURCE_DATE_EPOCH=$(git -C "$HERE" log -1 --format=%ct 2>/dev/null || date +%s)
fi
export SOURCE_DATE_EPOCH
TAR=(tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner
     --exclude-vcs --exclude='*.o' --exclude='*.ko' --exclude='*.cmd' --exclude='*.mod'
     --exclude='*.mod.c' --exclude='*.dtbo' --exclude='*_dtbo.h' --exclude='*.rpm')

top=$(mktemp -d "${TMPDIR:-/var/tmp}/askp-srpm.XXXXXX")
trap 'rm -rf "$top"' EXIT
mkdir -p "$top"/{SPECS,SOURCES,BUILD,RPMS,SRPMS}
RPMB=(rpmbuild --define "_topdir $top" --define "_sourcedir $top/SOURCES"
      --define "_srcrpmdir $top/SRPMS" --define "_specdir $top/SPECS")

spec_value() { rpmspec -q --srpm --qf "$2" "$1" 2>/dev/null; }

# Our own packages: the package directory plus the licence files, as
# <name>-<version>/ in Source0.
own_tarball() {
    local spec=$1 name ver stage
    name=$(spec_value "$spec" '%{name}')
    ver=$(spec_value "$spec" '%{version}')
    stage="$top/stage/$name-$ver"
    mkdir -p "$stage"
    cp -a "$HERE/packages/$pkg/." "$stage/"
    rm -f "$stage/$pkg.spec"
    cp "$HERE/LICENSE" "$HERE/LICENSING.md" "$stage/"
    "${TAR[@]}" -C "$top/stage" -cJf "$top/SOURCES/$name-$ver.tar.xz" "$name-$ver"
}

finish() {
    local spec=$1
    "${RPMB[@]}" -bs "$spec" >/dev/null
    local srpm
    srpm=$(ls "$top"/SRPMS/*.src.rpm)
    cp "$srpm" "$out/"
    log "wrote $out/$(basename "$srpm")"
}

build_kernel() {
    local conf="$HERE/packages/kernel/kernel-plus.conf" src nvr buildid date
    # shellcheck source=packages/kernel/kernel-plus.conf
    . "$conf"
    buildid=${BUILDID:?BUILDID missing in $conf}
    if [ -n "${KERNEL_SRPM:-}" ]; then
        src=$KERNEL_SRPM
    else
        src=$(python3 "$HERE/scripts/asahi-kernel.py" --chroot "${KERNEL_CHROOT:-fedora-44-aarch64}" \
              fetch ${KERNEL_NVR:+"$KERNEL_NVR"} "$CACHE_DIR/asahi-kernel")
    fi
    log "base $(basename "$src") sha256 $(sha256sum "$src" | cut -d' ' -f1)"
    rpm --define "_topdir $top" --define "_sourcedir $top/SOURCES" --define "_specdir $top/SPECS" \
        -i "$src" 2>/dev/null
    local spec="$top/SPECS/kernel.spec"
    [ -f "$spec" ] || die "no kernel.spec in $(basename "$src")"
    # Fedora's kernel.spec applies SOURCES/linux-kernel-test.patch last, and
    # @asahi ships it empty. Refuse to overwrite one that is not empty.
    [ -s "$top/SOURCES/linux-kernel-test.patch" ] &&
        die "the base SRPM already carries a non-empty linux-kernel-test.patch"
    grep -q '^ApplyOptionalPatch linux-kernel-test.patch' "$spec" ||
        die "kernel.spec no longer applies linux-kernel-test.patch; update make-srpm.sh"
    cat "$HERE"/packages/kernel/patches/*.patch > "$top/SOURCES/linux-kernel-test.patch"

    # Our settings go first, so they win over the spec's own defaults.
    {
        echo "# apple-silicon-kernel-plus: this is the @asahi kernel.spec with these"
        echo "# settings and the patches in linux-kernel-test.patch"
        echo "# (https://github.com/aquarat/apple-silicon-kernel-plus, packages/kernel)."
        echo "%define buildid .$buildid"
        for w in $WITHOUT; do echo "%define _without_$w 1"; done
        echo
    } > "$top/hdr"
    cat "$top/hdr" "$spec" > "$spec.new" && mv "$spec.new" "$spec"
    # Fedora forces kernel-headers on; @asahi's own kernel-headers stays the
    # one users get. Harmless if the line changes upstream (headers are built).
    sed -i 's/^%define with_headers 1$/%define with_headers %{?_without_headers: 0} %{?!_without_headers: 1}/' "$spec"

    nvr=$(rpmspec -q --srpm --qf '%{version}-%{release}' "$spec" 2>/dev/null)
    date=$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%a %b %d %Y')
    awk -v hdr="* $date $CHANGELOG_IDENTITY - ${nvr%.fc*}" -v pl="$(find "$HERE/packages/kernel/patches" -name '*.patch' -printf -- '- %f\n' | sort)" '
        { print }
        /^%changelog$/ && !done { print hdr; print "- apple-silicon-kernel-plus rebuild of the @asahi kernel, 16k variant only, with:"; print pl; print ""; done=1 }
    ' "$spec" > "$spec.new" && mv "$spec.new" "$spec"
    log "release $nvr (16k only; without: $WITHOUT)"

    if [ "${PREP_CHECK:-0}" = 1 ]; then
        log "rpmbuild -bp (do the patches apply?)"
        if ! "${RPMB[@]}" -bp --nodeps --target aarch64 "$spec" > "$top/prep.log" 2>&1; then
            tail -25 "$top/prep.log" >&2
            grep -q 'End of patch applications' "$top/prep.log" &&
                die "the patches apply, but %prep failed later (a missing tool?)"
            die "the patches do not apply to $(basename "$src")"
        fi
        log "patches apply"
        rm -rf "$top/BUILD"/*
    fi
    finish "$spec"
}

build_own() {
    local spec="$top/SPECS/$pkg.spec"
    cp "$HERE/packages/$pkg/$pkg.spec" "$spec"
    own_tarball "$spec"
    finish "$spec"
}

# Upstream tarball(s) named in the spec, checked against packages/<pkg>/sha256sums.
fetch_checked() {
    local spec=$1 url f
    while read -r url; do
        f=$(basename "$url")
        if [ ! -f "$CACHE_DIR/dl/$f" ]; then
            mkdir -p "$CACHE_DIR/dl"
            log "download $url"
            curl -fsSL --retry 3 -o "$CACHE_DIR/dl/$f.part" "$url"
            mv "$CACHE_DIR/dl/$f.part" "$CACHE_DIR/dl/$f"
        fi
        (cd "$CACHE_DIR/dl" && grep " $f\$" "$HERE/packages/$pkg/sha256sums" | sha256sum -c --quiet -) ||
            die "$f: sha256 does not match packages/$pkg/sha256sums"
        cp "$CACHE_DIR/dl/$f" "$top/SOURCES/"
    done < <(rpmspec -P "$spec" 2>/dev/null | sed -n 's/^Source[0-9]*:[[:space:]]*\(https\?:\/\/.*\)/\1/p')
}

build_mesa() {
    local spec="$top/SPECS/$pkg.spec"
    cp "$HERE/packages/$pkg/$pkg.spec" "$spec"
    fetch_checked "$spec"
    cp "$HERE"/packages/"$pkg"/patches/*.patch "$top/SOURCES/"
    finish "$spec"
}

# qemu-vmapple: Reims at the commit in the spec, its vendor/qemu submodule at
# the commit Reims pins, QEMU's meson subprojects, and the Rust crates
# (cargo vendor, git dependencies included), so COPR builds offline.
build_qemu() {
    local spec="$top/SPECS/$pkg.spec" reims qemu_pin short name ver git_dir w
    for c in git cargo meson curl; do command -v "$c" >/dev/null || die "missing $c"; done
    cp "$HERE/packages/$pkg/$pkg.spec" "$spec"
    reims=$(sed -n 's/^%global reims_commit[[:space:]]\+//p' "$spec")
    qemu_pin=$(sed -n 's/^%global qemu_commit[[:space:]]\+//p' "$spec")
    [[ $reims =~ ^[0-9a-f]{40}$ ]] || die "reims_commit in $pkg.spec is not a full commit id"
    short=${reims:0:12}
    name=$(spec_value "$spec" '%{name}')
    ver=$(spec_value "$spec" '%{version}')

    git_dir="$CACHE_DIR/git/reims-vgpu"
    if [ ! -d "$git_dir/.git" ]; then
        git clone -q --filter=blob:none --no-checkout https://github.com/aquarat/reims-vgpu.git "$git_dir"
    fi
    git -C "$git_dir" fetch -q origin "$reims" 2>/dev/null || git -C "$git_dir" fetch -q origin
    git -C "$git_dir" -c advice.detachedHead=false checkout -q -f "$reims"
    git -C "$git_dir" clean -q -fdx
    local pinned
    pinned=$(git -C "$git_dir" ls-tree HEAD vendor/qemu | awk '{print $3}')
    [ "$pinned" = "$qemu_pin" ] ||
        die "Reims $short pins vendor/qemu at $pinned, the spec says $qemu_pin (update qemu_commit)"
    git -C "$git_dir" submodule sync -q vendor/qemu
    git -C "$git_dir" submodule update -q --init --depth 1 vendor/qemu 2>/dev/null ||
        git -C "$git_dir" submodule update -q --init vendor/qemu
    [ "$(git -C "$git_dir/vendor/qemu" rev-parse HEAD)" = "$qemu_pin" ] || die "vendor/qemu checkout failed"
    git -C "$git_dir/vendor/qemu" clean -q -fdx

    # Source0: Reims + QEMU (no .git), with the meson subprojects QEMU needs
    # for this configuration (Rust in QEMU itself is off; dtc and slirp come
    # from the system).
    w="$top/stage/reims-vgpu-$short"
    mkdir -p "$w"
    git -C "$git_dir" archive HEAD | tar -x -C "$w"
    rm -rf "$w/vendor/qemu"
    mkdir -p "$w/vendor/qemu"
    git -C "$git_dir/vendor/qemu" archive HEAD | tar -x -C "$w/vendor/qemu"
    (cd "$w/vendor/qemu" && meson subprojects download keycodemapdb berkeley-softfloat-3 berkeley-testfloat-3 >/dev/null) ||
        die "meson subprojects download failed"
    find "$w/vendor/qemu/subprojects" -mindepth 2 -maxdepth 2 -name .git -exec rm -rf {} +
    rm -rf "$w/vendor/qemu/subprojects/packagecache"
    log "Source0 reims-vgpu-$short.tar.xz"
    "${TAR[@]}" -C "$top/stage" -cf - "reims-vgpu-$short" | xz -T0 -6 > "$top/SOURCES/reims-vgpu-$short.tar.xz"

    # Source1: the crates, from Cargo.lock (git dependencies included), and
    # the source-replacement config cargo vendor prints.
    log "cargo vendor"
    mkdir -p "$top/stage/cargo-vendor"
    (cd "$w" && CARGO_HOME="$CACHE_DIR/cargo-home" cargo vendor --locked --versioned-dirs \
        "$top/stage/cargo-vendor/vendor" > "$top/stage/cargo-vendor/config.toml") ||
        die "cargo vendor failed"
    sed -i "s|directory = \".*\"|directory = \"@VENDOR@\"|" "$top/stage/cargo-vendor/config.toml"
    "${TAR[@]}" -C "$top/stage" -cf - cargo-vendor | xz -T0 -6 > "$top/SOURCES/reims-vgpu-$short-vendor.tar.xz"

    mkdir -p "$top/stage/$name-$ver-extra"
    cp -a "$HERE/packages/$pkg/." "$top/stage/$name-$ver-extra/"
    rm -f "$top/stage/$name-$ver-extra/$pkg.spec"
    cp "$HERE/LICENSE" "$HERE/LICENSING.md" "$top/stage/$name-$ver-extra/"
    "${TAR[@]}" -C "$top/stage" -cJf "$top/SOURCES/$name-$ver-extra.tar.xz" "$name-$ver-extra"
    finish "$spec"
}

case $pkg in
kernel) build_kernel ;;
apple-avd|apple-ave) build_own ;;
mesa-honeykrisp-plus) build_mesa ;;
qemu-vmapple) build_qemu ;;
esac
