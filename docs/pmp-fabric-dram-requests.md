# PMP fabric and DRAM requests

| | |
|---|---|
| patches | `packages/kernel/patches/0030-pmdomain-apple-pmp-report-Use-a-64-bit-shift-for-the.patch`, `0031-pmdomain-apple-pmp-report-Add-a-DVFS-request-interfa.patch`, `0032-interconnect-Export-icc_get.patch`, `0033-interconnect-apple-Add-a-PMP-provider-for-fabric-and.patch`, `0034-soc-apple-Add-CPU-cluster-memory-bandwidth-votes.patch` |
| config | `INTERCONNECT_APPLE_PMP=y`, `APPLE_CPU_MEMVOTE=m` (`packages/kernel/configs/plus-aarch64.config`) |
| also | `apple-ave` 0.99.6-3: the encoder's PMP vote goes through the provider (`pmp_icc=1`), see [apple-ave.md](apple-ave.md) |
| pull requests | #18 (the series and its review rounds), #19 (kernel `BUILDID` `plus4`) |
| follow-up | 0035-0037, reporting the GPU to the PMP: PR #20, with its own document |

## What it does

- **0030** `pmp-report`: the report entry's bit is built with `BIT_ULL()`
  instead of `1 << id`. The PS-REQ/PS-ACK words are 64 bits wide, and
  t6002 uses ids 0x33 and 0x34 for its second die's display entries, for
  which the int shift was undefined behaviour.
- **0031** `pmp-report`: `apple_pmp_dvfs_request()` and
  `apple_pmp_dvfs_slots()` write an agent's DVFS request (SoC level, four
  fabric levels, DRAM controller (DCS) level, valid bit) into its slot of
  the PMP's shared dashboard. Write-only; unchanged values are not written
  again; nothing is written while the PMP is not running; all requests are
  withdrawn across system sleep and at shutdown and restored on resume.
- **0032** exports `icc_get()`, so consumers can find an interconnect path
  by node names.
