#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <HTTPClient.h>

#if __has_include("wifi_config.h")
#include "wifi_config.h"
#else
#include "wifi_config.h.example"
#endif

class NetworkManager {
public:
    NetworkManager();
    void begin();
    void update();
    bool isConnected();
    String getIpAddress();
    String getConnectedSSID();

    // Sends WAV audio to Hermes receiver and fills out transcript and reply
    bool sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply);

private:
    WiFiMulti _wifiMulti;
    uint32_t _lastReconnectAttempt;
    bool _wasConnected;
    size_t _configuredNetworksCount;
};

extern NetworkManager netManager;
