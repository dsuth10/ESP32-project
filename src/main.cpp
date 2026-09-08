#include <Arduino.h>
#include <Wire.h>
#include <TFT_eSPI.h>
#include <FT6336.h>
#include <BleKeyboard.h>
#include <Adafruit_NeoPixel.h>

#include "macropad_config.h"
#include "gui.h"
#include "audio_recorder.h"
#include "network_manager.h"
#include "environment_manager.h"

// Set to 1 for raw microphone isolation diagnostic (Wi-Fi, TLS & Hermes upload disabled).
// Once genuine microphone PCM is proven, set to 0 to restore full network pipeline.
#define AUDIO_DIAGNOSTIC_MODE 0

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

    case ACTION_VOICE:
      // Handled directly in loop()
      break;
  }
}

void setup() {
  disableLoopWDT();
  // 0. Ensure Audio Power Amplifier (FM8002 on GPIO 1, active-LOW) is shut down / muted
  pinMode(1, OUTPUT);
  digitalWrite(1, HIGH);

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

  // Initialize Touch Screen (Wire on SDA 16, SCL 15)
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

  // Configure BLE Security to avoid Windows MITM PIN requirement loop
  BLESecurity* pSecurity = new BLESecurity();
  pSecurity->setAuthenticationMode(ESP_LE_AUTH_BOND);
  pSecurity->setCapability(ESP_IO_CAP_NONE);
  pSecurity->setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);

  // Initialize Audio Recorder & ES8311 Codec
  Serial.println("[Setup] Initializing Audio Recorder & ES8311 Codec...");
  recorder.begin();

#if !AUDIO_DIAGNOSTIC_MODE
  // Initialize Environment Manager (NVS preferences & profiles)
  Serial.println("[Setup] Initializing Environment Manager...");
  envManager.begin();
  envManager.onEnvironmentChange([](EnvironmentMode newMode) {
    netManager.applyEnvironment(newMode);
  });

  // Initialize Wi-Fi Network Manager strictly for active environment
  Serial.println("[Setup] Initializing Wi-Fi Connection...");
  netManager.begin();
#else
  Serial.println("[Setup] *************************************************************");
  Serial.println("[Setup] *** AUDIO_DIAGNOSTIC_MODE ACTIVE                          ***");
  Serial.println("[Setup] *** Wi-Fi, TLS, Cloudflare & Hermes upload are DISABLED. ***");
  Serial.println("[Setup] *** Press voice button to record and view raw statistics. ***");
  Serial.println("[Setup] *************************************************************");
#endif

  Serial.println("[Setup] Ready! Pair with Windows as 'ESP32 MacroPad'.");
}

