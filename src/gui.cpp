#include "gui.h"
#include "network_manager.h"

MacroPadGUI::MacroPadGUI(TFT_eSPI& tft)
  : _tft(tft),
    _lastDrawnBatPercent(0),
    _lastDrawnCharging(false),
    _lastDrawnBatHealth(HEALTH_UNKNOWN),
    _voiceState(VOICE_UI_IDLE),
    _voiceStatusMsg(""),
    _voiceDetailMsg(""),
    _voiceScrollLine(0),
    _voiceAudioEnabled(true),
    _lastDrawnVolume(80),
    _currentStoragePath("/"),
    _storageScrollIndex(0),
    _storageTotalGB(0.0f),
    _storageFreeGB(0.0f),
    _storageUsedMB(0.0f) {}

void MacroPadGUI::init() {
  _tft.init();
  _tft.setRotation(UI_TFT_ROTATION);
  _tft.fillScreen(C_BG);
}

void MacroPadGUI::setVoiceAudioEnabled(bool enabled) {
  _voiceAudioEnabled = enabled;
}

void MacroPadGUI::getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h) {
  if (pageIndex == PAGE_VOICE) {
    w = UI_VOICE_BTN_W;
    h = UI_VOICE_BTN_H;
    x = UI_VOICE_BTN_X;
    y = UI_VOICE_BTN_Y;
    return;
  }

  uint8_t count = PROFILES[pageIndex].numButtons;

  if (count == 1) {
    w = UI_SINGLE_BTN_W;
    h = UI_SINGLE_BTN_H;
    x = UI_SINGLE_BTN_X;
    y = UI_SINGLE_BTN_Y;
  } else if (count <= 3) {
    w = UI_WIDE_BTN_W;
    h = UI_WIDE_BTN_H;
    x = UI_WIDE_BTN_X;
    y = UI_WIDE_BTN_ORIGIN_Y + btnIndex * (h + UI_WIDE_BTN_GAP);
  } else {
    w = UI_GRID_BTN_W;
    h = UI_GRID_BTN_H;
    uint8_t row = btnIndex / GRID_COLS;
    uint8_t col = btnIndex % GRID_COLS;
    x = UI_GRID_ORIGIN_X + col * (w + UI_GRID_GAP_X);
    y = UI_GRID_ORIGIN_Y + row * (h + UI_GRID_GAP_Y);
  }
}

