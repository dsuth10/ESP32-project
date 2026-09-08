#include "network_manager.h"
#include <WiFiClientSecure.h>
#include <esp_task_wdt.h>

NetworkManager netManager;

static String extractJsonField(const String& json, const String& key) {
    String searchKey = "\"" + key + "\":\"";
    int start = json.indexOf(searchKey);
    if (start == -1) {
        searchKey = "\"" + key + "\": \"";
        start = json.indexOf(searchKey);
        if (start == -1) return "";
    }
    start += searchKey.length();
    
    int end = start;
    while (end < (int)json.length()) {
        int nextQuote = json.indexOf("\"", end);
        if (nextQuote == -1) return "";
        if (nextQuote > 0 && json.charAt(nextQuote - 1) == '\\') {
            end = nextQuote + 1; // escaped quote, continue scanning
        } else {
            end = nextQuote;
            break;
        }
    }
    String val = json.substring(start, end);
    val.replace("\\\"", "\"");
    val.replace("\\n", " ");
    return val;
}

NetworkManager::NetworkManager() : _lastReconnectAttempt(0), _wasConnected(false), _configuredNetworksCount(0) {}

void NetworkManager::begin() {
    WiFi.mode(WIFI_STA);
    _configuredNetworksCount = 0;

#if defined(USE_WIFI_MULTI) && USE_WIFI_MULTI
    size_t count = sizeof(WIFI_NETWORKS) / sizeof(WIFI_NETWORKS[0]);
    for (size_t i = 0; i < count; i++) {
        const char* ssid = WIFI_NETWORKS[i].ssid;
        const char* pass = WIFI_NETWORKS[i].password;
        if (ssid && strlen(ssid) > 0 && 
            strcmp(ssid, "YOUR_WIFI_SSID") != 0 && 
            strcmp(ssid, "YOUR_HOME_SSID") != 0) {
            _wifiMulti.addAP(ssid, pass);
            _configuredNetworksCount++;
            Serial.printf("[WiFi] Registered network: %s\n", ssid);
        }
    }
#endif

#if defined(WIFI_SSID)
    if (_configuredNetworksCount == 0 && String(WIFI_SSID) != "YOUR_WIFI_SSID" && strlen(WIFI_SSID) > 0) {
        _wifiMulti.addAP(WIFI_SSID, WIFI_PASSWORD);
        _configuredNetworksCount++;
        Serial.printf("[WiFi] Registered legacy network: %s\n", WIFI_SSID);
    }
#endif

    if (_configuredNetworksCount == 0) {
        Serial.println("[WiFi] No valid networks configured in wifi_config.h. Wi-Fi idle.");
        return;
    }

    Serial.printf("[WiFi] Searching & connecting across %u registered network(s)...\n", (unsigned int)_configuredNetworksCount);
    // Initial connection attempt with timeout
    if (_wifiMulti.run(5000) == WL_CONNECTED) {
        _wasConnected = true;
        Serial.printf("[WiFi] >>> CONNECTED to '%s'! IP: %s, RSSI: %d dBm <<<\n",
                      WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
        Serial.println("[WiFi] Initial connection pending. Background scan will retry.");
    }
}

void NetworkManager::update() {
    if (_configuredNetworksCount == 0) return;

    bool connected = (WiFi.status() == WL_CONNECTED);
    if (connected && !_wasConnected) {
        _wasConnected = true;
        Serial.printf("[WiFi] >>> CONNECTED to '%s'! IP: %s, RSSI: %d dBm <<<\n",
                      WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else if (!connected && _wasConnected) {
        _wasConnected = false;
        Serial.println("[WiFi] <<< DISCONNECTED from Wi-Fi <<<");
    }

    if (!connected) {
        uint32_t now = millis();
        if (now - _lastReconnectAttempt > 10000) {
            _lastReconnectAttempt = now;
            Serial.println("[WiFi] Scanning & reconnecting via WiFiMulti...");
            _wifiMulti.run(3000);
        }
    }
}

bool NetworkManager::isConnected() {
    return (WiFi.status() == WL_CONNECTED);
}

String NetworkManager::getIpAddress() {
    if (isConnected()) {
        return WiFi.localIP().toString();
    }
    return "Disconnected";
}

String NetworkManager::getConnectedSSID() {
    if (isConnected()) {
        return WiFi.SSID();
    }
    return "Disconnected";
}

bool NetworkManager::sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply) {
    if (!isConnected()) {
        Serial.println("[HTTP] Cannot send voice: Wi-Fi not connected!");
        outTranscript = "Error: Wi-Fi Disconnected";
        outReply = "Check Wi-Fi & Hotspot (2.4GHz)";
        return false;
    }

    if (!wavData || wavSize < 44) {
        Serial.println("[HTTP] Invalid WAV data");
        return false;
    }

    HTTPClient http;
    WiFiClientSecure secureClient;
    secureClient.setInsecure(); // Allow TLS without embedded CA bundle

    if (String(HERMES_SERVER_URL).startsWith("https://")) {
        http.begin(secureClient, HERMES_SERVER_URL);
    } else {
        http.begin(HERMES_SERVER_URL);
    }

    http.addHeader("Content-Type", "audio/wav");
    http.addHeader("Connection", "close");
#ifdef HERMES_AUTH_TOKEN
    if (strlen(HERMES_AUTH_TOKEN) > 0) {
        http.addHeader("Authorization", "Bearer " + String(HERMES_AUTH_TOKEN));
    }
#endif
    http.setTimeout(65000); // 65s max uint16_t timeout for transit + Whisper STT + Hermes LLM reasoning

    Serial.printf("[HTTP] POSTing %u bytes to %s ...\n", (unsigned int)wavSize, HERMES_SERVER_URL);

    uint32_t httpStart = millis();
    int httpCode = http.POST((uint8_t*)wavData, wavSize);
    uint32_t httpDuration = millis() - httpStart;

    if (httpCode == HTTP_CODE_OK || httpCode == 200) {
        String response = http.getString();
        Serial.printf("[HTTP] 200 OK | %u ms | Response: %s\n", (unsigned int)httpDuration, response.c_str());

        outTranscript = extractJsonField(response, "transcript");
        outReply = extractJsonField(response, "reply");

        if (outTranscript.length() == 0) outTranscript = "Audio Processed";
        if (outReply.length() == 0) outReply = "Received by Hermes";

        Serial.printf("[STT] \"%s\"\n", outTranscript.c_str());
        Serial.printf("[REPLY] \"%s\"\n", outReply.c_str());

        http.end();
        return true;
    } else {
        Serial.printf("[HTTP] POST failed, error code: %d (%s) after %u ms\n", 
                      httpCode, http.errorToString(httpCode).c_str(), (unsigned int)httpDuration);
        if (httpCode > 0) {
            String errResponse = http.getString();
            Serial.printf("[HTTP] Server error response: %s\n", errResponse.c_str());
        }
        outTranscript = "HTTP Request Failed";
        outReply = String("Code: ") + httpCode;
        http.end();
        return false;
    }
}
