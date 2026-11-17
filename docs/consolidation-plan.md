# Consolidation plan: one fully featured kernel

Status: proposal, 2026-11-17. For review; nothing here is released.

This project's kernel should carry every kernel-side change the
maintainers have made for Apple silicon, so that one build has all of
them. This document lists that work, says where each change stands, and
sorts it into three groups: merge now, merge after testing, and keep out.

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

| item | what it does | where | carried | trees | upstream | tested | group |
|---|---|---|---|---|---|---|---|
| Independent PAuth patch on 7.3 | 0001 on 7.3 is still the rebase of the Linux 6.19 patch that `plus4` replaced on 7.2 (docs/kvm-pauth-provenance.md) | `main` 0001, rebased by context to 7.3 | 7.2 only | 7.3 | none | 7.2: macOS 13/26 guests on t6001; 7.3: build only | **merge now** |
| thunderbolt-net TSO for a lowered MSS | software-segments TSO packets when the path MSS is below what the receiver would use (uploads under 1 MB/s behind an MSS clamp) | thunderbolt-linux `tbnet-tx-mss` patch 8 = 0027; 0026 message corrected | in PR #2 (7.2), PR #3 (7.3) | 7.2, 7.3 | none | build; hardware test pending | merge after testing (PRs open) |
| Asahi GPU kernel-VM deferred BO drain | kernel mappings drop their GPUVM BOs as deferred but the kernel VM never drained them: GEM memory leaks per timestamp/allocator mapping | 0004 backport | in PR #2 (7.2) | 7.2 | upstream 256b1204c12d; the 7.3 base has it | A/B on t6001 in progress | merge after testing (PR open) |
| apple-ave 0.99.6 | driver reload checks and a staged-unload fix | AVE `main` ff8bba6 | in PR #4 | both | n/a (out of tree) | H.264 on t8103 after reload | merge after testing (PR open) |
| GEM shmem PRIME-import fix on 7.2 | imported dma-bufs become driver objects, so closing a handle unbinds them (re-import fails with `EALREADY` otherwise; `VM_BIND` touches memory past the C object) | upstream c2c491d3c360, 739b65e681da + drm/asahi `create_imported` | no | 7.2 only | upstream; the 7.3 base has it | not written | merge after testing, or skip in favour of 7.3 |
| AVD fixes in-tree | apple-avd 0001-0004 (0005 on 7.3) as kernel patches, not only DKMS | `packages/apple-avd/patches` | as DKMS | both | not upstream | DKMS builds run in production use | merge after testing (packaging change) |
| PMP device trees | builds t600x DTBs as with `-DAPPLE_USE_PMP` (PMP alias, display/ISP/AVD power domains behind PMP reports); the AVE encoder's clock vote needs it (about 3x faster) | a DTB post-processor with a `--check` against a flag build | no | both | Asahi has the `#ifdef`s, off by default | booted on t6000-j314s (7.1); the check passes on other t600x boards on 7.2 | keep out for now |
| VRR experiments | display (DCP) VRR patches on a 7.1.13 base | a lab kernel | no | 7.1 | Asahi 7.2 parses min/max VRR and marks VRR modes itself | not reviewed | keep out pending review |
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

## Merge now

1. **7.3: the independent PAuth patch** (PR #6, "Kernel 7.3.1 plus3").
   `main`'s 0001 rebased to 7.3.1 by context only (two hunks, no code
   change), plus `main` merged into the 7.3 branch so it has the
   provenance document, CREDITS/LICENSING wording, mesa-coopmat and the
   QEMU/Reims bumps. Stacked on PR #3 (7.3.1 plus2), so it is
   7.3.1 `plus3`. Without it, a 7.3 release would bring the replaced
   patch back.

Nothing else is ready to merge without a hardware test.

## Merge after testing

In order:

1. **PR #2 / #3 / #4** (TX-MSS, GPU kernel-VM BO drain, apple-ave 0.99.6):
   already open; they merge when their hardware tests pass.
