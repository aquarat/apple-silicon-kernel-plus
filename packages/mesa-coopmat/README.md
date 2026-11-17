# mesa-coopmat

Mesa's Vulkan driver for Apple M1/M2 GPUs (Honeykrisp, `libvulkan_asahi.so`)
with `VK_KHR_cooperative_matrix`, for GPU compute through ggml (llama.cpp,
stable-diffusion.cpp and other ggml programs). It is a parallel install: the system Mesa
stays the driver of every program, and a process uses this one only when
asked to.

| path | what |
|---|---|
| `/usr/lib64/apple-silicon-kernel-plus/mesa-coopmat/26.3.0-devel-20e478a1ab11/lib/libvulkan_asahi.so` | the driver |
| `.../26.3.0-devel-20e478a1ab11/share/vulkan/icd.d/asahi_icd.aarch64.json` | its ICD file, outside `/usr/share/vulkan/icd.d` |
| `.../26.3.0-devel-20e478a1ab11/PROVENANCE` | source commit, tree, upstream base, driver SHA256 |
| `/usr/lib64/apple-silicon-kernel-plus/mesa-coopmat/bin/with-coopmat` | runs a command with this driver |

The versioned directory changes with each source pin; the wrapper path
does not. Nothing is installed in `/usr/bin`; link the wrapper onto `PATH`
where it is wanted:

```sh
sudo ln -s /usr/lib64/apple-silicon-kernel-plus/mesa-coopmat/bin/with-coopmat /usr/local/bin/
with-coopmat vulkaninfo --summary       # one command with the coopmat driver
with-coopmat                            # prints VK_DRIVER_FILES=... and VK_ICD_FILENAMES=...
```

`with-coopmat` sets `VK_DRIVER_FILES` and `VK_ICD_FILENAMES` to the ICD file
and execs the command. `LD_LIBRARY_PATH` is not needed: the ICD file names
the driver by absolute path.

For a systemd service, either `ExecStart=/usr/lib64/.../bin/with-coopmat
<program>` or set the two variables in the unit
(`with-coopmat > /etc/<service>.env` gives an `EnvironmentFile`). A service
that must not change driver silently on a package update can name the
versioned ICD path directly: after an update that path is gone and the
service fails to find a GPU instead of running a different driver.

Long-running ggml jobs on this driver have been run with
`GGML_VK_MAX_NODES_PER_SUBMIT=1` (one graph node per Vulkan submission). That
is a ggml setting, not part of the driver; set it in the job if you need it.

## Source

github.com/aquarat/mesa, branch `coopmat`, pinned in the spec:

| | |
|---|---|
| commit | `20e478a1ab11f06d388c29fdbffbab85f349ccdd` (2026-11-17) |
| tree | `515e3eeabb5e013d5cd74a438b5ced319321331a` |
| upstream base | Mesa main `063a4640270ba4e1cf9ca7e916fcc090ab24c3a4` (2026-08-26, `26.3.0-devel`) |
| on top | 39 commits: Honeykrisp compute overlap, GPU timing/profiling (`HK_PERFTEST`), scratch and spill fixes, tessellation, `VK_EXT_fragment_shader_interlock`; then `d105715` (review fixes), `77e6f99` (prototype `VK_KHR_cooperative_matrix` on the SIMD-group matrix FMA), `7dd673b` (native mixed f16 x f16 + f32 FMA), `71969e3` (register allocation fix for `simd_matrix_fmadd`); then 3 AGX compiler fixes cherry-picked (`-x`) from later Mesa main, all three backported upstream to mesa-26.2.7 (`bbeb2dca` already in 26.2.6): `bebbaf49` (phi register shuffling order, MR 44475), `bbeb2dca` (mask the shift count of `bitfield_extract` and the fused shift ops, MR 44700), `b47973d0` (signext optimisation with `abs`, MR 45571) |

`scripts/make-srpm.sh mesa-coopmat` fetches only that commit (shallow) and
refuses it unless its tree id and `VERSION` match the spec, so the SRPM's
Source0 is that tree whatever the branch does later. Build options as
`mesa-honeykrisp-plus`: Vulkan `asahi` only, no Gallium, no window systems,
LLVM on.

## Version drift

The branch is a Mesa main snapshot, not Fedora's Mesa (26.2.x for Fedora
44). The Asahi DRM uAPI header is the same in this tree, in Fedora 44's Mesa
and in this project's 7.2 kernel and in Fedora Asahi Remix's 7.1 kernel, so
it runs on both. Moving the 39 commits onto a 26.2 release is not a
mechanical rebase (the compute and compiler changes depend on main); bump
the pin instead when the branch moves:

1. `git ls-remote https://github.com/aquarat/mesa.git refs/heads/coopmat`
2. In the spec: `mesa_commit`, `mesa_tree` (`git rev-parse <commit>^{tree}`),
   `mesa_date`, `mesa_version` (the tree's `VERSION`), `mesa_base` and the
   `Version` tag; `Release: 1`; changelog.
3. `scripts/build-srpms.sh mesa-coopmat`, `rpmbuild --rebuild`, then
   validate: `with-coopmat vulkaninfo` lists `VK_KHR_cooperative_matrix`,
   ggml's `test-backend-ops` (MUL_MAT, RMS_NORM, FLASH_ATTN_EXT) passes
   against the CPU backend, and a stock-vs-coopmat `llama-bench`.

## Status

Experimental. In daily use on M1 Max (t6001) and M1 Pro (t6000) for ggml
compute: llama.cpp, stable-diffusion.cpp and CLIP image embeddings.
`VK_KHR_cooperative_matrix` here is a prototype from a personal branch, not
upstream Mesa. Report problems to this project, not to Mesa.

Compared with the system Mesa on the same machine:

- Faster prompt processing: a 24B Q6_K perplexity run took 3.5 instead of
  4.7 minutes.
- Perplexity within noise (ratio 1.0005 ± 0.0010) and mean KL divergence
  0.003 against the system driver's logits.
- CLIP embeddings are bit-identical between builds of this commit.

**Known bad.** ggml's `test-backend-ops` against the CPU backend, over 19
operations (flash attention, `MUL_MAT_ID`, `GET_ROWS`, `SET_ROWS`, `CPY`,
`ROPE`, `SOFT_MAX`, norms, SSM and delta-net ops), fails 682 of 8848 cases
that all pass with the system Mesa:

- `FLASH_ATTN_EXT` with a `q5_0`/`q5_1` K/V cache (674 cases);
- `GET_ROWS` on `iq3_s` (8 cases).

Everything else in that run passes, including F16/F32/q4/q8 K/V flash
attention and all `MUL_MAT_ID` types. So do not use a q5 KV cache
(`-ctk`/`-ctv q5_0`/`q5_1`) or IQ3_S models with this driver until a release
says otherwise.

Those results are for the first pin, `71969e3`. Both failing groups unpack
bit fields at variable offsets, and the system Mesa 26.2.6 has upstream
`bbeb2dca` (AGX shifts do not mask the shift count, so NIR's
`bitfield_extract` and fused-shift patterns could read the wrong bits) while
`71969e3`'s base predates it. The pin `20e478a1ab11` adds that fix and two
other compiler fixes. It is expected to clear these failures but has not been
run on a GPU yet: rerun the sweep before relying on q5 KV or IQ3_S.
