#pragma once
#include <Arduino.h>
#include <BleKeyboard.h>

// Onboard Hardware Pins
#define PIN_TFT_BL        45
#define PIN_RGB_LED       42
#define PIN_BAT_ADC       9

#define PIN_TP_SDA        16
#define PIN_TP_SCL        15
#define PIN_TP_INT        17
#define PIN_TP_RST        18

// Screen Dimensions
#define SCREEN_WIDTH      320
#define SCREEN_HEIGHT     240

// UI Layout Constants
#define STATUS_BAR_H      32
#define GRID_ROWS         2
#define GRID_COLS         3
#define NUM_BUTTONS_PAGE  (GRID_ROWS * GRID_COLS)
#define NUM_PAGES         6
#define PAGE_VOICE        4
#define PAGE_DASHBOARD    5

#define TOUCH_PREV_PAGE   100
#define TOUCH_NEXT_PAGE   101
#define TOUCH_DASH_HOME   102
#define TOUCH_DASH_WORK   103
#define TOUCH_VOICE_CHAT  104

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
