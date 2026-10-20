#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-only
# Build one package's SRPM. Runs on Fedora: inside the container of
# scripts/build-srpms.sh, in GitHub Actions, or in COPR's make_srpm step
# (.copr/Makefile). Needs network access for the upstream sources.
#
#   scripts/make-srpm.sh <package> <outdir>
#   scripts/make-srpm.sh --list
#
# Packages: kernel apple-avd apple-ave apple-silicon-thunderbolt mesa-honeykrisp-plus qemu-vmapple
#
# Environment:
#   CACHE_DIR      downloads and git checkouts (default: <repo>/.cache)
#   FEDORA_SRPM    kernel only: use this local copy of the Fedora kernel SRPM
#                  named in packages/kernel/kernel-plus.conf (sha256 checked)
#   ASAHI_GIT      kernel only: fetch the Asahi commit from this git
#                  repository (a local clone, say) instead of ASAHI_REPO
#   PREP_CHECK=1   kernel only: also run `rpmbuild -bp` (patches apply,
#                  configs pass Fedora's checks?) before writing the SRPM;
#                  needs the kernel's build tools, not its full BuildRequires
set -euo pipefail

HERE=$(cd "$(dirname "$0")/.." && pwd)
PACKAGES=(kernel apple-avd apple-ave apple-silicon-thunderbolt mesa-honeykrisp-plus qemu-vmapple)
CACHE_DIR=${CACHE_DIR:-$HERE/.cache}

die() { echo "make-srpm: $*" >&2; exit 1; }
log() { echo "== $*" >&2; }

if [ "${1:-}" = --list ]; then printf '%s\n' "${PACKAGES[@]}"; exit 0; fi
pkg=${1:?usage: $0 <package> <outdir> | --list}
out=${2:?usage: $0 <package> <outdir>}
printf '%s\n' "${PACKAGES[@]}" | grep -qx -- "$pkg" || die "unknown package '$pkg' (${PACKAGES[*]})"
for c in rpmbuild rpmspec tar xz sha256sum python3 curl; do command -v "$c" >/dev/null || die "missing $c"; done
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

# A download into $CACHE_DIR/dl, checked against a sha256; prints the path.
fetch_url() {
    local url=$1 sum=$2 f
    f="$CACHE_DIR/dl/$(basename "$url")"
    if [ ! -f "$f" ] || ! echo "$sum  $f" | sha256sum -c --quiet - 2>/dev/null; then
        mkdir -p "$CACHE_DIR/dl"
        log "download $url"
        curl -fsSL --retry 3 -o "$f.part" "$url"
        mv "$f.part" "$f"
    fi
    echo "$sum  $f" | sha256sum -c --quiet - || die "$(basename "$f"): sha256 is not $sum"
    echo "$f"
}

