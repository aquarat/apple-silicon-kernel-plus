# Maintainer guide

How the packages are built, and the routine changes: a new kernel commit,
an AVD rebase, a Mesa patch or version, a Reims/QEMU bump. Releases:
[release-process.md](release-process.md).

## Layout

```
packages/<package>/      spec (or, for the kernel, kernel-plus.conf and configs/), patches, sources
scripts/make-srpm.sh     builds one SRPM (Fedora; network for downloads)
scripts/build-srpms.sh   runs make-srpm.sh in a Fedora 44 container (docker/podman)
scripts/kernel-configs.py applies the kernel config overlays; diffs configs
scripts/asahi-kernel.py  finds and fetches @asahi's published kernel SRPMs
scripts/kernel-watch.py  kernel status: does COPR need a build, what moved upstream?
scripts/rebase-avd.sh    rebuilds packages/apple-avd/src for a kernel
scripts/copr-setup.sh    creates the COPR project and package definitions
.copr/Makefile           COPR's make_srpm entry point
container/               the tools image (install-tools.sh is shared with CI)
.github/workflows/       ci, kernel-watch, copr-build
```

Downloads, git checkouts and the cargo cache go to `.cache/` (git-ignored).
Generated tarballs, vendored crates and SRPMs are never committed.

## Building SRPMs

```sh
scripts/build-srpms.sh                         # all, into out/
scripts/build-srpms.sh kernel apple-avd        # some
PREP_CHECK=1 scripts/build-srpms.sh kernel     # also check patches and configs (rpmbuild -bp)
FEDORA_SRPM=.cache/kernel-7.2.11-200.fc44.src.rpm scripts/build-srpms.sh kernel   # a local copy
LINT=1 scripts/build-srpms.sh apple-ave        # rpmlint the SRPM
```

The container is limited to 2 CPUs by default (`CPUS=`). A full binary
build is `rpmbuild --rebuild out/<srpm>` on a Fedora aarch64 machine with
the BuildRequires installed (`dnf builddep out/<srpm>`). The kernel takes
about 22 minutes on an M1 Max (10 cores, `rpmbuild --rebuild`, 16k only);
COPR does it for releases.

## The kernel

`packages/kernel/README.md` describes how the SRPM is put together. The
pins are in `packages/kernel/kernel-plus.conf`.

### Moving to a newer Asahi commit

Nothing moves by itself; the daily `kernel-watch` workflow only reports
that `asahi-wip` (or kernel.org, or `@asahi`) moved. To move:

1. Pick the commit: `git ls-remote https://github.com/AsahiLinux/linux.git
   refs/heads/asahi-wip`, or a later one that has run on test machines.
   Read its Makefile for the Linux version it is based on.
