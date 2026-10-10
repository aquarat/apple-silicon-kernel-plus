# Licensing

This repository is licensed under the GNU General Public License, version 2
only (`GPL-2.0-only`); the full text is in [LICENSE](LICENSE). That covers
the scripts, specs, configuration and documentation written for this
project. The packages contain other projects' code under their own licences;
this file lists them.

Our scripts carry `SPDX-License-Identifier: GPL-2.0-only` headers.

## Per package

| package | licence (RPM `License:` tag) | notes |
|---|---|---|
| kernel | `GPL-2.0-only` | Fedora Asahi Remix kernel; the `kernel.spec` tag is `@asahi`'s, unchanged |
| apple-avd | `GPL-2.0-only AND MIT AND BSD-2-Clause` | see below |
| apple-ave | `GPL-2.0-only` | all source files carry `GPL-2.0-only` |
| mesa-honeykrisp-plus | `MIT` | the Asahi Vulkan driver part of Mesa is MIT |
| qemu-vmapple | `GPL-2.0-only AND GPL-2.0-or-later AND LGPL-3.0-or-later AND` the crate licences | see below |

## Kernel patches

`packages/kernel/patches/*.patch` modify Linux and are distributed under
Linux's licence, `GPL-2.0-only`.

`0001-KVM-arm64-Apple-PAuth-virtualization-state.patch` is a rebase of a
Linux 6.19 patch by Anees Iqbal, published in
[steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64)
(commit `657bb24`, `patches/linux-6.19-vmapple-pac-vmkey.patch`). That
repository has no licence file. A change to Linux can only be distributed
under `GPL-2.0-only`, which is the licence it is offered under here. The
patch names him as its author (`From:`) and names its origin; it carries
no sign-off, as he has not given one. If he
objects to its distribution, the patch will be withdrawn.

`0002-KVM-arm64-emulate-MMIO-ldst-without-ISV.patch` is this project's work.

## apple-avd

The driver is the Fedora Asahi kernel's `drivers/media/platform/apple/avd`:

| files | licence |
|---|---|
| `avd-hw.c`, `avd-inst.h`, `avd-regs.h` | MIT |
| `avd-av1-entropymode.c` | BSD-2-Clause (Alliance for Open Media; also subject to the AOM Patent License 1.0, as its header says) |
| all other driver files | GPL-2.0-only |
| `patches/*.patch`, `Makefile`, `Kbuild` | GPL-2.0-only |

## apple-ave

From [aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver),
`driver/` and `test/` (here `overlay/`). Every file carries
`SPDX-License-Identifier: GPL-2.0-only`.

The driver's register addresses, command layouts and other constants were
found by studying Apple's firmware and macOS driver, to make the encoder
usable from Linux (interoperability). The upstream repository documents how
each was found.

No Apple firmware is in this repository or in any package built from it.
Users extract it from their own Mac or from Apple's IPSW
([docs/apple-ave-firmware.md](docs/apple-ave-firmware.md)).

## mesa-honeykrisp-plus

Mesa is mostly MIT; the files built here (the Asahi Vulkan driver and the
shared code it links) are MIT. `packages/mesa-honeykrisp-plus/patches/*.patch`
are offered under MIT, Mesa's licence.

## qemu-vmapple

| part | licence, as stated by the project |
|---|---|
| QEMU ([aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu)) | `GPL-2.0-only` as a whole (its `LICENSE` file); many files are `GPL-2.0-or-later`, some are other GPL-compatible licences |
| Reims ([aquarat/reims-vgpu](https://github.com/aquarat/reims-vgpu)) | its `LICENSE` file and README say `LGPL-3.0-or-later`; its crates' `Cargo.toml` files say `GPL-2.0-or-later` |
| metal2vulkan ([aquarat/metal2vulkan](https://github.com/aquarat/metal2vulkan)), a Cargo git dependency of Reims | `LGPL-3.0-or-later` (`LICENSE`, `Cargo.toml` and README agree) |
| other Rust crates (vendored into the SRPM) | each crate's own licence, mostly `MIT OR Apache-2.0`; the SRPM's vendor tarball keeps every crate's licence files |

The Reims statements disagree with each other. QEMU's `LICENSE` says the
emulator as a whole is GPL version 2, and the Reims and metal2vulkan code is
linked into the same binary. These are the upstream projects' statements, reported as
found; resolving them is for those projects.

Until this is settled, this project does not distribute `qemu-vmapple`
binaries: the COPR does not build it. Build it locally from the source
package (`scripts/build-srpms.sh`, then `rpmbuild --rebuild`); a build for
your own machines is not a distribution. The planned fix is to run Reims
as a separate process that QEMU talks to over shared memory, so that the two
are no longer one binary.
