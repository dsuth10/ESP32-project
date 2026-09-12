#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <functional>
#include "environment_manager.h"
#include "system_status.h"

class NetworkManager {
public:
    NetworkManager();
    void begin();
    void update();
    bool isConnected();
    String getIpAddress();
    String getConnectedSSID();
    int8_t getRSSI();

    // Strict environment profile application (Phase 6)
    void applyEnvironment(EnvironmentMode mode);

    // Sends WAV audio to Hermes receiver for active environment and fills out transcript and reply
    bool sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply, bool& outAudioAvailable, String& outAudioUrl);
    bool sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply);

    // Streams synthesized voice audio from receiver (:8787/voice/audio) directly into I2S speaker
    bool playVoiceAudioReply(const String& audioUrl = "/voice/audio", std::function<bool()> shouldAbort = nullptr);

    // Quick health probe to active receiver (:8787/health)
    bool checkReceiverHealth();

    // Deep composite status probe to active receiver (:8787/status) with Bearer token (Phases 3, 7, 20)
    bool fetchCompositeStatus(DashboardStatus& outStatus);

    // Lightweight periodic Internet connectivity check (Phase 13)
    bool checkInternet();

private:
    uint32_t _lastReconnectAttempt;
    bool _wasConnected;
    String _targetSSID;
    String _targetPassword;

    uint32_t _lastInternetCheck;
    bool _lastInternetState;

    void startConnection();
};

extern NetworkManager netManager;
