# apple-silicon-kernel-plus

RPM packages for Fedora Asahi Remix on Apple silicon Macs: the Fedora Asahi
kernel with two KVM patches for macOS guests, video decoder and encoder
drivers, a patched Vulkan driver, and QEMU for macOS guests. COPR builds and
hosts the packages; GitHub Actions checks them and starts the builds.

**Unofficial.** This project is not affiliated with or endorsed by Asahi
Linux, Fedora or Apple. Do not report bugs from these packages to Asahi
Linux or Fedora; report them here.

## Packages

| package | what | status |
|---|---|---|
| `kernel` (`kernel-16k-*`) | The `@asahi/kernel` COPR's kernel, 16k variant, rebuilt with two KVM patches: Apple PAuth VM-key context (on), and emulation of MMIO loads/stores without a syndrome (**off by default**). [packages/kernel](packages/kernel) | stable |
| `dkms-apple-avd` | The Asahi AVD video decoder driver with four fixes for long-running streams, built by DKMS. [packages/apple-avd](packages/apple-avd) | stable |
| `apple-ave`, `dkms-apple-ave` | A V4L2 H.264/HEVC encoder driver for the AVE block, reverse engineered. No firmware included. [packages/apple-ave](packages/apple-ave) | **experimental** |
| `mesa-honeykrisp-plus` | Mesa's Asahi Vulkan driver (Honeykrisp) with two shader compiler fixes, installed beside the system Mesa and used only through `VK_DRIVER_FILES`. Patch 0002 is still being validated. [packages/mesa-honeykrisp-plus](packages/mesa-honeykrisp-plus) | stable (0002: in validation) |
| `qemu-vmapple`, `qemu-vmapple-kvm-nisv` | QEMU with the `vmapple` machine and the Reims paravirtual GPU, installed beside Fedora's qemu; and an opt-in package that turns on the kernel's no-syndrome MMIO emulation. [packages/qemu-vmapple](packages/qemu-vmapple) | stable |

## Supported hardware

As the sources state; "tested" means on at least one machine of that SoC.

| package | SoCs |
|---|---|
| kernel | what the `@asahi` kernel supports (M1 and M2 families). The KVM patches act only on CPUs with Apple's ACTLR virtualization (M1: t8103, t6000, t6001, t6002; M2: t8112, t6020, t6021, t6022); tested on t6001 |
| dkms-apple-avd | M1 family (t8103, t6000, t6001, t6002); t8112: H.264 works, HEVC times out (open) |
| apple-ave | t6000, t8103 (H.264 without B frames), t8112; t6001 and t6002 only after per-machine preparation. All with the macOS 13.5 system firmware |
| mesa-honeykrisp-plus | M1 and M2 GPUs, as Mesa's Asahi driver |
| qemu-vmapple | hosts that run the kernel above; macOS 13 and 26 guests used on t6001 and t6002 hosts |

## Install

The COPR project is `aquarat/apple-silicon-kernel-plus` (it may not exist
yet; this line is a placeholder until it does).

```sh
sudo dnf copr enable aquarat/apple-silicon-kernel-plus
sudo dnf upgrade                      # moves you to this project's kernel (see below)
sudo dnf install dkms-apple-avd       # and/or: apple-ave, mesa-honeykrisp-plus, qemu-vmapple
```

DKMS packages need `kernel-16k-devel` for each installed kernel.

**Enabling this COPR moves you to this project's kernel.** For the same
`@asahi` release, this project's kernel sorts as newer than the stock one,
so `dnf upgrade` installs it and makes it the default boot entry. That is
intended. See [Kernel release naming](#kernel-release-naming).

## Kernel release naming

The kernel keeps `@asahi`'s version and release and adds a build id,
`.plus<N>`, before the dist tag:

| | release | `uname -r` |
|---|---|---|
| stock `@asahi` | `7.1.13-402.asahi.fc44` | `7.1.13-402.asahi.fc44.aarch64+16k` |
| this project | `7.1.13-402.asahi.plus1.fc44` | `7.1.13-402.asahi.plus1.fc44.aarch64+16k` |

rpm compares the release segment by segment: `402` = `402`, `asahi` =
`asahi`, then `plus` against `fc`; letters compare as strings, and `plus` >
`fc`. So:

- `7.1.13-402.asahi.plus1.fc44` is **newer** than `7.1.13-402.asahi.fc44`;
- the next `@asahi` release, e.g. `7.1.13-403.asahi.fc44`, is **newer** than
  `7.1.13-402.asahi.plus1.fc44` (403 > 402), until this project rebuilds it as
  `7.1.13-403.asahi.plus1.fc44`;
- `plus2` replaces `plus1` when only this project's patches change.

(A build id such as `.askp1` would sort *older* than the stock kernel,
because `a` < `f`.)

Between an `@asahi` release and this project's rebuild of it (normally
within a day, plus the COPR build time), `dnf upgrade` installs the stock
kernel, which has no KVM patches. To stay on this project's kernels instead,
give the COPR repository a higher priority:

