# SPDX-License-Identifier: GPL-2.0-only
# apple-silicon-thunderbolt: userspace policy for Thunderbolt/USB4 PCIe on
# Apple M1 Pro/Max/Ultra with this project's kernel (pcie-apple-apciec).
# 60-apciec-nvme-apst.rules is github.com/aquarat/apple-silicon-thunderbolt-linux
# udev/ at the commit below.
%global tb_commit 0238ce0

Name:           apple-silicon-thunderbolt
Version:        1.0
Release:        1%{?dist}
Summary:        Policy for NVMe drives in Thunderbolt enclosures on Apple silicon
License:        GPL-2.0-only
URL:            https://github.com/aquarat/apple-silicon-thunderbolt-linux
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
Requires:       udev

%description
A udev rule for NVMe drives behind the Thunderbolt/USB4 PCIe controllers
(pcie-apple-apciec) of Apple M1 Pro, M1 Max and M1 Ultra Macs: it turns off
autonomous power state transitions (APST) for those drives only, because a
drive entering a low-power state drops the USB4 link. The internal drive
keeps its APST settings. Does not authorize Thunderbolt devices; use boltd
(bolt) or your own policy for that.

%prep
%autosetup

%build

%install
install -Dpm0644 60-apciec-nvme-apst.rules %{buildroot}%{_udevrulesdir}/60-apciec-nvme-apst.rules

%files
%license LICENSE LICENSING.md
%{_udevrulesdir}/60-apciec-nvme-apst.rules

%changelog
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 1.0-1
- First package: the NVMe APST rule from apple-silicon-thunderbolt-linux 0238ce0.
