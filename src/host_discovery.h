#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include "environment_manager.h"

#ifndef DISCOVERY_UDP_PORT
#define DISCOVERY_UDP_PORT 8788
#endif

class HostDiscovery {
public:
    HostDiscovery();
    void begin();
    void stop();

    // Fast check for incoming UDP beacon (non-blocking, <1ms)
    bool checkBeacon();

    // Actively discover receiver using multi-tier fallback (UDP query, mDNS, subnet scan)
    bool discoverNow();

    // Sends a UDP discovery broadcast packet
    bool sendQuery();

    // Resolves hostname via mDNS (e.g., "Couch")
    bool queryMdns(const char* hostname = "Couch");

    // Probes fast candidate IPs on current /24 subnet (gateway, .33, etc.)
    bool probeSubnet();

    // Verifies receiver liveness via GET http://<ip>:<port>/health (<600ms)
    bool verifyReceiver(const String& ip, uint16_t port = 8787);

private:
    WiFiUDP _udp;
    bool _udpStarted;
    uint32_t _lastBeaconCheck;
    uint32_t _lastDiscoveryAttempt;

    bool parseAndApplyDiscoveryPayload(const char* payload, const IPAddress& remoteIp);
};

extern HostDiscovery hostDiscovery;
