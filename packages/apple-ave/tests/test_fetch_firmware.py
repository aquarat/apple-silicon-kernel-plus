# SPDX-License-Identifier: GPL-2.0-only
"""Tests for firmware/apple-ave-fetch-firmware and firmware/ave_fwgen.py.

No network, no Apple files: everything is synthetic. A small Mach-O with the
RTKit tag list the firmware has, a small MH_FILESET kernelcache with an
AppleAVE2 kext and a DPE CfgSet, both wrapped in IM4P/IMG4 DER, put in a
ZIP64 archive, served from a local file or a localhost HTTP server that
answers range requests.

    python3 -m unittest discover -s packages/apple-ave/tests -v
"""
import contextlib
import hashlib
import http.server
import importlib.machinery
import importlib.util
import io
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
FWDIR = os.path.join(HERE, "..", "firmware")
TOOL = os.path.join(FWDIR, "apple-ave-fetch-firmware")
REAL_HASHES = os.path.join(FWDIR, "known-hashes.txt")


def load_tool():
    os.environ["APPLE_AVE_LIBDIR"] = FWDIR
    loader = importlib.machinery.SourceFileLoader("apple_ave_fetch_firmware", TOOL)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


T = load_tool()
G = T.G


def sha(b):
    return hashlib.sha256(b).hexdigest()


def rd(path):
    with open(path, "rb") as f:
        return f.read()


