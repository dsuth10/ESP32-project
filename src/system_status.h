#pragma once
#include <Arduino.h>

enum HealthState {
    HEALTH_UNKNOWN = 0, // Grey
    HEALTH_READY,       // Green
    HEALTH_DEGRADED,    // Amber
    HEALTH_FAILED       // Red
};

struct DashboardStatus {
    HealthState wifi;
    String wifiSsid;
    int8_t wifiRssi;
    String ipAddress;

    HealthState internet;
    bool internetConnected;

    HealthState ble;
    bool bleConnected;
    String expectedBleHost;

    HealthState voiceHost;
    bool voiceHostReady;

    HealthState hermes;
    bool hermesReady;

    HealthState aiBackend;
    String aiBackendName;

    bool macropadReady;
    bool voiceReady;

    DashboardStatus() 
        : wifi(HEALTH_UNKNOWN), wifiSsid("Scanning..."), wifiRssi(0), ipAddress(""),
          internet(HEALTH_UNKNOWN), internetConnected(false),
          ble(HEALTH_UNKNOWN), bleConnected(false), expectedBleHost("Host PC"),
          voiceHost(HEALTH_UNKNOWN), voiceHostReady(false),
          hermes(HEALTH_UNKNOWN), hermesReady(false),
          aiBackend(HEALTH_UNKNOWN), aiBackendName("Hermes/Ollama"),
          macropadReady(false), voiceReady(false) {}
};
