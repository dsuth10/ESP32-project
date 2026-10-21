# Project instructions

Use Australian English and metric measurements.

## Firmware and physical boards

The original ES3C28P ESP32-S3 is the stable device; preserve its installed firmware and stable/write-locked registration while developing on the CYD test board.

Before registering a board, uploading firmware, changing upload tooling or planning recovery, read [board upload safety](docs/board-upload-safety.md). Use the guarded PlatformIO or manifest-based `flash.py` route with an explicit profile/port and the registered physical identity. Keep hardware identities, settings and flash backups private in `.local/`.

A stable-device upload requires the user's explicit release decision and the reviewed role change described in that runbook. Treat a guard rejection as a stop for that write: investigate the mismatch rather than changing registrations, fingerprints or ports to make it pass. Use the registered test device for feature trials.

Keep development on the feature branch. The original main commit and stable-device firmware remain the reference until the user approves a release. Report build/automated checks separately from physical board and application acceptance.
