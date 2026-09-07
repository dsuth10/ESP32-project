# ESP32-S3 2.8" Touch Display (ES3C28P) Guide & Solution

## 1. The Mystery Solved: Why Joshua Was Stuck

Joshua Hermes was investigating the board under the assumption that it was a **Waveshare ESP32-S3-Touch-LCD-2.8**. 

However:
1. **Wrong Board Identity:** This board is **NOT** the Waveshare board. It is the **ES3C28P** (manufactured by Spotpear / QD Electronic / LCDWIKI: `2.8inch_IPS_ESP32-S3_ILI9341V_ES3C28P`).
2. **Wrong Touch Controller:** The touch IC is **NOT** a CST328 or CST3530. It is a **FocalTech FT6336G** capacitive touch controller.
3. **The "Ghost" Devices Were Real:**
   - In test step 12, Joshua probed `GPIO16 (SDA)` and `GPIO15 (SCL)` and observed ACKs at `0x18` and `0x38`, but dismissed them as "ghosts" caused by strapping pins or level-shifters.
   - **`0x38`** is the standard I2C address of the **FT6336G Touch Controller**!
   - **`0x18`** is the standard I2C address of the onboard **ES8311 Audio Codec**!
   - **`GPIO 17`** (which Joshua observed pulsing ~2,000 times during touch) is indeed **`TP_INT`**!
   - **`GPIO 18`** is **`TP_RST`**!

---

## 2. Complete Hardware Pinout Reference

### Display (2.8" 240×320 IPS SPI — ILI9341V / ST7789 compatible)
| Signal | ESP32-S3 GPIO | Description |
|---|---|---|
| **TFT_CS** | **GPIO 10** | Chip Select (Active Low) |
| **TFT_MOSI** | **GPIO 11** | SPI Data Out |
| **TFT_SCK** | **GPIO 12** | SPI Clock |
| **TFT_MISO** | **GPIO 13** | SPI Data In |
| **TFT_DC / RS** | **GPIO 46** | Data/Command (HIGH=Data, LOW=Command) |
| **TFT_BL** | **GPIO 45** | Backlight Control (HIGH=ON) |
| **TFT_RST** | **CHIP_PU** | Tied to ESP32 hardware reset |

### Capacitive Touch (FocalTech FT6336G — I2C Address: 0x38)
| Signal | ESP32-S3 GPIO | Description |
|---|---|---|
| **TP_SDA** | **GPIO 16** | I2C Data (shared with ES8311 Audio Codec) |
| **TP_SCL** | **GPIO 15** | I2C Clock (shared with ES8311 Audio Codec) |
| **TP_INT** | **GPIO 17** | Touch Interrupt (Active Low on touch) |
| **TP_RST** | **GPIO 18** | Touch Reset (Active Low) |

### Audio (ES8311 Audio Codec — I2C Address: 0x18)
| Signal | ESP32-S3 GPIO | Description |
|---|---|---|
| **AUDIO_EN (PA)** | **GPIO 1** | Audio PA Enable (Active Low) |
| **I2S_MCK** | **GPIO 4** | Master Clock |
| **I2S_SCK (BCLK)**| **GPIO 5** | Bit Clock |
| **I2S_DO (ASDOUT)**| **GPIO 6** | Audio Data from ES8311 to ESP32 (Microphone) |
| **I2S_LRC (WS)** | **GPIO 7** | Word Select (Left/Right clock) |
| **I2S_DI (DSDIN)**| **GPIO 8** | Audio Data from ESP32 to ES8311 (Speaker DAC) |

### Other Onboard Peripherals
| Peripheral | Pin | Notes |
|---|---|---|
| **RGB LED** | **GPIO 42** | WS2812 / Single-wire addressable RGB LED |
| **Battery ADC** | **GPIO 9** | Battery voltage ADC divider input |
| **SD Card (SDIO)** | **GPIO 38, 40, 39, 41, 48, 47** | CLK=38, CMD=40, D0=39, D1=41, D2=48, D3=47 |
| **Native USB** | **GPIO 19 (D-), GPIO 20 (D+)** | USB CDC / JTAG serial |

---

## 3. Current Status & Flashed Firmware

The board on **COM5** is running the **Wireless Bluetooth MacroPad Firmware**:

- **Bluetooth BLE HID Keyboard:** Pairs with Windows as **`ESP32 MacroPad`**.
- **Display & Touch:** 2.8" IPS in landscape (320×240) with 4 interactive profiles:
  - **Page 1 (Media & Audio):** Play/Pause, Mute, Volume Up/Down, Track Prev/Next.
  - **Page 2 (Productivity):** Copy, Paste, Undo, Select All, Save, Cut.
  - **Page 3 (Windows Tools):** Snipping Tool, Task Manager, Desktop, Explorer, Lock PC, Calculator.
  - **Page 4 (Custom Keys):** 3 wide buttons for **`WIN + CTRL + SPACE`**, **`ENTER`**, and **`SHIFT + ENTER`** (new line in chat without sending).
- **RGB LED Feedback (GPIO 42):** Amber breathing when waiting to pair, solid green when connected, and bright white flash on touch.
- **Touch Screen:** Active and responsive to taps, swipes, sliders, tabs, buttons, and switches.

---

## 4. Quick Flash Tool (`flash.py`)

A helper script is provided to quickly switch between demo firmwares:

```bash
# Flash the interactive LVGL widgets demo
python flash.py widgets COM5

# Flash the LVGL Music player demo
python flash.py music COM5

# Flash the LVGL benchmark demo
python flash.py benchmark COM5

# Flash the LVGL stress demo
python flash.py stress COM5

# Flash the Xiaozhi AI Voice demo
python flash.py xiaozhi COM5
```

---

## 5. Directory Structure

```
ESP32 project/
├── bin/                          # Factory prebuilt binaries
│   ├── lv_demo_widgets.bin       # Interactive LVGL GUI demo
│   ├── lv_demo_music.bin         # Music player demo
│   ├── lv_demo_benchmark.bin     # Performance benchmark
│   └── common.bin                # AI Voice demo
├── docs/                         # Official documentation & hardware schematics
│   ├── schematic.pdf             # Complete schematic
│   ├── pinout_allocation.xlsx    # Full GPIO resource allocation table
│   ├── user_manual.pdf           # User manual
│   └── quick_start_manual.pdf    # Quick start instructions
├── examples/
│   └── touch_pen/                # Arduino touch drawing demo & touch.h driver
├── libraries/
│   └── FT6336/                   # FT6336 Arduino driver library
├── esp-idf-lvgl/                 # Full ESP-IDF 5.4.1 + LVGL 8.4 project source
├── flash.py                      # One-click demo flasher
└── README.md
```
