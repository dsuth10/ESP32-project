# Second board: initial inspection

21 October 2026 — USB/serial inspection only

The user connected a different touchscreen board with both USB-C and micro-USB connectors. After reconnecting via micro-USB, Windows exposed **COM6**, `USB-SERIAL CH340`, USB VID/PID `1A86:7523`, status OK. The USB-C connector's function has not been established. A separate unidentified USB device remained present; it has not been attributed to this board.

Read-only esptool 5.4.0 bootloader queries (`--no-stub chip-id` and `--no-stub flash-id`, 115200 baud) reported:

| Item | Observed |
| --- | --- |
| Processor | ESP32-D0WD-V3, revision v3.1; original ESP32 family, not ESP32-S3 |
| Features | Dual core plus low-power core, 240 MHz, Wi-Fi and Bluetooth |
| Crystal | 40 MHz |
| External flash | Detected 4 MB |
| Flash manufacturer/device IDs | `5e` / `4016` |
| PSRAM | Not established by these queries |
| Display, touch, audio, battery/power wiring | Not yet identified |

Each diagnostic connection briefly reset the board and finished with an RTS reset. No firmware or persistent configuration was written. The unique MAC address is deliberately omitted from this report.

The current project targets the ES3C28P ESP32-S3, with a 16 MB flash layout and configured 8 MB octal PSRAM. Its GPIO assignments include pins outside the original ESP32's range. The existing binary, partition layout and hardware definitions must therefore not be treated as a drop-in match for this new board. Retain the existing S3 target unchanged and add a separate hardware/build profile only after the new board's printed model/revision and schematic are identified.

The original ESP32 supports Bluetooth LE, so a Bluetooth shortcut/controller port is a plausible candidate; this is not a verified working port. The Windows companion and cloud/media architecture can remain the shared host side. Display/touch drivers and pin mapping, available RAM/PSRAM, audio input/output and power handling require independent verification before promising the existing handheld feature set. See [project hardware reference](hardware-reference.md) and [Espressif ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.html).

Next evidence needed: the exact board/model label or clear front/back photographs. No firmware build or upload is authorised by this inspection record alone.
