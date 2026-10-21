# Board upload safety

The original ES3C28P ESP32-S3 is the stable device. Keep its installed firmware unchanged while developing on the CYD. Registration reads identity and partition metadata; it does not install firmware, but briefly resets the board.

## Registered hardware and roles

| Profile | Hardware | Supported builds | Current role |
| --- | --- | --- | --- |
| `es3c28p-s3` | ESP32-S3, 16 MB flash | `esp32-s3-portrait`, `esp32-s3-devkitc-1` | Original board: stable, write-locked |
| `cyd-2432s028` | ESP32, 4 MB flash | Standalone `cyd-identify` diagnostic only | New board: test |

The complete application has not yet been ported to the CYD. Its screen and touch configuration have been tested; audio and other peripherals remain unverified.

Install the tested host uploader with `python -m pip install -r tools/board-safety-requirements.txt`. PlatformIO's bundled esptool remains a build dependency; guarded uploading uses the host's pinned esptool API.

The private registry lives at `.local/boards/registry.json` in the original repository, shared by Git worktrees. It contains each board's eFuse base MAC, processor, flash capacity, role, label and partition-table fingerprint. It is ignored by Git. A COM number is only the connection address, never the board identity. Registration cannot replace a conflicting identity, role or partition fingerprint.

Read-only registration, after physically identifying the connected board:

```powershell
python tools/board_safety.py register --profile es3c28p-s3 --port COM5 --label original-s3
python tools/board_safety.py register --profile cyd-2432s028 --port COM6 --label test-cyd --role test
```

These boards have already been registered on this computer. Do not re-register a different board under an existing label. Stable is the default role, including older registrations without a role field. There is deliberately no force/unlock switch. Changing the stable device's role requires a separately reviewed release decision and an explicit local registration change, after preserving a recovery backup; it must not be part of routine feature testing.

## Build and check without writing

```powershell
python -m platformio run -e esp32-s3-portrait
python tools/board_safety.py check --profile es3c28p-s3 --port COM5 --manifest .pio/build/esp32-s3-portrait/board-upload.json

python -m platformio run -d tools/board_diagnostics/cyd_identifier
python tools/board_safety.py check --profile cyd-2432s028 --port COM6 --manifest tools/board_diagnostics/cyd_identifier/.pio/build/cyd-identify/board-upload.json
```

Each compiled image gets a `board-upload.json` manifest with image SHA-256 hashes, processor/profile/environment binding, region limits and build-setting fingerprints. The manifest records image integrity and selected build settings; it is not a signed source-provenance attestation. Builds regenerate the upload binary and manifest even when compilation is cached. If build settings change, rebuild; leave the recorded hashes intact.

## Guarded test upload

```powershell
python -m platformio run -d tools/board_diagnostics/cyd_identifier -e cyd-identify -t upload --upload-port COM6
```

The root PlatformIO environments and diagnostic environment route `upload` through the same guard. Always supply the port explicitly. With both boards connected, a CYD build aimed at COM5 is refused; an S3 build aimed at COM6 is refused. Even a correctly matched S3 upload to the original is refused because it is stable/write-locked. Close serial monitors first; a busy, missing or unreadable port is a refusal, never a reason to select another port automatically.

`flash.py` is now a manifest-based guarded entry point, for example:

```powershell
python flash.py --check-only --profile es3c28p-s3 --port COM5 --manifest .pio/build/esp32-s3-portrait/board-upload.json
```

The old positional demo-bin commands are disabled. Unmanifested prebuilt/golden binaries are not accepted by this uploader. Existing private recovery archives remain intact; a future recovery requires a reviewed, board-bound recovery manifest rather than an unguarded command.

Before any write, the guard checks the explicit port, manifest and file hashes, image processor, permitted offsets and sizes, known physical device identity, chip, flash capacity, device role and unchanged partition fingerprint. It preloads image bytes, then uses one serial connection for identity checks and writing, without reopening the COM port. Unexpected security/encryption states are refused. Writes retain esptool's own safety checks and data verification. There is no full-flash erase option.

PlatformIO erase, filesystem/OTA upload and standalone bootloader/programming targets are disabled pending separately reviewed guarded workflows. Unsupported profiles, missing/corrupt registry or manifest, unknown devices, changed files/layouts and inspection failures stop the operation. Read-only `check` can inspect a stable board.

These safeguards cover the repository's supported upload routes. A person can still deliberately run an external raw esptool, OpenOCD or ESP-IDF command, modify the guard, or check out an older unguarded version. Local scripts cannot prevent those bypasses. Do not use those routes for routine uploads.

## Verification

Run `python -m unittest discover -s tools/tests -p test_board_safety.py`. Device checks and live-route results are recorded in the hardware inspection report; mocked test success does not establish physical UI or classroom acceptance.

### Verified on 21 October 2026

Both physical boards were registered on this computer: original S3 at COM5, CYD at COM6. The original role is explicitly stable/write-locked; the test board role is test. Registration did not write flash.

26 automated tests passed. Guarded S3 and CYD builds generated manifests successfully. With both devices connected, live checks refused CYD images on the S3, S3 images on the CYD, and an otherwise matching upload to the stable S3. The legacy entry point refused a cross-board upload and its old positional arguments. PlatformIO refused an upload without a port and refused erase and filesystem-upload targets. Read-only preflights passed on both boards.

In the feature checkout, the normal PlatformIO CYD upload refused COM5, then succeeded on the registered COM6 test board, with data verification. No firmware was uploaded to the original S3. Both local checkouts have the safety tooling so the older working folder does not retain its previous unguarded launcher; the original main commit and application firmware sources were not changed. The safety changes are committed on the feature branch.

Final cached-build regression checks also passed. After the guarded test upload, the first 65,536 flash bytes on the CYD matched its original private backup byte-for-byte, verifying that its bootloader, partition table, NVS and OTA metadata were preserved.
