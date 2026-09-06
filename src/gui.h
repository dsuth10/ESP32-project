#pragma once
#include <Arduino.h>
#include <TFT_eSPI.h>
#include "macropad_config.h"

#define TOUCH_PREV_PAGE 100
#define TOUCH_NEXT_PAGE 101

class MacroPadGUI {
public:
  MacroPadGUI(TFT_eSPI& tft);
  void init();
  void drawAll(bool isConnected, uint8_t currentPage);
  void drawStatusBar(bool isConnected, uint8_t currentPage);
  void drawButton(uint8_t pageIndex, uint8_t btnIndex, bool pressed);
  int8_t getTouchTarget(int16_t x, int16_t y, uint8_t currentPage);

private:
  TFT_eSPI& _tft;
  void getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h);
};
