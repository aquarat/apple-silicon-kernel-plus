# SPDX-License-Identifier: GPL-2.0-only
# Out-of-tree build for the Apple AVD V4L2 decoder against the running kernel.
KVER ?= $(shell uname -r)
KDIR ?= /lib/modules/$(KVER)/build
PWD  := $(shell pwd)
# make DEBUG=1  : log every instruction word pushed to the decoder (dev_info,
#                 very verbose: hundreds of dmesg lines per frame)
# make AVD_CFLAGS='-DFOO' : arbitrary extra defines
ifeq ($(DEBUG),1)
AVD_CFLAGS += -DDEBUG_INST -DDEBUG_INST_ADDR
endif
export AVD_CFLAGS

all: modules

modules:
	$(MAKE) -C $(KDIR) M=$(PWD) AVD_CFLAGS="$(AVD_CFLAGS)" modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

.PHONY: all modules clean