void MacroPadGUI::drawStatusBar(bool isConnected, uint8_t currentPage, uint8_t batteryPercent, bool isCharging, HealthState batHealth) {
  _tft.fillRect(0, 0, SCREEN_WIDTH, STATUS_BAR_H, C_STATUS_BG);
  _tft.drawFastHLine(0, UI_SYSTEM_BAR_H - 1, SCREEN_WIDTH, 0x3186);
#if defined(UI_PORTRAIT)
  if (UI_TITLE_BAR_H > 0) {
    _tft.drawFastHLine(0, STATUS_BAR_H - 1, SCREEN_WIDTH, 0x3186);
  }
#endif

  uint16_t ledColor = isConnected ? C_CONNECTED : C_DISCONNECTED;
  _tft.fillCircle(10, UI_SYSTEM_BAR_H / 2, 5, ledColor);
  _tft.drawCircle(10, UI_SYSTEM_BAR_H / 2, 6, 0xFFFF);

  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(isConnected ? C_CONNECTED : 0xFBA0, C_STATUS_BG);
#if defined(UI_PORTRAIT)
  _tft.drawString(isConnected ? "OK" : "...", UI_CONN_TEXT_X, UI_CONN_TEXT_Y, 2);
#else
  _tft.drawString(isConnected ? "CONNECTED" : "WAITING...", UI_CONN_TEXT_X, UI_CONN_TEXT_Y, 2);
#endif

#if defined(UI_PORTRAIT)
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(PROFILES[currentPage].themeColor, C_STATUS_BG);
  _tft.drawString(PROFILES[currentPage].title, UI_TITLE_CX, UI_TITLE_CY, 2);
  if (currentPage == PAGE_DASHBOARD) {
    drawDashboardPowerButton();
  }
#else
  if (currentPage == PAGE_DASHBOARD) {
    _tft.setTextDatum(ML_DATUM);
    _tft.setTextColor(PROFILES[currentPage].themeColor, C_STATUS_BG);
    _tft.drawString(PROFILES[currentPage].title, 96, STATUS_BAR_H / 2, 2);
    drawDashboardPowerButton();
  } else {
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(PROFILES[currentPage].themeColor, C_STATUS_BG);
    _tft.drawString(PROFILES[currentPage].title, UI_TITLE_CX, UI_TITLE_CY, 2);
  }
#endif

  updateStatusBarBattery(batteryPercent, isCharging, batHealth);

  _tft.fillRoundRect(UI_NAV_PREV_X, UI_NAV_PREV_Y, UI_NAV_PREV_W, UI_NAV_PREV_H, 4, 0x2124);
  _tft.drawRoundRect(UI_NAV_PREV_X, UI_NAV_PREV_Y, UI_NAV_PREV_W, UI_NAV_PREV_H, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.setTextDatum(MC_DATUM);
  _tft.drawString("<", UI_NAV_PREV_X + UI_NAV_PREV_W / 2, UI_NAV_PREV_Y + UI_NAV_PREV_H / 2, 2);

  char pageBuf[8];
  snprintf(pageBuf, sizeof(pageBuf), "%d/%d", currentPage + 1, NUM_PAGES);
  _tft.setTextColor(C_TEXT_MUTED, C_STATUS_BG);
  _tft.drawString(pageBuf, UI_NAV_PAGE_CX, UI_NAV_PREV_Y + UI_NAV_PREV_H / 2, 2);

  _tft.fillRoundRect(UI_NAV_NEXT_X, UI_NAV_NEXT_Y, UI_NAV_NEXT_W, UI_NAV_NEXT_H, 4, 0x2124);
  _tft.drawRoundRect(UI_NAV_NEXT_X, UI_NAV_NEXT_Y, UI_NAV_NEXT_W, UI_NAV_NEXT_H, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.drawString(">", UI_NAV_NEXT_X + UI_NAV_NEXT_W / 2, UI_NAV_NEXT_Y + UI_NAV_NEXT_H / 2, 2);
}

void MacroPadGUI::updateStatusBarBattery(uint8_t batteryPercent, bool isCharging, HealthState batHealth) {
  _lastDrawnBatPercent = batteryPercent;
  _lastDrawnCharging = isCharging;
  _lastDrawnBatHealth = batHealth;

  const int16_t bx = UI_BAT_X;
  const int16_t by = UI_BAT_Y;
  const int16_t bw = UI_BAT_W;
  const int16_t bh = UI_BAT_H;

  // Clear battery area (differential redraw)
  _tft.fillRect(bx, by, bw, bh, C_STATUS_BG);

  if (batteryPercent == 0 && batHealth == HEALTH_UNKNOWN) {
    return; // Don't render until first telemetry read
  }

  // Battery icon frame (15 x 10)
  _tft.drawRoundRect(bx, by + 4, 15, 10, 2, 0xFFFF);
  _tft.fillRect(bx + 15, by + 7, 2, 4, 0xFFFF); // Terminal nipple

  // Battery fill bar inside frame (11 x 6 max)
  uint16_t fillColor = 0x07E0; // Green
  if (isCharging) {
    fillColor = 0x07FF; // Cyan for charging
  } else if (batHealth == HEALTH_DEGRADED) {
    fillColor = 0xFDA0; // Amber
  } else if (batHealth == HEALTH_FAILED) {
    fillColor = 0xF800; // Red
  }

  int fillW = (11 * batteryPercent) / 100;
  if (fillW > 11) fillW = 11;
  if (fillW > 0) {
    _tft.fillRect(bx + 2, by + 6, fillW, 6, fillColor);
  }

  // Percentage text next to icon
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(fillColor, C_STATUS_BG);
  char pctBuf[8];
  if (isCharging) {
    snprintf(pctBuf, sizeof(pctBuf), "+%d%%", batteryPercent);
  } else {
    snprintf(pctBuf, sizeof(pctBuf), "%d%%", batteryPercent);
  }
  _tft.drawString(pctBuf, bx + 19, by + 9, 1);
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

void MacroPadGUI::drawVoiceAudioToggle(bool pressed) {
  int16_t x = UI_VOICE_AUDIO_X;
  int16_t y = UI_VOICE_AUDIO_Y;
  int16_t w = UI_VOICE_AUDIO_W;
  int16_t h = UI_VOICE_AUDIO_H;

  uint16_t bg;
  uint16_t border;
  uint16_t textPrimary;
  uint16_t textSub;

  if (pressed) {
    bg = 0xFFFF;
    border = 0xFFFF;
    textPrimary = 0x0000;
    textSub = 0x2965;
  } else if (_voiceAudioEnabled) {
    bg = 0x0B4E;          // Deep Green/Teal
    border = 0x07E0;      // Bright Green
    textPrimary = 0xFFFF; // White
    textSub = 0x07E0;     // Green
  } else {
    bg = 0x2124;          // Dark Slate
    border = 0xFDA0;      // Amber
    textPrimary = 0xFFFF; // White
    textSub = 0xFDA0;     // Amber
  }

  _tft.fillRoundRect(x, y, w, h, 8, bg);
  _tft.drawRoundRect(x, y, w, h, 8, border);
  if (!pressed) {
    _tft.drawRoundRect(x + 1, y + 1, w - 2, h - 2, 7, border);
  }

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(textPrimary, bg);
  _tft.drawString("AUDIO", x + w / 2, y + 12, 2);

  _tft.setTextColor(textSub, bg);
  _tft.drawString(_voiceAudioEnabled ? "[ ON ]" : "[ OFF ]", x + w / 2, y + 28, 2);
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

void MacroPadGUI::clearConversation() {
  _history.clear();
  _chatLines.clear();
  _voiceScrollLine = 0;
  _voiceState = VOICE_UI_IDLE;
  _voiceStatusMsg = "";
  _voiceDetailMsg = "";
  redrawVoiceCard();
}

void MacroPadGUI::addVoiceTurn(const String& transcript, const String& reply) {
  if (transcript.length() > 0) {
    _history.push_back({true, transcript});
  }
  if (reply.length() > 0) {
    _history.push_back({false, reply});
  }

  // Bound conversation history to last 20 messages (10 full turns)
  const size_t maxHistory = 20;
  if (_history.size() > maxHistory) {
    _history.erase(_history.begin(), _history.begin() + (_history.size() - maxHistory));
  }

  rebuildChatLines();
  scrollToLatestResponse();
}

void MacroPadGUI::rebuildChatLines() {
  _chatLines.clear();
  const int16_t textMaxW = UI_VOICE_TEXT_MAX_W;

  for (size_t i = 0; i < _history.size(); i++) {
    const ChatMessage& msg = _history[i];
    if (msg.isUser) {
      _chatLines.push_back({"You:", 0x07FF}); // Cyan
      wrapTextToChatLines(_tft, msg.text.c_str(), textMaxW, 0xFFFF, _chatLines, 2);
    } else {
      _chatLines.push_back({"Hermes:", 0x07E0}); // Green
      wrapTextToChatLines(_tft, msg.text.c_str(), textMaxW, 0xFFFF, _chatLines, 2);
    }
    if (i + 1 < _history.size()) {
      _chatLines.push_back({"", 0xFFFF}); // Blank line separator between turns
    }
  }
}

void MacroPadGUI::scrollToBottom() {
  const int visibleLines = UI_VOICE_VISIBLE_LINES;
  int total = (int)_chatLines.size();
  _voiceScrollLine = max(0, total - visibleLines);
}

void MacroPadGUI::scrollToLatestResponse() {
  const int visibleLines = UI_VOICE_VISIBLE_LINES;
  int total = (int)_chatLines.size();
  if (total <= visibleLines) {
    _voiceScrollLine = 0;
    return;
  }

  // Find the last "Hermes:" header in _chatLines so user starts reading from the top of the answer
  int lastHermesLine = -1;
  for (int i = (int)_chatLines.size() - 1; i >= 0; i--) {
    if (_chatLines[i].text == "Hermes:" && _chatLines[i].color == 0x07E0) {
      lastHermesLine = i;
      break;
    }
  }

  if (lastHermesLine >= 0) {
    int maxScroll = total - visibleLines;
    _voiceScrollLine = constrain(lastHermesLine, 0, maxScroll);
  } else {
    _voiceScrollLine = max(0, total - visibleLines);
  }
}

void MacroPadGUI::scrollToTop() {
  _voiceScrollLine = 0;
}

bool MacroPadGUI::canScrollUp() const {
  return (_voiceScrollLine > 0);
}

bool MacroPadGUI::canScrollDown() const {
  const int visibleLines = UI_VOICE_VISIBLE_LINES;
  int total = (int)_chatLines.size();
  return (_voiceScrollLine + visibleLines < total);
}

bool MacroPadGUI::voiceChatScrollable() const {
  return (_chatLines.size() > UI_VOICE_VISIBLE_LINES);
}

void MacroPadGUI::scrollVoiceChat(int deltaLines) {
  const int visibleLines = UI_VOICE_VISIBLE_LINES;
  int total = (int)_chatLines.size();
  if (total <= visibleLines) {
    return;
  }

  int maxScroll = total - visibleLines;
  int newScroll = constrain(_voiceScrollLine + deltaLines, 0, maxScroll);
  if (newScroll != _voiceScrollLine) {
    _voiceScrollLine = newScroll;
    renderVoiceChatViewport();
  }
}

void MacroPadGUI::renderVoiceChatViewport() {
  const int16_t vpX = UI_VOICE_VP_X;
  const int16_t vpY = UI_VOICE_VP_Y;
  const int16_t vpW = UI_VOICE_VP_W;
  const int16_t vpH = UI_VOICE_VP_H;
  const uint16_t bgColor = 0x0842;
  const uint8_t font = 2;
  const int16_t lineHeight = UI_VOICE_LINE_H;
  const int visibleLines = UI_VOICE_VISIBLE_LINES;
  const int total = (int)_chatLines.size();

  _tft.fillRect(vpX, vpY, vpW, vpH, bgColor);

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

  const int16_t ctrlX = UI_VOICE_CTRL_X;
  const int16_t ctrlW = UI_VOICE_CTRL_W;

  if (total > visibleLines) {
    bool upActive = canScrollUp();
    bool downActive = canScrollDown();

    uint16_t upBg = upActive ? 0x18F4 : 0x1084;
    uint16_t upBorder = upActive ? 0x8A3F : 0x2124;
    uint16_t upTri = upActive ? 0xFFFF : 0x632C;

    _tft.fillRoundRect(ctrlX, vpY + 1, ctrlW, 26, 4, upBg);
    _tft.drawRoundRect(ctrlX, vpY + 1, ctrlW, 26, 4, upBorder);
    _tft.fillTriangle(ctrlX + 13, vpY + 7, ctrlX + 7, vpY + 19, ctrlX + 19, vpY + 19, upTri);

    const int16_t trackX = ctrlX + 10;
    const int16_t trackY = vpY + 30;
    const int16_t trackW = 6;
    const int16_t trackH = max((int16_t)20, (int16_t)(vpH - 62));

    _tft.fillRoundRect(trackX, trackY, trackW, trackH, 3, 0x18C3);

    int16_t thumbH = (visibleLines * trackH) / total;
    if (thumbH < 10) thumbH = 10;
    int maxScroll = total - visibleLines;
    int16_t thumbY = trackY + (_voiceScrollLine * (trackH - thumbH)) / maxScroll;

    _tft.fillRoundRect(trackX, thumbY, trackW, thumbH, 3, 0x8A3F);

    uint16_t downBg = downActive ? 0x18F4 : 0x1084;
    uint16_t downBorder = downActive ? 0x8A3F : 0x2124;
    uint16_t downTri = downActive ? 0xFFFF : 0x632C;

    const int16_t dnBtnY = vpY + vpH - 27;
    _tft.fillRoundRect(ctrlX, dnBtnY, ctrlW, 26, 4, downBg);
    _tft.drawRoundRect(ctrlX, dnBtnY, ctrlW, 26, 4, downBorder);
    _tft.fillTriangle(ctrlX + 13, dnBtnY + 19, ctrlX + 7, dnBtnY + 7, ctrlX + 19, dnBtnY + 7, downTri);
  } else {
    _tft.fillRect(ctrlX - 2, vpY, ctrlW + 6, vpH, bgColor);
  }
}

void MacroPadGUI::drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg) {
  _voiceState = state;
  _voiceStatusMsg = statusMsg ? statusMsg : "";
  _voiceDetailMsg = detailMsg ? detailMsg : "";

  if (state == VOICE_UI_SUCCESS) {
    if (statusMsg && detailMsg && (strlen(statusMsg) > 0 || strlen(detailMsg) > 0)) {
      addVoiceTurn(statusMsg, detailMsg);
    }
  }

  redrawVoiceCard();
}

void MacroPadGUI::redrawVoiceCard() {
  int16_t x = UI_VOICE_CARD_X;
  int16_t y = UI_VOICE_CARD_Y;
  int16_t w = UI_VOICE_CARD_W;
  int16_t h = UI_VOICE_CARD_H;

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
      if (_voiceAudioEnabled) {
        pillBg = 0x18C3;
        pillText = 0x8410;
        pillStr = "READY - HOLD BUTTON TO SPEAK";
      } else {
        pillBg = 0x2124;
        pillText = 0xFDA0;
        pillStr = "READY [TEXT ONLY] - HOLD TO TALK";
      }
      break;

    case VOICE_UI_RECORDING:
      pillBg = 0x9800; // Red
      pillText = 0xFFFF;
      pillStr = _voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "[ RECORDING AUDIO ]";
      break;

    case VOICE_UI_SENDING:
      pillBg = 0xFD60; // Bright Amber/Orange
      pillText = 0x0000;
      pillStr = _voiceAudioEnabled ? "[ TRANSCRIBING & WAITING FOR AI ]" : "[ WAITING FOR TEXT REPLY ]";
      break;

    case VOICE_UI_SUCCESS:
      pillBg = 0x03E0; // Green
      pillText = 0xFFFF;
      pillStr = _voiceAudioEnabled ? "[ RESPONSE RECEIVED ]" : "[ TEXT REPLY RECEIVED ]";
      break;

    case VOICE_UI_ERROR:
      pillBg = 0x8000; // Red
      pillText = 0xFFFF;
      pillStr = _voiceStatusMsg.length() > 0 ? _voiceStatusMsg.c_str() : "[ REQUEST FAILED ]";
      break;
  }

  // Draw pill banner
  bool hasHistory = !_history.empty();
  int16_t pillW = hasHistory ? (w - 56) : (w - 12);
  _tft.fillRoundRect(x + 6, y + 6, pillW, 20, 4, pillBg);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(pillText, pillBg);
  _tft.drawString(pillStr, x + 6 + pillW / 2, y + 16, 2);

  // Draw Clear Button [CLR] if conversation history exists
  if (hasHistory) {
    int16_t clrX = x + w - 46;
    int16_t clrY = y + 6;
    _tft.fillRoundRect(clrX, clrY, 40, 20, 4, 0x3186);
    _tft.drawRoundRect(clrX, clrY, 40, 20, 4, 0x632C);
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(0xCE7F, 0x3186);
    _tft.drawString("CLR", clrX + 20, clrY + 10, 2);
  }

  // Divider line below pill
  _tft.drawFastHLine(x + 6, y + 30, w - 12, 0x2965);

  if (hasHistory) {
    // Always render scrollable conversation history if we have messages!
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
  else { // VOICE_UI_IDLE and no history yet
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
  _tft.fillCircle(x + 8, y + 7, 3, dotColor);

  // Draw Label only on fullRedraw (static labels never change)
  if (fullRedraw) {
    _tft.setTextDatum(ML_DATUM);
    _tft.setTextColor(C_TEXT_MUTED, 0x0842);
    _tft.drawString(label, x + 18, y + 7, 2);
  }

  // Clear value area to prevent ghosting when text length changes
  _tft.fillRect(x + 75, y, w - 80, 14, 0x0842);

  // Draw Value (Right aligned)
  _tft.setTextDatum(MR_DATUM);
  _tft.setTextColor(C_TEXT_WHITE, 0x0842);
  _tft.drawString(value, x + w - 8, y + 7, 2);
}

void MacroPadGUI::drawDashboardVolume(uint8_t volume, bool fullRedraw) {
  _lastDrawnVolume = volume;
  const int16_t volY = UI_DASH_VOL_Y;
  const int16_t volH = UI_DASH_VOL_H;

  if (fullRedraw) {
    _tft.fillRoundRect(UI_DASH_VOL_MINUS_X, volY, UI_DASH_VOL_MINUS_W, volH, 6, 0x1084);
    _tft.drawRoundRect(UI_DASH_VOL_MINUS_X, volY, UI_DASH_VOL_MINUS_W, volH, 6, 0x4228);
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(C_TEXT_WHITE, 0x1084);
    _tft.drawString("-", UI_DASH_VOL_MINUS_X + UI_DASH_VOL_MINUS_W / 2, volY + volH / 2, 4);

    _tft.fillRoundRect(UI_DASH_VOL_PLUS_X, volY, UI_DASH_VOL_PLUS_W, volH, 6, 0x1084);
    _tft.drawRoundRect(UI_DASH_VOL_PLUS_X, volY, UI_DASH_VOL_PLUS_W, volH, 6, 0x4228);
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(C_TEXT_WHITE, 0x1084);
    _tft.drawString("+", UI_DASH_VOL_PLUS_X + UI_DASH_VOL_PLUS_W / 2, volY + volH / 2, 4);

    _tft.fillRoundRect(UI_DASH_VOL_CTR_X, volY, UI_DASH_VOL_CTR_W, volH, 6, 0x0842);
    _tft.drawRoundRect(UI_DASH_VOL_CTR_X, volY, UI_DASH_VOL_CTR_W, volH, 6, 0x3186);
  }

  _tft.fillRect(UI_DASH_VOL_CTR_X + 2, volY + 2, UI_DASH_VOL_CTR_W - 4, volH - 4, 0x0842);

  _tft.setTextDatum(MC_DATUM);
  char volStr[32];
  if (volume == 0) {
    snprintf(volStr, sizeof(volStr), "HERMES VOL: MUTED");
    _tft.setTextColor(0xF800, 0x0842);
  } else {
    snprintf(volStr, sizeof(volStr), "HERMES VOL: %d%%", volume);
    _tft.setTextColor(0x07FF, 0x0842);
  }
  _tft.drawString(volStr, UI_DASH_VOL_LABEL_CX, volY + 11, 2);

  const int16_t trackX = UI_DASH_VOL_TRACK_X;
  const int16_t trackY = volY + 22;
  const int16_t trackW = UI_DASH_VOL_TRACK_W;
  const int16_t trackH = 5;
  _tft.fillRoundRect(trackX, trackY, trackW, trackH, 2, 0x18C3);

  if (volume > 0) {
    int16_t fillW = (trackW * volume) / 100;
    if (fillW < 4) fillW = 4;
    uint16_t barColor = (volume > 85) ? 0xFDA0 : 0x07E0;
    _tft.fillRoundRect(trackX, trackY, fillW, trackH, 2, barColor);
  }
}

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, uint8_t volume, bool fullRedraw) {
  _lastDrawnVolume = volume;
  int16_t cardX = UI_DASH_CARD_X;
  int16_t cardY = UI_DASH_CARD_Y;
  int16_t cardW = UI_DASH_CARD_W;
  int16_t cardH = UI_DASH_CARD_H;

  if (fullRedraw) {
    // Background card
    _tft.fillRoundRect(cardX, cardY, cardW, cardH, 6, 0x0842);
    _tft.drawRoundRect(cardX, cardY, cardW, cardH, 6, 0x3186);

    // Header banner inside card
    _tft.fillRoundRect(cardX + 4, cardY + 3, cardW - 8, 16, 4, 0x18C3);
    _tft.setTextDatum(ML_DATUM);
    _tft.setTextColor(0xFFFF, 0x18C3);
    _tft.drawString("SYSTEM TELEMETRY", cardX + 10, cardY + 11, 2);
  }

  // Subsystem readiness badges on header right
  _tft.fillRect(cardX + cardW - 130, cardY + 3, 122, 16, 0x18C3);
  _tft.setTextDatum(MR_DATUM);
  if (status.battery == HEALTH_FAILED && !status.isCharging && status.batteryVoltage > 0.5f) {
    _tft.setTextColor(0xF800, 0x18C3);
    _tft.drawString("LOW BAT", cardX + cardW - 10, cardY + 11, 2);
  } else if (status.macropadReady && status.voiceReady) {
    _tft.setTextColor(0x07E0, 0x18C3);
    _tft.drawString("READY", cardX + cardW - 10, cardY + 11, 2);
  } else if (status.macropadReady) {
    _tft.setTextColor(0xFDA0, 0x18C3);
    _tft.drawString("MACROPAD", cardX + cardW - 10, cardY + 11, 2);
  } else {
    _tft.setTextColor(0xFBA0, 0x18C3);
    _tft.drawString("WAIT", cardX + cardW - 10, cardY + 11, 2);
  }
  if (fullRedraw) {
    drawDashboardPowerButton();
  }

  // Row heights: 14px per row (fits 7 telemetry rows cleanly)
  int16_t rowY = cardY + 21;
  int16_t rowH = 14;

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

  // Row 7: Power & Battery Telemetry
  rowY += rowH;
  char batBuf[36];
  if (status.batteryVoltage <= 0.5f) {
    snprintf(batBuf, sizeof(batBuf), "Detecting...");
  } else if (status.isCharging) {
    snprintf(batBuf, sizeof(batBuf), "Charging %d%% (%.2fV)", status.batteryPercent, status.batteryVoltage);
  } else {
    snprintf(batBuf, sizeof(batBuf), "%d%% (%.2fV)", status.batteryPercent, status.batteryVoltage);
  }
  drawStatusRow(cardX + 4, rowY, cardW - 8, "Battery", batBuf, status.battery, fullRedraw);

  // Update Status Bar Battery as well (differential)
  updateStatusBarBattery(status.batteryPercent, status.isCharging, status.battery);

  // Middle Section: Volume Control Bar (Rule 9: fullRedraw or differential)
  drawDashboardVolume(volume, fullRedraw);

  // Bottom Section: Environment Switcher Buttons (only on fullRedraw)
  if (fullRedraw) {
    int16_t btnY = UI_DASH_ENV_Y;
    int16_t btnH = UI_DASH_ENV_H;
    int16_t btnW = UI_DASH_ENV_W;

    bool homeActive = (currentMode == ENV_HOME);
    uint16_t homeBg = homeActive ? 0x0B4E : 0x1084;
    uint16_t homeBorder = homeActive ? 0x07E0 : 0x4228;
    _tft.fillRoundRect(UI_DASH_HOME_X, btnY, btnW, btnH, 6, homeBg);
    _tft.drawRoundRect(UI_DASH_HOME_X, btnY, btnW, btnH, 6, homeBorder);
    if (homeActive) {
      _tft.drawRoundRect(UI_DASH_HOME_X + 1, btnY + 1, btnW - 2, btnH - 2, 5, homeBorder);
    }
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(homeActive ? 0xFFFF : C_TEXT_MUTED, homeBg);
#if defined(UI_PORTRAIT)
    _tft.drawString(homeActive ? "HOME *" : "HOME", UI_DASH_HOME_X + btnW / 2, btnY + btnH / 2, 2);
#else
    _tft.drawString(homeActive ? "HOME [ ACTIVE ]" : "SWITCH TO HOME", UI_DASH_HOME_X + btnW / 2, btnY + btnH / 2, 2);
#endif

    bool workActive = (currentMode == ENV_WORK);
    uint16_t workBg = workActive ? 0x3194 : 0x1084;
    uint16_t workBorder = workActive ? 0x07E0 : 0x4228;
    _tft.fillRoundRect(UI_DASH_WORK_X, btnY, btnW, btnH, 6, workBg);
    _tft.drawRoundRect(UI_DASH_WORK_X, btnY, btnW, btnH, 6, workBorder);
    if (workActive) {
      _tft.drawRoundRect(UI_DASH_WORK_X + 1, btnY + 1, btnW - 2, btnH - 2, 5, workBorder);
    }
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(workActive ? 0xFFFF : C_TEXT_MUTED, workBg);
#if defined(UI_PORTRAIT)
    _tft.drawString(workActive ? "WORK *" : "WORK", UI_DASH_WORK_X + btnW / 2, btnY + btnH / 2, 2);
#else
    _tft.drawString(workActive ? "WORK [ ACTIVE ]" : "SWITCH TO WORK", UI_DASH_WORK_X + btnW / 2, btnY + btnH / 2, 2);
#endif
  }
}

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, bool fullRedraw) {
  drawDashboard(status, currentMode, _lastDrawnVolume, fullRedraw);
}

void MacroPadGUI::drawDashboardSwitching(const char* targetModeName) {
  int16_t cardX = UI_DASH_CARD_X;
  int16_t cardY = UI_DASH_CARD_Y;
  int16_t cardW = UI_DASH_CARD_W;
  int16_t cardH = UI_DASH_CARD_H;

  _tft.fillRoundRect(cardX, cardY, cardW, cardH, 6, 0x1084);
  _tft.drawRoundRect(cardX, cardY, cardW, cardH, 6, 0xFDA0);

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(0xFFFF, 0x1084);
  char buf[48];
  snprintf(buf, sizeof(buf), "Switching to %s Profile...", targetModeName);
  _tft.drawString(buf, SCREEN_WIDTH / 2, cardY + 32, 2);

  _tft.setTextColor(0xFDA0, 0x1084);
  _tft.drawString("Reconnecting Wi-Fi & Services...", SCREEN_WIDTH / 2, cardY + 65, 2);
}

void MacroPadGUI::drawDashboardPowerButton() {
  const uint16_t bg = 0x4800;
  const uint16_t border = 0xF800;
  const uint16_t icon = 0xFFFF;
  _tft.fillRoundRect(DASH_PWR_X, DASH_PWR_Y, DASH_PWR_W, DASH_PWR_H, 4, bg);
  _tft.drawRoundRect(DASH_PWR_X, DASH_PWR_Y, DASH_PWR_W, DASH_PWR_H, 4, border);

  const int16_t cx = DASH_PWR_X + DASH_PWR_W / 2;
  const int16_t cy = DASH_PWR_Y + DASH_PWR_H / 2;
  _tft.drawCircle(cx, cy, 6, icon);
  _tft.drawCircle(cx, cy, 5, icon);
  _tft.fillRect(cx - 2, DASH_PWR_Y + 3, 5, 5, bg);
  _tft.drawFastVLine(cx, DASH_PWR_Y + 4, 8, icon);
  _tft.drawFastVLine(cx - 1, DASH_PWR_Y + 4, 8, icon);
}

void MacroPadGUI::drawPowerConfirmDialog() {
  _tft.fillRect(0, STATUS_BAR_H, SCREEN_WIDTH, SCREEN_HEIGHT - STATUS_BAR_H, 0x0000);
  _tft.fillRoundRect(PWR_DIALOG_X, PWR_DIALOG_Y, PWR_DIALOG_W, PWR_DIALOG_H, 8, 0x1084);
  _tft.drawRoundRect(PWR_DIALOG_X, PWR_DIALOG_Y, PWR_DIALOG_W, PWR_DIALOG_H, 8, 0xF800);
  _tft.drawRoundRect(PWR_DIALOG_X + 1, PWR_DIALOG_Y + 1, PWR_DIALOG_W - 2, PWR_DIALOG_H - 2, 7, 0x8000);

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(C_TEXT_WHITE, 0x1084);
  _tft.drawString("Power off?", PWR_TITLE_CX, PWR_TITLE_CY, 4);
  _tft.setTextColor(C_TEXT_MUTED, 0x1084);
  _tft.drawString("Tap screen or BOOT to wake", PWR_TITLE_CX, PWR_HINT_CY, 2);

  _tft.fillRoundRect(PWR_CANCEL_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0x2124);
  _tft.drawRoundRect(PWR_CANCEL_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.drawString("CANCEL", PWR_CANCEL_X + PWR_BTN_W / 2, PWR_BTN_Y + PWR_BTN_H / 2, 2);

  _tft.fillRoundRect(PWR_CONFIRM_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0xA800);
  _tft.drawRoundRect(PWR_CONFIRM_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0xF800);
  _tft.setTextColor(C_TEXT_WHITE, 0xA800);
  _tft.drawString("POWER OFF", PWR_CONFIRM_X + PWR_BTN_W / 2, PWR_BTN_Y + PWR_BTN_H / 2, 2);
}

int16_t MacroPadGUI::getPowerDialogTarget(int16_t x, int16_t y) {
  if (y >= PWR_BTN_Y && y <= PWR_BTN_Y + PWR_BTN_H) {
    if (x >= PWR_CANCEL_X && x <= PWR_CANCEL_X + PWR_BTN_W) {
      return TOUCH_POWER_CANCEL;
    }
    if (x >= PWR_CONFIRM_X && x <= PWR_CONFIRM_X + PWR_BTN_W) {
      return TOUCH_POWER_CONFIRM;
    }
  }
  return -1;
}

void MacroPadGUI::drawSleepSplash() {
  _tft.fillScreen(0x0000);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(C_TEXT_MUTED, 0x0000);
  _tft.drawString("Going to sleep...", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, 2);
}

void MacroPadGUI::sleepDisplay() {
  _tft.writecommand(TFT_DISPOFF);
  delay(20);
  _tft.writecommand(0x10); // SLPIN (ILI9341 / ST7789)
  delay(120);
}

void MacroPadGUI::wakeDisplay() {
  _tft.writecommand(0x11); // SLPOUT
  delay(120);
  _tft.writecommand(0x29); // DISPON
  delay(20);
}

void MacroPadGUI::drawAll(bool isConnected, uint8_t currentPage) {
  _tft.fillScreen(C_BG);
  drawStatusBar(isConnected, currentPage, _lastDrawnBatPercent, _lastDrawnCharging, _lastDrawnBatHealth);

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
    status.battery = _lastDrawnBatHealth;
    status.batteryPercent = _lastDrawnBatPercent;
    status.isCharging = _lastDrawnCharging;

    drawDashboard(status, envManager.getMode(), _lastDrawnVolume, true); // fullRedraw = true on initial page entry
    return;
  }

  if (currentPage == PAGE_STORAGE) {
    drawStorageExplorer(true);
    return;
  }

  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    drawButton(currentPage, i, false);
  }
  if (currentPage == PAGE_VOICE) {
    drawVoiceAudioToggle(false);
    redrawVoiceCard();
  }
}

int16_t MacroPadGUI::getTouchTarget(int16_t x, int16_t y, uint8_t currentPage) {
  if (y >= 0 && y < STATUS_BAR_H) {
#if defined(UI_PORTRAIT)
    if (y < UI_SYSTEM_BAR_H) {
      if (x >= UI_NAV_PREV_HIT_X0 && x <= UI_NAV_PREV_HIT_X1) return TOUCH_PREV_PAGE;
      if (x >= UI_NAV_NEXT_HIT_X0 && x <= UI_NAV_NEXT_HIT_X1) return TOUCH_NEXT_PAGE;
    } else if (currentPage == PAGE_DASHBOARD &&
               x >= DASH_PWR_X - 6 && x <= DASH_PWR_X + DASH_PWR_W + 6) {
      return TOUCH_POWER;
    }
#else
    if (x >= UI_NAV_PREV_HIT_X0 && x <= UI_NAV_PREV_HIT_X1) return TOUCH_PREV_PAGE;
    if (x >= UI_NAV_NEXT_HIT_X0 && x <= UI_NAV_NEXT_HIT_X1) return TOUCH_NEXT_PAGE;
    if (currentPage == PAGE_DASHBOARD && x >= DASH_PWR_X - 6 && x <= DASH_PWR_X + DASH_PWR_W + 6) {
      return TOUCH_POWER;
    }
#endif
    return -1;
  }

  if (currentPage == PAGE_VOICE) {
    if (x >= UI_VOICE_AUDIO_HIT_X0 && x <= UI_VOICE_AUDIO_HIT_X1 &&
        y >= UI_VOICE_AUDIO_HIT_Y0 && y <= UI_VOICE_AUDIO_HIT_Y1) {
      return TOUCH_VOICE_AUDIO_TOGGLE;
    }

    if (!_history.empty() &&
        x >= UI_VOICE_CLR_X0 && x <= UI_VOICE_CLR_X1 &&
        y >= UI_VOICE_CLR_Y0 && y <= UI_VOICE_CLR_Y1) {
      return TOUCH_VOICE_CLEAR;
    }

    if (_chatLines.size() > UI_VOICE_VISIBLE_LINES) {
      if (x >= UI_VOICE_CTRL_X - 6 && x <= UI_VOICE_CTRL_X + UI_VOICE_CTRL_W + 6) {
        if (y >= UI_VOICE_SCROLL_UP_Y0 && y <= UI_VOICE_SCROLL_UP_Y1) {
          return TOUCH_VOICE_SCROLL_UP;
        }
        if (y >= UI_VOICE_SCROLL_DN_Y0 && y <= UI_VOICE_SCROLL_DN_Y1) {
          return TOUCH_VOICE_SCROLL_DOWN;
        }
      }
    }

    if (x >= UI_VOICE_CHAT_HIT_X0 && x <= UI_VOICE_CHAT_HIT_X1 &&
        y >= UI_VOICE_CHAT_HIT_Y0 && y <= UI_VOICE_CHAT_HIT_Y1) {
      return TOUCH_VOICE_CHAT;
    }
  }

  if (currentPage == PAGE_DASHBOARD) {
    if (y >= UI_DASH_VOL_HIT_Y0 && y <= UI_DASH_VOL_HIT_Y1) {
      if (x >= UI_DASH_VOL_DOWN_X0 && x <= UI_DASH_VOL_DOWN_X1) {
        return TOUCH_DASH_VOL_DOWN;
      }
      if (x >= UI_DASH_VOL_UP_X0 && x <= UI_DASH_VOL_UP_X1) {
        return TOUCH_DASH_VOL_UP;
      }
      if (x >= UI_DASH_VOL_MUTE_X0 && x <= UI_DASH_VOL_MUTE_X1) {
        return TOUCH_DASH_VOL_MUTE;
      }
    }
    if (y >= UI_DASH_ENV_HIT_Y0 && y <= UI_DASH_ENV_HIT_Y1) {
      if (x >= UI_DASH_HOME_HIT_X0 && x <= UI_DASH_HOME_HIT_X1) {
        return TOUCH_DASH_HOME;
      }
      if (x >= UI_DASH_WORK_HIT_X0 && x <= UI_DASH_WORK_HIT_X1) {
        return TOUCH_DASH_WORK;
      }
    }
    return -1;
  }

  if (currentPage == PAGE_STORAGE) {
    if (y >= UI_STOR_NAV_HIT_Y0 && y <= UI_STOR_NAV_HIT_Y1) {
      if (x >= UI_STOR_UP_HIT_X0 && x <= UI_STOR_UP_HIT_X1) return TOUCH_STORAGE_UP;
      if (x >= UI_STOR_REF_HIT_X0 && x <= UI_STOR_REF_HIT_X1) return TOUCH_STORAGE_REFRESH;
    }

#if defined(UI_PORTRAIT)
    if (y >= UI_STOR_SCROLL_HIT_Y0 && y <= UI_STOR_SCROLL_HIT_Y1) {
      if (x >= UI_STOR_SCROLL_UP_HIT_X0 && x <= UI_STOR_SCROLL_UP_HIT_X1) {
        return TOUCH_STORAGE_SCROLL_UP;
      }
      if (x >= UI_STOR_SCROLL_DN_HIT_X0 && x <= UI_STOR_SCROLL_DN_HIT_X1) {
        return TOUCH_STORAGE_SCROLL_DOWN;
      }
    }

    if (x >= UI_STOR_LIST_HIT_X0 && x <= UI_STOR_LIST_HIT_X1 &&
        y >= UI_STOR_LIST_HIT_Y0 && y < UI_STOR_LIST_HIT_Y1) {
      int row = (y - UI_STOR_LIST_Y) / UI_STOR_ROW_H;
      if (row >= 0 && row < UI_STOR_VISIBLE_ROWS) {
        return (int16_t)(TOUCH_STORAGE_ITEM_BASE + row);
      }
    }
#else
    if (x >= UI_STOR_SCROLL_HIT_X0 && x <= UI_STOR_SCROLL_HIT_X1 &&
        y >= UI_STOR_SCROLL_HIT_Y0 && y <= UI_STOR_SCROLL_HIT_Y1) {
      if (y < UI_STOR_SCROLL_MID_Y) return TOUCH_STORAGE_SCROLL_UP;
      else return TOUCH_STORAGE_SCROLL_DOWN;
    }

    if (x >= UI_STOR_LIST_HIT_X0 && x <= UI_STOR_LIST_HIT_X1 &&
        y >= UI_STOR_LIST_HIT_Y0 && y <= UI_STOR_LIST_HIT_Y1) {
      int row = (y - UI_STOR_LIST_Y) / UI_STOR_ROW_H;
      if (row >= 0 && row < UI_STOR_VISIBLE_ROWS) {
        return (int16_t)(TOUCH_STORAGE_ITEM_BASE + row);
      }
    }
#endif
    return -1;
  }

  uint8_t count = PROFILES[currentPage].numButtons;
  for (uint8_t i = 0; i < count; i++) {
    int16_t bx, by, bw, bh;
    getButtonRect(currentPage, i, bx, by, bw, bh);
    if (x >= bx && x <= (bx + bw) && y >= by && y <= (by + bh)) {
      return (int16_t)i;
    }
  }

  return -1;
}

// =========================================================================
// Page 7 Storage Explorer & Directory Browser Implementation
// =========================================================================

void MacroPadGUI::drawStorageExplorer(bool fullRedraw) {
  if (fullRedraw) {
    _tft.fillRect(0, STATUS_BAR_H, SCREEN_WIDTH, SCREEN_HEIGHT - STATUS_BAR_H, C_BG);
    refreshStorageExplorer();
    return;
  }

  int16_t cardX = UI_STOR_CARD_X;
  int16_t cardY = UI_STOR_CARD_Y;
  int16_t cardW = UI_STOR_CARD_W;
  int16_t cardH = UI_STOR_CARD_H;

  _tft.fillRoundRect(cardX, cardY, cardW, cardH, 5, 0x0842);
  _tft.drawRoundRect(cardX, cardY, cardW, cardH, 5, 0x3186);

  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(0x07FF, 0x0842);
  char capBuf[40];
  SDCardStatus status = getSDCardStatus();
  if (status.mounted) {
    snprintf(capBuf, sizeof(capBuf), "%s %.2f GB", status.cardTypeStr.c_str(), _storageTotalGB);
  } else {
    snprintf(capBuf, sizeof(capBuf), "SD Card Disconnected");
  }
  _tft.drawString(capBuf, cardX + 8, cardY + 11, 2);

  _tft.setTextDatum(MR_DATUM);
  char freeBuf[48];
  if (status.mounted) {
    float pctFree = (_storageTotalGB > 0) ? (_storageFreeGB / _storageTotalGB * 100.0f) : 0;
#if defined(UI_PORTRAIT)
    snprintf(freeBuf, sizeof(freeBuf), "%.1fGB free", _storageFreeGB);
#else
    snprintf(freeBuf, sizeof(freeBuf), "Free: %.2f GB (%.1f%%)", _storageFreeGB, pctFree);
#endif
    _tft.setTextColor(0x07E0, 0x0842);
  } else {
    snprintf(freeBuf, sizeof(freeBuf), "Not Mounted");
    _tft.setTextColor(0xF800, 0x0842);
  }
  _tft.drawString(freeBuf, cardX + cardW - 8, cardY + 11, 2);

  int16_t barX = cardX + 8;
  int16_t barY = cardY + 23;
  int16_t barW = cardW - 16;
  int16_t barH = 7;
  _tft.fillRoundRect(barX, barY, barW, barH, 3, 0x2124);
  _tft.drawRoundRect(barX, barY, barW, barH, 3, 0x4A69);

  if (status.mounted && _storageTotalGB > 0) {
    float usedGB = _storageTotalGB - _storageFreeGB;
    if (usedGB < 0) usedGB = 0;
    int16_t fillW = (int16_t)((usedGB / _storageTotalGB) * (barW - 2));
    if (fillW < 3 && usedGB > 0) fillW = 3;
    if (fillW > barW - 2) fillW = barW - 2;
    if (fillW > 0) {
      _tft.fillRoundRect(barX + 1, barY + 1, fillW, barH - 2, 2, 0x07FF);
    }
  }

  int16_t navY = UI_STOR_NAV_Y;
  _tft.fillRect(cardX, navY, cardW - (UI_STOR_UP_W + UI_STOR_REF_W + 8), UI_STOR_NAV_H, C_BG);
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(0xFFFF, C_BG);
  String displayPath = "Path: " + _currentStoragePath;
#if defined(UI_PORTRAIT)
  if (displayPath.length() > 14) {
    displayPath = "..." + displayPath.substring(displayPath.length() - 11);
  }
#else
  if (displayPath.length() > 22) {
    displayPath = "..." + displayPath.substring(displayPath.length() - 19);
  }
#endif
  _tft.drawString(displayPath.c_str(), cardX + 4, navY + UI_STOR_NAV_H / 2, 2);

  bool canUp = (_currentStoragePath != "/");
  uint16_t upBg = canUp ? 0x2124 : 0x1084;
  uint16_t upBorder = canUp ? 0x07E0 : 0x3186;
  uint16_t upText = canUp ? 0x07E0 : 0x632C;
  _tft.fillRoundRect(UI_STOR_UP_X, navY, UI_STOR_UP_W, UI_STOR_NAV_H, 3, upBg);
  _tft.drawRoundRect(UI_STOR_UP_X, navY, UI_STOR_UP_W, UI_STOR_NAV_H, 3, upBorder);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(upText, upBg);
  _tft.drawString(canUp ? "UP .." : "ROOT", UI_STOR_UP_X + UI_STOR_UP_W / 2, navY + UI_STOR_NAV_H / 2, 2);

  _tft.fillRoundRect(UI_STOR_REF_X, navY, UI_STOR_REF_W, UI_STOR_NAV_H, 3, 0x2124);
  _tft.drawRoundRect(UI_STOR_REF_X, navY, UI_STOR_REF_W, UI_STOR_NAV_H, 3, 0x051D);
  _tft.setTextColor(0x051D, 0x2124);
  _tft.drawString("REF", UI_STOR_REF_X + UI_STOR_REF_W / 2, navY + UI_STOR_NAV_H / 2, 2);

  drawStorageListOnly();
}

void MacroPadGUI::drawStorageListOnly() {
  int16_t listX = UI_STOR_LIST_X;
  int16_t listY = UI_STOR_LIST_Y;
  int16_t listW = UI_STOR_LIST_W;
  int16_t rowH = UI_STOR_ROW_H;
  const int visibleRows = UI_STOR_VISIBLE_ROWS;

  for (int i = 0; i < visibleRows; i++) {
    int16_t rowY = listY + i * rowH;
    int itemIdx = _storageScrollIndex + i;

    if (itemIdx < (int)_storageEntries.size()) {
      const SDFileEntry& entry = _storageEntries[itemIdx];
      uint16_t rowBg = (i % 2 == 0) ? 0x1084 : 0x0842;
      _tft.fillRoundRect(listX, rowY, listW, rowH - 2, 4, rowBg);
      _tft.drawRoundRect(listX, rowY, listW, rowH - 2, 4, 0x2124);

      if (entry.isDirectory) {
        _tft.fillRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x4220);
        _tft.drawRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0xFDA0);
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0xFDA0, 0x4220);
        _tft.drawString("DIR", listX + 23, rowY + (rowH / 2) - 1, 2);

        _tft.setTextDatum(ML_DATUM);
        _tft.setTextColor(0xFFFF, rowBg);
        String dirName = entry.name + "/";
#if defined(UI_PORTRAIT)
        if (dirName.length() > 12) dirName = dirName.substring(0, 10) + "..";
#else
        if (dirName.length() > 17) dirName = dirName.substring(0, 15) + "..";
#endif
        _tft.drawString(dirName.c_str(), listX + 46, rowY + (rowH / 2) - 1, 2);

        _tft.setTextDatum(MR_DATUM);
        _tft.setTextColor(0xFDA0, rowBg);
        _tft.drawString(">", listX + listW - 8, rowY + (rowH / 2) - 1, 4);
      } else {
        _tft.fillRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x2124);
        _tft.drawRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x632C);
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0xBDD7, 0x2124);
        _tft.drawString("FILE", listX + 23, rowY + (rowH / 2) - 1, 2);

        _tft.setTextDatum(ML_DATUM);
        _tft.setTextColor(0xFFFF, rowBg);
        String fileName = entry.name;
