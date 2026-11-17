# SPDX-License-Identifier: GPL-2.0-only
# mesa-coopmat: Mesa's Asahi Vulkan driver (Honeykrisp) with cooperative
# matrices (VK_KHR_cooperative_matrix on the SIMD-group matrix FMA), for GPU
# compute jobs (llama.cpp, stable-diffusion.cpp and other ggml programs).
#
# Opt-in and per process: everything is in its own versioned prefix under
# %%{_libdir}/apple-silicon-kernel-plus/mesa-coopmat/. Nothing goes into the
# system library path, /usr/bin or /usr/share/vulkan/icd.d, so the system Mesa stays
# the driver of every other program. A program uses this driver only when
# started through with-coopmat or with VK_DRIVER_FILES naming its ICD file.
#
# Source: github.com/aquarat/mesa, branch coopmat, pinned to mesa_commit.
# make-srpm.sh fetches exactly that commit and refuses it unless its tree is
# mesa_tree and its VERSION file is mesa_version. It is upstream Mesa main
# 063a4640270b (26.3.0-devel) plus 39 commits of this project; it is not
# Fedora's Mesa version (README.md, "Version drift").
%global mesa_commit  71969e371aeab8bc8fdcaa970d08230d52a9442e
%global mesa_tree    b2dd2c16cf1ddc94bc573ff05aee9335de22f17a
%global mesa_date    20260906
%global mesa_version 26.3.0-devel
%global mesa_base    063a4640270ba4e1cf9ca7e916fcc090ab24c3a4
%global mesa_short   %(c=%{mesa_commit}; echo ${c:0:12})

%global coopmat_root   %{_libdir}/apple-silicon-kernel-plus/mesa-coopmat
%global coopmat_prefix %{coopmat_root}/%{mesa_version}-%{mesa_short}
%global icd            %{coopmat_prefix}/share/vulkan/icd.d/asahi_icd.%{_target_cpu}.json

# A private copy: provide nothing that other packages could pick up.
%global __provides_exclude_from ^%{coopmat_root}/.*$
# Every file of the main package under coopmat_root: the /usr/lib/.build-id
# links go to the -debuginfo subpackage, the licence into the prefix.
%global _build_id_links alldebug

Name:           mesa-coopmat
Version:        26.3.0~devel^%{mesa_date}git%(c=%{mesa_commit}; echo ${c:0:7})
Release:        1%{?dist}
Summary:        Mesa Asahi Vulkan driver with cooperative matrices, opt-in per process
License:        MIT
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        mesa-coopmat-%{mesa_short}.tar.xz
Source1:        with-coopmat
Source2:        README.md
ExclusiveArch:  aarch64

BuildRequires:  meson >= 1.4.0
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  bison
BuildRequires:  flex
BuildRequires:  python3-devel
BuildRequires:  python3-mako
BuildRequires:  python3-pycparser
BuildRequires:  python3-pyyaml
BuildRequires:  python3-packaging
BuildRequires:  kernel-headers
BuildRequires:  systemd-devel
BuildRequires:  pkgconfig(libdrm) >= 2.4.133
BuildRequires:  pkgconfig(expat)
BuildRequires:  pkgconfig(zlib) >= 1.2.3
BuildRequires:  pkgconfig(libzstd)
BuildRequires:  pkgconfig(libelf)
BuildRequires:  llvm-devel >= 7.0.0
BuildRequires:  clang-devel
BuildRequires:  pkgconfig(libclc)
BuildRequires:  pkgconfig(SPIRV-Tools)
BuildRequires:  pkgconfig(LLVMSPIRVLib)
BuildRequires:  vulkan-headers
BuildRequires:  glslang
BuildRequires:  pkgconfig(vulkan)
BuildRequires:  python3

Requires:       vulkan-loader

%description
Mesa's Vulkan driver for Apple M1/M2 GPUs (Honeykrisp) from the coopmat
branch of github.com/aquarat/mesa (commit %{mesa_short}): Mesa main of
2026-08-26 (%{mesa_version}) with this project's Honeykrisp compute and
profiling changes and VK_KHR_cooperative_matrix, which ggml's Vulkan backend
uses for matrix multiplication and flash attention.

