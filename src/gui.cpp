#include "gui.h"
#include "network_manager.h"

namespace {
  const int16_t DASH_PWR_X = 282;
  const int16_t DASH_PWR_Y = 36;
  const int16_t DASH_PWR_W = 24;
  const int16_t DASH_PWR_H = 18;

  const int16_t PWR_CANCEL_X = 40;
  const int16_t PWR_CONFIRM_X = 168;
  const int16_t PWR_BTN_Y = 132;
  const int16_t PWR_BTN_W = 112;
  const int16_t PWR_BTN_H = 44;
}

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
  _tft.setRotation(1); // Landscape 320x240
  _tft.fillScreen(C_BG);
}

void MacroPadGUI::setVoiceAudioEnabled(bool enabled) {
  _voiceAudioEnabled = enabled;
}

void MacroPadGUI::getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h) {
  if (pageIndex == PAGE_VOICE) {
    // Voice page: Main hold-to-talk button alongside audio toggle
    w = 222;
    h = 42;
    x = 10;
    y = 36;
    return;
  }

  uint8_t count = PROFILES[pageIndex].numButtons;

  if (count == 1) {
    // Single compact button
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

void MacroPadGUI::drawStatusBar(bool isConnected, uint8_t currentPage, uint8_t batteryPercent, bool isCharging, HealthState batHealth) {
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
  _tft.drawString(isConnected ? "CONNECTED" : "WAITING...", 20, STATUS_BAR_H / 2, 2);

  // Profile Title (Centered)
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(PROFILES[currentPage].themeColor, C_STATUS_BG);
  _tft.drawString(PROFILES[currentPage].title, 142, STATUS_BAR_H / 2, 2);

  // Battery Indicator Widget (x: 198..244)
  updateStatusBarBattery(batteryPercent, isCharging, batHealth);

  // Page switcher buttons (< [1/6] >)
  // Left arrow button
  _tft.fillRoundRect(248, 4, 24, 24, 4, 0x2124);
  _tft.drawRoundRect(248, 4, 24, 24, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.setTextDatum(MC_DATUM);
  _tft.drawString("<", 260, 16, 2);

  // Page number text
  char pageBuf[8];
  snprintf(pageBuf, sizeof(pageBuf), "%d/%d", currentPage + 1, NUM_PAGES);
  _tft.setTextColor(C_TEXT_MUTED, C_STATUS_BG);
  _tft.drawString(pageBuf, 282, 16, 2);

  // Right arrow button
  _tft.fillRoundRect(296, 4, 22, 24, 4, 0x2124);
  _tft.drawRoundRect(296, 4, 22, 24, 4, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.drawString(">", 307, 16, 2);
}

void MacroPadGUI::updateStatusBarBattery(uint8_t batteryPercent, bool isCharging, HealthState batHealth) {
  _lastDrawnBatPercent = batteryPercent;
  _lastDrawnCharging = isCharging;
  _lastDrawnBatHealth = batHealth;

  const int16_t bx = 198;
  const int16_t by = 7;
  const int16_t bw = 46;
  const int16_t bh = 18;

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
  int16_t x = 238;
  int16_t y = 36;
  int16_t w = 72;
  int16_t h = 42;

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
  // Allow 258px width for text, leaving space for scrollbar & touch buttons on right
  const int16_t textMaxW = 258;

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
  const int visibleLines = 7;
  int total = (int)_chatLines.size();
  _voiceScrollLine = max(0, total - visibleLines);
}

void MacroPadGUI::scrollToLatestResponse() {
  const int visibleLines = 7;
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
  const int visibleLines = 7;
  int total = (int)_chatLines.size();
  return (_voiceScrollLine + visibleLines < total);
}

bool MacroPadGUI::voiceChatScrollable() const {
  return (_chatLines.size() > 7);
}

void MacroPadGUI::scrollVoiceChat(int deltaLines) {
  const int visibleLines = 7;
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
  const int16_t vpX = 14;
  const int16_t vpY = 115;
  const int16_t vpW = 262; // Text area width
  const int16_t vpH = 116;
  const uint16_t bgColor = 0x0842;
  const uint8_t font = 2;
  const int16_t lineHeight = 16;
  const int visibleLines = 7;
  const int total = (int)_chatLines.size();

  // 1. Clear conversation text area (minimal differential fill - Rule 9)
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

  // 3. Render vertical scrollbar & on-screen controls if total lines exceed capacity
  const int16_t ctrlX = 280;
  const int16_t ctrlW = 26;

  if (total > visibleLines) {
    bool upActive = canScrollUp();
    bool downActive = canScrollDown();

    // Up Button [ ▲ ] (y: 116..142)
    uint16_t upBg = upActive ? 0x18F4 : 0x1084;
    uint16_t upBorder = upActive ? 0x8A3F : 0x2124;
    uint16_t upTri = upActive ? 0xFFFF : 0x632C;

    _tft.fillRoundRect(ctrlX, vpY + 1, ctrlW, 26, 4, upBg);
    _tft.drawRoundRect(ctrlX, vpY + 1, ctrlW, 26, 4, upBorder);
    _tft.fillTriangle(ctrlX + 13, vpY + 7, ctrlX + 7, vpY + 19, ctrlX + 19, vpY + 19, upTri);

    // Track & Thumb (y: 145..198, h: 54)
    const int16_t trackX = 290;
    const int16_t trackY = vpY + 30;
    const int16_t trackW = 6;
    const int16_t trackH = 54;

    _tft.fillRoundRect(trackX, trackY, trackW, trackH, 3, 0x18C3);

    int16_t thumbH = (visibleLines * trackH) / total;
    if (thumbH < 10) thumbH = 10;
    int maxScroll = total - visibleLines;
    int16_t thumbY = trackY + (_voiceScrollLine * (trackH - thumbH)) / maxScroll;

    _tft.fillRoundRect(trackX, thumbY, trackW, thumbH, 3, 0x8A3F); // Vibrant Violet

    // Down Button [ ▼ ] (y: 202..228)
    uint16_t downBg = downActive ? 0x18F4 : 0x1084;
    uint16_t downBorder = downActive ? 0x8A3F : 0x2124;
    uint16_t downTri = downActive ? 0xFFFF : 0x632C;

    _tft.fillRoundRect(ctrlX, vpY + 87, ctrlW, 26, 4, downBg);
    _tft.drawRoundRect(ctrlX, vpY + 87, ctrlW, 26, 4, downBorder);
    _tft.fillTriangle(ctrlX + 13, vpY + 107, ctrlX + 7, vpY + 95, ctrlX + 19, vpY + 95, downTri);
  } else {
    // Clear the control column if not scrollable
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
  const int16_t volY = 158;
  const int16_t volH = 34;

  if (fullRedraw) {
    // 1. Minus Button [ - ] (x: 8..52, w: 44)
    _tft.fillRoundRect(8, volY, 44, volH, 6, 0x1084);
    _tft.drawRoundRect(8, volY, 44, volH, 6, 0x4228);
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(C_TEXT_WHITE, 0x1084);
    _tft.drawString("-", 30, volY + volH / 2, 4);

    // 2. Plus Button [ + ] (x: 268..312, w: 44)
    _tft.fillRoundRect(268, volY, 44, volH, 6, 0x1084);
    _tft.drawRoundRect(268, volY, 44, volH, 6, 0x4228);
    _tft.setTextDatum(MC_DATUM);
    _tft.setTextColor(C_TEXT_WHITE, 0x1084);
    _tft.drawString("+", 290, volY + volH / 2, 4);

    // 3. Center Box Container (x: 56..264, w: 208)
    _tft.fillRoundRect(56, volY, 208, volH, 6, 0x0842);
    _tft.drawRoundRect(56, volY, 208, volH, 6, 0x3186);
  }

  // Differential overwrite of center dynamic contents (Rule 9)
  _tft.fillRect(58, volY + 2, 204, volH - 4, 0x0842);

  _tft.setTextDatum(MC_DATUM);
  char volStr[32];
  if (volume == 0) {
    snprintf(volStr, sizeof(volStr), "HERMES VOL: MUTED");
    _tft.setTextColor(0xF800, 0x0842); // Red
  } else {
    snprintf(volStr, sizeof(volStr), "HERMES VOL: %d%%", volume);
    _tft.setTextColor(0x07FF, 0x0842); // Cyan
  }
  _tft.drawString(volStr, 160, volY + 11, 2);

  // Volume Bar Track (w = 180, h = 5, x = 70, y = volY + 22)
  const int16_t trackX = 70;
  const int16_t trackY = volY + 22;
  const int16_t trackW = 180;
  const int16_t trackH = 5;
  _tft.fillRoundRect(trackX, trackY, trackW, trackH, 2, 0x18C3);

  if (volume > 0) {
    int16_t fillW = (trackW * volume) / 100;
    if (fillW < 4) fillW = 4;
    uint16_t barColor = (volume > 85) ? 0xFDA0 : 0x07E0; // Green, warning amber if high
    _tft.fillRoundRect(trackX, trackY, fillW, trackH, 2, barColor);
  }
}

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, uint8_t volume, bool fullRedraw) {
  _lastDrawnVolume = volume;
  int16_t cardX = 8;
  int16_t cardY = 34;
  int16_t cardW = 304;
  int16_t cardH = 122;

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

  // Subsystem readiness badges on header right (leave room for power button)
  _tft.fillRect(cardX + cardW - 170, cardY + 3, 114, 16, 0x18C3);
  _tft.setTextDatum(MR_DATUM);
  if (status.battery == HEALTH_FAILED && !status.isCharging && status.batteryVoltage > 0.5f) {
    _tft.setTextColor(0xF800, 0x18C3);
    _tft.drawString("LOW BAT", cardX + cardW - 32, cardY + 11, 2);
  } else if (status.macropadReady && status.voiceReady) {
    _tft.setTextColor(0x07E0, 0x18C3);
    _tft.drawString("READY", cardX + cardW - 32, cardY + 11, 2);
  } else if (status.macropadReady) {
    _tft.setTextColor(0xFDA0, 0x18C3);
    _tft.drawString("MACROPAD", cardX + cardW - 32, cardY + 11, 2);
  } else {
    _tft.setTextColor(0xFBA0, 0x18C3);
    _tft.drawString("WAIT", cardX + cardW - 32, cardY + 11, 2);
  }
  drawDashboardPowerButton();

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
    int16_t btnY = 196;
    int16_t btnH = 38;
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

void MacroPadGUI::drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, bool fullRedraw) {
  drawDashboard(status, currentMode, _lastDrawnVolume, fullRedraw);
}

void MacroPadGUI::drawDashboardSwitching(const char* targetModeName) {
  int16_t cardX = 8;
  int16_t cardY = 34;
  int16_t cardW = 304;
  int16_t cardH = 122;

  _tft.fillRoundRect(cardX, cardY, cardW, cardH, 6, 0x1084);
  _tft.drawRoundRect(cardX, cardY, cardW, cardH, 6, 0xFDA0);

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(0xFFFF, 0x1084);
  char buf[48];
  snprintf(buf, sizeof(buf), "Switching to %s Profile...", targetModeName);
  _tft.drawString(buf, 160, cardY + 32, 2);

  _tft.setTextColor(0xFDA0, 0x1084);
  _tft.drawString("Reconnecting Wi-Fi & Services...", 160, cardY + 65, 2);
}

void MacroPadGUI::drawDashboardPowerButton() {
  const uint16_t bg = 0x4800;
  const uint16_t border = 0xF800;
  const uint16_t icon = 0xFFFF;
  _tft.fillRoundRect(DASH_PWR_X, DASH_PWR_Y, DASH_PWR_W, DASH_PWR_H, 4, bg);
  _tft.drawRoundRect(DASH_PWR_X, DASH_PWR_Y, DASH_PWR_W, DASH_PWR_H, 4, border);

  const int16_t cx = DASH_PWR_X + DASH_PWR_W / 2;
  const int16_t cy = DASH_PWR_Y + DASH_PWR_H / 2 + 1;
  _tft.drawCircle(cx, cy, 5, icon);
  _tft.drawFastVLine(cx, DASH_PWR_Y + 3, 7, icon);
  _tft.drawFastVLine(cx - 1, DASH_PWR_Y + 3, 6, icon);
  _tft.drawFastVLine(cx + 1, DASH_PWR_Y + 3, 6, icon);
}

void MacroPadGUI::drawPowerConfirmDialog() {
  _tft.fillRect(0, STATUS_BAR_H, SCREEN_WIDTH, SCREEN_HEIGHT - STATUS_BAR_H, 0x0000);
  _tft.fillRoundRect(28, 52, 264, 140, 8, 0x1084);
  _tft.drawRoundRect(28, 52, 264, 140, 8, 0xF800);
  _tft.drawRoundRect(29, 53, 262, 138, 7, 0x8000);

  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(C_TEXT_WHITE, 0x1084);
  _tft.drawString("Power off?", 160, 78, 4);
  _tft.setTextColor(C_TEXT_MUTED, 0x1084);
  _tft.drawString("Tap the screen or BOOT to wake", 160, 108, 2);

  _tft.fillRoundRect(PWR_CANCEL_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0x2124);
  _tft.drawRoundRect(PWR_CANCEL_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0x632C);
  _tft.setTextColor(C_TEXT_WHITE, 0x2124);
  _tft.drawString("CANCEL", PWR_CANCEL_X + PWR_BTN_W / 2, PWR_BTN_Y + PWR_BTN_H / 2, 2);

  _tft.fillRoundRect(PWR_CONFIRM_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0xA800);
  _tft.drawRoundRect(PWR_CONFIRM_X, PWR_BTN_Y, PWR_BTN_W, PWR_BTN_H, 6, 0xF800);
  _tft.setTextColor(C_TEXT_WHITE, 0xA800);
  _tft.drawString("POWER OFF", PWR_CONFIRM_X + PWR_BTN_W / 2, PWR_BTN_Y + PWR_BTN_H / 2, 2);
}

int8_t MacroPadGUI::getPowerDialogTarget(int16_t x, int16_t y) {
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
  _tft.drawString("Going to sleep...", 160, 120, 2);
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

int8_t MacroPadGUI::getTouchTarget(int16_t x, int16_t y, uint8_t currentPage) {
  // Check Top Navigation Buttons (Status Bar: y = 0..32)
  if (y >= 0 && y <= 32) {
    if (x >= 244 && x <= 280) return TOUCH_PREV_PAGE;
    if (x >= 288 && x <= 320) return TOUCH_NEXT_PAGE;
    return -1;
  }

  // Check Page 6 Voice scroll area & controls
  if (currentPage == PAGE_VOICE) {
    // Top audio toggle button: x = 232..316, y = 34..80
    if (x >= 232 && x <= 316 && y >= 34 && y <= 80) {
      return TOUCH_VOICE_AUDIO_TOGGLE;
    }

    // 1. Check Clear Button (top right of card header)
    if (!_history.empty() && x >= 254 && x <= 312 && y >= 82 && y <= 112) {
      return TOUCH_VOICE_CLEAR;
    }

    // 2. Check Dedicated Scroll Buttons on right side if scrollable
    if (_chatLines.size() > 7) {
      // Up button area: x = 274..314, y = 114..148
      if (x >= 274 && x <= 314 && y >= 114 && y <= 148) {
        return TOUCH_VOICE_SCROLL_UP;
      }
      // Down button area: x = 274..314, y = 194..236
      if (x >= 274 && x <= 314 && y >= 194 && y <= 236) {
        return TOUCH_VOICE_SCROLL_DOWN;
      }
    }

    // 3. Main conversation card touch down (for swipe drag or tap)
    if (x >= 10 && x <= 310 && y >= 112 && y <= 234) {
      return TOUCH_VOICE_CHAT;
    }
  }

  // Check Page 1 Dashboard buttons
  if (currentPage == PAGE_DASHBOARD) {
    if (x >= 276 && x <= 308 && y >= 34 && y <= 56) {
      return TOUCH_POWER;
    }
    // Volume controls: y = 152..192
    if (y >= 152 && y <= 192) {
      if (x >= 4 && x <= 54) {
        return TOUCH_DASH_VOL_DOWN;
      }
      if (x >= 266 && x <= 316) {
        return TOUCH_DASH_VOL_UP;
      }
      if (x >= 55 && x <= 265) {
        return TOUCH_DASH_VOL_MUTE;
      }
    }
    // HOME button: left bottom area (y = 194..240)
    if (x >= 4 && x <= 158 && y >= 194 && y <= 240) {
      return TOUCH_DASH_HOME;
    }
    // WORK button: right bottom area (y = 194..240)
    if (x >= 160 && x <= 316 && y >= 194 && y <= 240) {
      return TOUCH_DASH_WORK;
    }
    return -1;
  }

  // Check Page 7 Storage Explorer touch targets
  if (currentPage == PAGE_STORAGE) {
    // 1. Navigation bar: UP button (x: 224..272) & REF button (x: 274..316), y: 70..96
    if (y >= 70 && y <= 96) {
      if (x >= 220 && x <= 272) return TOUCH_STORAGE_UP;
      if (x >= 274 && x <= 316) return TOUCH_STORAGE_REFRESH;
    }

    // 2. Scroll buttons on right side: x: 270..316, y: 96..238
    if (x >= 270 && x <= 316 && y >= 96 && y <= 238) {
      if (y < 166) return TOUCH_STORAGE_SCROLL_UP;
      else return TOUCH_STORAGE_SCROLL_DOWN;
    }

    // 3. File / Folder list items on left side: x: 8..268, y: 96..236
    if (x >= 8 && x <= 268 && y >= 96 && y <= 236) {
      int row = (y - 96) / 27;
      if (row >= 0 && row < 5) {
        return (int8_t)(TOUCH_STORAGE_ITEM_BASE + row);
      }
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

// =========================================================================
// Page 7 Storage Explorer & Directory Browser Implementation
// =========================================================================

void MacroPadGUI::drawStorageExplorer(bool fullRedraw) {
  if (fullRedraw) {
    _tft.fillRect(0, STATUS_BAR_H, SCREEN_WIDTH, SCREEN_HEIGHT - STATUS_BAR_H, C_BG);
    refreshStorageExplorer();
    return;
  }

  // 1. Storage Capacity Header Card (y: 34..70, height 36)
  int16_t cardX = 8;
  int16_t cardY = 34;
  int16_t cardW = 304;
  int16_t cardH = 36;

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
    snprintf(freeBuf, sizeof(freeBuf), "Free: %.2f GB (%.1f%%)", _storageFreeGB, pctFree);
    _tft.setTextColor(0x07E0, 0x0842);
  } else {
    snprintf(freeBuf, sizeof(freeBuf), "Not Mounted");
    _tft.setTextColor(0xF800, 0x0842);
  }
  _tft.drawString(freeBuf, cardX + cardW - 8, cardY + 11, 2);

  // Storage usage bar
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

  // 2. Breadcrumbs & Nav Bar (y: 73..93, height 20)
  int16_t navY = 73;
  _tft.fillRect(cardX, navY, cardW - 86, 20, C_BG);
  _tft.setTextDatum(ML_DATUM);
  _tft.setTextColor(0xFFFF, C_BG);
  String displayPath = "Path: " + _currentStoragePath;
  if (displayPath.length() > 22) {
    displayPath = "..." + displayPath.substring(displayPath.length() - 19);
  }
  _tft.drawString(displayPath.c_str(), cardX + 4, navY + 10, 2);

  // [ UP .. ] button (x: 226, y: navY, w: 46, h: 20)
  bool canUp = (_currentStoragePath != "/");
  uint16_t upBg = canUp ? 0x2124 : 0x1084;
  uint16_t upBorder = canUp ? 0x07E0 : 0x3186;
  uint16_t upText = canUp ? 0x07E0 : 0x632C;
  _tft.fillRoundRect(226, navY, 46, 20, 3, upBg);
  _tft.drawRoundRect(226, navY, 46, 20, 3, upBorder);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(upText, upBg);
  _tft.drawString(canUp ? "UP .." : "ROOT", 249, navY + 10, 2);

  // [ REF ] Refresh button (x: 276, y: navY, w: 36, h: 20)
  _tft.fillRoundRect(276, navY, 36, 20, 3, 0x2124);
  _tft.drawRoundRect(276, navY, 36, 20, 3, 0x051D);
  _tft.setTextColor(0x051D, 0x2124);
  _tft.drawString("REF", 294, navY + 10, 2);

  // 3. Draw the file list and scroll controls
  drawStorageListOnly();
}

void MacroPadGUI::drawStorageListOnly() {
  int16_t listX = 8;
  int16_t listY = 96;
  int16_t listW = 258;
  int16_t rowH = 27;

  // Render 5 items
  for (int i = 0; i < 5; i++) {
    int16_t rowY = listY + i * rowH;
    int itemIdx = _storageScrollIndex + i;

    if (itemIdx < (int)_storageEntries.size()) {
      const SDFileEntry& entry = _storageEntries[itemIdx];
      uint16_t rowBg = (i % 2 == 0) ? 0x1084 : 0x0842;
      _tft.fillRoundRect(listX, rowY, listW, rowH - 2, 4, rowBg);
      _tft.drawRoundRect(listX, rowY, listW, rowH - 2, 4, 0x2124);

      if (entry.isDirectory) {
        // Folder badge
        _tft.fillRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x4220); // Amber
        _tft.drawRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0xFDA0);
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0xFDA0, 0x4220);
        _tft.drawString("DIR", listX + 23, rowY + (rowH / 2) - 1, 2);

        // Name
        _tft.setTextDatum(ML_DATUM);
        _tft.setTextColor(0xFFFF, rowBg);
        String dirName = entry.name + "/";
        if (dirName.length() > 17) dirName = dirName.substring(0, 15) + "..";
        _tft.drawString(dirName.c_str(), listX + 46, rowY + (rowH / 2) - 1, 2);

        // Size badge
        _tft.setTextDatum(MR_DATUM);
        _tft.setTextColor(0xBDD7, rowBg);
        _tft.drawString("<DIR>", listX + listW - 6, rowY + (rowH / 2) - 1, 2);
      } else {
        // File badge
        _tft.fillRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x2124); // Slate
        _tft.drawRoundRect(listX + 4, rowY + 3, 38, rowH - 8, 3, 0x632C);
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0xBDD7, 0x2124);
        _tft.drawString("FILE", listX + 23, rowY + (rowH / 2) - 1, 2);

        // Name
        _tft.setTextDatum(ML_DATUM);
        _tft.setTextColor(0xFFFF, rowBg);
        String fileName = entry.name;
        if (fileName.length() > 17) fileName = fileName.substring(0, 15) + "..";
        _tft.drawString(fileName.c_str(), listX + 46, rowY + (rowH / 2) - 1, 2);

        // Size
        _tft.setTextDatum(MR_DATUM);
        _tft.setTextColor(0x07FF, rowBg);
        _tft.drawString(entry.formattedSize.c_str(), listX + listW - 6, rowY + (rowH / 2) - 1, 2);
      }
    } else {
      // Empty row
      _tft.fillRect(listX, rowY, listW, rowH - 2, C_BG);
      if (itemIdx == 0 && _storageEntries.empty()) {
        _tft.setTextDatum(MC_DATUM);
        _tft.setTextColor(0x632C, C_BG);
        _tft.drawString("(Folder is empty)", listX + listW / 2, rowY + (rowH / 2) - 1, 2);
      }
    }
  }

  // Scroll controls on right: x = 272..312 (width 40)
  int16_t btnX = 272;
  int16_t btnW = 40;
  int16_t btnH = 65;

  // Scroll UP button
  bool canScrollUp = (_storageScrollIndex > 0);
  uint16_t upBg = canScrollUp ? 0x2124 : 0x1084;
  uint16_t upBorder = canScrollUp ? 0x07E0 : 0x3186;
  uint16_t upText = canScrollUp ? 0x07E0 : 0x632C;
  _tft.fillRoundRect(btnX, listY, btnW, btnH, 4, upBg);
  _tft.drawRoundRect(btnX, listY, btnW, btnH, 4, upBorder);
  _tft.setTextDatum(MC_DATUM);
  _tft.setTextColor(upText, upBg);
  _tft.drawString("/\\", btnX + btnW / 2, listY + btnH / 2, 4);

  // Scroll DOWN button
  bool canScrollDown = (_storageScrollIndex + 5 < (int)_storageEntries.size());
  uint16_t dnBg = canScrollDown ? 0x2124 : 0x1084;
  uint16_t dnBorder = canScrollDown ? 0x07E0 : 0x3186;
  uint16_t dnText = canScrollDown ? 0x07E0 : 0x632C;
  _tft.fillRoundRect(btnX, listY + btnH + 5, btnW, btnH, 4, dnBg);
  _tft.drawRoundRect(btnX, listY + btnH + 5, btnW, btnH, 4, dnBorder);
  _tft.setTextColor(dnText, dnBg);
  _tft.drawString("\\/", btnX + btnW / 2, listY + btnH + 5 + btnH / 2, 4);
}

void MacroPadGUI::scrollStorageList(int16_t delta) {
  int newIdx = _storageScrollIndex + delta;
  int maxIdx = max(0, (int)_storageEntries.size() - 5);
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
  int maxIdx = max(0, (int)_storageEntries.size() - 5);
  _storageScrollIndex = constrain(_storageScrollIndex, (int16_t)0, (int16_t)maxIdx);
  drawStorageExplorer(false);
}
