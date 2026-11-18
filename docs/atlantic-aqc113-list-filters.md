# atlantic: AQC113 list filters relative to the base index

| | |
|---|---|
| patch | `packages/kernel/patches/0003-net-atlantic-AQC113-Enable-list-filters-relative-to-.patch` |
| subject | net: atlantic: AQC113: Enable list filters relative to the base index |
| package | `kernel` |
| pull requests | none of its own: added with the 7.2.11 kernel (commit `4a98204`) and rewritten for 7.2.15 (commit `f902567`), before the PR history; carried to 7.3.1 in #9; its compile check was fixed in #13 |

## What it does

In `hw_atl_b0_hw_packet_filter_set_int()`, the loop that enables the L2
unicast/multicast list filters compares each filter against its position in
the list instead of its absolute index. With the B0 controller's base index
of 1 the condition is the same as before.

## Why

Since Linux 7.2's AQC113 (ATL2) filter rework, the station MAC address is
programmed at the firmware-reported `l2_filters_base_index` and the
unicast/multicast list follows it at base + 1 .. base + count. Asahi's fix
"net: atlantic: AQC113: Fix hw_packet_filter_set for l2 filter base index >
0" starts the loop at base + 1, so the station MAC filter stays on, but the
loop still enables filter *i* only when *i* ≤ `mc_list_count`, an absolute
index. `aq_nic_set_multicast_list()` programs the list first and sets the
packet filter last, so with a non-zero base every list entry is switched off
again unless the list is longer than the base index.

On a Mac Studio's built-in AQC113 10GbE port the firmware reports base
index 9. Unicast to the port's own address works, but multicast and
secondary unicast addresses are dropped unless the port is promiscuous or
in all-multicast mode.

## Design and history

- **7.2.11 (first version).** Before Asahi's fix existed, 0003 was a larger
  patch ("net: atlantic: atl2: keep the station MAC unicast filter
  enabled"): ATL2 got its own `packet_filter_set` that enabled the unicast
  filters relative to the base index and bounded the multicast list. On
  the built-in AQC113 of an M1 Max Mac Studio unicast RX had stopped with
  eight multicast addresses and came back when a ninth was added (the base
  index is 9); broadcast still worked, so DHCP succeeded while unicast was
  lost.
- **7.2.15 and later (this version).** Asahi's tree keeps the station MAC
  filter on itself, so only the comparison in the loop is left to fix. The
  rewrite enables the same filter slots as the earlier patch did.

## Testing

- The first version: 7.2.11 on an M1 Max Mac Studio, built-in 10GbE:
  unicast RX works with promiscuous mode off.
- This version: build only (7.2.15, Asahi `6ba0637d1ed9`; then 7.3.1). The
  CI compile check (#10) did not actually compile it at first, because the
  patched file is built by its parent directory's Makefile; #13 fixed that,
  and the check now fails if a touched C file produces no object.

## Limitations and open items

- Not yet run on an AQC113 port with 7.3.1 (listed in
  [consolidation-plan.md](consolidation-plan.md), "Still to test on
  hardware").

## Hardware

Aquantia/Marvell AQC113 (ATL2) controllers with a non-zero filter base
index, such as the built-in 10GbE port of the Mac Studio. Other atlantic
controllers (base index 1): no change.

## Upstream status and provenance

Not submitted upstream; it applies on top of the Asahi tree's own AQC113
fix. This project's work (LICENSING.md, CREDITS.md), written
from the Linux driver source and observed on hardware.
