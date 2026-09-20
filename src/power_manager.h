#pragma once
#include <Arduino.h>
#include <esp_sleep.h>

class PowerManager {
public:
  void begin();
  bool isSoftWake() const { return _softWake; }
  uint8_t restorePage(uint8_t fallback) const;
  const char* enterSoftOff();

private:
  bool _softWake = false;
  esp_sleep_wakeup_cause_t _wakeCause = ESP_SLEEP_WAKEUP_UNDEFINED;

  void releasePinHolds();
  void fadeBacklightOff();
  void setBacklightDuty(uint8_t duty);
  void detachBacklightPwm();
  void logWakeCause() const;
#if TOUCH_WAKE_DIAG
  const char* enterSoftOffDiag();
#endif
};

extern PowerManager powerManager;