#if defined(UI_PORTRAIT)
        if (fileName.length() > 12) fileName = fileName.substring(0, 10) + "..";
#else
        if (fileName.length() > 17) fileName = fileName.substring(0, 15) + "..";
#endif
        _tft.drawString(fileName.c_str(), listX + 46, rowY + (rowH / 2) - 1, 2);

        _tft.setTextDatum(MR_DATUM);
        _tft.setTextColor(0x07FF, rowBg);
        _tft.drawString(entry.formattedSize.c_str(), listX + listW - 6, rowY + (rowH / 2) - 1, 2);
      }
    } else {
      _tft.fillRect(listX, rowY, listW, rowH - 2, C_BG);
      if (itemIdx == 0 && _storageEntries.empty()) {
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0x632C, C_BG);
        _tft.drawString("(Folder is empty)", listX + listW / 2, rowY + (rowH / 2) - 1, 2);
      }
    }
  }

#if defined(UI_PORTRAIT)
  int16_t btnY = UI_STOR_SCROLL_Y;
  int16_t btnH = UI_STOR_SCROLL_BAR_H;
  int16_t btnW = UI_STOR_SCROLL_BTN_W;

  bool canScrollUp = (_storageScrollIndex > 0);
  uint16_t upBg = canScrollUp ? 0x2124 : 0x1084;
  uint16_t upBorder = canScrollUp ? 0x07E0 : 0x3186;
  uint16_t upColor = canScrollUp ? 0xFFFF : 0x632C;
  _tft.fillRoundRect(UI_STOR_SCROLL_UP_X, btnY, btnW, btnH, 4, upBg);
  _tft.drawRoundRect(UI_STOR_SCROLL_UP_X, btnY, btnW, btnH, 4, upBorder);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(upColor, upBg);
  _tft.drawString("UP", UI_STOR_SCROLL_UP_X + btnW / 2, btnY + btnH / 2, 2);

  bool canScrollDown = (_storageScrollIndex + visibleRows < (int)_storageEntries.size());
  uint16_t dnBg = canScrollDown ? 0x2124 : 0x1084;
  uint16_t dnBorder = canScrollDown ? 0x07E0 : 0x3186;
  uint16_t dnColor = canScrollDown ? 0xFFFF : 0x632C;
  _tft.fillRoundRect(UI_STOR_SCROLL_DN_X, btnY, btnW, btnH, 4, dnBg);
  _tft.drawRoundRect(UI_STOR_SCROLL_DN_X, btnY, btnW, btnH, 4, dnBorder);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(dnColor, dnBg);
  _tft.drawString("DN", UI_STOR_SCROLL_DN_X + btnW / 2, btnY + btnH / 2, 2);
