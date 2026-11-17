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

`0001-KVM-arm64-Handle-Apple-PAuth-virtualization-state-under-VHE.patch`,
`0002-KVM-arm64-emulate-MMIO-ldst-without-ISV.patch` and
`0003-net-atlantic-AQC113-Enable-list-filters-relative-to-.patch` are this
project's work.

Until 7.2.11 `plus3` (and 7.3.1 `plus2`), 0001 was a rebase of a patch by Anees Iqbal from
[steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64),
a repository that then had no licence. (On 2026-11-11 he released its
patches into the public domain, in
[a comment on its issue 1](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64/issues/1#issuecomment-6789795685).)
From 7.2.11 `plus4` (and 7.3.1 `plus3`) it is replaced by an
independent implementation, written from m1n1's register definitions
(`GPL-2.0-or-later`) and a functional specification by an implementer
without access to that patch. How it was written, the sources it used and
the two incidents in that process are in
[docs/kvm-pauth-provenance.md](docs/kvm-pauth-provenance.md).

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

The Reims source in the SRPM leaves out what is not Reims' own work or not
needed to build it: the README's screenshots of macOS (`assets/`) and the
tests' shader fixtures compiled with Apple's Metal toolchain (`*.metallib`,
`*.mtlb`, `air/`); the shader sources stay. The vendored crates are checked
as a whole: every crate in the SRPM, linked or not, must carry a licence
Fedora allows (`scripts/cargo-vendor-check.py`), and their prebuilt
binaries (Windows import libraries, wasm runtime objects, test DLLs, none
used on Linux) are removed.

The QEMU source in the qemu-vmapple SRPM has none of QEMU's prebuilt
firmware (`pc-bios/`: SeaBIOS, iPXE, EDK2, OpenBIOS, SLOF, U-Boot, OpenSBI,
device tree blobs and others), whose sources the SRPM does not carry. The
package installs none of them; vmapple boots the user's own AVPBooter, and
the one option ROM a guest needs links to Fedora's `ipxe-roms-qemu`.

## Provenance of the reverse-engineered parts

Three parts of these packages describe interfaces of Apple software that
are not documented:

- the **AVE encoder driver** (apple-ave): the encoder's registers, its
  firmware's boot handshake and command formats;
- the **`avp,rtc` clock** in qemu-vmapple (`hw/vmapple/avp-rtc.c` in
  [aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu)):
  the register layout of the clock Apple's Virtualization.framework gives
  macOS guests;
- **Reims' decoding of the paravirtual GPU's command stream** (the
  serializer wire format, reims-vgpu-backend): the layout of the records
  the guest's Metal driver writes.

They were written for interoperability, so that Linux can drive this
hardware and host these guests, from observation of the hardware and of
macOS (register state, the bytes Apple's serializer produces) and from
disassembly of Apple's firmware and drivers. No Apple code and no Apple
data tables are copied into them: they contain interface facts, such as
constants, register offsets and bit layouts, command and record formats,
each stated in this project's own code. Data that is more than that (the
AVE firmware itself, its register tunables, boot-loader data) is not in
any package; users make it on their own Mac from their own copy
([apple-ave](#apple-ave)). How the AVE facts were found, and an item-by-item
inventory of everything taken from Apple's files with the reason each is
an interface fact, are in the AVE repository's
[docs/00-methodology.md](https://github.com/aquarat/apple-m-series-ave-driver/blob/main/docs/00-methodology.md)
and
[docs/100-no-apple-data.md](https://github.com/aquarat/apple-m-series-ave-driver/blob/main/docs/100-no-apple-data.md).
That inventory lists one item as less clear-cut: about fifty individual
protocol field values that a macOS 13.5 encoding session sends
(`ave_macos_*_13_5` in `ave_abi.h`), applied only when the
`session_macos` module parameter asks for them (off by default). The
clock's register layout is described in the header of `avp-rtc.c`; Reims'
approach is in its `crates/reims-vgpu-wire/README.md`.

This is not how Asahi Linux works. Asahi Linux's
[copyright and reverse-engineering policy](https://asahilinux.org/copyright/)
does not accept code developed alongside disassembly or decompilation of
Apple binaries (except from specific trusted contributors), and asks
others for a clean-room process; this project did not follow that process
for these parts. This project is not affiliated with or endorsed by Asahi
Linux, and these parts are not Asahi Linux code.
