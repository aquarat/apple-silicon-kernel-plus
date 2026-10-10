# SPDX-License-Identifier: GPL-2.0-only
# qemu-vmapple: QEMU with the vmapple machine and the Reims paravirtual GPU,
# for macOS guests on Apple silicon Linux hosts. Built as the macOS VM
# stack's scripts/build-qemu.sh does: github.com/aquarat/reims-vgpu at
# reims_commit, whose vendor/qemu submodule pins github.com/aquarat/qemu-reims-vgpu
# at qemu_commit; Reims is a Rust staticlib that QEMU's meson build links in.
#
# Installed beside Fedora's qemu: the binary is
# /usr/libexec/qemu-vmapple/qemu-system-aarch64 (also /usr/bin/qemu-vmapple),
# data in /usr/share/qemu-vmapple. Nothing in Fedora's qemu paths.
#
# The SRPM carries every source (scripts/make-srpm.sh): Reims with QEMU and
# the meson subprojects QEMU needs, and the Rust crates from `cargo vendor`
# (the metal2vulkan git dependency included). The build needs no network.
%global reims_commit 294f1489b0469916dcc69ccb624349d386378d47
%global qemu_commit  2cd151d3b483759e8a527077f9680a54c5ecb93f
%global reims_date   20261010
%global reims_short  %(echo %{reims_commit} | cut -c1-12)
%global qemu_version 11.1.50

Name:           qemu-vmapple
Version:        %{qemu_version}^%{reims_date}git%(echo %{reims_commit} | cut -c1-7)
Release:        1%{?dist}
Summary:        QEMU for macOS guests (vmapple machine, Reims paravirtual GPU)
# QEMU: GPL-2.0-only as a whole, many files GPL-2.0-or-later (and other
# GPL-compatible licences, per file). Reims: LICENSE says LGPL-3.0-or-later,
# its crates' Cargo.toml say GPL-2.0-or-later. metal2vulkan: LGPL-3.0-or-later.
# Vendored crates (cargo tree, normal dependencies): mostly MIT OR
# Apache-2.0; some only MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC or
# Unicode-3.0 terms. Each crate's licence files are in the vendor tarball.
License:        GPL-2.0-only AND GPL-2.0-or-later AND LGPL-3.0-or-later AND MIT AND Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND ISC AND Unicode-3.0
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        reims-vgpu-%{reims_short}.tar.xz
Source1:        reims-vgpu-%{reims_short}-vendor.tar.xz
Source2:        %{name}-%{version}-extra.tar.xz
ExclusiveArch:  aarch64

BuildRequires:  gcc
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  bison
BuildRequires:  flex
BuildRequires:  bzip2
BuildRequires:  glib2-devel
BuildRequires:  pixman-devel
BuildRequires:  gtk3-devel
BuildRequires:  libepoxy-devel
BuildRequires:  wayland-devel
BuildRequires:  libxkbcommon-devel
BuildRequires:  vulkan-loader-devel
BuildRequires:  vulkan-headers
BuildRequires:  libslirp-devel
BuildRequires:  libfdt-devel
BuildRequires:  zlib-ng-compat-devel
BuildRequires:  gnutls-devel
BuildRequires:  nettle-devel
BuildRequires:  systemd-rpm-macros

# Reims loads the Vulkan loader at run time (ash), so there is no automatic
# dependency on it.
Requires:       vulkan-loader
Recommends:     mesa-honeykrisp-plus

