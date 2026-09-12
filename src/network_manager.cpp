#include "network_manager.h"
#include "audio_recorder.h"
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

static bool extractJsonBool(const String& json, const String& key, bool defaultVal = false) {
    String searchKey = "\"" + key + "\":";
    int start = json.indexOf(searchKey);
    if (start == -1) {
        searchKey = "\"" + key + "\": ";
        start = json.indexOf(searchKey);
        if (start == -1) return defaultVal;
    }
    start += searchKey.length();
    while (start < (int)json.length() && json.charAt(start) == ' ') start++;
    if (json.startsWith("true", start)) return true;
    if (json.startsWith("false", start)) return false;
    return defaultVal;
}

static String extractJsonObject(const String& json, const String& objKey) {
    String searchKey = "\"" + objKey + "\":";
    int start = json.indexOf(searchKey);
    if (start == -1) {
        searchKey = "\"" + objKey + "\": ";
        start = json.indexOf(searchKey);
        if (start == -1) return "";
    }
    int braceStart = json.indexOf('{', start);
    if (braceStart == -1) return "";
    int depth = 0;
    for (int i = braceStart; i < (int)json.length(); i++) {
        if (json.charAt(i) == '{') depth++;
        else if (json.charAt(i) == '}') {
            depth--;
            if (depth == 0) {
                return json.substring(braceStart, i + 1);
            }
        }
    }
    return "";
}

NetworkManager::NetworkManager() 
    : _lastReconnectAttempt(0), _wasConnected(false),
      _lastInternetCheck(0), _lastInternetState(false) {}

void NetworkManager::begin() {
    WiFi.onEvent([](WiFiEvent_t event, WiFiEventInfo_t info) {
        switch (event) {
            case ARDUINO_EVENT_WIFI_STA_START:
                Serial.println("[WiFi Event] STA Started");
                break;
            case ARDUINO_EVENT_WIFI_STA_CONNECTED:
                Serial.println("[WiFi Event] Associated with AP successfully");
                break;
            case ARDUINO_EVENT_WIFI_STA_GOT_IP:
                Serial.printf("[WiFi Event] Obtained IP: %s\n", 
                              IPAddress(info.got_ip.ip_info.ip.addr).toString().c_str());
                break;
            case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
                Serial.printf("[WiFi Event] Disconnected from AP. Reason code: %d\n", 
                              info.wifi_sta_disconnected.reason);
                break;
            default:
                break;
        }
    });

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true); // Allow ESP-IDF background auto-reconnect to active SSID

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
    WiFi.disconnect(false, false);
    delay(50);
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
        // Give association, 4-way handshake, and Telstra band-steering 25 seconds before retrying
        if (now - _lastReconnectAttempt > 25000) {
            _lastReconnectAttempt = now;
            Serial.printf("[WiFi] Retrying connection to '%s' (status=%d)...\n", 
                          _targetSSID.c_str(), (int)WiFi.status());
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

bool NetworkManager::sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply, bool& outAudioAvailable, String& outAudioUrl) {
    outAudioAvailable = false;
    outAudioUrl = "";

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
        outAudioAvailable = extractJsonBool(response, "audio_available", false);
        outAudioUrl = extractJsonField(response, "audio_url");
        if (outAudioAvailable && outAudioUrl.length() == 0) {
            outAudioUrl = "/voice/audio";
        }

        if (outTranscript.length() == 0) outTranscript = "Audio Processed";
        if (outReply.length() == 0) outReply = "Received by Hermes";

        int serverMs = extractJsonInt(response, "server_ms");
        int whisperMs = extractJsonInt(response, "whisper_ms");
        int hermesMs = extractJsonInt(response, "hermes_ms");
        int ttsMs = extractJsonInt(response, "tts_ms");
        if (serverMs > 0) {
            int netTransit = (int)httpDuration - serverMs;
            Serial.printf("[PERF] Roundtrip: %u ms | Server: %d ms (Whisper: %d ms, Hermes: %d ms, TTS: %d ms) | Audio: %s\n",
                          (unsigned int)httpDuration, serverMs, whisperMs, hermesMs, ttsMs > 0 ? ttsMs : 0, outAudioAvailable ? "YES" : "NO");
        }

        Serial.printf("[STT] \"%s\"\n", outTranscript.c_str());
        Serial.printf("[REPLY] \"%s\"\n", outReply.c_str());

        http.end();
        return true;
    } else {
        Serial.printf("[HTTP] POST failed, error code: %d (%s) after %u ms\n", 
                      httpCode, http.errorToString(httpCode).c_str(), (unsigned int)httpDuration);
        String serverErrMsg = "";
        if (httpCode > 0) {
            serverErrMsg = http.getString();
            Serial.printf("[HTTP] Server error response: %s\n", serverErrMsg.c_str());
        }

        if (httpCode == HTTPC_ERROR_READ_TIMEOUT) {
            outTranscript = "Response Timed Out";
            outReply = "Server took too long to answer (> " + String(timeoutMs / 1000) + "s)";
        } else if (httpCode == HTTPC_ERROR_CONNECTION_REFUSED) {
            outTranscript = "Connection Refused";
            outReply = "Receiver not running on host";
        } else if (httpCode == 429) {
            outTranscript = "Receiver Busy";
            outReply = "Another voice task is processing";
        } else if (httpCode == 401) {
            outTranscript = "Auth Failed (401)";
            outReply = "Check Bearer token in config";
        } else if (httpCode == 500) {
            outTranscript = "Server Error (500)";
            String cleanMsg = extractJsonField(serverErrMsg, "message");
            outReply = cleanMsg.length() > 0 ? cleanMsg : "Receiver exception occurred";
        } else if (httpCode > 0) {
            outTranscript = "HTTP Error " + String(httpCode);
            outReply = http.errorToString(httpCode);
        } else {
            outTranscript = "Network Error (" + String(httpCode) + ")";
            outReply = http.errorToString(httpCode);
        }

        http.end();
        return false;
    }
}

