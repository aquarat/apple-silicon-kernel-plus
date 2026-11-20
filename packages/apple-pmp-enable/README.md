# apple-pmp-enable

Opt-in tool that turns on the power management coprocessor (PMP) of a 14"
MacBook Pro with M1 Pro or M1 Max running this project's 7.3.4 `plus5`
kernel: it patches the machine's device tree into m1n1's stage 2
(`boot.bin`) and tries it as a self-reverting one-shot boot, kept only
after `apple-pmp-enable commit` and its checks. Every other board and
device tree is refused. Installing the package changes nothing.

Full document: [docs/pmp-enable.md](../../docs/pmp-enable.md) (what it
does, the trial, risks, validated boards, design, tests).

**Recovery.** If the Mac does not start after `enable` and a restart: hold
the power button until "Loading startup options", choose Options, open
Utilities > Terminal, mount the Linux install's EFI partition
(`diskutil list`, `diskutil mount diskXsY`) and copy
`m1n1/boot.bin.pre-pmp` over `m1n1/boot.bin` on it. The same steps are in
`m1n1/PMP-RECOVERY.txt` on that partition.

```sh
sudo apple-pmp-enable check            # changes nothing
sudo apple-pmp-enable enable --dry-run  # prints what enable would do
sudo apple-pmp-enable enable            # stage the trial, then restart yourself
sudo apple-pmp-enable commit            # on the trial boot, within 15 minutes
sudo apple-pmp-enable disable           # PMP off from the next boot
apple-pmp-enable status
```

| file | installed as |
|---|---|
| `apple-pmp-enable` | `/usr/sbin/apple-pmp-enable`: the commands, the trial |
| `pmp-dtb` | `/usr/libexec/apple-pmp-enable/pmp-dtb`: the device tree fixup, validation and `boot.bin` reader |
| `validated.txt` | `/usr/share/apple-pmp-enable/validated.txt`: the device trees it accepts |
| `boot-safety/*.conf` | `/usr/share/apple-pmp-enable/boot-safety/`: drop-ins copied to `/etc/systemd` for a trial only |
| `systemd/*` | `apple-pmp-trial.service`, `apple-pmp-deadman.{service,timer}`: enabled for a trial only |
| `tests/` | `%check`: the 7.3.4 device trees (`tests/dtb/`) and a fake machine |

Tests: `python3 -m unittest discover -s tests -v` in this directory
(needs `dtc` and `gzip`).
