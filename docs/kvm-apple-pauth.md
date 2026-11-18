# KVM: Apple PAuth virtualization state

| | |
|---|---|
| patch | `packages/kernel/patches/0001-KVM-arm64-Handle-Apple-PAuth-virtualization-state-under-VHE.patch` |
| subject | KVM: arm64: Handle Apple PAuth virtualization state under VHE |
| package | `kernel` (always on) |
| pull requests | #6 (7.3.1 rebase), #7 (7.2.11 line), #9 (7.3.1 on `main`); the `plus4` rewrite on 7.2.11 predates the PR history (commit `5c4d277`) |
| more | [kvm-macos-guests.md](kvm-macos-guests.md) (how to use it, checks), [kvm-pauth-provenance.md](kvm-pauth-provenance.md) (how it was written, full test record) |

## What it does

KVM handles Apple's pointer-authentication registers for guests:

- APCTL and KERNKEYLO/HI become per-vCPU state (reset to 0), loaded and
  saved through their EL12 aliases like the other EL1 registers under VHE,
  and reachable from user space with `KVM_GET_ONE_REG`/`KVM_SET_ONE_REG`
  (`ARM64_SYS_REG(3, 6, 15, 15, 0)` and `ARM64_SYS_REG(3, 6, 15, 2, 3/4)`,
  listed by `KVM_GET_REG_LIST`);
- each VM gets a random 128-bit VM key at creation, written to
  APVMKEYLO/HI_EL2 on every vCPU load with APSTS_EL12 set to 1, never
  visible to the guest or user space, cleared when the VM is destroyed;
- every guest access to these registers gets UNDEF.

`dmesg` prints `kvm [1]: Apple PAuth virtualization state enabled` when it
is active.

## Why

macOS guests on QEMU's `vmapple` machine manage their pointer
authentication keys through vendor hypercalls, which QEMU serves by writing
the guest's key registers with `KVM_SET_ONE_REG`. Stock KVM knows only the
architectural keys. Without this patch QEMU's `KVM_SET_ONE_REG` for
`APCTL_EL12` fails with `ENOENT` at XNU's first PAuth hypercall
(`0xc1000000`), and QEMU stops the guest with `vmapple: platform hypercall
0xc1000000 failed: No such file or directory` (the negative control in
[kvm-pauth-provenance.md](kvm-pauth-provenance.md#testing)).

## Design and alternatives

- **CPU detection by MIDR.** No ID register advertises these registers, a
  probe would fault on a CPU without them, and later Apple parts lock them.
  The capability `ARM64_HAS_PAUTH_VIRT_APPLE` matches the M1 and M2 rows of
  m1n1's table of parts whose Apple system registers are unlocked. M3 is
  unlocked too but left out until KVM runs there. The existing
  `ARM64_HAS_ACTLR_VIRT` capability was not used, because it matches every
  Apple part from M2 on, including the locked ones.
- **VHE on bare metal only.** A static key is enabled only with VHE and no
  SMCCC conduit. A nested guest hypervisor also runs at (virtual) EL2 and
  sees the host's MIDR, but there these registers UNDEF; Apple machines have
  no firmware below EL2, so a conduit means a hypervisor is below. nVHE,
  hVHE and protected mode are unchanged.
- **A random VM key per VM, not a constant.** The specification required
  a random key per VM rather than a fixed value. The trade-off: a
  guest that writes its own keys in Apple mode (APCTL bit 0) signs
  differently in a new VM, so migrating such a guest into a new VM, or
  restoring a snapshot there, would fail pointer authentication. Keys set
  through `KVM_SET_ONE_REG`, which is how QEMU serves macOS's hypercalls,
  sign the same in every VM, and a macOS 26 guest migrated to a file
  resumed in a new QEMU process.

## Testing

On an M1 Max (t6001), 7.2.11 with this patch (`plus4`):

- macOS 26.4 guests at 4, 6 and 8 vCPUs (Swift build and simulator
  unit-test workload), a macOS 13.6 guest, and a macOS 26 and a macOS 13
  guest at once on the same four CPUs: all passed;
- a Linux guest's own pointer authentication, and the host's before and
  after about three hours of guests: passed;
- every guest access to the new registers gets UNDEF; the registers are
  listed, reset to 0, and round-trip across thousands of load/put cycles of
  two VMs on one CPU;
- negative control, the same tree without 0001: macOS 13.6 and 26.4 guests
  fail as described under Why, and two VMs give the same signatures.

The 7.3.1 rebase (#6) changed context in two hunks only (`struct kvm_arch`
and `arch/arm64/tools/cpucaps`); it is build-tested (the KVM and arm64
objects compile, the new symbols are present). After #9 merged, on an M1
Ultra Mac Studio with 7.3.1 `plus3`, a macOS 26.4 and a macOS 13.6 guest
each ran a CI job to completion (exit 0).

## Limitations and open items

- On 7.3.1 only the guest jobs above have run; the full test list above
  (several vCPU counts, two guests at once, the negative control) was run on
  7.2.11.
- nVHE paths not tested (`kvm-arm.mode=nvhe` is rejected on M1 Max); no M2
  hardware tested.
- Migration of a guest that uses Apple-mode keys of its own into a new VM
  fails by design (see Design).

## Hardware

M1 and M2 CPUs (t8103, t6000, t6001, t6002; t8112, t6020, t6021, t6022),
KVM in VHE mode on bare metal. Tested on t6001 and (plus3 and earlier) on
t6002. Every other CPU: no change.

## Upstream status and provenance

Not submitted upstream. This project's work, an independent implementation:
up to 7.2.11 `plus3` (7.3.1 `plus2`), 0001 was a rebase of a Linux 6.19
patch by Anees Iqbal; from `plus4` (7.3.1 `plus3`) it was rewritten
clean-room style from m1n1's register definitions (`GPL-2.0-or-later`), the
pinned Asahi tree, QEMU's `target/arm/kvm-vmapple.c` and a functional
specification, by an implementer without access to the earlier patch. The
process, its sources and two disclosed incidents are in
[kvm-pauth-provenance.md](kvm-pauth-provenance.md); LICENSING.md and
CREDITS.md say the same. Anees Iqbal first showed that macOS guests need
this state; the commit message credits him.
