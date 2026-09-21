# Portrait UI Branch — Flash & Revert Guide

Branch: `feature/portrait-ui`

Compile-time layout switch:
- `-DUI_LANDSCAPE` → known-good 320×240 UI (default env)
- `-DUI_PORTRAIT` → experimental 240×320 UI

## Flash portrait

```bash
python -m platformio run -e esp32-s3-portrait -t upload
python -m platformio device monitor -e esp32-s3-portrait
```

## Revert to landscape (cheapest first)

### 1. Rebuild & flash landscape from this branch

```bash
python -m platformio run -e esp32-s3-devkitc-1 -t upload
```

### 2. Check out `main` and flash

```bash
git checkout main
python -m platformio run -e esp32-s3-devkitc-1 -t upload
```

### 3. Emergency: flash archived golden binaries (no rebuild)

Golden landscape binaries live outside git at:

`bin/golden-landscape-<sha>/` (`firmware.bin`, `bootloader.bin`, `partitions.bin`)

Example with esptool (adjust COM port and partition offsets to match `partitions.csv`):

```bash
python -m esptool --chip esp32s3 --port COM5 write_flash 0x0 bin/golden-landscape-<sha>/bootloader.bin 0x8000 bin/golden-landscape-<sha>/partitions.bin 0x10000 bin/golden-landscape-<sha>/firmware.bin
```

Or simply rebuild from `main` at the archived SHA if the archive folder is missing.
