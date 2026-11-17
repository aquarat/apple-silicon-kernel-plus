# Kernel patch 0001: how it was written

`packages/kernel/patches/0001-KVM-arm64-Handle-Apple-PAuth-virtualization-state-under-VHE.patch`
makes KVM handle Apple's pointer-authentication virtualization state, which
macOS guests on QEMU's `vmapple` machine need
([kvm-macos-guests.md](kvm-macos-guests.md)).

## Why it was rewritten

**Up to `plus3`.** Patch 0001 was a rebase of a Linux 6.19 patch by Anees
Iqbal (steelbrain), from
[steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64)
(`657bb24`). That repository has no licence. A licence was asked for in
[its issue 1](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64/issues/1)
on 2026-10-23. No answer had come by 2026-11-10. Downstream projects (for
example omvm, for Omarchy) could not package a kernel with it.

**2026-11-11.** He released the patches in that repository into the public
domain
([comment](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64/issues/1#issuecomment-6789795685))
and announced that he would archive the repository. This project keeps the
independent implementation described here; nothing of his patch returns.

**From `plus4`.** 0001 is an independent implementation. Two things made
that practical:
- Most of what such a patch contains is set by the hardware and by KVM's
  structure: register encodings, the registers QEMU expects to reach, and
  where KVM saves and restores EL1 state.
- All of the hardware facts are already published in m1n1 under
  `GPL-2.0-or-later`.

## Process (2026-11-10)

It was written clean-room style, in two separate roles.

**1. Specification.** Someone who had read the old patch wrote a functional
specification. It contained:
- the register encodings, cited to m1n1:
  - `src/cpu_regs.h`;
  - `proxyclient/m1n1/apple_regs.json`;
  - `src/hv/hv.c` and `proxyclient/m1n1/hv/__init__.py` for the VM-key
    set-up;
  - `src/chickens.c` for which CPUs have the registers unlocked;
- the user-space interface QEMU uses: aquarat/qemu-reims-vgpu
  `target/arm/kvm-vmapple.c`;
- requirements:
  - only on CPUs that have the registers, and otherwise no change;
  - per-vCPU state;
  - a random VM key per VM, not a fixed constant;
  - the exact one-register IDs QEMU uses;
  - UNDEF for guest accesses;
  - no effect on the host;
- a test plan.

It contained no code, and it did not describe the old patch.

**2. Implementation.** A separate implementer (an AI agent with no prior
context) wrote the patch from:
- that specification;
- m1n1;
- the pinned Asahi kernel tree;
- the QEMU file above.

The implementer was told not to open the old patch, anything derived from
it, or any kernel tree or build that contains it. It confirmed it didn't.

**Sources the implementer used**
- The specification.
- m1n1 at `6ee64bdd`: the files above, plus `proxyclient/m1n1/sysreg.py`.
- AsahiLinux/linux `asahi-wip` at `e09c62843a8e`, fetched fresh.
- For the 7.1 variant, Fedora Asahi `kernel-7.1.13-401.asahi` from
  gitlab.com/fedora-asahi/kernel-asahi.
- aquarat/qemu-reims-vgpu `c6d87a84`: `target/arm/kvm-vmapple.c`, and the
  migration-blocker code of the `vmapple` devices.
- This repository's `kernel-plus.conf`, `make-srpm.sh`, the header of
  patch 0002 and `packages/kernel/README.md`.
- The VM flow's README and scripts in aquarat/apple-macos-arm64-vm-guest,
  but not its `patches/` or its history.

**How the old patch was kept out of the builds.** The test kernels were
built from a copy of this repository with the old 0001 removed by file
name, unopened. The checks:
- the SRPM's patch hashes match the new file;
- the new symbols are present in `System.map`;
- a control build without any PAuth patch has none of them.

## Incidents, disclosed

**(a) A summary line.** While looking up the package layout, the
implementer read one line of this repository's `packages/kernel/README.md`
that summarised the old 0001: that it "only acts on Apple CPUs with ACTLR
virtualization (M1, M2), and only for guests". The new patch does not use
the ACTLR capabilities. It matches CPUs by MIDR against m1n1's list, for
reasons given in its commit message.

**(b) Observing the old kernel, after the code was final.** A test reboot
failed, and the test machine fell back to its default kernel, which carried
the old patch. Without noticing, the implementer ran its own black-box test
and a `dmesg` search on that kernel. What it saw:
- which register IDs that kernel lists;
- that signatures behave the same way;
- that it prints no capability line.

This was about 3.5 hours after the code was final; the patch-id was
unchanged before and after. The implementer then stopped, deleted what it
had captured, and afterwards changed only a sentence in the commit message.

Neither incident gave the implementer any of the old patch's code.

## Testing

On an M1 Max (t6001), kernel `7.2.11-900.asahiwip` with the new patch and
QEMU unchanged:
- **macOS 26.4 guests:** four runs at 4, 6 and 8 vCPUs; the Swift build and
  simulator unit-test workload passed every time.
- **A macOS 13.6 guest:** passed.
- **Two macOS guests at once on the same four CPUs:** passed.
- **A Linux guest:** its own pointer authentication passed.
- **The host's own pointer authentication:** passed before and after about
  three hours of guests.
- **Guest accesses:** every access to the new registers gets UNDEF.
- **The KVM interface:** the registers are listed, reset to 0, and
  round-trip values across thousands of load/put cycles of two VMs on one
  CPU.

**Negative control (2026-11-11).** The same tree and configuration built
without 0001 (`7.2.11-900.asahiwip.nopac1`; none of the new symbols in
`System.map` or `/proc/kallsyms`), on the same machine:
- **macOS 26.4 and macOS 13.6 guests:** both fail as expected. iBootStage2
  completes; at XNU's first PAuth hypercall (`0xc1000000`) QEMU's
  `KVM_SET_ONE_REG` for `APCTL_EL12` returns `ENOENT`, and QEMU stops the
  VM with `vmapple: platform hypercall 0xc1000000 failed: No such file or
  directory`.
- **The KVM interface:** none of the three Apple register IDs is listed;
  reading or writing them returns `ENOENT`; two VMs produce the same
  signatures, where the patched kernel gives them different ones.
- **The host's own pointer authentication:** passed.

**Not tested:**
- the nVHE paths (`kvm-arm.mode=nvhe` is rejected on M1 Max);
- M2 hardware.

## Credit

Anees Iqbal first showed that macOS guests under KVM need this state. The
commit message says so, and [CREDITS.md](../CREDITS.md) credits him for it.
He is not named as the patch's author, because he did not write this code.
