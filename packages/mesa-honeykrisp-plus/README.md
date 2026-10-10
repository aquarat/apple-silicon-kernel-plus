# mesa-honeykrisp-plus

Mesa's Vulkan driver for Apple M1/M2 GPUs (Honeykrisp, `libvulkan_asahi.so`)
with this project's patches. It is a parallel install: it does not replace
the system Mesa, and nothing uses it unless asked to.

| path | what |
|---|---|
| `/usr/lib64/apple-silicon-kernel-plus/mesa/lib/libvulkan_asahi.so` | the driver |
| `/usr/lib64/apple-silicon-kernel-plus/mesa/share/vulkan/icd.d/asahi_icd.aarch64.json` | its ICD file, outside `/usr/share/vulkan/icd.d` |
| `/usr/bin/honeykrisp-plus` | runs a command with `VK_DRIVER_FILES` set to that ICD file |

```sh
honeykrisp-plus vulkaninfo --summary     # one command
honeykrisp-plus                          # prints VK_DRIVER_FILES=...
```

For QEMU with the Reims GPU (qemu-vmapple), set the same `VK_DRIVER_FILES`
in the environment of the QEMU process.

## Patches

| patch | status |
|---|---|
| 0001 asahi: widen 16-bit varyings before st_vary | in use with macOS guests |
| 0002 asahi: narrow 16-bit flat fragment inputs from their 32-bit coefficients | **still being validated** |

Both fix crashes in the shader compiler on 16-bit varyings, which shaders
translated from Metal use. Without them, the compiler aborts the process
that builds the pipeline (QEMU and its guest).

## Build

- Mesa version: the one Fedora ships as `mesa-vulkan-drivers` for the
  target release (26.2.4 for Fedora 44), so the kernel interface and system
  libraries match. `sha256sums` pins the tarball.
- Options: as `scripts/build-mesa-honeykrisp.sh` in
  [apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest):
  Vulkan `asahi` only, no Gallium, no window systems (`-Dplatforms=`), LLVM
  on. Rendering is off-screen; there are no X11 or Wayland surfaces.

When Fedora updates Mesa, update `Version` and `sha256sums` and rebuild
(docs/maintainer-guide.md).
