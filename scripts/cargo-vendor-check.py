#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
"""Checks on a `cargo vendor --versioned-dirs` tree, for scripts/make-srpm.sh.

  cargo-vendor-check.py prune VENDOR
      Remove prebuilt binaries (static and import libraries, objects, DLLs)
      from the vendored crates, and drop them from each crate's
      .cargo-checksum.json so cargo still verifies every other file. None of
      them is used on aarch64 Linux: they are Windows import libraries
      (windows_*, winapi-*-gnu), wasm runtime objects and test DLLs. Prints
      what it removed.

  cargo-vendor-check.py licences TAG METADATA LINKED VENDOR
      TAG       the spec's License tag
      METADATA  `cargo metadata --format-version 1` of the workspace
      LINKED    one "name version" per line: the crates linked into the binary
      Every crate in VENDOR (and every workspace package) must have a licence
      expression that Fedora allows, each AND part satisfied by one OR
      choice: the linked crates from TAG alone, the others (build scripts,
      proc-macros, other targets' crates, all in the SRPM) from TAG plus
      FEDORA_ALLOWED_EXTRA. Exits non-zero with the list of failures.
"""
import json
import os
import re
import sys

# Licences on Fedora's allowed list
# (https://docs.fedoraproject.org/en-US/legal/allowed-licenses/) that crates
# which are vendored but not linked may carry, beyond the License tag.
FEDORA_ALLOWED_EXTRA = {
    "0BSD", "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-2-Clause",
    "BSD-3-Clause", "BSL-1.0", "ISC", "MIT", "MIT-0", "MPL-2.0",
    "Unicode-3.0", "Unicode-DFS-2016", "Unlicense", "Zlib",
}

BINARY = re.compile(r"\.(a|lib|o|obj|dll|so(\.[0-9.]+)?|dylib|exe)$")


def prune(vendor):
    removed = []
    for crate in sorted(os.listdir(vendor)):
        root = os.path.join(vendor, crate)
        if not os.path.isdir(root):
            continue
        gone = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                if BINARY.search(fn):
                    p = os.path.join(dirpath, fn)
                    os.unlink(p)
                    gone.append(os.path.relpath(p, root))
        if not gone:
            continue
        ck = os.path.join(root, ".cargo-checksum.json")
        with open(ck, encoding="utf-8") as f:
            sums = json.load(f)
        for g in gone:
            sums["files"].pop(g.replace(os.sep, "/"), None)
        with open(ck, "w", encoding="utf-8") as f:
            json.dump(sums, f, sort_keys=True, separators=(",", ":"))
        # Directories left empty (lib/ of the import-library crates).
        for dirpath, _, _ in sorted(os.walk(root), key=lambda t: -len(t[0])):
            if dirpath != root and not os.listdir(dirpath):
                os.rmdir(dirpath)
        removed += [f"{crate}/{g}" for g in gone]
    for r in removed:
        print(r)


# --- SPDX expressions: WITH binds tighter than AND, AND tighter than OR ---
def tokens(expr):
    expr = expr.replace("/", " OR ")
    return re.findall(r"\(|\)|[A-Za-z0-9.+-]+", expr)


def parse(toks):
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take():
        nonlocal pos
        pos += 1
        return toks[pos - 1]

    def atom():
        t = take()
        if t == "(":
            e = disj()
            if take() != ")":
                raise ValueError("unbalanced parentheses")
            return e
        if t in ("AND", "OR", "WITH", ")"):
            raise ValueError(f"unexpected {t}")
        if peek() == "WITH":
            take()
            return ("id", f"{t} WITH {take()}")
        return ("id", t)

    def conj():
        parts = [atom()]
        while peek() == "AND":
            take()
            parts.append(atom())
        return ("and", parts) if len(parts) > 1 else parts[0]

    def disj():
        parts = [conj()]
        while peek() == "OR":
            take()
            parts.append(conj())
        return ("or", parts) if len(parts) > 1 else parts[0]

    e = disj()
    if pos != len(toks):
        raise ValueError("trailing tokens")
    return e


def ok(e, allowed):
    kind, v = e
    if kind == "id":
        return v in allowed
    if kind == "and":
        return all(ok(x, allowed) for x in v)
    return any(ok(x, allowed) for x in v)


def ids(e):
    kind, v = e
    return {v} if kind == "id" else set().union(*(ids(x) for x in v))


def licences(tag, metadata, linked, vendor):
    in_tag = ids(parse(tokens(tag)))
    with open(metadata, encoding="utf-8") as f:
        meta = json.load(f)
    with open(linked, encoding="utf-8") as f:
        linked = {tuple(l.split()[:2]) for l in f if l.strip()}
    pkgs = {(p["name"], p["version"]): p for p in meta["packages"]}
    bad = []
    vendored = sorted(d for d in os.listdir(vendor) if os.path.isdir(os.path.join(vendor, d)))
    for d in vendored:
        if not any(f"{n}-{v}" == d for n, v in pkgs):
            bad.append(f"{d}: vendored, but not in cargo metadata")
    for (name, ver), p in sorted(pkgs.items()):
        lic = (p.get("license") or "").strip()
        what = f"{name} {ver}"
        if not lic:
            bad.append(f"{what}: no SPDX licence expression")
            continue
        try:
            e = parse(tokens(lic))
        except (ValueError, IndexError) as ex:
            bad.append(f"{what}: {lic!r}: {ex}")
            continue
        if (name, ver) in linked:
            if not ok(e, in_tag):
                bad.append(f"{what} (linked): {lic}: not covered by the License tag")
        elif not ok(e, in_tag | FEDORA_ALLOWED_EXTRA):
            bad.append(f"{what} (vendored): {lic}: not an allowed licence")
    missing = linked - set(pkgs)
    bad += [f"{n} {v}: linked, but not in cargo metadata" for n, v in sorted(missing)]
    if bad:
        sys.exit("licence check failed:\n  " + "\n  ".join(bad))
    print(f"{len(pkgs)} packages ({len(vendored)} vendored, {len(linked)} linked): licences OK")


def main(argv):
    if len(argv) == 2 and argv[0] == "prune":
        prune(argv[1])
    elif len(argv) == 5 and argv[0] == "licences":
        licences(*argv[1:])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
