#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Find and fetch the Fedora Asahi Remix kernel SRPM from the @asahi/kernel COPR.

The answer comes from the published repository metadata of one chroot, which
is what `dnf` on a Fedora Asahi Remix machine sees. COPR build states are not
used: @asahi builds can fail on other chroots and are published by hand.

  asahi-kernel.py latest                 print the newest kernel NVR, e.g. 7.1.13-402.asahi.fc44
  asahi-kernel.py url [NVR]              print the SRPM URL (default: the newest)
  asahi-kernel.py fetch [NVR] DIR        download the SRPM into DIR, check its sha256
                                         against the metadata, print the path

Options (before the command): --chroot fedora-44-aarch64 (default),
--repo URL (default: the @asahi/kernel results URL for the chroot).
Environment: ASAHI_KERNEL_REPO overrides --repo.
Only the Python standard library is used.
"""
import argparse
import gzip
import hashlib
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

COPR_RESULTS = "https://download.copr.fedorainfracloud.org/results/@asahi/kernel/{chroot}/"
NS = {"repo": "http://linux.duke.edu/metadata/repo",
      "common": "http://linux.duke.edu/metadata/common",
      "rpm": "http://linux.duke.edu/metadata/rpm"}


def die(msg):
    print(f"asahi-kernel: {msg}", file=sys.stderr)
    sys.exit(1)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "apple-silicon-kernel-plus"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def rpmvercmp(a, b):
    """rpm's version segment comparison (lib/rpmvercmp.c), without tilde/caret
    subtleties beyond what kernel releases use."""
    if a == b:
        return 0
    seg = re.compile(r"(\d+|[a-zA-Z]+|~|\^)")
    sa, sb = seg.findall(a), seg.findall(b)
    for x, y in zip(sa, sb):
        if x == y:
            continue
        if x == "~" or y == "~":
            return -1 if x == "~" else 1
        if x == "^" or y == "^":
            return 1 if x == "^" else -1
        xd, yd = x.isdigit(), y.isdigit()
        if xd and yd:
            xi, yi = int(x), int(y)
            if xi != yi:
                return 1 if xi > yi else -1
        elif xd != yd:
            return 1 if xd else -1
        elif x != y:
            return 1 if x > y else -1
    if len(sa) == len(sb):
        return 0
    rest = (sa if len(sa) > len(sb) else sb)[min(len(sa), len(sb))]
    longer_is_a = len(sa) > len(sb)
    if rest == "~":
        return -1 if longer_is_a else 1
    return 1 if longer_is_a else -1


def kernel_srpms(repo):
    repomd = ET.fromstring(get(repo + "repodata/repomd.xml"))
    href = None
    for d in repomd.findall("repo:data", NS):
        if d.get("type") == "primary":
            href = d.find("repo:location", NS).get("href")
    if not href:
        die("no primary metadata in " + repo)
    primary = gzip.decompress(get(repo + href))
    out = []
    for pkg in ET.fromstring(primary).findall("common:package", NS):
        if pkg.findtext("common:name", namespaces=NS) != "kernel":
            continue
        if pkg.findtext("common:arch", namespaces=NS) != "src":
            continue
        v = pkg.find("common:version", NS)
        ck = pkg.find("common:checksum", NS)
        out.append({
            "nvr": f"{v.get('ver')}-{v.get('rel')}",
            "ver": v.get("ver"), "rel": v.get("rel"),
            "href": pkg.find("common:location", NS).get("href"),
            "sha256": ck.text if ck.get("type") == "sha256" else None,
        })
    if not out:
        die("no kernel SRPM in " + repo)
    return out


def newest(pkgs):
    best = pkgs[0]
    for p in pkgs[1:]:
        c = rpmvercmp(p["ver"], best["ver"]) or rpmvercmp(p["rel"], best["rel"])
        if c > 0:
            best = p
    return best


def pick(pkgs, nvr):
    if not nvr:
        return newest(pkgs)
    for p in pkgs:
        if p["nvr"] == nvr or p["nvr"] == nvr.removeprefix("kernel-"):
            return p
    die(f"kernel {nvr} is not in the repository (have: {', '.join(sorted(p['nvr'] for p in pkgs))})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chroot", default="fedora-44-aarch64")
    ap.add_argument("--repo")
    ap.add_argument("command", choices=["latest", "url", "fetch", "list"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    repo = os.environ.get("ASAHI_KERNEL_REPO") or a.repo or COPR_RESULTS.format(chroot=a.chroot)
    if not repo.endswith("/"):
        repo += "/"
    pkgs = kernel_srpms(repo)

    if a.command == "list":
        for p in sorted(pkgs, key=lambda p: p["nvr"]):
            print(p["nvr"])
    elif a.command == "latest":
        print(newest(pkgs)["nvr"])
    elif a.command == "url":
        print(repo + pick(pkgs, a.args[0] if a.args else None)["href"])
    elif a.command == "fetch":
        if not a.args:
            die("fetch needs a directory")
        dest = a.args[-1]
        p = pick(pkgs, a.args[0] if len(a.args) > 1 else None)
        os.makedirs(dest, exist_ok=True)
        path = os.path.join(dest, os.path.basename(p["href"]))
        if not (os.path.exists(path) and p["sha256"] and
                hashlib.sha256(open(path, "rb").read()).hexdigest() == p["sha256"]):
            data = get(repo + p["href"])
            have = hashlib.sha256(data).hexdigest()
            if p["sha256"] and have != p["sha256"]:
                die(f"sha256 mismatch for {p['href']}: {have}, metadata says {p['sha256']}")
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        print(path)


if __name__ == "__main__":
    main()
