# SPDX-License-Identifier: GPL-2.0-only
# apple-avd: the Asahi kernel tree's Apple AVD decoder driver with fixes,
# as DKMS source. src/ is scripts/rebase-avd.sh output: the in-tree driver of
# the kernel named below plus patches/. See README.md.
%global base_kernel 7.2.11-900.asahiwip.plus1.fc44

Name:           apple-avd
Version:        7.2.11.1
Release:        1%{?dist}
Summary:        Apple AVD video decoder driver with stream fixes (DKMS source)
# avd-hw.c, avd-inst.h, avd-regs.h: MIT. avd-av1-entropymode.c: BSD-2-Clause
# (Alliance for Open Media). Everything else: GPL-2.0-only.
License:        GPL-2.0-only AND MIT AND BSD-2-Clause
URL:            https://github.com/aquarat/apple-silicon-kernel-plus
Source0:        %{name}-%{version}.tar.xz
BuildArch:      noarch

%description
The Apple Video Decoder (AVD) V4L2 stateless driver from the
apple-silicon-kernel-plus kernel
%{base_kernel} (Asahi Linux kernel tree),
with four fixes for long-running streams.
This is the source package; install dkms-apple-avd.

%package -n dkms-apple-avd
Summary:        Apple AVD video decoder driver with stream fixes, built by DKMS
Requires:       dkms
Requires:       gcc
Requires:       make
Recommends:     kernel-16k-devel
Provides:       apple-avd-kmod = %{version}-%{release}

%description -n dkms-apple-avd
The Apple Video Decoder (AVD) V4L2 stateless driver (H.264, HEVC, VP9,
AV1) as it ships in the apple-silicon-kernel-plus kernel
%{base_kernel}, plus four fixes:
- an H.264 slice that fails early no longer leaves its request
  uncompleted (EBUSY afterwards) or a freed job table in use;
- slices that reference invalid DPB entries are rejected instead of
  faulting the decoder;
- the job segment table no longer needs a contiguous allocation;
- user space can ask for cacheable capture buffers, which makes reading
  decoded frames back with the CPU much faster.

DKMS builds it for each installed 7.2.x kernel that has its
-devel package. The module goes to extra/ and is preferred to the in-tree
one (/usr/lib/depmod.d/apple-avd.conf). Kernels of another series are
skipped and keep the in-tree driver until this package is rebased.
The decoder firmware (apple/avd-fw-*.bin) is not included.

%prep
%autosetup -n %{name}-%{version}

%build
# Nothing: DKMS builds the module on the target system, per kernel.

%install
d=%{buildroot}%{_usrsrc}/apple-avd-%{version}
mkdir -p $d
cp -a src/. $d/
rm -f $d/.gitignore
sed 's/@VERSION@/%{version}/' dkms.conf > $d/dkms.conf
install -D -m 0644 depmod-apple-avd.conf %{buildroot}%{_prefix}/lib/depmod.d/apple-avd.conf

%post -n dkms-apple-avd
dkms add -m apple-avd -v %{version} --rpm_safe_upgrade >/dev/null 2>&1 || :
for k in /lib/modules/*; do
    k=${k##*/}
    [ -d "%{_usrsrc}/kernels/$k" ] || continue
    # Output stays visible: a failed build must show in dnf's output.
    dkms install -m apple-avd -v %{version} -k "$k" || :
done

%preun -n dkms-apple-avd
dkms remove -m apple-avd -v %{version} --all --rpm_safe_upgrade >/dev/null 2>&1 || :

%files -n dkms-apple-avd
%license LICENSE LICENSING.md
%doc README.md patches
%{_usrsrc}/apple-avd-%{version}/
%{_prefix}/lib/depmod.d/apple-avd.conf

%changelog
* Tue Oct 20 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 7.2.11.1-1
- Rebased onto the kernel-7.2.11-900.asahiwip.plus1.fc44 driver (Asahi
  asahi-wip e09c62843a8e). 7.2 sizes the H.264 slice table dynamically and
  resets slice_num itself, so 0004 is now the error-path fix (complete the
  request, clear the freed job table); 0003 also covers the new grow path.
- DKMS builds it for 7.2 kernels only.

* Sat Oct 10 2026 aquarat <3090997+aquarat@users.noreply.github.com> - 7.1.13.1-1
- First release: the kernel-7.1.13-402.asahi.fc44 driver plus four fixes
