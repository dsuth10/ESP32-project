#include "gui.h"
#include "network_manager.h"

MacroPadGUI::MacroPadGUI(TFT_eSPI& tft)
  : _tft(tft),
    _voiceState(VOICE_UI_IDLE),
    _voiceStatusMsg(""),
    _voiceDetailMsg(""),
    _voiceTranscript(""),
    _voiceReply(""),
    _voiceScrollLine(0) {}

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

static void wrapTextToChatLines(TFT_eSPI& tft, const char* text, int16_t maxW, uint16_t color, std::vector<ChatLine>& outLines, uint8_t font = 2) {
  if (!text || strlen(text) == 0) return;
  String word = "";
  String line = "";
  size_t len = strlen(text);

  for (size_t i = 0; i <= len; i++) {
    char c = text[i];
    if (c == '\r') continue; // Ignore carriage return for clean CRLF handling
    if (c == ' ' || c == '\n' || c == '\0') {
      // If the word itself is wider than maxW, break it into chunks
      while (word.length() > 0 && tft.textWidth(word.c_str(), font) > maxW) {
        size_t fitLen = word.length();
        while (fitLen > 1 && tft.textWidth(word.substring(0, fitLen).c_str(), font) > maxW) {
          fitLen--;
        }
        if (line.length() > 0) {
          outLines.push_back({line, color});
          line = "";
        }
        outLines.push_back({word.substring(0, fitLen), color});
        word = word.substring(fitLen);
      }

      String testLine = (line.length() == 0) ? word : (line + " " + word);
      if (tft.textWidth(testLine.c_str(), font) > maxW && line.length() > 0) {
        outLines.push_back({line, color});
        line = word;
      } else {
        line = testLine;
      }
      word = "";

      if (c == '\n') {
        outLines.push_back({line, color});
        line = "";
      }
    } else {
      word += c;
    }
  }
  if (line.length() > 0) {
    outLines.push_back({line, color});
  }
}

void MacroPadGUI::rebuildChatLines() {
  _chatLines.clear();
  const int16_t textMaxW = 280;

  if (_voiceTranscript.length() > 0) {
    _chatLines.push_back({"You:", 0x07FF}); // Cyan
    wrapTextToChatLines(_tft, _voiceTranscript.c_str(), textMaxW, 0xFFFF, _chatLines, 2);
    _chatLines.push_back({"", 0xFFFF}); // Blank line separator
  }

  _chatLines.push_back({"Hermes:", 0x07E0}); // Green
  wrapTextToChatLines(_tft, _voiceReply.c_str(), textMaxW, 0xFFFF, _chatLines, 2);
}

void MacroPadGUI::renderVoiceChatViewport() {
  const int16_t vpX = 14;
  const int16_t vpY = 115;
  const int16_t vpW = 292;
  const int16_t vpH = 116;
  const uint16_t bgColor = 0x0842;
  const uint8_t font = 2;
  const int16_t lineHeight = 16;
  const int visibleLines = 7;
  const int total = (int)_chatLines.size();

  // 1. Clear conversation text area and scrollbar track
  _tft.fillRect(vpX, vpY, vpW, vpH, bgColor);

  // 2. Render visible chat lines
  int16_t curY = vpY + 2;
  int endLine = min(total, _voiceScrollLine + visibleLines);
  for (int i = _voiceScrollLine; i < endLine; i++) {
    if (_chatLines[i].text.length() > 0) {
      _tft.setTextDatum(TL_DATUM);
      _tft.setTextColor(_chatLines[i].color, bgColor);
      _tft.drawString(_chatLines[i].text.c_str(), vpX, curY, font);
    }
    curY += lineHeight;
  }

  // 3. Render vertical scrollbar if total lines exceed visible capacity
  if (total > visibleLines) {
    const int16_t sbX = 302;
    const int16_t sbY = vpY + 2;
    const int16_t sbW = 4;
    const int16_t sbH = vpH - 4; // 112px

    // Track
    _tft.fillRoundRect(sbX, sbY, sbW, sbH, 2, 0x18C3);

    // Thumb
    int16_t thumbH = (visibleLines * sbH) / total;
    if (thumbH < 14) thumbH = 14;
    int maxScroll = total - visibleLines;
    int16_t thumbY = sbY + (_voiceScrollLine * (sbH - thumbH)) / maxScroll;

    _tft.fillRoundRect(sbX, thumbY, sbW, thumbH, 2, 0x8A3F); // Vibrant violet thumb
  }
}