%description
QEMU with the vmapple machine (Apple's Virtualization.framework platform),
KVM acceleration on Apple silicon, the avp,rtc clock macOS 26 expects, and
Reims, a paravirtual GPU that runs macOS guests' Metal work on the host's
Vulkan driver.

Built from github.com/aquarat/reims-vgpu (commit %{reims_short}) and its
QEMU fork github.com/aquarat/qemu-reims-vgpu (the commit Reims pins),
aarch64-softmmu only. Installed beside Fedora's qemu packages:
/usr/libexec/qemu-vmapple/qemu-system-aarch64, also run as qemu-vmapple.

macOS guests also need the kernel from this project (KVM patches) with the
no-syndrome MMIO emulation turned on (qemu-vmapple-kvm-nisv). This package
contains no macOS software or Apple firmware.

%package kvm-nisv
Summary:        Turn on the kernel's no-syndrome MMIO emulation for macOS guests
BuildArch:      noarch
Requires:       systemd

%description kvm-nisv
Sets the kernel parameter kvm.emulate_nisv_ldst to Y at boot and on install,
through a tmpfiles.d rule. The parameter exists only in the kernel from
apple-silicon-kernel-plus, where it is off by default; macOS guests need it
on (XNU accesses the interrupt controller with instructions KVM otherwise
cannot emulate). On other kernels the rule does nothing.
Removing this package turns the emulation off again.

%prep
%setup -q -n reims-vgpu-%{reims_short} -a 1 -a 2

%build
export CARGO_HOME=$PWD/.cargo-home CARGO_NET_OFFLINE=true CARGO_BUILD_JOBS=%{_smp_build_ncpus}
mkdir -p "$CARGO_HOME"
sed "s|@VENDOR@|$PWD/cargo-vendor/vendor|" cargo-vendor/config.toml > "$CARGO_HOME/config.toml"
cd vendor/qemu
./configure \
    --prefix=%{_prefix} --libdir=%{_libdir} --datadir=%{_datadir} \
    --sysconfdir=%{_sysconfdir} --localstatedir=%{_localstatedir} \
    --bindir=%{_libexecdir}/qemu-vmapple --libexecdir=%{_libexecdir}/qemu-vmapple \
    --with-suffix=qemu-vmapple \
    --extra-cflags="%{optflags}" --extra-ldflags="%{build_ldflags}" \
    --target-list=aarch64-softmmu --enable-kvm --enable-gnutls --enable-gtk \
    --enable-slirp --disable-docs --disable-tools --disable-rust --disable-gettext \
    --disable-werror --disable-download \
    -Dreims_vgpu_backend=vulkan
%{__ninja} -C build %{_smp_mflags}

%install
# Install into a staging root and keep only our own directories: no desktop
# file, icons or other paths that Fedora's qemu packages own.
cd vendor/qemu
DESTDIR=$PWD/stage %{__ninja} -C build install
mkdir -p %{buildroot}%{_libexecdir} %{buildroot}%{_datadir} %{buildroot}%{_bindir}
cp -a stage%{_libexecdir}/qemu-vmapple %{buildroot}%{_libexecdir}/
cp -a stage%{_datadir}/qemu-vmapple %{buildroot}%{_datadir}/
test -x %{buildroot}%{_libexecdir}/qemu-vmapple/qemu-system-aarch64
ln -s ../libexec/qemu-vmapple/qemu-system-aarch64 %{buildroot}%{_bindir}/qemu-vmapple
cd ../..
install -D -m 0644 %{name}-%{version}-extra/kvm-nisv.tmpfiles \
    %{buildroot}%{_tmpfilesdir}/qemu-vmapple-kvm-nisv.conf

%post kvm-nisv
%tmpfiles_create qemu-vmapple-kvm-nisv.conf

%postun kvm-nisv
if [ "$1" -eq 0 ] && [ -w /sys/module/kvm/parameters/emulate_nisv_ldst ]; then
    echo N > /sys/module/kvm/parameters/emulate_nisv_ldst || :
fi

%files
%license vendor/qemu/COPYING vendor/qemu/LICENSE LICENSE
%license %{name}-%{version}-extra/LICENSING.md
%doc %{name}-%{version}-extra/README.md README.md
%{_bindir}/qemu-vmapple
%{_libexecdir}/qemu-vmapple/
%{_datadir}/qemu-vmapple/

%files kvm-nisv
%license %{name}-%{version}-extra/LICENSE
%{_tmpfilesdir}/qemu-vmapple-kvm-nisv.conf

%changelog
* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 11.1.50^20261010git294f148-1
- First release: reims-vgpu 294f148 with qemu-reims-vgpu 2cd151d
