#include "power_manager.h"

#include <FT6336.h>
#include <Adafruit_NeoPixel.h>
#include <driver/gpio.h>
#include <driver/rtc_io.h>

#include "macropad_config.h"
#include "gui.h"
#include "audio_recorder.h"

extern FT6336 ts;
extern Adafruit_NeoPixel pixel;

#define SLEEP_MAGIC 0x5AFE0FF1ul

#ifndef TOUCH_WAKE_DIAG
#define TOUCH_WAKE_DIAG 0
#endif

RTC_DATA_ATTR static uint32_t rtcSleepMagic = 0;
RTC_DATA_ATTR static uint8_t rtcSavedPage = 0;

PowerManager powerManager;

#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
static bool s_blPwmAttached = false;
#else
static const int BL_PWM_CHANNEL = 7;
static bool s_blPwmAttached = false;
#endif

static void releaseRtcPin(gpio_num_t pin) {
  gpio_hold_dis(pin);
  rtc_gpio_hold_dis(pin);
  rtc_gpio_deinit(pin);
}

void PowerManager::begin() {
  releasePinHolds();
  _wakeCause = esp_sleep_get_wakeup_cause();
  _softWake = (_wakeCause == ESP_SLEEP_WAKEUP_EXT0 || _wakeCause == ESP_SLEEP_WAKEUP_EXT1);
  logWakeCause();
  if (!_softWake) {
    rtcSleepMagic = 0;
  }
}

uint8_t PowerManager::restorePage(uint8_t fallback) const {
  if (_softWake && rtcSleepMagic == SLEEP_MAGIC && rtcSavedPage < NUM_PAGES) {
    return rtcSavedPage;
  }
  return fallback;
}

const char* PowerManager::enterSoftOff() {
#if TOUCH_WAKE_DIAG
  return enterSoftOffDiag();
#else
  if (recorder.isRecording()) {
    recorder.stopRecording();
  }
  pinMode(PIN_PA_ENABLE, OUTPUT);
  digitalWrite(PIN_PA_ENABLE, HIGH);
  pinMode(PIN_TP_RST, OUTPUT);
  digitalWrite(PIN_TP_RST, HIGH);
  pinMode(PIN_BOOT, INPUT_PULLUP);

  pixel.clear();
  pixel.show();

  fadeBacklightOff();

  uint32_t idleStart = millis();
  while (millis() - idleStart < 500) {
    ts.read();
    if (!ts.isTouched && digitalRead(PIN_BOOT) == HIGH) {
      break;
    }
    delay(20);
  }

  Serial.println("[Power] Soft-off (touch poll). Tap screen or BOOT.");

  const char* reason = "touch";
  while (true) {
    if (digitalRead(PIN_BOOT) == LOW) {
      reason = "BOOT";
      break;
    }
    ts.read();
    if (ts.isTouched) {
      reason = "touch";
      break;
    }
    delay(40);
  }

  uint32_t liftStart = millis();
  while (millis() - liftStart < 800) {
    ts.read();
    if (!ts.isTouched && digitalRead(PIN_BOOT) == HIGH) {
      break;
    }
    delay(20);
  }

  Serial.printf("[Power] Woke from %s\n", reason);
  return reason;
#endif
}

