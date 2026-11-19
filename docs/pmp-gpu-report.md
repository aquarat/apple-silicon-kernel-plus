# The GPU's power-state report to the PMP (t6000/t6001)

Kernel patches 0035-0037 (`packages/kernel/patches/`). They give M1 Pro/Max GPUs their full
memory bandwidth while the power management coprocessor (PMP) runs. Summary in
`packages/kernel/README.md`, "The GPU's report to the PMP"; licensing in `LICENSING.md`.

## Applies to

| SoC | machines | status |
|---|---|---|
| t6000 (M1 Pro) | MacBook Pro 14"/16" (J314s, J316s) | entry added (`report@9`) |
| t6001 (M1 Max) | MacBook Pro 14"/16" (J314c, J316c), Mac Studio (J375c) | entry added, **tested on a 14" M1 Max** |
| t6002 (M1 Ultra) | Mac Studio (J375d) | entry deleted: the PMP has not been run on a two-die machine |
| t602x and later, t8112, t8103 | | not covered |

The patches only matter when the PMP runs. That needs a device tree built with `APPLE_USE_PMP`
and loaded by m1n1's stage 2. Fedora's trees don't set it, and Asahi's `pmp` driver must start the
PMP. Without the PMP, nothing is written.

## Problem

With the PMP running, it owns the SoC, fabric and DRAM controller (DCS) performance states.
Memory-bound GPU work on an M1 Max then runs below the speed it has with the PMP not running. With
llama.cpp's Vulkan matrix-vector product (4096x14336, the token-generation shape), the loss is
3-20% depending on the data type. While the GPU works, the PMGR fabric and DCS p-state registers
stay at their idle values (`fabric-ps` 3, `dcs-ps` 7).

The CPU-side requests from patches 0030-0034 don't help the GPU. A CPU-cluster request raises the
fabric and DCS (to 11/9), but GPU mat-vec stays at about 194 GB/s. The PMP ignores writes from
Linux into the GPU's own request slot.

## Root cause

The PMP has its own bandwidth-driven DVFS for the GPU. Its configuration in Apple's device tree
(`/arm-io/pmp/iop-pmp-nub`) has `agx-fast/slow-{af,afr,dcs}-bw-threshold` tables. The DCS table
decodes as up/down thresholds of about 40/80/111 per level. **It only runs for a GPU that has been
reported powered on.** Blocks report their power state to the PMP as bits in a request word of the
PMP's shared dashboard. Asahi's `pmp-report` driver writes these bits for the blocks it has entries
for.

- Apple's device tree marks the PMGR device `GFX` (id 10, so report bit 9) `notify_pmp`. Its
  record in the PMP's `soc-device` table is `AGX`, of type `GFX_`.
- Asahi's t600x device trees have a report entry for every other `notify_pmp` block (ANE, ISP,
  display, encoder, decoder, ...) but none for the GPU.
- t8112's tree has one and uses it as the GPU's power domain.

Evidence: with bit 9 set by hand while the GPU runs, the PMP acknowledges it. Under GPU load the
PMP then raises fabric to 7 and DCS to 9. Within a second of the load ending it drops them back to
idle. Bandwidth rises above the PMP-not-running figures (table below).

## Why not t8112's way

Making the entry the GPU's power domain, as t8112 does, reports `GFX` when the GPU's domain powers
on. That is before the GPU firmware boots. On an M1 Max the machine then hard-hung 1-10 s after the
GPU firmware started, 3 times out of 3, with no kernel message. The same steps without the entry
were fine.

The timing is what differs:

| how the bit was set | relative to the GPU firmware's boot | result |
|---|---|---|
| as the GPU's power domain | before | hard hang, 3/3 |
| at the GPU driver's bind (driver probe has booted the firmware) | after | fine |
| minutes later, by hand | long after | fine |
| GPU driver bound first, PMP started 8 s later | after | fine |

A missing PMP doorbell does not explain the hang. Asahi's GPU configurations map no PMP doorbell or
PMGR scratch page for t8112 either; only t8103's older PMP has them. t8112, t600x and t602x all give
the GPU firmware the same dashboard windows instead. Why reporting early hangs t600x is not known.
The best guess is that the PMP, once told the GPU is on, starts touching the GPU's side of the
fabric while the GPU firmware is still bringing it up. The fix doesn't depend on the answer.

## Design

- **0035, binding:** `Documentation/devicetree/bindings/power/apple,pmp-report.yaml`. It documents
  the report node and its entries as Asahi's trees already use them; the Asahi tree has no binding.
  It adds two properties:
  - `apple,report-while-bound`: a phandle to a device;
  - `apple,report-settle-ms`: a delay after bind, default 0.
- **0036, `pmp-report`:** an entry with `apple,report-while-bound` is not a power domain. A
  platform bus notifier follows the named device's driver:
  - The bit goes on after `BUS_NOTIFY_BOUND_DRIVER` (plus the settle time). If the PMP is not
    running yet, the report waits for it, backing off up to 30 s between checks. It is never
    written while the PMP is not running.
  - It goes off at `BUS_NOTIFY_UNBIND_DRIVER`, before the driver's `remove`.
  - It goes off at `PM_SUSPEND_PREPARE`/`PM_HIBERNATION_PREPARE` and back on after
    `PM_POST_*`, once devices have resumed. It also goes off from a reboot notifier.
  - A consumer that is already bound when the entry probes is handled.
  - When the entry itself unbinds, its notifiers are unregistered, the pending work is cancelled
    and the bit is cleared.
  - The same read-modify-write and acknowledge poll as power-domain entries, under the driver's
    lock.