bool NetworkManager::sendVoiceAudio(const uint8_t* wavData, size_t wavSize, String& outTranscript, String& outReply) {
    bool dummyAudio = false;
    String dummyUrl = "";
    return sendVoiceAudio(wavData, wavSize, outTranscript, outReply, dummyAudio, dummyUrl);
}

bool NetworkManager::playVoiceAudioReply(const String& audioUrl, std::function<bool()> shouldAbort) {
    if (!isConnected()) return false;

    const EnvironmentProfile& prof = envManager.getActiveProfile();
    const char* authToken = prof.authToken;

    // Construct full URL from active profile receiver URL
    String fullUrl = prof.receiverUrl;
    if (audioUrl.startsWith("http://") || audioUrl.startsWith("https://")) {
        fullUrl = audioUrl;
    } else {
        int idx = fullUrl.indexOf("/voice");
        if (idx != -1) {
            fullUrl = fullUrl.substring(0, idx) + (audioUrl.startsWith("/") ? audioUrl : "/" + audioUrl);
        } else {
            fullUrl = fullUrl + (audioUrl.startsWith("/") ? audioUrl : "/" + audioUrl);
        }
    }

    Serial.printf("[HTTP] Fetching voice audio stream from: %s\n", fullUrl.c_str());

    HTTPClient http;
    WiFiClientSecure secureClient;
    secureClient.setInsecure();

    if (fullUrl.startsWith("https://")) {
        http.begin(secureClient, fullUrl);
    } else {
        http.begin(fullUrl);
    }

    if (authToken && strlen(authToken) > 0) {
        http.addHeader("Authorization", "Bearer " + String(authToken));
    }
    http.setTimeout(25000);

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK && httpCode != 200) {
        Serial.printf("[HTTP] Failed to fetch audio stream: %d (%s)\n", httpCode, http.errorToString(httpCode).c_str());
        http.end();
        return false;
    }

    WiFiClient* stream = http.getStreamPtr();
    size_t contentLen = http.getSize();
    bool played = recorder.playAudioStream(*stream, contentLen, shouldAbort);
    http.end();
    return played;
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

bool NetworkManager::checkInternet() {
    if (!isConnected()) {
        _lastInternetState = false;
        return false;
    }
    uint32_t now = millis();
    if (now - _lastInternetCheck < 30000 && _lastInternetCheck != 0) {
        return _lastInternetState;
    }
    _lastInternetCheck = now;

    // Use DNS resolution of a fast public resolver
    IPAddress result;
    int err = WiFi.hostByName("one.one.one.one", result);
    if (err == 1) {
        _lastInternetState = true;
        return true;
    }
    err = WiFi.hostByName("google.com", result);
    _lastInternetState = (err == 1);
    return _lastInternetState;
}

