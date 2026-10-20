# Update policy

This is a best-effort project. Nothing here is a promise
of response times.

## kernel

- The kernel is the Asahi Linux kernel tree at one commit of its
  `asahi-wip` branch, pinned in `packages/kernel/kernel-plus.conf`
  together with the Linux release it is based on and the Fedora kernel
  SRPM of that release. It is **experimental**: `asahi-wip` is Asahi's
  integration branch, not a release.
- It does not follow upstream by itself. `asahi-wip` is rebased often (onto
  each stable release, with work in progress), and not every state of it
  is one to ship. A maintainer moves the pin by hand, after the new commit
  has booted and run on test machines (Thunderbolt, 10GbE, KVM guests), and
  after the patches and configs are rebased (docs/maintainer-guide.md).
- A scheduled workflow (`kernel-watch`) runs daily. It starts a COPR build
  when `kernel-plus.conf` on the default branch names a release the project
  has not built (that is, after a bump is merged) and its prep check
  passes. It also reports, as workflow warnings, what a maintainer should
  look at: `asahi-wip` moved; kernel.org has a newer stable release of the
  kernel's series; `@asahi` publishes a kernel that sorts above this
  project's (users without the repository priority would get it).
- A failed COPR build of the same release is not retried automatically.
- Stable and security fixes arrive only with a bump of the pin, in practice
  when `asahi-wip` moves to a newer stable release. There are no separate
  security updates, and between bumps this kernel can be behind both
  kernel.org and `@asahi`. If that matters to you, use `@asahi`'s kernel.
- When `@asahi` ships a kernel of the same or a newer series that has
  what this project needs (Thunderbolt/USB4 in particular), the kernel goes
  back to being a rebuild of `@asahi`'s (scripts/asahi-kernel.py still
  finds those SRPMs).
- Kernels are install-only; dnf keeps the previous ones (default:
  `installonly_limit=3`). Booting a 7.1 kernel while a 7.2 kernel is
  installed needs the device-tree step in README.md, Rollback.

## dkms-apple-avd

- DKMS builds it for every installed 7.2 kernel from this project with
  its `-devel` package (`BUILD_EXCLUSIVE_KERNEL`); kernels of other series
  (the 7.1 kernels) use their in-tree decoder.
- When this project's kernel moves to a new kernel series, DKMS skips the
  module for that series and the in-tree decoder is used, until this
  project rebases the driver (maintainer guide). The in-tree driver has the problems the patches
  fix (for example, H.264 streams stop after 4096 slices).

## apple-ave (experimental)

- Follows its upstream repository by hand. No schedule.
- Only for the macOS 13.5 system firmware. Other system firmware versions are
  refused until upstream ports them.
- The firmware files are made on each user's Mac by `apple-ave-fetch-firmware`
  from Apple's 13.5 image; if Apple ever removes that image from its CDN,
  `--ipsw` and `--from-dir` still work from local copies.

## mesa-honeykrisp-plus

- Tracks the Mesa version that Fedora ships for the target release, by hand,
  after Fedora updates it. Until then the private copy keeps the previous
  version, which keeps working as long as the kernel interface it uses does
  not change.
- Patches that upstream Mesa merges are dropped.

## qemu-vmapple and reims-vgpu-backend

- qemu-vmapple tracks `aquarat/qemu-reims-vgpu` `master`, and
  reims-vgpu-backend `aquarat/reims-vgpu` `master`, by hand, after the new
  commits have run macOS guests together (the out-of-process build the
  production runners use). A change to the apv-gpu-proxy protocol moves
  both packages at once.

## Fedora releases

- Built for Fedora 44 (`fedora-44-aarch64`), the release `@asahi` and Fedora
  Asahi Remix currently target. The kernel uses Fedora 44's kernel SRPM.
  Other releases are added when they matter; Mesa needs a matching version
  per release, and the kernel that release's kernel SRPM.