#if TOUCH_WAKE_DIAG
const char* PowerManager::enterSoftOffDiag() {
  if (recorder.isRecording()) {
    recorder.stopRecording();
  }
  pinMode(PIN_PA_ENABLE, OUTPUT);
  digitalWrite(PIN_PA_ENABLE, HIGH);
  pinMode(PIN_TP_RST, OUTPUT);
  digitalWrite(PIN_TP_RST, HIGH);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  pinMode(PIN_TP_INT, INPUT_PULLUP);

  pixel.clear();
  pixel.show();

  static const uint8_t kDuties[] = {0, 13, 255};
  static const char* kPhaseNames[] = {"BL=0%", "BL=~5%", "BL=100%"};
  const int kNumPhases = 3;
  const uint32_t kPhaseMs = 20000;

  struct PhaseStats {
    uint32_t touchSeen = 0;
    uint32_t busFail = 0;
    uint32_t intLow = 0;
    uint32_t samples = 0;
  };
  PhaseStats stats[3] = {};

  uint32_t idleStart = millis();
  while (millis() - idleStart < 500) {
    ts.read();
    if (!ts.isTouched && digitalRead(PIN_BOOT) == HIGH) {
      break;
    }
    delay(20);
  }

  Serial.println("[Diag] Soft-off diagnostic. Tap does NOT wake; BOOT exits.");
  Serial.println("[Diag] Phases cycle: 0% -> ~5% -> 100% (20s each).");
  Serial.flush();

  int phase = 0;
  setBacklightDuty(kDuties[phase]);
  Serial.printf("[Diag] Entering phase %d (%s)\n", phase, kPhaseNames[phase]);

  uint32_t sessionStart = millis();
  uint32_t phaseStart = millis();
  uint32_t lastHeartbeat = 0;
  uint8_t prevTd = 0xFE;
  int prevInt = -1;
  bool prevBusOk = true;
  bool firstSample = true;

  while (true) {
    if (digitalRead(PIN_BOOT) == LOW) {
      break;
    }

    ts.read();
    uint8_t td = ts.lastStatusRaw;
    bool busOk = ts.lastBusOk;
    uint8_t chipId = ts.readRegisterRaw(FT6336_ID_G_FOCALTECH_ID);
    int intPin = digitalRead(PIN_TP_INT);
    int bootPin = digitalRead(PIN_BOOT);
    bool touched = ts.isTouched;

    PhaseStats& st = stats[phase];
    st.samples++;
    if (touched) st.touchSeen++;
    if (!busOk) st.busFail++;
    if (intPin == LOW) st.intLow++;

    bool changed = firstSample ||
                   td != prevTd ||
                   intPin != prevInt ||
                   busOk != prevBusOk;
    uint32_t now = millis();
    bool heartbeat = (now - lastHeartbeat) >= 1000;

    if (changed || heartbeat) {
      float tSec = (now - sessionStart) / 1000.0f;
      Serial.printf(
        "[Diag] t=%.1fs ph=%d bl=%u td=0x%02X bus=%s id=0x%02X touch=%d int=%d boot=%d%s\n",
        tSec,
        phase,
        (unsigned)kDuties[phase],
        td,
        busOk ? "OK" : "FAIL",
        chipId,
        touched ? 1 : 0,
        intPin,
        bootPin,
        heartbeat && !changed ? " (hb)" : ""
      );
      Serial.flush();
      lastHeartbeat = now;
      prevTd = td;
      prevInt = intPin;
      prevBusOk = busOk;
      firstSample = false;
    }

    if (now - phaseStart >= kPhaseMs) {
      Serial.printf(
        "[Diag] Phase %d (%s) summary: samples=%lu touchSeen=%lu busFail=%lu intLow=%lu\n",
        phase,
        kPhaseNames[phase],
        (unsigned long)st.samples,
        (unsigned long)st.touchSeen,
        (unsigned long)st.busFail,
        (unsigned long)st.intLow
      );
      phase = (phase + 1) % kNumPhases;
      setBacklightDuty(kDuties[phase]);
      phaseStart = millis();
      firstSample = true;
      Serial.printf("[Diag] Entering phase %d (%s)\n", phase, kPhaseNames[phase]);
      Serial.flush();
    }

    delay(40);
  }

  detachBacklightPwm();
  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, LOW);

  Serial.println("[Diag] ========== SESSION SUMMARY ==========");
  for (int i = 0; i < kNumPhases; i++) {
    Serial.printf(
      "[Diag]   %s: samples=%lu touchSeen=%lu busFail=%lu intLow=%lu\n",
      kPhaseNames[i],
      (unsigned long)stats[i].samples,
      (unsigned long)stats[i].touchSeen,
      (unsigned long)stats[i].busFail,
      (unsigned long)stats[i].intLow
    );
  }
  Serial.println("[Diag] Decision guide:");
  Serial.println("[Diag]   touchSeen>0 only with BL on/dim -> Option A (dim-BL poll)");
  Serial.println("[Diag]   touchSeen>0 with BL=0%          -> Option B (BL-off poll)");
  Serial.println("[Diag]   busFail / id!=0x11              -> fix I2C/RST");
  Serial.println("[Diag]   intLow==0 even while tapping    -> INT unusable");
  Serial.println("[Diag]   touchSeen==0 all phases         -> Option D/E (BOOT only)");
  Serial.println("[Diag] =====================================");
  Serial.flush();

  uint32_t liftStart = millis();
  while (millis() - liftStart < 800) {
    ts.read();
    if (!ts.isTouched && digitalRead(PIN_BOOT) == HIGH) {
      break;
    }
    delay(20);
  }

  Serial.println("[Power] Woke from BOOT (diag)");
  return "BOOT";
}
#endif

void PowerManager::releasePinHolds() {
  gpio_deep_sleep_hold_dis();
  gpio_hold_dis((gpio_num_t)PIN_TFT_BL);
  gpio_hold_dis((gpio_num_t)PIN_RGB_LED);
  releaseRtcPin((gpio_num_t)PIN_PA_ENABLE);
  releaseRtcPin((gpio_num_t)PIN_TP_RST);
  releaseRtcPin((gpio_num_t)PIN_TP_INT);
  releaseRtcPin((gpio_num_t)PIN_TP_SDA);
  releaseRtcPin((gpio_num_t)PIN_TP_SCL);
  gpio_hold_dis((gpio_num_t)PIN_BOOT);
  rtc_gpio_hold_dis((gpio_num_t)PIN_BOOT);
}

void PowerManager::setBacklightDuty(uint8_t duty) {
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
  if (!s_blPwmAttached) {
    ledcAttach(PIN_TFT_BL, 5000, 8);
    s_blPwmAttached = true;
  }
  ledcWrite(PIN_TFT_BL, duty);
#else
  if (!s_blPwmAttached) {
    ledcSetup(BL_PWM_CHANNEL, 5000, 8);
    ledcAttachPin(PIN_TFT_BL, BL_PWM_CHANNEL);
    s_blPwmAttached = true;
  }
  ledcWrite(BL_PWM_CHANNEL, duty);
#endif
}

void PowerManager::detachBacklightPwm() {
  if (!s_blPwmAttached) {
    return;
  }
#if defined(ESP_ARDUINO_VERSION) && ESP_ARDUINO_VERSION >= ESP_ARDUINO_VERSION_VAL(3, 0, 0)
  ledcDetach(PIN_TFT_BL);
#else
  ledcDetachPin(PIN_TFT_BL);
#endif
  s_blPwmAttached = false;
}

void PowerManager::fadeBacklightOff() {
  setBacklightDuty(255);
  for (int duty = 255; duty >= 0; duty -= 15) {
    setBacklightDuty((uint8_t)duty);
    delay(18);
  }
  detachBacklightPwm();
  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, LOW);
}

void PowerManager::logWakeCause() const {
  switch (_wakeCause) {
    case ESP_SLEEP_WAKEUP_EXT0:
    case ESP_SLEEP_WAKEUP_EXT1:
      Serial.printf("[Power] Woke from previous deep-sleep (cause=%d)\n", (int)_wakeCause);
      break;
    default:
      Serial.printf("[Power] Cold boot (cause=%d)\n", (int)_wakeCause);
      break;
  }
}
