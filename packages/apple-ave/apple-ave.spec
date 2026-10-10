# SPDX-License-Identifier: GPL-2.0-only
# apple-ave: the Apple AVE H.264/HEVC encoder driver. EXPERIMENTAL.
# src/ is github.com/aquarat/apple-m-series-ave-driver at the commit below
# (driver/, and test/ as overlay/ without the diagnostic modules).
# See README.md. No Apple firmware is in this package.
%global ave_commit b0af15e

Name:           apple-ave
Version:        0.99.3
Release:        1%{?dist}
Summary:        EXPERIMENTAL Apple AVE H.264/HEVC video encoder driver
License:        GPL-2.0-only
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
Requires:       dkms-apple-ave = %{version}-%{release}
Requires:       kmod
%{?systemd_requires}

%description
EXPERIMENTAL. Boot integration for the Apple Video Encoder (AVE) driver:
apple-ave.service and ave-load load the encoder on supported SoCs (t6000,
t8103, t8112; t6001 and t6002 only after per-machine preparation), and
install-firmware installs the firmware files the user extracted from their
own Mac or from Apple's IPSW. The service is disabled until you enable it.

The driver is reverse engineered and has been tested on few machines. It
needs the macOS 13.5 system firmware set up by the Asahi installer. No Apple
firmware is included. Read /usr/share/doc/apple-ave/README.md first.

%package -n dkms-apple-ave
Summary:        EXPERIMENTAL Apple AVE H.264/HEVC video encoder driver (DKMS)
Requires:       dkms
Requires:       gcc
Requires:       make
Requires:       dtc
Requires:       python3
Recommends:     kernel-16k-devel
Recommends:     apple-ave = %{version}-%{release}
Provides:       apple-ave-kmod = %{version}-%{release}

%description -n dkms-apple-ave
EXPERIMENTAL. Source, built by DKMS, for two kernel modules:
- apple-ave: a V4L2 stateful encoder for Apple's video encoder block (AVE):
  NV12/P010 in, H.264 (Baseline/Main/High) or HEVC (Main/Main 10) out,
  usable from ffmpeg (h264_v4l2m2m, hevc_v4l2m2m) and GStreamer;
- ave-overlay: adds the encoder to the device tree at run time, because
  Fedora's device trees have no AVE node.
The register layouts and constants come from reverse engineering of Apple's
firmware and macOS driver, for interoperability. Upstream:
https://github.com/aquarat/apple-m-series-ave-driver (commit %{ave_commit}).
ave-overlay is only loaded by apple-ave.service (a modprobe.d rule refuses
other loads). No Apple firmware is included.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing: DKMS builds the modules on the target system, per kernel.

%install
d=%{buildroot}%{_usrsrc}/apple-ave-%{version}
mkdir -p $d
cp -a src/. $d/
sed 's/@VERSION@/%{version}/' dkms.conf > $d/dkms.conf
install -D -m 0644 files/modprobe-apple-ave.conf %{buildroot}%{_prefix}/lib/modprobe.d/apple-ave.conf
install -D -m 0644 files/depmod-apple-ave.conf   %{buildroot}%{_prefix}/lib/depmod.d/apple-ave.conf
install -D -m 0755 files/ave-load                %{buildroot}%{_libexecdir}/apple-ave/ave-load
install -D -m 0644 files/apple-ave.service       %{buildroot}%{_unitdir}/apple-ave.service
install -D -m 0755 firmware/install-firmware     %{buildroot}%{_libexecdir}/apple-ave/install-firmware
install -D -m 0644 firmware/known-hashes.txt     %{buildroot}%{_datadir}/apple-ave/firmware/known-hashes.txt
mkdir -p %{buildroot}%{_sysconfdir}/apple-ave

%post
%systemd_post apple-ave.service

%preun
%systemd_preun apple-ave.service

%postun
%systemd_postun apple-ave.service

%post -n dkms-apple-ave
dkms add -m apple-ave -v %{version} --rpm_safe_upgrade >/dev/null 2>&1 || :
for k in /lib/modules/*; do
    k=${k##*/}
    [ -d "%{_usrsrc}/kernels/$k" ] || continue
    # Output stays visible: a failed build must show in dnf's output.
    dkms install -m apple-ave -v %{version} -k "$k" || :
done

%preun -n dkms-apple-ave
dkms remove -m apple-ave -v %{version} --all --rpm_safe_upgrade >/dev/null 2>&1 || :

%files
%license LICENSE LICENSING.md
%doc README.md
%dir %{_libexecdir}/apple-ave
%{_libexecdir}/apple-ave/install-firmware
%{_unitdir}/apple-ave.service
%{_datadir}/apple-ave/
%dir %{_sysconfdir}/apple-ave

%files -n dkms-apple-ave
%license LICENSE LICENSING.md
%doc README.md
%{_usrsrc}/apple-ave-%{version}/
%{_prefix}/lib/modprobe.d/apple-ave.conf
%{_prefix}/lib/depmod.d/apple-ave.conf
# The modprobe.d hook calls ave-load, so it lives with the modules.
%dir %{_libexecdir}/apple-ave
%{_libexecdir}/apple-ave/ave-load

%changelog
* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 0.99.3-1
- First release: AVE driver commit b0af15e; t6000, t8103 and t8112, with
  t6001 and t6002 behind per-machine markers; experimental
