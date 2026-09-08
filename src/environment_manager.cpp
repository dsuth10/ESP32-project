#include "environment_manager.h"

EnvironmentManager envManager;

EnvironmentManager::EnvironmentManager() 
    : _currentMode(ENV_HOME), _changeCallback(nullptr) {
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
    _homeProfile.voiceTimeoutMs = 25000;
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
    _prefs.end();

    Serial.printf("[Env] Initialized. Active Environment: %s (SSID: %s)\n", 
                  getModeName(), getActiveProfile().ssid);
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
                  getModeName(), getActiveProfile().ssid, getActiveProfile().receiverUrl);

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

void EnvironmentManager::onEnvironmentChange(EnvironmentChangeCallback cb) {
    _changeCallback = cb;
}
