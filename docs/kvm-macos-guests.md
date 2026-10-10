# KVM for macOS guests

macOS guests (QEMU's `vmapple` machine, the platform of Apple's
Virtualization.framework) need two things stock KVM does not do. This
project's kernel adds both, in `packages/kernel/patches/`.

## 0001: Apple PAuth virtualization state (always on)

On entry to a guest, KVM programs Apple's VM key (APVMKEYLO/HI_EL2) and
APSTS, and saves and restores APCTL, KERNKEYLO and KERNKEYHI through their
EL12 aliases. QEMU reads and writes them through the one-register ABI.
Without it macOS stops in launchd as soon as it uses signed pointers.

It only acts on CPUs with Apple's ACTLR virtualization capability (M1:
`ARM64_HAS_ACTLR_VIRT_APPLE`, M2: `ARM64_HAS_ACTLR_VIRT`), and only for
guests. The host's own PAuth state is not touched.

Origin: a rebase of Anees Iqbal's Linux 6.19 patch (CREDITS.md).

## 0002: MMIO loads/stores without a syndrome (off by default)

XNU writes the GIC redistributor with a pre-indexed store
(`str w9, [x8, #128]!`). The CPU reports the stage-2 abort without a valid
instruction syndrome (ISV=0), which KVM cannot complete, so the guest
panics early in boot. With the emulation on, KVM decodes single-register
LDR/STR (immediate) from guest memory, checks the address against the fault
address, applies the base write-back and completes the access through the
normal MMIO path. Other instructions behave as before.

It is a module parameter of the built-in `kvm` module, default **off**:

| how | effect |
|---|---|
| `sudo dnf install qemu-vmapple-kvm-nisv` | a tmpfiles.d rule writes `Y` at every boot and on install; removing the package writes `N` |
| `sudo grubby --update-kernel=ALL --args=kvm.emulate_nisv_ldst=1` | kernel command line, from the next boot |
| `echo Y \| sudo tee /sys/module/kvm/parameters/emulate_nisv_ldst` | now, until reboot |

`/etc/modprobe.d` does not work here: KVM is built in (`CONFIG_KVM=y`), so
its parameters come from the kernel command line or from sysfs.

With it off, KVM behaves exactly as without the patch; Linux guests do not
need it.

## Checks

```sh
uname -r                                           # ...asahi.plus<N>.fc44.aarch64+16k
cat /sys/module/kvm/parameters/emulate_nisv_ldst   # Y for macOS guests
dmesg | grep -E "ACTLR virtualization|VHE mode"
```

## Userspace

QEMU: `qemu-vmapple` (this project). The VM tooling (restore, golden
images, runners) is in
[aquarat/apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest).
With the Reims GPU, run QEMU with `VK_DRIVER_FILES` pointing at
`mesa-honeykrisp-plus` (`honeykrisp-plus qemu-vmapple ...`).
