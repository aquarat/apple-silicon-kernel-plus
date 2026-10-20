# apple-silicon-kernel-plus

RPM packages for Fedora Asahi Remix on Apple silicon Macs: a kernel from
the Asahi Linux kernel tree's `asahi-wip` branch (Linux 7.2, with
Thunderbolt/USB4 host support) and KVM patches for macOS guests, packaged
like the Fedora Asahi kernel; video decoder and encoder drivers, a patched
Vulkan driver, and QEMU for macOS guests with its paravirtual GPU as a
separate program. COPR builds and hosts the packages; GitHub Actions
checks them and starts the builds.

**Unofficial.** This project is not affiliated with or endorsed by Asahi
Linux, Fedora or Apple. Do not report bugs from these packages to Asahi
Linux or Fedora; report them here.

## Packages

| package | what | status |
|---|---|---|
| `kernel` (`kernel-16k-*`) | Fedora's `kernel-16k` packages built from the Asahi Linux kernel tree (`asahi-wip`, Linux 7.2.11) with `@asahi`'s configuration, the Thunderbolt/USB4 host driver and the tunnelled-PCIe driver (`pcie-apple-apciec`, NVMe in Thunderbolt enclosures on M1 Pro/Max/Ultra) as modules, an AQC113 10GbE fix, and two KVM patches for macOS guests: Apple PAuth VM-key context and emulation of MMIO loads/stores without a syndrome (both on). [packages/kernel](packages/kernel) | **experimental** ([why](packages/kernel/README.md)) |
| `apple-silicon-thunderbolt` | udev rules: NVMe power-state transitions (APST) off for drives in Thunderbolt enclosures only (they drop the USB4 link otherwise), and threaded NAPI with GRO off for Thunderbolt networking (thunderbolt-net). [packages/apple-silicon-thunderbolt](packages/apple-silicon-thunderbolt) | experimental |
| `dkms-apple-avd` | The Asahi AVD video decoder driver with four fixes for long-running streams, built by DKMS. [packages/apple-avd](packages/apple-avd) | stable |
| `apple-ave`, `dkms-apple-ave` | A V4L2 H.264/HEVC encoder driver for the AVE block, reverse engineered, and `apple-ave-fetch-firmware`, which makes its firmware files on your Mac from Apple's own image. No Apple firmware or Apple data included. [packages/apple-ave](packages/apple-ave) | **experimental** ([why](packages/apple-ave/README.md#status)) |
| `mesa-honeykrisp-plus` | Mesa's Asahi Vulkan driver (Honeykrisp) with two shader compiler fixes, installed beside the system Mesa and used only through `VK_DRIVER_FILES`. Patch 0002 is still being validated. [packages/mesa-honeykrisp-plus](packages/mesa-honeykrisp-plus) | stable (0002: in validation) |
| `qemu-vmapple` | QEMU with the `vmapple` machine for macOS guests, installed beside Fedora's qemu. Its paravirtual GPU runs out of process: the `apv-gpu-proxy` device forwards it to `reims-vgpu-backend`; no GPU code in QEMU. (`qemu-vmapple-kvm-nisv` is retired: an empty package now, see [its README](packages/qemu-vmapple/README.md#qemu-vmapple-kvm-nisv-retired).) [packages/qemu-vmapple](packages/qemu-vmapple) | experimental (out-of-process GPU: new in this release; in production use since 2026-10-19) |
| `reims-vgpu-backend` | Reims, the paravirtual GPU of macOS guests, as its own program: runs the guest's Metal work on the host's Vulkan driver (with `mesa-honeykrisp-plus`), for `qemu-vmapple`. [packages/reims-vgpu-backend](packages/reims-vgpu-backend) | experimental (new package; in production use since 2026-10-19) |

## Supported hardware

As the sources state; "tested" means on at least one machine of that SoC.

