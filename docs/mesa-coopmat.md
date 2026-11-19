# Honeykrisp with cooperative matrices (mesa-coopmat)

| | |
|---|---|
| package | `mesa-coopmat` ([packages/mesa-coopmat](../packages/mesa-coopmat/README.md)) |
| source | [aquarat/mesa](https://github.com/aquarat/mesa) branch `coopmat`, pinned to `20e478a1ab11` (tree `515e3eeabb5e`) in the spec; no patch files in this repository |
| pull requests | #1 (the package, pin `71969e3`), #16 (pin `20e478a1ab11`: three upstream AGX compiler fixes), #17 (GPU validation of that pin) |

## What it does

Mesa's Asahi Vulkan driver (Honeykrisp) built from a Mesa main snapshot
with `VK_KHR_cooperative_matrix`, for GPU compute through ggml
(llama.cpp, stable-diffusion.cpp, CLIP embeddings). It installs into its
own versioned directory with its own ICD file; `with-coopmat <command>`
selects it for one process, and the system Mesa stays everyone else's
driver.

The source is Mesa main `063a4640270b` (2026-08-26, `26.3.0-devel`) plus
39 commits (Honeykrisp compute overlap, GPU timing, scratch and spill
fixes, tessellation, `VK_EXT_fragment_shader_interlock`, the prototype
`VK_KHR_cooperative_matrix` on the SIMD-group matrix FMA, native mixed
f16 x f16 + f32 FMA, a register allocation fix for `simd_matrix_fmadd`),
plus three AGX compiler fixes cherry-picked (`-x`) from later Mesa main:

| upstream commit | merge request | fix |
|---|---|---|
| `bbeb2dca` | !44700 | mask the shift count of `bitfield_extract` and the fused shift ops (AGX shifts do not mask it; NIR assumes they do) |
| `bebbaf49` | !44475 | phi register shuffling order (register allocation) |
| `b47973d0` | !45571 | skip the signext optimisation with `abs` |

## Why

Cooperative matrices let ggml's Vulkan backend use the GPU's SIMD-group
matrix units: a 24B Q6_K perplexity run took 3.5 instead of 4.7 minutes
compared with the system Mesa on the same machine.

The second pin (#16) fixed correctness. ggml's `test-backend-ops` on the
first pin (`71969e3`) failed 682 of 8848 cases: `FLASH_ATTN_EXT` with a
`q5_0`/`q5_1` K/V cache (674) and `GET_ROWS` on `iq3_s` (8), while the
system Mesa 26.2.6 passed them all. 26.2.6 contains `bbeb2dca`; the coopmat
base predates it. Both failing groups unpack bit fields at variable
offsets, and `GET_ROWS` uses no cooperative matrices, which pointed at the
base, not the coopmat code.

## Design and alternatives

- **Pin a commit and verify it.** `scripts/make-srpm.sh mesa-coopmat`
  fetches only the pinned commit and refuses it unless its tree id and
  `VERSION` match the spec, so the SRPM's source is that tree whatever the
  branch does later. A `PROVENANCE` file records commit, tree, upstream
  base and the driver's SHA-256.
- **Opt-in per process, versioned paths.** Nothing in `icd.d` or
  `/usr/bin`; the versioned directory changes with each pin, the wrapper
  path does not. A service that must not change driver silently can name
  the versioned ICD path and fails to find a GPU after an upgrade instead.
- **Cherry-pick the three fixes rather than rebase.** The 39 commits depend
  on Mesa main; moving them onto a 26.2 release is not a mechanical rebase,
  so the pin moves with the branch and needed upstream fixes are
  cherry-picked. All three were also backported upstream to 26.2.7.

## Testing

- #1: built with `rpmbuild --rebuild` in a Fedora 44 container; rpmlint 0
  errors; installed and in daily use on an M1 Max (t6001) and an M1 Pro
  (t6000).
- #16: the SRPM tree check passes; rpmlint 0 errors; an RPM build in a
  Fedora 44 container passed `%check`.
- #17, pin `20e478a1ab11` on an M1 Max with kernel 7.3.1 `plus3`:
  - `vulkaninfo` lists `VK_KHR_cooperative_matrix` with the wrapper and not
    without it;
  - `test-backend-ops` against the CPU backend: 8848/8848 over the 18
    operations of the original sweep (`71969e3`: 8166/8848), plus
    2592/2592 `MUL_MAT` and 136/136 GLU cases; q5 KV flash attention
    674/674 and `iq3_s` `GET_ROWS` 8/8;
  - logits against the system Mesa (Devstral 24B Q6_K, 6 x 2048 tokens):
    mean KL divergence 0.002826, 99th percentile 0.0204, same top token
    97.133%, perplexity ratio 1.0005 ± 0.0010, identical to `71969e3`;
  - CLIP embeddings are bit-identical between builds of this commit;
  - no kernel GPU messages.

## Limitations and open items

- `VK_KHR_cooperative_matrix` here is a prototype from a personal branch,
  not upstream Mesa; problems go to this project, not to Mesa.
- A Mesa main snapshot, not Fedora's Mesa; the Asahi DRM uAPI header is the
  same as in Fedora 44's Mesa and the kernels this project builds.
- Hosts still on the first pin (`71969e3`) keep the q5 KV / `iq3_s`
  failures.
- Long-running ggml jobs have been run with
  `GGML_VK_MAX_NODES_PER_SUBMIT=1` (a ggml setting, not part of the
  driver).

## Hardware

M1 and M2 GPUs; run on t6001 (M1 Max) and t6000 (M1 Pro).

## Upstream status and provenance

Mesa code under MIT. The base and the three compiler fixes are upstream
Mesa (authorship in Mesa's history). The 39 commits on top, including the
cooperative-matrix prototype, are on the personal `coopmat` branch and not
submitted upstream as far as this repository records.
