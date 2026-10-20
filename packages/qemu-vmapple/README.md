# qemu-vmapple

QEMU with the `vmapple` machine, for macOS guests under KVM on Apple silicon
Linux hosts. The paravirtual GPU runs out of process: QEMU's
`apv-gpu-proxy` device forwards it to `reims-vgpu-backend`
([packages/reims-vgpu-backend](../reims-vgpu-backend)), a separate program
in its own package. This QEMU contains no Reims, metal2vulkan, Rust or
Vulkan code and loads none.

| | |
|---|---|
| binary | `/usr/libexec/qemu-vmapple/qemu-system-aarch64`, also `/usr/bin/qemu-vmapple` |
| data | `/usr/share/qemu-vmapple`: keymaps, and `efi-virtio.rom` (virtio-net's option ROM), a link to Fedora's iPXE build (`ipxe-roms-qemu`). No other firmware: vmapple boots your AVPBooter |
| source | [aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu) at `qemu_commit` |
| configuration | `aarch64-softmmu`, KVM, GTK, GnuTLS, slirp, no Rust; as `MODE=oop scripts/build-qemu.sh` in [apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest) |
| GPU | `-M vmapple,gfx-device=apv-gpu-proxy`, served by `reims-vgpu-backend` (recommended by this package) |

It does not conflict with Fedora's `qemu-*` packages: it owns only the paths
above.

## What else a macOS guest needs

1. The kernel from this project (`kernel-16k-…plus…`), for the PAuth
   VM-key context.
2. The no-syndrome MMIO emulation turned on. It is on by default in this
   project's kernel from 7.2.11; on an older 7.1.x kernel from this
   project, see [docs/kvm-macos-guests.md](../../docs/kvm-macos-guests.md).
   `qemu-vmapple-kvm-nisv`, which used to turn it on, is retired: it is
   now an empty package (see below).
3. For the GPU: `reims-vgpu-backend`, and a Vulkan driver that handles the
   shaders it produces, i.e. `mesa-honeykrisp-plus`, selected with
   `VK_DRIVER_FILES` in the backend's environment. Without the GPU
   (`gfx-device=none`) neither is needed.
4. A macOS installation (restore image, AVPBooter, auxiliary storage). The
   VM tooling in apple-macos-arm64-vm-guest makes and runs those. This
   package contains no macOS software or Apple firmware.

## Running a guest with the GPU

The two programs must speak the same apv-gpu-proxy protocol version: this
package recommends `apv-gpu-proxy-backend = <version>`, which
`reims-vgpu-backend` provides. Guest RAM must be a shared memfd, so the
backend can map it.

With the VM tooling (what the production runners do), point its
variables at the packaged programs:

```sh
# scripts/vm-run.sh / launch-kvm.sh
export QEMU_BIN=/usr/libexec/qemu-vmapple/qemu-system-aarch64
export GPU_BACKEND_BIN=/usr/libexec/qemu-vmapple/reims-vgpu-backend
export $(honeykrisp-plus)                # VK_DRIVER_FILES: mesa-honeykrisp-plus's ICD file

# runner host profile (forgejo-ephemeral-runner.sh): GPU slots
GPU_OOP_QEMU_BIN=/usr/libexec/qemu-vmapple/qemu-system-aarch64
GPU_BACKEND_BIN=/usr/libexec/qemu-vmapple/reims-vgpu-backend
```

`launch-kvm.sh` then starts the backend on a socket, supervises it (its
log is `gpu-backend.log` beside QEMU's), and starts QEMU with
`gfx-device=apv-gpu-proxy`; `vm-run.sh` gives both a persistent `TMPDIR`,
`~/.cache/reims-vgpu`, where Reims keeps its Vulkan pipeline cache.
Unsetting `GPU_BACKEND_BIN` alone is the runners' fallback to an
in-process QEMU, which this package no longer is.

By hand, the same thing:

```sh
mkdir -p ~/.cache/reims-vgpu
sock=$XDG_RUNTIME_DIR/vm1.gpu            # a unix socket path: at most 107 bytes
TMPDIR=~/.cache/reims-vgpu honeykrisp-plus \
    reims-vgpu-backend --socket "$sock" >> gpu-backend.log 2>&1 &
qemu-vmapple -cpu host -smp 8 -m 16G \
    -object memory-backend-memfd,id=ram,size=16G,share=on \
    -machine vmapple,uuid=<ECID>,accel=kvm,memory-backend=ram,gfx-device=apv-gpu-proxy,aux-ram-share=on \
    -global apv-gpu-proxy.socket="$sock" \
    -global apv-gpu-proxy.on-backend-loss=stop \
    ...                                   # -bios, disks, network: see launch-kvm.sh
```

The backend serves one QEMU and exits when that QEMU goes away; start one
backend per guest. If it dies (a host GPU driver crash, say), QEMU stops
the guest and prints `apv-gpu-proxy: GPU backend lost: <reason>`;
`on-backend-loss=reset` instead resets the guest onto a new backend
listening on the same socket, and `shutdown` powers it off. Other
settings (`REIMS_VGPU_MAX_REFRESH_HZ`, default 60, or `--max-refresh-hz`;
`REIMS_VGPU_FRAME_PACING`) are in
[packages/reims-vgpu-backend](../reims-vgpu-backend/README.md).

## qemu-vmapple-kvm-nisv (retired)

Up to release 1 this subpackage installed a tmpfiles.d rule that wrote `Y`
to `/sys/module/kvm/parameters/emulate_nisv_ldst` at boot, and its removal
script wrote `N`. From release 2 it is empty and has no scriptlets: the
kernel turns the emulation on by itself. It is kept rather than obsoleted,
because removing the old package (which an `Obsoletes:` does) runs its
removal script and switches the emulation off on the running kernel until
the next boot; upgrading to the empty package does not. Remove it whenever
you like. A later release may drop it with `Obsoletes:` once nobody has the
old version.

## Sources in the SRPM

COPR builds may not have network access, so `scripts/make-srpm.sh
qemu-vmapple` puts everything into the SRPM:

- `qemu-reims-vgpu-<commit>.tar.xz`: QEMU (no `.git`), with QEMU's meson
  subprojects `keycodemapdb`, `berkeley-softfloat-3` and
  `berkeley-testfloat-3` downloaded. `dtc` and `slirp` come from Fedora.

The build runs QEMU's configure with `--disable-download` and
`--disable-rust`. `make-srpm.sh` refuses a QEMU commit that has no
`apv-gpu-proxy` device or still has the in-process Reims device or its
cargo build, and checks the spec's `apv_protocol` against the protocol
header; the spec's `%check` checks the built binary (no Reims or Rust
symbols, no Vulkan loader).

## Updating

Set `qemu_commit` (full id), `qemu_date` (its commit date, YYYYMMDD),
`qemu_version` (QEMU's `VERSION`; `make-srpm.sh` checks it) and, if the
protocol header changed, `apv_protocol` (here and in
`reims-vgpu-backend.spec`; bump both packages together) in the spec, add a
changelog entry, rebuild. docs/maintainer-guide.md has the steps.

## Licences

QEMU is GPL version 2 as a whole, with per-file licences that are
compatible with it (mostly GPL-2.0-or-later). `apv-gpu-proxy.c` is
GPL-2.0-or-later and its protocol header MIT, both written for this fork.
Reims and metal2vulkan are not in this package. See `LICENSING.md`.
