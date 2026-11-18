# thunderbolt-net: forwarding a peer's TSO packets

| | |
|---|---|
| patches | `packages/kernel/patches/0026-net-thunderbolt-Make-oversized-TSO-packets-forwardab.patch`, `0027-net-thunderbolt-Segment-TSO-packets-the-receiver-wou.patch` |
| package | `kernel` |
| pull requests | 0026: none of its own (commit `8e0c55e`, 7.2.11 `plus3`, before the PR history). 0027: #2 (7.2.11 `plus5`, now on branch `kernel-7.2` through #7) and #3 (7.3.1 `plus2`); on `main` through #9 |
| upstream source | [aquarat/apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux) `patches/tb-net/` 0007 and 0008 |
| related | [thunderbolt-net.md](thunderbolt-net.md) (0020-0025) |

## What it does

- **0026, receive side.** A received TCP packet larger than the MTU (a
  peer's TSO packet, reassembled from Thunderbolt frames) becomes a GSO
  packet, the way GRO builds them: the checksum the peer computed is
  verified and replaced with the pseudo-header checksum, `CHECKSUM_PARTIAL`
  is set, and `gso_size`/`gso_segs`/`gso_type` are filled in (`DODGY`, as
  the headers come from the peer). A bridge or router then segments it on
  the way out, in software or by the egress device's TSO.
- **0027, send side.** An `ndo_features_check` keeps TSO only for TCP
  packets whose `gso_size` equals the MTU minus their IP and TCP headers,
  the size the receiver will cut them at, and segments every other GSO
  packet in software before it is split into Thunderbolt frames: a lowered
  MSS, IPv6 with extension headers, encapsulated packets. 0027 also
  corrects 0026's comment, which said the local MTU's MSS is at most what
  the peer's segments used.

## Why

A ThunderboltIP peer does not segment TSO packets: it splits them into
Thunderbolt frames and the receiver reassembles one packet of up to 64 KiB.
Local delivery takes it as is, but a bridge drops it in
`is_skb_forwardable()` and IPv4/IPv6 forwarding answer "fragmentation
needed". With a thunderbolt-net interface bridged to an Ethernet uplink,
TCP from the peer to the LAN ran at a few hundred kB/s (only segments that
happened to fit got through) unless TSO was turned off on the peer, which
caps it at about 5.4 Gb/s.

ThunderboltIP has no field for the segment size, so 0026 derives the MSS
from the local MTU. That matches the peer's segments only when they were
full-sized. When path MTU discovery or an MSS clamp has lowered the
sender's MSS (a VPN, tunnel or overlay network behind the bridging Mac),
the forwarded segments are too large for the smaller hop, which drops them;
the sender is already at the lower MSS, so TCP stalls at a congestion
window of about two segments. Uploads from a Thunderbolt peer to a service
behind an overlay network with MTU 1450 ran at under 1 MB/s instead of
about 150 MB/s, with a "fragmentation needed" message for nearly every
segment.

## Design and alternatives

- **Rebuild GSO metadata on receive (0026)** rather than asking every peer
  to turn TSO off: TSO off costs most of the link's throughput.
- **Fix the MSS mismatch at the sender (0027).** Carrying the segment size
  in the frame header would change the wire protocol that macOS and other
  peers speak, and the receiver cannot know the MTU of hops beyond it, so
  the sender has to do this. A full-sized MSS, the common case, keeps the
  TSO path. Both ends of the link are assumed to have the same MTU.
- Local delivery is unchanged apart from the checksum being verified in
  thunderbolt-net instead of by TCP.

## Testing

0026, Mac-to-Mac over 2x20 Gb/s (M1 Max to M1 Max), MTU 1500, peer TSO on,
from the peer through a bridge into a veth (MTU 1500):

| | forwarded |
|---|---|
| before | 0.01 Gb/s (418 retransmits) |
| after | 19.1-19.5 Gb/s, 0 retransmits, IPv4 and IPv6 |
| peer TSO off (the old workaround) | 5.4 Gb/s |

A client behind the bridge's Ethernet uplink went from 1.3 Mbit/s to its
Wi-Fi rate (42 Mbit/s). Local delivery stayed at 20.4-20.5 Gb/s.
SHA-256 checked 1 GiB transfers, forwarded and delivered locally, matched.
It works with GRO on or off on the receiver.

0027 (#2, #3): full 16k RPM build of the 7.2.11 tree, the thunderbolt-net
module compiled cleanly with W=1 against 7.3.1, checkpatch clean. Hardware
validation (a sub-1500-MTU path, an MSS clamp, MTU 1500 forwarding
throughput) was in progress when they merged; its results are not recorded
in this repository.

## Limitations and open items

- 0027's hardware validation results are not recorded here (see Testing);
  [consolidation-plan.md](consolidation-plan.md) lists Thunderbolt
  networking with 0027 on 7.3.1 as still to be run.
- Every sender needs 0027; a peer without it (macOS, another OS) can still
  send TSO packets with a lowered MSS that this receiver re-segments at its
  own MTU.
- Both ends are assumed to use the same MTU.

## Hardware

Not Apple-specific: any thunderbolt-net host. Tested between M1 Max Macs.

## Upstream status and provenance

Not submitted upstream; kept in upstream form (`Fixes:` and `Assisted-by:`
tags) in apple-silicon-thunderbolt-linux. This project's work, written
against the Linux networking stack's GSO/GRO and thunderbolt-net sources.
No Apple code or data is involved.
