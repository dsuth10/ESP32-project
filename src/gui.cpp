#include "gui.h"
#include "network_manager.h"

MacroPadGUI::MacroPadGUI(TFT_eSPI& tft) : _tft(tft) {}

void MacroPadGUI::init() {
  _tft.init();
  _tft.setRotation(1); // Landscape 320x240
  _tft.fillScreen(C_BG);
}

void MacroPadGUI::getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h) {
  uint8_t count = PROFILES[pageIndex].numButtons;

  if (count == 1) {
    // Single compact button on Voice Page
    w = 300;
    h = 42;
    x = 10;
    y = 36;
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

static void drawWrappedText(TFT_eSPI& tft, const char* text, int16_t x, int16_t y, int16_t maxW, uint8_t maxLines, uint16_t color, uint16_t bg, uint8_t font = 2) {
  if (!text || strlen(text) == 0) return;
  tft.setTextDatum(TL_DATUM);
  tft.setTextColor(color, bg);

  int16_t curX = x;
  int16_t curY = y;
  int16_t lineHeight = (font == 1) ? 12 : 16;
  uint8_t lineCount = 0;

  String word = "";
  String line = "";
  size_t len = strlen(text);

  for (size_t i = 0; i <= len; i++) {
    char c = text[i];
    if (c == ' ' || c == '\n' || c == '\0') {
      String testLine = (line.length() == 0) ? word : (line + " " + word);
      if (tft.textWidth(testLine.c_str(), font) > maxW && line.length() > 0) {
        tft.drawString(line.c_str(), curX, curY, font);
        lineCount++;
        if (lineCount >= maxLines) return;
        curY += lineHeight;
        line = word;
      } else {
        line = testLine;
      }
      word = "";
      if (c == '\n') {
        tft.drawString(line.c_str(), curX, curY, font);
        lineCount++;
        if (lineCount >= maxLines) return;
        curY += lineHeight;
        line = "";
      }
    } else {
      word += c;
    }
  }
  if (line.length() > 0 && lineCount < maxLines) {
    tft.drawString(line.c_str(), curX, curY, font);
  }
}

void MacroPadGUI::drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg) {
  int16_t x = 10;
  int16_t y = 82;
  int16_t w = 300;
  int16_t h = 152;

  uint16_t borderColor = 0x39E7;
  uint16_t bgColor = 0x0842;

  _tft.fillRoundRect(x, y, w, h, 6, bgColor);
  _tft.drawRoundRect(x, y, w, h, 6, borderColor);

  // Status Indicator Pill (20px high)
  uint16_t pillBg = 0x2124;
  uint16_t pillText = 0x9CD3;
  const char* pillStr = "VOICE SATELLITE READY";

  switch (state) {
    case VOICE_UI_IDLE:
      pillBg = 0x18C3;
      pillText = 0x8410;
      pillStr = "READY - HOLD BUTTON TO SPEAK";
      break;

    case VOICE_UI_RECORDING:
      pillBg = 0x9800; // Red
      pillText = 0xFFFF;
      pillStr = "[ RECORDING AUDIO ]";
      break;

    case VOICE_UI_SENDING:
      pillBg = 0xD3A0; // Amber
      pillText = 0x0000;
      pillStr = "[ TRANSCRIBING & SENDING ]";
      break;

    case VOICE_UI_SUCCESS:
      pillBg = 0x03E0; // Green
      pillText = 0xFFFF;
      pillStr = "[ RESPONSE RECEIVED ]";
      break;

    case VOICE_UI_ERROR:
      pillBg = 0x8000; // Red
      pillText = 0xFFFF;
      pillStr = "[ TRANSMISSION FAILED ]";
      break;
  }

  // Draw pill banner
  _tft.fillRoundRect(x + 6, y + 6, w - 12, 20, 4, pillBg);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(pillText, pillBg);
  _tft.drawString(pillStr, x + w / 2, y + 16, 2);

  // Divider line below pill
  _tft.drawFastHLine(x + 6, y + 30, w - 12, 0x2965);

  if (state == VOICE_UI_SUCCESS) {
    // 1. Question (Transcript)
    _tft.setTextDatum(TL_DATUM);
    _tft.setTextColor(0x07FF, bgColor); // Cyan
    _tft.drawString("You:", x + 10, y + 36, 2);
    drawWrappedText(_tft, statusMsg ? statusMsg : "", x + 46, y + 36, w - 56, 2, 0xFFFF, bgColor, 2);

    // Divider between question and reply
    _tft.drawFastHLine(x + 10, y + 74, w - 20, 0x2965);

    // 2. Answer (Hermes response)
    _tft.setTextDatum(TL_DATUM);
    _tft.setTextColor(0x07E0, bgColor); // Green
    _tft.drawString("Hermes:", x + 10, y + 80, 2);
    drawWrappedText(_tft, detailMsg ? detailMsg : "", x + 10, y + 98, w - 20, 3, 0xFFFF, bgColor, 2);
  }
  else if (state == VOICE_UI_RECORDING) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xFFFF, bgColor);
    _tft.drawString("Listening to your voice...", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString("Release button when done speaking", x + w / 2, y + 92, 2);
  }
  else if (state == VOICE_UI_SENDING) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xFFE0, bgColor);
    _tft.drawString("Uploading audio to Hermes...", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString(detailMsg ? detailMsg : "Transcribing with Whisper AI...", x + w / 2, y + 92, 2);
  }
  else if (state == VOICE_UI_ERROR) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xF800, bgColor);
    _tft.drawString(statusMsg ? statusMsg : "Transmission Failed", x + w / 2, y + 54, 2);
    _tft.setTextColor(0xFA40, bgColor);
    drawWrappedText(_tft, detailMsg ? detailMsg : "", x + 10, y + 78, w - 20, 3, 0xFA40, bgColor, 2);
  }
  else { // VOICE_UI_IDLE
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xCE7F, bgColor);
    _tft.drawString("Hold button above to record voice.", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString("Question & answer will appear here.", x + w / 2, y + 92, 2);
  }
}