- **0033** an interconnect provider, `apple-pmp-icc`, registered by the
  report driver when the SoC's slots are known: one node per agent with a
  known slot (the three CPU clusters and the first video encoder on
  t6000/t6001), each linked to a DRAM node. An agent's aggregated bandwidth
  (the larger of average and peak) picks a step: up to 64 GB/s asks for
  fabric level 1, up to 128 GB/s for level 2, more for fabric level 3 and
  DCS level 3; no bandwidth withdraws the request. A request tag can add a
  minimum SoC level (the encoder's clock follows it). Built in, and cannot
  be unbound, since consumers hold paths into it.
- **0034** `apple-cpu-memvote`: every 10 ms, for each CPU busy at least
  half the period at no less than 60% of its maximum frequency, read its L1D
  load misses and active cycles from the CPU PMU. A cluster with a CPU at or
  above 10 misses per 1000 cycles requests 200 GB/s from the provider, and
  drops the request 100 ms after its last such sample. `mode=auto|off|force`
  (module parameter, writable in sysfs) for A/B tests, thresholds as
  module parameters, and a `stats` attribute with each cluster's state and
  time with a request.

## Why

On M1 Pro/Max with the power management coprocessor (PMP) running (a
device tree built with `APPLE_USE_PMP`; Fedora's trees are not), the PMP
sets the SoC, fabric and DRAM-controller performance states from its own
monitors and from per-agent requests in its dashboard. Running it saves
about 1.3 W at idle on an M1 Max, but Linux writes none of the requests, and
the PMP has no CPU-cluster bandwidth monitor of its own, so a CPU that
streams memory gets the lowest fabric and DCS levels: CPU STREAM bandwidth
halves compared with the PMP not running (110/133 to 55/67 GB/s copy/triad
with 10 threads, 52/71 to 25/29 with one).

A request in a cluster's slot fixes that: fabric level 3 with DCS level 3
gives 160/165 GB/s with 10 threads, more than with the PMP off. Holding the
request all the time costs nothing measurable at idle, but about 2.4 W
under compute-bound load (sha256 on 10 threads, same throughput), so the
request has to follow memory demand, not CPU load: L1D load misses per 1000
cycles are 56-205 for STREAM and about 1 for sha256, an order of magnitude
either side of the threshold of 10.

## Design and alternatives

- **Layers.** The dashboard transport lives in the report driver, which
  already maps the window (non-posted, as everything under `/soc`) and
  owns its lock. The interconnect provider turns bandwidth into levels.
  Consumers (CPU clusters, the encoder) ask for bandwidth in the usual
  `icc_set_bw()` way, so they stay SoC-independent and the step table can
  be recalibrated per SoC.
- **Interconnect, not devfreq or PM QoS.** Linux does not own the fabric and
  DRAM clocks: the firmware runs their DVFS, and Linux only sends floors per
  agent. That is the interconnect framework's model (as for Qualcomm's RPMh
  or MediaTek's DVFSRC). A devfreq device for "the fabric" would claim
  control Linux does not have, and PM QoS has no per-agent aggregation; a
  global knob in undocumented PMP levels would become ABI.
- **Write-only.** Reading a slot while the PMP has not yet consumed a write
  makes it drop that request, so there is no read-back API. Each slot is
  meant to have one owner.
- **`icc_get()` by name.** On Apple silicon the device tree comes from the
  boot loader's copy, so new `interconnects` properties cannot be relied on
  to reach every machine.
- **A memory-intensity gate for the CPU.** A floor tied to CPU frequency
  alone (the usual `opp-peak-kBps` pattern) would hold the request under
  compute-bound load and cost the 2.4 W above. The PMU miss rate separates
  the two by an order of magnitude. L2-resident working sets also miss L1D
  and will request bandwidth they do not need; a second event could refine
  that if it matters. Idle CPUs are not read (no IPIs to wake them).
- **Steps.** Measured with CPU STREAM from one cluster's slot on an M1 Max:
  fabric level 1, 2 and 3 + DCS 3 give about 128, 146 and 160 GB/s (10
  threads), against 55 GB/s with no request and 110 GB/s with the PMP off.

Review rounds on #18 (Codex) changed 0034 and apple-ave:

- a CPU skipped in a period (idle or slow) only rebaselines its counters
  on its next read, so a ratio covers exactly one 10 ms period;
- clusters come from the device tree's cpu-map (`topology_cluster_id()`:
  0 = E, 1/2 = P0/P1, also the order of the PMP slots), so no cpufreq
  policy is needed at probe and offline CPUs keep their cluster;
- counters missing at probe are created when the CPU is next busy (retried
  at most every 10 s), and a CPU-hotplug teardown callback marks a CPU's
  counters for recreation when it goes offline;
- a held request is resent when `bw_kbps` changes;
- apple-ave gives its interconnect path back on every power-off, so a
  reprobe after a firmware hang cannot leave an abandoned path aggregated
  with the new one.

## Testing

M1 Max (14" MacBook Pro), 7.3.1 with this series, PMP running, SMC system
power. First revision (PR #18 description):

| | `mode=auto` | `mode=off` | PMP not running |
|---|---|---|---|
| CPU STREAM 10 threads, copy/triad GB/s | 163/165 | 55/67 | 110/134 |
| CPU STREAM 1 thread, E / P0 / P1 cluster | 35 / 77 / 76 | - / 25 / - | 52 (P) |
| idle W (3 pairs, 60 s each) | 4.84, 4.68, 4.50 | 4.88, 4.63, 4.54 | |
| sha256 on 10 threads, W (5 pairs, 25 s) | 25.6 | 25.9 | |
| GPU mat-vec f16/bf16 GB/s | 197/195 | 188/192 | 217/237 |
| encoder, 120 frames 1080p H.264 | 2.51 s (2.50 s with the driver's own slot write; 3.92 s without a vote) | | |

Final revision (`f53a26e`), a trial kernel built from exactly these patches
on the 7.3.1 `plus3` base (PR #18 comments):

| | `mode=auto` | `mode=off` | `mode=force` |
|---|---|---|---|
| CPU STREAM 10 threads, copy/triad GB/s | 150.9/161.7 right after switching from `off`, then 160.6/165.5 | 54.5/67.2 | 158.5/162.5 |
| 1 thread E / P0 / P1, copy/triad | 34.7/35.2, 76.8/80.8, 75.8/81.3 | P0 25.2/29.2 | |
| sha256 on 10 threads, W (5 pairs, 25 s), mean | 25.75 | 26.10 | |
| GPU mat-vec f32/f16/bf16/q4_0 GB/s | 163.9/197.1/196.5/114.0 | 163.1/184.6/189.5/133.3 | |
| idle W (3 pairs, 60 s, `off` first) | 4.81, 4.66, 4.56 | 4.79, 4.63, 4.54 | |

- Over those 6 idle minutes the clusters' requests were held for a combined
  3 ms.
- `bw_kbps` while held (`force`): 200000000 to 50000000 updated all three
  cluster requests (`interconnect_summary`) and 10-thread STREAM fell to
  137/128 GB/s (the provider's lower step); back to `auto` dropped the
  requests to 0.
- apple-ave, 120 frames 1080p H.264: through the provider 2.49 / 2.52 /
  2.43 s, direct slot write 2.48 / 2.49 s, no vote 3.93 / 3.93 s; identical
  output in all three (PSNR 44.22 dB); votes go up and down per stream and
  the path is given back at power-off.
- No new warnings, faults or PMP crashes in the kernel log.
- CPU hotplug could not be exercised (the platform refuses to offline
  CPUs); that path is compile-tested only.

## Limitations and open items

- The GPU is not helped: its 3-20% shortfall on memory-bound work with the
  PMP running is not a CPU-request problem. t600x device trees have no PMP
  report entry for the GPU (t8112's have one). Making such an entry the
  GPU's power domain, as t8112 does, hung an M1 Max within seconds of the
  GPU firmware starting (3 of 3); reporting it once the GPU driver has
  bound is the approach of PR #20 (0035-0037).
- t6002 (two dies' worth of clusters and agents), t8112 and t8103 get no
  provider.
- Only the first video encoder (AVE0) has a node; other agents (decoder,
  ISP, display, neural engine) are not described yet.
- CPU hotplug paths are compile-tested only.
- The PMP device trees themselves are not part of this project
  ([consolidation-plan.md](consolidation-plan.md), "Keep out"): without
  them, none of this does anything.

## Hardware

M1 Pro and M1 Max (t6000, t6001) with the PMP running. Machines without the
PMP running: nothing is written, nothing is sampled. t6002, t8112, t8103:
no provider, no change (0030 also fixes t6002's report entries). Tested on
an M1 Max.

## Upstream status and provenance

Not submitted upstream. This project's work; the new files carry
`GPL-2.0-only OR MIT`, as the `pmp-report` driver they extend. As
LICENSING.md says: what they rely on was found from Apple's device tree
(the ADT of the restore image, as Asahi's own device trees are written),
Asahi's `pmp-report` driver and black-box measurement on Linux. Three
interface facts were first learned by
[aquarat/apple-m-series-ave-driver](https://github.com/aquarat/apple-m-series-ave-driver)
from macOS 13.5's kernelcache, for interoperability, and are documented
there (docs/75): the dashboard's read/write addressing, the numbering of
the request slots, and the layout of a request word. No code or data from
Apple's files is in these patches; the slot numbers and request steps are
facts of the hardware interface and of measurements.
