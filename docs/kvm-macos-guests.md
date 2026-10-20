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

## 0002: MMIO loads/stores without a syndrome (on by default)

XNU writes the GIC redistributor with a pre-indexed store
(`str w9, [x8, #128]!`). The CPU reports the stage-2 abort without a valid
instruction syndrome (ISV=0), which KVM cannot complete, so the guest
panics early in boot. With the emulation on, KVM decodes single-register
LDR/STR (immediate) from guest memory, checks the address against the fault
address, applies the base write-back and completes the access through the
normal MMIO path. Other instructions behave as before.

It is a module parameter of the built-in `kvm` module, default **on** from
the 7.2.11 kernel (up to 7.1.13 it was off and had to be turned on):

| how | effect |
|---|---|
| nothing | on |
| `sudo grubby --update-kernel=ALL --args=kvm.emulate_nisv_ldst=0` | off, from the next boot |
| `echo N \| sudo tee /sys/module/kvm/parameters/emulate_nisv_ldst` | off now, until reboot (`Y` turns it on again) |

`/etc/modprobe.d` does not work here: KVM is built in (`CONFIG_KVM=y`), so
its parameters come from the kernel command line or from sysfs.

With it off, KVM behaves exactly as without the patch. Linux guests do not
need it and are not affected by it: their MMIO accesses carry a syndrome.
With it on, an access KVM cannot decode is handled as before (the guest
gets the abort, or user space a `KVM_EXIT_ARM_NISV` exit when it asked for
that); user space that asked for those exits no longer gets them for the
LDR/STR forms KVM now decodes.

`qemu-vmapple-kvm-nisv`, which turned it on with a tmpfiles.d rule, is
retired; its last version is empty (packages/qemu-vmapple/README.md). On a
7.1.13 kernel from this project, use the command line or sysfs to turn it on.

## Checks

```sh
uname -r                                           # ...asahiwip.plus<N>.fc44.aarch64+16k
cat /sys/module/kvm/parameters/emulate_nisv_ldst   # Y for macOS guests
dmesg | grep -E "ACTLR virtualization|VHE mode"
```

## Userspace

QEMU: `qemu-vmapple` (this project). The VM tooling (restore, golden
images, runners) is in
[aquarat/apple-macos-arm64-vm-guest](https://github.com/aquarat/apple-macos-arm64-vm-guest).

The paravirtual GPU runs out of process, as on the production runners:
`reims-vgpu-backend` serves QEMU's `apv-gpu-proxy` device over a unix
socket and the guest's shared-memfd RAM, and uses the Vulkan driver from
`mesa-honeykrisp-plus`. With the VM tooling, set

```sh
export QEMU_BIN=/usr/libexec/qemu-vmapple/qemu-system-aarch64        # vm-run.sh, launch-kvm.sh
export GPU_BACKEND_BIN=/usr/libexec/qemu-vmapple/reims-vgpu-backend
export $(honeykrisp-plus)                                            # VK_DRIVER_FILES
# runner GPU slots (host profile): GPU_OOP_QEMU_BIN=<the QEMU above>, GPU_BACKEND_BIN=<the backend above>
```

and `launch-kvm.sh` starts one backend per guest, with `TMPDIR` set to
`~/.cache/reims-vgpu` (Reims' pipeline cache) by `vm-run.sh`. By hand:

```sh
TMPDIR=~/.cache/reims-vgpu honeykrisp-plus reims-vgpu-backend --socket $XDG_RUNTIME_DIR/vm1.gpu &
qemu-vmapple -machine vmapple,accel=kvm,memory-backend=ram,gfx-device=apv-gpu-proxy,aux-ram-share=on \
    -object memory-backend-memfd,id=ram,size=16G,share=on \
    -global apv-gpu-proxy.socket=$XDG_RUNTIME_DIR/vm1.gpu ...
```

If the backend dies, QEMU stops the guest with the reason
(`apv-gpu-proxy.on-backend-loss=stop`, the default). Details:
[packages/qemu-vmapple](../packages/qemu-vmapple/README.md#running-a-guest-with-the-gpu)
and [packages/reims-vgpu-backend](../packages/reims-vgpu-backend/README.md).
