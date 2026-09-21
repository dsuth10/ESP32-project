# Portrait UI — Flash & Revert Guide

Portrait (240×320) is the default UI on `main`.

Compile-time layout switch:
- `-DUI_PORTRAIT` → default 240×320 UI (`esp32-s3-portrait`)
- `-DUI_LANDSCAPE` → legacy 320×240 UI (`esp32-s3-devkitc-1`)

## Flash portrait (default)

```bash
python -m platformio run -t upload
# or explicitly:
python -m platformio run -e esp32-s3-portrait -t upload
```

## Revert to landscape (cheapest first)

### 1. Flash legacy landscape env

```bash
python -m platformio run -e esp32-s3-devkitc-1 -t upload
```

### 2. Emergency: flash archived golden binaries (no rebuild)

Golden landscape binaries live outside git at:

`bin/golden-landscape-<sha>/` (`firmware.bin`, `bootloader.bin`, `partitions.bin`)

Example with esptool (adjust COM port):

```bash
python -m esptool --chip esp32s3 --port COM5 write_flash 0x0 bin/golden-landscape-<sha>/bootloader.bin 0x8000 bin/golden-landscape-<sha>/partitions.bin 0x10000 bin/golden-landscape-<sha>/firmware.bin
```
