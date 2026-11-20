# Turning the PMP on: apple-pmp-enable

| | |
|---|---|
| package | `apple-pmp-enable` ([packages/apple-pmp-enable](../packages/apple-pmp-enable)), opt-in |
| needs | this project's kernel `7.3.4-900.asahiwip.plus5` (patches 0030-0037), GRUB, `update-m1n1` |
| boards | 14" MacBook Pro with M1 Pro (`t6000-j314s`) or M1 Max (`t6001-j314c`); everything else is refused |
| related | [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md), [pmp-gpu-report.md](pmp-gpu-report.md), [benchmarks.md](benchmarks.md#power-management-pmp) |
| pull request | #24 |

> **Read the [recovery](#recovery) section before you run `enable`.** If the
> machine does not start with the new boot image, the fix is in macOS
> recovery: copy `m1n1/boot.bin.pre-pmp` over `m1n1/boot.bin` on the EFI
> partition. The tool cannot do that for you in that case.

## What it does

The power management coprocessor (PMP) of the M1 Pro and M1 Max sets the
SoC, fabric and DRAM performance states. Running it saves about 1.2-1.4 W
on an M1 Max laptop, idle or busy, and with this project's kernel
(0030-0037) the CPU and GPU keep, or exceed, the memory bandwidth they have
without it ([benchmarks.md](benchmarks.md#power-management-pmp)).

But the PMP runs only if m1n1, the boot loader, finds a `pmp` alias in the
device tree it hands to Linux. m1n1's stage 2 (`m1n1/boot.bin` on the EFI
system partition, written by `update-m1n1`) carries the device trees, and
Fedora's are built without `APPLE_USE_PMP`, so the PMP never starts. No
kernel module can change that. `apple-pmp-enable`:

1. **patches this machine's device tree only**, as the kernel would have
   built it with `-DAPPLE_USE_PMP`, and only if that tree is one it has
   been validated on (the board, and the exact stock tree by its sha256);
   anything else is refused;
2. builds the new `boot.bin` from exactly what `update-m1n1` uses (the same
   m1n1, U-Boot, device trees and options), with only this board's tree
   replaced, and refuses if your current `boot.bin` is not what
   `update-m1n1` would write (so the trial changes one thing only);
3. **stages it as a one-shot trial boot** (below) and keeps it only when
   you run `apple-pmp-enable commit` on the trial boot and its checks pass.

Installing the package does nothing: no scriptlet writes the EFI partition,
the boot entries or the device trees, and its systemd units stay disabled
until `enable`.

## Use

```sh
sudo dnf install apple-pmp-enable
sudo apple-pmp-enable check          # can this machine take it? changes nothing
sudo apple-pmp-enable enable --dry-run
sudo apple-pmp-enable enable         # stages the trial; does not restart
# restart; on the trial boot, log in and within 15 minutes:
sudo apple-pmp-enable verify         # the boot checks only (optional)
sudo apple-pmp-enable commit
apple-pmp-enable status
```

`enable --deadman MINUTES` sets the time the trial boot waits for a
commit (default 15, at least 5).

`check` refuses, among others, when: the board or its device tree is not
validated; the running kernel is not the default one, or not the kernel
the validated tree belongs to; `boot.bin` is not what `update-m1n1` would
write now (run `update-m1n1`, restart once, then try again; with
`M1N1_UPDATE_DISABLED` set in `/etc/sysconfig/update-m1n1`, `update-m1n1`
does nothing, so remove that first); the PMP is already on; a boot entry already sets `module_blacklist=` (the trial needs
that parameter); GRUB already has a one-shot boot pending (`next_entry`);
the EFI partition mounted at `/boot/efi` is not the one m1n1 boots from.

## The trial

`enable` does, in this order (`--dry-run` prints it):

1. saves the current `boot.bin` as `m1n1/boot.bin.pre-pmp` on the EFI
   partition (and in `/var/lib/apple-pmp-enable`), with
   `m1n1/PMP-RECOVERY.txt` beside it. An existing `boot.bin.pre-pmp`
   that differs (a backup of your own, or one from an earlier trial) is
   kept as `boot.bin.pre-pmp.bak-YYYYMMDD` (`--dry-run` names it);
2. adds `module_blacklist=pmp` to every boot entry (with grubby, so also
   to `/etc/kernel/cmdline` for kernels installed meanwhile). With the
   `pmp` module not loaded, the PMP device tree is inert: the PMP is not
   started and its report entries pass power requests straight through, so
   any boot other than the trial behaves as before, even from the new
   `boot.bin`;
3. adds a boot entry `<machine-id>-<kernel>-pmptrial` without it, with
   `apple_pmp_enable.trial=1 panic=10 watchdog.open_timeout=90
   softlockup_panic=1 rd.emergency=reboot`;
4. installs boot-safety drop-ins for the trial window: emergency and rescue
   mode restart the machine after 2 minutes, a boot that has not reached
   `multi-user.target` after 15 minutes restarts, and systemd runs the
   hardware watchdog (30 s); enables `apple-pmp-trial.service` and the
   dead-man `apple-pmp-deadman.timer`;
5. writes the new `boot.bin`;
6. makes the trial entry GRUB's next boot, once (`next_entry`).

Then, at the next restart:

| what happens | result |
|---|---|
| the trial boot reaches early user space | `apple-pmp-trial.service` (before `sysinit.target`) puts `boot.bin.pre-pmp` back at once: any later restart is back to the old state |
| you run `commit` on it and every check passes | the PMP `boot.bin` is written again and kept; the blacklist, the trial entry, the drop-ins and the units are removed |
| no commit within the dead-man time | the machine restarts; that boot (old `boot.bin`) removes the rest |
| a check fails | `commit` refuses; the dead-man or `abort` + restart go back |
| the trial boot hangs or panics before user space | panic or watchdog restart; GRUB's one-shot is used up, so the normal entry boots (`module_blacklist=pmp`, PMP not started) and `apple-pmp-trial.service` reverts everything |
| m1n1 itself fails on the new `boot.bin` | nothing on the machine can help: [recovery](#recovery) |

The checks (`verify`): the trial entry's flag is on the command line; the
device tree has the `pmp` alias and m1n1 set the PMP node up (`okay`, with
its tunables); the PMP is running (`apple-cpu-memvote`'s `stats` says
`pmp 1`, patch 0034); no PMP firmware crash or error in the kernel log.
Failed systemd units are listed for information.

After a commit the PMP stays on until `boot.bin` is rewritten. Kernel and
m1n1 updates run `update-m1n1`, which writes Fedora's device trees again:
the PMP is then off from the next boot, as before `enable` (`status`
shows it). Run `enable` again once this package lists the new kernel's
device tree. With `M1N1_UPDATE_DISABLED` set, `boot.bin` keeps the 7.3.4
PMP tree when you move to a newer kernel; a newer kernel on an older tree
usually boots but may lack nodes it needs (README, Rollback).

## Recovery

When m1n1 stops on the new image (for example a board whose Apple device
tree lacks a PMP node m1n1 needs: it then does not boot at all) the machine
starts nothing, and only macOS recovery helps. The previous image is on the
EFI partition as `m1n1/boot.bin.pre-pmp` (the file `m1n1/PMP-RECOVERY.txt`
says the same):

1. Shut the Mac down. Press and hold the power button until "Loading
   startup options" appears, choose **Options**, then Continue (this is
   1TR, the recovery system).
2. Utilities > Terminal.
3. Find and mount the EFI partition of the Linux install:

   ```sh
   diskutil list                # the EFI partition next to the Linux partitions, e.g. disk0s4
   diskutil mount disk0s4       # mounts it under /Volumes, e.g. /Volumes/EFI - FEDOR
   ls "/Volumes/EFI - FEDOR/m1n1"
   ```

4. Put the old image back and restart:

   ```sh
   cp "/Volumes/EFI - FEDOR/m1n1/boot.bin.pre-pmp" "/Volumes/EFI - FEDOR/m1n1/boot.bin"
   ```

Linux then boots as before the trial; its next boot runs
`apple-pmp-trial.service`, which removes the trial's boot entries and
drop-ins (state `failed`).

## Turning it off and removing it

```sh
sudo apple-pmp-enable disable     # PMP off from the next boot
sudo dnf remove apple-pmp-enable
```

`disable` writes `boot.bin.pre-pmp` back if `boot.bin` is still the
committed image, otherwise a `boot.bin` with the stock device trees, as
`update-m1n1` would (the PMP one is kept as `boot.bin.old`). During a trial
use `abort` instead (before the trial boot it restores everything; on the
trial boot the PMP stays on until that boot ends). Removing the package
never touches the EFI partition or the boot entries; if the PMP was
committed it stays on until `boot.bin` is rewritten (`disable` first, or
the next `update-m1n1`). `boot.bin.pre-pmp` (and any `.bak-*` copies), `PMP-RECOVERY.txt` and
`/var/lib/apple-pmp-enable` are left in place; delete them when you no
longer need them.

## Risks

- **A bad stage 2 needs macOS recovery** (above). The tool narrows this
  to validated boards and trees whose patched result is known to have
  booted, but cannot rule it out (a different Apple firmware version, say).
- **Power under GPU load goes up.** With the GPU report (0037) the PMP
  raises fabric and DRAM for the GPU: about +8-10 W under sustained GPU
  load on an M1 Max for the extra bandwidth, energy per byte about even
  ([pmp-gpu-report.md](pmp-gpu-report.md)). Idle power goes down.
- **Webcam:** two ISP IOMMU translation faults at webcam probe appeared on
  PMP boots of both laptops; the ISP still binds. Not investigated.
- **Suspend/resume with the PMP is untested** (the test machine's
  `pm_test` hangs without these patches too).
- **Boot entries:** during a trial every entry carries
  `module_blacklist=pmp`; a kernel installed during the trial gets it too.
  The trial removes it at the end; do not install kernels or run
  `update-m1n1` during a trial.

## Validated boards

A row in [validated.txt](../packages/apple-pmp-enable/validated.txt) is one
stock device tree, by sha256, from this project's kernel package, which

- passes `pmp-dtb check` against a `-DAPPLE_USE_PMP` build of the same
  kernel source (every `power-domains` property by target, the alias, the
  set of properties), and
- has booted, patched, from a rebuilt stage 2 on that board, with the PMP
  started.

`patch` also checks the result's structural digest against the row, so a
tree is only ever written if it equals one that booted.

| board | machine | stock tree (7.3.4 `plus5`) | patched (sha256) | booted |
|---|---|---|---|---|
| `t6000-j314s` | 14" MacBook Pro, M1 Pro | `0d9caf93c1bdff3f…` | `ce773eacc15fd7fc…` | as the machine's permanent stage 2 since 2026-11-18, after a one-shot trial (GPU 81.6/96.3/125.0/79.5 GB/s, STREAM 8 threads 137-138/130-132; [kernel-7.3.4-rebase.md](kernel-7.3.4-rebase.md#tests-m1-pro-laptop-t6000-pmp-running)) |
| `t6001-j314c` | 14" MacBook Pro, M1 Max | `4662c27d3122ca54…` | `a0d9073936930d72…` | as a one-shot trial, 2026-11-18 (PMP started, 67 tunables; GPU 170/222/263/155 GB/s, STREAM 10 threads 159-162/159-164; [pmp-gpu-report.md](pmp-gpu-report.md#limitations-and-open-points)) |

The patched trees this package writes are byte-identical to those two (the
tests check it with the 7.3.4 trees in `tests/dtb/`).

Not listed:

| board | why |
|---|---|
| `t6000-j316s`, `t6001-j316c` (16" MacBook Pro), `t6001-j375c` (Mac Studio, M1 Max) | `check` passes on 7.3.4 `plus5`, but the PMP has not been booted on them. One boot with the fixup (as above, with someone able to reach macOS recovery) would validate them. |
| `t6002-j375d` (Mac Studio, M1 Ultra) | the 7.3.4 source's own `APPLE_USE_PMP` build does not compile (die 1's MSR scalers reference report entries that do not exist); die 1 has no report entries for its encoders; 0037 deletes the GPU report there; the PMP has never run on a two-die machine |
| `t8112` (M2) | the PMP firmware crashes about 80 ms in unless the neural engine's power domain is kept on, and the encoder was slower with the PMP; 7.3.4 moves the MSR scaler there too, which the fixup does not cover (`check` fails) |
| `t8103` (M1) | an older PMP without Linux support |
| t602x and later | not tried |

### Adding a kernel or a board (maintainers)

Every new kernel needs new rows: the trees change with each kernel, and a
kernel series can add `APPLE_USE_PMP` blocks (7.3.4 added the MSR scaler,
so `MOVED` in `pmp-dtb` gained `msr@`; 7.3 dropped the decoder's, its node
is now `video-codec@`).

1. Build the board's tree from the kernel source with and without the flag
   (the plain build must equal the RPM's
   `/usr/lib/modules/<kernel>/dtb/apple/<board>.dtb` byte for byte). From
   the prepared kernel tree, with its own `scripts/dtc/dtc` (Asahi's trees
   use syntax stock dtc rejects):

   ```sh
   f=arch/arm64/boot/dts/apple/<board>.dts
   for mode in stock flag; do
     { [ $mode = flag ] && echo '#define APPLE_USE_PMP'; cat $f; } > $mode.dts
     gcc -E -nostdinc -I scripts/dtc/include-prefixes -I arch/arm64/boot/dts/apple -I include \
         -undef -D__DTS__ -x assembler-with-cpp -o $mode.tmp $mode.dts
     scripts/dtc/dtc -q -b 0 -i arch/arm64/boot/dts/apple -i scripts/dtc/include-prefixes \
         -Wno-unique_unit_address -Wno-unit_address_vs_reg -Wno-avoid_unnecessary_addr_size \
         -Wno-alias_paths -Wno-interrupt_map -Wno-simple_bus_reg -o <board>.$mode.dtb $mode.tmp
   done
   ```

2. Read the source's `#ifdef APPLE_USE_PMP` blocks; if a new device moved,
   add its node name to `MOVED`. Then
   `pmp-dtb check <board>.stock.dtb <board>.flag.dtb` must say `PASS`.
3. Boot it: the patched tree in a stage 2 that differs from the working one
   only in that tree, as a one-shot (on a laptop, `apple-pmp-enable enable`
   with a temporary row is exactly that), with a way to reach macOS
   recovery. Check `apple-pmp-enable verify`, the display, the camera, video
   decoding, and the bandwidth figures.
4. Add the row (`sha256sum` of the stock tree, `pmp-dtb digest` of the
   patched one), the tree to `tests/dtb/`, and the result to this document.

## Design and alternatives

- **One board's tree, nothing else.** The trial `boot.bin` differs from the
  working one only in that tree; refusing a `boot.bin` that `update-m1n1`
  would not reproduce keeps a trial from also testing a new m1n1 or U-Boot.
- **Validated trees, not boards.** A fixup that is right for one kernel's
  tree can be wrong for the next (new `APPLE_USE_PMP` blocks), and a wrong
  power-domain move is found only by booting. Keying on the stock tree's
  hash means every accepted input was checked against a flag build and
  booted. The cost: each kernel bump needs a package update.
- **Not at kernel installation.** An earlier version of this tooling
  patched the trees from a kernel-install hook, so every kernel update rewrote the
  stage 2 with PMP trees. Here a kernel update goes back to Fedora's trees
  (the safe direction) and turning the PMP on again is an explicit trial.
- **Two layers of fallback.** The early `boot.bin` restore makes the trial
  self-reverting from early user space on; `module_blacklist=pmp` on every
  other entry covers a trial that dies before that, since the PMP tree is
  inert without the module (the A/B measurements of
  [pmp-fabric-dram-requests.md](pmp-fabric-dram-requests.md) used exactly
  that as "PMP not running", four boots). Neither covers m1n1 failing,
  hence the validated list and the recovery steps.
- **Commit by hand.** A person confirms the machine works (display,
  input, network) before the image is kept; the checks catch what a person
  cannot see (the PMP running, no firmware crash).
- **A rebuilt `update-m1n1` image, not a call to it.** `update-m1n1`
  writes the system partition directly and exits when
  `M1N1_UPDATE_DISABLED` is set; the tool reads the same configuration
  (`/etc/sysconfig/update-m1n1`, `/etc/m1n1.conf`) and lays the image out
  the same way (m1n1, the trees, gzip'd U-Boot, the options).

## Testing

- `tests/test_pmp_dtb.py`, with the 7.3.4 `plus5` trees of seven boards
  (`tests/dtb/`): the patched trees of the two validated boards are
  byte-identical to the ones that booted; both pass `check` against
  their flag builds; every other board, a modified tree, the wrong board,
  an already patched tree and a mismatched digest are refused; `boot.bin`
  parsing.
- `tests/test_trial.py`: the whole trial on a fake machine (a directory
  with an EFI partition, boot entries, `/proc` and `/sys` files and
  stand-ins for grubby, grub2-editenv, systemctl and journalctl): check and
  dry run change nothing; enable stages exactly the steps above; the trial
  boot restores `boot.bin`; commit with passing and failing checks; the
  dead-man; a trial boot that never reached user space; abort before and
  on the trial boot; disable (also: it never writes an image it could not
  assemble or that lacks the board's stock tree); a `boot.bin` restore that
  fails on the ESP keeps `module_blacklist=pmp` and retries at the next
  boot; and the refusals.
- The package's `%check` runs both; CI runs them, shellcheck and rpmlint.
- On hardware: the package itself has not run `enable` on a machine. The
  patched trees are byte-identical to the two that booted, and the trial
  follows the scheme those boots used (a one-shot stage 2 put back early
  in the trial boot, kept only after checks).

## Upstream status and provenance

Not submitted upstream. This project's work (GPL-2.0-only), generalised
from the tooling used for the two machines above (the device tree fixup
and the self-reverting trial boot).
What it relies on comes from the Linux device tree sources (the
`APPLE_USE_PMP` blocks; `GPL-2.0+ OR MIT`), m1n1's `dt_set_pmp()` (MIT;
read for its behaviour, no code taken) and `update-m1n1` from
asahi-scripts (MIT; its image layout, re-implemented). The test trees in
`tests/dtb/` are built from the kernel sources this project packages
(`GPL-2.0+ OR MIT`); no Apple data is in this package. m1n1 copies the
PMP's tunables from the Mac's own Apple device tree at boot.
