# apple-ave (EXPERIMENTAL)

A V4L2 stateful encoder driver for the Apple Video Encoder (AVE) block of
M1 and M2 SoCs: NV12 or P010 in, H.264 (Baseline, Main, High) or HEVC
(Main, Main 10) out. ffmpeg uses it through `h264_v4l2m2m` and
`hevc_v4l2m2m`, GStreamer through `v4l2h264enc` and `v4l2h265enc`.

**This package is experimental.** The driver was written by reverse
engineering, for interoperability: its register layouts and command formats
were found by studying Apple's firmware and macOS driver. A driver bug can
hang the encoder or the machine. Do not use it where that matters. Why it
is still experimental, per SoC, and what would change that: [Status](#status).

Upstream: [aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver),
commit `057c5df`. Its `docs/` describe how each part was found and tested.

## Packages

| package | contents |
|---|---|
| `dkms-apple-ave` | the sources DKMS builds: `apple-ave` (the driver) and `ave-overlay` (adds the encoder to the device tree at run time; Fedora's device trees have no AVE node); a modprobe.d rule that lets only `ave-load` load the overlay. The build needs no Apple data |
| `apple-ave` | `apple-ave-fetch-firmware` (makes and verifies the firmware files), `apple-ave.service` and `ave-load` (load the SoC's overlay, then the driver), `apple-ave-fetch-firmware.service` (opt-in), `install-firmware`, `known-hashes.txt` |

No Apple firmware, and no data taken from Apple's files, is in either
package. The upstream repository's read-only diagnostic modules are not
included.

## Setup

1. `sudo dnf install apple-ave` (pulls in `dkms-apple-ave`; DKMS needs
   `kernel-16k-devel` for each kernel).
2. `sudo apple-ave-fetch-firmware`: shows what it will read from Apple
   (the AVE firmware, about 0.5 MB, from Apple's macOS 13.5 restore image
   on Apple's CDN; the kernelcache, about 26 MB, unless the Asahi installer
   left this Mac's own on the EFI partition), asks, then makes, checks and
   installs the files. `--dry-run` shows the plan without any network
   access; `--ipsw FILE` and `--from-dir DIR` use local copies instead.
   Details: [apple-ave-firmware.md](apple-ave-firmware.md).
3. `sudo systemctl enable --now apple-ave.service`
4. `/usr/libexec/apple-ave/ave-load status` lists the encoder nodes
   (`apple-ave-enc` on `/dev/videoN`) and the firmware files.

If the files are missing, `ave-load` loads nothing and says which command
to run. To make them at boot instead (this may download from Apple's CDN):
`sudo systemctl enable apple-ave-fetch-firmware.service`.

To stop using the encoder: `sudo systemctl disable apple-ave.service` and
reboot (the overlay cannot be removed from a running kernel).

## Supported SoCs

All with the macOS 13.5 system firmware (the Asahi installer's default).

| SoC | encoders | loaded | notes |
|---|---|---|---|
| t6000 M1 Pro | 1 | by default | |
| t8103 M1 | 1 | by default | H.264 limited to I and P frames (B frames hang the firmware on this SoC); HEVC B frames work |
| t8112 M2 | 1 | by default | |
| t6001 M1 Max | 2 | after `sudo touch /etc/apple-ave/allow-t6001` | the driver now programs the encoder's DAPF itself, so stock m1n1 should do; not yet run that way. The second encoder comes up from the boot after the first one's pristine DATA was kept |
| t6002 M1 Ultra | 4 (the first is used) | after `sudo touch /etc/apple-ave/allow-t6002` | no per-machine preparation any more: the firmware placement is read from the live ADT; not yet run on a second M1 Ultra |
| others (M2 Pro/Max/Ultra, M3 and later) | | | not ported |

## Status

"Stable" here would mean, per SoC, on the driver commit this package
ships: `v4l2-compliance` passes for both codecs; the upstream soak
(`tools/stress.sh`, docs/84) passes with no failures; a reload in the same
boot and a recovery from a forced firmware hang work; and two boots through
this package's own path (fetch tool, then the service) encode correctly.
No SoC meets that yet. What exists (upstream docs/53, 84, 87-98):

| SoC | machines | evidence | missing |
|---|---|---|---|
| t6001 | 1 (the lab machine; patched m1n1, PMP DTB) | `v4l2-compliance` 54/54 (both codecs, Main 10); soak 2 h 16 min, 0 failures (6055 identical streams, 60 000 frames per codec, 300 open/close cycles, 40 SIGKILLs); five reloads in a boot; hang recovery; both encoders at once; PSNR 43.5-44.8 dB from 192x96 to 4K | all of it on the shipped commit (the soak ran on 2026-09-27's code); stock m1n1; B frames not rerun since their fix |
| t6000 | 1 | 60-frame runs at 720p-4K (43.7-44.8 dB), rate control, B frames and two references, 2-pass; loaded at boot through a service on one machine since 2026-09-30 | soak, compliance, the shipped commit |
| t8112 | 1 | 60-120-frame runs (H.264 44.2-44.7 dB, HEVC 44.3, Main 10 55.6), reload byte-identical, B frames, 2-pass; loaded at boot on one machine since 2026-10-03 | soak, compliance, the shipped commit |
| t8103 | 2 | H.264 and HEVC at 44.2 dB, a reload, a few hundred frames per session; H.264 B frames / two references hang (clamped) | soak, compliance, the shipped commit |
| t6002 | 1 | all four encoders (44.26 dB each, output identical to the M1 Pro's), four concurrent ffmpeg clients for 5 rounds | soak, compliance, a second machine, the shipped commit |

And the commit this package ships adds four changes that have not run on
hardware yet (upstream docs/99, docs/100): the firmware placement read
from the live ADT, the DAPF programmed by the driver on t6001, the AVE_DPE
tables loaded from the generated file (byte-identical to the tables used
in every run above) and the driver's own copy of the pristine DATA. The
first SoC that can become stable is t6001, on the lab machine, once those
runs and the soak pass on this commit.

## Speed and the performance vote

The encoder's clock is raised by a vote to the power-management
coprocessor (PMP), which runs only when the device tree was built with its
`pmp` alias; Fedora's is not, and this project does not change device
trees. `ave-load` sends the vote where the PMP is running and the vote
helps (t6000, t6001); otherwise the encoder runs at its boot clock.
H.264, one stream, upstream docs/87, 89, 90, 98 and the upstream README:

| SoC | without the vote (stock DT) | with the vote |
|---|---|---|
| t6000 M1 Pro | 1080p ~64 fps (15.5 ms), 4K ~18 fps | ~194 fps, ~55 fps |
| t6001 M1 Max | 1080p ~70 fps, 4K ~19 fps | ~170 fps, ~48 fps |
| t8103 M1 | 1080p ~156 fps, 4K ~42 fps | (no PMP report on this SoC) |
| t8112 M2 | 1080p ~158 fps, 4K ~42 fps | slower: the PMP makes it ~1.5x slower, so no vote |
| t6002 M1 Ultra | 1080p ~57 fps per encoder, ~230 fps with all four | (no die-1 report entries; not used) |

On a t6001 with the PMP running but no vote it is slower still (~57 fps at
1080p).

## Example

```sh
ffmpeg -i in.mp4 -c:v hevc_v4l2m2m -b:v 8M -c:a copy out.mp4
```

Stock ffmpeg's V4L2 encoders have limits (no fixed QP, no B frames); the
upstream repository's `ffmpeg/` directory has patches.

## Tests

`python3 -m unittest discover -s tests` (also run by the RPM's `%check`):
the Image4 parser, the ZIP reader over files and HTTP range requests, the
DPE table generator, the pristine-DATA checks, the hash checks, and the
fetch tool end to end, including `--dry-run` and `--capture`, all on
synthetic files.
