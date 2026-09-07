#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "wifi_config.h"

class NetworkManager {
public:
    NetworkManager();
    void begin();
    void update();
    bool isConnected();
    String getIpAddress();

    // Sends WAV audio to Hermes receiver and fills out transcript and reply
    bool sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply);

private:
    uint32_t _lastReconnectAttempt;
    bool _wasConnected;
};

extern NetworkManager netManager;
