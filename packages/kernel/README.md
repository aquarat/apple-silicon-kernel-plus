# packages/kernel

**Experimental.** The kernel is built from the Asahi Linux kernel tree's
`asahi-wip` branch (Linux 7.2.11), not from a kernel `@asahi` has
released. `asahi-wip` is Asahi's integration branch: it carries work that
is not in any Fedora Asahi Remix kernel yet, among it the Thunderbolt/USB4
series for Apple silicon. The commit pinned here is the one this project
soak-tested Thunderbolt on, but it has not had the testing a `@asahi`
release gets. If you want the stock kernel's stability, do not use this
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
| Source0 `linux-7.2.11.tar.xz` | the kernel.org tarball | `LINUX_TARBALL_URL`, `LINUX_TARBALL_SHA256` |
| `kernel.spec`, scripts, other sources | Fedora's `kernel-7.2.11-200.fc44` SRPM from Koji | `FEDORA_SRPM_URL`, `FEDORA_SRPM_SHA256` |
| `patch-7.2-redhat.patch` | generated: the [AsahiLinux/linux](https://github.com/AsahiLinux/linux) tree at `ASAHI_COMMIT` plus Fedora's own `patch-7.2-redhat.patch`, as one diff against the tarball | `ASAHI_COMMIT` (a full commit id: the content) |
| `linux-kernel-test.patch` | `patches/*.patch`, in file name order | this directory |
| `kernel-*-fedora.config` | Fedora's configs with `configs/asahi-*.config` and `configs/plus-*.config` applied | this directory |

This is the layout of `@asahi`'s own SRPMs: their `patch-<major>-redhat.patch`
is the Asahi tree plus Fedora's patch, and their `kernel.spec` is
Fedora's with a few settings changed. `make-srpm.sh` makes the same
changes to Fedora's 7.2.11 spec:

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
| 0001 | KVM: save, restore and expose Apple's PAuth virtualization state (VM key, APSTS, APCTL, KERNKEYLO/HI). Needed by macOS guests on QEMU's `vmapple` machine. Only acts on Apple CPUs with ACTLR virtualization (M1, M2), and only for guests | always on |
| 0002 | KVM: decode and emulate MMIO loads/stores that fault without an instruction syndrome (XNU's pre-indexed store to the GIC) | **on**; `kvm.emulate_nisv_ldst=0` turns it off |
| 0003 | atlantic: keep the station MAC unicast filter enabled on AQC113 (ATL2). 7.2's ATL2 filter rework drops unicast frames to the interface's own address when the firmware's filter base index is above the multicast list length (the Mac Studio's built-in 10GbE: unicast RX dead unless promiscuous) | fix |

0001 is a rebase of work by Anees Iqbal (see `CREDITS.md`). 0002 and 0003
are this project's own work. All three are in `git format-patch` form
against the tarball plus `patch-7.2-redhat.patch`; docs/maintainer-guide.md
shows how to rebase them.

0002 was off by default up to the 7.1.13 kernels and is on from 7.2.11:
macOS guests need it, Linux guests never trigger it, and with it on KVM
still behaves as before for every access it does not decode. The
`qemu-vmapple-kvm-nisv` package, which used to turn it on, is retired
(packages/qemu-vmapple/README.md).

### Reserved: tunnelled PCIe over Thunderbolt (APCIEC)

The Asahi tree has the Thunderbolt/USB4 host router driver
(`thunderbolt_apple`, `reset-apple-cio`) but no driver for the PCIe
controllers that carry PCIe tunnels (APCIEC), so Thunderbolt PCIe devices
(NVMe enclosures, 10GbE adapters) do not work yet. Two patches will add it,
and they take these slots:

- `0010-*.patch`: the APCIEC tunnelled-PCIe driver;
- `0011-*.patch`: its device-tree nodes for t600x (j314c, j316c, j375c,
  j375d).

Until they are here, the kernel has what the Asahi series does: USB3
tunnels and XDomain (`thunderbolt_net`), no PCIe or DisplayPort tunnels,
and suspend is refused while a device is connected. When adding them: the
config symbol goes into `configs/plus-aarch64.config` (as a module), and
the `Kernel release naming` rules say which part of the release to bump.

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

1. Symbols that are new in Linux 7.2 itself: Fedora's 7.2.11 configs
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
