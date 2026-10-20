#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Kernel status for the daily watch: does COPR need a build, and has
anything upstream moved that a maintainer should look at?

  kernel-watch.py [--project aquarat/apple-silicon-kernel-plus] [--chroot fedora-44-aarch64]

The kernel is built from the Asahi tree at the commit pinned in
packages/kernel/kernel-plus.conf; it never moves by itself
(docs/update-policy.md). This script prints key=value lines (for
$GITHUB_OUTPUT):

  ours=7.2.11-900.asahiwip.plus1      what kernel-plus.conf builds
  copr=7.2.11-900.asahiwip.plus1      the project's newest kernel build (empty: none)
  copr_state=succeeded
  build=true|false                    true: kernel-plus.conf names a release COPR
                                      has not built (after a merged bump)
  reason=...
  wip_head=<commit>                   the head of ASAHI_BRANCH now
  wip_moved=true|false                it is not ASAHI_COMMIT
  wip_version=7.2.12                  the kernel version at wip_head (empty: unknown)
  asahi_nvr=7.1.13-402.asahi.fc44     @asahi's newest published kernel
  asahi_newer=true|false              it would sort above ours (dnf would offer it)
  stable=7.2.13                       kernel.org's newest release of our series
  stable_newer=true|false             it is newer than KERNEL_VERSION
  notices=...                         a one-line summary for a warning

build=false if the newest COPR build already has the release (any state:
a failed build is not retried daily; reason says so).
Network: GitHub (git ls-remote, raw Makefile), kernel.org, COPR. No
credentials.
"""
import argparse
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "packages", "kernel", "kernel-plus.conf")
API = "https://copr.fedorainfracloud.org/api_3"
spec = importlib.util.spec_from_file_location("asahi_kernel", os.path.join(HERE, "asahi-kernel.py"))
ak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ak)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "apple-silicon-kernel-plus"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def read_conf(path):
    """The plain VAR=value lines of kernel-plus.conf (shell quoting allowed)."""
    out = {}
    with open(path) as f:
        for line in f:
            m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line.strip())
            if m:
                v = shlex.split(m.group(2))
                out[m.group(1)] = v[0] if v else ""
    return out


def evr_cmp(a, b):
    """rpm comparison of two version-release strings."""
    va, ra = a.split("-", 1)
    vb, rb = b.split("-", 1)
    return ak.rpmvercmp(va, vb) or ak.rpmvercmp(ra, rb)


def strip_dist(evr):
    return re.sub(r"\.fc\d+$", "", evr)


def latest_build(project, package):
    owner, name = project.split("/", 1)
    url = (f"{API}/package/?ownername={owner}&projectname={name}"
           f"&packagename={package}&with_latest_build=True")
    try:
        data = json.loads(get(url))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    b = (data.get("builds") or {}).get("latest")
    if not b:
        return None
    return {"state": b.get("state"), "version": (b.get("source_package") or {}).get("version") or ""}


def wip_head(repo, branch):
    out = subprocess.run(["git", "ls-remote", repo, f"refs/heads/{branch}"],
                         check=True, capture_output=True, text=True, timeout=120).stdout.split()
    return out[0] if out else ""


def makefile_version(repo, commit):
    m = re.match(r"https://github\.com/([^/]+/[^/.]+)(\.git)?$", repo)
    if not m or not commit:
        return ""
    try:
        mk = get(f"https://raw.githubusercontent.com/{m.group(1)}/{commit}/Makefile").decode()
    except (urllib.error.URLError, TimeoutError):
        return ""
    v = {k: re.search(rf"^{k} = (.*)$", mk, re.M) for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL", "EXTRAVERSION")}
    if not all(v[k] for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL")):
        return ""
    return f"{v['VERSION'][1]}.{v['PATCHLEVEL'][1]}.{v['SUBLEVEL'][1]}{v['EXTRAVERSION'][1] if v['EXTRAVERSION'] else ''}"


def stable_latest(series):
    rel = json.loads(get("https://www.kernel.org/releases.json"))
    vers = [r["version"] for r in rel.get("releases", [])
            if r.get("version", "").startswith(series + ".") or r.get("version") == series]
    best = ""
    for v in vers:
        if not best or ak.rpmvercmp(v, best) > 0:
            best = v
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="aquarat/apple-silicon-kernel-plus")
    ap.add_argument("--chroot", default="fedora-44-aarch64")
    a = ap.parse_args()
    c = read_conf(CONF)
    ver = c["KERNEL_VERSION"]
    ours = f"{ver}-{c['PKGRELEASE']}.{c['BUILDID']}"
    notices = []

    b = latest_build(a.project, "kernel")
    copr = strip_dist(b["version"]) if b and b["version"] else ""
    state = b["state"] if b else ""
    if not copr:
        build, reason = True, "no kernel build in the project yet"
    elif copr == ours:
        build = False
        reason = (f"the project's build of {ours} is {state}; not retrying automatically"
                  if state in ("failed", "canceled") else f"the project already has {ours} ({state})")
    elif evr_cmp(ours, copr) > 0:
        build, reason = True, f"kernel-plus.conf names {ours}, the project's newest build is {copr}"
    else:
        build, reason = False, f"the project's {copr} is newer than kernel-plus.conf's {ours}"

    head = wip_head(c["ASAHI_REPO"], c["ASAHI_BRANCH"])
    moved = bool(head) and head != c["ASAHI_COMMIT"]
    wver = makefile_version(c["ASAHI_REPO"], head) if moved else ver
    if moved:
        notices.append(f"{c['ASAHI_BRANCH']} moved to {head[:12]} (Linux {wver or '?'})")

    asahi = ak.newest(ak.kernel_srpms(ak.COPR_RESULTS.format(chroot=a.chroot)))
    asahi_newer = evr_cmp(strip_dist(asahi["nvr"]), ours) > 0
    if asahi_newer:
        notices.append(f"@asahi's {asahi['nvr']} sorts above {ours}: dnf offers it unless this COPR has priority")
    elif ak.rpmvercmp(asahi["ver"], ver) >= 0:
        notices.append(f"@asahi publishes {asahi['nvr']}, the same series as ours")

    series = ".".join(ver.split(".")[:2])
    stable = stable_latest(series)
    stable_newer = bool(stable) and ak.rpmvercmp(stable, ver) > 0
    if stable_newer:
        notices.append(f"kernel.org has {stable}, we are on {ver}")

    for k, v in (("ours", ours), ("copr", copr), ("copr_state", state), ("build", str(build).lower()),
                 ("reason", reason), ("wip_head", head), ("wip_moved", str(moved).lower()),
                 ("wip_version", wver), ("asahi_nvr", asahi["nvr"]), ("asahi_newer", str(asahi_newer).lower()),
                 ("stable", stable), ("stable_newer", str(stable_newer).lower()),
                 ("notices", "; ".join(notices))):
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
