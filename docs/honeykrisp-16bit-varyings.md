# Honeykrisp: 16-bit varyings (mesa-honeykrisp-plus)

| | |
|---|---|
| patches | `packages/mesa-honeykrisp-plus/patches/0001-asahi-widen-16-bit-varyings-before-st_vary.patch`, `0002-asahi-narrow-16-bit-flat-fragment-inputs.patch` |
| package | `mesa-honeykrisp-plus` ([packages/mesa-honeykrisp-plus](../packages/mesa-honeykrisp-plus/README.md)) |
| pull requests | none: the package and both patches were added in commits `3a008e9` and `58fe1b4` (2026-10-10/11), before the PR history |

## What it does

- **0001** widens 16-bit vertex outputs to 32 bits by their type before
  `st_vary`: `f2f32` for floats, `i2i32` for signed and `u2u32` for other
  integers.
- **0002** narrows flat 16-bit fragment inputs from their 32-bit
  coefficient by type: `f2fN` for floats, `u2uN` (truncation) for integers,
  matching how 0001 widened them.

## Why

Varying slots (UVS) on the AGX GPU are 32-bit: `st_vary` only takes 32-bit
sources, and the fragment shader reads varyings as 32-bit values and
converts them after interpolation (`agx_nir_lower_interpolation`).

- A 16-bit vertex output, such as a half varying from SPIR-V `Float16`
  (Metal shaders translated to SPIR-V), reached `st_vary` as a 16-bit
  source, and the backend aborted the process compiling the pipeline
  (`value.size == AGX_SIZE_32`).
- The flat path (`load_input`) only asserted that the load was 32-bit
  (compiled out in release builds) and returned the 32-bit coefficient for
  a 16-bit load. A `half4` varying decorated Flat (a vertex colour from
  Metal's `[[flat]]`) then compiled to a 32-bit value standing in for a
  16-bit def, and the backend aborted on "Packing assertion failed ...
  unaligned reg". Release Mesa without 0001 aborts on the same pair with
  the other assertion.

An abort in the driver's compiler takes down the process that asked for
the pipeline: for macOS guests that is `reims-vgpu-backend` (formerly
QEMU), and with it the guest's GPU.

## Design and alternatives

- **Convert at the boundary, by type,** so the 32-bit slot convention of
  the hardware and of the interpolated path stays as it is; 0002 mirrors
  0001 for the flat path.
- **A separate install.** The patched driver goes to
  `/usr/lib64/apple-silicon-kernel-plus/mesa/` with its ICD file outside
  `/usr/share/vulkan/icd.d`, used only through `VK_DRIVER_FILES` (the
  `honeykrisp-plus` wrapper), so the system Mesa stays the driver of every
  other program. The Mesa version follows Fedora's (`26.2.4` for Fedora 44)
  so the kernel interface and system libraries match; the build is
  Vulkan-only, no window systems.

## Testing

Recorded in the package history: 0001 in use with macOS guests from the
start; 0002 first "being validated", then (`58fe1b4`) in production with
the Reims rendering fixes, which reach it on every Skia/Compose app in the
guest. No separate test suite results are recorded in this repository.

## Limitations and open items

- No recorded test beyond production use (for example a Mesa CTS run or a
  shader-level reproducer in the repository).
- The top-level README still lists 0002 as "in validation", while the
  package README says it is in use; one of them should be updated.

## Hardware

M1 and M2 GPUs, as Mesa's Asahi driver.

## Upstream status and provenance

Not submitted to Mesa: this repository records no merge request, and a
search of Mesa's GitLab for these titles finds none. This project's work, offered under MIT, Mesa's licence
(LICENSING.md), written from Mesa's source.