It is installed in its own versioned directory under
%{_libdir}/apple-silicon-kernel-plus/mesa-coopmat/ and does not
replace the system Mesa. Programs use it only when started through the
wrapper in that directory (bin/with-coopmat <command>) or with
VK_DRIVER_FILES set to its ICD file. Built without window-system
integration (no X11/Wayland surfaces): it is for compute.

%prep
%autosetup -n mesa-coopmat-%{mesa_short}
test "$(cat VERSION)" = "%{mesa_version}"

%build
%set_build_flags
meson setup %{_vpath_builddir} \
    --prefix=%{coopmat_prefix} --libdir=lib --datadir=share --sysconfdir=%{_sysconfdir} \
    --buildtype=release -Db_ndebug=true \
    -Dvulkan-drivers=asahi -Dgallium-drivers= -Dplatforms= -Dglx=disabled \
    -Degl=disabled -Dgbm=disabled -Dopengl=false -Dgles1=disabled \
    -Dgles2=disabled -Dllvm=enabled -Dvideo-codecs= -Dtools= \
    -Dbuild-tests=false -Dvalgrind=disabled -Dlibunwind=disabled -Dlmsensors=disabled
%ninja_build -C %{_vpath_builddir}

%install
DESTDIR=%{buildroot} meson install -C %{_vpath_builddir} --no-rebuild
# Only the Vulkan driver, its ICD file and its drirc defaults are wanted.
rm -rf %{buildroot}%{coopmat_prefix}/include %{buildroot}%{coopmat_prefix}/lib/pkgconfig
install -D -m 0755 %{SOURCE1} %{buildroot}%{coopmat_root}/bin/with-coopmat
sed -i 's|@ICD@|%{icd}|' %{buildroot}%{coopmat_root}/bin/with-coopmat
install -m 0644 %{SOURCE2} %{buildroot}%{coopmat_prefix}/README.md
install -m 0644 docs/license.rst %{buildroot}%{coopmat_prefix}/license.rst
cat > %{buildroot}%{coopmat_prefix}/PROVENANCE <<EOF
package:  %{name}-%{version}-%{release}
source:   https://github.com/aquarat/mesa branch coopmat
commit:   %{mesa_commit} (%{mesa_date})
tree:     %{mesa_tree}
upstream: Mesa main %{mesa_base} (%{mesa_version})
EOF

%check
# The ICD file must name the driver in this prefix, not a system path.
python3 -I - %{buildroot}%{icd} %{coopmat_prefix}/lib/libvulkan_asahi.so <<'EOF'
import json, sys
icd = json.load(open(sys.argv[1]))
path = icd["ICD"]["library_path"]
if path != sys.argv[2]:
    sys.exit(f"ICD library_path is {path}, expected {sys.argv[2]}")
EOF
test -x %{buildroot}%{coopmat_prefix}/lib/libvulkan_asahi.so
grep -q '^ICD=%{icd}$' %{buildroot}%{coopmat_root}/bin/with-coopmat
# Nothing outside the package's own directory (debug files go to the
# -debuginfo/-debugsource subpackages).
test -z "$(cd %{buildroot} && find . ! -type d ! -path '.%{coopmat_root}/*' \
    ! -path './usr/lib/debug/*' ! -path './usr/src/debug/*')"
# The driver's hash as installed: %check runs after rpmbuild has split the
# debug info off and stripped it, which %install would be too early for.
echo "driver:   lib/libvulkan_asahi.so sha256 $(sha256sum %{buildroot}%{coopmat_prefix}/lib/libvulkan_asahi.so | cut -d' ' -f1) (as installed)" \
    >> %{buildroot}%{coopmat_prefix}/PROVENANCE

%files
%license %{coopmat_prefix}/license.rst
%doc %{coopmat_prefix}/README.md
%dir %{_libdir}/apple-silicon-kernel-plus
%dir %{coopmat_root}
%{coopmat_root}/bin/
%dir %{coopmat_prefix}
%{coopmat_prefix}/PROVENANCE
%{coopmat_prefix}/lib/
%{coopmat_prefix}/share/

%changelog
* Tue Nov 17 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 26.3.0~devel^20260906git71969e3-1
- First release: aquarat/mesa coopmat 71969e371aea (Mesa main 063a4640270b +
  39 commits). Opt-in per process through with-coopmat; the system Mesa stays
  the default
