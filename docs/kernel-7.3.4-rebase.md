# Kernel 7.3.4 (plus5): the rebase

This records the move of `packages/kernel` from Asahi 7.3.1 (`plus4`) to
Asahi 7.3.4 (`plus5`): what is pinned, why the release sorts where it
does, what changed in the patches and configs, and how it was tested.

## Pins (`packages/kernel/kernel-plus.conf`)

| | value |
|---|---|
| Asahi tree | `asahi-wip` at `201be96df5654336bdcbe1da2103f193d7a0b940` (its Makefile: 7.3.4); kept in this project's fork as tag `plus/asahi-wip-7.3.4-201be96df565` |
| kernel.org tarball | `linux-7.3.4.tar.xz`, sha256 `b11b6df8295e8e991ff040b71aaa4994a8b55caa23b6b092907f195b5840fd1f` (kernel.org `sha256sums.asc`) |
| Fedora SRPM | `kernel-7.3.4-200.fc44.src.rpm` from Koji, sha256 `4b205aefad7dc8190447ac0ca0688d7c878e7e67200e31c92c1e700e8c844c43` |
| release | `PKGRELEASE=900.asahiwip`, `BUILDID=plus5` |

## Release ordering

The maintainer guide's rule for a new Linux version is `BUILDID=plus1`.
This release uses `plus5` instead, so the plus number keeps rising along
the 7.3 line (7.3.1 ended at `plus4`). Either way the release sorts above
everything it must replace, checked with `rpmdev-vercmp`:

```
7.3.4-900.asahiwip.plus5.fc44 > 7.3.4-401.asahi.fc44         (@asahi's 7.3.4)
7.3.4-900.asahiwip.plus5.fc44 > 7.3.1-900.asahiwip.plus4.fc44 (this project's previous)
```

`@asahi`'s 7.3.4-401 sorted above our 7.3.1 builds, so dnf would have
offered it to users of this COPR; with 7.3.4 plus5 it no longer does.

## Patches

All patches were rebased with `git am --3way` onto the tarball plus the
new `patch-7.3-redhat.patch` (the Asahi tree and Fedora's patch). Their
content is unchanged, apart from the context lines that moved, except:

- **0003 (atlantic, AQC113 list filters relative to the base index) is
  dropped.** The 7.3.4 tree has its own `hw_atl2_hw_packet_filter_set()`,
  which enables the unicast/multicast list entries relative to the
  firmware's `l2_filters_base_index`. That is the problem 0003 fixed.
  `hw_atl_b0.c` no longer has the shared helper the patch changed.

The other patch files keep their names and numbers (0001, 0002, 0010-0013,
0020-0027, 0030-0034). The GPU report patches 0035-0037 (#20, see
`pmp-gpu-report.md`) were merged for 7.3.1 without a release bump. They
apply to 7.3.4 unchanged and ship first in plus5.

## Configs

`CONFIG_VIDEO_APPLE_MSR` is new in this Asahi tree: the MSR scaler and
colour-space converter, an M2M V4L2 driver for Apple hardware. Fedora's
`%prep` check stopped on it as unset. `plus-aarch64.config` sets it to `m`,
like the other Apple media drivers. With that, `PREP_CHECK=1
scripts/make-srpm.sh kernel` passes: the patches apply and Fedora's
config checks pass.

## DKMS packages

- **apple-avd.** `scripts/rebase-avd.sh` against the 7.3.4 SRPM: all
  patches in `packages/apple-avd/patches` apply, and the result is
  identical to `packages/apple-avd/src`. The package does not change, and
  `BUILD_EXCLUSIVE_KERNEL` (`^7\.[23]\.`) covers 7.3.4.
- **apple-ave.** Builds against the 7.3.4 tree, together with its overlay.
- **Both modules** compile cleanly against a 7.3.4 build tree, with no
  warnings.

## Tests (M1 Max laptop, t6001; PMP running)

The kernel was built from the rebased tree with a configuration reduced
to the test machine's modules. It was booted once as a one-shot GRUB
entry, with the machine's default kernel left untouched:

- **Boot:** clean. Wi-Fi, the GPU driver and the PMP all come up, the
  `apple-pmp-icc` provider and `apple-cpu-memvote` load, and the kernel
  log has no WARNING.
- **CPU STREAM (10 threads, copy/triad GB/s):**
  - memvote `auto`: 151/155 and 152/164;
  - `off`: 55/67;
  - one thread on a P-cluster in `auto`: 76/82.

  These match 7.3.1 plus4.
- **GPU mat-vec (f32/f16/bf16/q4_0 GB/s):** 164/194/193/124, as on 7.3.1
  without the GPU report patches.
- **apple-ave:** 120 1080p H.264 frames take 2.51 s with the vote through
  the PMP interconnect provider and 3.91 s without a vote. The output is
  identical in both cases, PSNR 44.2 dB.

### With the GPU report patches (0035-0037)

This is a second one-shot boot. The test machine's device tree comes from
its boot loader (m1n1 stage 2), which does not have the new `report@9`
entry. The entry, `apple,report-while-bound = <&gpu>`, was therefore
added live with a lab-only `of_changeset` module, after the GPU driver
had bound. CPU requests were off (`apple_cpu_memvote.mode=off`):

- **Report bit:** the PMP's report word (PS-REQ/PS-ACK) went from
  `0x60003000` to `0x60003200`, bit 9 being the GPU.
- **Fabric and DCS:** under GPU load the PMGR fabric/DCS states rose from
  3/7 to 7/9, and dropped back to 3/7 when the GPU went idle.
- **GPU mat-vec (f32/f16/bf16/q4_0 GB/s):** 162.7/190.8/190.7/134.4 before
  the report, 171.8/221.8/263.1/154.4 and 171.4/222.5/264.1/153.3 after it.
  That is above the PMP-off figures (168/217/237/148).
- **Mixed load (memvote `auto`):** the same mat-vec while 8-thread STREAM
  runs gives GPU 166/222/266/152 and STREAM 152/145. 10-thread STREAM
  alone gives 155/161.
- **Kernel log:** no warnings, faults or GPU errors.
