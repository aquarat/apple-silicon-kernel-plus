# Documentation

## Patch and package documents

Every patch this repository carries, and every package that changes
someone else's code, has a document here: what it does, why (the problem
and the evidence), the design and its alternatives, how it was tested and
what was measured, known limitations, the hardware it applies to, its
upstream status and provenance, and the pull requests. New patches come
with one ([CONTRIBUTING.md](../CONTRIBUTING.md)).

The documents are named by topic, not by patch number: numbers change when
a series is rebased or renumbered, and then only the tables below need
updating.

They live in `docs/`, beside the existing KVM documents, rather than next
to the patches: `packages/*/patches/` are build inputs (the kernel SRPM
applies `patches/*.patch` in name order, `scripts/rebase-avd.sh` reads the
AVD patches), a series that spans several packages (the PMP requests and
apple-ave, the APCIEC patches and their udev rule) has one natural place
here, and links between documents stay short.

### Kernel (`packages/kernel/patches/`)

The current patch set is that of 7.3.4 `plus5`; what the rebase from 7.3.1
changed (pins, release ordering, the dropped 0003, configs, tests) is in
[kernel-7.3.4-rebase.md](kernel-7.3.4-rebase.md).

| patch file | topic | document |
|---|---|---|
| `0001-KVM-arm64-Handle-Apple-PAuth-virtualization-state-under-VHE.patch` | KVM: Apple PAuth state for macOS guests | [kvm-apple-pauth.md](kvm-apple-pauth.md) (also [kvm-macos-guests.md](kvm-macos-guests.md), [kvm-pauth-provenance.md](kvm-pauth-provenance.md)) |
| `0002-KVM-arm64-emulate-MMIO-ldst-without-ISV.patch` | KVM: MMIO loads/stores without a syndrome | [kvm-mmio-without-isv.md](kvm-mmio-without-isv.md) |
| `0003-net-atlantic-AQC113-Enable-list-filters-relative-to-.patch` (**retired** in 7.3.4 `plus5`, #21: the 7.3.4 tree fixes it upstream) | atlantic: AQC113 list filters | [atlantic-aqc113-list-filters.md](atlantic-aqc113-list-filters.md) |
| `0004-drm-asahi-Drain-deferred-GPUVM-BOs-when-a-kernel-map.patch` (branch `kernel-7.2` only) | drm/asahi: kernel-VM BO leak | [asahi-gpu-kernel-vm-bo-drain.md](asahi-gpu-kernel-vm-bo-drain.md) |
| `0010-dt-bindings-pci-Add-Apple-T600x-tunnelled-PCIe-contr.patch` | tunnelled PCIe (APCIEC): binding | [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md) |
| `0011-PCI-apple-Add-driver-for-the-T600x-tunnelled-PCIe-co.patch` | APCIEC: driver | [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md) |
| `0012-arm64-dts-apple-t600x-Add-tunnelled-PCIe-controllers.patch` | APCIEC: SoC nodes | [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md) |
| `0013-arm64-dts-apple-t600x-Enable-tunnelled-PCIe-on-j314-.patch` | APCIEC: board nodes | [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md) |
| `0020-thunderbolt-apple-Enable-E2E-flow-control-on-Tx-ring.patch` | thunderbolt-net: Tx E2E flag | [thunderbolt-net.md](thunderbolt-net.md) |
| `0021-net-thunderbolt-Enable-E2E-flow-control-on-the-Tx-ri.patch` | thunderbolt-net: Tx E2E | [thunderbolt-net.md](thunderbolt-net.md) |
| `0022-arm64-dts-apple-t600x-Mark-the-USB4-NHIs-as-DMA-cohe.patch` | thunderbolt-net: coherent NHIs | [thunderbolt-net.md](thunderbolt-net.md) |
| `0023-net-thunderbolt-Fix-a-lost-Tx-queue-wakeup.patch` | thunderbolt-net: lost wakeup | [thunderbolt-net.md](thunderbolt-net.md) |
| `0024-net-thunderbolt-Use-a-page-pool-for-Rx-buffers.patch` | thunderbolt-net: Rx page pool | [thunderbolt-net.md](thunderbolt-net.md) |
| `0025-thunderbolt-apple-Derive-a-per-machine-host-router-U.patch` | thunderbolt: per-machine UID | [thunderbolt-net.md](thunderbolt-net.md) |
| `0026-net-thunderbolt-Make-oversized-TSO-packets-forwardab.patch` | thunderbolt-net: forwarding TSO packets | [thunderbolt-net-tso-forwarding.md](thunderbolt-net-tso-forwarding.md) |
| `0027-net-thunderbolt-Segment-TSO-packets-the-receiver-wou.patch` | thunderbolt-net: TSO with a lowered MSS | [thunderbolt-net-tso-forwarding.md](thunderbolt-net-tso-forwarding.md) |
| `0030-pmdomain-apple-pmp-report-Use-a-64-bit-shift-for-the.patch` | PMP: 64-bit report bit | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) |
| `0031-pmdomain-apple-pmp-report-Add-a-DVFS-request-interfa.patch` | PMP: DVFS request interface | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) |
| `0032-interconnect-Export-icc_get.patch` | interconnect: export `icc_get()` | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) |
| `0033-interconnect-apple-Add-a-PMP-provider-for-fabric-and.patch` | PMP: interconnect provider | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) |
| `0034-soc-apple-Add-CPU-cluster-memory-bandwidth-votes.patch` | PMP: CPU cluster bandwidth votes | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) |
| `0035-dt-bindings-power-apple-Add-the-PMP-power-state-repo.patch` | PMP: report-node binding | [pmp-gpu-report.md](pmp-gpu-report.md) |
| `0036-pmdomain-apple-pmp-report-Report-a-block-only-while-.patch` | PMP: report a block while its driver is bound | [pmp-gpu-report.md](pmp-gpu-report.md) |
| `0037-arm64-dts-apple-t600x-Report-the-GPU-to-the-PMP-whil.patch` | PMP: report the GPU (t6000/t6001) | [pmp-gpu-report.md](pmp-gpu-report.md) |

