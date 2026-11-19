# SPDX-License-Identifier: GPL-2.0-only
"""End-to-end tests of apple-pmp-enable against a fake machine: a directory
tree with an ESP, boot entries, /proc and /sys files, update-m1n1's
configuration and the real 7.3.4 device trees, and stand-ins for grubby,
grub2-editenv, systemctl and journalctl that only record what they are
asked to do. Nothing outside the temporary directory is touched.

Each test walks one path of the trial: enable, the trial boot, commit, the
dead-man, the boot after a failed trial, abort, disable, and the refusals.
"""
import lzma
import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOL = os.path.join(PKG, "apple-pmp-enable")
KREL = "7.3.4-900.asahiwip.plus5.fc44.aarch64+16k"
OLD = "7.3.1-900.asahiwip.plus3.fc44.aarch64+16k"
MID = "0123456789abcdef0123456789abcdef"
TRIAL_ARGS = "apple_pmp_enable.trial=1 panic=10 watchdog.open_timeout=90 softlockup_panic=1 rd.emergency=reboot"

STUBS = {
    "grubby": r"""#!/bin/bash
# --default-kernel | --update-kernel=ALL --args=X | --remove-args=X
case $1 in
--default-kernel) echo "/boot/vmlinuz-$FAKE_DEFAULT"; exit 0 ;;
esac
echo "grubby $*" >> "$FAKE/calls.log"
for a in "$@"; do
    case $a in
    --args=*) for f in "$APPLE_PMP_ENTRIES"/*.conf; do sed -i "/^options /s/\$/ ${a#--args=}/" "$f"; done ;;
    --remove-args=*) for f in "$APPLE_PMP_ENTRIES"/*.conf; do sed -i "/^options /s/ ${a#--remove-args=}//g" "$f"; done ;;
    esac
done
""",
    "grub2-editenv": r"""#!/bin/bash
# grub2-editenv - list | set K=V | unset K
f=$FAKE/grubenv; touch "$f"
case $2 in
list) cat "$f" ;;
set) k=${3%%=*}; grep -v "^$k=" "$f" > "$f.t"; echo "$3" >> "$f.t"; mv "$f.t" "$f" ;;
unset) grep -v "^$3=" "$f" > "$f.t"; mv "$f.t" "$f" ;;
esac
""",
    "systemctl": r"""#!/bin/bash
echo "systemctl $*" >> "$FAKE/calls.log"
exit 0
""",
    "journalctl": r"""#!/bin/bash
cat "$FAKE/journal" 2>/dev/null
exit 0
""",
}


def xz_copy(src, dst):
    with lzma.open(src) as s, open(dst, "wb") as d:
        d.write(s.read())


