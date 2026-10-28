#ifndef MQTT_CLIENT_MANAGER_H
#define MQTT_CLIENT_MANAGER_H

#include <Arduino.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Update.h>
#include <HTTPClient.h>
#include "config.h"
#include "telemetry_types.h"
#include "offline_buffer.h"

class MqttClientManager {
public:
    MqttClientManager(OfflineFlashBuffer& buffer);
    void begin();
    void loop();

    bool isConnected();
    bool publishTelemetry(const InverterTelemetry& telemetry);
    void flushOfflineBuffer();

private:
    OfflineFlashBuffer& _buffer;
    WiFiClientSecure _secureClient;
    PubSubClient _mqtt;
    uint32_t _lastReconnectAttemptMs;
    uint32_t _lastHeartbeatMs;

    bool connect();
    void onMessageReceived(char* topic, byte* payload, unsigned int length);
    void handleOtaCommand(const String& otaUrl);
    void publishHeartbeat();

    static void mqttCallback(char* topic, byte* payload, unsigned int length);
};

#endif // MQTT_CLIENT_MANAGER_H