#else
  int16_t btnX = UI_STOR_SCROLL_X;
  int16_t btnW = UI_STOR_SCROLL_W;
  int16_t btnH = UI_STOR_SCROLL_BTN_H;
  int16_t cx = btnX + (btnW / 2);

  bool canScrollUp = (_storageScrollIndex > 0);
  uint16_t upBg = canScrollUp ? 0x2124 : 0x1084;
  uint16_t upBorder = canScrollUp ? 0x07E0 : 0x3186;
  uint16_t upColor = canScrollUp ? 0xFFFF : 0x632C;
  _tft.fillRoundRect(btnX, listY, btnW, btnH, 4, upBg);
  _tft.drawRoundRect(btnX, listY, btnW, btnH, 4, upBorder);
  int16_t cyUp = listY + (btnH / 2);
  _tft.fillTriangle(cx, cyUp - 12, cx - 12, cyUp + 4, cx + 12, cyUp + 4, upColor);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(upColor, upBg);
  _tft.drawString("UP", cx, cyUp + 18, 2);

  bool canScrollDown = (_storageScrollIndex + visibleRows < (int)_storageEntries.size());
  uint16_t dnBg = canScrollDown ? 0x2124 : 0x1084;
  uint16_t dnBorder = canScrollDown ? 0x07E0 : 0x3186;
  uint16_t dnColor = canScrollDown ? 0xFFFF : 0x632C;
  int16_t dnY = listY + btnH + 5;
  _tft.fillRoundRect(btnX, dnY, btnW, btnH, 4, dnBg);
  _tft.drawRoundRect(btnX, dnY, btnW, btnH, 4, dnBorder);
  int16_t cyDn = dnY + (btnH / 2);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(dnColor, dnBg);
  _tft.drawString("DN", cx, cyDn - 18, 2);
  _tft.fillTriangle(cx, cyDn + 12, cx - 12, cyDn - 4, cx + 12, cyDn - 4, dnColor);
