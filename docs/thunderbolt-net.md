# Thunderbolt networking on Apple silicon (thunderbolt-net)

| | |
|---|---|
| patches | `packages/kernel/patches/0020-thunderbolt-apple-Enable-E2E-flow-control-on-Tx-ring.patch`, `0021-net-thunderbolt-Enable-E2E-flow-control-on-the-Tx-ri.patch`, `0022-arm64-dts-apple-t600x-Mark-the-USB4-NHIs-as-DMA-cohe.patch`, `0023-net-thunderbolt-Fix-a-lost-Tx-queue-wakeup.patch`, `0024-net-thunderbolt-Use-a-page-pool-for-Rx-buffers.patch`, `0025-thunderbolt-apple-Derive-a-per-machine-host-router-U.patch` |
| package files | `packages/apple-silicon-thunderbolt/61-thunderbolt-net-threaded.rules` (package `apple-silicon-thunderbolt`) |
| pull requests | none of their own: added in commit `cc9112b` (7.2.11 `plus2`, before the PR history); carried to 7.3.1 in #9 and rebased to 7.3.4 in #21 |
| upstream source | [aquarat/apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux) `patches/tb-net/` 0001-0006; its README has the full test record |
| related | [thunderbolt-net-tso-forwarding.md](thunderbolt-net-tso-forwarding.md) (0026, 0027: forwarding a peer's TSO packets) |

## What it does

| patch | change | Apple-specific? |
|---|---|---|
| 0020 | a `tx_e2e` flag in `struct tb_nhi`, set for the Apple NHI: the host interface needs end-to-end (E2E) flow control on its Tx rings too | yes |
| 0021 | thunderbolt-net enables E2E on its Tx ring when the NHI sets `tx_e2e` | no (only acts with the flag) |
| 0022 | the t600x USB4 NHIs are marked `dma-coherent` | yes |
| 0023 | fixes a lost Tx queue wakeup in thunderbolt-net | no |
| 0024 | a page pool for thunderbolt-net's Rx buffers | no |
| 0025 | a per-machine host router UID instead of the bootloader's placeholder | yes |
| udev rule | threaded NAPI and GRO off on thunderbolt-net interfaces | policy |

## Why

- **Lost frames (0020, 0021).** On the Apple NHI, E2E flow control works
  only when it is enabled on both rings of a channel. thunderbolt-net
  enables it on the Rx ring alone; the register read-back shows the Rx ring
  set up correctly (options `0x90001000`) and the Tx ring without its E2E
  bit (`0x80000000`), which then never waits for credits. Once the receiver
  falls behind it runs out of descriptors and drops frames (counted as
  `rx_missed_errors`; TCP retransmits). Turning thunderbolt-net's `e2e`
  parameter off made no difference.
- **Cache maintenance (0022).** The NHIs sit on the same coherent fabric as
  the tunnelled PCIe controllers, already marked `dma-coherent`; without the
  property every 4 KiB ring frame gets cache maintenance.
- **A stopped interface (0023).** If all Tx completions run between the
  free-buffer check in `tbnet_start_xmit()` and `netif_stop_queue()`, the
  queue stays stopped with every buffer free and the interface never sends
  again; carrier stays up and nothing is logged. Seen after about 19 minutes
  of bidirectional iperf3 at 15 Gb/s per direction.
- **CPU-bound receive (0024).** Every received frame took a fresh page,
  cleared (16 KiB with `init_on_alloc=1` on a 16K-page kernel) and mapped
  and unmapped through the strict NHI IOMMU domain. The Rx NAPI thread
  spent about 44% of its time in `clear_page()` and 10% in IOMMU paths and
  saturated a CPU at 7-8 Gb/s.
- **Identical UIDs (0025).** m1n1 copies the host router DROM from the
  Apple device tree, whose UIDs are placeholders shared by every Mac of a
  family (on some ports just the port index). Two Macs cabled between the
  same port index announce the same XDomain UUID: the connection is treated
  as a loop, lane bonding is skipped, and thunderbolt-net gives both ends
  the same MAC address, which also breaks bridging several Macs.
- **udev rule.** Apple's interrupt controller cannot set interrupt affinity
  and delivers most ring interrupts to the efficiency cores, where softirq
  NAPI runs; a NAPI thread can run on a performance core. GRO reorders
  segments on this path and causes spurious retransmits.

## Design and alternatives

- **0020/0021: a per-NHI flag**, not E2E on every Tx ring: hosts that do not
  set it keep today's behaviour. The Falcon Ridge E2E workaround, for one,
  sends its Rx credits to an unused HopID, so a Tx ring that waited for
  them would stall. The new member sits in existing padding, so `struct
  tb_nhi`'s layout does not change.
- **0023** re-checks the free buffers after stopping the queue, with
  barriers pairing the callback's producer-index update and the stop bit,
  as `netif_txq_try_stop()` does.
- **0024** keeps Rx pages DMA mapped in a page pool and recycles them
  through the skbs; the pool syncs only the part the hardware writes. A
  bigger Rx ring was the alternative: before the pool, 1024 entries gave
  8.1 instead of 7.2 Gb/s; with the pool, 512 or 1024 entries give the same
  single stream and about 10% more bidirectional for 2-4x the memory
  (4 MiB per interface at 256 entries on 16K pages), so the ring size is
  left at 256.
- **0025** treats the UIDs as real only when all host routers of the
  machine share the same non-zero upper bits (the layout a per-machine
  value with the port index in the low byte would have). Otherwise it
  derives the UID from a salted SHA-256 of the machine serial number, so
  the serial is not exposed, keeping the port index in the low byte. The
  fix-up runs before the link can come up.
- **udev rule, not a kernel default**, so it can be removed: deleting the
  GRO line keeps GRO on.

## Testing

Same-host loopback between two USB4 ports of a Mac Studio (M1 Max, one end
in a network namespace, 20 Gb/s x2, MTU 65522, iperf3):

| step | per direction | bidirectional | lost frames |
|---|---|---|---|
| unpatched | 3.4 Gb/s | | thousands per run |
| + `dma-coherent` (0022) | 4.0-4.2 Gb/s | 2.4 + 2.3 Gb/s | thousands per run |
| + Tx E2E (0020, 0021) | 4.8 Gb/s | 2.3 + 2.3 Gb/s | 0 |
| + Rx ring 1024, threaded NAPI, GRO off (no page pool) | 8.2 Gb/s | 7.4 + 7.4 Gb/s | 0 |
| 0020-0024, ring 256, threaded NAPI, GRO off | 21.2 Gb/s | 15.2 + 14.6 Gb/s | 0 |

- 0021: TCP retransmits fell from 1600-5600 to 200-700 per 15 s run.
- 0022: a 1 h bidirectional soak with periodic SHA-256 checked transfers
  showed no corruption.
- 0024: at a fixed 5 Gb/s single stream, the Rx NAPI thread fell from 59%
  to 17% of a CPU and the whole loopback from 0.86 to 0.40 CPUs; MTU 1500
  gives the same rates; with the driver defaults (softirq NAPI, GRO on) a
  single stream went from 5.1 to 9.5 Gb/s.
- 0020-0024: a 30 min bidirectional run averaged 15.2 + 14.7 Gb/s with no
  lost frames, 28 TCP retransmits in total and every SHA-256 checked
  1 GiB transfer intact, while a tunnelled NVMe drive on a third port ran a
  write/verify load. Before 0023 the same run stopped transmitting after
  19 minutes.
- 0025: the host routers got distinct UIDs; Mac-to-Mac between an M1 Max
  Mac Studio and an M1 Max MacBook Pro (whose routers carry the same
  placeholder UIDs) gave distinct XDomain UUIDs and MACs and a bonded
  20 Gb/s x2 link: 21.4 / 19.9 Gb/s single stream at MTU 1500 with GRO off,
  14.7 + 14.2 Gb/s bidirectional, no lost frames.
- udev rule: with 0024, threaded NAPI takes a single stream from 13-14 to
  17 Gb/s with background load on every core; Mac-to-Mac at MTU 1500, GRO
  on cost about 20% (16.9 against 21.4 Gb/s) with hundreds of retransmits
  per 15 s run.
- In longer use, the series runs a small star network: one Mac bridges its
  10GbE port and its Thunderbolt ports for other Macs (an M1 Mac mini at
  about 18.5 Gb/s each way, an M1 Ultra Mac Studio at 15.9 / 18.9 Gb/s)
  that reach the LAN only over Thunderbolt; both survive reboots of either
  end.

## Limitations and open items

- Not tested against Intel/AMD hosts or macOS peers.
- On an M1 Mac mini one Type-C port controller occasionally fails to probe
  at boot (an i2c timeout), and that port then never links; a Mac that
  depends on the cable should retry the bind.
- Known USB4 link drop under heavy load shortly after a reconnect (see
  [thunderbolt-pcie-apciec.md](thunderbolt-pcie-apciec.md)).
- The Rx ring size is a compile-time constant (256).
- On 7.3.1 `plus3` the star network above was re-checked (every peer on
  a 20 Gb/s x2 link, 17-19 Gb/s to the bridging Mac; see
  [thunderbolt-net-tso-forwarding.md](thunderbolt-net-tso-forwarding.md#testing));
  the single-machine loopback numbers were not re-measured.

## Hardware

0020 and 0025 act only on the Apple NHI (t8103, t8112, t600x as the Asahi
tree describes them); 0022 is t600x only; 0021, 0023, 0024 are generic
thunderbolt-net changes. Tested Mac-to-Mac between t6001, t8103 and t6002.

## Upstream status and provenance

Not submitted upstream; kept in upstream form (`git format-patch`, `Fixes:`
and `Assisted-by:` tags) in apple-silicon-thunderbolt-linux. This project's
work, written against the Linux thunderbolt and thunderbolt-net sources and
the Asahi USB4 series (Sven Peter's), with behaviour found by register
read-back and measurement on hardware. 0025 uses the machine serial number
only as a salted hash input; the serial is not exposed.
