#include "environment_manager.h"

EnvironmentManager envManager;

EnvironmentManager::EnvironmentManager() 
    : _currentMode(ENV_HOME), _changeCallback(nullptr) {
    _mutex = xSemaphoreCreateMutex();
    initProfiles();
}

void EnvironmentManager::initProfiles() {
    // Populate HOME profile
    _homeProfile.mode = ENV_HOME;
#ifdef HOME_ENV_NAME
    _homeProfile.name = HOME_ENV_NAME;
#else
    _homeProfile.name = "HOME";
#endif

#ifdef HOME_WIFI_SSID
    _homeProfile.ssid = HOME_WIFI_SSID;
#elif defined(WIFI_SSID)
    _homeProfile.ssid = WIFI_SSID;
#else
    _homeProfile.ssid = "";
#endif

#ifdef HOME_WIFI_PASSWORD
    _homeProfile.password = HOME_WIFI_PASSWORD;
#elif defined(WIFI_PASSWORD)
    _homeProfile.password = WIFI_PASSWORD;
#else
    _homeProfile.password = "";
#endif

#ifdef HOME_RECEIVER_URL
    _homeProfile.receiverUrl = HOME_RECEIVER_URL;
#elif defined(HERMES_SERVER_URL)
    _homeProfile.receiverUrl = HERMES_SERVER_URL;
#else
    _homeProfile.receiverUrl = "http://192.168.0.45:8787/voice";
#endif

#ifdef HOME_STATUS_URL
    _homeProfile.statusUrl = HOME_STATUS_URL;
#else
    _homeProfile.statusUrl = "http://192.168.0.45:8787/status";
#endif
    _homeProfile.defaultReceiverUrl = _homeProfile.receiverUrl;
    _homeProfile.defaultStatusUrl = _homeProfile.statusUrl;
    _homeProfile.discoveredIp = "";

#ifdef HOME_AUTH_TOKEN
    _homeProfile.authToken = HOME_AUTH_TOKEN;
#elif defined(HERMES_AUTH_TOKEN)
    _homeProfile.authToken = HERMES_AUTH_TOKEN;
#else
    _homeProfile.authToken = "";
#endif

#ifdef HOME_BLE_HOST
    _homeProfile.expectedBleHost = HOME_BLE_HOST;
#else
    _homeProfile.expectedBleHost = "Home Desktop";
#endif

#ifdef HOME_VOICE_TIMEOUT_MS
    _homeProfile.voiceTimeoutMs = HOME_VOICE_TIMEOUT_MS;
#else
    _homeProfile.voiceTimeoutMs = 60000;
#endif

    // Populate WORK profile
    _workProfile.mode = ENV_WORK;
#ifdef WORK_ENV_NAME
    _workProfile.name = WORK_ENV_NAME;
#else
    _workProfile.name = "WORK";
#endif

#ifdef WORK_WIFI_SSID
    _workProfile.ssid = WORK_WIFI_SSID;
#else
    _workProfile.ssid = "Galaxy A55 5G BF29";
#endif

#ifdef WORK_WIFI_PASSWORD
    _workProfile.password = WORK_WIFI_PASSWORD;
#else
    _workProfile.password = "";
#endif

#ifdef WORK_RECEIVER_URL
    _workProfile.receiverUrl = WORK_RECEIVER_URL;
#else
    _workProfile.receiverUrl = "http://10.170.101.33:8787/voice";
#endif

#ifdef WORK_STATUS_URL
    _workProfile.statusUrl = WORK_STATUS_URL;
#else
    _workProfile.statusUrl = "http://10.170.101.33:8787/status";
#endif
    _workProfile.defaultReceiverUrl = _workProfile.receiverUrl;
    _workProfile.defaultStatusUrl = _workProfile.statusUrl;
    _workProfile.discoveredIp = "";

#ifdef WORK_AUTH_TOKEN
    _workProfile.authToken = WORK_AUTH_TOKEN;
#else
    _workProfile.authToken = "";
#endif

#ifdef WORK_BLE_HOST
    _workProfile.expectedBleHost = WORK_BLE_HOST;
#else
    _workProfile.expectedBleHost = "School Desktop";
#endif

#ifdef WORK_VOICE_TIMEOUT_MS
    _workProfile.voiceTimeoutMs = WORK_VOICE_TIMEOUT_MS;
#else
    _workProfile.voiceTimeoutMs = 65000;
#endif
}

