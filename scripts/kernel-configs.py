#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply the config overlays in packages/kernel/configs to Fedora's kernel configs.

  kernel-configs.py apply SOURCES_DIR OVERLAY_DIR
      Rewrites every kernel-*-fedora.config in SOURCES_DIR. For each file,
      the overlays of its group are applied in this order (later wins):
          asahi-<group>.config   @asahi's own choices (from its 7.1.13 SRPM)
          plus-<group>.config    this project's choices and the values for
                                 symbols that are new in the Asahi 7.2 tree
      <group> is "aarch64" for kernel-aarch64-*, "s390x" for kernel-s390x-*,
      and "other" for the rest. A missing overlay file is skipped.
      A symbol already in the file is changed in place; a new one is
      appended. Lines are "CONFIG_FOO=value" or "# CONFIG_FOO is not set".

  kernel-configs.py diff OLD NEW
      Prints the symbols whose value differs between two config files
      (overlay syntax), e.g. to regenerate asahi-*.config from @asahi's and
      Fedora's SRPMs of the same kernel.

Only the Python standard library is used.
"""
import os
import re
import sys

SET = re.compile(r"^(CONFIG_\w+)=(.*)$")
UNSET = re.compile(r"^# (CONFIG_\w+) is not set$")


def parse_line(line):
    m = SET.match(line)
    if m:
        return m.group(1), m.group(2)
    m = UNSET.match(line)
    if m:
        return m.group(1), None
    return None, None


def fmt(sym, val):
    return f"# {sym} is not set" if val is None else f"{sym}={val}"


def load(path):
    out = {}
    with open(path) as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if not line.strip() or (line.startswith("#") and not UNSET.match(line)):
                continue
            sym, val = parse_line(line)
            if not sym:
                sys.exit(f"kernel-configs: {path}:{n}: not a config line: {line}")
            if sym in out:
                sys.exit(f"kernel-configs: {path}:{n}: {sym} given twice")
            out[sym] = val
    return out


def group(name):
    if name.startswith("kernel-aarch64-"):
        return "aarch64"
    if name.startswith("kernel-s390x-"):
        return "s390x"
    return "other"


def merge(path, overlay):
    with open(path) as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    seen = set()
    for i, line in enumerate(lines):
        sym, _ = parse_line(line)
        if sym in overlay:
            lines[i] = fmt(sym, overlay[sym])
            seen.add(sym)
    lines += [fmt(s, v) for s, v in sorted(overlay.items()) if s not in seen]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def cmd_apply(src, ovl):
    names = sorted(n for n in os.listdir(src) if re.match(r"kernel-.*-fedora\.config$", n))
    if not names:
        sys.exit(f"kernel-configs: no kernel-*-fedora.config in {src}")
    for n in names:
        used = []
        for kind in ("asahi", "plus"):
            p = os.path.join(ovl, f"{kind}-{group(n)}.config")
            if os.path.exists(p):
                merge(os.path.join(src, n), load(p))
                used.append(os.path.basename(p))
        print(f"{n}: {' + '.join(used) or 'unchanged'}")


def cmd_diff(old, new):
    a, b = load_any(old), load_any(new)
    for s in sorted(set(a) | set(b)):
        if a.get(s, "absent") != b.get(s, "absent"):
            print(fmt(s, b.get(s)) if s in b else f"# {s} removed")


def load_any(path):
    out = {}
    with open(path) as f:
        for line in f:
            sym, val = parse_line(line.rstrip("\n"))
            if sym:
                out[sym] = val
    return out


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "apply":
        cmd_apply(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 4 and sys.argv[1] == "diff":
        cmd_diff(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
