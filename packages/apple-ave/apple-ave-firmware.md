# Apple AVE firmware files

The AVE encoder runs Apple firmware, and the driver needs a few register
tables that only Apple's macOS driver holds. None of that is in this
repository or in any package built from it, and it must not be added: the
driver source carries no data taken from Apple's files (the AVE
repository's docs/100 has the inventory). `apple-ave-fetch-firmware` makes
the files on your Mac, from your own copy of Apple's files, and checks
every one of them against `known-hashes.txt` (sha256).

```sh
sudo apple-ave-fetch-firmware            # shows what it will do and asks first
sudo apple-ave-fetch-firmware --dry-run  # the plan only: no network, nothing written
apple-ave-fetch-firmware --check         # what is installed
```

## What it makes

| file | from | how |
|---|---|---|
| `apple/ave_<variant>.bin` | `Firmware/ave/AppleAVE2FW_<variant>.im4p` | the IM4P's payload, unwrapped by the tool (it is neither compressed nor encrypted) |
| `apple/ave-13.5-dpe-<set>.bin` | `kernelcache.release.<x>` | the kernelcache is LZFSE-decompressed (the `lzfse` package); `ave_fwgen.py` reads the AVE_DPE register tables `gs_sAVE_DPE_CfgSet_<set>` out of AppleAVE2.kext |
| `apple/ave-13.5-h13g-data-pristine.bin` (M1 only) | the firmware image | the image's DATA with this SoC's register addresses and an empty tunables table |

| SoC | variant | DPE set | kernelcache |
|---|---|---|---|
| t6000 M1 Pro | H13S | Castor_6000 | mac13j |
| t6001 M1 Max | H13C | Castor_6000 | mac13j |
| t6002 M1 Ultra | H13D | Castor_6000 | mac13j |
| t8103 M1 | H13G | Acis_8103 | mac13g |
| t8112 M2 | H14G | Atlas_8112 | mac14g |

Every 13.5 kernelcache carries the same AppleAVE2.kext; the tool takes any
of the three it knows.

## Where Apple's files come from

1. **The kernelcache the Asahi installer left on the EFI system partition**
   (`/boot/efi/asahi/kernelcache.release.*`): this Mac's own 13.5
   kernelcache. Used when its sha256 is a known one, so most machines
   download no kernelcache at all. `--no-local-kernelcache` skips it.
2. **Apple's restore image, read in place** (the default): macOS **13.5
   (22G74)**,
   `https://updates.cdn-apple.com/2023SummerFCS/fullrestores/032-69606/D3E05CDF-E105-434C-A4A1-4E3DC7668DD0/UniversalMac_13.5_22G74_Restore.ipsw`,
   the URL the Asahi installer uses for 13.5. An IPSW is a ZIP; the tool
   reads its directory (about 0.2 MB) and the members it needs with HTTP
   range requests: the AVE firmware (about 0.5 MB over the wire) and,
   unless (1) found one, the kernelcache (about 26 MB). Not the 12.9 GB
   image.
3. **A local IPSW**: `--ipsw UniversalMac_13.5_22G74_Restore.ipsw`.
4. **A directory**: `--from-dir DIR` searches DIR for
   `AppleAVE2FW_<variant>.im4p` (or a personalized `AVE.img4`) and a 13.5
   kernelcache (`kernelcache.release.*`, or a personalized `kernelcache`),
   e.g. a mounted macOS 13.5 Preboot volume. The Asahi stub's Preboot holds
   them under `<volume group>/Restore/`. Tested with synthetic copies only;
   mounting APFS from Linux (`apfs-fuse`, read-only) is up to you, and a
   FileVault-encrypted volume cannot be read this way.

The Asahi installer's `all_firmware.tar.gz` does not contain the AVE
firmware.

## Checks

- the IM4P and kernelcache bytes against their known sha256 and size,
  before anything is unpacked (a personalized IMG4 is checked by the IM4P
  inside it);
- the firmware image, the generated tables and the M1's blob against their
  known sha256;
- nothing is written unless every file of the set passed; files are
  written atomically, mode 0644, and relabelled for SELinux.

## The pristine DATA blob

To restart a core within one boot (a reload of the module, or a recovery
after a firmware hang) the driver writes the firmware's data segment back
as the boot loader left it. Part of it is written by the boot loader
itself, so it is in no file you have. The driver copies it at the first
start of each boot, checks it against the image, uses it for that load,
and offers it in debugfs. `ave-load` runs `apple-ave-fetch-firmware
--capture` after each load, which checks the copy again and installs it
under the name the driver asks for (for example
`apple/ave-13.5-h13s-data-pristine.bin`) for reloads in later boots.
The copy differs from boot to boot only in a random stack cookie, so it has
no fixed hash; it is checked byte for byte against the image instead.

- t6000, t8112, t6002: the first load of a boot works without it.
- t6001: the second encoder builds its DATA from it, so it comes up from
  the boot after the first capture (`ave-load` loads only the first until
  then).
- t8103: iBoot's copy lies in Linux's memory on these machines, so the
  driver builds its own from the M1 blob above.

## Doing it at boot (opt-in)

```sh
sudo systemctl enable apple-ave-fetch-firmware.service
```

runs `apple-ave-fetch-firmware --yes` before `apple-ave.service` on every
boot. When the files are in place it does nothing and uses no network;
when they are not, it downloads as in (2) above. Enabling it is your
consent to that download; it is off by default.

## Without the tool

The files can be made by hand with the AVE repository's
`tools/ave_fwgen.py` and installed with
`/usr/libexec/apple-ave/install-firmware DIR`, which refuses any file whose
sha256 is not in `known-hashes.txt`.

## Why only 13.5

The firmware runs from where the boot loader placed it, and the boot
loader loads the system firmware of the macOS stub Asahi installed: 13.5
(`/proc/device-tree/chosen/asahi,os-fw-version`). The driver's layout
checks and these tables are for that build; `ave-load` and the tool refuse
other versions (`--force` makes the files anyway).
