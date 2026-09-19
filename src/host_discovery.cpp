#include "host_discovery.h"

HostDiscovery hostDiscovery;

HostDiscovery::HostDiscovery()
    : _udpStarted(false), _lastBeaconCheck(0), _lastDiscoveryAttempt(0) {
}

void HostDiscovery::begin() {
    if (WiFi.status() == WL_CONNECTED && !_udpStarted) {
        if (_udp.begin(DISCOVERY_UDP_PORT)) {
            _udpStarted = true;
            Serial.printf("[Discovery] Listening on UDP port %u\n", DISCOVERY_UDP_PORT);
        } else {
            Serial.printf("[Discovery] Failed to bind UDP port %u\n", DISCOVERY_UDP_PORT);
        }
    }
}

void HostDiscovery::stop() {
    if (_udpStarted) {
        _udp.stop();
        _udpStarted = false;
        Serial.println("[Discovery] UDP listener stopped.");
    }
}

bool HostDiscovery::parseAndApplyDiscoveryPayload(const char* payload, const IPAddress& remoteIp) {
    if (!payload || strlen(payload) == 0) return false;

    // Fast check for signature
    if (!strstr(payload, "\"service\"") || !strstr(payload, "hermes-receiver")) {
        return false;
    }

    String discoveredIp = "";
    const char* ipKey = "\"ip\":";
    const char* pIp = strstr(payload, ipKey);
    if (pIp) {
        pIp += strlen(ipKey);
        while (*pIp == ' ' || *pIp == '"') pIp++;
        const char* pEnd = pIp;
        while (*pEnd && *pEnd != '"' && *pEnd != ',' && *pEnd != '}') pEnd++;
        discoveredIp = String(pIp).substring(0, pEnd - pIp);
    }

    // Fall back to remote socket IP if payload didn't contain explicit IP or if it's 127.0.0.1
    if (discoveredIp.length() == 0 || discoveredIp == "127.0.0.1" || discoveredIp == "0.0.0.0") {
        discoveredIp = remoteIp.toString();
    }

    // Parse port
    uint16_t port = 8787;
    const char* portKey = "\"port\":";
    const char* pPort = strstr(payload, portKey);
    if (pPort) {
        pPort += strlen(portKey);
        while (*pPort == ' ') pPort++;
        port = (uint16_t)atoi(pPort);
        if (port == 0) port = 8787;
    }

    if (discoveredIp.length() > 0 && discoveredIp != "0.0.0.0") {
        Serial.printf("[Discovery] Discovered Hermes Receiver at %s:%u\n", discoveredIp.c_str(), port);
        envManager.setDiscoveredHost(envManager.getMode(), discoveredIp, port);
        return true;
    }
    return false;
}

bool HostDiscovery::checkBeacon() {
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!_udpStarted) begin();
    if (!_udpStarted) return false;

    int packetSize = _udp.parsePacket();
    if (packetSize > 0) {
        char buf[512];
        int len = _udp.read(buf, sizeof(buf) - 1);
        if (len > 0) {
            buf[len] = '\0';
            return parseAndApplyDiscoveryPayload(buf, _udp.remoteIP());
        }
    }
    return false;
}

bool HostDiscovery::sendQuery() {
    if (WiFi.status() != WL_CONNECTED) return false;
    if (!_udpStarted) begin();
    if (!_udpStarted) return false;

    const char* query = "{\"query\":\"hermes-receiver\"}";
    size_t qLen = strlen(query);

    // 1. Broadcast to global 255.255.255.255
    _udp.beginPacket(IPAddress(255, 255, 255, 255), DISCOVERY_UDP_PORT);
    _udp.write((const uint8_t*)query, qLen);
    _udp.endPacket();

    // 2. Broadcast to active subnet broadcast address
    IPAddress subnetBroadcast = WiFi.localIP() | ~WiFi.subnetMask();
    _udp.beginPacket(subnetBroadcast, DISCOVERY_UDP_PORT);
    _udp.write((const uint8_t*)query, qLen);
    _udp.endPacket();

    Serial.printf("[Discovery] Broadcasted discovery query to %s:%u\n", 
                  subnetBroadcast.toString().c_str(), DISCOVERY_UDP_PORT);

    // Wait up to 400ms for immediate response
    uint32_t start = millis();
    while (millis() - start < 400) {
        if (checkBeacon()) {
            return true;
        }
        delay(20);
    }
    return false;
}