void MacroPadGUI::scrollVoiceChat(int deltaLines) {
  const int visibleLines = 7;
  int total = (int)_chatLines.size();
  if (_voiceState != VOICE_UI_SUCCESS || total <= visibleLines) {
    return;
  }

  int maxScroll = total - visibleLines;
  int newScroll = constrain(_voiceScrollLine + deltaLines, 0, maxScroll);
  if (newScroll != _voiceScrollLine) {
    _voiceScrollLine = newScroll;
    renderVoiceChatViewport();
  }
}

bool MacroPadGUI::voiceChatScrollable() const {
  return (_voiceState == VOICE_UI_SUCCESS && _chatLines.size() > 7);
}

void MacroPadGUI::drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg) {
  _voiceState = state;

  if (state == VOICE_UI_SUCCESS) {
    _voiceTranscript = statusMsg ? statusMsg : "";
    _voiceReply = detailMsg ? detailMsg : "";
    _voiceScrollLine = 0;
    rebuildChatLines();
  } else {
    _voiceStatusMsg = statusMsg ? statusMsg : "";
    _voiceDetailMsg = detailMsg ? detailMsg : "";
    _chatLines.clear();
    _voiceScrollLine = 0;
  }

  redrawVoiceCard();
}

void MacroPadGUI::redrawVoiceCard() {
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

  switch (_voiceState) {
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
      pillStr = "[ REQUEST FAILED ]";
      break;
  }

  // Draw pill banner
  _tft.fillRoundRect(x + 6, y + 6, w - 12, 20, 4, pillBg);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(pillText, pillBg);
  _tft.drawString(pillStr, x + w / 2, y + 16, 2);

  // Divider line below pill
  _tft.drawFastHLine(x + 6, y + 30, w - 12, 0x2965);

  if (_voiceState == VOICE_UI_SUCCESS) {
    renderVoiceChatViewport();
  }
  else if (_voiceState == VOICE_UI_RECORDING) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xFFFF, bgColor);
    _tft.drawString(_voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "Listening to your voice...", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString(_voiceDetailMsg.length() > 0 ? _voiceDetailMsg.c_str() : "Release button when done speaking", x + w / 2, y + 92, 2);
  }
  else if (_voiceState == VOICE_UI_SENDING) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xFFE0, bgColor);
    _tft.drawString(_voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "Uploading audio to Hermes...", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString(_voiceDetailMsg.length() > 0 ? _voiceDetailMsg.c_str() : "Transcribing with Whisper AI...", x + w / 2, y + 92, 2);
  }
  else if (_voiceState == VOICE_UI_ERROR) {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xF800, bgColor);
    _tft.drawString(_voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "Request Failed", x + w / 2, y + 54, 2);
    _tft.setTextColor(0xFA40, bgColor);
    drawWrappedText(_tft, _voiceDetailMsg.c_str(), x + 10, y + 78, w - 20, 3, 0xFA40, bgColor, 2);
  }
  else { // VOICE_UI_IDLE
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xCE7F, bgColor);
    _tft.drawString(_voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "Hold button above to record voice.", x + w / 2, y + 64, 2);
    _tft.setTextColor(0x8410, bgColor);
    _tft.drawString(_voiceDetailMsg.length() > 0 ? _voiceDetailMsg.c_str() : "Question & answer will appear here.", x + w / 2, y + 92, 2);
  }
}

