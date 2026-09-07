#include "gui.h"

MacroPadGUI::MacroPadGUI(TFT_eSPI& tft) : _tft(tft) {}

void MacroPadGUI::init() {
  _tft.init();
  _tft.setRotation(1); // Landscape 320x240
  _tft.fillScreen(C_BG);
}

void MacroPadGUI::getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h) {
  uint8_t count = PROFILES[pageIndex].numButtons;

  if (count == 1) {
    // Single Large Center Button (Voice Page)
    w = 280;
    h = 75;
    x = 20;
    y = 44;
  } else if (count <= 3) {
    // 3 Wide Horizontal Buttons stacked vertically
    w = 300;
    h = 58;
    x = 10;
    y = 38 + btnIndex * (h + 8);
  } else {
    // 2 Rows x 3 Columns Standard Grid
    w = 98;
    h = 94;
    uint8_t row = btnIndex / GRID_COLS;
    uint8_t col = btnIndex % GRID_COLS;
    x = 7 + col * (w + 6);
    y = 38 + row * (h + 6);
  }
}

void MacroPadGUI::drawStatusBar(bool isConnected, uint8_t currentPage) {
  // Draw Status Bar Background
  _tft.fillRect(0, 0, SCREEN_WIDTH, STATUS_BAR_H, C_STATUS_BG);
  _tft.drawFastHLine(0, STATUS_BAR_H - 1, SCREEN_WIDTH, 0x3186);

  // Connection Indicator LED Circle
  uint16_t ledColor = isConnected ? C_CONNECTED : C_DISCONNECTED;
  _tft.fillCircle(10, STATUS_BAR_H / 2, 5, ledColor);
  _tft.drawCircle(10, STATUS_BAR_H / 2, 6, 0xFFFF);

  // Connection Status Text
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(isConnected ? C_CONNECTED : 0xFBA0, C_STATUS_BG);
  _tft.drawString(isConnected ? "CONNECTED" : "WAITING...", 22, STATUS_BAR_H / 2, 2);

  // Profile Title (Centered)
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(PROFILES[currentPage].themeColor, C_STATUS_BG);
  _tft.drawString(PROFILES[currentPage].title, 160, STATUS_BAR_H / 2, 2);

  // Page switcher buttons (< [1/5] >)
  // Left arrow button
  _tft.fillRoundRect(220, 4, 30, 24, 4, 0x2124);
  _tft.drawRoundRect(220, 4, 30, 24, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.setTextDatum(MC_DATUM);
  _tft.drawString("<", 235, 16, 2);

  // Page number text
  char pageBuf[8];
  snprintf(pageBuf, sizeof(pageBuf), "%d/%d", currentPage + 1, NUM_PAGES);
  _tft.setTextColor(C_TEXT_MUTED, C_STATUS_BG);
  _tft.drawString(pageBuf, 268, 16, 2);

  // Right arrow button
  _tft.fillRoundRect(286, 4, 30, 24, 4, 0x2124);
  _tft.drawRoundRect(286, 4, 30, 24, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.drawString(">", 301, 16, 2);
}

void MacroPadGUI::drawButton(uint8_t pageIndex, uint8_t btnIndex, bool pressed) {
  if (pageIndex >= NUM_PAGES || btnIndex >= PROFILES[pageIndex].numButtons) return;

  const MacroButton& btn = PROFILES[pageIndex].buttons[btnIndex];
  int16_t x, y, w, h;
  getButtonRect(pageIndex, btnIndex, x, y, w, h);

  uint16_t bg = pressed ? 0xFFFF : btn.bgColor;
  uint16_t border = pressed ? 0xFFFF : btn.borderColor;
  uint16_t textPrimary = pressed ? 0x0000 : C_TEXT_WHITE;
  uint16_t textSub = pressed ? 0x2965 : C_TEXT_MUTED;

  // Background & border
  _tft.fillRoundRect(x, y, w, h, 8, bg);
  _tft.drawRoundRect(x, y, w, h, 8, border);
  if (!pressed) {
    _tft.drawRoundRect(x + 1, y + 1, w - 2, h - 2, 7, border);
  }

  // Primary Label & Subtitle
  _tft.setTextDatum(MC_DATUM);
  if (PROFILES[pageIndex].numButtons == 1) {
    // Large Voice button layout
    _tft.setTextColor(textPrimary, bg);
    _tft.drawString(btn.label, x + w / 2, y + h / 2 - 12, 4);

    _tft.setTextColor(textSub, bg);
    _tft.drawString(btn.subtitle, x + w / 2, y + h / 2 + 16, 2);
  } else if (PROFILES[pageIndex].numButtons <= 3) {
    // Wide horizontal buttons layout
    _tft.setTextColor(textPrimary, bg);
    _tft.drawString(btn.label, x + w / 2, y + h / 2 - 10, 2);

    _tft.setTextColor(textSub, bg);
    _tft.drawString(btn.subtitle, x + w / 2, y + h / 2 + 12, 2);
  } else {
    // 6 buttons grid layout
    _tft.setTextColor(textPrimary, bg);
    _tft.drawString(btn.label, x + w / 2, y + h / 2 - 12, 2);

    _tft.setTextColor(textSub, bg);
    _tft.drawString(btn.subtitle, x + w / 2, y + h / 2 + 14, 2);
  }
}

void MacroPadGUI::drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg) {
  int16_t x = 15;
  int16_t y = 128;
  int16_t w = 290;
  int16_t h = 98;

  uint16_t borderColor = 0x5A1F;
  uint16_t bgColor = 0x0842;
  uint16_t headerColor = 0xFFFF;
  const char* header = "HERMES VOICE SATELLITE";

  switch (state) {
    case VOICE_UI_IDLE:
      borderColor = 0x8A3F; // Violet
      bgColor = 0x10A4;
      headerColor = 0xCE7F;
      header = "HERMES VOICE SATELLITE";
      break;

    case VOICE_UI_RECORDING:
      borderColor = 0xF800; // Red
      bgColor = 0x4800;     // Dark Red
      headerColor = 0xFFFF;
      header = "[ RECORDING AUDIO ]";
      break;

    case VOICE_UI_SENDING:
      borderColor = 0xFD20; // Amber / Yellow
      bgColor = 0x4220;     // Dark Amber
      headerColor = 0xFFE0;
      header = "[ TRANSCRIBING & SENDING ]";
      break;

    case VOICE_UI_SUCCESS:
      borderColor = 0x07E0; // Green
      bgColor = 0x0280;     // Dark Green
      headerColor = 0x87F0;
      header = "[ SENT TO HERMES & TELEGRAM ]";
      break;

    case VOICE_UI_ERROR:
      borderColor = 0xF800; // Red
      bgColor = 0x3000;
      headerColor = 0xFA40;
      header = "[ TRANSMISSION FAILED ]";
      break;
  }

  // Draw card panel
  _tft.fillRoundRect(x, y, w, h, 6, bgColor);
  _tft.drawRoundRect(x, y, w, h, 6, borderColor);
  _tft.drawRoundRect(x + 1, y + 1, w - 2, h - 2, 5, borderColor);

  // Card Header
  _tft.setTextDatum(TC_DATUM);
  _tft.setTextColor(headerColor, bgColor);
  _tft.drawString(header, x + w / 2, y + 8, 2);

  // Status Message
  _tft.setTextColor(0xFFFF, bgColor);
  _tft.drawString(statusMsg ? statusMsg : "", x + w / 2, y + 32, 2);

  // Detail / Transcript (wrapped or clamped)
  _tft.setTextColor(C_TEXT_MUTED, bgColor);
  String detail = detailMsg ? String(detailMsg) : "";
  if (detail.length() > 38) {
    detail = detail.substring(0, 35) + "...";
  }
  _tft.drawString(detail.c_str(), x + w / 2, y + 56, 2);

  // Server hint at bottom
  _tft.setTextColor(0x7BEF, bgColor);
  _tft.drawString("Hermes Cloudflare Gateway", x + w / 2, y + 78, 1);
}

void MacroPadGUI::drawAll(bool isConnected, uint8_t currentPage) {
  _tft.fillScreen(C_BG);
  drawStatusBar(isConnected, currentPage);
  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    drawButton(currentPage, i, false);
  }
  if (currentPage == PAGE_VOICE) {
    drawVoiceCard(VOICE_UI_IDLE, "Hermes Satellite Ready", "Hold button above to record voice message");
  }
}

int8_t MacroPadGUI::getTouchTarget(int16_t x, int16_t y, uint8_t currentPage) {
  // Check Top Navigation Buttons (Status Bar is 32px high, allow up to 36px for easy touch)
  if (y >= 0 && y <= (STATUS_BAR_H + 4)) {
    // Left arrow area
    if (x >= 180 && x < 255) return TOUCH_PREV_PAGE;
    // Page indicator ("X/5") and Right arrow area
    if (x >= 255 && x <= 320) return TOUCH_NEXT_PAGE;
    // Tapping the profile title in the center also advances to next page
    if (x >= 80 && x < 180) return TOUCH_NEXT_PAGE;
    return -1;
  }

  // Check Macro Buttons on active page
  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    int16_t bx, by, bw, bh;
    getButtonRect(currentPage, i, bx, by, bw, bh);
    if (x >= bx && x <= (bx + bw) && y >= by && y <= (by + bh)) {
      return (int8_t)i;
    }
  }

  return -1;
}
