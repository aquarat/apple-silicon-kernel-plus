# SPDX-License-Identifier: GPL-2.0-only
# reims-vgpu-backend: the Reims paravirtual GPU for macOS guests, as its own
# program. qemu-vmapple's apv-gpu-proxy device connects to it over a unix
# socket and hands it the guest RAM (a shared memfd) and eventfds; it runs
# the guest's Metal work on the host's Vulkan driver through metal2vulkan.
# Built as the macOS VM stack's `MODE=oop scripts/build-qemu.sh` builds it:
# github.com/aquarat/reims-vgpu at reims_commit,
# `cargo build --release -p reims-vgpu-backend`.
#
# Installed beside qemu-vmapple: /usr/libexec/qemu-vmapple/reims-vgpu-backend
# (also /usr/bin/reims-vgpu-backend). It contains no QEMU code.
#
# The SRPM carries every source (scripts/make-srpm.sh): Reims, and the Rust
# crates from `cargo vendor` (the metal2vulkan git dependency included). The
# build needs no network.
%global reims_commit 2677a20ca8a34ccbe33b7a579ce493723fbc824e
%global reims_date   20261019
%global reims_short  %(c=%{reims_commit}; echo ${c:0:12})
%global crate_version 0.1.0
# apv-gpu-proxy protocol version (APV_PROXY_VERSION in the protocol header;
# make-srpm.sh checks it). qemu-vmapple must speak the same version.
%global apv_protocol 1

Name:           reims-vgpu-backend
Version:        %{crate_version}^%{reims_date}git%(c=%{reims_commit}; echo ${c:0:7})
Release:        1%{?dist}
Summary:        Reims paravirtual GPU for macOS guests, as a separate process
# Reims: LICENSE and README say LGPL-3.0-or-later, as does the backend
# crate's Cargo.toml; the other Reims crates' Cargo.toml say
# GPL-2.0-or-later. reims-vgpu-proxy-wire: MIT. metal2vulkan:
# LGPL-3.0-or-later. Linked crates (cargo tree, normal dependencies, no
# proc-macros; LICENSE.dependencies in the package lists each): mostly
# MIT OR Apache-2.0; winit, spirv, ab_glyph and others Apache-2.0 only;
# tiny-skia BSD-3-Clause, arrayref BSD-2-Clause, libloading ISC. Together:
# distributable under GPL-3.0-or-later terms (LICENSING.md). make-srpm.sh
# refuses a crate whose licence is missing here.
License:        LGPL-3.0-or-later AND GPL-2.0-or-later AND Apache-2.0 AND BSD-2-Clause AND BSD-3-Clause AND ISC AND MIT AND (MIT OR Apache-2.0) AND (Apache-2.0 OR MIT OR Zlib) AND (Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT) AND (BSD-2-Clause OR Apache-2.0 OR MIT)
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        reims-vgpu-%{reims_short}.tar.xz
Source1:        reims-vgpu-%{reims_short}-vendor.tar.xz
Source2:        %{name}-%{version}-extra.tar.xz
ExclusiveArch:  aarch64

BuildRequires:  cargo
BuildRequires:  rust
BuildRequires:  cargo-rpm-macros
BuildRequires:  gcc
BuildRequires:  pkgconf-pkg-config
BuildRequires:  vulkan-loader-devel
BuildRequires:  wayland-devel
BuildRequires:  libxkbcommon-devel
BuildRequires:  util-linux-core

# The Vulkan loader is opened at run time (ash), so there is no automatic
# dependency on it.
Requires:       vulkan-loader
Recommends:     mesa-honeykrisp-plus
Provides:       apv-gpu-proxy-backend = %{apv_protocol}
# The crates linked into the binary, from Cargo.lock (make-srpm.sh fills
# these in from `cargo tree`).
# @BUNDLED_CRATES@

%description
Reims, a paravirtual GPU for macOS guests, as its own program: it serves
qemu-vmapple's apv-gpu-proxy device over a unix socket, shared memory and
eventfds, and runs the guest's Metal work on the host's Vulkan driver
(metal2vulkan translates the shaders). A crash in the host GPU driver ends
only this process; QEMU stops the guest with the reason.