- **0037, device trees:** `report@9` (`label = "pmp-gfx"`, `apple,report-while-bound = <&gpu>`)
  in `t600x-die0.dtsi`, deleted in `t6002.dtsi`. The GPU keeps its PMGR domain (`ps_gfx`). No GPU
  driver change.

Alternative: the GPU driver could report after its own firmware initialisation, since it knows best
when the firmware is up. It is written in Rust and would need bindings to `pmp-report`; the bus
notifier needs no driver change.

## Testing

**Machine:** MacBook Pro 14" M1 Max (t6001, J314c), Fedora Asahi Remix 44.

**Kernel:** 7.3.1 with 0001-0034 and 0036. The PMP was started by Asahi's `pmp` driver; m1n1's
stage 2 device tree has `APPLE_USE_PMP`.

**Procedure:**
- Boot with `modprobe.blacklist=asahi`, add `report@9` to the running device tree (a lab-only
  module applying an `of_changeset`), then load the GPU driver.
- `apple_cpu_memvote.mode=off`, so CPU requests can't raise fabric/DCS.
- Power is the SMC's total system power at 1 Hz (0.25 s for the load runs).

**Bandwidth:** GPU mat-vec 4096x14336 via `test-backend-ops perf -o MUL_MAT -b Vulkan0`, n=1,
in GB/s:

| | f32 | f16 | bf16 | q4_0 |
|---|---|---|---|---|
| report on, this driver (14 runs over two boots, range) | 167.9-170.7 | 218.4-224.4 | 256.5-264.4 | 150.8-155.3 |
| no report, same kernel (3 runs) | 162.6-164.1 | 185.8-194.1 | 185.4-190.1 | 134.9-136.6 |
| PMP not running (7.1.13, same machine) | 167.6 | 217.4 | 236.9 | 147.8 |

**Power,** in the same boot with the bit toggled around the driver, 2 pairs:
- Under continuous GPU mat-vec: 53.1-54.3 W without the report, 63.8-64.2 W with it, so about
  +10 W for 4-37% more bandwidth. Energy per byte is about even: better for bf16, worse for f32.
- Idle: 13.3-13.5 W both ways, so no idle cost. Idle was high in that boot because the desktop
  started before the GPU driver.
- An earlier same-boot A/B on 7.1.13 gave idle 4.31-4.63 W either way, and +8 W under GPU load.

**Other results:**
- No warnings, IOMMU faults, PMP crashes or hangs in any run with the report set after the GPU
  driver bound.
- Soaks: 5-7 minutes of alternating GPU load and idle per boot.
- `dt_binding_check` and `CHECK_DTBS` pass for t6000-j314s, t6001-j314c and t6002-j375d.
- `checkpatch` is clean apart from the generic MAINTAINERS note, already covered by
  `bindings/power/apple*`.
- The driver builds with W=1 without warnings.

## Limitations and open points

- **Booted from a rebuilt stage 2 after the merge** (2026-11-18): the tests above added the entry
  to the running device tree. The DTBs in this package only take effect once m1n1's stage 2 is
  rebuilt from them. That was done afterwards on two laptops, each as a one-shot trial of the new
  stage 2 that put the previous one back unless the boot was accepted: only the machine's own DTB
  was replaced by 7.3.4 `plus5`'s with the PMP enabled, m1n1 and U-Boot unchanged.
  - 14" M1 Max (J314c): `report@9` was in the device tree before any module loaded; GPU mat-vec
    170 / 222 / 263 / 155 GB/s and 10-thread STREAM 159-162 / 159-164, the same as with the
    entry added at run time. A 7.3.1 `plus3` kernel (without 0036) also booted on that device
    tree, but treats `report@9` as an unused power domain and switches it off, so it gets no
    GPU report (GPU 160 / 186 / 187 / 131).
  - 14" M1 Pro (J314s): the same numbers as with the entry added at run time
    ([kernel-7.3.4-rebase.md](kernel-7.3.4-rebase.md#tests-m1-pro-laptop-t6000-pmp-running)).
- **Suspend/resume untested:** `pm_test=devices` hangs the test machine without these patches too.
- **Entry unbind not exercised on hardware:** unbinding an entry through sysfs was only
  compile-tested.
- **t6002:** its Apple device tree also lists a single `GFX` device (id 10), but the PMP has not
  been run on a two-die machine.
- **t602x and later:** not covered.
- **Power trade-off:** about 10 W more under sustained GPU memory load. It is the PMP's own policy
  (Apple's thresholds), not a Linux choice.

## Provenance

- **Report bit and device ids:** Apple's device trees in the macOS restore image
  (`DeviceTree.j314sap/j314cap/j375dap.im4p`), read with m1n1's ADT parser. Asahi's own device
  trees are written from the same source. The dashboard addressing and request-word bitmaps come
  from Asahi's `pmp-report` driver.
- **Everything else:** black-box measurement on Linux.
- **What is in the patches:** no code or data from Apple's files.
