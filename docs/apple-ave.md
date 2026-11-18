# AVE video encoder (apple-ave, dkms-apple-ave)

| | |
|---|---|
| package | `apple-ave`, `dkms-apple-ave` ([packages/apple-ave](../packages/apple-ave/README.md), firmware: [apple-ave-firmware.md](../packages/apple-ave/apple-ave-firmware.md)) |
| sources | `packages/apple-ave/src/driver/` and `src/overlay/`: vendored from [aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver) at `ff8bba6`, plus this repository's own change for the PMP interconnect provider (below); `packages/apple-ave/firmware/`, `files/`, `tests/`: this project's packaging |
| pull requests | #4 and #8 (0.99.6, driver `ff8bba6`), #11 (0.99.6-2, local-only firmware tool), #18 (0.99.6-3, the vote through the PMP interconnect provider); earlier versions (0.99.4, 0.99.5) predate the PR history |

This package carries no patch files: the driver is a vendored copy of the
upstream repository, which documents its design, reverse engineering and
tests in its own `docs/` (about a hundred documents). This page records
what this repository adds or changes and where the evidence lives.

## What it does

A V4L2 stateful encoder driver for the Apple Video Encoder (AVE) block of
M1 and M2 SoCs: NV12 or P010 in, H.264 (Baseline, Main, High) or HEVC
(Main, Main 10) out, through ffmpeg's `h264_v4l2m2m`/`hevc_v4l2m2m` and
GStreamer's `v4l2h264enc`/`v4l2h265enc`. `ave-overlay` adds the encoder to
the device tree at run time (Fedora's trees have no AVE node);
`apple-ave.service` and `ave-load` load the SoC's overlay, then the driver.
`apple-ave-fetch-firmware` makes the firmware files on the user's Mac from
the user's own copy of Apple's macOS 13.5 files.

## Why

Linux has no driver for the hardware video encoder of Apple silicon Macs;
software encoding costs CPU time the encoder would save. On t6000 with the
PMP vote, 1080p H.264 runs at about 194 fps on one encoder.

## Changes this repository carries

- **0.99.6 (#4, #8): driver `ff8bba6`** (the upstream repository's PR #6,
  its issue #5): a reload checks live DATA against the image instead of
  mistaking another unit's iBoot fills for a core that has run; a cold core
  whose DAPF was never programmed this boot is refused with its own
  message; removing a staged load that never released the core no longer
  asks it to halt (which failed, leaked the DATA mapping and made the next
  full load refuse with `-EEXIST`).
- **0.99.6-2 (#11): the firmware tool reads local files unless told
  otherwise.** The kernelcache on the EFI partition, `--from-dir` or
  `--ipsw`; reading Apple's restore image from Apple's servers needs
  `--download-from-apple`, which first prints a notice that it is Apple
  software under Apple's licence terms. `apple-ave-fetch-firmware.service`
  never downloads (`PrivateNetwork=yes`). Part of bringing the COPR in
  line with COPR's build rules and Fedora's licensing guidance.
- **0.99.6-3 (#18): the PMP vote through the interconnect provider.** On a
  kernel with this project's PMP provider
  ([pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md)), the driver
  asks for its vote as a bandwidth request on the `apple-pmp-ave0` node
  (the SoC level as the request tag, the fabric level as a bandwidth step)
  instead of writing the PMP's request slot itself, so one owner (the
  provider) writes the dashboard. `pmp_icc=0` keeps the direct write; on
  kernels without the provider nothing changes (`__has_include` of the
  provider's header). After the review on #18 the path is given back on
  every power-off, including an unclean teardown, so a reprobe after a
  firmware hang cannot leave an old request aggregated with the new one.
  This change exists only in this repository's copy of the driver, not
  upstream.

## Design and alternatives

- **No Apple data in any package.** The firmware and its register tables
  are made on the user's machine by `apple-ave-fetch-firmware`, checked
  against `known-hashes.txt` (hashes and sizes only).
- **Overlays instead of device-tree changes.** This project does not change
  device trees for the encoder; the overlay module adds the node at run
  time, and only `ave-load` may load it (a modprobe.d install rule). The
  overlay cannot be removed from a running kernel.
- **t6001 and t6002 behind marker files** (`/etc/apple-ave/allow-t6001`,
  `allow-t6002`) until they have run in the packaged configuration.

## Testing

- 0.99.6: `python3 -m unittest discover -s packages/apple-ave/tests`
  passes, the SRPM builds, and the driver compiles against 7.2.11 and
  7.3.1; H.264 on t8103 after a reload ([consolidation-plan.md](consolidation-plan.md)).
- 0.99.6-2: on an M1 Max (macOS 13.5 stub), the old default,
  `--download-from-apple`, `--from-dir` with the EFI kernelcache and
  `--from-dir` alone all gave byte-identical files matching
  `known-hashes.txt`; the new default with no options made no network
  request, wrote nothing and exited with instructions. 50 unit tests pass
  in the RPM's `%check`.
- 0.99.6-3, M1 Max, 120 frames 1080p H.264: through the provider 2.49 /
  2.52 / 2.43 s, direct slot write 2.48 / 2.49 s, no vote 3.93 s; output
  identical (PSNR 44.22 dB).
- Per-SoC evidence (compliance, soak, reloads, hang recovery, PSNR) is in
  the package README's [Status](../packages/apple-ave/README.md#status)
  and the upstream docs it cites (53, 84, 87-98).

## Limitations and open items

- **Experimental.** No SoC meets the package's own definition of stable
  yet (per SoC, on the shipped commit: `v4l2-compliance` for both codecs,
  the upstream soak, a reload and a forced-hang recovery, two boots through
  the package's own path).
- Four changes in the shipped commit have not run on hardware yet
  (upstream docs/99, docs/100): the firmware placement read from the live
  ADT, the DAPF programmed by the driver on t6001, the DPE tables from the
  generated file and the driver's own copy of the pristine DATA.
- t8103: H.264 limited to I and P frames (B frames hang the firmware).
- The `pmp_icc` change is not upstream in the AVE repository yet.
- The PMP vote needs a PMP device tree, which this project does not ship.

## Hardware

t6000, t8103, t8112 by default; t6001 and t6002 after the marker file; all
with the macOS 13.5 system firmware. M2 Pro/Max/Ultra, M3 and later: not
ported.

## Upstream status and provenance

Out of tree; upstream is the AVE repository. `GPL-2.0-only` (LICENSING.md).
The driver's register addresses, command layouts and other interface facts
were found by studying Apple's firmware and macOS driver, for
interoperability; this is not the clean-room process Asahi Linux asks for,
and these parts are not Asahi Linux code. How each fact was found, and an
item-by-item inventory of everything taken from Apple's files with the
reason it is an interface fact, are in the upstream
[docs/00-methodology.md](https://github.com/aquarat/apple-m-series-ave-driver/blob/main/docs/00-methodology.md)
and
[docs/100-no-apple-data.md](https://github.com/aquarat/apple-m-series-ave-driver/blob/main/docs/100-no-apple-data.md).
The `ave_macos_*_13_5` field values in `ave_abi.h` are, in this project's
position, interface facts (LICENSING.md, "Provenance of the
reverse-engineered parts"). The firmware tool's Image4 and ZIP readers are
this project's own code (CREDITS.md). The t8103 support is based on a port
by GitHub user henriSchulz, as the sources note.
