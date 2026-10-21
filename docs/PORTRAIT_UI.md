# Portrait UI — guarded build and recovery guide

Portrait (240 × 320) is the default S3 UI. `esp32-s3-portrait` selects portrait; `esp32-s3-devkitc-1` selects legacy landscape. These are ES3C28P ESP32-S3 builds, not CYD builds.

The original device is stable and write-locked during feature development. Follow [board upload safety](board-upload-safety.md) for registration, read-only preflight and supported upload routes. Do not bypass a stable-device rejection to test a feature.

Build without uploading:

```powershell
python -m platformio run -e esp32-s3-portrait
python -m platformio run -e esp32-s3-devkitc-1
```

After a separately approved release and device-role change, the normal upload command must specify both environment and port, for example `python -m platformio run -e esp32-s3-portrait -t upload --upload-port COM5`. The guard still verifies the actual device; COM5 is only an example connection address.

Private golden landscape archives remain at `bin/golden-landscape-<sha>/`. They are preserved for recovery, but the old direct-esptool restoration instructions are retired. Archived binaries require a reviewed board-bound recovery manifest and a verified recovery backup before use. The current uploader refuses unmanifested binaries and provides no force or full-erase switch.
