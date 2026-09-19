#pragma once
#include <Arduino.h>
#include <Preferences.h>

#if __has_include("wifi_config.h")
#include "wifi_config.h"
#else
#include "wifi_config.h.example"
#endif

enum EnvironmentMode {
    ENV_HOME = 0,
    ENV_WORK = 1
};

struct EnvironmentProfile {
    EnvironmentMode mode;
    const char* name;
    const char* ssid;
    const char* password;
    String receiverUrl;
    String statusUrl;
    String defaultReceiverUrl;
    String defaultStatusUrl;
    const char* authToken;
    const char* expectedBleHost;
    uint32_t voiceTimeoutMs;
    String discoveredIp;
};

class EnvironmentManager {
public:
    EnvironmentManager();
    void begin();

    EnvironmentMode getMode() const;
    const char* getModeName() const;
    const EnvironmentProfile& getActiveProfile() const;
    const EnvironmentProfile& getProfile(EnvironmentMode mode) const;

    bool setMode(EnvironmentMode mode, bool persist = true);
    bool toggleMode();

    void setDiscoveredHost(EnvironmentMode mode, const String& hostIp, uint16_t port = 8787);
    String getDiscoveredHost(EnvironmentMode mode) const;
    void resetHostToDefault(EnvironmentMode mode);

    String getReceiverUrl() const;
    String getStatusUrl() const;

    typedef void (*EnvironmentChangeCallback)(EnvironmentMode newMode);
    void onEnvironmentChange(EnvironmentChangeCallback cb);

private:
    EnvironmentMode _currentMode;
    EnvironmentProfile _homeProfile;
    EnvironmentProfile _workProfile;
    EnvironmentChangeCallback _changeCallback;
    Preferences _prefs;
    SemaphoreHandle_t _mutex;

    void initProfiles();
};

extern EnvironmentManager envManager;
