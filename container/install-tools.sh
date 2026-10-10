#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Install the tools that build this project's SRPMs and lint its specs and
# scripts, on Fedora (as root). Used by container/Containerfile and by the
# GitHub workflows. The compiler and kernel tools are only for the kernel
# prep check (rpmbuild -bp: do the patches apply?).
set -e
dnf -y install --setopt=install_weak_deps=False \
    rpm-build rpmdevtools rpmlint cpio xz zstd bzip2 tar gzip \
    git-core curl ca-certificates python3 make patch diffutils findutils \
    meson ninja-build cargo rust ShellCheck \
    python3-rpm-macros systemd-rpm-macros gcc flex bison bc perl-interpreter \
    openssl openssl-devel elfutils-libelf-devel dwarves hostname kmod which \
    glibc-langpack-en "$@"
dnf clean all
