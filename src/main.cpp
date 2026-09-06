#include <Arduino.h>
#include <Wire.h>
#include <TFT_eSPI.h>
#include <FT6336.h>
#include <BleKeyboard.h>
#include <Adafruit_NeoPixel.h>

#include "macropad_config.h"
#include "gui.h"

// Hardware Instances
TFT_eSPI tft = TFT_eSPI();
FT6336 ts = FT6336(PIN_TP_SDA, PIN_TP_SCL, PIN_TP_INT, PIN_TP_RST, 240, 320);
BleKeyboard bleKeyboard("ESP32 MacroPad", "Spotpear", 100);
Adafruit_NeoPixel pixel(1, PIN_RGB_LED, NEO_GRB + NEO_KHZ800);
MacroPadGUI gui(tft);

// Application State
uint8_t currentPage = 0;
bool lastBleState = false;
uint32_t lastPulseTime = 0;
uint8_t pulseBrightness = 0;
int8_t pulseDirection = 1;

void setLedColor(uint8_t r, uint8_t g, uint8_t b) {
  pixel.setPixelColor(0, pixel.Color(r, g, b));
  pixel.show();
}

void executeMacro(const MacroButton& btn) {
  Serial.printf("[MacroPad] Executing: %s (%s)\n", btn.label, btn.subtitle);

  if (!bleKeyboard.isConnected()) {
    Serial.println("[MacroPad] Not connected to host via BLE. Keystroke dropped.");
    return;
  }

  switch (btn.type) {
    case ACTION_MEDIA:
      if (btn.mediaKey) {
        bleKeyboard.write(*btn.mediaKey);
      }
      break;

    case ACTION_KEY_COMBO:
      if (btn.mod1) bleKeyboard.press(btn.mod1);
      if (btn.mod2) bleKeyboard.press(btn.mod2);
      if (btn.mod3) bleKeyboard.press(btn.mod3);
      if (btn.key)  bleKeyboard.press(btn.key);
      delay(30);
      bleKeyboard.releaseAll();
      break;

    case ACTION_STRING:
      if (btn.textPayload) {
        bleKeyboard.print(btn.textPayload);
      }
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n==========================================");
  Serial.println("   ESP32-S3 Touch Bluetooth MacroPad      ");
  Serial.println("==========================================");

  // Initialize Backlight (GPIO 45 HIGH)
  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, HIGH);

  // Initialize RGB LED
  pixel.begin();
  pixel.setBrightness(40);
  setLedColor(0, 0, 50); // Blue during startup

  // Initialize Touch Screen
  Serial.println("[Setup] Initializing FT6336 Touch...");
  ts.begin();
  ts.setRotation(ROTATION_RIGHT); // Landscape rotation

  // Initialize Display & GUI
  Serial.println("[Setup] Initializing ILI9341 Display...");
  gui.init();
  gui.drawAll(false, currentPage);

  // Initialize BLE Keyboard
  Serial.println("[Setup] Starting BLE Keyboard as 'ESP32 MacroPad'...");
  bleKeyboard.begin();

  Serial.println("[Setup] Ready! Pair with Windows as 'ESP32 MacroPad'.");
}

void loop() {
  bool currentBleState = bleKeyboard.isConnected();

  // 1. Check BLE Connection Changes
  if (currentBleState != lastBleState) {
    lastBleState = currentBleState;
    gui.drawStatusBar(currentBleState, currentPage);

    if (currentBleState) {
      Serial.println("[BLE] >>> CONNECTED to host! <<<");
      setLedColor(0, 50, 15); // Solid Green/Teal
    } else {
      Serial.println("[BLE] <<< DISCONNECTED from host. Advertising... <<<");
      setLedColor(50, 0, 0); // Red
    }
  }

  // 2. Background LED Breathing Effect when Disconnected
  if (!currentBleState) {
    uint32_t now = millis();
    if (now - lastPulseTime > 25) {
      lastPulseTime = now;
      pulseBrightness += pulseDirection * 2;
      if (pulseBrightness >= 60) pulseDirection = -1;
      if (pulseBrightness <= 4)  pulseDirection = 1;
      setLedColor(pulseBrightness, pulseBrightness / 4, 0); // Breathing amber
    }
  }

  // 3. Touch Handling
  ts.read();
  if (ts.isTouched) {
    int16_t tx = ts.points[0].x;
    int16_t ty = ts.points[0].y;

    // Constrain coordinates to landscape 320x240
    tx = constrain(tx, 0, 319);
    ty = constrain(ty, 0, 239);

    int8_t target = gui.getTouchTarget(tx, ty, currentPage);

    if (target == TOUCH_PREV_PAGE) {
      currentPage = (currentPage == 0) ? (NUM_PAGES - 1) : (currentPage - 1);
      setLedColor(50, 50, 50);
      gui.drawAll(currentBleState, currentPage);
      delay(150);
      while (true) {
        ts.read();
        if (!ts.isTouched) break;
        delay(20);
      }
      if (currentBleState) setLedColor(0, 50, 15);
    } 
    else if (target == TOUCH_NEXT_PAGE) {
      currentPage = (currentPage + 1) % NUM_PAGES;
      setLedColor(50, 50, 50);
      gui.drawAll(currentBleState, currentPage);
      delay(150);
      while (true) {
        ts.read();
        if (!ts.isTouched) break;
        delay(20);
      }
      if (currentBleState) setLedColor(0, 50, 15);
    } 
    else if (target >= 0 && target < PROFILES[currentPage].numButtons) {
      uint8_t btnIndex = (uint8_t)target;
      const MacroButton& btn = PROFILES[currentPage].buttons[btnIndex];

      // Visual & Haptic Press Feedback
      gui.drawButton(currentPage, btnIndex, true);
      setLedColor(120, 120, 120); // Bright White flash

      // Send Macro Command
      executeMacro(btn);

      // Wait until finger is lifted
      uint32_t pressStart = millis();
      while (true) {
        ts.read();
        if (!ts.isTouched) break;
        // Safety timeout in case finger stays held
        if (millis() - pressStart > 1500) break;
        delay(15);
      }

      // Visual Release Feedback
      gui.drawButton(currentPage, btnIndex, false);
      if (currentBleState) {
        setLedColor(0, 50, 15);
      }

      delay(30); // Small debounce
    }
  }

  delay(10);
}
