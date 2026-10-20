# SPDX-License-Identifier: GPL-2.0-only
# qemu-vmapple: QEMU with the vmapple machine, for macOS guests on Apple
# silicon Linux hosts. Built as the macOS VM stack's
# `MODE=oop scripts/build-qemu.sh` builds it: github.com/aquarat/qemu-reims-vgpu
# at qemu_commit, on its own. Its paravirtual GPU slot holds apv-gpu-proxy,
# which forwards the device to a separate program (reims-vgpu-backend, its
# own package); no Reims, metal2vulkan, Rust or Vulkan code is built into or
# loaded by this QEMU, and the check section verifies that.
#
# Installed beside Fedora's qemu: the binary is
# /usr/libexec/qemu-vmapple/qemu-system-aarch64 (also /usr/bin/qemu-vmapple),
# data in /usr/share/qemu-vmapple. Nothing in Fedora's qemu paths.
#
# The SRPM carries every source (scripts/make-srpm.sh): QEMU with the meson
# subprojects it needs. The build needs no network.
%global qemu_commit  c6d87a8406ecd228fa917b7ceaba9dc89980f3af
%global qemu_date    20261018
%global qemu_short   %(c=%{qemu_commit}; echo ${c:0:12})
%global qemu_version 11.1.50
# apv-gpu-proxy protocol version (APV_PROXY_VERSION in the protocol header;
# make-srpm.sh checks it). The backend must speak the same version.
%global apv_protocol 1

Name:           qemu-vmapple
Version:        %{qemu_version}^%{qemu_date}git%(c=%{qemu_commit}; echo ${c:0:7})
Release:        1%{?dist}
Summary:        QEMU for macOS guests (vmapple machine, out-of-process GPU proxy)
# QEMU: GPL-2.0-only as a whole (its LICENSE); source files carry their own
# GPL-2.0-compatible licences, mostly GPL-2.0-or-later, some LGPL-2.1-or-later,
# MIT or BSD (TCG, util). apv-gpu-proxy.c: GPL-2.0-or-later; its protocol
# header: MIT. berkeley-softfloat-3 (linked): BSD-3-Clause.
License:        GPL-2.0-only AND GPL-2.0-or-later AND LGPL-2.1-or-later AND MIT AND BSD-2-Clause AND BSD-3-Clause
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        qemu-reims-vgpu-%{qemu_short}.tar.xz
Source1:        %{name}-%{version}-extra.tar.xz
ExclusiveArch:  aarch64

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  bison
BuildRequires:  flex
BuildRequires:  bzip2
BuildRequires:  binutils
BuildRequires:  glib2-devel
BuildRequires:  pixman-devel
BuildRequires:  gtk3-devel
BuildRequires:  libepoxy-devel
BuildRequires:  wayland-devel
BuildRequires:  libxkbcommon-devel
BuildRequires:  libslirp-devel
BuildRequires:  libfdt-devel
BuildRequires:  zlib-ng-compat-devel
BuildRequires:  gnutls-devel
BuildRequires:  nettle-devel
BuildRequires:  systemd-rpm-macros
# For the %%check that the virtio-net option ROM link resolves.
BuildRequires:  ipxe-roms-qemu

# The GPU device model (Reims) is a separate program in its own package.
# A guest without the paravirtual GPU (gfx-device=none) does not need it.
Recommends:     apv-gpu-proxy-backend = %{apv_protocol}
# virtio-net-pci loads efi-virtio.rom; it is Fedora's iPXE build, as in
# Fedora's qemu packages.
Requires:       ipxe-roms-qemu

