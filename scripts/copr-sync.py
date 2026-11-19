#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Which packages does the COPR project still need to build?

  copr-sync.py [--project OWNER/PROJECT] [--build] [--retry-failed] [PACKAGE...]

For every package except the kernel (scripts/kernel-watch.py starts the
kernel's builds, after its prep check), compare the version-release its spec
on this checkout names with the COPR project's builds of that package:

  ok        the newest build is of this version-release and succeeded
  building  the newest build is of this version-release and still running
  failed    the newest build is of this version-release and failed: not
            retried (a daily retry would only fail again) unless
            --retry-failed is given
  missing   COPR has no build of this version-release yet (never built,
            or the spec moved on after a merge)

With --build, `copr-cli build-package` starts a build of every missing
package (needs a copr-cli config with the project's credentials). Without
it, nothing is changed. Prints one line per package, and key=value lines
for $GITHUB_OUTPUT at the end:

  missing=apple-avd qemu-vmapple      packages without a build of their spec
  failed=...                          packages whose build of their spec failed
  started=...                         builds started (with --build)

Exit status 0 unless something went wrong talking to COPR or starting a
build. Reading the project needs no credentials.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.dirname(HERE)
API = "https://copr.fedorainfracloud.org/api_3"
# Build timeouts in seconds, as in scripts/copr-setup.sh.
TIMEOUT = {"qemu-vmapple": 36000, "reims-vgpu-backend": 36000,
           "mesa-honeykrisp-plus": 18000, "mesa-coopmat": 18000}
RUNNING = {"pending", "starting", "importing", "running", "waiting", "forked"}


def packages():
    """Every package with its own spec (the kernel's spec comes from Fedora)."""
    out = []
    for name in sorted(os.listdir(os.path.join(TOP, "packages"))):
        if os.path.isfile(os.path.join(TOP, "packages", name, name + ".spec")):
            out.append(name)
    return out


def spec_evr(name):
    """version-release of packages/<name>/<name>.spec, without the dist tag
    (COPR records a build's source package that way)."""
    spec = os.path.join(TOP, "packages", name, name + ".spec")
    r = subprocess.run(["rpmspec", "-q", "--srpm", "--define", "dist %{nil}",
                        "--qf", "%{version}-%{release}", spec],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def copr_builds(project, name):
    """The package's builds, newest first, as (id, state, version-release)."""
    owner, proj = project.split("/", 1)
    q = urllib.parse.urlencode({"ownername": owner, "projectname": proj,
                                "packagename": name, "limit": 100})
    req = urllib.request.Request(f"{API}/build/list?{q}",
                                 headers={"User-Agent": "apple-silicon-kernel-plus"})
    with urllib.request.urlopen(req, timeout=60) as r:
        items = json.load(r)["items"]
    out = [(b["id"], b["state"], (b.get("source_package") or {}).get("version") or "")
           for b in items]
    return sorted(out, reverse=True)


def status(project, name, want):
    """(state, build id) of the newest build of exactly `want`."""
    builds = copr_builds(project, name)
    # A build whose SRPM step has not run yet has no version: count it as
    # building this one, so a second run does not start another.
    for bid, state, evr in builds:
        if evr == want or (not evr and state in RUNNING):
            if state == "succeeded":
                return "ok", bid
            if state in RUNNING:
                return "building", bid
            return "failed", bid
    return "missing", None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", default="aquarat/apple-silicon-kernel-plus")
    ap.add_argument("--build", action="store_true", help="start builds of missing packages")
    ap.add_argument("--retry-failed", action="store_true",
                    help="with --build: also rebuild packages whose build of this version failed")
    ap.add_argument("package", nargs="*", help="default: every package except the kernel")
    a = ap.parse_args()

    names = a.package or packages()
    unknown = sorted(set(names) - set(packages()))
    if unknown:
        sys.exit(f"copr-sync: no spec for {' '.join(unknown)} (the kernel: kernel-watch.py)")

    missing, failed, started = [], [], []
    for name in names:
        want = spec_evr(name)
        state, bid = status(a.project, name, want)
        print(f"{name:28} {want:40} {state}{f' (build {bid})' if bid else ''}")
        if state == "missing":
            missing.append(name)
        elif state == "failed":
            failed.append(name)

    todo = missing + (failed if a.retry_failed else [])
    if a.build:
        for name in todo:
            cmd = ["copr-cli", "build-package", a.project, "--name", name, "--nowait",
                   "--timeout", str(TIMEOUT.get(name, 3600))]
            print("+", " ".join(cmd), flush=True)
            subprocess.run(cmd, check=True)
            started.append(name)

    print(f"missing={' '.join(missing)}")
    print(f"failed={' '.join(failed)}")
    print(f"started={' '.join(started)}")


if __name__ == "__main__":
    main()