Built from github.com/aquarat/reims-vgpu (commit %{reims_short}), which is
steelbrain-bot/reims-vgpu with Asahi Linux host changes. Use it with
mesa-honeykrisp-plus (VK_DRIVER_FILES): stock Honeykrisp aborts on shaders
macOS 26 guests use.

%prep
%setup -q -n reims-vgpu-%{reims_short} -a 1 -a 2
cp -p crates/reims-vgpu-proxy-wire/LICENSE LICENSE.reims-vgpu-proxy-wire
# This package's README beside Reims' own.
cp -p %{name}-%{version}-extra/README.md README.package.md

%build
export CARGO_HOME=$PWD/.cargo-home CARGO_NET_OFFLINE=true CARGO_INCREMENTAL=0
export CARGO_BUILD_JOBS=%{_smp_build_ncpus}
mkdir -p "$CARGO_HOME"
sed "s|@VENDOR@|$PWD/cargo-vendor/vendor|" cargo-vendor/config.toml > "$CARGO_HOME/config.toml"
export RUSTFLAGS="%{build_rustflags}"
cargo build --frozen --release -p reims-vgpu-backend
# The licence of every crate linked into the binary, and their licence files.
cargo tree --frozen -p reims-vgpu-backend -e no-build,no-dev,no-proc-macro \
    --prefix none --format '{p}: {l}' | sed 's/ (\*)$//' | sort -u > LICENSE.dependencies
mkdir -p crate-licenses
cargo tree --frozen -p reims-vgpu-backend -e no-build,no-dev,no-proc-macro \
    --prefix none --format '{p}' | sed 's/ (\*)$//' | awk '{ sub(/^v/, "", $2); print $1 "-" $2 }' |
    sort -u | while read -r c; do
        d=cargo-vendor/vendor/$c
        test -d "$d" || continue
        for f in "$d"/LICENSE* "$d"/LICENCE* "$d"/COPYING* "$d"/NOTICE* "$d"/UNLICENSE*; do
            test -f "$f" || continue
            mkdir -p "crate-licenses/$c"
            cp -p "$f" "crate-licenses/$c/"
        done
    done

%install
install -Dpm0755 target/release/reims-vgpu-backend \
    %{buildroot}%{_libexecdir}/qemu-vmapple/reims-vgpu-backend
mkdir -p %{buildroot}%{_bindir}
ln -s ../libexec/qemu-vmapple/reims-vgpu-backend %{buildroot}%{_bindir}/reims-vgpu-backend
# Many crates ship the same licence text: one copy, hard-linked.
mkdir -p %{buildroot}%{_licensedir}/%{name}
cp -a crate-licenses %{buildroot}%{_licensedir}/%{name}/
hardlink -q -c %{buildroot}%{_licensedir}/%{name}/crate-licenses

%check
b=%{buildroot}%{_libexecdir}/qemu-vmapple/reims-vgpu-backend
# Its own program: no QEMU code, and it speaks the protocol version above.
grep -q '^#define APV_PROXY_VERSION %{apv_protocol}u$' \
    crates/reims-vgpu-proxy-wire/include/apv-gpu-proxy-protocol.h
if nm -D $b | grep -E ' (qemu_|qdev_|object_new)'; then exit 1; fi
# A usage error, not a crash, without arguments.
if $b > usage.txt 2>&1; then exit 1; fi
grep -q -- '--socket' usage.txt

%files
%license LICENSE LICENSE.reims-vgpu-proxy-wire LICENSE.dependencies
%license %{_licensedir}/%{name}/crate-licenses
%license %{name}-%{version}-extra/LICENSING.md
%doc README.package.md README.md README.asahi.md
%{_bindir}/reims-vgpu-backend
%dir %{_libexecdir}/qemu-vmapple
%{_libexecdir}/qemu-vmapple/reims-vgpu-backend

%changelog
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 0.1.0^20261019git2677a20-1
- First release: reims-vgpu 2677a20 (40c5bc1 with a README change), the
  out-of-process device for qemu-vmapple's apv-gpu-proxy (protocol 1), with
  metal2vulkan 6406b8e. The display refresh-rate cap
  (REIMS_VGPU_MAX_REFRESH_HZ, default 60) and opt-in surface pacing
  (REIMS_VGPU_FRAME_PACING).