%description
QEMU with the vmapple machine (Apple's Virtualization.framework platform),
KVM acceleration on Apple silicon and the avp,rtc clock macOS 26 expects.
The paravirtual GPU slot holds apv-gpu-proxy, a small device that forwards
the GPU's registers, interrupts and guest memory to a separate process,
reims-vgpu-backend (package reims-vgpu-backend), over a unix socket, shared
memory and eventfds. No GPU code is built into this QEMU.

Built from github.com/aquarat/qemu-reims-vgpu (commit %{qemu_short}),
aarch64-softmmu only. Installed beside Fedora's qemu packages:
/usr/libexec/qemu-vmapple/qemu-system-aarch64, also run as qemu-vmapple.

macOS guests also need the kernel from this project (KVM patches; its
no-syndrome MMIO emulation is on by default since kernel 7.2.11). This
package contains no macOS software or Apple firmware.

%package kvm-nisv
Summary:        Retired: the kernel's no-syndrome MMIO emulation is now on by default
BuildArch:      noarch

%description kvm-nisv
Empty. This package used to turn on the kernel parameter
kvm.emulate_nisv_ldst with a tmpfiles.d rule. The kernel from
apple-silicon-kernel-plus has it on by default since 7.2.11, so the rule is
gone. The package stays, empty and without scriptlets, so that upgrading
it does not switch the emulation off on the running kernel (the old
version's removal script did that). Remove it whenever you like.

%prep
%setup -q -n qemu-reims-vgpu-%{qemu_short} -a 1

%build
./configure \
    --prefix=%{_prefix} --libdir=%{_libdir} --datadir=%{_datadir} \
    --sysconfdir=%{_sysconfdir} --localstatedir=%{_localstatedir} \
    --bindir=%{_libexecdir}/qemu-vmapple --libexecdir=%{_libexecdir}/qemu-vmapple \
    --with-suffix=qemu-vmapple \
    --extra-cflags="%{optflags}" --extra-ldflags="%{build_ldflags}" \
    --target-list=aarch64-softmmu --enable-kvm --enable-gnutls --enable-gtk \
    --enable-slirp --disable-docs --disable-tools --disable-rust --disable-gettext \
    --disable-werror --disable-download \
    --disable-install-blobs --disable-guest-agent
%{__ninja} -C build %{_smp_mflags}

%install
# Install into a staging root and keep only our own directories: no desktop
# file, icons or other paths that Fedora's qemu packages own. No firmware
# blobs (--disable-install-blobs; vmapple boots the user's AVPBooter) and no
# guest agent; the one option ROM a guest needs, virtio-net's, links to
# Fedora's iPXE build as Fedora's qemu does.
DESTDIR=$PWD/stage %{__ninja} -C build install
mkdir -p %{buildroot}%{_libexecdir} %{buildroot}%{_datadir} %{buildroot}%{_bindir}
cp -a stage%{_libexecdir}/qemu-vmapple %{buildroot}%{_libexecdir}/
cp -a stage%{_datadir}/qemu-vmapple %{buildroot}%{_datadir}/
test -x %{buildroot}%{_libexecdir}/qemu-vmapple/qemu-system-aarch64
ln -s ../libexec/qemu-vmapple/qemu-system-aarch64 %{buildroot}%{_bindir}/qemu-vmapple
ln -s ../ipxe.efi/1af41000.rom %{buildroot}%{_datadir}/qemu-vmapple/efi-virtio.rom

%check
q=%{buildroot}%{_libexecdir}/qemu-vmapple/qemu-system-aarch64
test -f %{_datadir}/ipxe.efi/1af41000.rom
# The GPU proxy is there.
$q -device apv-gpu-proxy,help | grep -q '^apv-gpu-proxy options:'
# The licence split (LICENSING.md): no Reims, metal2vulkan, Rust or Vulkan
# code in this binary, and no Vulkan loader among its libraries.
# (`!` does not stop a script under -e, hence the explicit exits.)
if nm -D $q | grep -E 'reims_vgpu|metal2vulkan|rust_eh_personality|vkGetInstanceProcAddr'; then exit 1; fi
if strings -a $q | grep -E 'reims_vgpu_qemu_|metal2vulkan'; then exit 1; fi
if ldd $q | grep -i vulkan; then exit 1; fi

%files
%license COPYING LICENSE
%license %{name}-%{version}-extra/LICENSING.md
%doc %{name}-%{version}-extra/README.md README.asahi-kvm.md
%{_bindir}/qemu-vmapple
%{_libexecdir}/qemu-vmapple/
%{_datadir}/qemu-vmapple/

%files kvm-nisv
%license %{name}-%{version}-extra/LICENSE

%changelog
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 11.1.50^20261018gitc6d87a8-1
- Reims out of process: QEMU is now aquarat/qemu-reims-vgpu c6d87a8 built
  on its own, with the apv-gpu-proxy device (gfx-device=apv-gpu-proxy); the
  GPU device model is the separate program reims-vgpu-backend (package
  reims-vgpu-backend, recommended). QEMU no longer links Reims or
  metal2vulkan, needs no Rust or Vulkan, and %%check verifies that.
- The in-process reims-vgpu-mmio device is gone from this QEMU.
- The vmapple KVM wiring is the fork's rewrite (c9bd4dfb, 5deca34b).
- No longer installs QEMU's prebuilt firmware for other machines (OpenBIOS,
  SLOF, U-Boot, EDK2 and others; their sources are not in the SRPM, and
  vmapple boots the user's AVPBooter) or qemu-ga. efi-virtio.rom, which
  virtio-net-pci loads, links to Fedora's iPXE (ipxe-roms-qemu).

* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 11.1.50^20261011git51c70eb-2
- qemu-vmapple-kvm-nisv is retired: the kernel's no-syndrome MMIO emulation
  is on by default from kernel 7.2.11. The subpackage is now empty and has
  no scriptlets, so upgrading it leaves the running kernel's setting alone.

* Sun Oct 11 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 11.1.50^20261011git51c70eb-1
- reims-vgpu 51c70eb with qemu-reims-vgpu 6740a49: the copy path (guest
  data copied directly between guest RAM and mapped Vulkan memory) and the
  macOS 26 rendering fixes (pipelines with no fragment function,
  metal2vulkan byte-record attribute loads). Needs mesa-honeykrisp-plus
  with patch 0002.
- The forks were rewritten to drop session trailers from commit messages;
  294f148 is now 7bfdd68 and 2cd151d is 6740a49 (same trees).

* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 11.1.50^20261010git294f148-1
- First release: reims-vgpu 294f148 with qemu-reims-vgpu 2cd151d
