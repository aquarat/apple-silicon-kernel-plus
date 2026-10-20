# reims-vgpu-backend

Reims, the paravirtual GPU of macOS guests, as its own program. QEMU's
`apv-gpu-proxy` device ([packages/qemu-vmapple](../qemu-vmapple)) connects
to it over a unix socket and hands it the guest RAM (a shared memfd) and
eventfds; it runs the guest's Metal work on the host's Vulkan driver, with
metal2vulkan translating the shaders. A crash in the host GPU driver ends
only this process: QEMU stops the guest with the reason.

| | |
|---|---|
| binary | `/usr/libexec/qemu-vmapple/reims-vgpu-backend`, also `/usr/bin/reims-vgpu-backend` |
| source | [aquarat/reims-vgpu](https://github.com/aquarat/reims-vgpu) at `reims_commit` (steelbrain-bot/reims-vgpu with the Asahi host changes), with [aquarat/metal2vulkan](https://github.com/aquarat/metal2vulkan) at the commit its `Cargo.lock` pins |
| build | `cargo build --release -p reims-vgpu-backend` (default features), as `MODE=oop scripts/build-qemu.sh` in [apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest) |
| provides | `apv-gpu-proxy-backend = <protocol version>`, which `qemu-vmapple` recommends |
| runtime | the Vulkan loader; `mesa-honeykrisp-plus` (recommended) as the driver |

It contains no QEMU code; the two programs share only the protocol header
(MIT, in both trees).

## Use

```text
reims-vgpu-backend --socket PATH [--max-refresh-hz HZ] [--frame-pacing on|off]
reims-vgpu-backend --listen-fd N            an already listening socket
reims-vgpu-backend --fold-breadcrumbs       after an instance died: quarantine the driver call it left
```

One backend serves one QEMU (one guest) and exits when that QEMU goes
away. Start it before QEMU; the socket path must fit a unix socket address
(107 bytes). [packages/qemu-vmapple](../qemu-vmapple/README.md#running-a-guest-with-the-gpu)
has the QEMU side, both by hand and through the VM tooling's
`GPU_BACKEND_BIN`.

Environment, as the production runners set it:

| variable | |
|---|---|
| `VK_DRIVER_FILES` | the Vulkan driver: `mesa-honeykrisp-plus` (`honeykrisp-plus reims-vgpu-backend ...`). Stock Honeykrisp aborts on shaders macOS 26 guests use; llvmpipe draws the desktop but not the iOS simulator |
| `TMPDIR` | where Reims keeps its Vulkan pipeline cache and translation scratch directories: use a persistent one, `~/.cache/reims-vgpu`, or every host boot recompiles every pipeline |
| `REIMS_VGPU_MAX_REFRESH_HZ` | the display's refresh-rate cap (default 60; 0 = the native 120); `--max-refresh-hz` |
| `REIMS_VGPU_FRAME_PACING` | `on` also paces guest surfaces to that cap (default off: it costs UI-test time) |
| `REIMS_VGPU_FAIL_LOG`, `REIMS_VGPU_DRAW_LOG_PATH` | the failure log (a named path is capped at 64 MiB) and the verbose draw log (`off`) |
| `REIMS_VGPU_BREADCRUMB_DIR` | where a driver call in flight leaves its breadcrumb; `--fold-breadcrumbs` moves one a dead backend left into the host's driver quarantine (`REIMS_VGPU_QUARANTINE_DIR`, default `$XDG_STATE_HOME/reims-vgpu`, i.e. `~/.local/state/reims-vgpu`), so later runs refuse that call until the driver changes |

## Sources in the SRPM

`scripts/make-srpm.sh reims-vgpu-backend` puts everything into the SRPM, so
the build runs offline (`cargo build --frozen`):

- `reims-vgpu-<commit>.tar.xz`: Reims (no `.git`, without the `vendor/qemu`
  submodule, which only the in-process build uses).
- `reims-vgpu-<commit>-vendor.tar.xz`: `cargo vendor` of Reims'
  `Cargo.lock`, including the git dependency metal2vulkan, and the
  source-replacement config that points cargo at it.

It also fills in the spec's `Provides: bundled(crate(...))` from
`cargo tree` (the crates linked into the binary), refuses a crate whose
licence is not in the spec's `License` tag, and checks the spec's
`apv_protocol` against the protocol header. The package carries
`LICENSE.dependencies` (each linked crate and its licence) and the crates'
licence files.

## Updating

Set `reims_commit` (full id), `reims_date` (its commit date, YYYYMMDD) and
`crate_version` (the backend crate's version) in the spec, and
`apv_protocol` if the protocol header changed (then in
`qemu-vmapple.spec` too, bumping both together); add a changelog entry,
rebuild. docs/maintainer-guide.md has the steps.

## Licences

Reims states LGPL-3.0-or-later in its `LICENSE`, README and the backend
crate's `Cargo.toml`, and GPL-2.0-or-later in its other crates'
`Cargo.toml`. metal2vulkan is LGPL-3.0-or-later; the protocol crate MIT;
the other linked crates mostly MIT OR Apache-2.0, some Apache-2.0 only,
BSD or ISC. See `LICENSING.md`.