# The kernel: Fedora's kernel SRPM of KERNEL_VERSION (spec, scripts,
# configs, Fedora's patch) turned into a kernel from the Asahi tree at
# ASAHI_COMMIT. packages/kernel/README.md describes each step.
build_kernel() {
    local conf="$HERE/packages/kernel/kernel-plus.conf" spec tarball srpm g base asahi fed
    local tree patch pv buildid nvr date mk
    local -a G
    # shellcheck source=packages/kernel/kernel-plus.conf
    . "$conf"
    for c in git rpm cpio; do command -v "$c" >/dev/null || die "missing $c"; done
    buildid=${BUILDID:?BUILDID missing in $conf}
    [[ $ASAHI_COMMIT =~ ^[0-9a-f]{40}$ ]] || die "ASAHI_COMMIT in $conf is not a full commit id"
    [[ $PKGRELEASE =~ ^[0-9]+\.asahiwip$ ]] || die "PKGRELEASE in $conf must look like 900.asahiwip"
    pv=$(echo "$KERNEL_VERSION" | cut -d. -f1,2)

    # 1. Fedora's SRPM: kernel.spec and everything it needs.
    if [ -n "${FEDORA_SRPM:-}" ]; then
        srpm=$FEDORA_SRPM
        echo "$FEDORA_SRPM_SHA256  $srpm" | sha256sum -c --quiet - ||
            die "$srpm: sha256 is not FEDORA_SRPM_SHA256"
    else
        srpm=$(fetch_url "$FEDORA_SRPM_URL" "$FEDORA_SRPM_SHA256")
    fi
    log "base $(basename "$srpm") sha256 $FEDORA_SRPM_SHA256"
    rpm --define "_topdir $top" --define "_sourcedir $top/SOURCES" --define "_specdir $top/SPECS" \
        -i "$srpm" 2>/dev/null
    spec="$top/SPECS/kernel.spec"
    [ -f "$spec" ] || die "no kernel.spec in $(basename "$srpm")"
    [ "$(sed -n 's/^%define specrpmversion //p' "$spec")" = "$KERNEL_VERSION" ] ||
        die "$(basename "$srpm") is not kernel $KERNEL_VERSION"
    [ -f "$top/SOURCES/patch-$pv-redhat.patch" ] || die "no patch-$pv-redhat.patch in $(basename "$srpm")"
    # Fedora's kernel.spec applies SOURCES/linux-kernel-test.patch last, and
    # ships it empty. Refuse to overwrite one that is not empty.
    [ -s "$top/SOURCES/linux-kernel-test.patch" ] &&
        die "the Fedora SRPM already carries a non-empty linux-kernel-test.patch"
    grep -q '^ApplyOptionalPatch linux-kernel-test.patch' "$spec" ||
        die "kernel.spec no longer applies linux-kernel-test.patch; update make-srpm.sh"

    # 2. Source0: kernel.org's tarball instead of Fedora's repack (same files).
    tarball=$(fetch_url "$LINUX_TARBALL_URL" "$LINUX_TARBALL_SHA256")
    [ "$(basename "$tarball")" = "linux-$KERNEL_VERSION.tar.xz" ] || die "LINUX_TARBALL_URL is not linux-$KERNEL_VERSION.tar.xz"
    cp "$tarball" "$top/SOURCES/"

    # 3. patch-<major>-redhat.patch: the Asahi tree at ASAHI_COMMIT plus
    # Fedora's patch, as one diff against the tarball (the layout @asahi's
    # SRPMs use). Built in a git repository without a work tree.
    g="$CACHE_DIR/git/linux"
    [ -d "$g" ] || git init -q --bare "$g"
    G=(git --git-dir="$g" -c core.quotePath=false -c diff.noprefix=false -c diff.mnemonicPrefix=false
       -c diff.renames=false -c diff.algorithm=myers -c core.abbrev=12)
    base=$("${G[@]}" rev-parse -q --verify "refs/tags/tarball-$KERNEL_VERSION^{tree}" 2>/dev/null || :)
    if [ -z "$base" ]; then
        log "import linux-$KERNEL_VERSION.tar.xz"
        tree="$top/tarball"
        mkdir -p "$tree"
        tar -xf "$tarball" -C "$tree" --strip-components=1
        (cd "$tree" && GIT_INDEX_FILE="$top/tarball.index" "${G[@]}" --work-tree=. add -A -f .)
        base=$(GIT_INDEX_FILE="$top/tarball.index" "${G[@]}" write-tree)
        "${G[@]}" tag -f "tarball-$KERNEL_VERSION" "$base" >/dev/null
        rm -rf "$tree" "$top/tarball.index"
    fi
    if ! "${G[@]}" cat-file -e "$ASAHI_COMMIT^{commit}" 2>/dev/null; then
        log "fetch $ASAHI_COMMIT from ${ASAHI_GIT:-$ASAHI_REPO}"
        "${G[@]}" fetch -q --depth 1 "${ASAHI_GIT:-$ASAHI_REPO}" "$ASAHI_COMMIT" ||
            { [ -z "${ASAHI_GIT:-}" ] && [ -n "${ASAHI_MIRROR:-}" ] &&
              log "not in $ASAHI_REPO; fetch from the mirror $ASAHI_MIRROR" &&
              "${G[@]}" fetch -q --depth 1 "$ASAHI_MIRROR" "$ASAHI_COMMIT"; } ||
            die "cannot fetch $ASAHI_COMMIT (packages/kernel/README.md: if the commit is gone)"
        "${G[@]}" cat-file -e "$ASAHI_COMMIT^{commit}" || die "fetch did not give $ASAHI_COMMIT"
    fi
    mk=$("${G[@]}" show "$ASAHI_COMMIT:Makefile" | awk -F' = ' '
        $1=="VERSION"{v=$2} $1=="PATCHLEVEL"{p=$2} $1=="SUBLEVEL"{s=$2} $1=="EXTRAVERSION"{e=$2}
        END{print v"."p"."s e}')
    [ "$mk" = "$KERNEL_VERSION" ] || die "the Asahi commit is Linux $mk, kernel-plus.conf says $KERNEL_VERSION"
    asahi=$("${G[@]}" rev-parse "$ASAHI_COMMIT^{tree}")
    GIT_INDEX_FILE="$top/fedora.index" "${G[@]}" read-tree "$asahi"
    GIT_INDEX_FILE="$top/fedora.index" "${G[@]}" apply --cached "$top/SOURCES/patch-$pv-redhat.patch" ||
        die "Fedora's patch-$pv-redhat.patch does not apply to the Asahi tree"
    fed=$(GIT_INDEX_FILE="$top/fedora.index" "${G[@]}" write-tree)
    rm -f "$top/fedora.index"
    patch="$top/SOURCES/patch-$pv-redhat.patch"
    "${G[@]}" diff --no-renames --full-index "$base" "$fed" > "$patch.new"
    grep -q '^GIT binary patch' "$patch.new" && die "the Asahi tree changes binary files; patch(1) cannot apply that"
    mv "$patch.new" "$patch"
    log "patch-$pv-redhat.patch: Asahi $ASAHI_BRANCH ${ASAHI_COMMIT:0:12} + Fedora $(basename "$srpm" .src.rpm)," \
        "$("${G[@]}" diff --shortstat "$base" "$fed" | sed 's/^ *//'), sha256 $(sha256sum "$patch" | cut -d' ' -f1)"

    # 4. This project's patches, applied after it.
    cat "$HERE"/packages/kernel/patches/*.patch > "$top/SOURCES/linux-kernel-test.patch"

    # 5. Configs: Fedora's, with @asahi's choices and this project's.
    python3 -I "$HERE/scripts/kernel-configs.py" apply "$top/SOURCES" "$HERE/packages/kernel/configs" >&2

    # 6. @asahi's module placement: the Apple display and GPU drivers in
    # kernel-16k-modules-core.
    local dv="$top/SOURCES/def_variants.yaml.fedora" anchor='  - drivers/gpu/drm/drm.*: modules-core'
    grep -qxF -- "$anchor" "$dv" || die "def_variants.yaml.fedora changed; update make-srpm.sh"
    if ! grep -q 'drivers/gpu/drm/asahi/' "$dv"; then
        awk -v a="$anchor" '{ print } $0 == a {
            print "  - drivers/gpu/drm/apple/.*: modules-core"
            print "  - drivers/gpu/drm/asahi/.*: modules-core" }' "$dv" > "$dv.new" && mv "$dv.new" "$dv"
    fi

    # 7. kernel.spec: release, the 16k variant on, the rest off.
    if ! grep -q '^%define pkgrelease [0-9]*$' "$spec" ||
       ! grep -q '^%define specrelease [0-9]*%{?buildid}%{?dist}$' "$spec"; then
        die "kernel.spec has no plain pkgrelease/specrelease; update make-srpm.sh"
    fi
    sed -i -e "s/^%define pkgrelease [0-9]*\$/%define pkgrelease $PKGRELEASE/" \
           -e "s/^%define specrelease [0-9]*%{?buildid}%{?dist}\$/%define specrelease $PKGRELEASE%{?buildid}%{?dist}/" "$spec"
    {
        echo "# apple-silicon-kernel-plus: Fedora's kernel.spec ($(basename "$srpm" .src.rpm))"
        echo "# for the Asahi Linux kernel tree ($ASAHI_BRANCH $ASAHI_COMMIT),"
        echo "# with @asahi's 16k variant, settings and this project's patches"
        echo "# (https://github.com/aquarat/apple-silicon-kernel-plus, packages/kernel)."
        echo "%define buildid .$buildid"
        echo "%define _with_arm64_16k 1"
        for w in $WITHOUT; do echo "%define _without_$w 1"; done
        echo
    } > "$top/hdr"
    cat "$top/hdr" "$spec" > "$spec.new" && mv "$spec.new" "$spec"

    nvr=$(rpmspec -q --srpm --qf '%{version}-%{release}' "$spec" 2>/dev/null)
    [[ $nvr == "$KERNEL_VERSION-$PKGRELEASE.$buildid"* ]] || die "unexpected version-release $nvr"
    date=$(LC_ALL=C date -u -d "@$SOURCE_DATE_EPOCH" '+%a %b %d %Y')
    awk -v hdr="* $date $CHANGELOG_IDENTITY - ${nvr%.fc*}" \
        -v src="- Asahi Linux kernel tree, $ASAHI_BRANCH at ${ASAHI_COMMIT:0:12} (Linux $KERNEL_VERSION), with Fedora's $(basename "$srpm" .src.rpm) patch and configs" \
        -v pl="$(find "$HERE/packages/kernel/patches" -name '*.patch' -printf '%f\n' | sort | sed 's/^/- /')" '
        { print }
        /^%changelog$/ && !done { print hdr; print src; print "- apple-silicon-kernel-plus: 16k variant only, @asahi config choices, with:"; print pl; print ""; done=1 }
    ' "$spec" > "$spec.new" && mv "$spec.new" "$spec"
    log "release $nvr (16k only; without: $WITHOUT)"

    if [ "${PREP_CHECK:-0}" = 1 ]; then
        log "rpmbuild -bp (do the patches apply, do the configs pass?)"
        if ! "${RPMB[@]}" -bp --nodeps --target aarch64 "$spec" > "$top/prep.log" 2>&1; then
            tail -40 "$top/prep.log" >&2
            grep -q 'End of patch applications' "$top/prep.log" &&
                die "the patches apply, but %prep failed later (configs? a missing tool?)"
            die "the patches do not apply"
        fi
        log "patches apply, configs pass"
        rm -rf "${top:?}/BUILD"/*
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
    find "$HERE/packages/$pkg" -maxdepth 1 -type f ! -name '*.spec' ! -name sha256sums \
        ! -name README.md -exec cp {} "$top/SOURCES/" \;
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
    (cd "$w/vendor/qemu" && meson subprojects download keycodemapdb berkeley-softfloat-3 berkeley-testfloat-3 >/dev/null 2>&1) ||
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
        "$top/stage/cargo-vendor/vendor" > "$top/stage/cargo-vendor/config.toml" 2>"$top/vendor.log") ||
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
apple-avd|apple-ave|apple-silicon-thunderbolt) build_own ;;
mesa-honeykrisp-plus) build_mesa ;;
qemu-vmapple) build_qemu ;;
esac