void MacroPadGUI::drawStatusRow(int16_t x, int16_t y, int16_t w, const char* label, const char* value, HealthState health, bool fullRedraw) {
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

  // Draw Label only on fullRedraw (static labels never change)
  if (fullRedraw) {
    _tft.setTextDatum(ML_DATUM);
    _tft.setTextColor(C_TEXT_MUTED, 0x0842);
    _tft.drawString(label, x + 18, y + 8, 2);
  }

  // Clear value area to prevent ghosting when text length changes
  _tft.fillRect(x + 85, y, w - 90, 16, 0x0842);

  // Draw Value (Right aligned)
  _tft.setTextDatum(MR_DATUM);
  _tft.setTextColor(C_TEXT_WHITE, 0x0842);
  _tft.drawString(value, x + w - 8, y + 8, 2);
}

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, bool fullRedraw) {
  int16_t cardX = 8;
  int16_t cardY = 36;
  int16_t cardW = 304;
  int16_t cardH = 144;

  if (fullRedraw) {
    // Background card
    _tft.fillRoundRect(cardX, cardY, cardW, cardH, 6, 0x0842);
    _tft.drawRoundRect(cardX, cardY, cardW, cardH, 6, 0x3186);

    // Header banner inside card
    _tft.fillRoundRect(cardX + 4, cardY + 4, cardW - 8, 22, 4, 0x18C3);
    _tft.setTextDatum(ML_DATUM);
    _tft.setTextColor(0xFFFF, 0x18C3);
    _tft.drawString("SYSTEM TELEMETRY", cardX + 12, cardY + 15, 2);
  }

  // Subsystem readiness badges on header right (clear badge box only)
  _tft.fillRect(cardX + cardW - 145, cardY + 5, 140, 20, 0x18C3);
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
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Wi-Fi", wifiBuf, status.wifi, fullRedraw);

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
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Internet", internetVal, status.internet, fullRedraw);

  // Row 3: Bluetooth HID + Expected Host (Phase 21)
  rowY += rowH;
  char bleBuf[40];
  if (status.bleConnected) {
    snprintf(bleBuf, sizeof(bleBuf), "Connected (%s)", status.expectedBleHost.c_str());
  } else {
    snprintf(bleBuf, sizeof(bleBuf), "Advertising...");
  }
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Bluetooth", bleBuf, status.ble, fullRedraw);

  // Row 4: Voice Host
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Voice Host", status.voiceHostReady ? "Online (:8787)" : "Unreachable", status.voiceHost, fullRedraw);

  // Row 5: Hermes Gateway
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Hermes", status.hermesReady ? "Ready (:8642)" : (status.hermes == HEALTH_DEGRADED ? "Starting / Live" : "Offline"), status.hermes, fullRedraw);

  // Row 6: AI Backend
  rowY += rowH;
  drawStatusRow(cardX + 4, rowY, cardW - 8, "AI Model", status.aiBackendName.c_str(), status.aiBackend, fullRedraw);

  // Bottom Section: Environment Switcher Buttons (only on fullRedraw)
  if (fullRedraw) {
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
    status.internet = netManager.isConnected() ? HEALTH_READY : HEALTH_FAILED;
    status.internetConnected = netManager.isConnected();
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

    drawDashboard(status, envManager.getMode(), true); // fullRedraw = true on initial page entry
    return;
  }

  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    drawButton(currentPage, i, false);
  }
  if (currentPage == PAGE_VOICE) {
    redrawVoiceCard();
  }
}

int8_t MacroPadGUI::getTouchTarget(int16_t x, int16_t y, uint8_t currentPage) {
  // Check Top Navigation Buttons (allow up to 45px for effortless finger touches)
  if (y >= 0 && y <= 45) {
    // Left side of top bar navigates to previous page (< arrow & title)
    if (x < 260) return TOUCH_PREV_PAGE;
    // Right side of top bar navigates to next page (> arrow)
    return TOUCH_NEXT_PAGE;
  }

  // Check Page 5 Voice scroll area (inside conversation card)
  if (currentPage == PAGE_VOICE) {
    if (x >= 10 && x <= 310 && y >= 112 && y <= 234) {
      return TOUCH_VOICE_CHAT;
    }
  }

  // Check Page 6 Dashboard buttons
  if (currentPage == PAGE_DASHBOARD) {
    // HOME button: left bottom area
    if (x >= 4 && x <= 158 && y >= 180 && y <= 240) {
      return TOUCH_DASH_HOME;
    }
    // WORK button: right bottom area
    if (x >= 160 && x <= 316 && y >= 180 && y <= 240) {
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
