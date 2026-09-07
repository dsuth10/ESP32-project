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

NetworkManager::NetworkManager() : _lastReconnectAttempt(0), _wasConnected(false) {}

void NetworkManager::begin() {
    if (String(WIFI_SSID) == "YOUR_WIFI_SSID" || strlen(WIFI_SSID) == 0) {
        Serial.println("[WiFi] No SSID configured in wifi_config.h. Wi-Fi idle.");
        return;
    }

    Serial.printf("[WiFi] Connecting to SSID: %s ...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void NetworkManager::update() {
    if (String(WIFI_SSID) == "YOUR_WIFI_SSID" || strlen(WIFI_SSID) == 0) return;

    bool connected = (WiFi.status() == WL_CONNECTED);
    if (connected && !_wasConnected) {
        _wasConnected = true;
        Serial.printf("[WiFi] >>> CONNECTED! IP: %s, RSSI: %d dBm <<<\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else if (!connected && _wasConnected) {
        _wasConnected = false;
        Serial.println("[WiFi] <<< DISCONNECTED from Wi-Fi <<<");
    }

    if (!connected) {
        uint32_t now = millis();
        if (now - _lastReconnectAttempt > 10000) {
            _lastReconnectAttempt = now;
            Serial.println("[WiFi] Reconnecting...");
            WiFi.disconnect();
            WiFi.reconnect();
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

bool NetworkManager::sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply) {
    if (!isConnected()) {
        Serial.println("[HTTP] Cannot send voice: Wi-Fi not connected!");
        outTranscript = "Error: Wi-Fi Disconnected";
        outReply = "Please check wifi_config.h";
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
    http.addHeader("Authorization", "Bearer " + String(HERMES_AUTH_TOKEN));
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
