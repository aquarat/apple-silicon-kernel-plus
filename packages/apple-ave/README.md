# apple-ave (EXPERIMENTAL)

A V4L2 stateful encoder driver for the Apple Video Encoder (AVE) block of
M1 and M2 SoCs: NV12 or P010 in, H.264 (Baseline, Main, High) or HEVC
(Main, Main 10) out. ffmpeg uses it through `h264_v4l2m2m` and
`hevc_v4l2m2m`, GStreamer through `v4l2h264enc` and `v4l2h265enc`.

**This package is experimental.** The driver was written by reverse
engineering, for interoperability: its register layouts, command formats
and other constants were found by studying Apple's firmware and macOS
driver. It has run on a few machines only. A driver bug can hang the
encoder or the machine. Do not use it where that matters.

Upstream: [aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver),
commit `b0af15e`. Its `docs/` describe how each part was found and tested.

## Packages

| package | contents |
|---|---|
| `dkms-apple-ave` | the sources DKMS builds: `apple-ave` (the driver) and `ave-overlay` (adds the encoder to the device tree at run time; Fedora's device trees have no AVE node); a modprobe.d rule that lets only `ave-load` load the overlay |
| `apple-ave` | `apple-ave.service` and `ave-load` (loads the SoC's overlay, then the driver), `install-firmware`, `known-hashes.txt` |

The upstream repository's read-only diagnostic modules are not included.

## Supported SoCs

All with the macOS 13.5 system firmware (the Asahi installer's default).

| SoC | encoders | state |
|---|---|---|
| t6000 M1 Pro | 1 | works upstream; loaded by default |
| t8103 M1 | 1 | works upstream; H.264 limited to I and P frames (B frames hang the firmware on this SoC); loaded by default |
| t8112 M2 | 1 | works upstream; loaded by default |
| t6001 M1 Max | 2 | needs m1n1 support or a driver change first; loaded only if `/etc/apple-ave/allow-t6001` exists |
| t6002 M1 Ultra | 4 | the driver carries one machine's firmware placement; loaded (first encoder only) only if `/etc/apple-ave/allow-t6002` exists |
| others (M2 Pro/Max/Ultra, M3 and later) | | not ported |

Without the power-management coprocessor (PMP) the encoder runs at its boot
clock. On t6000 that is about a third of the speed macOS gets; this project
does not change device trees to enable the PMP.

## Setup

1. Install: `sudo dnf install apple-ave` (pulls in `dkms-apple-ave`, and
   needs `kernel-16k-devel` for each kernel).
2. Make and install the firmware files for your Mac:
   [docs/apple-ave-firmware.md](../../docs/apple-ave-firmware.md).
3. `sudo systemctl enable --now apple-ave.service`
4. `/usr/libexec/apple-ave/ave-load status` lists the encoder nodes
   (`apple-ave-enc` on `/dev/videoN`).

To stop using it: `sudo systemctl disable apple-ave.service` and reboot
(the overlay cannot be removed from a running kernel).

## Example

```sh
ffmpeg -i in.mp4 -c:v hevc_v4l2m2m -b:v 8M -c:a copy out.mp4
```

Stock ffmpeg's V4L2 encoders have limits (no fixed QP, no B frames); the
upstream repository's `ffmpeg/` directory has patches.
