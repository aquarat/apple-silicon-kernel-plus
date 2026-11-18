# AVD decoder fixes (dkms-apple-avd)

| | |
|---|---|
| patches | `packages/apple-avd/patches/0001-media-apple-avd-allow-cacheable-non-coherent-MMAP-bu.patch`, `0002-media-apple-avd-h264-reject-slices-that-reference-in.patch`, `0003-media-apple-avd-allocate-the-job-segment-table-with-.patch`, `0004-media-apple-avd-h264-complete-the-request-and-drop-t.patch`, `0005-media-apple-avd-keep-working-with-firmware-without-a.patch` |
| package | `dkms-apple-avd` ([packages/apple-avd](../packages/apple-avd/README.md)) |
| pull requests | 0001-0004: none of their own (commit `67aa5a5`, before the PR history; rebased in `c083205` and `2e4a6b6`). 0005: on the 7.3 line, on `main` through #9; its legacy-firmware fallback fixed in #12 after the review on #9 |

## What it does and why

| patch | problem | fix |
|---|---|---|
| 0001 | Capture buffers are allocated on a device not marked `dma-coherent`, so both mappings are Normal-NC. Reading decoded frames back is a serialised uncached DRAM transaction per load: ~250 MB/s, about 18 ms of CPU per 2304x1296 frame for a client that copies frames (ffmpeg's `v4l2request` hwaccel without a DRM-PRIME consumer, as network video recorders use it). Hardware decode cost 4-5x the CPU of software decode. | `allow_cache_hints` on both queues and `V4L2_BUF_CAP_SUPPORTS_MMAP_CACHE_HINTS`: user space can ask for cacheable buffers with `V4L2_MEMORY_FLAG_NON_COHERENT`; videobuf2 does the cache maintenance. `DMA_ATTR_NO_KERNEL_MAPPING` is dropped from the capture queue (`dma_alloc_noncontiguous()` rejects it; it had no effect behind an IOMMU anyway). Clients that do not ask are unaffected. |
| 0002 | A P/B slice whose reference lists point at DPB entries that are not valid (every time a client starts decoding on a non-IDR frame, e.g. joining a live RTSP stream mid-GOP) makes the decoder dereference an uninitialised reference slot: a DART fault, a frame that never completes and, 2 s later, a watchdog reset that disturbs other contexts decoding at the time. | Validate the reference lists before anything reaches the hardware; fail the request with `-EINVAL`, so the client gets the buffer back with `V4L2_BUF_FLAG_ERROR` as for corrupt input. |
| 0003 | The job segment table (2056 bytes per slice) was allocated physically contiguous for every frame: about 8.4 MB (order 10) in 7.1, which failed once the page cache was full (four concurrent 2304x1296 decodes on t6000 silently lost frames); in 7.2 about 170 KB (order 4 on 16K pages) for a 1296-line stream, more while it grows. | `kvcalloc()`/`kvfree()` everywhere: the CPU only reads the table, so it need not be contiguous; `kvcalloc()` also checks the multiplication. |
| 0004 | When an H.264 slice fails early (no memory for the slice or a bigger table), the media request is never completed, so every later request on the context fails with `EBUSY`; and the freed table pointer is left set, so the next slice writes into freed memory and the table is freed twice. | Complete the request on that path too and clear the pointer, so the rest of the frame is refused and the next frame starts a new job. (The 7.1 version also fixed a missing `slice_num` reset, which stopped streams after 4096 slices; 7.2 has that fix.) |
| 0005 | Asahi's 7.2.15 driver reads the codec list from a config block in the firmware and fails the probe when there is none, so firmware built from avd-fw before that block (before 0.2) leaves the machine with no decoder. | For such firmware, read the older `CODECS:` trailer, limited to the SoC's capabilities, as the driver did before 7.2.15; assume the SoC's list, with a warning, only when the firmware has neither. |

## Design and alternatives

- **DKMS, not in-tree patches.** Decided in
  [consolidation-plan.md](consolidation-plan.md) (decision 4): the same
  source builds for 7.2 and 7.3 kernels (`BUILD_EXCLUSIVE_KERNEL="^7\.[23]\..*asahi.*"`),
  so a 7.2 kernel kept for rollback keeps the patched decoder, and the
  package also works on stock kernels of the same series. A depmod.d rule
  makes the DKMS module win over the in-tree one.
- **0001 uses the standard videobuf2 cache-hint mechanism**, so no driver
  or uAPI invention, and coherency is still correct without assumptions
  about the fabric.
- **0002 rejects the slice** rather than substituting the destination
  buffer as other stateless drivers (hantro, rkvdec) do: the reference slot
  table cannot be filled for an entry with no buffer.
- **0005, first version and review.** The first version trusted the SoC's
  full list for every firmware without the config block; the review on #9
  pointed out that firmware with the older `CODECS:` trailer could then
  announce formats it cannot decode. #12 reads the trailer first.

## Testing

- 0001, M1 Mac mini (t8103), one 2304x1296 NV12 buffer (13.2 MB plane):
  read-back 240-250 MB/s coherent against 17.9-23.9 GB/s cacheable (memcpy,
  NEON, ldnp/stnp). `ffmpeg -hwaccel v4l2request ... -vf
  fps=5,scale=640:360` for 150 frames: 2.97 s user + 0.09 s sys before,
  0.36-0.40 s user + 0.11-0.14 s sys after (software decode: 0.53 s
  single-threaded), output bit-identical; decode plus read-back alone from
  2.75 s to 0.08 s user + 0.12 s sys. Verified with the full clip matrix
  (GStreamer `v4l2slh264dec`, coherent buffers, unchanged) and per-frame
  md5 comparison against software decode.
- 0002 and 0003: the failures were seen with network video recorder
  workloads (a client joining live RTSP streams mid-GOP; four concurrent
  2304x1296 decodes on t6000 while recordings filled the page cache). The
  commit messages record the failure modes and the fixes' logic, not
  separate measurements of the fixes; the top-level README lists the
  package as stable, and its DKMS builds have run in production use.
- 0004: no test is recorded beyond the code path described.
- 0005 (#12): compiles with W=1 and no warnings against 7.3.1 and 7.2.11
  headers; SRPM builds, rpmlint clean; `scripts/rebase-avd.sh` against the
  7.3.1 `plus3` kernel gives the same in-tree driver, and 0001-0004 apply
  unchanged.
- dkms-apple-avd 7.3.1.2 (0001-0005) on 7.3.1 `plus3`, after #12 merged:
  - an M1 Pro MacBook Pro running a network video recorder workload
    decoded H.264, HEVC and a camera clip bit-exact against software
    decode, then ran a 15 min soak with five cameras at 5.04 fps and no
    skipped frames;
  - an M1 Ultra Mac Studio decoded H.264 and HEVC bit-exact against
    software decode;
  - an M2 Mac mini, whose installed firmware has neither the config block
    nor a `CODECS:` trailer, took 0005's last fallback: it logged the new
    warning "Firmware without config block or codec list" and announced
    the same codecs as before;
  - DKMS built the module for the installed 7.3.1 kernels, and an M1 Max
    Mac Studio loaded it from DKMS's `extra/` directory.

## Limitations and open items

- t8112 (M2): H.264 works, HEVC times out (open).
- [consolidation-plan.md](consolidation-plan.md) still lists the DKMS
  builds on 7.3.1 as to do; the results above cover them.
- 0001's cacheable buffers were measured on 7.1/7.2; the 7.3.1 bit-exact
  checks do not say which buffer mode the client used.
- 0001 helps only clients that ask for non-coherent buffers (ffmpeg needs
  to request `V4L2_MEMORY_FLAG_NON_COHERENT`).

## Hardware

M1 family (t8103, t6000, t6001, t6002); t8112 partly (see above).

## Upstream status and provenance

Not upstream. Fixes to the Asahi Linux AVD driver (`GPL-2.0-only`, with
MIT and BSD-2-Clause files as LICENSING.md lists), this project's work,
written from the driver's source and observed failures. The firmware is
built from [AsahiLinux/avd-fw](https://github.com/AsahiLinux/avd-fw) and
not shipped by this package.
