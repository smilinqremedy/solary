#include "mqtt_client_manager.h"
#include <ArduinoJson.h>

static MqttClientManager* s_mqttManagerInstance = nullptr;

MqttClientManager::MqttClientManager(OfflineFlashBuffer& buffer)
    : _buffer(buffer),
      _mqtt(_secureClient),
      _lastReconnectAttemptMs(0),
      _lastHeartbeatMs(0) {
    s_mqttManagerInstance = this;
}

void MqttClientManager::mqttCallback(char* topic, byte* payload, unsigned int length) {
    if (s_mqttManagerInstance) {
        s_mqttManagerInstance->onMessageReceived(topic, payload, length);
    }
}

void MqttClientManager::begin() {
    // Configure TLS Client with Root CA
    #if (MQTT_BROKER_PORT == 8883)
    _secureClient.setCACert(ROOT_CA_CERT);
    #else
    _secureClient.setInsecure(); // Fallback for testing environments without TLS termination
    #endif

    _secureClient.setTimeout(10); // 10s socket timeout
    _mqtt.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
    _mqtt.setCallback(mqttCallback);
    _mqtt.setBufferSize(1024); // Expand buffer for JSON payloads
    _mqtt.setKeepAlive(MQTT_KEEPALIVE_SEC);

    log_i("MQTT Client Manager configured for broker: %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT);
}

bool MqttClientManager::connect() {
    log_i("Attempting MQTTS TLS connection to %s as %s...", MQTT_BROKER_HOST, MQTT_CLIENT_ID);

    // LWT Payload for sudden power loss or network drop
    const char* lwtTopic = MQTT_TOPIC_STATUS;
    const char* lwtPayload = "{\"status\":\"offline\",\"reason\":\"lwt_drop\"}";

    if (_mqtt.connect(MQTT_CLIENT_ID, MQTT_USERNAME, MQTT_AUTH_TOKEN, lwtTopic, 1, true, lwtPayload)) {
        log_i("MQTTS Connected successfully!");

        // Subscribe to remote device commands
        _mqtt.subscribe(MQTT_TOPIC_COMMANDS, 1);

        // Publish Online Status
        publishHeartbeat();
        return true;
    } else {
        log_w("MQTTS connection failed, state rc=%d. Will retry in %d ms",
              _mqtt.state(), MQTT_RETRY_INTERVAL_MS);
        return false;
    }
}

bool MqttClientManager::isConnected() {
    return _mqtt.connected();
}

void MqttClientManager::loop() {
    uint32_t now = millis();

    if (!_mqtt.connected()) {
        if (now - _lastReconnectAttemptMs > MQTT_RETRY_INTERVAL_MS) {
            _lastReconnectAttemptMs = now;
            connect();
        }
    } else {
        _mqtt.loop();

        // Flush offline buffer in gentle batches
        flushOfflineBuffer();

        // Publish periodic heartbeat every 60 seconds
        if (now - _lastHeartbeatMs > 60000) {
            _lastHeartbeatMs = now;
            publishHeartbeat();
        }
    }
}

bool MqttClientManager::publishTelemetry(const InverterTelemetry& telemetry) {
    if (!_mqtt.connected()) {
        log_d("MQTT offline. Enqueuing telemetry to flash buffer...");
        return _buffer.push(telemetry);
    }

    String jsonPayload = telemetry.toJson();
    bool published = _mqtt.publish(MQTT_TOPIC_TELEMETRY, jsonPayload.c_str(), false);

    if (!published) {
        log_w("Failed to publish telemetry to MQTT. Falling back to flash buffer.");
        _buffer.push(telemetry);
        return false;
    }

    log_i("Live Telemetry Published: %s", jsonPayload.c_str());
    return true;
}

void MqttClientManager::flushOfflineBuffer() {
    uint32_t pending = _buffer.getPendingCount();
    if (pending == 0) return;

    uint8_t count = 0;
    while (_mqtt.connected() && !_buffer.isEmpty() && count < BUFFER_FLUSH_BATCH_SIZE) {
        InverterTelemetry record;
        if (_buffer.peek(record)) {
            String jsonPayload = record.toJson();
            if (_mqtt.publish(MQTT_TOPIC_HISTORICAL, jsonPayload.c_str(), false)) {
                _buffer.pop();
                count++;
                log_d("Flushed historical record (%u remaining)", _buffer.getPendingCount());
            } else {
                log_w("Failed to publish historical record, breaking batch flush.");
                break;
            }
        } else {
            break;
        }
    }
}

void MqttClientManager::publishHeartbeat() {
    JsonDocument doc;
    doc["device_id"] = DEVICE_ID;
    doc["status"] = "online";
    doc["fw_version"] = FIRMWARE_VERSION;
    doc["hw_rev"] = HARDWARE_REVISION;
    doc["uptime_s"] = (uint32_t)(millis() / 1000);
    doc["free_heap"] = ESP.getFreeHeap();
    doc["pending_buffer"] = _buffer.getPendingCount();

    String payload;
    serializeJson(doc, payload);
    _mqtt.publish(MQTT_TOPIC_STATUS, payload.c_str(), true);
}

void MqttClientManager::onMessageReceived(char* topic, byte* payload, unsigned int length) {
    String msg;
    for (unsigned int i = 0; i < length; i++) {
        msg += (char)payload[i];
    }
    log_i("MQTT Command received on [%s]: %s", topic, msg.c_str());

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, msg);
    if (err) {
        log_e("Invalid JSON in command: %s", err.c_str());
        return;
    }

    const char* action = doc["action"] | "";
    if (strcmp(action, "ota") == 0) {
        const char* url = doc["url"] | "";
        if (strlen(url) > 0) {
            handleOtaCommand(String(url));
        }
    } else if (strcmp(action, "reboot") == 0) {
        log_w("Remote reboot requested via MQTT.");
        delay(500);
        ESP.restart();
    } else if (strcmp(action, "clear_buffer") == 0) {
        _buffer.clear();
        log_i("Buffer cleared by remote command.");
    }
}

void MqttClientManager::handleOtaCommand(const String& otaUrl) {
    log_i("Starting Remote Signed OTA update from: %s", otaUrl.c_str());

    HTTPClient http;
    http.begin(otaUrl);
    int httpCode = http.GET();

    if (httpCode != HTTP_CODE_OK) {
        log_e("HTTP GET failed with code: %d", httpCode);
        http.end();
        return;
    }

    int contentLength = http.getSize();
    if (contentLength <= 0) {
        log_e("Invalid OTA content length: %d", contentLength);
        http.end();
        return;
    }

    bool canBegin = Update.begin(contentLength);
    if (!canBegin) {
        log_e("Not enough space to begin OTA update");
        http.end();
        return;
    }

    WiFiClient* stream = http.getStreamPtr();
    size_t written = Update.writeStream(*stream);

    if (written == contentLength) {
        log_i("Written : %u bytes successfully. Finalizing...", written);
    } else {
        log_e("OTA written only : %u/%u bytes. Error: %d", written, contentLength, Update.getError());
    }

    if (Update.end()) {
        if (Update.isFinished()) {
            log_i("OTA Update Success! Rebooting to new firmware partition...");
            http.end();
            delay(1000);
            ESP.restart();
        } else {
            log_e("OTA failed, update not finished");
        }
    } else {
        log_e("Update.end() failed: %d", Update.getError());
    }
    http.end();
}