class Machine:
    """A fake t6001-j314c (M1 Max MacBook Pro) on the 7.3.4 plus5 kernel."""

    def __init__(self, board="t6001-j314c"):
        self.root = tempfile.mkdtemp(prefix="apple-pmp-enable-test.")
        r = self.root
        soc, brd = board.split("-")
        for d in ("esp/m1n1", "state", "dt/chosen", "sys/bus/platform/devices/apple-cpu-memvote.1.auto",
                  "entries", "etc/systemd", f"modules/{KREL}/kernel/drivers/soc/apple", "dtb/apple",
                  "boot", "bin", "share/boot-safety", "libexec"):
            os.makedirs(os.path.join(r, d), exist_ok=True)
        self.write("dt/compatible", f"apple,{brd}\0apple,{soc}\0apple,arm-platform\0".encode())
        self.write(f"modules/{KREL}/kernel/drivers/soc/apple/pmp.ko.xz", b"")
        self.memvote(0)
        self.write("machine-id", MID + "\n")
        self.write("boot_id", "boot-1\n")
        self.write("cmdline", "root=UUID=x ro rhgb quiet\n")
        self.write("journal", "")
        for k in (KREL, OLD):
            self.write(f"entries/{MID}-{k}.conf", textwrap.dedent(f"""\
                title Fedora Linux ({k}) 44
                version {k}
                linux /vmlinuz-{k}
                initrd /initramfs-{k}.img
                options root=UUID=x ro rhgb quiet
                grub_class fedora
                """))
        # update-m1n1's inputs and the ESP boot.bin it wrote from them
        self.write("boot/m1n1.bin", os.urandom(8192) + b"\xd0\x0d\xfe\xed\0\0\0\0" + os.urandom(512))
        self.write("boot/u-boot-nodtb.bin", os.urandom(4096))
        for f in os.listdir(os.path.join(HERE, "dtb")):
            if ".flag." not in f:
                xz_copy(os.path.join(HERE, "dtb", f), os.path.join(r, "dtb/apple", f[:-3]))
        self.write("sysconfig", textwrap.dedent(f"""\
            M1N1="{r}/boot/m1n1.bin"
            U_BOOT="{r}/boot/u-boot-nodtb.bin"
            DTBS="{r}/dtb"
            CONFIG="{r}/m1n1.conf"
            """))
        self.write("m1n1.conf", "# options\ndisplay=1920x1080\n")
        subprocess.run(["bash", "-c", f'export LC_ALL=C; {{ cat "{r}/boot/m1n1.bin" "{r}"/dtb/apple/t6*.dtb '
                        f'"{r}"/dtb/apple/t81*.dtb; gzip -c "{r}/boot/u-boot-nodtb.bin"; '
                        f'printf "display=1920x1080\\n"; }} > "{r}/esp/m1n1/boot.bin"'], check=True)
        self.before = self.read("esp/m1n1/boot.bin")
        # the package's files
        shutil.copy(os.path.join(PKG, "pmp-dtb"), os.path.join(r, "libexec/pmp-dtb"))
        shutil.copy(os.path.join(PKG, "validated.txt"), os.path.join(r, "share/validated.txt"))
        for f in os.listdir(os.path.join(PKG, "boot-safety")):
            shutil.copy(os.path.join(PKG, "boot-safety", f), os.path.join(r, "share/boot-safety", f))
        for name, body in STUBS.items():
            p = os.path.join(r, "bin", name)
            self.write(f"bin/{name}", body)
            os.chmod(p, 0o755)
        self.env = dict(os.environ)
        self.env.update({
            "PATH": os.path.join(r, "bin") + ":" + os.environ["PATH"],
            "FAKE": r, "FAKE_DEFAULT": KREL, "APPLE_PMP_TEST": "1", "APPLE_PMP_GRACE": "0",
            "APPLE_PMP_SHARE": f"{r}/share", "APPLE_PMP_LIBEXEC": f"{r}/libexec",
            "APPLE_PMP_STATE_DIR": f"{r}/state", "APPLE_PMP_DT": f"{r}/dt",
            "APPLE_PMP_SYSFS": f"{r}/sys", "APPLE_PMP_CMDLINE": f"{r}/cmdline",
            "APPLE_PMP_BOOT_ID": f"{r}/boot_id", "APPLE_PMP_SYSCONFIG": f"{r}/sysconfig",
            "APPLE_PMP_ENTRIES": f"{r}/entries", "APPLE_PMP_MACHINE_ID": f"{r}/machine-id",
            "APPLE_PMP_ETC_SYSTEMD": f"{r}/etc/systemd", "APPLE_PMP_MODULES": f"{r}/modules",
            "APPLE_PMP_ESP": f"{r}/esp", "APPLE_PMP_KREL": KREL,
        })

    def path(self, p):
        return os.path.join(self.root, p)

    def write(self, p, data):
        mode = "wb" if isinstance(data, bytes) else "w"
        with open(self.path(p), mode) as f:
            f.write(data)

    def read(self, p, text=False):
        with open(self.path(p), "r" if text else "rb") as f:
            return f.read()

    def run(self, *args):
        return subprocess.run([TOOL, *args], env=self.env, capture_output=True, text=True)

    def memvote(self, pmp):
        self.write("sys/bus/platform/devices/apple-cpu-memvote.1.auto/stats",
                   f"cluster0 cpu0 high 0 ups 0 ms_high 0\npmu 1 pmp {pmp}\n")

    def new_boot(self, n, trial, pmp_dt):
        """Restart: a new boot id, the command line of the entry GRUB
        picks, and the device tree m1n1 built from the ESP boot.bin."""
        env = dict(l.split("=", 1) for l in self.read("grubenv", True).split() if "=" in l) \
            if os.path.exists(self.path("grubenv")) else {}
        self.write("boot_id", f"boot-{n}\n")
        cmd = "root=UUID=x ro rhgb quiet"
        if trial:
            assert env.get("next_entry") == f"{MID}-{KREL}-pmptrial", env
            cmd += " " + TRIAL_ARGS
        self.write("cmdline", cmd + "\n")
        # GRUB clears next_entry when it uses it
        if os.path.exists(self.path("grubenv")):
            self.write("grubenv", "".join(f"{k}={v}\n" for k, v in env.items() if k != "next_entry"))
        node = self.path("dt/soc/pmp@28e700000")
        if pmp_dt:
            os.makedirs(self.path("dt/aliases"), exist_ok=True)
            os.makedirs(node, exist_ok=True)
            self.write("dt/aliases/pmp", b"/soc/pmp@28e700000\0")
            self.write("dt/soc/pmp@28e700000/status", b"okay\0")
            self.write("dt/soc/pmp@28e700000/apple,tunable-dcs-bw-threshold", b"\0\0\0\1")
        else:
            shutil.rmtree(self.path("dt/aliases"), ignore_errors=True)
            shutil.rmtree(self.path("dt/soc"), ignore_errors=True)
        self.memvote(1 if pmp_dt and trial else 0)

    def state(self):
        p = self.path("state/state")
        if not os.path.exists(p):
            return {}
        return dict(l.split("=", 1) for l in self.read("state/state", True).splitlines())

    def options(self, k=KREL):
        for line in self.read(f"entries/{MID}-{k}.conf", True).splitlines():
            if line.startswith("options "):
                return line

    def cleanup(self):
        shutil.rmtree(self.root)


