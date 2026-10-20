# SPDX-License-Identifier: GPL-2.0-only
# apple-silicon-thunderbolt: userspace policy for Thunderbolt/USB4 PCIe on
# Apple M1 Pro/Max/Ultra with this project's kernel (pcie-apple-apciec).
# The rules are github.com/aquarat/apple-silicon-thunderbolt-linux udev/ at
# the commit below.
%global tb_commit ff6b5e1

Name:           apple-silicon-thunderbolt
Version:        1.1
Release:        1%{?dist}
Summary:        Policy for Thunderbolt NVMe and networking on Apple silicon
License:        GPL-2.0-only
URL:            https://github.com/aquarat/apple-silicon-thunderbolt-linux
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
Requires:       udev
# 61-thunderbolt-net-threaded.rules turns GRO off with it
Requires:       ethtool

%description
A udev rule for NVMe drives behind the Thunderbolt/USB4 PCIe controllers
(pcie-apple-apciec) of Apple M1 Pro, M1 Max and M1 Ultra Macs: it turns off
autonomous power state transitions (APST) for those drives only, because a
drive entering a low-power state drops the USB4 link. The internal drive
keeps its APST settings.

A second rule runs the receive path of Thunderbolt networking
(thunderbolt-net) in a NAPI kernel thread and turns GRO off on those
interfaces. Apple's interrupt controller sends most ring interrupts to the
efficiency cores, and GRO reorders segments on this path.

Does not authorize Thunderbolt devices; use boltd (bolt) or your own policy
for that.

%prep
%autosetup

%build

%install
install -Dpm0644 60-apciec-nvme-apst.rules %{buildroot}%{_udevrulesdir}/60-apciec-nvme-apst.rules
install -Dpm0644 61-thunderbolt-net-threaded.rules %{buildroot}%{_udevrulesdir}/61-thunderbolt-net-threaded.rules

%files
%license LICENSE LICENSING.md
%{_udevrulesdir}/60-apciec-nvme-apst.rules
%{_udevrulesdir}/61-thunderbolt-net-threaded.rules

%changelog
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 1.1-1
- thunderbolt-net rule (threaded NAPI, GRO off) from
  apple-silicon-thunderbolt-linux ff6b5e1.

* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 1.0-1
- First package: the NVMe APST rule from apple-silicon-thunderbolt-linux dfbc506.