def wr(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


# --- synthetic DER ---------------------------------------------------------
def der(tag, value):
    n = len(value)
    if n < 0x80:
        hdr = bytes([tag, n])
    else:
        k = (n.bit_length() + 7) // 8
        hdr = bytes([tag, 0x80 | k]) + n.to_bytes(k, "big")
    return hdr + value


def ia5(s):
    return der(0x16, s.encode())


def dint(v):
    return der(0x02, v.to_bytes(max(1, (v.bit_length() + 8) // 8), "big"))


def im4p(payload, fourcc="avef", extra=b""):
    return der(0x30, ia5("IM4P") + ia5(fourcc) + ia5("AVE-1234") +
               der(0x04, payload) + extra)


def img4(im4p_bytes):
    return der(0x30, ia5("IMG4") + im4p_bytes + der(0xA0, der(0x30, ia5("IM4M"))))


# --- a synthetic firmware image ---------------------------------------------
DATA_VM = 0xD0000
DATA_SIZE = 0x8000          # __DATA vmsize
DATA_FILE = 0x2000          # file-backed part
TAGLIST = 0x300             # DATA offset of the patchbay
TUN_OFF = 0x1000            # DATA offset of the tunables table
TUN_CAP = 24


def make_image():
    """A 64-bit Mach-O: header, one LC_SEGMENT_64 __DATA, the file-backed DATA."""
    data = bytearray(DATA_FILE)
    recs = [("STKG", 8, 0), ("SOC_", 4, 0), ("SOCR", 4, 0), ("CpAd", 8, 0),
            ("WrAd", 8, 0), ("IOBA", 8, 0), ("TUNS", 8, DATA_VM + TUN_OFF),
            ("TUNZ", 4, 8 + 20 * TUN_CAP + 16), ("IOSZ", 4, 0)]
    o = TAGLIST
    for code, n, val in recs:
        data[o:o + 4] = code[::-1].encode()
        struct.pack_into("<I", data, o + 4, n)
        data[o + 8:o + 8 + n] = val.to_bytes(n, "little")
        o += 8 + n
    data[TUN_OFF:TUN_OFF + 8] = bytes([1, 3, TUN_CAP, 0]) + b"\xff" * 4
    data[TUN_OFF + 8 + 20 * TUN_CAP:TUN_OFF + 8 + 20 * TUN_CAP + 16] = b"\xa5" * 16
    data[0:16] = b"not the patchbay"
    hdr = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, 1, 72, 0, 0)
    fileoff = 0x1000
    seg = struct.pack("<II16sQQQQIIII", 0x19, 72, b"__DATA", DATA_VM, DATA_SIZE,
                      fileoff, DATA_FILE, 3, 3, 0, 0)
    img = bytearray(fileoff)
    img[:len(hdr)] = hdr
    img[len(hdr):len(hdr) + len(seg)] = seg
    return bytes(img) + bytes(data)


FILLS = dict(SOC_=0x6001, SOCR=0x11, CpAd=0x40D800000, WrAd=0x40DC00000,
             IOBA=0x40C000000, STKG=0x1122334455667788,
             tunables=(0x7, [(0x1000, 0xff, 0x12), (0x2008, 0xf0f0, 0x3030)]))


# --- a synthetic kernelcache --------------------------------------------------
KC_BASE = 0xFFFFFE0007004000
# made-up values in the real layout
DPE = dict(cat_default=[(0x010, 0x0000FFFF, 0x1234)],
           cac_default=[(0x020, 0x00FF0000, 0x110000), (0x024, 3, 2), (0x3FC, 0xF, 5)],
           cac_8bit=[(0x028, 0xF0, 0x50), (0x02C, 1, 0)])


def make_kernelcache(setname="Castor_6000", dpe=DPE, width=4, cat_base=0xDC000,
                     level=0, symbol=None):
    """MH_FILESET: __TEXT, __DATA_CONST, a com.apple.driver.AppleAVE2 entry whose
    Mach-O has an LC_SYMTAB naming the CfgSet; the CfgSet with chained pointers."""
    size = 0x10000
    d = bytearray(size)
    const_off = 0x4000                      # file offset = VA - KC_BASE
    kext_off = 0x8000
    sym_off, str_off = 0xA000, 0xB000
    # the top-level Mach-O
    cmds = b""
    cmds += struct.pack("<II16sQQQQIIII", 0x19, 72, b"__TEXT", KC_BASE, const_off, 0,
                        const_off, 5, 5, 0, 0)
    cmds += struct.pack("<II16sQQQQIIII", 0x19, 72, b"__DATA_CONST", KC_BASE + const_off,
                        size - const_off, const_off, size - const_off, 3, 3, 0, 0)
    name = b"com.apple.driver.AppleAVE2\0"
    fe = struct.pack("<IIQQII", 0x80000035, 0, KC_BASE + kext_off, kext_off, 32, 0) + name
    fe += b"\0" * (-len(fe) % 8)
    fe = fe[:4] + struct.pack("<I", len(fe)) + fe[8:]
    cmds += fe
    d[0:32] = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 12, 3, len(cmds), 0, 0)
    d[32:32 + len(cmds)] = cmds
    # the kext's own Mach-O header with LC_SYMTAB (kernelcache-wide offsets)
    syms = [symbol or f"__ZL30gs_sAVE_DPE_CfgSet_{setname}", "__ZL30gs_sAVE_DPE_CfgSet_Other_9999"]
    strtab = b"\0" + b"".join(s.encode() + b"\0" for s in syms)
    cfg_va = [KC_BASE + const_off + 0x100, KC_BASE + const_off + 0x180]
    nl = b""
    stridx = 1
    for s, va in zip(syms, cfg_va):
        nl += struct.pack("<IBBHQ", stridx, 0x0E, 1, 0, va)
        stridx += len(s) + 1
    st = struct.pack("<IIIIII", 0x02, 24, sym_off, len(syms), str_off, len(strtab))
    d[kext_off:kext_off + 32] = struct.pack("<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 11, 1,
                                            len(st), 0, 0)
    d[kext_off + 32:kext_off + 32 + len(st)] = st
    d[sym_off:sym_off + len(nl)] = nl
    d[str_off:str_off + len(strtab)] = strtab
    # the CfgSet and its tables
    o = const_off + 0x100
    struct.pack_into("<4Q", d, o, (0xDCBFC << 32) | cat_base, (0xDC3FC << 32) | cat_base,
                     (0xDCBFC << 32) | 0xDC400, 0)
    tab = const_off + 0x400
    for key, slot in (("cat_default", 0), ("cac_default", 3), ("cac_8bit", 4)):
        ents = dpe[key]
        ptr = (0x20 << 48) | (level << 30) | (tab - 0)   # offset from KC_BASE
        struct.pack_into("<QQ", d, o + 0x20 + 16 * slot, ptr if ents else 0, len(ents))
        for k, (off, clear, val) in enumerate(ents):
            struct.pack_into("<4I", d, tab + 16 * k, off, width, clear, val)
        tab += 16 * len(ents) + 16
    return bytes(d)


class Image4(unittest.TestCase):
    def test_im4p_payload(self):
        self.assertEqual(T.im4p_payload(im4p(b"hello")), ("avef", b"hello"))

    def test_long_form_length(self):
        p = bytes(range(256)) * 300            # needs a 3-byte length
        self.assertEqual(T.im4p_payload(im4p(p))[1], p)

    def test_img4_wrapper(self):
        p = b"\xcf\xfa\xed\xfe" + b"x" * 1000
        self.assertEqual(T.im4p_payload(img4(im4p(p))), ("avef", p))
        self.assertEqual(T.inner_im4p(img4(im4p(p))), im4p(p))
        self.assertEqual(T.inner_im4p(im4p(p)), im4p(p))

    def test_refuses_keybags(self):
        with self.assertRaisesRegex(T.Refused, "encrypted"):
            T.im4p_payload(im4p(b"x", extra=der(0x04, b"kbag")))

    def test_compression_info(self):
        comp = der(0x30, dint(1) + dint(4096))
        self.assertEqual(G.im4p_parse(im4p(b"bvx2....", "krnl", comp))[2], (1, 4096))
        with self.assertRaisesRegex(T.Refused, "compressed"):
            T.im4p_payload(im4p(b"bvx2....", extra=comp))
        with self.assertRaisesRegex(T.Refused, "compressed"):
            T.im4p_payload(im4p(b"bvx2...."))

    def test_refuses_other_magic(self):
        with self.assertRaises(T.DERError):
            T.im4p_payload(der(0x30, ia5("IM4M") + ia5("x")))

    def test_every_truncation_is_refused(self):
        good = img4(im4p(b"payload" * 40))
        for n in range(len(good)):
            with self.assertRaises(T.Refused, msg=f"truncated to {n}"):
                T.im4p_payload(good[:n])

    def test_length_past_container(self):
        bad = bytearray(im4p(b"abc"))
        bad[1] += 5
        with self.assertRaises(T.DERError):
            T.im4p_payload(bytes(bad))

    def test_indefinite_length(self):
        with self.assertRaisesRegex(T.DERError, "indefinite"):
            T.im4p_payload(b"\x30\x80\x00\x00")


class Dpe(unittest.TestCase):
    def test_tables_from_kernelcache(self):
        kc = G.Kernelcache(make_kernelcache())
        t = G.dpe_tables(kc, "Castor_6000")
        self.assertEqual(t, {k: list(v) for k, v in DPE.items()})
        b = G.dpe_encode(t)
        self.assertEqual(b[:8], b"AVEDPE01")
        self.assertEqual(len(b), 24 + 12 * 6)
        self.assertEqual(G.dpe_decode(b), t)

    def test_from_im4p_uncompressed_and_imgs(self):
        raw = make_kernelcache()
        self.assertEqual(G.kernelcache_macho(raw), raw)
        self.assertEqual(G.kernelcache_macho(im4p(raw, "krnl")), raw)
        with self.assertRaisesRegex(T.Refused, "not a kernelcache"):
            G.kernelcache_macho(im4p(raw, "avef"))

    @unittest.skipUnless(shutil.which("lzfse"), "no lzfse command")
    def test_lzfse_roundtrip(self):
        raw = make_kernelcache()
        enc = subprocess.run(["lzfse", "-encode"], input=raw, capture_output=True,
                             check=True).stdout
        k = im4p(enc, "krnl", der(0x30, dint(1) + dint(len(raw))))
        self.assertEqual(G.kernelcache_macho(k), raw)
        bad = im4p(enc, "krnl", der(0x30, dint(1) + dint(len(raw) + 1)))
        with self.assertRaisesRegex(T.Refused, "LZFSE output"):
            G.kernelcache_macho(bad)

    def test_lzfse_missing(self):
        old = shutil.which
        try:
            G.shutil.which = lambda name: None
            with self.assertRaisesRegex(T.Refused, "install lzfse"):
                G.lzfse_decode(b"bvx2", 10)
        finally:
            G.shutil.which = old

    def test_refusals(self):
        with self.assertRaisesRegex(T.Refused, "0 symbol"):
            G.dpe_tables(G.Kernelcache(make_kernelcache()), "Atlas_8112")
        with self.assertRaisesRegex(T.Refused, "32-bit register"):
            G.dpe_tables(G.Kernelcache(make_kernelcache(width=2)), "Castor_6000")
        with self.assertRaisesRegex(T.Refused, "windows"):
            G.dpe_tables(G.Kernelcache(make_kernelcache(cat_base=0xDD000)), "Castor_6000")
        with self.assertRaisesRegex(T.Refused, "cache level"):
            G.dpe_tables(G.Kernelcache(make_kernelcache(level=1)), "Castor_6000")
        # a symbol that merely contains the name is not it
        kc = G.Kernelcache(make_kernelcache(symbol="__ZL30xgs_sAVE_DPE_CfgSet_Castor_6000"))
        with self.assertRaisesRegex(T.Refused, "0 symbol"):
            G.dpe_tables(kc, "Castor_6000")

    def test_decode_refuses_bad_files(self):
        b = G.dpe_encode({k: list(v) for k, v in DPE.items()})
        for bad in (b[:-1], b"XXXXXXXX" + b[8:], b + b"\0" * 12):
            with self.assertRaises(T.Refused):
                G.dpe_decode(bad)


class Pristine(unittest.TestCase):
    def test_fills(self):
        img = make_image()
        blob = G.build_pristine(img, FILLS)
        self.assertEqual(len(blob), DATA_SIZE)
        self.assertEqual(blob[:16], b"not the patchbay")
        self.assertFalse(any(blob[DATA_FILE:]))
        tags = G.walk_tags(bytearray(blob))
        for name, n in G.FILL_TAGS:
            o = tags[name][0]
            self.assertEqual(int.from_bytes(blob[o:o + n], "little"), FILLS[name], name)
        self.assertEqual(blob[TUN_OFF:TUN_OFF + 4], bytes([1, 3, TUN_CAP, 2]))
        self.assertEqual(struct.unpack_from("<I", blob, TUN_OFF + 4)[0], 0x7)
        self.assertEqual(struct.unpack_from("<IQQ", blob, TUN_OFF + 8), FILLS["tunables"][1][0])
        e = TUN_OFF + 8 + 20 * TUN_CAP
        self.assertEqual(blob[e:e + 16], b"\xa5" * 16)

    def test_only_fill_bytes_change(self):
        img = make_image()
        d0, _ = G.image_data(img)
        blob = G.build_pristine(img, FILLS)
        tags = G.walk_tags(d0)
        allowed = set()
        for name, n in G.FILL_TAGS:
            allowed |= set(range(tags[name][0], tags[name][0] + n))
        allowed |= set(range(TUN_OFF, TUN_OFF + 8 + 20 * TUN_CAP))
        diff = {k for k in range(len(blob)) if blob[k] != d0[k]}
        self.assertTrue(diff)
        self.assertLessEqual(diff, allowed)

    def test_no_tunables(self):
        blob = G.build_pristine(make_image(), dict(FILLS, tunables=None))
        self.assertEqual(blob[TUN_OFF:TUN_OFF + 8], bytes([1, 3, TUN_CAP, 0]) + b"\xff" * 4)

    def test_controls_differ(self):
        a = G.build_pristine(make_image(), FILLS)
        self.assertNotEqual(a, G.build_pristine(make_image(), dict(FILLS, CpAd=0x40D801000)))
        self.assertNotEqual(a, G.build_pristine(make_image(), dict(FILLS, tunables=None)))
        self.assertNotEqual(a, G.build_pristine(make_image(), dict(FILLS, STKG=1)))

    def test_refuses_non_macho(self):
        with self.assertRaises(T.Refused):
            G.build_pristine(b"\0" * 4096, FILLS)

    def test_refuses_table_already_filled(self):
        img = bytearray(make_image())
        img[0x1000 + TUN_OFF + 3] = 1
        with self.assertRaisesRegex(T.Refused, "tunables"):
            G.build_pristine(bytes(img), FILLS)

    def test_check_pristine(self):
        img = make_image()
        blob = G.build_pristine(img, FILLS)
        v = G.check_pristine(img, blob, "t6001", 0)
        self.assertEqual((v["SOC_"], v["tunables"]), (0x6001, 2))
        with self.assertRaisesRegex(T.Refused, "encoder 1"):
            G.check_pristine(img, blob, "t6001", 1)
        with self.assertRaisesRegex(T.Refused, "t6000"):
            G.check_pristine(img, blob, "t6000", 0)
        bad = bytearray(blob)
        bad[0x10] ^= 1                                  # outside the fill set
        with self.assertRaisesRegex(T.Refused, "outside"):
            G.check_pristine(img, bytes(bad), "t6001", 0)
        bad = bytearray(blob)
        bad[TUN_OFF + 3] = TUN_CAP + 1                  # count > capacity
        with self.assertRaisesRegex(T.Refused, "tunables"):
            G.check_pristine(img, bytes(bad), "t6001", 0)
        with self.assertRaisesRegex(T.Refused, "bytes"):
            G.check_pristine(img, blob[:-1], "t6001", 0)


class Hashes(unittest.TestCase):
    def write(self, text):
        f = tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt")
        f.write(text)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_load_and_check(self):
        good = b"firmware"
        p = self.write(f"# comment\n\n{sha(good)}  apple/x.bin  what it is\n"
                       f"{sha(b'm')}  ipsw:Firmware/ave/X.im4p  size=1  member\n")
        k = T.load_hashes(p)
        self.assertEqual(k["ipsw:Firmware/ave/X.im4p"], (sha(b"m"), 1))
        self.assertEqual(T.check_hash(k, "apple/x.bin", good), sha(good))
        with self.assertRaisesRegex(T.Refused, "expected"):
            T.check_hash(k, "apple/x.bin", good + b"!")
        with self.assertRaisesRegex(T.Refused, "not listed"):
            T.check_hash(k, "apple/y.bin", good)
        with self.assertRaisesRegex(T.Refused, "bytes, expected 1"):
            T.check_hash(k, "ipsw:Firmware/ave/X.im4p", b"mm")

    def test_malformed_line(self):
        with self.assertRaises(ValueError):
            T.load_hashes(self.write("abc  apple/x.bin\n"))

    def test_real_list_covers_every_soc(self):
        k = T.load_hashes(REAL_HASHES)
        for soc, s in T.SOCS.items():
            for key in ("ipsw:" + T.ave_member(s["variant"]), "ipsw:" + s["kc"]):
                self.assertIn(key, k, soc)
                self.assertIsNotNone(k[key][1], f"{soc}: {key} has its size")
            self.assertIn(T.image_name(s["variant"]), k, soc)
            self.assertIn(G.dpe_file_name(s["dpe"]), k, soc)
            if s.get("built"):
                self.assertIn(s["pristine"][0], k, soc)


# --- archives and servers ----------------------------------------------------
def make_zip(path, members, zip64=True):
    with zipfile.ZipFile(path, "w") as z:
        for name, (data, method) in members.items():
            zi = zipfile.ZipInfo(name)
            zi.compress_type = method
            with z.open(zi, "w", force_zip64=zip64) as f:
                f.write(data)


class RangeHandler(http.server.BaseHTTPRequestHandler):
    data = b""
    honour_range = True
    requests = []

    def do_GET(self):
        rng = self.headers.get("Range")
        type(self).requests.append(rng)
        if rng and self.honour_range and rng.startswith("bytes="):
            a, b = rng[6:].split("-")
            a, b = int(a), min(int(b), len(self.data) - 1)
            body = self.data[a:b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(self.data)}")
        else:
            body = self.data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextlib.contextmanager
def serve(data, honour_range=True):
    h = type("H", (RangeHandler,), {"data": data, "honour_range": honour_range,
                                     "requests": []})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/x.ipsw", h
    finally:
        srv.shutdown()
        srv.server_close()


class Zip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.big = os.urandom(3000) * 50
        self.members = {
            "Firmware/ave/AppleAVE2FW_H13C.im4p": (self.big, zipfile.ZIP_DEFLATED),
            "Firmware/stored.bin": (b"stored member", zipfile.ZIP_STORED),
            "Restore/BuildManifest.plist": (b"<plist/>" * 1000, zipfile.ZIP_DEFLATED),
        }

    def check_zip(self, src):
        z = T.RemoteZip(src)
        self.assertEqual(set(z.members), set(self.members))
        for name, (data, _) in self.members.items():
            self.assertEqual(z.read(name), data)
        with self.assertRaises(T.Refused):
            z.read("missing")

    def test_local_zip64(self):
        p = os.path.join(self.tmp.name, "a.ipsw")
        make_zip(p, self.members)
        src = T.FileSource(p)
        self.check_zip(src)
        src.close()

    def test_local_plain_zip(self):
        p = os.path.join(self.tmp.name, "b.zip")
        make_zip(p, self.members, zip64=False)
        src = T.FileSource(p)
        self.check_zip(src)
        src.close()

    def test_corrupt_member_crc(self):
        p = os.path.join(self.tmp.name, "c.zip")
        make_zip(p, {"Firmware/stored.bin": (b"stored member", zipfile.ZIP_STORED)})
        b = bytearray(rd(p))
        b[b.find(b"stored member")] ^= 1
        wr(p, bytes(b))
        src = T.FileSource(p)
        with self.assertRaisesRegex(T.Refused, "CRC"):
            T.RemoteZip(src).read("Firmware/stored.bin")
        src.close()

    def test_not_a_zip(self):
        p = os.path.join(self.tmp.name, "d.zip")
        wr(p, b"\0" * 1000)
        src = T.FileSource(p)
        with self.assertRaisesRegex(T.Refused, "not a zip"):
            T.RemoteZip(src)
        src.close()

    def test_http_ranges_read_only_what_is_needed(self):
        p = os.path.join(self.tmp.name, "e.ipsw")
        pad = os.urandom(2_000_000)    # a large member nobody asks for
        make_zip(p, dict(self.members, **{"Restore/big.dmg": (pad, zipfile.ZIP_STORED)}))
        with serve(rd(p)) as (url, h):
            src = T.HTTPSource(url, retries=1)
            z = T.RemoteZip(src)
            self.assertEqual(z.read("Firmware/stored.bin"), b"stored member")
            self.assertLess(src.fetched, 200_000, "only the directory and one member")
            self.assertTrue(all(r and r.startswith("bytes=") for r in h.requests))

    def test_http_server_without_ranges_is_refused(self):
        with serve(b"x" * 100, honour_range=False) as (url, _):
            with self.assertRaisesRegex(T.Refused, "range"):
                T.HTTPSource(url, retries=1)


class EndToEnd(unittest.TestCase):
    """main() with synthetic Apple files under a synthetic known-hashes.txt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        self.image = make_image()
        self.im4p = im4p(self.image)
        self.kc = im4p(make_kernelcache(), "krnl")
        self.dpe = G.dpe_encode({k: list(v) for k, v in DPE.items()})
        self.hashes = os.path.join(self.d, "known-hashes.txt")
        with open(self.hashes, "w") as f:
            f.write(f"{sha(self.im4p)}  ipsw:Firmware/ave/AppleAVE2FW_H13C.im4p  size={len(self.im4p)}\n"
                    f"{sha(self.kc)}  ipsw:kernelcache.release.mac13j  size={len(self.kc)}\n"
                    f"{sha(self.image)}  apple/ave_h13c.bin\n"
                    f"{sha(self.dpe)}  apple/ave-13.5-dpe-castor_6000.bin\n")
        self.ipsw = os.path.join(self.d, "UniversalMac.ipsw")
        make_zip(self.ipsw, {"Firmware/ave/AppleAVE2FW_H13C.im4p": (self.im4p, zipfile.ZIP_DEFLATED),
                             "Firmware/ave/AppleAVE2FW_H13S.im4p": (b"other", zipfile.ZIP_DEFLATED),
                             "kernelcache.release.mac13j": (self.kc, zipfile.ZIP_STORED)})
        self.out = os.path.join(self.d, "out")
        self.esp = os.path.join(self.d, "esp")
        self.saved_esp, self.saved_dbg = T.ESP_DIRS, T.DEBUGFS
        T.ESP_DIRS = (self.esp,)
        T.DEBUGFS = os.path.join(self.d, "debugfs")
        self.addCleanup(setattr, T, "ESP_DIRS", self.saved_esp)
        self.addCleanup(setattr, T, "DEBUGFS", self.saved_dbg)

    def run_main(self, *args):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            rc = T.main(["--soc", "t6001", "--hashes", self.hashes, "--output-dir", self.out,
                         *args])
        return rc, buf_out.getvalue() + buf_err.getvalue()

    def files(self):
        out = {}
        for p in ("apple/ave_h13c.bin", "apple/ave-13.5-dpe-castor_6000.bin",
                  "apple/ave-13.5-data-pristine.bin"):
            f = os.path.join(self.out, p)
            if os.path.exists(f):
                out[p] = rd(f)
        return out

    def test_dry_run_touches_nothing(self):
        rc, out = self.run_main("--dry-run", "--url", "http://127.0.0.1:9/never")
        self.assertEqual(rc, 0, out)
        self.assertIn("Dry run", out)
        self.assertIn("AppleAVE2FW_H13C.im4p", out)
        self.assertIn("kernelcache.release.mac13j", out)
        self.assertFalse(os.path.exists(self.out))

    def test_dry_run_names_the_local_kernelcache(self):
        wr(os.path.join(self.esp, "kernelcache.release.mac13j"), self.kc)
        rc, out = self.run_main("--dry-run", "--url", "http://127.0.0.1:9/never")
        self.assertEqual(rc, 0, out)
        self.assertIn("no download", out)
        dl = next(l for l in out.splitlines() if l.startswith("Download:"))
        self.assertNotIn("kernelcache", dl)

    def test_not_a_terminal_without_yes(self):
        rc, out = self.run_main("--ipsw", self.ipsw)
        self.assertEqual(rc, 3, out)
        self.assertFalse(os.path.exists(self.out))

    def test_from_local_ipsw(self):
        rc, out = self.run_main("--ipsw", self.ipsw, "--yes")
        self.assertEqual(rc, 0, out)
        f = self.files()
        self.assertEqual(f["apple/ave_h13c.bin"], self.image)
        self.assertEqual(f["apple/ave-13.5-dpe-castor_6000.bin"], self.dpe)
        rc, out = self.run_main("--check")
        self.assertEqual(rc, 0, out)
        self.assertIn("not yet", out)              # the pristine blob comes later
        rc, out = self.run_main("--ipsw", self.ipsw, "--yes")
        self.assertIn("nothing to do", out)

    def test_from_http_with_the_esp_kernelcache(self):
        wr(os.path.join(self.esp, "kernelcache.release.mac13j"), self.kc)
        ipsw = os.path.join(self.d, "nokc.ipsw")     # an image without the kernelcache
        make_zip(ipsw, {"Firmware/ave/AppleAVE2FW_H13C.im4p": (self.im4p, zipfile.ZIP_DEFLATED)})
        with serve(rd(ipsw)) as (url, _):
            rc, out = self.run_main("--url", url, "--yes")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.files()), 2)

    def test_from_http(self):
        with serve(rd(self.ipsw)) as (url, _):
            rc, out = self.run_main("--url", url, "--yes")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.files()), 2)

    def test_from_dir_im4p_and_img4(self):
        root = os.path.join(self.d, "preboot")
        wr(os.path.join(root, "Restore", "Firmware", "ave", "AppleAVE2FW_H13C.im4p"), self.im4p)
        wr(os.path.join(root, "Restore", "kernelcache.release.mac13j"), self.kc)
        rc, out = self.run_main("--from-dir", root, "--yes")
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(self.files()), 2)
        # personalized copies (IMG4) carry the same IM4Ps
        shutil.rmtree(root)
        shutil.rmtree(self.out)
        wr(os.path.join(root, "boot", "x", "usr", "standalone", "firmware", "FUD", "AVE.img4"),
           img4(self.im4p))
        wr(os.path.join(root, "boot", "x", "System", "Library", "Caches",
                        "com.apple.kernelcaches", "kernelcache"), img4(self.kc))
        rc, out = self.run_main("--from-dir", root, "--yes")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.files()["apple/ave_h13c.bin"], self.image)

    def test_wrong_version_is_refused(self):
        other = im4p(self.image + b"newer")
        p = os.path.join(self.d, "other.ipsw")
        make_zip(p, {"Firmware/ave/AppleAVE2FW_H13C.im4p": (other, zipfile.ZIP_DEFLATED),
                     "kernelcache.release.mac13j": (self.kc, zipfile.ZIP_STORED)})
        rc, out = self.run_main("--ipsw", p, "--yes")
        self.assertEqual(rc, 1, out)
        self.assertIn("Nothing was installed", out)
        self.assertEqual(self.files(), {})

    def test_tampered_member_is_refused(self):
        bad = bytearray(self.im4p)
        bad[-1] ^= 0xFF
        p = os.path.join(self.d, "bad.ipsw")
        make_zip(p, {"Firmware/ave/AppleAVE2FW_H13C.im4p": (bytes(bad), zipfile.ZIP_DEFLATED),
                     "kernelcache.release.mac13j": (self.kc, zipfile.ZIP_STORED)})
        rc, out = self.run_main("--ipsw", p, "--yes")
        self.assertEqual(rc, 1, out)
        self.assertIn("sha256", out)
        self.assertEqual(self.files(), {})

    def test_wrong_tables_are_refused(self):
        # a kernelcache whose tables differ from the listed DPE file
        kc2 = im4p(make_kernelcache(dpe=dict(DPE, cac_8bit=[(0x028, 0xF0, 0x40)])), "krnl")
        with open(self.hashes, "a") as f:
            f.write(f"{sha(kc2)}  ipsw:kernelcache.release.mac13g  size={len(kc2)}\n")
        root = os.path.join(self.d, "dir")
        wr(os.path.join(root, "AppleAVE2FW_H13C.im4p"), self.im4p)
        wr(os.path.join(root, "kernelcache.release.mac13g"), kc2)
        rc, out = self.run_main("--from-dir", root, "--yes")
        self.assertEqual(rc, 1, out)
        self.assertIn("ave-13.5-dpe-castor_6000.bin", out)
        self.assertEqual(self.files(), {}, "nothing installed when one file fails")

    def test_unknown_soc(self):
        rc, out = self.run_main("--soc", "t8122", "--dry-run")
        self.assertEqual(rc, 1, out)

    def test_check_reports_missing(self):
        rc, out = self.run_main("--check")
        self.assertEqual(rc, 1)
        self.assertIn("absent", out)

    def test_capture(self):
        rc, out = self.run_main("--capture")
        self.assertEqual(rc, 1, out)               # nothing in debugfs yet
        self.run_main("--ipsw", self.ipsw, "--yes")
        cold = G.build_pristine(self.image, FILLS)
        wr(os.path.join(T.DEBUGFS, "apple_ave_iboot_data"), cold)
        bad = bytearray(cold)
        bad[0x10] ^= 1
        wr(os.path.join(T.DEBUGFS, "apple_ave1_iboot_data"), bytes(bad))  # ave1: owned, ignored
        rc, out = self.run_main("--capture")
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.files()["apple/ave-13.5-data-pristine.bin"], cold)
        rc, out = self.run_main("--check")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("not yet", out)
        # a second capture keeps the valid file
        wr(os.path.join(T.DEBUGFS, "apple_ave_iboot_data"),
           G.build_pristine(self.image, dict(FILLS, STKG=5)))
        rc, out = self.run_main("--capture")
        self.assertIn("kept", out)
        self.assertEqual(self.files()["apple/ave-13.5-data-pristine.bin"], cold)

    def test_capture_refuses_a_warm_copy(self):
        self.run_main("--ipsw", self.ipsw, "--yes")
        warm = bytearray(G.build_pristine(self.image, FILLS))
        warm[0x1800] ^= 0x55                       # a core has written DATA
        wr(os.path.join(T.DEBUGFS, "apple_ave_iboot_data"), bytes(warm))
        rc, out = self.run_main("--capture")
        self.assertEqual(rc, 1, out)
        self.assertNotIn("apple/ave-13.5-data-pristine.bin", self.files())


class Built(unittest.TestCase):
    def test_t8103_recipe_has_no_tunables(self):
        b = T.SOCS["t8103"]["built"]
        self.assertIsNone(b["tunables"])
        blob = G.build_pristine(make_image(), b)
        G.check_pristine(make_image(), blob, "t8103", 0)


class Detect(unittest.TestCase):
    def test_from_device_tree(self):
        with tempfile.TemporaryDirectory() as d:
            wr(os.path.join(d, "compatible"), b"apple,j314c\0apple,t6001\0apple,arm-platform\0")
            wr(os.path.join(d, "chosen", "asahi,os-fw-version"), b"13.5\0")
            old = T.DT
            T.DT = d
            try:
                self.assertEqual(T.detect(), ("t6001", "j314c", "13.5"))
            finally:
                T.DT = old


if __name__ == "__main__":
    unittest.main()
