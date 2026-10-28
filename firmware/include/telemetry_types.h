#ifndef TELEMETRY_TYPES_H
#define TELEMETRY_TYPES_H

#include <Arduino.h>
#include <ArduinoJson.h>

// Packed struct for low flash memory footprint in LittleFS circular queue
struct __attribute__((packed)) InverterTelemetry {
    char device_id[20];
    uint32_t timestamp;      // Unix epoch timestamp
    float grid_voltage_v;    // Input AC Grid Voltage
    bool grid_status;        // Grid Available: 1/true, Grid Down: 0/false
    float pv_voltage_v;      // Solar Array DC Voltage
    float pv_power_w;        // Real-time Solar Generation in Watts
    float battery_voltage_v; // DC Battery Voltage
    float battery_soc_pct;   // Battery State of Charge (0 - 100%)
    float battery_current_a; // Charging > 0, Discharging < 0
    float output_power_w;    // Current household/facility load in Watts
    float inverter_temp_c;   // Internal temperature in Celsius
    uint16_t fault_code;     // Hex error code
    bool is_buffered;        // Flag to indicate if this is historical flushed data

    // Default constructor
    InverterTelemetry() {
        memset(device_id, 0, sizeof(device_id));
        timestamp = 0;
        grid_voltage_v = 0.0f;
        grid_status = false;
        pv_voltage_v = 0.0f;
        pv_power_w = 0.0f;
        battery_voltage_v = 0.0f;
        battery_soc_pct = 0.0f;
        battery_current_a = 0.0f;
        output_power_w = 0.0f;
        inverter_temp_c = 0.0f;
        fault_code = 0;
        is_buffered = false;
    }

    // Serialize to standard JSON format expected by Cloud Backend & MQTT
    String toJson() const {
        JsonDocument doc;
        doc["device_id"] = device_id;
        doc["timestamp"] = timestamp;
        
        // Exact keys as specified in platform prompt
        doc["grid_v"]    = round(grid_voltage_v * 10.0f) / 10.0f;
        doc["grid_on"]   = grid_status;
        doc["pv_v"]      = round(pv_voltage_v * 10.0f) / 10.0f;
        doc["pv_w"]      = (int)round(pv_power_w);
        doc["bat_v"]     = round(battery_voltage_v * 10.0f) / 10.0f;
        doc["bat_soc"]   = (int)round(battery_soc_pct);
        doc["bat_a"]     = round(battery_current_a * 10.0f) / 10.0f;
        doc["load_w"]    = (int)round(output_power_w);
        doc["temp_c"]    = round(inverter_temp_c * 10.0f) / 10.0f;
        doc["fault_code"]= fault_code;
        
        if (is_buffered) {
            doc["buffered"] = true;
        }

        String output;
        serializeJson(doc, output);
        return output;
    }

    // Populate from JSON
    bool fromJson(const String& jsonStr) {
        JsonDocument doc;
        DeserializationError err = deserializeJson(doc, jsonStr);
        if (err) return false;

        strlcpy(device_id, doc["device_id"] | "", sizeof(device_id));
        timestamp = doc["timestamp"] | 0;
        grid_voltage_v = doc["grid_v"] | 0.0f;
        grid_status = doc["grid_on"] | false;
        pv_voltage_v = doc["pv_v"] | 0.0f;
        pv_power_w = doc["pv_w"] | 0.0f;
        battery_voltage_v = doc["bat_v"] | 0.0f;
        battery_soc_pct = doc["bat_soc"] | 0.0f;
        battery_current_a = doc["bat_a"] | 0.0f;
        output_power_w = doc["load_w"] | 0.0f;
        inverter_temp_c = doc["temp_c"] | 0.0f;
        fault_code = doc["fault_code"] | 0;
        is_buffered = doc["buffered"] | false;
        return true;
    }
};

#endif // TELEMETRY_TYPES_H
