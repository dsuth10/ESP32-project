#pragma once
#include <Arduino.h>
#include <TFT_eSPI.h>
#include "macropad_config.h"
#include "system_status.h"
#include "environment_manager.h"

enum VoiceUIState {
  VOICE_UI_IDLE,
  VOICE_UI_RECORDING,
  VOICE_UI_SENDING,
  VOICE_UI_SUCCESS,
  VOICE_UI_ERROR
};

class MacroPadGUI {
public:
  MacroPadGUI(TFT_eSPI& tft);
  void init();
  void drawAll(bool isConnected, uint8_t currentPage);
  void drawStatusBar(bool isConnected, uint8_t currentPage);
  void drawButton(uint8_t pageIndex, uint8_t btnIndex, bool pressed);
  void drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg);
  void drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, bool fullRedraw = true);
  void drawDashboardSwitching(const char* targetModeName);
  int8_t getTouchTarget(int16_t x, int16_t y, uint8_t currentPage);

private:
  TFT_eSPI& _tft;
  void getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h);
  void drawStatusRow(int16_t x, int16_t y, int16_t w, const char* label, const char* value, HealthState health, bool fullRedraw = true);
};
