# mesa-coopmat

Mesa's Vulkan driver for Apple M1/M2 GPUs (Honeykrisp, `libvulkan_asahi.so`)
with `VK_KHR_cooperative_matrix`, for GPU compute through ggml (llama.cpp,
stable-diffusion.cpp and other ggml programs). It is a parallel install: the system Mesa
stays the driver of every program, and a process uses this one only when
asked to.

| path | what |
|---|---|
| `/usr/lib64/apple-silicon-kernel-plus/mesa-coopmat/27.0.0-devel-5956a5be4777/lib/libvulkan_asahi.so` | the driver |
| `.../27.0.0-devel-5956a5be4777/share/vulkan/icd.d/asahi_icd.aarch64.json` | its ICD file, outside `/usr/share/vulkan/icd.d` |
| `.../27.0.0-devel-5956a5be4777/PROVENANCE` | source commit, tree, upstream base, driver SHA256 |
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

github.com/aquarat/mesa, branch `coopmat-27`, pinned in the spec:

| | |
|---|---|
| commit | `5956a5be4777994ff25cee9c5f85485eee460df2` (2026-11-19) |
| tree | `a617ac5972a62a1d7ffd946ec1933703b5547584` |
| upstream base | Mesa main `23732583a81cf342daa311e46afcf6d05012fae1` (2026-11-19, `27.0.0-devel`) |
| on top | 42 commits: Honeykrisp compute overlap and the light in-stream barrier for buffer-only compute dependencies, GPU timing/profiling (`HK_GPUTIME`, `HK_PERFTEST`), shader-cache key and bounds-check fixes, scratch and spill fixes, tessellation, `VK_EXT_fragment_shader_interlock`, the prototype `VK_KHR_cooperative_matrix` on the SIMD-group matrix FMA with native mixed f16 x f16 + f32 FMA, and a register allocation fix for `simd_matrix_fmadd`. The fork's README (its landing page) describes them commit by commit. |

`coopmat-27` is the previous pin's branch `coopmat` rebased onto Mesa main.
The three AGX compiler fixes that the previous pin `20e478a1ab11`
cherry-picked (`bebbaf49`, `bbeb2dca`, `b47973d0`) are upstream now and were
dropped. Every other commit applied unchanged, apart from a one-line
argument change in KosmicKrisp's `kk_shader.c`. The branch `coopmat` stays at
the previous pin as a reference.

`scripts/make-srpm.sh mesa-coopmat` fetches only that commit (shallow) and
refuses it unless its tree id and `VERSION` match the spec, so the SRPM's
Source0 is that tree whatever the branch does later. Build options as
`mesa-honeykrisp-plus`: Vulkan `asahi` only, no Gallium, no window systems,
LLVM on.

## Version drift

The branch is a Mesa main snapshot (27.0.0-devel), not Fedora's Mesa (26.2.x for Fedora
44). The Asahi DRM uAPI header is the same in this tree, in Fedora 44's Mesa
and in this project's 7.2 kernel and in Fedora Asahi Remix's 7.1 kernel, so
it runs on both. Moving the 42 commits onto a 26.2 release is not a
mechanical rebase (the compute and compiler changes depend on main); bump
the pin instead when the branch moves, or rebase the series onto newer Mesa
main on a new branch (as `coopmat-27` was):

1. `git ls-remote https://github.com/aquarat/mesa.git refs/heads/coopmat-27`
2. In the spec: `mesa_commit`, `mesa_tree` (`git rev-parse <commit>^{tree}`),
   `mesa_date`, `mesa_version` (the tree's `VERSION`), `mesa_base` and the
   `Version` tag; `Release: 1`; changelog.
3. `scripts/build-srpms.sh mesa-coopmat`, `rpmbuild --rebuild`, then
   validate: `with-coopmat vulkaninfo` lists `VK_KHR_cooperative_matrix`,
   ggml's `test-backend-ops` passes against the CPU backend over the 18
   operations listed under Status plus `MUL_MAT` (a quick check: MUL_MAT, RMS_NORM,
   FLASH_ATTN_EXT; before release: the full set, including q5 KV flash
   attention and `iq3_s` `GET_ROWS`), and a stock-vs-coopmat `llama-bench`.

## Status

Experimental. The previous pin `20e478a1ab11` is in daily use on M1 Max
(t6001) and M1 Pro (t6000) for ggml compute: llama.cpp,
stable-diffusion.cpp and CLIP image embeddings. This pin, `5956a5be4777`,
has passed the checks below but has not been deployed yet.
`VK_KHR_cooperative_matrix` here is a prototype from a personal branch, not
upstream Mesa. Report problems to this project, not to Mesa.

Compared with the system Mesa on the same machine (M1 Max, Qwen3.6-35B-A3B
UD-Q5_K_XL, `llama-bench -fa 1`):

- Prompt processing (pp512): 271.2 against 217.6 tokens/s (+25 %), the
  same as `20e478a1ab11` (271.0).
- Decode (tg128): 30.18 against 25.45 tokens/s (+19 %). `20e478a1ab11` did
  29.71; the gain comes from the light dependency barrier.
- Earlier pins: perplexity within noise of the system driver (ratio
  1.0005 ± 0.0010), mean KL divergence 0.003.

**Correctness (pin `5956a5be4777`, 2026-11-19).**

- ggml's `test-backend-ops` against the CPU backend (llama.cpp of
  2026-11-19), full suite: 23,116/23,116 with the RPM's driver. One run of a
  local build of the same commit failed one `SET_ROWS f32 -> q2_0` case.
  That case fails intermittently on every driver, including `20e478a1ab11`
  and upstream Mesa (1-2 runs in 100), because the test draws new random
  inputs and the CPU and GPU can round a tie differently.
- The 29-operation sweep (12,418 cases): all pass.
- Against `20e478a1ab11`: logits of Qwen3.6-35B-A3B differ only at rounding
  level (mean KL divergence about 0, same top token 100 % in prefill- and
  decode-shaped runs), and greedy text is identical.
- dEQP-VK 1.4.7.1 `compute.pipeline.*` (22,533 cases, including 17,924
  cooperative-matrix cases): no failures and no new ones against upstream
  Mesa main; the cooperative-matrix results are identical to
  `20e478a1ab11`.

The first pin, `71969e3`, failed 682 of 8848 cases of the 18-operation
sweep:

- `FLASH_ATTN_EXT` with a `q5_0`/`q5_1` K/V cache (674 cases);
- `GET_ROWS` on `iq3_s` (8 cases).

Both groups unpack bit fields at variable offsets. `71969e3`'s Mesa base
predates upstream `bbeb2dca` (AGX shifts do not mask the shift count, so
NIR's `bitfield_extract` and fused-shift patterns could read the wrong
bits). `20e478a1ab11` cherry-picked it, and this pin's base contains it. A
q5 KV cache and IQ3_S models are fine on `20e478a1ab11` and later, but not
on a host still running `71969e3`.