#endif
}

void MacroPadGUI::highlightStorageRow(uint8_t row, bool isDirectory) {
  if (row >= UI_STOR_VISIBLE_ROWS) return;
  int16_t listX = UI_STOR_LIST_X;
  int16_t listY = UI_STOR_LIST_Y;
  int16_t listW = UI_STOR_LIST_W;
  int16_t rowH = UI_STOR_ROW_H;
  int16_t rowY = listY + row * rowH;
  uint16_t highlightColor = isDirectory ? 0xFDA0 : 0x07FF;
  _tft.drawRoundRect(listX, rowY, listW, rowH - 2, 4, highlightColor);
  _tft.drawRoundRect(listX + 1, rowY + 1, listW - 2, rowH - 4, 3, highlightColor);
}

void MacroPadGUI::scrollStorageList(int16_t delta) {
  int newIdx = _storageScrollIndex + delta;
  int maxIdx = max(0, (int)_storageEntries.size() - UI_STOR_VISIBLE_ROWS);
  newIdx = constrain(newIdx, 0, maxIdx);
  if (newIdx != _storageScrollIndex) {
    _storageScrollIndex = (int16_t)newIdx;
    drawStorageListOnly();
  }
}

void MacroPadGUI::navigateStorageTo(const String& path) {
  _currentStoragePath = path;
  _storageScrollIndex = 0;
  _storageEntries = sdCardListDirectory(_currentStoragePath);
  drawStorageExplorer(false);
}

void MacroPadGUI::navigateStorageUp() {
  if (_currentStoragePath == "/") return;

  String path = _currentStoragePath;
  if (path.length() > 1 && path.endsWith("/")) {
    path = path.substring(0, path.length() - 1);
  }

  int lastSlash = path.lastIndexOf('/');
  if (lastSlash <= 0) {
    path = "/";
  } else {
    path = path.substring(0, lastSlash);
  }

  navigateStorageTo(path);
}

void MacroPadGUI::refreshStorageExplorer() {
  sdCardGetStorageSpace(_storageTotalGB, _storageFreeGB, _storageUsedMB);
  _storageEntries = sdCardListDirectory(_currentStoragePath);
  int maxIdx = max(0, (int)_storageEntries.size() - UI_STOR_VISIBLE_ROWS);
  _storageScrollIndex = constrain(_storageScrollIndex, (int16_t)0, (int16_t)maxIdx);
  drawStorageExplorer(false);
}
