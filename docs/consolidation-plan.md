# Consolidation plan: one fully featured kernel

Status: decided, 2026-11-17 (see "Decisions"). Nothing here is released
until COPR builds it.

This project's kernel should carry every kernel-side change the
maintainers have made for Apple silicon, so that one build has all of
them. This document lists that work and says where each change stands. It
was sorted into merge now, merge after testing and keep out; the
owner's decisions follow.

Scope: kernel patches, kernel configuration, device trees, and the
out-of-tree modules packaged here (`dkms-apple-avd`, `dkms-apple-ave`).
Userspace packages (Mesa, QEMU, Reims) are out of scope, except where
they need something from the kernel.

## Where the work comes from

| source | kernel-side content |
|---|---|
| this repository, `main` (7.2.11 `plus4`) | patches 0001-0003, 0010-0013, 0020-0026; apple-avd patches 0001-0004; apple-ave 0.99.5 |
| this repository, `kernel-7.3` (7.3.1 `plus1`) | the same series on Asahi `c2e6784b008c`; 0003 rewritten for 7.3; apple-avd 0005. Still has the pre-`plus4` 0001 |
| [apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux) | APCIEC driver and DT (0010-0013); thunderbolt-net series (0020-0026); TX-MSS fix (patch 8, branch `tbnet-tx-mss`) |
| [apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver) | the AVE encoder driver (0.99.6 on `main`: reload checks, staged unload) |
| [apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest) | 7.1.13 copies of 0001/0002 (identical in code); notes that its dma-buf GPU path needs the GEM PRIME-import fix |
| [qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu), [reims-vgpu](https://github.com/aquarat/reims-vgpu) | no kernel patches; they need 0001's registers, `CONFIG_UDMABUF=y` and `CONFIG_UCLAMP_TASK=y` (both set) |
| [aquarat/linux](https://github.com/aquarat/linux) | the pinned Asahi commits under `plus/` tags; no commits of our own |
| maintainers' lab trees | debug and bring-up code (see "Keep out") |

## Inventory

"7.2" is 7.2.11 (`main`), "7.3" is 7.3.1 (`kernel-7.3`).

| item | what it does | where | carried | trees | upstream | tested | outcome |
|---|---|---|---|---|---|---|---|
| Independent PAuth patch on 7.3 | 0001 on 7.3 is still the rebase of the Linux 6.19 patch that `plus4` replaced on 7.2 (docs/kvm-pauth-provenance.md) | `main` 0001, rebased by context to 7.3 | 7.2 only | 7.3 | none | 7.2: macOS 13/26 guests on t6001; 7.3: build only | merged (#6) |
| thunderbolt-net TSO for a lowered MSS | software-segments TSO packets when the path MSS is below what the receiver would use (uploads under 1 MB/s behind an MSS clamp) | thunderbolt-linux `tbnet-tx-mss` patch 8 = 0027; 0026 message corrected | in PR #2 (7.2), PR #3 (7.3) | 7.2, 7.3 | none | build; hardware test pending | merged (#2, #3) |
| Asahi GPU kernel-VM deferred BO drain | kernel mappings drop their GPUVM BOs as deferred but the kernel VM never drained them: GEM memory leaks per timestamp/allocator mapping | 0004 backport | in PR #2 (7.2) | 7.2 | upstream 256b1204c12d; the 7.3 base has it | A/B on t6001 in progress | merged on 7.2 (#2); not needed on 7.3 |
| apple-ave 0.99.6 | driver reload checks and a staged-unload fix | AVE `main` ff8bba6 | in PR #4 | both | n/a (out of tree) | H.264 on t8103 after reload | merged (#4) |
| GEM shmem PRIME-import fix on 7.2 | imported dma-bufs become driver objects, so closing a handle unbinds them (re-import fails with `EALREADY` otherwise; `VM_BIND` touches memory past the C object) | upstream c2c491d3c360, 739b65e681da + drm/asahi `create_imported` | no | 7.2 only | upstream; the 7.3 base has it | not written | skipped |
| AVD fixes in-tree | apple-avd 0001-0004 (0005 on 7.3) as kernel patches, not only DKMS | `packages/apple-avd/patches` | as DKMS | both | not upstream | DKMS builds run in production use | stays DKMS |
| PMP device trees | builds t600x DTBs as with `-DAPPLE_USE_PMP` (PMP alias, display/ISP/AVD power domains behind PMP reports); the AVE encoder's clock vote needs it (about 3x faster) | a DTB post-processor with a `--check` against a flag build | no | both | Asahi has the `#ifdef`s, off by default | booted on t6000-j314s (7.1); the check passes on other t600x boards on 7.2 | keep out |
| VRR experiments | display (DCP) VRR patches on a 7.1.13 base | a lab kernel | no | 7.1 | Asahi 7.2 parses min/max VRR and marks VRR modes itself | not reviewed | keep out |
| AVE DT binding draft | `apple,ave` binding and a t6001 dtsi | AVE repo `dts/` | no | n/a | no | marked not usable (placeholder power domains) | keep out |
| Thunderbolt bring-up code | runtime DT-overlay module enabling inert nodes stage by stage, inert DTB generator, APCIEC prototype | lab trees | no | 7.1/7.2 | superseded by 0010-0013, 0022 | lab only | keep out |
| thunderbolt-net debug | ring-size/throttling build knobs, NAPI kick, register and ring dump modules | lab trees | no | 7.2 | n/a | lab only | keep out |
| USB4 debug options | `USB4_DEBUGFS_WRITE=y`, `USB4_DMA_TEST=m` | lab config | off on purpose | both | n/a | n/a | keep out |
| 7.1 Thunderbolt backport | Asahi's USB4 series on 7.1.13 | lab tree | no | 7.1 | in `asahi-wip` 7.2+ | compile only | keep out |
| netconsole | `NETCONSOLE=m`, `NETCONSOLE_DYNAMIC=y` | Fedora config | yes (Fedora's values) | both | n/a | n/a | nothing to do |

Already carried and unchanged by this plan: 0001-0003 (KVM PAuth, KVM
MMIO without ISV, AQC113), 0010-0013 (APCIEC), 0020-0026 (Thunderbolt
networking), `plus-aarch64.config` (USB4 host and CIO reset drivers,
APCIEC as modules), apple-avd 0001-0004/0005, apple-ave 0.99.5.

## Decisions (2026-11-17)

1. **7.3.1 replaces 7.2.11 on `main` now.** The 7.2.11 line continues on
   branch `kernel-7.2` (7.2.11 `plus5`: #2, retargeted there as #7).
2. **Merge order** #3, then #6, then the move of `main` to 7.3.1 (#9).
3. **GEM PRIME-import backport to 7.2: skipped.** 7.3.1 has the fix.
4. **AVD stays DKMS.** On 7.3.1 it is `dkms-apple-avd` 7.3.1.2 (the
   7.2.15/7.3.1 driver plus 0005), built for 7.2 and 7.3 kernels, so a 7.2
   kernel kept for rollback keeps the patched decoder. No in-tree AVD
   patches for now.
5. **PMP device trees stay out** of this project.
6. **CI compile job: added** (see CI).
7. **VRR experiments stay out.**

## Done

- **7.3: the independent PAuth patch** (#6, 7.3.1 `plus3`): `main`'s
  0001 rebased to 7.3.1 by context only (two hunks, no code change), and
  `main` merged into the 7.3 line.
- **7.3.1 on `main`** (#9): the 7.3 line with `main` merged in (apple-ave
  0.99.6). 7.2.11 `plus5`'s 0004 is not carried: the 7.3.1 Asahi base has
  that fix.
- The mirror tag `plus/asahi-wip-7.3.1-c2e6784b008c` is in
  [aquarat/linux](https://github.com/aquarat/linux).

## Still to test on hardware (7.3.1)

- a macOS guest with the rebased 0001 (the checks in
  kvm-macos-guests.md);
- 0003 on an AQC113 port (rewritten for 7.3, not yet run);
- Thunderbolt networking with 0027, and NVMe over APCIEC;
- the DKMS builds of both modules on the built kernel.

## Keep out

- **PMP device trees**: a PMP-enabled DTB stops the machine from booting
  if the bootloader cannot find the PMP nodes in the Apple device tree;
  it has been booted on one board, t6002 is not supported, and on t8112
  the PMP firmware crashes unless the ANE stays powered (and the encoder
  gets slower). Device trees go into the boot image for every kernel, so a
  bad one cannot be undone by picking another boot entry.
- **VRR experiments**: written for 7.1; the 7.2 and later trees have
  their own VRR handling.
- **GEM PRIME-import backport to 7.2**: 7.3.1 has the fix.
- **Bring-up and debug code** (overlay module, prototypes, debug modules,
  debug configs, 7.1 backport): lab tools, superseded by the patches
  above, or for a kernel series this project no longer builds.
- **AVE DT binding draft**: not usable yet; the driver uses its overlays.
- **Deployment tooling** (boot-image guards, kernel pinning, per-machine
  encoder options, network cutover scripts): specific to one set of
  machines; not part of this project.

## Packaging

- **In-tree patches** (`packages/kernel/patches/`): everything that
  changes the kernel image or in-tree modules: KVM, Thunderbolt/USB4,
  networking, PCIe, DT, DRM. One patch per change, in `git format-patch`
  form, numbered by area (00xx KVM/misc, 001x APCIEC, 002x
  thunderbolt-net).
- **DKMS** for the AVD decoder fixes (rebased per kernel series) and the
  AVE encoder (experimental, out of tree, loaded with overlays, firmware
  made on the user's machine). Both also build for stock kernels of the
  same series.

## Versions and BUILDID

| branch | release |
|---|---|
| `main` | `7.3.1-900.asahiwip.plus3` |
| `kernel-7.2` | `7.2.11-900.asahiwip.plus5` |

- 7.3.1 `plus1` and `plus2` were earlier states of the 7.3 line; their
  numbers are not reused for different content.
- 7.3.1 sorts above every 7.2.11 release. A newer Asahi commit on 7.3.1
  is `901.asahiwip.plus1`; a new Linux version is `900.asahiwip.plus1`.
- Merging a new release into `main` makes `kernel-watch` start a COPR
  build of it (docs/update-policy.md).
- `kernel-7.2.15` (7.2 is end of life at 7.2.15) stays for reference and
  is not merged.

## CI

`ci` checks that patches apply and configs pass (`rpmbuild -bp`), and
builds SRPMs. The `kernel-build` workflow adds a compile check
(`scripts/kernel-build-check.sh`), on pull requests and pushes that
change the kernel or the module packages:

- the SRPM's prepared tree with its 16k config, `make prepare`;
- the directories of every C/Rust file the kernel patches touch;
- the Apple device trees, when a patch touches one;
- `apple-avd` and `apple-ave` built against that tree, as DKMS builds
  them.

A full kernel build stays a maintainer step (about 22 minutes on an
M1 Max) before a release.
