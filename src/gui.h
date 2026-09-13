#pragma once
#include <Arduino.h>
#include <TFT_eSPI.h>
#include <vector>
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

struct ChatLine {
  String text;
  uint16_t color;
};

struct ChatMessage {
  bool isUser;
  String text;
};

class MacroPadGUI {
public:
  MacroPadGUI(TFT_eSPI& tft);
  void init();
  void drawAll(bool isConnected, uint8_t currentPage);
  void drawStatusBar(bool isConnected, uint8_t currentPage);
  void drawButton(uint8_t pageIndex, uint8_t btnIndex, bool pressed);
  void drawVoiceCard(VoiceUIState state, const char* statusMsg, const char* detailMsg);
  void redrawVoiceCard();
  void scrollVoiceChat(int deltaLines);
  void scrollToBottom();
  void scrollToTop();
  void scrollToLatestResponse();
  bool canScrollUp() const;
  bool canScrollDown() const;
  bool voiceChatScrollable() const;
  void addVoiceTurn(const String& transcript, const String& reply);
  void clearConversation();
  void drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, uint8_t volume, bool fullRedraw = true);
  void drawDashboard(const DashboardStatus& status, EnvironmentMode currentMode, bool fullRedraw = true);
  void drawDashboardVolume(uint8_t volume, bool fullRedraw = false);
  void drawDashboardSwitching(const char* targetModeName);
  void drawVoiceAudioToggle(bool pressed = false);
  void setVoiceAudioEnabled(bool enabled);
  bool isVoiceAudioEnabled() const { return _voiceAudioEnabled; }
  int8_t getTouchTarget(int16_t x, int16_t y, uint8_t currentPage);

private:
  TFT_eSPI& _tft;

  // Page 5 Voice Assistant Chat & Audio State
  VoiceUIState _voiceState;
  String _voiceStatusMsg;
  String _voiceDetailMsg;
  int _voiceScrollLine;
  bool _voiceAudioEnabled;
  uint8_t _lastDrawnVolume;
  std::vector<ChatMessage> _history;
  std::vector<ChatLine> _chatLines;

  void getButtonRect(uint8_t pageIndex, uint8_t btnIndex, int16_t& x, int16_t& y, int16_t& w, int16_t& h);
  void drawStatusRow(int16_t x, int16_t y, int16_t w, const char* label, const char* value, HealthState health, bool fullRedraw = true);
  void renderVoiceChatViewport();
  void rebuildChatLines();
};
