# Update policy

This is a best-effort project. Nothing here is a promise
of response times.

## kernel

- The kernel follows `@asahi/kernel`: every build is `@asahi`'s newest
  published kernel SRPM for `fedora-44-aarch64`, plus this project's
  patches and build settings.
- A scheduled workflow runs daily. When `@asahi` has published a newer
  kernel than this project's newest build, it checks that the patches apply
  and starts a COPR build. A kernel build in COPR takes several hours.
- Until that build is published, `dnf upgrade` offers `@asahi`'s newer
  kernel, which has no KVM patches. Users who need the patches can give this
  COPR a higher priority (README, Kernel release naming); dnf then waits for
  this project's build.
- If the patches no longer apply, there is no build until they are rebased.
  The workflow fails visibly. Users stay on the last kernel built here, or
  move to `@asahi`'s, depending on repository priority.
- A failed COPR build for the same `@asahi` release is not retried
  automatically.
- Security fixes reach this kernel when `@asahi` ships them; there are no
  separate security updates.
- Kernels are install-only; dnf keeps the previous ones (default:
  `installonly_limit=3`).

## dkms-apple-avd

- DKMS builds it for every installed 7.1 Fedora Asahi kernel with its
  `-devel` package.
- When `@asahi` moves to a new kernel series, DKMS skips the module for that
  series and the in-tree decoder is used, until this project rebases the
  driver (maintainer guide). The in-tree driver has the problems the patches
  fix (for example, H.264 streams stop after 4096 slices).

## apple-ave (experimental)

- Follows its upstream repository by hand. No schedule.
- Only for the macOS 13.5 system firmware. Other system firmware versions are
  refused until upstream ports them.

## mesa-honeykrisp-plus

- Tracks the Mesa version that Fedora ships for the target release, by hand,
  after Fedora updates it. Until then the private copy keeps the previous
  version, which keeps working as long as the kernel interface it uses does
  not change.
- Patches that upstream Mesa merges are dropped.

## qemu-vmapple

- Tracks `aquarat/reims-vgpu` `master` (and the QEMU commit it pins), by
  hand, after the new commit has run macOS guests.

## Fedora releases

- Built for Fedora 44 (`fedora-44-aarch64`), the release `@asahi` and Fedora
  Asahi Remix currently target. Other releases are added when they matter;
  Mesa needs a matching version per release.
