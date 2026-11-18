# drm/asahi: drain deferred GPUVM BOs of kernel mappings (7.2 line only)

| | |
|---|---|
| patch | `packages/kernel/patches/0004-drm-asahi-Drain-deferred-GPUVM-BOs-when-a-kernel-map.patch`, **on branch `kernel-7.2` only** (7.2.11 `plus5`) |
| subject | drm/asahi: Drain deferred GPUVM BOs when a kernel mapping is dropped |
| pull requests | #2 (7.2.11 `plus5`), #7 (brought to `kernel-7.2`) |
| `main` | not carried: the 7.3.1 Asahi base (`c2e6784b008c`) already has the fix (#3, #9) |

## What it does

When a `KernelMappingInner` is dropped, the patch drops its `GpuVmBo`
explicitly and drains the owning GPUVM's deferred list. The struct's field
order is unchanged, so the GEM reference and then the owning GPUVM are
released after the cleanup, as the comment on the struct requires.

## Why

`KernelMappingInner` holds a `GpuVmBo` reference released with
`drm_gpuvm_bo_put_deferred()`: the last put only moves the vm_bo to the
GPUVM's deferred list, and it, its GEM reference and its pages are freed
only when someone calls `drm_gpuvm_bo_deferred_cleanup()` on that GPUVM.
User VMs do that when they are torn down, but kernel mappings live in the
device's kernel VM, which never is. Userspace timestamp buffers are mapped
there: each process that loaded a model with llama.cpp's Vulkan backend
left about 239 MB of unevictable shmem behind after a clean exit, with no
GPU faults, and 3.8 GB had accumulated on one machine.

## Design and alternatives

A backport of the `KernelMappingInner` part of Asahi's asahi-wip commit
`256b1204c12d` ("drm/asahi: Adjustment for v7.2 + partial drm-rust v7.3",
Janne Grunau). That commit also reorders the struct's fields; the backport
keeps the 7.2.11 field order so that the release order the struct's comment
requires still holds. The 7.2 line stays on its pinned Asahi commit;
`main` moved to 7.3.1, whose base has the fix, so the backport exists only
for the 7.2 line.

## Testing

Recorded in #2: a full 16k RPM build of the tree; build-tested. A runtime
A/B (GEM reproducer, model loads) was in progress when #2 merged
([consolidation-plan.md](consolidation-plan.md)); its results are not
recorded in this repository.

## Limitations and open items

- Runtime results are not recorded here (see Testing).
- Only the 7.2.11 line (`kernel-7.2`) carries it.

## Hardware

All machines the Asahi GPU driver supports (M1 and M2 families).

## Upstream status and provenance

Upstream in the Asahi tree (`256b1204c12d`); this patch is a partial
backport of it. The authorship of the upstream change is in that commit.
