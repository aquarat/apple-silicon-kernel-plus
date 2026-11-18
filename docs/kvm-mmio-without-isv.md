# KVM: MMIO loads and stores without an instruction syndrome

| | |
|---|---|
| patch | `packages/kernel/patches/0002-KVM-arm64-emulate-MMIO-ldst-without-ISV.patch` |
| subject | KVM: arm64: emulate MMIO load/store-immediate aborts without a syndrome |
| package | `kernel`; on by default, `kvm.emulate_nisv_ldst=0` turns it off |
| pull requests | none of its own: it came with the first kernel package (commit `1e1f452`, off by default) and was turned on by default in the 7.2.11 kernel (commit `4a98204`), both before the PR history; rebased in #9 and to 7.3.4 in #21 |
| more | [kvm-macos-guests.md](kvm-macos-guests.md#0002-mmio-loadsstores-without-a-syndrome-on-by-default) (switching it, checks) |

## What it does

When a guest's stage-2 data abort on an MMIO address has no valid
instruction syndrome (ISV=0), KVM resolves the guest PC's IPA with `AT
S1E1R` in the exit path while the guest's EL1 regime is live, reads the
instruction, and decodes single-register LDR/STR (immediate: unsigned
offset, unscaled, pre- and post-indexed; general-purpose registers only).
It checks the decoded address against FAR, builds a valid syndrome, applies
the base write-back and lets the normal MMIO path (the in-kernel vGIC or
user space) complete the access. Every other instruction behaves as before.

## Why

XNU programs the GIC redistributor with a pre-indexed store (`str w9, [x8,
#128]!`). The CPU reports the abort without a syndrome, which stock KVM
cannot complete, so a macOS guest panics early in boot. Linux guests never
hit this path: their MMIO accesses carry a syndrome.

## Design and alternatives

- **Decode in KVM, a narrow set.** Only single-register LDR/STR immediate
  forms are decoded; anything else gets the old behaviour, so a guest that
  worked before is not affected.
- **The alternative KVM already offers** is `KVM_EXIT_ARM_NISV`: a VMM can
  ask for these exits and emulate the instruction itself. That needs an
  instruction decoder in the VMM, and the access it would have to complete
  here targets the in-kernel vGIC, which a user-space VMM does not own.
  This repository records no further comparison. With the emulation on, a
  VMM that asked for those exits no longer gets them for the forms KVM now
  decodes.
- **Default.** Off up to the 7.1.13 kernels (a package,
  `qemu-vmapple-kvm-nisv`, turned it on); on from 7.2.11, because macOS
  guests need it, Linux guests never trigger it, and KVM still behaves as
  before for every access it does not decode. The package is retired.
  `CONFIG_KVM=y`, so the switch is a kernel command-line parameter or the
  sysfs file `/sys/module/kvm/parameters/emulate_nisv_ldst`, not
  `/etc/modprobe.d`.

## Testing

Recorded in the commit message: kernel `7.1.13-401.asahi` on an M1 Max
(t6001), macOS 13 and 26 guests; then rebased to 7.2.11 with the default
changed to on. The macOS guest tests of [kvm-apple-pauth.md](kvm-apple-pauth.md)
(7.2.11, macOS 13.6 and 26.4) ran with it on, and so did the macOS 26.4 and
13.6 guest jobs on an M1 Ultra Mac Studio with 7.3.1 `plus3`. No separate
measurements were recorded.

## Limitations and open items

- Only single-register LDR/STR immediate forms on general-purpose
  registers; pairs, SIMD/FP registers and other addressing modes still fail
  as on a stock kernel.

## Hardware

Any arm64 host running KVM; the instructions it decodes are architectural.
Used on M1 Max (t6001) and M1 Ultra (t6002) hosts with macOS guests.

## Upstream status and provenance

Not submitted upstream. This project's work (LICENSING.md, CREDITS.md),
written against the Linux KVM sources and the Arm architecture's
instruction encodings. No Apple code or data is involved: the faulting
instruction is read from guest memory at run time.