```sh
sudo dnf config-manager setopt "copr:copr.fedorainfracloud.org:aquarat:apple-silicon-kernel-plus.priority=10"
```

dnf then takes `kernel-16k` only from this repository.

## Rollback

Kernels are install-only: the previous ones stay installed and bootable.

```sh
sudo dnf copr disable aquarat/apple-silicon-kernel-plus
sudo dnf remove dkms-apple-avd apple-ave dkms-apple-ave mesa-honeykrisp-plus 'qemu-vmapple*'   # what you installed
sudo dnf distro-sync
dnf list --installed 'kernel-16k-core'          # is a stock (.asahi.fc44) kernel installed?
sudo dnf install kernel-16k-<version>-<release>.asahi.fc44   # if not, e.g. 7.1.13-402.asahi.fc44
sudo grubby --set-default /boot/vmlinuz-<stock kernel release>+16k
sudo reboot
# after booting the stock kernel:
sudo dnf remove $(rpm -qa 'kernel-16k*' | grep '\.plus[0-9]')
```

## Using the KVM patches (macOS guests)

Patch 0001 (PAuth VM-key context) is always active; it only affects guests
on Apple CPUs. Patch 0002 (emulation of MMIO loads/stores that fault without
an instruction syndrome) is **off by default**. macOS guests need it on,
because XNU accesses the interrupt controller with such instructions.

KVM is built into the kernel, so `/etc/modprobe.d` options do not apply.
Turn it on in one of these ways:

```sh
sudo dnf install qemu-vmapple-kvm-nisv             # tmpfiles.d rule: on at every boot
# or, kernel command line:
sudo grubby --update-kernel=ALL --args=kvm.emulate_nisv_ldst=1
# or, until the next reboot:
echo Y | sudo tee /sys/module/kvm/parameters/emulate_nisv_ldst
```

Check: `cat /sys/module/kvm/parameters/emulate_nisv_ldst` prints `Y`.
On a stock kernel the file does not exist. More in
[docs/kvm-macos-guests.md](docs/kvm-macos-guests.md).

## Firmware for the AVE encoder

No Apple firmware is in this repository or its packages. Each user extracts
it for their own Mac from Apple's macOS 13.5 IPSW, with the tools of the
AVE driver repository, and installs it with `install-firmware`, which checks
each file's sha256: [docs/apple-ave-firmware.md](docs/apple-ave-firmware.md).

## Update policy

Short version ([docs/update-policy.md](docs/update-policy.md)):

- **kernel:** follows `@asahi`. A daily job notices a new `@asahi` kernel,
  checks that the patches apply and starts a COPR build. If they do not
  apply, there is no build until the patches are rebased.
- **dkms-apple-avd:** rebased when `@asahi` moves to a new kernel series; until
  then DKMS skips the new series and the in-tree driver is used.
- **mesa-honeykrisp-plus:** follows Fedora's Mesa version, by hand.
- **qemu-vmapple, apple-ave:** follow their upstream repositories, by hand.

This is a best-effort project. There is no security support beyond rebuilding
`@asahi`'s kernels.

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
  0001 is a rebase of, and Reims, the paravirtual GPU in qemu-vmapple.
- The Asahi Linux contributors and the Fedora Asahi SIG: the kernel, the AVD
  driver and the `@asahi` packages this project builds on.
- The Mesa developers: the Asahi Vulkan driver.
- The QEMU developers: QEMU and its `vmapple` machine.

Details: [CREDITS.md](CREDITS.md).

## Licence

GPL-2.0-only ([LICENSE](LICENSE)) for this repository's own files. The
packages contain other projects' code under their licences:
[LICENSING.md](LICENSING.md).
