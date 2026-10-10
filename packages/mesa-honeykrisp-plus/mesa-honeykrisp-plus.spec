# SPDX-License-Identifier: GPL-2.0-only
# mesa-honeykrisp-plus: Mesa's Asahi Vulkan driver (Honeykrisp) with this
# project's patches, installed in its own prefix next to the system Mesa.
# Nothing in /usr/lib64 or /usr/share/vulkan/icd.d is touched; programs use it
# only when VK_DRIVER_FILES points at its ICD file. See README.md.
#
# Keep Version equal to Fedora's mesa-vulkan-drivers for the target release,
# so the kernel interface and system libraries line up.
%global askp_prefix %{_libdir}/apple-silicon-kernel-plus/mesa
%global icd %{askp_prefix}/share/vulkan/icd.d/asahi_icd.%{_target_cpu}.json

# A private copy: provide nothing that other packages could pick up.
%global __provides_exclude_from ^%{askp_prefix}/.*$

Name:           mesa-honeykrisp-plus
Version:        26.2.4
Release:        1%{?dist}
Summary:        Patched Mesa Asahi Vulkan driver, installed beside the system Mesa
License:        MIT
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        https://archive.mesa3d.org/mesa-%{version}.tar.xz
Source1:        honeykrisp-plus
Patch1:         0001-asahi-widen-16-bit-varyings-before-st_vary.patch
Patch2:         0002-asahi-narrow-16-bit-flat-fragment-inputs.patch
ExclusiveArch:  aarch64

BuildRequires:  meson >= 1.3.0
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

Requires:       vulkan-loader

%description
Mesa %{version}'s Vulkan driver for Apple M1/M2 GPUs (Honeykrisp), built with
the patches of the apple-silicon-kernel-plus project, for the paravirtual
GPU of macOS guests (qemu-vmapple).

It is installed in its own directory under %{_libdir} and does not
replace the system Mesa. Programs use it only when VK_DRIVER_FILES names
its ICD file, or when started through the wrapper: honeykrisp-plus <command>
(honeykrisp-plus alone prints the VK_DRIVER_FILES value).

Patch 0002 is still being validated.
Built without window-system integration (no X11/Wayland surfaces), as the
macOS guest stack uses it: rendering is off-screen.

%prep
%autosetup -n mesa-%{version} -p1

%build
%set_build_flags
meson setup %{_vpath_builddir} \
    --prefix=%{askp_prefix} --libdir=lib --datadir=share --sysconfdir=%{_sysconfdir} \
    --buildtype=release -Db_ndebug=true \
    -Dvulkan-drivers=asahi -Dgallium-drivers= -Dplatforms= -Dglx=disabled \
    -Degl=disabled -Dgbm=disabled -Dopengl=false -Dgles1=disabled \
    -Dgles2=disabled -Dllvm=enabled -Dvideo-codecs= -Dtools= \
    -Dbuild-tests=false -Dvalgrind=disabled -Dlibunwind=disabled -Dlmsensors=disabled
%ninja_build -C %{_vpath_builddir}

%install
DESTDIR=%{buildroot} meson install -C %{_vpath_builddir} --no-rebuild
# Only the Vulkan driver, its ICD file and its drirc defaults are wanted.
rm -rf %{buildroot}%{askp_prefix}/include %{buildroot}%{askp_prefix}/lib/pkgconfig
test -f %{buildroot}%{icd}
install -D -m 0755 %{SOURCE1} %{buildroot}%{_bindir}/honeykrisp-plus
sed -i 's|@ICD@|%{icd}|' %{buildroot}%{_bindir}/honeykrisp-plus

%files
%license docs/license.rst
%{_bindir}/honeykrisp-plus
%dir %{_libdir}/apple-silicon-kernel-plus
%{askp_prefix}/

%changelog
* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 26.2.4-1
- First release: Mesa 26.2.4 Asahi Vulkan driver with 0001 (widen 16-bit
  varyings before st_vary) and 0002 (narrow 16-bit flat fragment inputs);
  0002 is still being validated
