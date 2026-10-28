#include <Arduino.h>
#include <esp_task_wdt.h>
#include "config.h"
#include "telemetry_types.h"
#include "modbus_inverter.h"
#include "offline_buffer.h"
#include "network_manager.h"
#include "mqtt_client_manager.h"

// =============================================================================
// GLOBAL INSTANCES & RTOS SYNCHRONIZATION
// =============================================================================
static InverterModbusReader   inverterReader;
static OfflineFlashBuffer     offlineBuffer;
static NetworkManager         networkManager;
static MqttClientManager      mqttManager(offlineBuffer);

// Inter-Task Communication Queue (holds up to 10 unhandled telemetry frames)
static QueueHandle_t telemetryQueue = nullptr;

// FreeRTOS Task Handles
static TaskHandle_t hModbusTask   = nullptr;
static TaskHandle_t hNetworkTask  = nullptr;
static TaskHandle_t hWatchdogTask = nullptr;

// =============================================================================
// TASK 1: Modbus Polling Task (Core 1, Priority 3)
// Deterministic 5-second sampling loop directly communicating via MAX485
// =============================================================================
void modbusPollingTask(void* pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    const TickType_t xFrequency = pdMS_TO_TICKS(MODBUS_POLL_MS);

    log_i("Task 1 (Modbus Polling) started on Core %d", xPortGetCoreID());

    for (;;) {
        vTaskDelayUntil(&xLastWakeTime, xFrequency);

        InverterTelemetry telemetry;
        bool readSuccess = inverterReader.readTelemetry(telemetry);

        if (readSuccess) {
            // Send telemetry to Network Task via FreeRTOS queue (non-blocking)
            if (xQueueSend(telemetryQueue, &telemetry, pdMS_TO_TICKS(100)) != pdTRUE) {
                log_w("Telemetry queue full! Directly saving sample to offline flash buffer");
                offlineBuffer.push(telemetry);
            }
        } else {
            log_w("Inverter Modbus read failed. Retrying next cycle.");
        }

        // Feed hardware task watchdog for this task
        esp_task_wdt_reset();
    }
}

// =============================================================================
// TASK 2: Network & MQTT Communication Task (Core 0, Priority 2)
// Handles Wi-Fi/GSM state machine, TLS socket, publishing & buffer drainage
// =============================================================================
void networkMqttTask(void* pvParameters) {
    log_i("Task 2 (Network & MQTT) started on Core %d", xPortGetCoreID());

    for (;;) {
        // Run network stack checks (Wi-Fi reconnection / GSM fallback)
        networkManager.loop();

        // Run MQTT loop (handles packets, pings, command reception, buffer flush)
        if (networkManager.isConnected()) {
            mqttManager.loop();
        }

        // Process incoming telemetry samples from Modbus task queue
        InverterTelemetry sample;
        while (xQueueReceive(telemetryQueue, &sample, 0) == pdTRUE) {
            if (mqttManager.isConnected()) {
                mqttManager.publishTelemetry(sample);
            } else {
                // If network/broker is offline, enqueue directly to LittleFS circular buffer
                log_w("Network/MQTT unavailable. Buffering telemetry into LittleFS flash.");
                offlineBuffer.push(sample);
            }
        }

        // Feed hardware task watchdog
        esp_task_wdt_reset();

        vTaskDelay(pdMS_TO_TICKS(50)); // Fast responsive loop
    }
}

// =============================================================================
// TASK 3: Watchdog & System Health Task (Core 0, Priority 1)
// Toggles heartbeat indicator, tracks free memory, verifies thread health
// =============================================================================
void watchdogTask(void* pvParameters) {
    log_i("Task 3 (Watchdog & Health) started on Core %d", xPortGetCoreID());

    for (;;) {
        // Check flash buffer status and alert LED
        if (offlineBuffer.getPendingCount() > 0) {
            // Buffer has un-flushed items: slow blink alert LED
            digitalWrite(LED_ALERT_PIN, HIGH);
            vTaskDelay(pdMS_TO_TICKS(100));
            digitalWrite(LED_ALERT_PIN, LOW);
        } else {
            digitalWrite(LED_ALERT_PIN, LOW);
        }

        // Diagnostic log every 30 seconds
        static uint32_t lastHealthLog = 0;
        if (millis() - lastHealthLog > 30000) {
            lastHealthLog = millis();
            log_i("System Health -> Free Heap: %u bytes | Min Heap: %u bytes | Buffer Pending: %u records | Net: %s",
                  ESP.getFreeHeap(),
                  ESP.getMinFreeHeap(),
                  offlineBuffer.getPendingCount(),
                  networkManager.isConnected() ? "ONLINE" : "OFFLINE");
        }

        esp_task_wdt_reset();
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

// =============================================================================
// ARDUINO SETUP & LOOP
// =============================================================================
void setup() {
    Serial.begin(115200);
    delay(1000);
    log_i("\n========================================================");
    log_i("  NIGERIAN SOLAR INTELLIGENCE EDGE GATEWAY (ESP32)     ");
    log_i("  Firmware: %s | Hardware: %s", FIRMWARE_VERSION, HARDWARE_REVISION);
    log_i("========================================================");

    // Pin Modes
    pinMode(LED_ALERT_PIN, OUTPUT);
    pinMode(LED_MODBUS_PIN, OUTPUT);
    digitalWrite(LED_ALERT_PIN, LOW);
    digitalWrite(LED_MODBUS_PIN, LOW);

    // Initialize LittleFS Offline Buffer
    if (!offlineBuffer.begin()) {
        log_e("Critical: LittleFS Offline Buffer initialization failed!");
    }

    // Initialize Inverter Modbus RS485 Interface
    inverterReader.begin(ACTIVE_INVERTER_PROFILE);

    // Initialize Network Stack (Wi-Fi + GSM)
    networkManager.begin();

    // Initialize MQTTS Client
    mqttManager.begin();

    // Create FreeRTOS Telemetry Queue
    telemetryQueue = xQueueCreate(10, sizeof(InverterTelemetry));
    if (telemetryQueue == nullptr) {
        log_e("Fatal: Failed to create telemetryQueue!");
        while (1) { delay(1000); }
    }

    // Initialize Hardware Task Watchdog Timer (TWDT) for 15 seconds
    esp_task_wdt_init(WDT_TIMEOUT_SECONDS, true);

    // Launch FreeRTOS Tasks with Core Affinity:
    // Core 1 dedicated to real-time deterministic Modbus polling
    xTaskCreatePinnedToCore(
        modbusPollingTask,
        "ModbusPoller",
        4096,
        nullptr,
        3, // High priority
        &hModbusTask,
        1  // Core 1
    );

    // Core 0 handles network, TLS cryptographic handshakes, and MQTT queues
    xTaskCreatePinnedToCore(
        networkMqttTask,
        "NetMqttLoop",
        8192,
        nullptr,
        2, // Normal priority
        &hNetworkTask,
        0  // Core 0
    );

    // Core 0 handles system health & watchdog monitoring
    xTaskCreatePinnedToCore(
        watchdogTask,
        "WatchdogHealth",
        2048,
        nullptr,
        1, // Low priority
        &hWatchdogTask,
        0  // Core 0
    );

    // Subscribe tasks to Task Watchdog Timer
    esp_task_wdt_add(hModbusTask);
    esp_task_wdt_add(hNetworkTask);
    esp_task_wdt_add(hWatchdogTask);

    log_i("All FreeRTOS tasks started successfully.");
}

void loop() {
    // Main loop remains empty as all logic executes in dedicated FreeRTOS tasks
    vTaskDelete(nullptr);
}
