# CYD identification diagnostic

**Historical diagnostic only.** The CYD application port is abandoned; ES3C28P S3 is the programme's sole application target. Retain this source and its recorded checks for recovery/guard evidence, not as a scheduled development path. See [current scope](../../../docs/2026-10-21-companion-media-agent-master-plan.md).

Standalone diagnostic for the second ESP32-2432S028 candidate board; not a target for the existing ESP32-S3 firmware.

Build with `python -m platformio run -d tools/board_diagnostics/cyd_identifier`.
The compiler version is pinned alongside the existing toolchains. The build uses Arduino ESP32 2.0.17 with the locally installed PlatformIO platform 7.1.1.

The ordinary upload target now uses the shared board safety guard; see ../../../docs/board-upload-safety.md. It requires an explicitly selected port, a registered test device and a matching image manifest. Preserve a complete private flash backup before testing. On the inspected COM6 board, installation wrote only `firmware.bin` at `0x10000`, within the existing 0x140000-byte app0 partition. The original bootloader and partition table were retained. Its original app0 bytes are recoverable from the complete backup; restoration must use the same physical board and verified backup. Never commit flash dumps or settings.

Arduino NVS initialisation is bypassed with a diagnostic-only linker wrapper. No networking, storage access or SD-card operations are performed. There is no PSRAM detection or microphone/audio test.

Serial is 115200 baud. Commands: `A` initialises the ILI9341 candidate, `B` the ST7789 candidate, `I` toggles colour inversion, `R` reads LCD registers. Default is B, inversion off. Registers alone may not identify the controller reliably.

In portrait orientation the expected image has a black background, white border, red/green/blue vertical stripes, and one small white square at the top for A or two for B. Unequal bottom corner markers show orientation. The user must confirm the physical image; successful rendering with shared commands does not prove a unique controller model.

Touch events report raw X/Y/Z readings when the expected GPIO36 interrupt is low. Press the centre and opposite corners while capturing serial output to establish whether coordinates vary correctly. This is not yet a calibrated production touch driver.

Pin-map reference: https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display/blob/main/DisplayConfig/CYD2USB/User_Setup.h
Touch candidate: https://github.com/edemko/esp32-2432s028r-idf-clock
