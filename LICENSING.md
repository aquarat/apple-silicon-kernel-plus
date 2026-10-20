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
| kernel | `GPL-2.0-only` | the Asahi Linux kernel tree with Fedora's kernel patch; the `License:` tag is that of Fedora's `kernel.spec`, unchanged |
| apple-avd | `GPL-2.0-only AND MIT AND BSD-2-Clause` | see below |
| apple-ave | `GPL-2.0-only` | all source files carry `GPL-2.0-only` |
| mesa-honeykrisp-plus | `MIT` | the Asahi Vulkan driver part of Mesa is MIT |
| qemu-vmapple | `GPL-2.0-only AND GPL-2.0-or-later AND LGPL-2.1-or-later AND MIT AND BSD-2-Clause AND BSD-3-Clause` | QEMU only; see below |
| reims-vgpu-backend | `LGPL-3.0-or-later AND GPL-2.0-or-later AND Apache-2.0 AND` the other crate licences | Reims, metal2vulkan and Rust crates; see below |

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

`0002-KVM-arm64-emulate-MMIO-ldst-without-ISV.patch` and
`0003-net-atlantic-atl2-keep-station-MAC-uc-filter-enabled.patch` are this
project's work.

## apple-avd

The driver is the Asahi Linux kernel tree's `drivers/media/platform/apple/avd`, as this project's kernel ships it:

| files | licence |
|---|---|
| `avd-hw.c`, `avd-inst.h`, `avd-regs.h` | MIT |
| `avd-av1-entropymode.c` | BSD-2-Clause (Alliance for Open Media; also subject to the AOM Patent License 1.0, as its header says) |
| all other driver files | GPL-2.0-only |
| `patches/*.patch`, `Makefile`, `Kbuild` | GPL-2.0-only |

## apple-ave

From [aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver):
`driver/`, `test/` (here `overlay/`) and `tools/ave_fwgen.py` (here
`firmware/ave_fwgen.py`). Every file carries
`SPDX-License-Identifier: GPL-2.0-only`, as do this project's
`apple-ave-fetch-firmware`, `ave-load`, `install-firmware` and tests.

The driver's register addresses, command layouts and other interface facts
were found by studying Apple's firmware and macOS driver, to make the
encoder usable from Linux (interoperability). The upstream repository
documents how each was found, and its docs/100 lists every item derived
from Apple's files and why it is a fact rather than copied data.

No Apple firmware and no data taken from Apple's files (firmware images,
register tables, boot-loader data) is in this repository or in any package
built from it. Users make those files on their own Mac from Apple's
restore image or their own copy of it
([packages/apple-ave/apple-ave-firmware.md](packages/apple-ave/apple-ave-firmware.md)).
`known-hashes.txt` holds only sha256 values and sizes, to verify them.

At run time `apple-ave-fetch-firmware` uses the `lzfse` command (Apple's
reference LZFSE implementation, `BSD-3-Clause`, Fedora's `lzfse` package)
to decompress the kernelcache; it is a separate program, not linked.

## mesa-honeykrisp-plus

Mesa is mostly MIT; the files built here (the Asahi Vulkan driver and the
shared code it links) are MIT. `packages/mesa-honeykrisp-plus/patches/*.patch`
are offered under MIT, Mesa's licence.

## qemu-vmapple and reims-vgpu-backend

The paravirtual GPU runs out of process: QEMU and Reims are two programs in
two packages.

| package | part | licence, as stated by the project |
|---|---|---|
| qemu-vmapple | QEMU ([aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu)) | `GPL-2.0-only` as a whole (its `LICENSE` file); source files carry their own GPL-2.0-compatible licences, mostly `GPL-2.0-or-later`; the linked `berkeley-softfloat-3` is `BSD-3-Clause` |
| qemu-vmapple | `hw/display/apv-gpu-proxy.c`, the GPU proxy device (written for the fork) | `GPL-2.0-or-later` |
| both | `apv-gpu-proxy-protocol.h`, the protocol between the two (in both trees, identical) | `MIT` |
| reims-vgpu-backend | Reims ([aquarat/reims-vgpu](https://github.com/aquarat/reims-vgpu)) | its `LICENSE` file, README and the backend crate's `Cargo.toml` say `LGPL-3.0-or-later`; its other crates' `Cargo.toml` files say `GPL-2.0-or-later` |
| reims-vgpu-backend | metal2vulkan ([aquarat/metal2vulkan](https://github.com/aquarat/metal2vulkan)), a Cargo git dependency of Reims | `LGPL-3.0-or-later` (`LICENSE`, `Cargo.toml` and README agree) |
| reims-vgpu-backend | other Rust crates (vendored into the SRPM, statically linked) | each crate's own licence: mostly `MIT OR Apache-2.0`; `Apache-2.0` only (winit, spirv, ab_glyph and others), `BSD-3-Clause`, `BSD-2-Clause`, `ISC`. The package lists each in `LICENSE.dependencies` and carries their licence files |

**qemu-vmapple** contains no Reims, metal2vulkan, Rust or Vulkan code and
loads none: its build has no cargo step and includes no Reims header, and
the binary does not link or open the Vulkan loader. `make-srpm.sh` refuses
a QEMU commit that still has the in-process Reims device or its cargo glue,
and the spec's `%check` fails on Reims or Rust symbols, or a Vulkan
library, in the built binary. Everything in it is GPL-2.0-compatible, so
it is distributable under QEMU's licence.

**reims-vgpu-backend** contains no QEMU code. The licences in it are
compatible with each other: GPL-2.0-or-later code may be used under GPL
version 3, which LGPL-3.0-or-later code and the Apache-2.0, BSD, ISC and
MIT crates can be combined with, so the binary as a whole is distributable
under GPL-3.0-or-later terms. Which of its two statements Reims intends
(LGPL-3.0-or-later or GPL-2.0-or-later) no longer matters for distribution:
either way the combination works. `make-srpm.sh` refuses a crate whose
licence is not in the spec's `License` tag.

**The two programs** run as separate processes and talk through a unix
socket, eventfds and shared memory (the guest RAM, a register page, a
posted-write ring) over a small, versioned, published interface: register
windows, a memory table and events, described by the MIT header. Neither
links the other or shares its internal data structures. This is the
arrangement QEMU uses with vhost-user and vfio-user device backends under
other licences.

Earlier releases of qemu-vmapple linked Reims and metal2vulkan into the
QEMU binary, which combined GPL-2.0-only code with LGPL-3.0 code (and
Apache-2.0-only crates) in one program; that is why they were not
distributed. With the split this conflict is gone, and the COPR builds both
packages. This is this project's reading of the licences, not legal advice;
if an upstream project disagrees, the packages will be withdrawn.

The Reims source in the SRPM also has its tests' small shader fixtures,
compiled from Reims' own shader sources; they are not built into the
package.
