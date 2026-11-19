# SPDX-License-Identifier: GPL-2.0-only
"""Tests of pmp-dtb with the real device trees of this project's 7.3.4
plus5 kernel (tests/dtb/, xz-compressed copies of
/usr/lib/modules/7.3.4-900.asahiwip.plus5.fc44.aarch64+16k/dtb/apple/, and
-DAPPLE_USE_PMP builds of the same source as *.flag.dtb; docs/pmp-enable.md).

  python3 -m unittest discover -s tests -v      (from packages/apple-pmp-enable)

Needs dtc's fdtget/fdtput and gzip.
"""
import gzip
import hashlib
import importlib.machinery
import importlib.util
import lzma
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
TOOL = os.path.join(PKG, "pmp-dtb")
VALIDATED = os.path.join(PKG, "validated.txt")
KREL = "7.3.4-900.asahiwip.plus5.fc44.aarch64+16k"

# The patched trees that booted with the PMP: the M1 Pro's committed boot.bin
# and the M1 Max's trial boot.bin hold exactly these bytes.
BOOTED = {
    "t6000-j314s": "ce773eacc15fd7fca39e7b369d04c43e44ac151633d6e7de7637840b7b7dae38",
    "t6001-j314c": "a0d9073936930d7214a33af5f8fae7e2faecc23660b37743158c7229572092b8",
}
STOCK = {
    "t6000-j314s": "0d9caf93c1bdff3ffa93aee094ad794bf8d77694dec1fb08fa2f110f7139a1b5",
    "t6001-j314c": "4662c27d3122ca5470fc06798d6c6da5dbf8b01ef9c79adb59ff65ca99062bb9",
}

loader = importlib.machinery.SourceFileLoader("pmp_dtb", TOOL)
pmp_dtb = importlib.util.module_from_spec(importlib.util.spec_from_loader("pmp_dtb", loader))
loader.exec_module(pmp_dtb)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run(*args):
    return subprocess.run(["python3", "-I", TOOL, *args], capture_output=True, text=True)


def fdtput_version():
    r = subprocess.run(["dtc", "--version"], capture_output=True, text=True)
    return r.stdout.strip().split()[-1] if r.returncode == 0 else ""


class DtbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="pmp-dtb-test.")
        cls.dtb = {}
        for f in sorted(os.listdir(os.path.join(HERE, "dtb"))):
            name = f[:-len(".dtb.xz")]
            out = os.path.join(cls.tmp, name + ".dtb")
            with lzma.open(os.path.join(HERE, "dtb", f)) as s, open(out, "wb") as d:
                d.write(s.read())
            cls.dtb[name] = out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def out(self, name):
        return os.path.join(self.tmp, "out-" + name)

    def test_fixtures_are_the_validated_stock_trees(self):
        for b, s in STOCK.items():
            self.assertEqual(sha(self.dtb[b]), s, b)

    def test_patch_validated_boards(self):
        for b in ("t6000-j314s", "t6001-j314c"):
            with self.subTest(b):
                o = self.out(b + ".dtb")
                r = run("patch", "--validated", VALIDATED, "--board", b, self.dtb[b], o)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("/aliases/pmp = /soc/pmp@28e700000", r.stdout)
                for dev in ("dcp@", "isp@", "msr@"):
                    self.assertRegex(r.stdout, f"/soc/{dev}[0-9a-f]+: power-domains\\[0\\]")
                # 7.3 dropped the decoder's APPLE_USE_PMP block (its node is
                # video-codec@ now), and the GPU is reported while its driver
                # is bound (0037): neither moves.
                self.assertNotIn("/soc/video-codec@", r.stdout)
                self.assertNotIn("/soc/gpu@", r.stdout)
                if fdtput_version() == "1.8.1":
                    self.assertEqual(sha(o), BOOTED[b], "not the bytes that booted")
                pd = subprocess.run(["fdtget", "-t", "s", o, "/aliases", "pmp"],
                                    capture_output=True, text=True).stdout.strip()
                self.assertEqual(pd, "/soc/pmp@28e700000")

    def test_patch_matches_flag_build(self):
        for b in ("t6000-j314s", "t6001-j314c"):
            with self.subTest(b):
                r = run("check", self.dtb[b], self.dtb[b + ".flag"])
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("CHECK PASS", r.stdout)

    def test_check_fails_on_a_different_tree(self):
        r = run("check", self.dtb["t6000-j314s"], self.dtb["t6001-j314c.flag"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("CHECK FAIL", r.stdout)

    def test_refuses_unvalidated_boards(self):
        cases = {
            "t6000-j316s": "not a validated board",
            "t6001-j375c": "not a validated board",
            "t6002-j375d": "not a validated board",
            "t8112-j473": "not a validated board",
            "t8103-j274": "not a validated board",
        }
        for b, why in cases.items():
            with self.subTest(b):
                o = self.out(b + ".dtb")
                r = run("patch", "--validated", VALIDATED, self.dtb[b], o)
                self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
                self.assertIn(why, r.stderr)
                self.assertFalse(os.path.exists(o))

    def test_refuses_unsupported_socs_even_unlisted(self):
        # The SoC check holds without the list too (t8112 needs more than MOVED).
        for b in ("t8112-j473", "t8103-j274", "t6002-j375d"):
            with self.subTest(b):
                with self.assertRaises(pmp_dtb.Refused):
                    pmp_dtb.patch_tree(self.dtb[b], self.out(b + "-raw.dtb"))

    def test_refuses_a_changed_tree(self):
        changed = self.out("j314c-changed.dtb")
        shutil.copyfile(self.dtb["t6001-j314c"], changed)
        subprocess.run(["fdtput", "-t", "s", changed, "/", "model", "Something else"], check=True)
        r = run("patch", "--validated", VALIDATED, changed, self.out("x.dtb"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("is not a validated t6001-j314c device tree", r.stderr)

    def test_refuses_the_wrong_board(self):
        r = run("patch", "--validated", VALIDATED, "--board", "t6000-j314s",
                self.dtb["t6001-j314c"], self.out("y.dtb"))
        self.assertEqual(r.returncode, 3)
        self.assertIn("is for t6001-j314c, this machine is t6000-j314s", r.stderr)

    def test_refuses_patching_twice(self):
        once = self.out("once.dtb")
        pmp_dtb.patch_tree(self.dtb["t6000-j314s"], once)
        with self.assertRaises(pmp_dtb.Refused):
            pmp_dtb.patch_tree(once, self.out("twice.dtb"))

    def test_refuses_when_the_result_differs(self):
        # A validated input whose patched digest is not the listed one.
        bad = self.out("validated-bad.txt")
        with open(VALIDATED) as f, open(bad, "w") as g:
            for line in f:
                if line.startswith("t6000-j314s"):
                    w = line.split()
                    w[3] = "0" * 64
                    line = " ".join(w) + "\n"
                g.write(line)
        o = self.out("z.dtb")
        r = run("patch", "--validated", bad, self.dtb["t6000-j314s"], o)
        self.assertEqual(r.returncode, 3)
        self.assertIn("not writing it", r.stderr)
        self.assertFalse(os.path.exists(o))

    def test_board_from_device_tree(self):
        d = os.path.join(self.tmp, "proc-dt")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "compatible"), "wb") as f:
            f.write(b"apple,j314c\0apple,t6001\0apple,arm-platform\0")
        r = run("board", "--dt", d)
        self.assertEqual(r.stdout.strip(), "t6001-j314c")

    def test_bootbin(self):
        # m1n1 (with a stray FDT magic in it, as the real one has), the trees,
        # gzip'd U-Boot, the options: update-m1n1's layout.
        m1n1 = os.urandom(4096) + b"\xd0\x0d\xfe\xed\0\0\0\0" + os.urandom(1000)
        patched = self.out("bb-j314c.dtb")
        pmp_dtb.patch_tree(self.dtb["t6001-j314c"], patched)
        trees = [self.dtb["t6000-j314s"], patched, self.dtb["t8112-j473"]]
        bb = self.out("boot.bin")
        with open(bb, "wb") as f:
            f.write(m1n1)
            for t in trees:
                with open(t, "rb") as g:
                    f.write(g.read())
            f.write(gzip.compress(os.urandom(2000)))
            f.write(b"chosen.foo=bar\n")
        m1n1f = self.out("m1n1.bin")
        with open(m1n1f, "wb") as f:
            f.write(m1n1)
        for extra in ([], ["--m1n1", m1n1f]):
            with self.subTest(extra):
                r = run("bootbin", *extra, bb)
                self.assertEqual(r.returncode, 0, r.stderr)
                rows = [line.split() for line in r.stdout.splitlines()]
                self.assertEqual([x[0] for x in rows], ["t6000-j314s", "t6001-j314c", "t8112-j473"])
                self.assertEqual([x[2] for x in rows], ["-", "pmp", "-"])
                self.assertEqual(rows[1][1], sha(patched))

    def test_validated_list(self):
        rows = pmp_dtb.read_validated(VALIDATED)
        self.assertEqual(sorted(r["board"] for r in rows), ["t6000-j314s", "t6001-j314c"])
        for r in rows:
            self.assertEqual(r["kernel"], KREL)
            self.assertEqual(r["stock"], STOCK[r["board"]])
            self.assertEqual(len(r["patched"]), 64)


if __name__ == "__main__":
    unittest.main()
