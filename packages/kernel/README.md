# packages/kernel

**Experimental.** The kernel is built from the Asahi Linux kernel tree's
`asahi-wip` branch (Linux 7.3.4, commit 201be96df565), not from a kernel
`@asahi` has released (`@asahi` ships 7.3.4-401.asahi; this project's
7.3.4-900.asahiwip.plus5 sorts above it, so dnf keeps this COPR's kernel). `asahi-wip` is Asahi's integration branch: it
carries work that is not in any Fedora Asahi Remix kernel yet. (7.2.15 was
built from the `asahi-7.2.15-2` release tag instead.) The commit pinned here
has not had the testing a `@asahi` release gets. If you want the stock kernel's stability, do not use this
COPR's kernel (README.md, Rollback).

The packages are still Fedora's `kernel-16k-*`, built by Fedora's
`kernel.spec`, so they install, update and boot like the stock kernel
(`kernel-install`, dracut, `update-m1n1` with the kernel's device trees,
grub entries).

## Sources

`scripts/make-srpm.sh kernel` writes the SRPM from what
`kernel-plus.conf` pins:

| | what | pinned by |
|---|---|---|
| Source0 `linux-7.3.4.tar.xz` | the kernel.org tarball | `LINUX_TARBALL_URL`, `LINUX_TARBALL_SHA256` |
| `kernel.spec`, scripts, other sources | Fedora's `kernel-7.3.4-200.fc44` SRPM from Koji | `FEDORA_SRPM_URL`, `FEDORA_SRPM_SHA256` |
| `patch-7.2-redhat.patch` | generated: the [AsahiLinux/linux](https://github.com/AsahiLinux/linux) tree at `ASAHI_COMMIT` plus Fedora's own `patch-7.2-redhat.patch`, as one diff against the tarball | `ASAHI_COMMIT` (a full commit id: the content) |
| `linux-kernel-test.patch` | `patches/*.patch`, in file name order | this directory |
| `kernel-*-fedora.config` | Fedora's configs with `configs/asahi-*.config` and `configs/plus-*.config` applied | this directory |

This is the layout of `@asahi`'s own SRPMs: their `patch-<major>-redhat.patch`
is the Asahi tree plus Fedora's patch, and their `kernel.spec` is
Fedora's with a few settings changed. `make-srpm.sh` makes the same
changes to Fedora's 7.3.4 spec:

- `%define _with_arm64_16k 1`: the 16k variant, which Fedora does not build;
- `%define pkgrelease`/`specrelease`: this project's release
  (README.md, Kernel release naming) and `%define buildid .plus<N>`;
- `def_variants.yaml.fedora`: `drivers/gpu/drm/apple` and
  `drivers/gpu/drm/asahi` in `kernel-16k-modules-core`, as `@asahi` has it;
- only the 16k kernel is built (`WITHOUT` in `kernel-plus.conf`):
  `kernel-16k`, `-core`, `-modules`, `-modules-core`, `-modules-extra`,
  `-modules-internal`, `-devel`, `-devel-matched`. Debug kernels,
  debuginfo, UKIs, `kernel-headers`, `kernel-tools`, `perf` and the 4k
  kernel are not built; those stay `@asahi`'s;
- one `%changelog` entry naming the Asahi commit and the patches.

`@asahi`'s other changes to Fedora's spec (verbose build, headers on, a
dtbloader condition) do not apply to a 16k-only build without headers.
`VARIANTSTREAM = .asahi` in `@asahi`'s `Makefile.rhelver` is used only by
the source tree's `redhat/` tooling, not by the build.

Fedora's `patch-7.2-redhat.patch` (83 files: secure boot lockdown, crypto
and EFI changes, Fedora's Bluetooth change, ...) applies to the Asahi tree
without conflicts. `make-srpm.sh` stops if it ever does not.

The generated patch is reproducible: the same pins give the same patch
(the log prints its sha256). If Asahi ever removes `ASAHI_COMMIT` from
GitHub (`asahi-wip` is rebased often; GitHub keeps unreferenced commits for
a long time, but not forever), `make-srpm.sh` fails at the fetch: point
`ASAHI_GIT` at any clone that still has the commit, or move to a newer
commit (docs/maintainer-guide.md).

## The patches

| patch | what | default |
|---|---|---|
| 0001 | KVM: handle Apple's PAuth virtualization state (a random VM key per VM, APSTS, and per-vCPU APCTL, KERNKEYLO/HI exposed to user space). Needed by macOS guests on QEMU's `vmapple` machine. Only acts on M1 and M2 CPUs, under VHE on bare metal | always on |
| 0002 | KVM: decode and emulate MMIO loads/stores that fault without an instruction syndrome (XNU's pre-indexed store to the GIC) | **on**; `kvm.emulate_nisv_ldst=0` turns it off |

0001 and 0002 are this project's own work. 0001 is an independent
implementation of what Anees Iqbal first showed macOS guests need (see
`CREDITS.md` and `docs/kvm-pauth-provenance.md`); on 7.3.x it is the
7.2.11 `plus4` patch with its context rebased. 0003 (the AQC113 list
filters relative to the firmware's base index) is gone from 7.3.4: the
7.3.4 tree has its own `hw_atl2_hw_packet_filter_set()`, which enables the
list entries relative to the base index. Both patches are in `git format-patch` form against the
tarball plus `patch-7.3-redhat.patch`; docs/maintainer-guide.md
shows how to rebase them. (7.2.11 `plus5` also carried 0004, a backport
of Asahi's fix for GPU kernel-VM buffers that were never freed; 7.3.1's
Asahi base has that fix, so 0004 is not needed here.)

0002 was off by default up to the 7.1.13 kernels and is on from 7.2.11:
macOS guests need it, Linux guests never trigger it, and with it on KVM
still behaves as before for every access it does not decode. The
`qemu-vmapple-kvm-nisv` package, which used to turn it on, is retired
(packages/qemu-vmapple/README.md).

### Tunnelled PCIe over Thunderbolt (APCIEC), patches 0010-0013

The Asahi tree has the Thunderbolt/USB4 host router driver
(`thunderbolt_apple`, `reset-apple-cio`) but no driver for the PCIe
controllers that carry PCIe tunnels (APCIEC). Patches 0010-0013 add it, from
[aquarat/apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux)
(`patches/`, commit dfbc506):

- 0010: DT binding `apple,t6000-apciec`;
- 0011: the `pcie-apple-apciec` driver (`CONFIG_PCIE_APPLE_APCIEC=m`, in
  `configs/plus-aarch64.config`);
- 0012: the APCIEC and DART nodes for t600x die 0, USB4 ports 0-3;
- 0013: enables them on j375 (Mac Studio, ports 0-3) and j314/j316
  (MacBook Pro, ports 0-2) and adds the `usb4_N_pcie` aliases m1n1 fills.

With them, NVMe drives in USB4/Thunderbolt enclosures work (tested: Mac
Studio M1 Max, ASM2464PD enclosure). Install `apple-silicon-thunderbolt` for
the NVMe APST rule those drives need. To update them, copy the series from
that repository (its `scripts/make-patches.sh` regenerates it for a new
base) and bump the release as `Kernel release naming` says. Known issues and
limits are in that repository's README.

### Thunderbolt networking (thunderbolt-net), patches 0020-0027

`patches/tb-net/` of the same repository (commit 1648a11), for IP over a
USB4/Thunderbolt cable between two Macs (or a Mac and another host):

- 0020, 0021: end-to-end flow control on the transmit ring too, for the
  Apple NHI only (`tb_nhi::tx_e2e`). The Apple NHI's transmit ring ignores
  the receiver's credits otherwise, and frames are lost whenever the
  receiver falls behind;
- 0022: the t600x USB4 NHIs are DMA coherent (`dma-coherent`);
- 0023: a lost Tx queue wakeup in `thunderbolt_net` (the interface could
  stop sending for good; not Apple-specific);
- 0024: a page pool for `thunderbolt_net`'s receive buffers (the
  receiving CPU was the limit at 7-8 Gb/s; not Apple-specific);
- 0025: a per-machine host router UID. m1n1 passes on placeholder UIDs that
  are the same on every Mac of a family, so two Macs cabled between the
  same port number collided (same XDomain UUID, same thunderbolt-net MAC).
- 0026: packets from a peer with TSO on arrive larger than the MTU; they
  are now marked as GSO packets, so a bridge or router can forward them to
  a normal-MTU interface (before, a Mac bridged to a LAN through another
  Mac crawled at about 1 Mbit/s unless TSO was off on it; not
  Apple-specific).
- 0027: the receiver in 0026 cuts a forwarded TSO packet at its own MTU,
  because ThunderboltIP does not carry the segment size. When path MTU
  discovery or an MSS clamp lowered the sender's MSS (a tunnel or overlay
  network behind the bridging Mac), those segments are too large for the
  smaller hop and TCP crawled at under 1 MB/s. The sender now keeps TSO only
  for full-sized segments and segments the rest in software (from 7.3.1
  `plus2`; every sender needs it; not Apple-specific).

Measured Mac Studio M1 Max to MacBook Pro M1 Max: 21 Gb/s single stream,
14-15 Gb/s each way bidirectional, at MTU 1500 or 65522, no lost frames.
`apple-silicon-thunderbolt` has the udev rule that goes with them (threaded
NAPI and GRO off on thunderbolt-net interfaces).

### Fabric and DRAM requests to the PMP, patches 0030-0034

On M1 Pro/Max (t6000/t6001) with the power management coprocessor (PMP)
running (an `APPLE_USE_PMP` device tree; off in Fedora's trees), the PMP
sets the fabric and DRAM controller performance states. It saves about
1.3 W at idle on an M1 Max, but nothing in Linux asks it for bandwidth, so
a CPU that streams memory gets the lowest levels: CPU STREAM bandwidth
halves (110/133 -> 55/67 GB/s copy/triad, 10 threads). Each agent (CPU
cluster, GPU, encoder, ...) has a request slot in the PMP's shared
dashboard. These patches let Linux use the CPU clusters' and the encoder's
slots:

- 0030: `pmp-report`: a 64-bit shift for the report entry bit (ids of 31
  and above, used on t6002, were undefined behaviour);
- 0031: `pmp-report`: `apple_pmp_dvfs_request()`, which writes an agent's
  request (SoC, fabric and DRAM-controller levels) into its slot.
  Write-only (reading a slot back can cancel a request the PMP has not
  taken yet), withdrawn across suspend and at shutdown;
- 0032: `icc_get()` exported, so consumers can find paths by node name
  (the device tree comes from the boot loader, so consumers cannot rely on
  new `interconnects` properties);
- 0033: an interconnect provider (`INTERCONNECT_APPLE_PMP=y`): one node per
  agent with a known slot (the three CPU clusters and the first encoder on
  t6000/t6001), each linked to a DRAM node; the requested bandwidth picks a
  fabric/DRAM step, and a request tag can add a minimum SoC level;
- 0034: `apple-cpu-memvote` (`APPLE_CPU_MEMVOTE=m`): each CPU cluster
  requests bandwidth while it is memory-bound: busy, at a high frequency,
  and with at least 10 L1D load misses per 1000 cycles (CPU PMU). A
  request held all the time would cost about 2.4 W under compute-bound
  load. `apple_cpu_memvote.mode=off|auto|force` (also writable at
  `/sys/module/apple_cpu_memvote/parameters/mode`) is for A/B tests; the
  device's `stats` attribute shows each cluster's state.

The `apple-ave` package sends its PMP vote through the provider on this
kernel (`pmp_icc=1`, the default) instead of writing the slot itself.

Nothing changes on machines without the PMP running (the requests are not
written; the CPU votes are not sampled), or on t6002, t8112 and t8103 (no
provider).

Measured on an M1 Max (14", 7.3.1 with these patches, PMP running,
SMC system power):

| | `mode=auto` | `mode=off` | PMP not running |
|---|---|---|---|
| CPU STREAM 10 threads, copy/triad GB/s | 163/165 | 55/67 | 110/134 |
| CPU STREAM 1 thread, E / P0 / P1 cluster | 35 / 77 / 76 | - / 25 / - | 52 (P) |
| idle W (3 pairs, 60 s each) | 4.84, 4.68, 4.50 | 4.88, 4.63, 4.54 | |
| sha256 on 10 threads, W (5 pairs, 25 s) | 25.6 | 25.9 | |
| GPU mat-vec f16/bf16 GB/s | 197/195 | 188/192 | 217/237 |
| video encoder, 120 frames 1080p H.264 | 2.51 s (2.50 s with the driver's own slot write; 3.92 s without a vote) | | |

The encoder's output was identical with the vote through the provider and
with its old direct write (PSNR 44.2 dB).

### The GPU's report to the PMP, patches 0035-0037

Rationale, evidence, design, tests and provenance: [docs/pmp-gpu-report.md](../../docs/pmp-gpu-report.md).

The GPU's own shortfall with the PMP running (3-20% on memory-bound work)
is not a CPU-request problem: the PMP runs its own bandwidth-driven fabric
and DRAM controller DVFS for the GPU, but only for a GPU that has been
reported powered on. Apple's device tree marks the GPU (PMGR device `GFX`,
report bit 9) as one that reports its power state to the PMP; Asahi's
t600x device trees have a report entry for every other such block, but not
for the GPU. t8112's trees make such an entry the GPU's power domain. On an
M1 Max that reports the GPU before its firmware boots, and the machine
hard-hangs within seconds of the firmware starting (three times out of
three). Reported once the GPU driver has bound, it is fine.

- 0035: DT binding for the PMP power state report node and its entries
  (`Documentation/devicetree/bindings/power/apple,pmp-report.yaml`; the
  Asahi tree has none), with the new `apple,report-while-bound`;
- 0036: `pmp-report`: an entry with `apple,report-while-bound = <&dev>` is
  not a power domain. It reports its block on once that device's driver
  has bound and the PMP runs (it waits for the PMP if the driver binds
  first), and off when the driver starts to unbind, across system sleep
  and at shutdown;
- 0037: t6000/t6001 device trees: `report@9` for the GPU in that mode.
  The GPU keeps its PMGR power domain. Not on t6002: the PMP has not been
  run on a two-die machine yet (its Apple device tree also lists one `GFX`
  device, id 10); t602x and later are not covered either.

The bit was checked against Apple's device trees for the 14" M1 Pro
(J314s, t6000) and M1 Max (J314c, t6001). Measured on an M1 Max (14", PMP
running, entry added before the GPU driver loads, CPU votes off), GPU
mat-vec 4096x14336 in GB/s:

| | f32 | f16 | bf16 | q4_0 |
|---|---|---|---|---|
| with the report (0036, 0037) | ~169 | ~221 | ~260 | ~153 |
| without it | ~163 | ~190 | ~188 | ~136 |
| PMP not running | 168 | 217 | 237 | 148 |

Idle power is unchanged (the PMP drops the levels again when the GPU
idles); under sustained GPU mat-vec the machine draws about 10 W more
(53.7 -> 64.0 W) while doing 4-37% more work. Also tested: the GPU driver
binding before the PMP starts (the report follows once it runs). Not yet
tested: suspend/resume (it hangs this machine without these patches too)
and a boot with these device trees in m1n1's stage 2 (the tests added the
entry to the running device tree).

As with 0030-0034, nothing changes without the PMP running: these device
trees are only used when m1n1's stage 2 is rebuilt from them with
`APPLE_USE_PMP`, and the report is never written while the PMP is not
running.

## Thunderbolt in this kernel

- `thunderbolt_apple` (the Apple host router driver, `USB4_APPLE_SOC=m`)
  and `reset-apple-cio` (`RESET_APPLE_CIO=m`) are in
  `kernel-16k-modules-core`, with `thunderbolt_net`, `typec_thunderbolt`
  and the Type-C (`tps6598x`) and PHY (`phy-apple-atc`) drivers. The
  USB4 core is built in (`USB4=y`, Fedora's choice).
- The device trees of this kernel (`/usr/lib/modules/<release>/dtb`)
  describe the host routers: on t600x (`t6000-j314s`, `t6000-j316s`,
  `t6001-j314c`, `t6001-j316c`, `t6001-j375c`, `t6002-j375d`) one
  `apple,t6000-usb4-acio` node with its NHI per Thunderbolt port (3, 4 on
  the Mac Studio, 6 on the M1 Ultra), all enabled, with the `usb4_N_rc` and
  `usb4_N_nhi` aliases m1n1 fills the tunables and DROM through (m1n1
  1.6.1 as Fedora Asahi Remix 44 ships it). So the driver loads at boot
  on these machines; `modprobe.blacklist=thunderbolt_apple` on the
  kernel command line stops that.
- The trees are the ones the lab kernel was tested with (identical after
  decompiling, for j314c, j375c and j375d).
- Known issue: a USB4 link under heavy load can drop about 20 s after a
  reconnect.

## Configs

`configs/` holds two kinds of overlay, applied by
`scripts/kernel-configs.py` to Fedora's `kernel-*-fedora.config` files
before they go into the SRPM. Fedora's `%prep` then checks them as usual
(`process_configs.sh -w -n -c`): every symbol of the tree must have a value
(no new, unset symbols), and nothing may change when `olddefconfig` runs.
That check passes, so the build fails rather than picking values on its
own.

- `asahi-aarch64.config`, `asahi-s390x.config`, `asahi-other.config`:
  `@asahi`'s choices: exactly the difference between `@asahi`'s
  `kernel-7.1.13-402.asahi.fc44` configs and Fedora's
  `kernel-7.1.13-200.fc44` configs (`kernel-configs.py diff`), for the
  aarch64 configs, the s390x configs and the others. Not edited by hand.
- `plus-aarch64.config`: this project's choices.

How new 7.2 symbols get their values, deterministically:

1. Symbols that are new in Linux 7.2 itself: Fedora's 7.2 configs
   already set every one of them (Fedora's own config process requires
   it). Those values are used.
2. Symbols that only the Asahi tree has: `@asahi`'s 7.1.13 choices
   (`asahi-*.config`) cover all of them that existed in 7.1. The Asahi
   7.2 tree at the pinned commit adds two that are new:
   `USB4_APPLE_SOC` and `RESET_APPLE_CIO`; `plus-aarch64.config` sets them
   to `m`.
3. Anything new after a bump makes `%prep` fail with `Found unset config
   items` (or `Mismatches found`). Then add the symbol to
   `plus-<group>.config` with a chosen value, and say why in the commit.

`plus-aarch64.config` today: the Thunderbolt/USB4 host driver and its CIO
reset driver as modules; `USB4_DEBUGFS_WRITE` and `USB4_DMA_TEST` (on in
the lab kernel) off. `USB4_CONFIGFS` follows `USB4` (`def_tristate`), so it
is `y`, as in the lab kernel.

Values that differ from the lab kernel (the 7.1.13 config plus
`olddefconfig` on the same tree) come from Fedora's 7.2 choices, e.g.
`DRIVER_DEFERRED_PROBE_TIMEOUT=-1` on aarch64 (Fedora changed it in 7.2),
the new 7.2 drivers as modules, and the Fedora-only `LOCK_DOWN_IN_EFI_SECURE_BOOT`.
