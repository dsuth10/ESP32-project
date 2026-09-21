#pragma once
#include <Arduino.h>
#include <BleKeyboard.h>

// Onboard Hardware Pins
#define PIN_BOOT          0
#define PIN_PA_ENABLE     1
#define PIN_TFT_BL        45
#define PIN_RGB_LED       42
#define PIN_BAT_ADC       9

#define PIN_TP_SDA        16
#define PIN_TP_SCL        15
#define PIN_TP_INT        17
#define PIN_TP_RST        18

// Onboard SD Card Pins (SDIO 4-bit)
#define PIN_SD_CLK        38
#define PIN_SD_CMD        40
#define PIN_SD_D0         39
#define PIN_SD_D1         41
#define PIN_SD_D2         48
#define PIN_SD_D3         47

#include "ui_layout.h"

#define NUM_BUTTONS_PAGE  (GRID_ROWS * GRID_COLS)
#define NUM_PAGES         7
#define PAGE_DASHBOARD    0
#define PAGE_VOICE        5
#define PAGE_STORAGE      6

#define TOUCH_PREV_PAGE   100
#define TOUCH_NEXT_PAGE   101
#define TOUCH_DASH_HOME   102
#define TOUCH_DASH_WORK   103
#define TOUCH_VOICE_CHAT        104
#define TOUCH_VOICE_SCROLL_UP   105
#define TOUCH_VOICE_SCROLL_DOWN 106
#define TOUCH_VOICE_CLEAR       107
#define TOUCH_DASH_VOL_DOWN     108
#define TOUCH_DASH_VOL_UP       109
#define TOUCH_DASH_VOL_MUTE     110
#define TOUCH_VOICE_AUDIO_TOGGLE 111
#define TOUCH_POWER              112
#define TOUCH_POWER_CANCEL       113
#define TOUCH_POWER_CONFIRM      114

#define TOUCH_STORAGE_UP         120
#define TOUCH_STORAGE_REFRESH    121
#define TOUCH_STORAGE_SCROLL_UP  122
#define TOUCH_STORAGE_SCROLL_DOWN 123
#define TOUCH_STORAGE_ITEM_BASE  130

// Color Palette (RGB565)
#define C_BG              0x0842  // Very dark slate
#define C_STATUS_BG       0x1084  // Dark bar
#define C_TEXT_WHITE      0xFFFF
#define C_TEXT_MUTED      0xBDD7
#define C_CONNECTED       0x07E0  // Green
#define C_DISCONNECTED    0xF800  // Red
#define C_ACCENT          0x051D  // Cyan / Blue
#define C_VOICE_BG        0x18F4  // Deep Indigo
#define C_VOICE_BORDER    0x8A3F  // Vibrant Violet

// Action Types
enum ActionType {
  ACTION_MEDIA,
  ACTION_KEY_COMBO,
  ACTION_STRING,
  ACTION_VOICE
};

struct MacroButton {
  const char* label;
  const char* subtitle;
  uint16_t bgColor;
  uint16_t borderColor;
  ActionType type;
  
  // For ACTION_MEDIA
  const MediaKeyReport* mediaKey;
  
  // For ACTION_KEY_COMBO (up to 3 modifiers + 1 key)
  uint8_t mod1;
  uint8_t mod2;
  uint8_t mod3;
  uint8_t key;

  // For ACTION_STRING
  const char* textPayload;
};

struct MacroProfile {
  const char* title;
  uint16_t themeColor;
  uint8_t numButtons; // e.g. 3 or 6
  MacroButton buttons[NUM_BUTTONS_PAGE];
};

// Key combinations constants
extern const MacroProfile PROFILES[NUM_PAGES];
