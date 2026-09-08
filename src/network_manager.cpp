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

static int extractJsonInt(const String& json, const String& key) {
    String searchKey = "\"" + key + "\":";
    int start = json.indexOf(searchKey);
    if (start == -1) {
        searchKey = "\"" + key + "\": ";
        start = json.indexOf(searchKey);
        if (start == -1) return -1;
    }
    start += searchKey.length();
    while (start < (int)json.length() && json.charAt(start) == ' ') start++;
    int end = start;
    while (end < (int)json.length() && (isDigit(json.charAt(end)) || json.charAt(end) == '-')) end++;
    if (end > start) {
        return json.substring(start, end).toInt();
    }
    return -1;
}

NetworkManager::NetworkManager() : _lastReconnectAttempt(0), _wasConnected(false) {}

void NetworkManager::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(false); // Strict profile isolation: do not roam to other environments

    const EnvironmentProfile& prof = envManager.getActiveProfile();
    _targetSSID = prof.ssid;
    _targetPassword = prof.password;

    Serial.printf("[WiFi] Initializing for environment: %s | Target SSID: %s\n", 
                  prof.name, _targetSSID.c_str());

    startConnection();
}

void NetworkManager::startConnection() {
    if (_targetSSID.length() == 0 || 
        _targetSSID == "YOUR_WIFI_SSID" || 
        _targetSSID == "YOUR_HOME_SSID") {
        Serial.println("[WiFi] No valid SSID configured for this environment.");
        return;
    }

    Serial.printf("[WiFi] Connecting strictly to '%s' ...\n", _targetSSID.c_str());
    WiFi.disconnect(true);
    delay(100);
    WiFi.begin(_targetSSID.c_str(), _targetPassword.c_str());
    _lastReconnectAttempt = millis();
    _wasConnected = false;
}

void NetworkManager::applyEnvironment(EnvironmentMode mode) {
    const EnvironmentProfile& prof = envManager.getProfile(mode);
    _targetSSID = prof.ssid;
    _targetPassword = prof.password;

    Serial.printf("[WiFi] Applying environment %s -> Target SSID: '%s'\n", 
                  prof.name, _targetSSID.c_str());
    startConnection();
}

void NetworkManager::update() {
    if (_targetSSID.length() == 0) return;

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
            Serial.printf("[WiFi] Retrying connection to '%s'...\n", _targetSSID.c_str());
            WiFi.disconnect();
            WiFi.begin(_targetSSID.c_str(), _targetPassword.c_str());
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

int8_t NetworkManager::getRSSI() {
    if (isConnected()) {
        return WiFi.RSSI();
    }
    return 0;
}

bool NetworkManager::sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply) {
    if (!isConnected()) {
        Serial.println("[HTTP] Cannot send voice: Wi-Fi not connected!");
        outTranscript = "Error: Wi-Fi Disconnected";
        outReply = "Check Wi-Fi connection";
        return false;
    }

    if (!wavData || wavSize < 44) {
        Serial.println("[HTTP] Invalid WAV data");
        return false;
    }

    const EnvironmentProfile& prof = envManager.getActiveProfile();
    const char* serverUrl = prof.receiverUrl;
    const char* authToken = prof.authToken;
    uint32_t timeoutMs = prof.voiceTimeoutMs;

    HTTPClient http;
    WiFiClientSecure secureClient;
    secureClient.setInsecure(); // Allow TLS without embedded CA bundle if https

    if (String(serverUrl).startsWith("https://")) {
        http.begin(secureClient, serverUrl);
    } else {
        http.begin(serverUrl);
    }

    http.addHeader("Content-Type", "audio/wav");
    http.addHeader("Connection", "close");

    if (authToken && strlen(authToken) > 0) {
        http.addHeader("Authorization", "Bearer " + String(authToken));
    }

    http.setTimeout(timeoutMs);

    Serial.printf("[HTTP] POSTing %u bytes to [%s] %s (timeout: %u ms)...\n", 
                  (unsigned int)wavSize, prof.name, serverUrl, (unsigned int)timeoutMs);

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

        int serverMs = extractJsonInt(response, "server_ms");
        int whisperMs = extractJsonInt(response, "whisper_ms");
        int hermesMs = extractJsonInt(response, "hermes_ms");
        if (serverMs > 0) {
            int netTransit = (int)httpDuration - serverMs;
            Serial.printf("[PERF] Roundtrip: %u ms | Server: %d ms (Whisper: %d ms, Hermes: %d ms) | Network: %d ms\n",
                          (unsigned int)httpDuration, serverMs, whisperMs, hermesMs, netTransit > 0 ? netTransit : 0);
        }

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

bool NetworkManager::checkReceiverHealth() {
    if (!isConnected()) return false;

    const EnvironmentProfile& prof = envManager.getActiveProfile();
    String healthUrl = prof.statusUrl;
    if (healthUrl.endsWith("/status")) {
        healthUrl.replace("/status", "/health");
    } else if (healthUrl.endsWith("/voice")) {
        healthUrl.replace("/voice", "/health");
    }

    HTTPClient http;
    WiFiClientSecure secureClient;
    secureClient.setInsecure();

    if (healthUrl.startsWith("https://")) {
        http.begin(secureClient, healthUrl);
    } else {
        http.begin(healthUrl);
    }

    http.setTimeout(2000);
    int code = http.GET();
    http.end();
    return (code == 200);
}