Kernel configuration choices (`packages/kernel/configs/plus-aarch64.config`)
are explained in [packages/kernel/README.md](../packages/kernel/README.md#configs)
and in the document of the patch that needs them.

### Other packages

| package | files | document |
|---|---|---|
| `apple-silicon-thunderbolt` | `60-apciec-nvme-apst.rules` | [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md) |
| `apple-silicon-thunderbolt` | `61-thunderbolt-net-threaded.rules` | [thunderbolt-net.md](thunderbolt-net.md) |
| `dkms-apple-avd` | `packages/apple-avd/patches/0001-0005` | [apple-avd-fixes.md](apple-avd-fixes.md) |
| `apple-ave`, `dkms-apple-ave` | vendored driver and overlays, firmware tool, the PMP interconnect vote | [apple-ave.md](apple-ave.md) |
| `mesa-honeykrisp-plus` | `packages/mesa-honeykrisp-plus/patches/0001-0002` | [honeykrisp-16bit-varyings.md](honeykrisp-16bit-varyings.md) |
| `mesa-coopmat` | a pinned Mesa branch (no patch files) | [mesa-coopmat.md](mesa-coopmat.md) |
| `qemu-vmapple` | a pinned QEMU fork (no patch files) | [packages/qemu-vmapple/README.md](../packages/qemu-vmapple/README.md); KVM side: [kvm-macos-guests.md](kvm-macos-guests.md) |
| `apple-pmp-enable` | `pmp-dtb` (the `APPLE_USE_PMP` device tree fixup), `apple-pmp-enable` (the trial boot), `validated.txt` | [pmp-enable.md](pmp-enable.md) |
| `reims-vgpu-backend` | a pinned Reims fork (no patch files) | [packages/reims-vgpu-backend/README.md](../packages/reims-vgpu-backend/README.md) |

`qemu-vmapple` and `reims-vgpu-backend` build forks whose changes are
documented in those repositories; this repository carries only their
packaging, explained in the package READMEs and in LICENSING.md.

## Other documents

| document | what |
|---|---|
| [kvm-macos-guests.md](kvm-macos-guests.md) | using the KVM patches for macOS guests: switches and checks |
| [kvm-pauth-provenance.md](kvm-pauth-provenance.md) | how kernel patch 0001 was written (clean-room process, sources, incidents, tests) |
| [kernel-7.3.4-rebase.md](kernel-7.3.4-rebase.md) | the move from 7.3.1 `plus4` to 7.3.4 `plus5`: pins, release ordering, patch and config changes, tests (M1 Max and M1 Pro) |
| [benchmarks.md](benchmarks.md) | measured results of the patches and packages, as charts and tables, each citing the document it comes from; charts drawn by `scripts/bench-charts.py` from [data/benchmarks.json](data/benchmarks.json) into `img/` |
| [kernel-release-naming.md](kernel-release-naming.md) | the kernel's version-release scheme, its history and how it sorts against `@asahi`'s kernels |
| [consolidation-plan.md](consolidation-plan.md) | inventory of kernel-side work and what is carried, decided 2026-11-17 |
| [maintainer-guide.md](maintainer-guide.md) | building, rebasing and bumping the packages |
| [release-process.md](release-process.md) | versions and releases |
| [update-policy.md](update-policy.md) | how each package follows its upstream |