bool HostDiscovery::queryMdns(const char* hostname) {
    if (WiFi.status() != WL_CONNECTED) return false;

    Serial.printf("[Discovery] Querying mDNS for '%s.local'...\n", hostname);
    if (!MDNS.begin("esp32-macropad")) {
        Serial.println("[Discovery] Failed to start MDNS responder");
        return false;
    }

    IPAddress hostIp = MDNS.queryHost(hostname, 1200);
    if (hostIp != IPAddress(0, 0, 0, 0)) {
        String ipStr = hostIp.toString();
        Serial.printf("[Discovery] mDNS resolved '%s.local' -> %s\n", hostname, ipStr.c_str());
        if (verifyReceiver(ipStr, 8787)) {
            envManager.setDiscoveredHost(envManager.getMode(), ipStr, 8787);
            return true;
        }
    }
    return false;
}

bool HostDiscovery::verifyReceiver(const String& ip, uint16_t port) {
    if (ip.length() == 0 || ip == "0.0.0.0") return false;

    String url = "http://" + ip + ":" + String(port) + "/health";
    HTTPClient http;
    http.begin(url);
    http.setTimeout(500);
    int code = http.GET();
    http.end();

    if (code == 200) {
        Serial.printf("[Discovery] Liveness check SUCCESS at %s\n", url.c_str());
        return true;
    }
    return false;
}

bool HostDiscovery::probeSubnet() {
    if (WiFi.status() != WL_CONNECTED) return false;

    IPAddress myIp = WiFi.localIP();
    if (myIp[0] == 0) return false;

    Serial.printf("[Discovery] Probing candidate IPs on subnet %u.%u.%u.x...\n", 
                  myIp[0], myIp[1], myIp[2]);

    // Priority candidates on mobile hotspots:
    // 1. .33 (typical host assignment on Samsung Galaxy hotspots)
    // 2. Gateway IP
    // 3. .1
    // 4. .2
    // 5. .100
    uint8_t octets[] = {33, (uint8_t)WiFi.gatewayIP()[3], 1, 2, 100, 101};

    for (size_t i = 0; i < sizeof(octets) / sizeof(octets[0]); i++) {
        uint8_t lastOctet = octets[i];
        if (lastOctet == 0 || lastOctet == myIp[3]) continue;

        IPAddress cand(myIp[0], myIp[1], myIp[2], lastOctet);
        String candStr = cand.toString();

        if (verifyReceiver(candStr, 8787)) {
            Serial.printf("[Discovery] Subnet probe verified receiver at %s\n", candStr.c_str());
            envManager.setDiscoveredHost(envManager.getMode(), candStr, 8787);
            return true;
        }
    }
    return false;
}

bool HostDiscovery::discoverNow() {
    uint32_t now = millis();
    if (now - _lastDiscoveryAttempt < 2000) {
        return false;
    }
    _lastDiscoveryAttempt = now;

    Serial.println("[Discovery] Initiating multi-tier host discovery...");

    // Tier 1: Check pending UDP beacon
    if (checkBeacon()) return true;

    // Tier 2: Send UDP broadcast query and wait for reply
    if (sendQuery()) return true;

    // Tier 3: Query mDNS for hostname
#ifdef WORK_HOST_MDNS
    if (queryMdns(WORK_HOST_MDNS)) return true;
#else
    if (queryMdns("Couch")) return true;
#endif

    // Tier 4: Fast subnet candidate probe
    if (probeSubnet()) return true;

    Serial.println("[Discovery] Host discovery completed without finding active receiver.");
    return false;
}
