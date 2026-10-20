# SPDX-License-Identifier: GPL-2.0-only
# apple-ave: the Apple AVE H.264/HEVC encoder driver. EXPERIMENTAL.
# src/ is github.com/aquarat/apple-m-series-ave-driver at the commit below
# (driver/, and test/ as overlay/ without the diagnostic modules);
# firmware/ave_fwgen.py is that repository's tools/ave_fwgen.py.
# See README.md. No Apple firmware, and no data taken from Apple's files, is
# in this package: apple-ave-fetch-firmware makes them on the user's machine.
%global ave_commit 9ab14e4

Name:           apple-ave
Version:        0.99.5
Release:        1%{?dist}
Summary:        EXPERIMENTAL Apple AVE H.264/HEVC video encoder driver
License:        GPL-2.0-only
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
BuildRequires:  python3
Requires:       dkms-apple-ave = %{version}-%{release}
Requires:       kmod
Requires:       python3
# The kernelcache in Apple's image is LZFSE-compressed
Requires:       lzfse
%{?systemd_requires}

%description
EXPERIMENTAL. Boot integration and firmware tooling for the Apple Video
Encoder (AVE) driver:
- apple-ave-fetch-firmware makes the files the driver needs on this machine,
  from the user's own copy of Apple's macOS 13.5 files: the encoder firmware
  and the AVE_DPE register tables, read with HTTP range requests from Apple's
  restore image on Apple's CDN (about 0.5 MB, plus a 26 MB kernelcache unless
  the Asahi installer left one on the EFI partition), or from a local copy.
  Every file is checked against known sha256 values.
- apple-ave.service and ave-load load the encoder on supported SoCs (t6000,
  t8103, t8112; t6001 and t6002 after enabling them) and keep the firmware
  data the driver needs for reloads.
The service is disabled until you enable it. Nothing is downloaded unless you
run apple-ave-fetch-firmware or enable apple-ave-fetch-firmware.service.
Read /usr/share/doc/apple-ave/README.md first.

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
The register layouts and command formats come from reverse engineering of
Apple's firmware and macOS driver, for interoperability. The build needs no
Apple data: the driver loads the firmware and its tables at run time.
Upstream: https://github.com/aquarat/apple-m-series-ave-driver (commit
%{ave_commit}). ave-overlay is only loaded by apple-ave.service (a modprobe.d
rule refuses other loads).

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
install -D -m 0644 files/apple-ave-fetch-firmware.service %{buildroot}%{_unitdir}/apple-ave-fetch-firmware.service
install -D -m 0755 firmware/apple-ave-fetch-firmware %{buildroot}%{_bindir}/apple-ave-fetch-firmware
install -D -m 0755 firmware/ave_fwgen.py         %{buildroot}%{_datadir}/apple-ave/ave_fwgen.py
sed -i '1s|^#!/usr/bin/env python3$|#!/usr/bin/python3|' %{buildroot}%{_datadir}/apple-ave/ave_fwgen.py
install -D -m 0755 firmware/install-firmware     %{buildroot}%{_libexecdir}/apple-ave/install-firmware
install -D -m 0644 firmware/known-hashes.txt     %{buildroot}%{_datadir}/apple-ave/firmware/known-hashes.txt
mkdir -p %{buildroot}%{_sysconfdir}/apple-ave

%check
# Synthetic inputs only: no network, no Apple files.
python3 -m unittest discover -s tests -v

%post
%systemd_post apple-ave.service apple-ave-fetch-firmware.service

%preun
%systemd_preun apple-ave.service apple-ave-fetch-firmware.service

%postun
%systemd_postun apple-ave.service apple-ave-fetch-firmware.service

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
%doc README.md apple-ave-firmware.md
%{_bindir}/apple-ave-fetch-firmware
%dir %{_libexecdir}/apple-ave
%{_libexecdir}/apple-ave/install-firmware
%{_unitdir}/apple-ave.service
%{_unitdir}/apple-ave-fetch-firmware.service
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
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 0.99.5-1
- AVE driver commit 9ab14e4. The upstream history was rewritten and 057c5df
  no longer exists; its equivalent there is 508c279 (the same driver/ and
  test/ trees as 0.99.4). 9ab14e4 changes only comments in ave_drv.c and
  ave_session.c (commit ids of the rewritten history); no code change.

* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 0.99.4-1
- AVE driver commit 057c5df: no data from Apple's files in the source; the
  AVE_DPE tables are generated on the user's machine and loaded at run time,
  and the driver keeps the boot's pristine firmware DATA itself
- Firmware placement read from the live ADT; the driver programs t6001's DAPF
- apple-ave-fetch-firmware: makes and verifies the firmware files from
  Apple's macOS 13.5 image (range requests), a local IPSW or a directory
- Still experimental: the driver changes have not run on hardware yet

* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 0.99.3-1
- First release: AVE driver commit b0af15e; t6000, t8103 and t8112, with
  t6001 and t6002 behind per-machine markers; experimental