2. **7.3 as the main kernel.** Before `kernel-7.3` replaces `main`:
   a macOS guest on 7.3.1 with the rebased 0001 (the checks in
   kvm-macos-guests.md), Thunderbolt networking and NVMe, the 10GbE port
   (0003 was rewritten for 7.3 and has not run on hardware), DKMS
   builds of both modules. Push the `plus/asahi-wip-7.3.1-c2e6784b008c`
   tag to the mirror first (maintainer guide); it does not exist yet.
   Merging changes the default branch's release, so `kernel-watch` will
   start a COPR build.
3. **GEM PRIME-import fix on 7.2: probably skip.** 7.3.1 has it. A 7.2
   backport needs three upstream commits and a context fix in another
   Rust DRM driver, for one opt-in path (dma-buf import into the Asahi
   GPU). Do it only if 7.2 stays the main kernel for long.
4. **AVD fixes in the kernel.** Since this project builds the kernel, the
   decoder fixes can be kernel patches (`0030-0034`), which removes the
   DKMS build, the `depmod.d` override and the per-series
   `BUILD_EXCLUSIVE_KERNEL` gap after each kernel move. `dkms-apple-avd`
   would stay for stock `@asahi` kernels of the same series, or be
   retired. Needs a decoding soak (H.264 and HEVC, hours) on the built
   kernel before release.

## Keep out

- **PMP device trees**: a PMP-enabled DTB stops the machine from booting
  if the bootloader cannot find the PMP nodes in the Apple device tree;
  it has been booted on one board, t6002 is not supported, and on t8112
  the PMP firmware crashes unless the ANE stays powered (and the encoder
  gets slower). Device trees go into the boot image for every kernel, so a
  bad one cannot be undone by picking another boot entry. Revisit as a
  separate opt-in package with a per-board allowlist, after boots on
  more boards.
- **VRR experiments**: written for 7.1; the 7.2 tree has its own VRR
  handling. Review against 7.3 before deciding; nothing to merge as is.
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
  thunderbolt-net; proposed 003x AVD).
- **DKMS** stays for the AVE encoder: experimental, out of tree, loaded
  by hand with overlays, firmware made on the user's machine. It also
  builds for stock kernels of the same series.
- AVD: DKMS now; in-tree proposed above.

## Versions and BUILDID

| tree | now | after the open PRs |
|---|---|---|
| 7.2.11 (`main`) | `900.asahiwip.plus4` | `plus5` (PR #2) |
| 7.3.1 (`kernel-7.3`) | `900.asahiwip.plus1` | `plus2` (PR #3), `plus3` (PR #6) |

- 7.3.1 `plus1` was built and run as a test kernel, and `plus2` is taken
  by PR #3; neither number is reused for different content. If PR #3 and the plus3 PR merge in the other
  order, the second one to merge takes the next number.
- When 7.3 replaces 7.2 on `main`, it keeps its 7.3.1 `plusN`; 7.3.1
  sorts above every 7.2.11 release. A newer Asahi commit on 7.3.1 is
  `901.asahiwip.plus1`; a new Linux version is `900.asahiwip.plus1`.
- In-tree AVD patches would be a `BUILDID` bump of the kernel and a new
  `dkms-apple-avd` Release that skips kernels that already have them.
- `kernel-7.2.15` (7.2 is end of life at 7.2.15) stays for reference and
  is not merged.

## CI

`ci` checks today that patches apply and configs pass (`rpmbuild -bp`),
and builds SRPMs; nothing compiles kernel code. Proposed, as its own
change:

- a `kernel-build` job on the arm64 runner: the prepared tree, then
  `make prepare`, the directories the patches touch
  (`arch/arm64/kvm`, `drivers/thunderbolt`, `drivers/net/thunderbolt`,
  `drivers/pci/controller`, `drivers/net/ethernet/aquantia`) and
  `make dtbs` for `apple/`. The Rust DRM driver needs the Rust
  toolchain; build it there only when a patch touches it;
- the DKMS modules built against that tree;
- run on pull requests that change `packages/kernel/` or the module
  packages.

A full kernel build stays a maintainer step (about 22 minutes on an
M1 Max) before a release.

## Open decisions

1. Whether 7.3.1 replaces 7.2.11 on `main` now or after Asahi tags a 7.3
   release.
2. GEM PRIME-import backport to 7.2: skip (recommended) or do.
3. AVD fixes in-tree, and the future of `dkms-apple-avd`.
4. PMP device trees: stay out, or an opt-in package later.
5. The CI compile job.
