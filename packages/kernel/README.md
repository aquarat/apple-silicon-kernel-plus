# packages/kernel

The kernel package is not a spec of ours. `scripts/make-srpm.sh kernel` takes
the newest kernel SRPM that the `@asahi/kernel` COPR has published for
`fedora-44-aarch64`, and changes three things:

1. `patches/*.patch` become the SRPM's `linux-kernel-test.patch`, which
   Fedora's `kernel.spec` applies after its own patches. `@asahi` ships that
   file empty; the script refuses to overwrite a non-empty one.
2. `kernel-plus.conf` settings go at the top of `kernel.spec`: the build id
   (`.plus1`) and the variants that are not built. Only the 16k kernel is
   built: `kernel-16k`, `-core`, `-modules`, `-modules-core`,
   `-modules-extra`, `-modules-internal`, `-devel`, `-devel-matched`. Debug
   kernels, debuginfo, UKIs, `kernel-headers`, `kernel-tools`, `perf` and the
   4k kernel are not built; those stay `@asahi`'s. (The spec also emits an
   empty `kernel-modules-extra-matched` meta package; nothing needs it.)
3. One `%changelog` entry naming the patches.

Everything else is `@asahi`'s spec, configuration and sources, unchanged.

## The patches

| patch | what | default |
|---|---|---|
| 0001 | KVM: save, restore and expose Apple's PAuth virtualization state (VM key, APSTS, APCTL, KERNKEYLO/HI). Needed by macOS guests on QEMU's `vmapple` machine. Only acts on Apple CPUs with ACTLR virtualization (M1, M2), and only for guests | always on |
| 0002 | KVM: decode and emulate MMIO loads/stores that fault without an instruction syndrome (XNU's pre-indexed store to the GIC) | **off**; `kvm.emulate_nisv_ldst=1` |

0001 is a rebase of work by Anees Iqbal (see `CREDITS.md`). 0002 is this
project's own work.

Both are in `git format-patch` form against the `@asahi` kernel source
(`linux-<ver>.tar.xz` plus `patch-<major>-redhat.patch`).
`docs/maintainer-guide.md` shows how to rebase them.