void loop() {
  bool currentBleState = bleKeyboard.isConnected();

#if !AUDIO_DIAGNOSTIC_MODE
  // 1. Maintain Wi-Fi Connection
  netManager.update();
#endif

  // 2. Check BLE Connection Changes
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

  // 3. Background LED Breathing Effect when Disconnected
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

  // 4. Periodic Dashboard Telemetry Update (Page 6)
  if (currentPage == PAGE_DASHBOARD && !recorder.isRecording()) {
    static uint32_t lastDashUpdate = 0;
    uint32_t now = millis();
    if (now - lastDashUpdate > 3000) {
      lastDashUpdate = now;
      DashboardStatus status;
      status.ble = currentBleState ? HEALTH_READY : HEALTH_FAILED;
      status.bleConnected = currentBleState;
      status.expectedBleHost = envManager.getActiveProfile().expectedBleHost;
      status.macropadReady = currentBleState;

      // Deep probe: fetches composite status from receiver :8787/status with Bearer token
      netManager.fetchCompositeStatus(status);

      gui.drawDashboard(status, envManager.getMode());
    }
  }

  // 5. Touch Handling
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
    else if (target == TOUCH_DASH_HOME) {
      if (envManager.getMode() != ENV_HOME) {
        Serial.println("[Dashboard] User tapped SWITCH TO HOME");
        setLedColor(0, 100, 100);
        gui.drawDashboardSwitching("HOME");
        envManager.setMode(ENV_HOME);
        delay(400);
        gui.drawAll(currentBleState, currentPage);
        while (true) {
          ts.read();
          if (!ts.isTouched) break;
          delay(20);
        }
        if (currentBleState) setLedColor(0, 50, 15);
      }
    }
    else if (target == TOUCH_DASH_WORK) {
      if (envManager.getMode() != ENV_WORK) {
        Serial.println("[Dashboard] User tapped SWITCH TO WORK");
        setLedColor(100, 0, 100);
        gui.drawDashboardSwitching("WORK");
        envManager.setMode(ENV_WORK);
        delay(400);
        gui.drawAll(currentBleState, currentPage);
        while (true) {
          ts.read();
          if (!ts.isTouched) break;
          delay(20);
        }
        if (currentBleState) setLedColor(0, 50, 15);
      }
    }
    else if (target >= 0 && target < PROFILES[currentPage].numButtons) {
      uint8_t btnIndex = (uint8_t)target;
      const MacroButton& btn = PROFILES[currentPage].buttons[btnIndex];

      if (btn.type == ACTION_VOICE) {
        // === HERMES VOICE RECORD & SEND FLOW ===
        Serial.println("[Voice] >>> Touch down: Starting Voice Recording <<<");
        gui.drawButton(currentPage, btnIndex, true);
        gui.drawVoiceCard(VOICE_UI_RECORDING, "Listening...", "Keep holding while speaking");
        setLedColor(120, 0, 0); // Solid Red recording indicator

        recorder.startRecording();

        uint32_t lastSec = 0;
        while (true) {
          ts.read();
          recorder.update();

          uint32_t elapsedSec = recorder.getRecordDurationMs() / 1000;
          if (elapsedSec != lastSec && elapsedSec < 15) {
            lastSec = elapsedSec;
            char durBuf[32];
            snprintf(durBuf, sizeof(durBuf), "Recording [%u s]...", (unsigned int)elapsedSec);
            gui.drawVoiceCard(VOICE_UI_RECORDING, durBuf, "Release button to send");
          }

          if (!ts.isTouched || recorder.getRecordDurationMs() >= 15000) {
            break;
          }
          delay(10);
        }

        size_t wavBytes = recorder.stopRecording();
        gui.drawButton(currentPage, btnIndex, false);

        // Always log full per-channel diagnostics and codec registers
        recorder.logDiagnostics();

#if AUDIO_DIAGNOSTIC_MODE
        char titleBuf[64];
        char subBuf[128];
        snprintf(titleBuf, sizeof(titleBuf), "RMS: L%.0f R%.0f M%.0f", 
                 recorder.getLeftStats().getRms(),
                 recorder.getRightStats().getRms(),
                 recorder.getMonoStats().getRms());
        snprintf(subBuf, sizeof(subBuf), "Pk: L%d R%d | %s",
                 recorder.getMaxLeft(), recorder.getMaxRight(),
                 (recorder.getMonoStats().getRms() > 10.0 || recorder.getMaxLeft() > 30) ? "SIGNAL DETECTED" : "FLOOR / LOW");

        if (recorder.getMonoStats().getRms() > 10.0 || recorder.getMaxLeft() > 30) {
          gui.drawVoiceCard(VOICE_UI_SUCCESS, titleBuf, subBuf);
          setLedColor(0, 120, 30); // Green
        } else {
          gui.drawVoiceCard(VOICE_UI_ERROR, titleBuf, subBuf);
          setLedColor(120, 50, 0); // Amber
        }
        delay(4000);
#else
        if (wavBytes > 1000) {
          uint32_t peakVal = recorder.getMaxLeft() > recorder.getMaxRight() ? recorder.getMaxLeft() : recorder.getMaxRight();
          Serial.printf("[AUDIO] %.2fs | RMS %.1f | Peak %u | clipped %.2f%%\n",
                        recorder.getRecordDurationMs() / 1000.0f,
                        recorder.getMonoStats().getRms(),
                        peakVal,
                        recorder.getMonoStats().getClipPct());

          Serial.printf("[Voice] Recording finished (%u bytes). Sending to receiver...\n", (unsigned int)wavBytes);
          char statsBuf[64];
          gui.drawVoiceCard(VOICE_UI_SENDING, "Uploading to Gateway...", "Transcribing speech...");
          setLedColor(120, 80, 0); // Amber / Yellow

          String transcript, reply;
          bool success = netManager.sendVoiceAudio(recorder.getWavBuffer(), wavBytes, transcript, reply);

          if (success) {
            Serial.printf("[Voice] Success! Transcript: %s | Reply: %s\n", transcript.c_str(), reply.c_str());
            gui.drawVoiceCard(VOICE_UI_SUCCESS, transcript.c_str(), reply.c_str());
            setLedColor(0, 120, 30); // Bright Green
          } else {
            Serial.println("[Voice] Failed to send audio to receiver");
            gui.drawVoiceCard(VOICE_UI_ERROR, "Transmission Failed", reply.c_str());
            setLedColor(120, 0, 0); // Red
          }
        } else {
          Serial.println("[Voice] Recording too short, dropped.");
          gui.drawVoiceCard(VOICE_UI_IDLE, "Recording Canceled", "Hold button longer to speak");
          delay(800);
        }
#endif

        gui.drawButton(currentPage, btnIndex, false);
        if (currentBleState) {
          setLedColor(0, 50, 15);
        }
      } 
      else {
        // === STANDARD MACRO KEYSTROKE FLOW ===
        gui.drawButton(currentPage, btnIndex, true);
        setLedColor(120, 120, 120); // Bright White flash

        executeMacro(btn);

        // Wait until finger is lifted
        uint32_t pressStart = millis();
        while (true) {
          ts.read();
          if (!ts.isTouched) break;
          if (millis() - pressStart > 1500) break;
          delay(15);
        }

        gui.drawButton(currentPage, btnIndex, false);
        if (currentBleState) {
          setLedColor(0, 50, 15);
        }
        delay(30);
      }
    }
  }

  delay(10);
}