2. If the Linux version changed: `KERNEL_VERSION`, `LINUX_TARBALL_URL`
   and `LINUX_TARBALL_SHA256` (kernel.org's `sha256sums.asc`), and
   Fedora's kernel SRPM of that version for Fedora 44 from Koji
   (`https://kojipkgs.fedoraproject.org/packages/kernel/<version>/`,
   the `.fc44` build): `FEDORA_SRPM_URL`, `FEDORA_SRPM_SHA256`. If Fedora
   has no SRPM of exactly that version, wait for it, or use the Asahi commit
   based on the version Fedora has.
3. `ASAHI_COMMIT` (the full id); `PKGRELEASE`: `900.asahiwip` for a new
   Linux version, else one more than before; `BUILDID=plus1`.
4. Rebase the patches. Make a tree as `%prep` does and `git am` them:

   ```sh
   scripts/make-srpm.sh kernel out                   # the patches need not apply yet
   mkdir -p .cache/k && cd .cache/k && rpm2cpio ../../out/kernel-*.src.rpm | cpio -idm --quiet
   tar xf linux-<ver>.tar.xz && cd linux-<ver> && git init -q && git add -A -f && git commit -qm base
   git apply ../patch-<major>-redhat.patch && git add -A && git commit -qm asahi+fedora
   git am --3way ../../../packages/kernel/patches/*.patch   # fix conflicts, git am --continue
   git format-patch --zero-commit --no-signature -o ../../../packages/kernel/patches HEAD~3..HEAD
   ```

   (Remove the old patch files first; keep their names.) Keep the headers:
   `From: Anees Iqbal`, `Origin:` and the rebase note on 0001 (no
   sign-off unless he gives one), `Signed-off-by:` on 0002 and 0003. Check
   that `emulate_nisv_ldst` still defaults to on. If upstream fixed the
   atlantic problem (0003), drop the patch.
5. `PREP_CHECK=1 scripts/build-srpms.sh kernel` (or `scripts/make-srpm.sh`
   on a Fedora aarch64 machine with the kernel's build tools). `%prep`
   runs Fedora's config checks. On `Found unset config items`: add each
   listed symbol to `packages/kernel/configs/plus-<group>.config` with a
   value chosen on purpose (usually the one `listnewconfig` shows, `m` for
   drivers of Apple hardware), and say why in the commit message. On
   `Mismatches found`: a value in the overlays no longer survives
   `olddefconfig` (a dependency changed); change it in `plus-*.config`.
   Do not edit `asahi-*.config`.
6. Build the binary RPMs (`dnf builddep` + `rpmbuild --rebuild`) and boot
   them on test machines: Thunderbolt (`packages/kernel/README.md`), the
   10GbE port, a KVM guest (docs/kvm-macos-guests.md), and check the DKMS
   modules build (`dkms status`; rebase apple-avd if the series changed).
7. Release as usual (release-process.md). After the merge, `kernel-watch`
   starts the COPR build.

If `make-srpm.sh` refuses Fedora's SRPM (no `ApplyOptionalPatch
linux-kernel-test.patch`, a non-empty `linux-kernel-test.patch`, no plain
`pkgrelease`/`specrelease`, a changed `def_variants.yaml.fedora` anchor),
adapt `build_kernel` in `scripts/make-srpm.sh`.

If Fedora's `patch-<major>-redhat.patch` no longer applies to the Asahi
tree, the conflicting files are usually the few that both change
(`arch/arm64/Kconfig`, `arch/arm64/kernel/setup.c`,
`drivers/iommu/iommu.c`, `MAINTAINERS` in 7.2.11). Then carry a resolved
copy of Fedora's patch in `packages/kernel/`, make `build_kernel` use it
instead of the SRPM's, and say so in `packages/kernel/README.md`.

Every commit we build from is also kept in this project's fork
(`ASAHI_MIRROR`, https://github.com/aquarat/linux) under the tag
`plus/asahi-wip-<version>-<commit12>`, and `make-srpm.sh` fetches from there
when the Asahi tree no longer has it. When you pin a new commit, push that
tag before merging the bump:

```sh
git fetch --depth 1 https://github.com/AsahiLinux/linux.git <commit>
git tag -a plus/asahi-wip-<version>-<commit12> -m "Pinned base of kernel <version>-<release>" FETCH_HEAD
git push git@github.com:aquarat/linux.git refs/tags/plus/asahi-wip-<version>-<commit12>
```

`ASAHI_GIT` still overrides both (any local clone that has the commit).

### Patches only, same Asahi commit

Change `packages/kernel/patches/`, raise `BUILDID` (`plus2`, ...), check
with `PREP_CHECK=1`, build, test. The new release sorts above the old one
(README.md, Kernel release naming).

### Config changes

Edit `packages/kernel/configs/plus-<group>.config` (`aarch64` for the
kernels this project builds), raise `BUILDID`, and run the prep check:
Fedora's checks reject a value that `olddefconfig` would change.
`asahi-*.config` is regenerated only when the `@asahi` base it records is
replaced (`scripts/kernel-configs.py diff` of `@asahi`'s and Fedora's
configs of the same kernel, per group).

### Back to an @asahi kernel

When `@asahi` publishes a kernel with what this project needs, the
pre-7.2 way of building (`@asahi`'s SRPM plus `linux-kernel-test.patch`)
is in this repository's history (`scripts/make-srpm.sh`, before
`kernel-7.2`); `scripts/asahi-kernel.py` still finds and fetches
`@asahi`'s SRPMs. On the same Linux version as the last `asahiwip` build,
an `@asahi` release (`40x.asahi`) sorts below `900.asahiwip`, so either
wait for a newer Linux version or give the rebuild a release above 900.

## Rebasing apple-avd

Needed when this project's kernel moves to a new kernel series (DKMS then
skips the module, because of `BUILD_EXCLUSIVE_KERNEL`), or when a new Asahi
commit changes the in-tree driver within a series.

```sh
scripts/rebase-avd.sh                      # this project's kernel SRPM (make-srpm.sh kernel)
scripts/rebase-avd.sh out/kernel-*.src.rpm # an SRPM made already; or an @asahi NVR
```

It builds the pristine driver from the kernel SRPM, applies
`packages/apple-avd/patches/` with `git am`, and says whether the result
differs from `packages/apple-avd/src`. If it differs:

1. If a patch failed, fix it in the work tree (`git am --show-current-patch`,
   edit, `git am --continue`).
2. Check upstream first: if Asahi fixed one of the problems in-tree, drop
   that patch.
3. `git -C .cache/rebase-avd/apple-avd-<nvr> format-patch --zero-commit
   --no-signature -o packages/apple-avd/patches pristine..HEAD` (remove the
   old patch files first).
4. Copy the work tree (without `.git`) over `packages/apple-avd/src`.
5. In `apple-avd.spec`: `base_kernel`, `Version` (`<kernel version>.1`, or
   `.2`... for a new patch set on the same base), changelog. For a new
   series also `BUILD_EXCLUSIVE_KERNEL` in `dkms.conf`.
6. Build against the new `kernel-16k-devel` (see `scripts/rebase-avd.sh`
   header) and test decoding on a machine before release.

## apple-ave

`packages/apple-ave/src` is the AVE repository's `driver/` and `test/`
(renamed `overlay/`) at the commit in the spec, without `physdump.c`,
`isp_peek.c`, `psdump/` and the `.disabled` overlay, and with those modules
removed from `overlay/Makefile`; `firmware/ave_fwgen.py` is its
`tools/ave_fwgen.py`. To update: copy the new commit's trees the same way,
update `ave_commit`, `Version`, the changelog, and
`firmware/known-hashes.txt` if the files the driver loads changed. If the
SoC rows changed, update `files/ave-load`, `SOCS` in
`firmware/apple-ave-fetch-firmware` and the README tables.

Before committing, check that no Apple data came along: no generated
table (`ave_dpe_tables.h` and the like), no firmware, no blob. The driver
loads everything Apple-derived at run time (upstream docs/100), and
`python3 -m unittest discover -s packages/apple-ave/tests` must pass.

## Adding a Mesa patch

1. Put it in `packages/mesa-honeykrisp-plus/patches/` as
   `NNNN-<subject>.patch` in `git format-patch` form, with a commit message
   and `Signed-off-by:`.
2. Add `PatchNNNN:` to the spec, bump `Release`, add a changelog entry
   (say if it is still being validated).
3. `scripts/build-srpms.sh mesa-honeykrisp-plus` (the spec's `%autosetup -p1`
   applies it; a failure shows in `rpmbuild -bp`).

## A new Mesa version

When Fedora updates `mesa-vulkan-drivers` for the target release:

1. `Version:` = Fedora's version, `Release: 1`, changelog.
2. `sha256sums`: the new tarball's hash (`https://archive.mesa3d.org/`).
3. Rebuild; patches that no longer apply need a rebase (upstream may have
   merged them: drop those).

## Bumping Reims / QEMU

```sh
git ls-remote https://github.com/aquarat/reims-vgpu.git refs/heads/master    # the commit
# its pinned QEMU: the vendor/qemu gitlink at that commit
```

In `qemu-vmapple.spec` set `reims_commit` (full id), `qemu_commit` (the
`vendor/qemu` gitlink; `make-srpm.sh` refuses a mismatch), `reims_date`
(the commit date, YYYYMMDD), `qemu_version` (QEMU's `VERSION` file), reset
`Release` to 1, add a changelog entry. Then
`scripts/build-srpms.sh qemu-vmapple`. If QEMU now needs other meson
subprojects, add them to the `meson subprojects download` line in
`scripts/make-srpm.sh`; the offline build fails with `--disable-download`
otherwise.

## COPR

`scripts/copr-setup.sh` (once) creates the project with the
`fedora-44-aarch64` chroot and five SCM packages using the `make_srpm`
method. The SRPM step has network access in COPR; the RPM builds do not
need it, so "enable internet" stays off.

A new Fedora release: add its chroot (`copr-cli edit-chroot` /
`copr-cli modify --chroot`), and pass `KERNEL_CHROOT=fedora-NN-aarch64` for
its kernel; Mesa needs that release's Mesa version, which may mean a
separate branch or spec conditionals.
