#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Does the COPR project need a kernel build for the current @asahi kernel?

  kernel-watch.py [--project aquarat/apple-silicon-kernel-plus] [--chroot fedora-44-aarch64]

Compares the newest kernel SRPM published by @asahi/kernel (the base, e.g.
7.1.13-402.asahi) with the base of the newest kernel build in our COPR
project (7.1.13-402.asahi.plus1 -> 7.1.13-402.asahi). Prints key=value lines
(for $GITHUB_OUTPUT):

  asahi_nvr=7.1.13-402.asahi.fc44
  asahi_base=7.1.13-402.asahi
  ours_base=7.1.13-401.asahi        (empty if there is no build yet)
  ours_state=succeeded
  build=true|false
  reason=...

build=false when our newest build already has the same base and did not fail.
If it failed for the same base, build=false too (no daily retries of a
failing build); reason says so, and the workflow reports it.
Only public COPR APIs are used; no credentials.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("asahi_kernel", os.path.join(HERE, "asahi-kernel.py"))
ak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ak)

API = "https://copr.fedorainfracloud.org/api_3"


def base_of(evr):
    """7.1.13-402.asahi.plus1.fc44 / 7.1.13-402.asahi.fc44 / 7.1.13-402.asahi -> 7.1.13-402.asahi"""
    evr = re.sub(r"\.fc\d+$", "", evr)
    return re.sub(r"\.plus\d+$", "", evr)


def latest_build(project, package):
    owner, name = project.split("/", 1)
    url = (f"{API}/package/?ownername={owner}&projectname={name}"
           f"&packagename={package}&with_latest_build=True")
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    b = (data.get("builds") or {}).get("latest")
    if not b:
        return None
    return {"state": b.get("state"), "version": (b.get("source_package") or {}).get("version") or ""}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="aquarat/apple-silicon-kernel-plus")
    ap.add_argument("--chroot", default="fedora-44-aarch64")
    a = ap.parse_args()

    repo = ak.COPR_RESULTS.format(chroot=a.chroot)
    asahi = ak.newest(ak.kernel_srpms(repo))
    asahi_base = base_of(asahi["nvr"])
    ours = latest_build(a.project, "kernel")
    ours_base = base_of(ours["version"]) if ours and ours["version"] else ""
    state = ours["state"] if ours else ""

    if not ours or not ours_base:
        build, reason = True, "no kernel build in the project yet"
    elif ours_base != asahi_base:
        v1, r1 = asahi_base.split("-", 1)
        v2, r2 = ours_base.split("-", 1)
        newer = (ak.rpmvercmp(v1, v2) or ak.rpmvercmp(r1, r2)) > 0
        build = newer
        reason = (f"@asahi has {asahi_base}, the project has {ours_base}" if newer else
                  f"the project's {ours_base} is newer than @asahi's published {asahi_base}")
    elif state in ("failed", "canceled"):
        build, reason = False, f"the project's build of {ours_base} is {state}; not retrying automatically"
    else:
        build, reason = False, f"the project already has {ours_base} ({state})"

    for k, v in (("asahi_nvr", asahi["nvr"]), ("asahi_base", asahi_base), ("ours_base", ours_base),
                 ("ours_state", state), ("build", str(build).lower()), ("reason", reason)):
        print(f"{k}={v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
