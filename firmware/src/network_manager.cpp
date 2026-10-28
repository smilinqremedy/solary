#include "network_manager.h"

NetworkManager::NetworkManager()
    : _activeMode(NET_MODE_DISCONNECTED),
      _lastWifiAttemptMs(0),
      _wifiDisconnectStartMs(0),
      _gsmInitialized(false),
      _gsmSerial(1) { // UART1 for GSM
}

void NetworkManager::begin() {
    pinMode(LED_WIFI_PIN, OUTPUT);
    pinMode(GSM_PWR_PIN, OUTPUT);
    pinMode(GSM_RST_PIN, OUTPUT);

    digitalWrite(LED_WIFI_PIN, LOW);
    digitalWrite(GSM_PWR_PIN, LOW);
    digitalWrite(GSM_RST_PIN, LOW);

    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false); // Disable WiFi power save for ultra-low latency & reliability

    log_i("Starting Wi-Fi connection attempt...");
    WiFi.begin(); // Attempt with saved credentials in NVS

    _wifiDisconnectStartMs = millis();
}

void NetworkManager::startConfigPortal() {
    log_i("Launching On-Demand WiFiManager Captive Portal...");
    WiFiManager wm;
    wm.setConfigPortalTimeout(120); // 2 minute timeout so it returns if unconfigured

    String apName = "NG-Solar-Setup-" + String(DEVICE_ID);
    if (!wm.startConfigPortal(apName.c_str(), "solar1234")) {
        log_w("Config portal timed out. Continuing automatic network state machine.");
    } else {
        log_i("Wi-Fi credentials configured successfully via Captive Portal!");
    }
}

void NetworkManager::loop() {
    handleWifiState();
    updateStatusLeds();
}

void NetworkManager::handleWifiState() {
    if (WiFi.status() == WL_CONNECTED) {
        if (_activeMode != NET_MODE_WIFI) {
            _activeMode = NET_MODE_WIFI;
            _wifiDisconnectStartMs = 0;
            log_i("Wi-Fi Connected! IP: %s, RSSI: %d dBm", WiFi.localIP().toString().c_str(), WiFi.RSSI());
        }
        return;
    }

    // Wi-Fi is currently disconnected
    if (_activeMode == NET_MODE_WIFI || _wifiDisconnectStartMs == 0) {
        _wifiDisconnectStartMs = millis();
        _activeMode = NET_MODE_DISCONNECTED;
        log_w("Wi-Fi connection lost!");
    }

    uint32_t now = millis();

    // Check if Wi-Fi has been down longer than timeout (e.g. 60s) -> Switch to GSM
    if ((now - _wifiDisconnectStartMs > NETWORK_FAILOVER_TIMEOUT) && _activeMode != NET_MODE_GSM) {
        log_w("Wi-Fi down for > 60s. Activating GSM/LTE fallback (SIM800L / A7670E)...");
        if (initGsm() && connectGsm()) {
            _activeMode = NET_MODE_GSM;
            log_i("GSM Cellular connection active!");
        } else {
            log_e("GSM fallback connection failed. Will retry...");
        }
    }

    // Periodically re-probe Wi-Fi every 30 seconds if running on GSM
    if (now - _lastWifiAttemptMs > 30000) {
        _lastWifiAttemptMs = now;
        if (_activeMode == NET_MODE_GSM) {
            log_d("Probing Wi-Fi in background to see if primary link restored...");
            WiFi.reconnect();
        }
    }
}

bool NetworkManager::initGsm() {
    if (_gsmInitialized) return true;

    log_i("Powering on GSM modem on UART1 (RX=%d, TX=%d)...", GSM_RX_PIN, GSM_TX_PIN);
    _gsmSerial.begin(GSM_BAUD_RATE, SERIAL_8N1, GSM_RX_PIN, GSM_TX_PIN);

    // Pulse PWRKEY to turn on SIM800L / A7670E
    digitalWrite(GSM_PWR_PIN, HIGH);
    delay(1000);
    digitalWrite(GSM_PWR_PIN, LOW);
    delay(3000);

    // Basic AT test
    _gsmSerial.println("AT");
    delay(200);
    _gsmInitialized = true;
    return true;
}

bool NetworkManager::connectGsm() {
    // Send standard GPRS registration AT commands
    _gsmSerial.println("AT+CPIN?");
    delay(500);
    _gsmSerial.println("AT+CREG?");
    delay(500);
    _gsmSerial.printf("AT+CSTT=\"%s\",\"%s\",\"%s\"\r\n", GSM_APN, GSM_APN_USER, GSM_APN_PASS);
    delay(1000);
    _gsmSerial.println("AT+CIICR");
    delay(2000);
    _gsmSerial.println("AT+CIFSR"); // Fetch local IP
    delay(1000);
    return true;
}

bool NetworkManager::isConnected() {
    if (_activeMode == NET_MODE_WIFI) {
        return (WiFi.status() == WL_CONNECTED);
    }
    return (_activeMode == NET_MODE_GSM);
}

String NetworkManager::getIpAddress() const {
    if (_activeMode == NET_MODE_WIFI) {
        return WiFi.localIP().toString();
    } else if (_activeMode == NET_MODE_GSM) {
        return "Cellular-Active";
    }
    return "0.0.0.0";
}

int NetworkManager::getSignalStrength() {
    if (_activeMode == NET_MODE_WIFI) {
        return WiFi.RSSI();
    }
    return -75; // Representative cellular signal
}

void NetworkManager::updateStatusLeds() {
    static uint32_t lastBlink = 0;
    static bool ledState = false;
    uint32_t now = millis();

    if (_activeMode == NET_MODE_WIFI) {
        digitalWrite(LED_WIFI_PIN, HIGH); // Solid Blue
    } else if (_activeMode == NET_MODE_GSM) {
        // Fast double blink for GSM
        if (now - lastBlink > 250) {
            lastBlink = now;
            ledState = !ledState;
            digitalWrite(LED_WIFI_PIN, ledState);
        }
    } else {
        // Slow blink when seeking network
        if (now - lastBlink > 1000) {
            lastBlink = now;
            ledState = !ledState;
            digitalWrite(LED_WIFI_PIN, ledState);
        }
    }
}