void MacroPadGUI::drawStatusRow(int16_t x, int16_t y, int16_t w, const char* label, const char* value, HealthState health) {
  uint16_t dotColor;
  switch (health) {
    case HEALTH_READY:    dotColor = 0x07E0; break; // Green
    case HEALTH_DEGRADED: dotColor = 0xFDA0; break; // Amber
    case HEALTH_FAILED:   dotColor = 0xF800; break; // Red
    case HEALTH_UNKNOWN:
    default:              dotColor = 0x7BEF; break; // Muted Grey
  }

  // Draw status dot
  _tft.fillCircle(x + 8, y + 8, 4, dotColor);

  // Draw Label (Left aligned)
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(C_TEXT_MUTED, 0x0842);
  _tft.drawString(label, x + 18, y + 8, 2);

  // Draw Value (Right aligned)
  _tft.setTextDatum(MR_DATUM);
  _tft.setTextColor(C_TEXT_WHITE, 0x0842);
  _tft.drawString(value, x + w - 8, y + 8, 2);
}

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode) {
  int16_t cardX = 8;
  int16_t cardY = 36;
  int16_t cardW = 304;
  int16_t cardH = 144;

  // Background card
  _tft.fillRoundRect(cardX, cardY, cardW, cardH, 6, 0x0842);
  _tft.drawRoundRect(cardX, cardY, cardW, cardH, 6, 0x3186);

  // Header banner inside card
  _tft.fillRoundRect(cardX + 4, cardY + 4, cardW - 8, 22, 4, 0x18C3);
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(0xFFFF, 0x18C3);
  _tft.drawString("SYSTEM TELEMETRY", cardX + 12, cardY + 15, 2);

  // Subsystem readiness badges on header right
  _tft.setTextDatum(MR_DATUM);
  if (status.macropadReady && status.voiceReady) {
    _tft.setTextColor(0x07E0, 0x18C3);
    _tft.drawString("ALL SYSTEMS READY", cardX + cardW - 10, cardY + 15, 2);
  } else if (status.macropadReady) {
    _tft.setTextColor(0xFDA0, 0x18C3);
    _tft.drawString("MACROPAD READY", cardX + cardW - 10, cardY + 15, 2);
  } else {
    _tft.setTextColor(0xFBA0, 0x18C3);
    _tft.drawString("INITIALIZING...", cardX + cardW - 10, cardY + 15, 2);
  }

  // Row heights: 18px per row
  int16_t rowY = cardY + 30;
  int16_t rowH = 18;

  // Row 1: Wi-Fi SSID + RSSI
  char wifiBuf[32];
  if (status.wifi == HEALTH_READY) {
    snprintf(wifiBuf, sizeof(wifiBuf), "%s (%d dBm)", status.wifiSsid.c_str(), status.wifiRssi);
  } else {
    snprintf(wifiBuf, sizeof(wifiBuf), "%s", status.wifiSsid.c_str());
  }
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Wi-Fi", wifiBuf, status.wifi);

  // Row 2: Internet Connectivity (Phase 13)
  rowY += rowH;
  const char* internetVal;
  if (status.internet == HEALTH_READY) {
    internetVal = "Online";
  } else if (status.internet == HEALTH_DEGRADED) {
    internetVal = "Local LAN Only";
  } else {
    internetVal = "Offline";
  }
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Internet", internetVal, status.internet);

  // Row 3: Bluetooth HID + Expected Host (Phase 21)
  rowY += rowH;
  char bleBuf[40];
  if (status.bleConnected) {
    snprintf(bleBuf, sizeof(bleBuf), "Connected (%s)", status.expectedBleHost.c_str());
  } else {
    snprintf(bleBuf, sizeof(bleBuf), "Advertising...");
  }
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Bluetooth", bleBuf, status.ble);

  // Row 4: Voice Host
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Voice Host", status.voiceHostReady ? "Online (:8787)" : "Unreachable", status.voiceHost);

  // Row 5: Hermes Gateway
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Hermes", status.hermesReady ? "Ready (:8642)" : (status.hermes == HEALTH_DEGRADED ? "Starting / Live" : "Offline"), status.hermes);

  // Row 6: AI Backend
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "AI Model", status.aiBackendName.c_str(), status.aiBackend);

  // Bottom Section: Environment Switcher Buttons
  int16_t btnY = 186;
  int16_t btnH = 46;
  int16_t btnW = 146;

  bool homeActive = (currentMode == ENV_HOME);
  uint16_t homeBg = homeActive ? 0x0B4E : 0x1084;
  uint16_t homeBorder = homeActive ? 0x07E0 : 0x4228;
  _tft.fillRoundRect(cardX, btnY, btnW, btnH, 6, homeBg);
  _tft.drawRoundRect(cardX, btnY, btnW, btnH, 6, homeBorder);
  if (homeActive) {
    _tft.drawRoundRect(cardX + 1, btnY + 1, btnW - 2, btnH - 2, 5, homeBorder);
  }
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(homeActive ? 0xFFFF : C_TEXT_MUTED, homeBg);
  _tft.drawString(homeActive ? "HOME [ ACTIVE ]" : "SWITCH TO HOME", cardX + btnW / 2, btnY + btnH / 2, 2);

  // Right Button: WORK
  int16_t workX = cardX + btnW + 12;
  bool workActive = (currentMode == ENV_WORK);
  uint16_t workBg = workActive ? 0x3194 : 0x1084;
  uint16_t workBorder = workActive ? 0x07E0 : 0x4228;
  _tft.fillRoundRect(workX, btnY, btnW, btnH, 6, workBg);
  _tft.drawRoundRect(workX, btnY, btnW, btnH, 6, workBorder);
  if (workActive) {
    _tft.drawRoundRect(workX + 1, btnY + 1, btnW - 2, btnH - 2, 5, workBorder);
  }
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(workActive ? 0xFFFF : C_TEXT_MUTED, workBg);
  _tft.drawString(workActive ? "WORK [ ACTIVE ]" : "SWITCH TO WORK", workX + btnW / 2, btnY + btnH / 2, 2);
}

