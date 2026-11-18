# Tunnelled PCIe over Thunderbolt/USB4 (APCIEC)

| | |
|---|---|
| patches | `packages/kernel/patches/0010-dt-bindings-pci-Add-Apple-T600x-tunnelled-PCIe-contr.patch`, `0011-PCI-apple-Add-driver-for-the-T600x-tunnelled-PCIe-co.patch`, `0012-arm64-dts-apple-t600x-Add-tunnelled-PCIe-controllers.patch`, `0013-arm64-dts-apple-t600x-Enable-tunnelled-PCIe-on-j314-.patch` |
| package files | `packages/apple-silicon-thunderbolt/60-apciec-nvme-apst.rules` (package `apple-silicon-thunderbolt`) |
| config | `CONFIG_PCIE_APPLE_APCIEC=m` (`packages/kernel/configs/plus-aarch64.config`) |
| pull requests | none of their own: added in commits `aaa12fa` and `5f95446` (7.2.11, before the PR history); carried to 7.3.1 in #9 and rebased to 7.3.4 in #21 |
| upstream source | [aquarat/apple-silicon-thunderbolt-linux](https://github.com/aquarat/apple-silicon-thunderbolt-linux) `patches/` (commit `dfbc506`); its README has the full test record |

## What it does

- 0010: a DT binding, `apple,t6000-apciec`, for the PCIe root complex behind
  each USB4/Thunderbolt port of T600x SoCs. The controller is a clock
  provider and the port's DART references that clock.
- 0011: the `pcie-apple-apciec` host driver. It enables the port and its
  application clock, applies the bootloader-provided tunables, sets up the
  MSI window and RID-to-SID table as `pcie-apple.c` does, waits for a
  tunnel (`TUNSTAT`), trains the link (retrying at once on `LINK_DOWN`,
  which the first attempt on a new tunnel usually ends in) and only then
  scans the bus. On tunnel loss it removes everything below the root port
  and waits for the next tunnel. ASPM is disabled on all tunnelled links.
- 0012: APCIEC and DART nodes for USB4 ports 0-3 of die 0, disabled.
- 0013: enables them on the 14"/16" MacBook Pro (ports 0-2) and Mac Studio
  (ports 0-3) boards and adds the `usb4_N_pcie` aliases the bootloader uses
  to fill in the tunables.
- The udev rule turns NVMe APST off for drives behind an APCIEC root port
  only.

## Why

The Asahi tree has the Thunderbolt/USB4 host router driver but no driver for
the PCIe controllers that carry PCIe tunnels, so devices in Thunderbolt/USB4
enclosures (NVMe drives, for example) did not work. With APST on, a drive in
an ASM2464PD enclosure dropped the USB4 link about 15 s after going idle.

## Design and alternatives

- **The port block is `pcie-apple.c`'s**, with the same port register
  layout plus the tunnel reset handshake (`TUNCTRL`/`TUNSTAT`); the root
  port's link never leaves the SoC and runs over a tunnel the USB4
  connection manager builds.
- **The DART only responds while the port's application clock runs.** The
  controller therefore registers that clock and the DART node references
  it, so the DART cannot probe before the controller has started it and
  nothing is scanned before the DART is bound. No run-time DT changes are
  needed. An earlier lab driver created the DART with an `of_changeset`
  after enabling the port; that is not acceptable upstream.
- **Consequence: no unbinding.** Manual unbind is suppressed, as in
  `pcie-apple`: unbinding would unbind the DART first, whose device links
  unbind the PCI functions parents first, and a bridge losing its driver
  stops forwarding DMA (measured: 60 s of NVMe admin timeouts). Updating
  the module needs a reboot.
- **Tunnel arrival is polled** (every 200 ms for 60 s after probe or a loss,
  then every second); a notification from the connection manager would
  replace that.
- **ASPM off:** L1 across the tunnel drops the USB4 link within seconds.
- **Board parts are separate files** included from the T600x board files,
  because the shared `t600x-j314-j316.dtsi` and `t600x-j375.dtsi` are also
  used by T602x boards, which have no such controllers.
- **APST in user space, per drive.** In-kernel alternatives were evaluated:
  the controller driver cannot set nvme quirks (they come from nvme-pci's
  own tables; PCI fixups do not run from modules); an nvme-pci change that
  skips APST below tunnelled ports would affect all Thunderbolt NVMe and
  needs an upstream discussion; marking the root port external-facing would
  also make the devices "untrusted" (strict IOMMU, bounce buffers);
  `nvme_core.default_ps_max_latency_us=0` also turns APST off for the
  internal drive. The rule writes 0 to the controller's PM QoS latency
  tolerance, matched on the namespace's block device because the
  controller's attribute appears only after its own uevent.

## Testing

On a Mac Studio (M1 Max), rear port 3, ASM2464PD enclosure with a Samsung
SM961, asahi-wip 7.2.11:

- sequential 1M QD8 reads 3079 MiB/s, 4k random QD64x4 295k IOPS, crc32c
  write/verify clean;
- 10/10 software replugs with the namespace back in 3.8-3.9 s; 5 min idle
  without link loss (with the APST rule);
- a 1 h filesystem soak with 4 replugs passed, and passed again with the
  driver built into this project's 7.2.11 `plus1` kernel;
- later, alongside the Thunderbolt networking tests, a tunnelled NVMe drive
  on another port ran a crc32c write/verify load (838 GB verified, no
  errors) and kept working through three replugs.

Graphs are in the upstream repository's `docs/results/`.

## Limitations and open items

- Known issue: the USB4 link can drop under heavy load within about 20 s of
  a (re)connect (roughly 1 in 6 replug-then-read cycles; the USB4 PHY, not
  the PCIe side). In-flight I/O fails with EIO; no corruption seen. After
  such a drop the PCIe link may not return before the enclosure falls back
  to USB mass storage; a port power cycle or replug recovers it.
- No system suspend while a device is connected (the USB4 series refuses
  it); all functions behind one port share one DART stream; MSI/MSI-X only,
  no INTx.
- Not tested: ports 0-2, other enclosures, M1 Pro (t6000), M1 Ultra (t6002),
  MacBook Pros; the second die of the M1 Ultra is not described.
- NVMe over APCIEC on 7.3.1 is still to be run on hardware
  ([consolidation-plan.md](consolidation-plan.md)).

## Hardware

T600x: M1 Pro (t6000), M1 Max (t6001), M1 Ultra (t6002, die 0 only), on
j314/j316 (MacBook Pro) and j375 (Mac Studio) boards. Needs m1n1 1.6.1 or
later (it fills the tunables) and the Asahi USB4 series. Tested on t6001
only.

## Upstream status and provenance

Not submitted upstream; maintained in upstream form (`git format-patch`,
`Assisted-by:` tags) in apple-silicon-thunderbolt-linux. This project's
work: driver `GPL-2.0-only`, binding `GPL-2.0-only OR BSD-2-Clause`, DTS
`GPL-2.0+ OR MIT`. The port programming follows `pcie-apple.c`; the
per-device register tunables are copied into the device tree by m1n1 at
boot, and neither the driver nor the DTS contains tunable values.
LICENSING.md does not list this driver among the reverse-engineered parts,
and this repository does not record further detail of how the tunnel
register behaviour and node values were established beyond the above and
testing on hardware.