| package | SoCs |
|---|---|
| kernel | what the Asahi tree supports (M1 and M2 families). Thunderbolt/USB4: the Asahi tree's device trees describe it for t8103, t8112 and t600x; USB3 tunnels and XDomain (thunderbolt-net, with this project's flow-control, page-pool and per-machine UID patches; tested Mac-to-Mac on t6001); PCIe tunnels on t600x with `pcie-apple-apciec` (tested on t6001, Mac Studio port 3, NVMe enclosure; known issues in [apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux#status-and-known-issues)); no DisplayPort tunnels. The KVM patches act only on CPUs with Apple's ACTLR virtualization (M1: t8103, t6000, t6001, t6002; M2: t8112, t6020, t6021, t6022); tested on t6001 |
| dkms-apple-avd | M1 family (t8103, t6000, t6001, t6002); t8112: H.264 works, HEVC times out (open) |
| apple-ave | t6000, t8103 (H.264 without B frames), t8112; t6001 and t6002 after enabling them (not yet run in this configuration). All with the macOS 13.5 system firmware |
| mesa-honeykrisp-plus | M1 and M2 GPUs, as Mesa's Asahi driver |
| qemu-vmapple | hosts that run the kernel above; macOS 13 and 26 guests used on t6001 and t6002 hosts |
| reims-vgpu-backend | M1 and M2 GPUs, with `mesa-honeykrisp-plus`; the out-of-process GPU used with macOS 26 guests on a t6002 host |

## Install

The COPR project is `aquarat/apple-silicon-kernel-plus` (it may not exist
yet; this line is a placeholder until it does).

```sh
sudo dnf copr enable aquarat/apple-silicon-kernel-plus
sudo dnf upgrade                      # moves you to this project's kernel (see below)
sudo dnf install dkms-apple-avd       # and/or: apple-ave, mesa-honeykrisp-plus, apple-silicon-thunderbolt,
                                      #   qemu-vmapple (recommends reims-vgpu-backend)
```

DKMS packages need `kernel-16k-devel` for each installed kernel.

**Enabling this COPR moves you to this project's kernel, and that kernel is
experimental.** It is Linux 7.2 from Asahi's integration branch, while
`@asahi` ships 7.1; it sorts as newer than every `@asahi` 7.1 kernel, so
`dnf upgrade` installs it and makes it the default boot entry. Read
[Rollback](#rollback) before you do: going back to a 7.1 kernel needs one
extra step. See also [Kernel release naming](#kernel-release-naming).

## Kernel release naming

The kernel is `<Linux version>-<N>.asahiwip.plus<M>.fc44`:

| | version-release | `uname -r` |
|---|---|---|
| stock `@asahi` | `7.1.13-402.asahi.fc44` | `7.1.13-402.asahi.fc44.aarch64+16k` |
| this project, up to 7.1.13 | `7.1.13-402.asahi.plus1.fc44` | `7.1.13-402.asahi.plus1.fc44.aarch64+16k` |
| this project, 7.2.11 before Thunderbolt networking | `7.2.11-900.asahiwip.plus1.fc44` | `7.2.11-900.asahiwip.plus1.fc44.aarch64+16k` |
| this project now | `7.2.11-900.asahiwip.plus2.fc44` | `7.2.11-900.asahiwip.plus2.fc44.aarch64+16k` |

- The version is the Linux release the pinned Asahi commit is based on
  (`KERNEL_VERSION` in `packages/kernel/kernel-plus.conf`).
- `N` (`PKGRELEASE`) starts at 900 for each Linux version and goes up by
  one for each newer Asahi commit on the same Linux version. 900 is above
  any release number `@asahi` uses (400 and up), so for the same Linux
  version this project's kernel sorts first.
- `asahiwip` says where the source comes from; `plus<M>` (`BUILDID`) goes
  up when only this project's patches, configs or packaging change, and
  back to `plus1` when `N` or the version changes.

rpm compares version first, then the release segment by segment (numbers
as numbers, letters as strings). Checked with `rpmdev-vercmp`:

| this project's `7.2.11-900.asahiwip.plus1.fc44` against | result |
|---|---|
| `7.1.13-402.asahi.fc44` (stock), `7.1.13-402.asahi.plus1.fc44` (ours before), `7.1.14-403.asahi.fc44` | newer (7.2.11 > 7.1.x) |
| `7.2.11-400.asahi.fc44`, `7.2.11-402.asahi.fc44` (a future `@asahi` 7.2.11) | newer (900 > 40x) |
| `7.2.11-200.fc44` (Fedora's, not a 16k package anyway) | newer |
| `7.2.11-900.asahiwip.plus2.fc44`, `7.2.11-901.asahiwip.plus1.fc44`, `7.2.12-900.asahiwip.plus1.fc44` | older (our own next builds) |
| `7.2.12-400.asahi.fc44`, `7.3.0-400.asahi.fc44` (a future `@asahi` kernel of a newer Linux version) | older |

`7.2.11-901.asahiwip.plus1` is also newer than `7.2.11-900.asahiwip.plus9`:
`N` decides before `M`.

So once `@asahi` publishes a kernel of a newer Linux version than this
project's, `dnf upgrade` offers `@asahi`'s, which has none of this
project's changes. To stay on this project's kernels, give the COPR
repository a higher priority:

```sh
sudo dnf config-manager setopt "copr:copr.fedorainfracloud.org:aquarat:apple-silicon-kernel-plus.priority=10"
```

dnf then takes `kernel-16k` only from this repository.

## Rollback

Kernels are install-only: the previous ones stay installed and are listed
in the boot menu. **But do not boot a 7.1 kernel while a 7.2 kernel from
this project is installed.** m1n1 gives the kernel the device trees in the
EFI partition's `m1n1/boot.bin`, and `update-m1n1` writes the device trees
of the newest installed kernel there. A 7.1 kernel booted with the 7.2
Asahi device trees hung in testing before the network came up (the likely
cause: the display controller's IOMMU cells changed in 7.2). So point `/boot/dtb` (what `update-m1n1` reads) at the 7.1
kernel's trees before you boot it:

```sh
sudo dnf copr disable aquarat/apple-silicon-kernel-plus
sudo dnf remove dkms-apple-avd apple-ave dkms-apple-ave mesa-honeykrisp-plus 'qemu-vmapple*' reims-vgpu-backend   # what you installed
dnf list --installed 'kernel-16k-core'          # is a stock (.asahi.fc44) kernel installed?
sudo dnf install kernel-16k-7.1.13-402.asahi.fc44   # if not (or another stock version)
K=7.1.13-402.asahi.fc44.aarch64+16k             # the stock kernel's release, as in /boot/vmlinuz-*
sudo ln -sfn "dtb-$K" /boot/dtb && sudo update-m1n1   # boot.bin now has the 7.1 device trees
sudo grubby --set-default "/boot/vmlinuz-$K"
sudo reboot
# after booting the stock kernel:
sudo dnf remove $(rpm -qa 'kernel-16k*' | grep '\.asahiwip\.')
sudo dnf remove $(rpm -qa 'kernel-16k*' | grep '\.asahi\.plus[0-9]')   # older kernels of this project, if any
sudo dnf distro-sync
```

If a 7.1 kernel was booted with the 7.2 device trees and hangs: the
previous image is kept as `m1n1/boot.bin.old` on the EFI partition. In
macOS recovery (hold the power button, Options, Terminal), mount the EFI
partition of the Asahi install (`diskutil list`, `diskutil mount diskXsY`)
and copy `boot.bin.old` over `boot.bin`.

Keeping 7.1 device trees on purpose: setting
`DTBS=/usr/lib/modules/<7.1 kernel>/dtb` in `/etc/sysconfig/update-m1n1`
makes every kernel boot with those trees, so 7.1 kernels stay safe to
boot. This project's 7.2 kernel booted with 7.1-based trees in testing (on
a headless machine), without Thunderbolt, which needs the 7.2 trees' nodes.

## Using the KVM patches (macOS guests)

Patch 0001 (PAuth VM-key context) is always active; it only affects guests
on Apple CPUs. Patch 0002 (emulation of MMIO loads/stores that fault without
an instruction syndrome, which macOS guests need because XNU accesses the
interrupt controller with such instructions) is **on by default** from the
7.2.11 kernel (it was off up to 7.1.13). Nothing needs installing or
setting; `qemu-vmapple-kvm-nisv` is retired.

Check: `cat /sys/module/kvm/parameters/emulate_nisv_ldst` prints `Y`.
On a stock kernel the file does not exist. To turn it off:
`kvm.emulate_nisv_ldst=0` on the kernel command line, or `echo N | sudo tee
/sys/module/kvm/parameters/emulate_nisv_ldst` until the next reboot. More
in [docs/kvm-macos-guests.md](docs/kvm-macos-guests.md).

## Firmware for the AVE encoder

No Apple firmware, and no data taken from Apple's files, is in this
repository or its packages. `apple-ave-fetch-firmware` makes the files on
your Mac from Apple's macOS 13.5 restore image (read in place with HTTP
range requests: about 0.5 MB, plus a 26 MB kernelcache unless the Asahi
installer left one on the EFI partition), a local IPSW or a directory, and
checks each against known sha256 values:
[packages/apple-ave/apple-ave-firmware.md](packages/apple-ave/apple-ave-firmware.md).

## Update policy

Short version ([docs/update-policy.md](docs/update-policy.md)):

- **kernel:** a pinned commit of the Asahi tree's `asahi-wip` branch,
  moved by hand after it has run on test machines. A daily job reports
  when `asahi-wip`, kernel.org's stable series or `@asahi` move, and starts
  the COPR build after a bump is merged. Stable and security fixes arrive
  only with such a bump.
- **dkms-apple-avd:** rebased when this project's kernel moves to a new
  kernel series; until then DKMS skips the new series and the in-tree
  driver is used.
- **mesa-honeykrisp-plus:** follows Fedora's Mesa version, by hand.
- **qemu-vmapple, reims-vgpu-backend, apple-ave:** follow their upstream
  repositories, by hand.

This is a best-effort project. There is no security support: the kernel
gets upstream fixes when its Asahi commit is moved.

## Building

```sh
scripts/build-srpms.sh                 # all SRPMs, in a Fedora 44 container (docker or podman)
scripts/build-srpms.sh apple-avd       # one
```

COPR builds the same SRPMs through `.copr/Makefile`. Maintainer guide:
[docs/maintainer-guide.md](docs/maintainer-guide.md); releases:
[docs/release-process.md](docs/release-process.md).

## Credits

- Anees Iqbal ([steelbrain](https://github.com/steelbrain)): the original
  macOS-on-Asahi-KVM work, the Linux PAuth VM-key patch that kernel patch
  0001 is a rebase of, and Reims, the paravirtual GPU in
  reims-vgpu-backend.
- The Asahi Linux contributors and the Fedora Asahi SIG: the kernel tree
  (including Sven Peter's Thunderbolt/USB4 series), the AVD driver, and the
  `@asahi` packages and configuration this project builds on. The Fedora
  kernel maintainers: `kernel.spec` and Fedora's kernel patches.
- The Mesa developers: the Asahi Vulkan driver.
- The QEMU developers: QEMU and its `vmapple` machine.

Details: [CREDITS.md](CREDITS.md).

## Licence

GPL-2.0-only ([LICENSE](LICENSE)) for this repository's own files. The
packages contain other projects' code under their licences:
[LICENSING.md](LICENSING.md).
