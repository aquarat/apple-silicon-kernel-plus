# Maintainer guide

How the packages are built, and the routine changes: a new `@asahi` kernel,
an AVD rebase, a Mesa patch or version, a Reims/QEMU bump. Releases:
[release-process.md](release-process.md).

## Layout

```
packages/<package>/      spec (or, for the kernel, kernel-plus.conf), patches, sources
scripts/make-srpm.sh     builds one SRPM (Fedora; network for downloads)
scripts/build-srpms.sh   runs make-srpm.sh in a Fedora 44 container (docker/podman)
scripts/asahi-kernel.py  finds and fetches @asahi's published kernel SRPM
scripts/kernel-watch.py  does the COPR project need a kernel build?
scripts/rebase-avd.sh    rebuilds packages/apple-avd/src for a kernel
scripts/copr-setup.sh    creates the COPR project and package definitions
.copr/Makefile           COPR's make_srpm entry point
container/               the tools image (install-tools.sh is shared with CI)
.github/workflows/       ci, asahi-kernel-watch, copr-build
```

Downloads, git checkouts and the cargo cache go to `.cache/` (git-ignored).
Generated tarballs, vendored crates and SRPMs are never committed.

## Building SRPMs

```sh
scripts/build-srpms.sh                         # all, into out/
scripts/build-srpms.sh kernel apple-avd        # some
PREP_CHECK=1 scripts/build-srpms.sh kernel     # also check that the patches apply (rpmbuild -bp)
KERNEL_NVR=7.1.13-402.asahi.fc44 scripts/build-srpms.sh kernel
LINT=1 scripts/build-srpms.sh apple-ave        # rpmlint the SRPM
```

The container is limited to 2 CPUs by default (`CPUS=`). A full binary
build is `rpmbuild --rebuild out/<srpm>` on a Fedora aarch64 machine with
the BuildRequires installed (`dnf builddep out/<srpm>`). Do not build the
kernel locally unless you mean to; COPR does it.

## A new @asahi kernel

Usually nothing to do: the daily `asahi-kernel-watch` workflow notices it,
checks that the patches apply, and starts the COPR build. The kernel SRPM is
always built from the newest kernel `@asahi` has published for
`fedora-44-aarch64`.

When the patches no longer apply (the workflow fails at "Do the patches
apply?"):

```sh
python3 scripts/asahi-kernel.py fetch .cache/asahi-kernel     # the new SRPM
# Extract linux-<ver>.tar.xz and patch-<major>-redhat.patch from it, apply
# the redhat patch, `git init` + commit the result (arch/arm64 is enough),
# then:
git am --3way packages/kernel/patches/*.patch                 # fix conflicts, git am --continue
git format-patch --zero-commit --no-signature -o packages/kernel/patches <base>..HEAD
PREP_CHECK=1 scripts/build-srpms.sh kernel
```

Keep the headers: `From: Anees Iqbal`, `Origin:` and the rebase note on
0001 (no sign-off unless he gives one), `Signed-off-by:` on 0002. Check that `emulate_nisv_ldst` still defaults to
off.

`BUILDID` in `packages/kernel/kernel-plus.conf`: keep `plus1` for a new
`@asahi` release. Raise it (`plus2`, ...) only when the patches change for an
`@asahi` release that this project has already built, so the rebuild sorts
as newer.

If a new `@asahi` kernel changes `kernel.spec` so that `make-srpm.sh`
refuses (a non-empty `linux-kernel-test.patch`, or no `ApplyOptionalPatch
linux-kernel-test.patch`), adapt `build_kernel` in `scripts/make-srpm.sh`.

## Rebasing apple-avd

Needed when `@asahi` moves to a new kernel series (DKMS then skips the
module, because of `BUILD_EXCLUSIVE_KERNEL`), or when Fedora changes the
in-tree driver within a series.

```sh
scripts/rebase-avd.sh                      # newest @asahi kernel; or: scripts/rebase-avd.sh <nvr>
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
removed from `overlay/Makefile`. To update: copy the new commit's trees the
same way, update `ave_commit`, `Version`, the changelog, and
`firmware/known-hashes.txt` if the driver's firmware hashes changed. If the
SoC rows changed, update `files/ave-load` and the README tables.

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
