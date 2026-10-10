# qemu-vmapple

QEMU with the `vmapple` machine and the Reims paravirtual GPU, for macOS
guests under KVM on Apple silicon Linux hosts.

| | |
|---|---|
| binary | `/usr/libexec/qemu-vmapple/qemu-system-aarch64`, also `/usr/bin/qemu-vmapple` |
| data | `/usr/share/qemu-vmapple` (keymaps, firmware blobs QEMU ships) |
| sources | [aquarat/reims-vgpu](https://github.com/aquarat/reims-vgpu) at `reims_commit`, its `vendor/qemu` submodule = [aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu) at `qemu_commit` |
| configuration | `aarch64-softmmu`, KVM, GTK, GnuTLS, slirp, `-Dreims_vgpu_backend=vulkan`; as `scripts/build-qemu.sh` in [apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest) |

It does not conflict with Fedora's `qemu-*` packages: it owns only the paths
above.

## What else a macOS guest needs

1. The kernel from this project (`kernel-16k-…plus…`), for the PAuth
   VM-key context.
2. The no-syndrome MMIO emulation turned on: install
   `qemu-vmapple-kvm-nisv` (a tmpfiles.d rule that sets
   `kvm.emulate_nisv_ldst=Y`), or see the top-level README for the other
   ways.
3. For the GPU: a Vulkan driver that handles the shaders Reims produces,
   i.e. `mesa-honeykrisp-plus`, selected with `VK_DRIVER_FILES` in QEMU's
   environment (`honeykrisp-plus qemu-vmapple …`).
4. A macOS installation (restore image, AVPBooter, auxiliary storage). The
   VM tooling in apple-macos-arm64-vm-guest makes and runs those. This
   package contains no macOS software or Apple firmware.

## Sources in the SRPM

COPR builds may not have network access, so `scripts/make-srpm.sh
qemu-vmapple` puts everything into the SRPM:

- `reims-vgpu-<commit>.tar.xz`: Reims and QEMU (no `.git`), with QEMU's
  meson subprojects `keycodemapdb`, `berkeley-softfloat-3` and
  `berkeley-testfloat-3` downloaded. `dtc` and `slirp` come from Fedora.
- `reims-vgpu-<commit>-vendor.tar.xz`: `cargo vendor` of Reims'
  `Cargo.lock`, including the git dependency
  [aquarat/metal2vulkan](https://github.com/aquarat/metal2vulkan), and the
  source-replacement config that points cargo at it.

The build runs cargo with `CARGO_NET_OFFLINE=true` and QEMU's configure
with `--disable-download`.

## Updating

Set `reims_commit`, `qemu_commit` (the commit Reims pins in `vendor/qemu`;
`make-srpm.sh` checks it), `reims_date` and `qemu_version` (QEMU's
`VERSION`) in the spec, add a changelog entry, rebuild.
docs/maintainer-guide.md has the steps.

## Licences

QEMU is GPL version 2 as a whole, with many files GPL-2.0-or-later. Reims
states LGPL-3.0-or-later in its `LICENSE` and README, and GPL-2.0-or-later in
its crates' `Cargo.toml`. metal2vulkan is LGPL-3.0-or-later. The vendored
crates keep their own licence files. See `LICENSING.md`.