void EnvironmentManager::begin() {
    _prefs.begin("env_mgr", false);
    uint8_t saved = _prefs.getUChar("mode", (uint8_t)ENV_HOME);
    if (saved > (uint8_t)ENV_WORK) {
        saved = (uint8_t)ENV_HOME;
    }
    _currentMode = (EnvironmentMode)saved;

    // Load cached dynamic IPs if available (Rule 6: Zero-reflash persistence)
    String savedWorkIp = _prefs.getString("dyn_work_ip", "");
    if (savedWorkIp.length() > 0) {
        _workProfile.discoveredIp = savedWorkIp;
        _workProfile.receiverUrl = "http://" + savedWorkIp + ":8787/voice";
        _workProfile.statusUrl = "http://" + savedWorkIp + ":8787/status";
        Serial.printf("[Env] Loaded cached WORK dynamic host IP: %s\n", savedWorkIp.c_str());
    }

    String savedHomeIp = _prefs.getString("dyn_home_ip", "");
    if (savedHomeIp.length() > 0) {
        _homeProfile.discoveredIp = savedHomeIp;
        _homeProfile.receiverUrl = "http://" + savedHomeIp + ":8787/voice";
        _homeProfile.statusUrl = "http://" + savedHomeIp + ":8787/status";
        Serial.printf("[Env] Loaded cached HOME dynamic host IP: %s\n", savedHomeIp.c_str());
    }
    _prefs.end();

    Serial.printf("[Env] Initialized. Active Environment: %s (SSID: %s, Receiver: %s)\n", 
                  getModeName(), getActiveProfile().ssid, getActiveProfile().receiverUrl.c_str());
}

EnvironmentMode EnvironmentManager::getMode() const {
    return _currentMode;
}

const char* EnvironmentManager::getModeName() const {
    return (_currentMode == ENV_WORK) ? "WORK" : "HOME";
}

const EnvironmentProfile& EnvironmentManager::getActiveProfile() const {
    return (_currentMode == ENV_WORK) ? _workProfile : _homeProfile;
}

const EnvironmentProfile& EnvironmentManager::getProfile(EnvironmentMode mode) const {
    return (mode == ENV_WORK) ? _workProfile : _homeProfile;
}

bool EnvironmentManager::setMode(EnvironmentMode mode, bool persist) {
    if (mode == _currentMode) {
        return false;
    }

    _currentMode = mode;
    Serial.printf("[Env] Switched environment to: %s (SSID: %s, Receiver: %s)\n",
                  getModeName(), getActiveProfile().ssid, getActiveProfile().receiverUrl.c_str());

    if (persist) {
        if (_prefs.begin("env_mgr", false)) {
            _prefs.putUChar("mode", (uint8_t)_currentMode);
            _prefs.end();
            Serial.println("[Env] Persisted active environment to NVS.");
        } else {
            Serial.println("[Env] Warning: Failed to open NVS for persisting mode.");
        }
    }

    if (_changeCallback) {
        _changeCallback(_currentMode);
    }
    return true;
}

bool EnvironmentManager::toggleMode() {
    EnvironmentMode next = (_currentMode == ENV_HOME) ? ENV_WORK : ENV_HOME;
    return setMode(next, true);
}

void EnvironmentManager::setDiscoveredHost(EnvironmentMode mode, const String& hostIp, uint16_t port) {
    if (hostIp.length() == 0) return;

    if (_mutex && xSemaphoreTake(_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        EnvironmentProfile& target = (mode == ENV_WORK) ? _workProfile : _homeProfile;
        
        if (target.discoveredIp == hostIp) {
            // Already set to this IP
            xSemaphoreGive(_mutex);
            return;
        }

        target.discoveredIp = hostIp;
        target.receiverUrl = "http://" + hostIp + ":" + String(port) + "/voice";
        target.statusUrl = "http://" + hostIp + ":" + String(port) + "/status";
        
        Serial.printf("[Env] Updated %s dynamic host to: %s (Receiver: %s)\n",
                      target.name, hostIp.c_str(), target.receiverUrl.c_str());

        // Persist to NVS so future reboots instantly use this discovered IP
        if (_prefs.begin("env_mgr", false)) {
            const char* key = (mode == ENV_WORK) ? "dyn_work_ip" : "dyn_home_ip";
            _prefs.putString(key, hostIp);
            _prefs.end();
            Serial.printf("[Env] Persisted dynamic IP '%s' to NVS key '%s'\n", hostIp.c_str(), key);
        }

        xSemaphoreGive(_mutex);
    }
}

String EnvironmentManager::getDiscoveredHost(EnvironmentMode mode) const {
    const EnvironmentProfile& target = (mode == ENV_WORK) ? _workProfile : _homeProfile;
    return target.discoveredIp;
}

void EnvironmentManager::resetHostToDefault(EnvironmentMode mode) {
    if (_mutex && xSemaphoreTake(_mutex, pdMS_TO_TICKS(100)) == pdTRUE) {
        EnvironmentProfile& target = (mode == ENV_WORK) ? _workProfile : _homeProfile;
        target.discoveredIp = "";
        target.receiverUrl = target.defaultReceiverUrl;
        target.statusUrl = target.defaultStatusUrl;

        if (_prefs.begin("env_mgr", false)) {
            const char* key = (mode == ENV_WORK) ? "dyn_work_ip" : "dyn_home_ip";
            _prefs.remove(key);
            _prefs.end();
        }
        xSemaphoreGive(_mutex);
    }
}

String EnvironmentManager::getReceiverUrl() const {
    return getActiveProfile().receiverUrl;
}

String EnvironmentManager::getStatusUrl() const {
    return getActiveProfile().statusUrl;
}

void EnvironmentManager::onEnvironmentChange(EnvironmentChangeCallback cb) {
    _changeCallback = cb;
}
