#ifndef NETWORK_MANAGER_H
#define NETWORK_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <HardwareSerial.h>
#include "config.h"

enum NetworkMode {
    NET_MODE_DISCONNECTED = 0,
    NET_MODE_WIFI,
    NET_MODE_GSM
};

class NetworkManager {
public:
    NetworkManager();
    void begin();
    void loop();
    
    bool isConnected();
    NetworkMode getActiveMode() const { return _activeMode; }
    String getIpAddress() const;
    int getSignalStrength(); // RSSI in dBm
    
    // Explicit trigger for captive portal (e.g., long press button)
    void startConfigPortal();
    Client* getNetworkClient(); // Returns WiFiClient or GSM client pointer

private:
    NetworkMode _activeMode;
    uint32_t _lastWifiAttemptMs;
    uint32_t _wifiDisconnectStartMs;
    bool _gsmInitialized;
    HardwareSerial _gsmSerial;

    bool initGsm();
    bool connectGsm();
    void handleWifiState();
    void updateStatusLeds();
};

#endif // NETWORK_MANAGER_H
