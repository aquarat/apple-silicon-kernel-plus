# Apple AVE firmware

The AVE encoder runs Apple firmware. It is not in this repository, not in
any package built from it, and must not be added. Each user makes the files
for their own Mac from Apple's macOS 13.5 IPSW, with the tools of the
[AVE driver repository](https://github.com/aquarat/apple-m-series-ave-driver),
and installs them with `install-firmware`, which checks every file against
`known-hashes.txt`.

Two files per SoC:

| SoC | boards (IPSW BuildManifest) | firmware image | pristine DATA blob |
|---|---|---|---|
| t6000 M1 Pro | j314s, j316s | `apple/ave_h13s.bin` (H13S) | `apple/ave-13.5-h13s-data-pristine.bin` |
| t8103 M1 | j274, j293, j313, j456, j457 | `apple/ave_h13g.bin` (H13G) | `apple/ave-13.5-h13g-data-pristine.bin` |
| t8112 M2 | j413, j415, j473, j493 | `apple/ave_h14g.bin` (H14G) | `apple/ave-13.5-h14g-data-pristine.bin` |
| t6001 M1 Max | j314c, j316c, j375c | `apple/ave_h13c.bin` (H13C) | `apple/ave-13.5-data-pristine.bin` |
| t6002 M1 Ultra | j375d | `apple/ave_h13d.bin` (H13D) | `apple/ave-13.5-h13d-*data-pristine.bin` (four) |

The firmware image is the Mach-O inside
`Firmware/ave/AppleAVE2FW_<variant>.im4p` of the macOS **13.5 (22G74)** IPSW.
13.5 is the system firmware version the Asahi installer sets up
(`/proc/device-tree/chosen/asahi,os-fw-version`); `ave-load` refuses others.

The pristine DATA blob is the firmware's data segment as the boot loader
leaves it. The driver writes it back before it restarts the encoder (a
module reload or a recovery), as macOS does. It is built from the image plus
a few values the boot loader fills in.

## Steps

```sh
git clone https://github.com/aquarat/apple-m-series-ave-driver
cd apple-m-series-ave-driver
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

# 1. The firmware image. fetch_firmware.py reads only the needed members of
#    the IPSW with HTTP range requests (no full download). Example: M1 Pro.
IPSW=https://updates.cdn-apple.com/2023SummerFCS/fullrestores/032-69606/D3E05CDF-E105-434C-A4A1-4E3DC7668DD0/UniversalMac_13.5_22G74_Restore.ipsw
./.venv/bin/python tools/fetch_firmware.py --board j314s --variant H13S --outdir data/blobs --url "$IPSW"
./.venv/bin/pyimg4 im4p extract -i data/blobs/Firmware/ave/AppleAVE2FW_H13S.im4p -o data/blobs/ave_h13s.bin

# 2. The pristine DATA blob (t6000, t8112; for t8103 add --tunables none)
./.venv/bin/python tools/data_blob_from_image.py build --soc t6000 \
    --image data/blobs/ave_h13s.bin -o data/blobs/ave-13.5-h13s-data-pristine.bin

# 3. Install (checks the sha256 of each file)
sudo /usr/libexec/apple-ave/install-firmware data/blobs
/usr/libexec/apple-ave/install-firmware --check
```

For the other SoCs use the board and variant from the table. Use the
board of your own machine (`tr '\0' '\n' < /proc/device-tree/compatible`).

- **t6001 (M1 Max):** the blob comes from `tools/make_ave_data_blob.py`;
  see that repository's docs/43 and docs/51. The driver's t6001 row expects
  an m1n1 that sets up the first encoder's DAPF (its docs/50); with stock
  m1n1 the row needs `dapf_by_driver = true` in `driver/ave_soc.c` (its
  docs/84). That is why t6001 needs the marker file.
- **t6002 (M1 Ultra):** the driver carries the firmware placement of one
  M1 Ultra. Another machine needs its own placement and blobs, made with
  `tools/t6002_placement.py` (its docs/98). Not for general use.

When the files are in place on a supported SoC:

```sh
sudo systemctl enable --now apple-ave.service
/usr/libexec/apple-ave/ave-load status
```

## Why only 13.5

The firmware runs from where the boot loader placed it. The driver's tables
(placement, data layout, hashes) are for the 13.5 firmware only. A machine
installed with another system firmware version needs a port (the AVE
repository's docs/79).
