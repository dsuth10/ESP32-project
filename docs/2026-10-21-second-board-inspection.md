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

## Further identification and reversible diagnostic

The user subsequently reported PCB marking `ESP32-24325028` and panel marking `TPM408-28`, plausibly `ESP32-2432S028` and `TPM408-2.8`. These support CYD-family identification without establishing a precise revision or display controller.

No USB mass-storage device was exposed. A private complete 4,194,304-byte flash read was taken; its partition table checksum validated. The table has NVS at 0x9000, OTA metadata at 0xe000, app0 at 0x10000, app1 at 0x150000 and SPIFFS at 0x290000. The entire SPIFFS partition is erased. Bounded searches of the application areas found no recognisable onboard documentation; this is not an exhaustive reverse-engineering result. The application descriptor identifies an Arduino core builder and cannot date or identify the board.

Following the user's request for manual identification, the diagnostic in `tools/board_diagnostics/cyd_identifier` built successfully. The full original flash matched the backup by device-side digest immediately before installation. Only the diagnostic application was written at 0x10000 and its write hash verified. Neither the bootloader nor the partition table was uploaded. NVS initialisation is bypassed to preserve existing settings. The original application remains recoverable from the private backup; it has not yet been restored.

The diagnostic runs and responds over serial. Initial repeated raw LCD reads were: 04=`40 C0 D9 FF 80 00`, 09=`52 29 82 00 00 00`, D3=`00 00 00 00 00 00`, DA/DB=`81 FF 00 00 00 00`, DC=`B3 FF 00 00 00 00`. These values have not been accepted as a unique controller ID. Default test profile is ST7789 candidate, inversion off. Physical colour-pattern confirmation and varying touch coordinates remain pending. No PSRAM, audio, Bluetooth or production UI compatibility is established by this diagnostic.