class TrialTest(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def tearDown(self):
        self.m.cleanup()

    def ok(self, r):
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def assert_untouched(self):
        m = self.m
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assertNotIn("module_blacklist", m.options())
        self.assertNotIn("module_blacklist", m.options(OLD))
        self.assertFalse(os.path.exists(m.path(f"entries/{MID}-{KREL}-pmptrial.conf")))
        self.assertFalse(os.path.exists(m.path("etc/systemd/system/emergency.service.d")) and
                         os.listdir(m.path("etc/systemd/system/emergency.service.d")))
        env = m.read("grubenv", True) if os.path.exists(m.path("grubenv")) else ""
        self.assertNotIn("next_entry", env)

    def assert_cleaned(self):
        m = self.m
        self.assertNotIn("module_blacklist", m.options())
        self.assertNotIn("module_blacklist", m.options(OLD))
        self.assertFalse(os.path.exists(m.path(f"entries/{MID}-{KREL}-pmptrial.conf")))
        for d in ("system/emergency.service.d", "system/rescue.service.d",
                  "system/multi-user.target.d", "system.conf.d"):
            self.assertFalse(os.path.exists(m.path(f"etc/systemd/{d}/50-apple-pmp-trial.conf")), d)
        self.assertNotIn("next_entry", m.read("grubenv", True))
        self.assertIn("disable apple-pmp-trial.service apple-pmp-deadman.timer", m.read("calls.log", True))

    def enable(self):
        m = self.m
        r = self.ok(m.run("enable", "--deadman", "10"))
        self.assertIn("trial staged", r.stdout)
        return r

    def test_check_and_dry_run_change_nothing(self):
        m = self.m
        r = self.ok(m.run("check"))
        self.assertIn("board t6001-j314c", r.stdout)
        self.assertIn("validated", r.stdout)
        self.assertIn("only t6001-j314c.dtb differs", r.stdout)
        r = self.ok(m.run("enable", "--dry-run"))
        self.assertIn("dry run: nothing was changed", r.stdout)
        self.assert_untouched()
        self.assertEqual(m.state(), {})
        self.assertFalse(os.path.exists(m.path("esp/m1n1/boot.bin.pre-pmp")))

    def test_enable_stages_a_trial(self):
        m = self.m
        self.enable()
        st = m.state()
        self.assertEqual(st["phase"], "armed")
        # the ESP: the candidate, the saved image and the recovery note
        self.assertEqual(m.read("esp/m1n1/boot.bin.pre-pmp"), m.before)
        cand = m.read("esp/m1n1/boot.bin")
        self.assertNotEqual(cand, m.before)
        self.assertEqual(cand, m.read("state/boot.bin.pmp"))
        self.assertIn("boot.bin.pre-pmp", m.read("esp/m1n1/PMP-RECOVERY.txt", True))
        # only this board's tree differs, and it is the validated patched one
        r = subprocess.run([m.path("libexec/pmp-dtb"), "bootbin", m.path("esp/m1n1/boot.bin")],
                           capture_output=True, text=True, check=True)
        rows = {x.split()[0]: x.split()[2] for x in r.stdout.splitlines()}
        self.assertEqual(rows["t6001-j314c"], "pmp")
        self.assertEqual([b for b, p in rows.items() if p == "pmp"], ["t6001-j314c"])
        self.assertEqual(len(cand), len(m.before) + len(m.read("state/t6001-j314c-pmp.dtb"))
                         - os.path.getsize(m.path("dtb/apple/t6001-j314c.dtb")))
        # the boot entries: every normal one blacklists pmp, the trial one does not
        self.assertIn("module_blacklist=pmp", m.options())
        self.assertIn("module_blacklist=pmp", m.options(OLD))
        trial = m.read(f"entries/{MID}-{KREL}-pmptrial.conf", True)
        self.assertIn("(PMP trial)", trial)
        self.assertIn(TRIAL_ARGS, trial)
        self.assertNotIn("module_blacklist", trial)
        self.assertIn(f"next_entry={MID}-{KREL}-pmptrial", m.read("grubenv", True))
        # boot safety and the dead-man for the trial window
        for d in ("system/emergency.service.d", "system/rescue.service.d",
                  "system/multi-user.target.d", "system.conf.d"):
            self.assertTrue(os.path.exists(m.path(f"etc/systemd/{d}/50-apple-pmp-trial.conf")), d)
        self.assertIn("OnBootSec=10min",
                      m.read("etc/systemd/system/apple-pmp-deadman.timer.d/50-apple-pmp-trial.conf", True))
        self.assertIn("enable apple-pmp-trial.service apple-pmp-deadman.timer", m.read("calls.log", True))
        # a second enable is refused
        r = m.run("enable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("a trial is in progress", r.stderr)

    def test_trial_boot_and_commit(self):
        m = self.m
        self.enable()
        cand = m.read("esp/m1n1/boot.bin")
        m.new_boot(2, trial=True, pmp_dt=True)
        self.ok(m.run("boot"))
        # self-reverting: the old boot.bin is back during the trial boot
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assertEqual(m.state()["phase"], "trial")
        self.ok(m.run("boot"))  # a second start in the same boot changes nothing
        self.assertEqual(m.state()["phase"], "trial")
        r = self.ok(m.run("verify"))
        self.assertNotIn("FAIL", r.stdout)
        r = self.ok(m.run("commit"))
        self.assertEqual(m.read("esp/m1n1/boot.bin"), cand)
        self.assertEqual(m.read("esp/m1n1/boot.bin.pre-pmp"), m.before)
        self.assertEqual(m.state()["phase"], "committed")
        self.assert_cleaned()
        # the dead-man does nothing once committed
        self.ok(m.run("deadman"))
        self.assertNotIn("systemctl reboot", m.read("calls.log", True))
        # disable puts the saved image back
        m.new_boot(3, trial=False, pmp_dt=True)
        r = self.ok(m.run("disable"))
        self.assertIn("boot.bin.pre-pmp is back", r.stdout)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assertEqual(m.state()["phase"], "disabled")
        r = self.ok(m.run("disable"))
        self.assertIn("nothing to do", r.stdout)

    def commit_trial(self):
        m = self.m
        self.enable()
        m.new_boot(2, trial=True, pmp_dt=True)
        self.ok(m.run("boot"))
        self.ok(m.run("commit"))
        m.new_boot(3, trial=False, pmp_dt=True)

    def test_disable_never_writes_a_broken_image(self):
        m = self.m
        self.commit_trial()
        committed = m.read("esp/m1n1/boot.bin")
        # force the rebuild path, and make one of update-m1n1's trees unreadable
        os.remove(m.path("esp/m1n1/boot.bin.pre-pmp"))
        os.chmod(m.path("dtb/apple/t6000-j316s.dtb"), 0)
        try:
            r = m.run("disable")
        finally:
            os.chmod(m.path("dtb/apple/t6000-j316s.dtb"), 0o644)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("left as it is", r.stderr)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), committed)
        # without this board's tree among update-m1n1's inputs
        os.remove(m.path("dtb/apple/t6001-j314c.dtb"))
        r = m.run("disable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("has no stock t6001-j314c tree", r.stderr)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), committed)

    def test_disable_rebuilds_when_the_backup_is_gone(self):
        m = self.m
        self.commit_trial()
        os.remove(m.path("esp/m1n1/boot.bin.pre-pmp"))
        r = self.ok(m.run("disable"))
        self.assertIn("stock device trees", r.stdout)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)

    def test_failed_restore_keeps_the_fallback(self):
        m = self.m
        self.enable()
        cand = m.read("esp/m1n1/boot.bin")
        # the trial boot died before user space; on the normal boot the ESP
        # cannot be written
        m.new_boot(2, trial=True, pmp_dt=True)
        m.new_boot(3, trial=False, pmp_dt=True)
        os.chmod(m.path("esp/m1n1"), 0o555)
        try:
            self.ok(m.run("boot"))
        finally:
            os.chmod(m.path("esp/m1n1"), 0o755)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), cand)
        self.assertEqual(m.state()["phase"], "armed")
        self.assertIn("module_blacklist=pmp", m.options())
        self.assertNotIn("disable apple-pmp-trial.service", m.read("calls.log", True))
        # the next boot can write it: everything is undone
        m.new_boot(4, trial=False, pmp_dt=True)
        self.ok(m.run("boot"))
        self.assertEqual(m.state()["phase"], "failed")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()

    def test_failed_restore_after_an_uncommitted_trial(self):
        m = self.m
        self.enable()
        m.new_boot(2, trial=True, pmp_dt=True)
        self.ok(m.run("boot"))
        # pretend the early restore did not stick, and the ESP is read-only now
        m.write("esp/m1n1/boot.bin", m.read("state/boot.bin.pmp"))
        m.new_boot(3, trial=False, pmp_dt=True)
        os.chmod(m.path("esp/m1n1"), 0o555)
        try:
            self.ok(m.run("boot"))
        finally:
            os.chmod(m.path("esp/m1n1"), 0o755)
        self.assertEqual(m.state()["phase"], "trial")
        self.assertIn("module_blacklist=pmp", m.options())
        m.new_boot(4, trial=False, pmp_dt=True)
        self.ok(m.run("boot"))
        self.assertEqual(m.state()["phase"], "reverted")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()

    def test_commit_refused_when_the_pmp_did_not_start(self):
        m = self.m
        self.enable()
        m.new_boot(2, trial=True, pmp_dt=True)
        m.memvote(0)
        self.ok(m.run("boot"))
        r = m.run("commit")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FAIL the PMP is not running", r.stdout)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assertEqual(m.state()["phase"], "trial")
        # the dead-man restarts the machine ...
        self.ok(m.run("deadman"))
        self.assertIn("systemctl reboot", m.read("calls.log", True))
        # ... and the next boot (normal entry) undoes the rest
        m.new_boot(3, trial=False, pmp_dt=False)
        self.ok(m.run("boot"))
        self.assertEqual(m.state()["phase"], "reverted")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()

    def test_commit_refused_with_pmp_errors_in_the_log(self):
        m = self.m
        self.enable()
        m.new_boot(2, trial=True, pmp_dt=True)
        m.write("journal", "apple-pmp 28e700000.pmp: PMP firmware crashed\n")
        self.ok(m.run("boot"))
        r = m.run("commit")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FAIL PMP errors in the kernel log", r.stdout)

    def test_trial_boot_that_never_reached_user_space(self):
        m = self.m
        self.enable()
        # the trial boot died early; the watchdog restarted the machine and
        # GRUB, its one-shot used up, booted the normal entry, which
        # blacklists pmp, from the PMP boot.bin
        m.new_boot(2, trial=True, pmp_dt=True)
        m.new_boot(3, trial=False, pmp_dt=True)
        self.ok(m.run("boot"))
        self.assertEqual(m.state()["phase"], "failed")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()

    def test_abort_before_the_trial(self):
        m = self.m
        self.enable()
        r = self.ok(m.run("abort"))
        self.assertIn("aborted", r.stdout)
        self.assertEqual(m.state()["phase"], "aborted")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()
        # and it can be enabled again later
        self.enable()

    def test_abort_on_the_trial_boot(self):
        m = self.m
        self.enable()
        m.new_boot(2, trial=True, pmp_dt=True)
        self.ok(m.run("boot"))
        self.ok(m.run("abort"))
        self.assertEqual(m.state()["phase"], "aborted")
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assert_cleaned()

    def test_commit_only_on_the_trial_boot(self):
        m = self.m
        self.enable()
        r = m.run("commit")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not on a trial boot", r.stderr)

    def test_refuses_a_boot_bin_it_cannot_reproduce(self):
        m = self.m
        m.write("esp/m1n1/boot.bin", m.before + b"x")
        m.before = m.read("esp/m1n1/boot.bin")
        r = m.run("enable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is not what update-m1n1 would write", r.stderr)
        self.assert_untouched()

    def test_refuses_another_default_kernel(self):
        m = self.m
        m.env["FAKE_DEFAULT"] = OLD
        r = m.run("enable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("the default kernel is", r.stderr)
        self.assert_untouched()

    def test_refuses_an_existing_module_blacklist(self):
        m = self.m
        m.write("cmdline", "root=UUID=x ro module_blacklist=nouveau\n")
        r = m.run("enable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("module_blacklist", r.stderr)
        self.assert_untouched()

    def test_refuses_a_machine_with_the_pmp_on(self):
        m = self.m
        m.new_boot(2, trial=False, pmp_dt=True)
        r = m.run("check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("already has the PMP enabled", r.stderr)

    def test_refuses_a_pending_one_shot_boot(self):
        m = self.m
        m.write("grubenv", "saved_entry=x\nnext_entry=someone-elses-entry\n")
        r = m.run("enable")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("one-shot boot pending", r.stderr)
        self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
        self.assertIn("next_entry=someone-elses-entry", m.read("grubenv", True))

    def test_refuses_a_kernel_without_the_driver(self):
        m = self.m
        os.remove(m.path(f"modules/{KREL}/kernel/drivers/soc/apple/pmp.ko.xz"))
        r = m.run("check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no PMP driver", r.stderr)


class UnvalidatedBoardTest(unittest.TestCase):
    def test_refuses_unvalidated_boards(self):
        for board in ("t6000-j316s", "t6001-j375c", "t6002-j375d", "t8112-j473"):
            with self.subTest(board):
                m = Machine(board)
                try:
                    r = m.run("enable")
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn("is not a validated board", r.stderr)
                    self.assertEqual(m.read("esp/m1n1/boot.bin"), m.before)
                    self.assertEqual(m.state(), {})
                finally:
                    m.cleanup()


if __name__ == "__main__":
    unittest.main()
