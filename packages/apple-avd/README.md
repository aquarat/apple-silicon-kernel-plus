# apple-avd (dkms-apple-avd)

The Apple Video Decoder (AVD) V4L2 stateless driver from the Fedora Asahi
Remix kernel, with four fixes, built by DKMS. Decodes H.264, HEVC, VP9 and
AV1 (as far as the in-tree driver does).

## The fixes

| patch | problem in the in-tree driver |
|---|---|
| 0001 | Capture buffers are mapped uncached, so a client that copies decoded frames with the CPU reads at ~250 MB/s. The patch lets user space ask for cacheable buffers (`V4L2_MEMORY_FLAG_NON_COHERENT`); clients that do not ask are unaffected. |
| 0002 | A slice that references a DPB entry that is not valid (e.g. a stream joined mid-GOP) faults the decoder's IOMMU and resets it. Such slices are now rejected with `-EINVAL`. |
| 0003 | The 8 MB job segment table is allocated contiguously for every frame; under memory pressure frames are lost. Now `kvcalloc()`. |
| 0004 | `slice_num` is never reset, so every H.264 stream stops after 4096 slices (about 4.5 minutes of a 15 fps camera). |

Measurements and details are in each patch's message.

## Layout

| path | what |
|---|---|
| `src/` | the driver source DKMS builds: `scripts/rebase-avd.sh` output for the kernel in the spec's `base_kernel` |
| `patches/` | the fixes, in `git format-patch` form against the pristine driver plus our out-of-tree `Makefile`/`Kbuild` |
| `dkms.conf` | `BUILD_EXCLUSIVE_KERNEL="^7\.1\..*asahi.*"`: one kernel series |
| `depmod-apple-avd.conf` | makes modprobe prefer the DKMS module (in `extra/`) to the in-tree one |

## Checks after installing

```sh
dkms status apple-avd                    # "installed" for each kernel
modinfo -F filename apple_avd            # must end in /extra/apple-avd.ko.xz
```

After a reboot (or `modprobe -r apple_avd && modprobe apple_avd` with no
decoder in use), `lsmod | grep apple_avd` shows the DKMS module.

## Firmware

The driver loads `apple/avd-fw-<version>-<target>.bin`, built from
[AsahiLinux/avd-fw](https://github.com/AsahiLinux/avd-fw) (MIT). The in-tree
driver needs the same files, so a system that already decodes with it has
them. This package does not ship firmware.

## Licence

`avd-hw.c`, `avd-inst.h` and `avd-regs.h` are MIT; `avd-av1-entropymode.c`
is BSD-2-Clause (Alliance for Open Media); the rest is GPL-2.0-only, as in
the kernel. See `LICENSING.md` at the top of the repository.