void MacroPadGUI::drawDashboardSwitching(const char* targetModeName) {
  int16_t cardX = 20;
  int16_t cardY = 70;
  int16_t cardW = 280;
  int16_t cardH = 100;

  _tft.fillRoundRect(cardX, cardY, cardW, cardH, 8, 0x1084);
  _tft.drawRoundRect(cardX, cardY, cardW, cardH, 8, 0xFDA0);
  _tft.drawRoundRect(cardX + 1, cardY + 1, cardW - 2, cardH - 2, 7, 0xFDA0);

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(0xFFFF, 0x1084);
  char buf[48];
  snprintf(buf, sizeof(buf), "Switching to %s Profile...", targetModeName);
  _tft.drawString(buf, 160, cardY + 32, 2);

  _tft.setTextColor(0xFDA0, 0x1084);
  _tft.drawString("Reconnecting Wi-Fi & Services...", 160, cardY + 65, 2);
}

void MacroPadGUI::drawAll(bool isConnected, uint8_t currentPage) {
  _tft.fillScreen(C_BG);
  drawStatusBar(isConnected, currentPage);

  if (currentPage == PAGE_DASHBOARD) {
    DashboardStatus status;
    status.wifi = netManager.isConnected() ? HEALTH_READY : HEALTH_FAILED;
    status.wifiSsid = netManager.getConnectedSSID();
    status.wifiRssi = netManager.getRSSI();
    status.ipAddress = netManager.getIpAddress();
    status.internet = netManager.isConnected() ? (netManager.checkInternet() ? HEALTH_READY : HEALTH_DEGRADED) : HEALTH_FAILED;
    status.internetConnected = (status.internet == HEALTH_READY);
    status.ble = isConnected ? HEALTH_READY : HEALTH_FAILED;
    status.bleConnected = isConnected;
    status.expectedBleHost = envManager.getActiveProfile().expectedBleHost;
    status.voiceHost = netManager.isConnected() ? HEALTH_READY : HEALTH_UNKNOWN;
    status.voiceHostReady = netManager.isConnected();
    status.hermes = netManager.isConnected() ? HEALTH_READY : HEALTH_UNKNOWN;
    status.hermesReady = netManager.isConnected();
    status.aiBackend = netManager.isConnected() ? HEALTH_READY : HEALTH_UNKNOWN;
    status.aiBackendName = (envManager.getMode() == ENV_WORK) ? "Local Ollama" : "Hermes Gateway";
    status.macropadReady = isConnected;
    status.voiceReady = netManager.isConnected();

    drawDashboard(status, envManager.getMode());
    return;
  }

  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    drawButton(currentPage, i, false);
  }
  if (currentPage == PAGE_VOICE) {
    drawVoiceCard(VOICE_UI_IDLE, "", "");
  }
}

int8_t MacroPadGUI::getTouchTarget(int16_t x, int16_t y, uint8_t currentPage) {
  // Check Top Navigation Buttons (Status Bar is 32px high, allow up to 36px for easy touch)
  if (y >= 0 && y <= (STATUS_BAR_H + 4)) {
    // Left arrow area
    if (x >= 180 && x < 255) return TOUCH_PREV_PAGE;
    // Page indicator ("X/6") and Right arrow area
    if (x >= 255 && x <= 320) return TOUCH_NEXT_PAGE;
    // Tapping the profile title in the center also advances to next page
    if (x >= 80 && x < 180) return TOUCH_NEXT_PAGE;
    return -1;
  }

  // Check Page 6 Dashboard buttons
  if (currentPage == PAGE_DASHBOARD) {
    // HOME button: cardX (8) to 8 + 146 = 154, y: 186 to 232
    if (x >= 8 && x <= 156 && y >= 184 && y <= 236) {
      return TOUCH_DASH_HOME;
    }
    // WORK button: workX (166) to 166 + 146 = 312, y: 186 to 232
    if (x >= 164 && x <= 314 && y >= 184 && y <= 236) {
      return TOUCH_DASH_WORK;
    }
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
