# SPDX-License-Identifier: GPL-2.0-only
# Out-of-tree build of drivers/media/platform/apple/avd (AsahiLinux/linux).
# Mirrors the in-tree Makefile; the in-tree symbol is CONFIG_VIDEO_APPLE_AVD=m,
# forced to obj-m here. The driver has no CONFIG_* ifdefs of its own; the
# optional DEBUG_INST / DEBUG_INST_ADDR / AVD_DEBUG defines can be turned on
# with:  make EXTRA_CFLAGS='-DDEBUG_INST -DAVD_DEBUG'
apple-avd-y := avd-drv.o avd-v4l2.o avd-hw.o avd-h264.o avd-vp9.o avd-hevc.o \
	avd-av1.o avd-av1-entropymode.o
obj-m += apple-avd.o
ccflags-y += -Wno-error
# extra flags from the wrapper Makefile (make DEBUG=1 -> -DDEBUG_INST -DDEBUG_INST_ADDR)
ccflags-y += $(AVD_CFLAGS)
