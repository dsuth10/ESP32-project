#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "environment_manager.h"

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
    bool sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply);

    // Quick health probe to active receiver (:8787/health)
    bool checkReceiverHealth();

private:
    uint32_t _lastReconnectAttempt;
    bool _wasConnected;
    String _targetSSID;
    String _targetPassword;

    void startConnection();
};

extern NetworkManager netManager;
