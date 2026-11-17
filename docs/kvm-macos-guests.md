# KVM for macOS guests

macOS guests (QEMU's `vmapple` machine, the platform of Apple's
Virtualization.framework) need two things stock KVM does not do. This
project's kernel adds both, in `packages/kernel/patches/`.

## 0001: Apple PAuth virtualization state (always on)

macOS on `vmapple` manages its pointer-authentication keys through vendor
hypercalls, which QEMU serves by writing the guest's key registers with
`KVM_SET_ONE_REG`. KVM already handles the architectural keys; 0001 adds
Apple's:

- APCTL, KERNKEYLO and KERNKEYHI are per-vCPU state (reset to 0). While a
  vCPU is loaded they live in the CPU, written and read through their EL12
  aliases. QEMU reaches them as `ARM64_SYS_REG(3, 6, 15, 15, 0)` and
  `ARM64_SYS_REG(3, 6, 15, 2, 3/4)`, which `KVM_GET_REG_LIST` lists.
- Each VM gets a random 128-bit VM key when it is created. Every vCPU load
  writes it to APVMKEYLO/HI_EL2 and sets APSTS_EL12 to 1. The key is never
  visible to the guest or to user space, and is cleared when the VM is
  destroyed.
- A guest access to any of these registers gets UNDEF.

Without it macOS stops in launchd as soon as it uses signed pointers.

It only acts on M1 and M2 CPUs (matched by MIDR: m1n1's list of parts whose
Apple system registers are unlocked), with KVM in VHE mode on bare metal.
In nVHE, hVHE and protected mode, under a nested hypervisor, and on other
CPUs, KVM is unchanged. `dmesg` shows `kvm [1]: Apple PAuth virtualization
state enabled` when it is active.

On M1 Max the VM key only changes signatures made with keys the guest
writes itself in Apple mode (APCTL bit 0). Keys set through KVM, which is
how QEMU serves macOS's hypercalls, sign the same in every VM, and a
macOS 26 guest migrated to a file resumed in a new QEMU process.

Origin: this project's independent implementation
([kvm-pauth-provenance.md](kvm-pauth-provenance.md)). Anees Iqbal first
showed that macOS guests need this state (CREDITS.md).

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
dmesg | grep -E "PAuth virtualization|VHE mode"
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