bool NetworkManager::fetchCompositeStatus(DashboardStatus& outStatus) {
    // Populate base network fields
    bool connected = isConnected();
    outStatus.wifi = connected ? HEALTH_READY : HEALTH_FAILED;
    outStatus.wifiSsid = getConnectedSSID();
    outStatus.wifiRssi = getRSSI();
    outStatus.ipAddress = getIpAddress();

    // Check Internet (Phase 13)
    bool internetOk = checkInternet();
    outStatus.internet = internetOk ? HEALTH_READY : (connected ? HEALTH_DEGRADED : HEALTH_FAILED);
    outStatus.internetConnected = internetOk;

    if (!connected) {
        outStatus.voiceHost = HEALTH_UNKNOWN;
        outStatus.voiceHostReady = false;
        outStatus.hermes = HEALTH_UNKNOWN;
        outStatus.hermesReady = false;
        outStatus.aiBackend = HEALTH_UNKNOWN;
        outStatus.aiBackendName = "Offline";
        outStatus.voiceReady = false;
        return false;
    }

    const EnvironmentProfile& prof = envManager.getActiveProfile();
    const char* statusUrl = prof.statusUrl;
    const char* authToken = prof.authToken;

    HTTPClient http;
    WiFiClientSecure secureClient;
    secureClient.setInsecure();

    if (String(statusUrl).startsWith("https://")) {
        http.begin(secureClient, statusUrl);
    } else {
        http.begin(statusUrl);
    }

    http.addHeader("Connection", "close");
    if (authToken && strlen(authToken) > 0) {
        http.addHeader("Authorization", "Bearer " + String(authToken));
    }

    http.setTimeout(3000); // 3.0s timeout (runs safely in Core 0 FreeRTOS worker)
    int httpCode = http.GET();

    if (httpCode == 200) {
        String json = http.getString();
        http.end();

        // 1. Receiver
        String receiverObj = extractJsonObject(json, "receiver");
        bool recvReady = extractJsonBool(receiverObj, "ready", false);
        if (!recvReady && receiverObj.length() == 0) {
            // Server returned HTTP 200 without a nested receiver block: receiver service is alive
            String statusStr = extractJsonField(json, "status");
            recvReady = (statusStr == "ok" || statusStr == "degraded" || statusStr.length() == 0);
        }
        outStatus.voiceHost = recvReady ? HEALTH_READY : HEALTH_FAILED;
        outStatus.voiceHostReady = recvReady;

        // 2. Hermes Gateway
        String hermesObj = extractJsonObject(json, "hermes");
        bool hermesLive = extractJsonBool(hermesObj, "live", false);
        bool hermesReady = extractJsonBool(hermesObj, "ready", false);
        if (hermesReady) {
            outStatus.hermes = HEALTH_READY;
            outStatus.hermesReady = true;
        } else if (hermesLive) {
            outStatus.hermes = HEALTH_DEGRADED;
            outStatus.hermesReady = false;
        } else {
            outStatus.hermes = HEALTH_FAILED;
            outStatus.hermesReady = false;
        }

        // 3. AI Backend
        String backendObj = extractJsonObject(json, "backend");
        bool backendReady = extractJsonBool(backendObj, "ready", false);
        bool backendWarm = extractJsonBool(backendObj, "warm", false);
        String backendType = extractJsonField(backendObj, "type");

        if (backendReady && backendType == "ollama") {
            outStatus.aiBackend = HEALTH_READY;
            outStatus.aiBackendName = backendWarm ? "Ollama • Warm" : "Ollama • Cold";
        } else if (hermesReady) {
            // At Home: Hermes Gateway acts directly as the orchestrating AI agent
            outStatus.aiBackend = HEALTH_READY;
            outStatus.aiBackendName = "Hermes Gateway";
        } else if (backendReady) {
            outStatus.aiBackend = HEALTH_READY;
            outStatus.aiBackendName = "Ollama Fallback";
        } else {
            outStatus.aiBackend = (envManager.getMode() == ENV_WORK) ? HEALTH_FAILED : HEALTH_UNKNOWN;
            outStatus.aiBackendName = (envManager.getMode() == ENV_WORK) ? "Ollama Offline" : "Hermes Offline";
        }

        // Voice subsystem readiness:
        // Ready if Wi-Fi + Voice Host + (Hermes or Ollama) are functional
        outStatus.voiceReady = outStatus.voiceHostReady && (outStatus.hermesReady || backendReady);

        Serial.printf("[Telemetry] VoiceHost: %s | Hermes: %s | AI: %s | VoiceReady: %s\n",
                      outStatus.voiceHost == HEALTH_READY ? "Online" : "Failed",
                      outStatus.hermes == HEALTH_READY ? "Ready" : "Degraded/Failed",
                      outStatus.aiBackendName.c_str(),
                      outStatus.voiceReady ? "YES" : "NO");
        return true;
    } else {
        http.end();
        Serial.printf("[Telemetry] Status probe failed: HTTP %d\n", httpCode);
        outStatus.voiceHost = HEALTH_FAILED;
        outStatus.voiceHostReady = false;
        outStatus.hermes = HEALTH_UNKNOWN;
        outStatus.hermesReady = false;
        outStatus.aiBackend = HEALTH_UNKNOWN;
        outStatus.aiBackendName = (httpCode == 401) ? "Auth Failed (401)" : "Unreachable";
        outStatus.voiceReady = false;
        return false;
    }
}
