# SPDX-License-Identifier: GPL-2.0-only
# apple-pmp-enable: opt-in tool that turns on Apple's power management
# coprocessor (PMP) on validated M1 Pro/Max Macs through a self-reverting
# trial boot (docs/pmp-enable.md). Installing it changes nothing.

Name:           apple-pmp-enable
Version:        1.0
Release:        1%{?dist}
Summary:        Opt-in: turn on the power management coprocessor of M1 Pro/Max Macs
License:        GPL-2.0-only
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch
BuildRequires:  systemd-rpm-macros
# %%check: the device tree tests
BuildRequires:  python3
BuildRequires:  dtc
BuildRequires:  gzip
Requires:       python3
# fdtget, fdtput
Requires:       dtc
# /etc/sysconfig/update-m1n1, and the m1n1 and U-Boot binaries it names
Requires:       update-m1n1
Requires:       grubby
# grub2-editenv
Requires:       grub2-tools-minimal
# findmnt
Requires:       util-linux-core
Requires:       gzip
Requires:       systemd
# The device trees it accepts are this project's kernel's.
Recommends:     kernel-16k

%description
Turns on the power management coprocessor (PMP) of an M1 Pro or M1 Max
Mac, for the boards and kernels whose device trees have been validated
(14-inch MacBook Pro with M1 Pro or M1 Max, with this project's 7.3.4
kernel). With the PMP running the machine saves about 1.2-1.4 W at idle, and
this project's kernel patches keep the CPU and GPU memory bandwidth up.

m1n1 starts the PMP only if its stage 2 (boot.bin on the EFI system
partition) carries device trees with the PMP enabled, which Fedora's are
not. apple-pmp-enable patches this machine's device tree, refusing any
tree it has not been validated on, and tries the result as a one-shot
trial boot: the trial boot puts the previous boot.bin back as soon as it
starts, a dead-man timer restarts it unless you run
`apple-pmp-enable commit`, and only a commit after its boot checks pass
keeps the PMP on. If the trial does not even start, recovery is from macOS
recovery (copy m1n1/boot.bin.pre-pmp back), as the README describes.

Installing the package does nothing: run `apple-pmp-enable check`, then
`apple-pmp-enable enable`.

%prep
%autosetup

%build

%install
install -Dpm0755 apple-pmp-enable %{buildroot}%{_sbindir}/apple-pmp-enable
install -Dpm0755 pmp-dtb %{buildroot}%{_libexecdir}/%{name}/pmp-dtb
install -Dpm0644 validated.txt %{buildroot}%{_datadir}/%{name}/validated.txt
for f in boot-safety/*.conf; do
    install -Dpm0644 "$f" %{buildroot}%{_datadir}/%{name}/"$f"
done
install -Dpm0644 systemd/apple-pmp-trial.service %{buildroot}%{_unitdir}/apple-pmp-trial.service
install -Dpm0644 systemd/apple-pmp-deadman.service %{buildroot}%{_unitdir}/apple-pmp-deadman.service
install -Dpm0644 systemd/apple-pmp-deadman.timer %{buildroot}%{_unitdir}/apple-pmp-deadman.timer
install -dm0700 %{buildroot}%{_sharedstatedir}/%{name}

%check
python3 -m unittest discover -s tests -v

%preun
# Never touches the EFI partition or the boot entries. A trial in progress
# should be aborted first; say so.
if [ "$1" -eq 0 ] && grep -qE '^phase=(arming|armed|trial)$' %{_sharedstatedir}/%{name}/state 2>/dev/null; then
    echo "apple-pmp-enable: a PMP trial is in progress; run 'apple-pmp-enable abort' (the package can be reinstalled for it)" >&2
fi
%systemd_preun apple-pmp-trial.service apple-pmp-deadman.timer apple-pmp-deadman.service

%files
%license LICENSE LICENSING.md
%doc README.md
%{_sbindir}/apple-pmp-enable
%{_libexecdir}/%{name}/
%{_datadir}/%{name}/
%{_unitdir}/apple-pmp-trial.service
%{_unitdir}/apple-pmp-deadman.service
%{_unitdir}/apple-pmp-deadman.timer
%dir %attr(0700,root,root) %{_sharedstatedir}/%{name}

%changelog
* Thu Nov 19 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 1.0-1
- First package: the PMP device tree fixup for t6000-j314s and t6001-j314c
  on kernel 7.3.4-900.asahiwip.plus5, with a self-reverting trial boot.
