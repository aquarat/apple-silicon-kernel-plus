# SPDX-License-Identifier: GPL-2.0-only
# COPR "make_srpm" entry point. COPR runs, as root, in a Fedora mock chroot
# with network access:
#   make -f <clone>/.copr/Makefile srpm outdir=<dir> spec=<path from the package definition>
# The package is the directory of `spec`: packages/<package>/<anything>.
# For the kernel, whose spec comes from @asahi, use packages/kernel/kernel-plus.conf.
# PKG=<package> overrides. Locally: make -f .copr/Makefile srpm outdir=out PKG=apple-avd

TOP := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
outdir ?= $(TOP)/out
spec ?=
PKG ?= $(notdir $(patsubst %/,%,$(dir $(spec))))

DEPS := rpm-build rpmdevtools git-core curl ca-certificates python3 xz tar cpio \
        findutils diffutils meson ninja-build cargo rust

.PHONY: srpm deps
srpm: deps
	@test -n "$(PKG)" || { echo "set spec=packages/<package>/... or PKG=<package>"; exit 1; }
	$(TOP)/scripts/make-srpm.sh $(PKG) $(outdir)

# In COPR (root, dnf present) install what make-srpm.sh needs; elsewhere
# assume it is there (scripts/build-srpms.sh uses the tools container).
deps:
	@if [ "$$(id -u)" = 0 ] && command -v dnf >/dev/null; then \
	    dnf -y -q install --setopt=install_weak_deps=False $(DEPS); \
	fi
