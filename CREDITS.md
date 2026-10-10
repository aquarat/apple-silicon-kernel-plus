# Credits

This project packages and patches other people's work.

## Kernel

- **Fedora Asahi SIG** and the **Asahi Linux contributors**: the Fedora
  Asahi Remix kernel, its spec and the `@asahi/kernel` COPR that this
  project rebuilds. This project changes only what `packages/kernel`
  describes.
- **Anees Iqbal** ([steelbrain](https://github.com/steelbrain)): the work in
  [steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64)
  that first ran macOS guests under KVM on Asahi Linux, including the Linux
  6.19 patch for Apple's PAuth virtualization state. Kernel patch 0001 is a
  rebase of that patch onto the Fedora Asahi 7.1 kernel; the code changes
  are his. The patch header carries `Originally-by: Anees Iqbal` and its
  origin.
- Kernel patch 0002 (no-syndrome MMIO emulation) is this project's work.

## apple-avd

The driver is the Asahi Linux AVD driver as Fedora's kernel ships it
(copyright the Asahi Linux contributors, Eileen Yoon and the authors named
in each file, which also include Collabora, Rockchip, Google, Samsung and
the Alliance for Open Media). This project adds four fixes.

## apple-ave

[aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver).
Its t8103 (M1) support is based on a port by GitHub user henriSchulz, as its
sources note.

## mesa-honeykrisp-plus

The Mesa developers, in particular the authors of the Asahi Vulkan driver
(Honeykrisp). This project adds two patches.

## qemu-vmapple

- The QEMU developers, including the `vmapple` machine in upstream QEMU.
- Reims, the paravirtual GPU, is
  [steelbrain-bot/reims-vgpu](https://github.com/steelbrain-bot/reims-vgpu)
  by Anees Iqbal and contributors; all credit for the device, its design and
  the Metal-to-Vulkan path goes to its authors. This project builds the
  forks [aquarat/reims-vgpu](https://github.com/aquarat/reims-vgpu),
  [aquarat/qemu-reims-vgpu](https://github.com/aquarat/qemu-reims-vgpu) and
  [aquarat/metal2vulkan](https://github.com/aquarat/metal2vulkan), which add
  what an Asahi Linux host needs.
- The authors of the Rust crates vendored into the SRPM; each crate's
  licence file names them.

## Firmware tooling

The AVE firmware extraction uses the AVE driver repository's tools,
[pyimg4](https://github.com/m1stadev/PyIMG4) and
[remotezip](https://github.com/gtsystem/python-remotezip).
