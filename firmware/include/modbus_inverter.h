#ifndef MODBUS_INVERTER_H
#define MODBUS_INVERTER_H

#include <Arduino.h>
#include <ModbusMaster.h>
#include "config.h"
#include "telemetry_types.h"

class InverterModbusReader {
public:
    InverterModbusReader();
    void begin(int profile = ACTIVE_INVERTER_PROFILE);
    bool readTelemetry(InverterTelemetry& telemetry);
    void setProfile(int profile);
    int getProfile() const { return _profile; }
    
    // Diagnostic stats
    uint32_t getSuccessfulReads() const { return _successfulReads; }
    uint32_t getFailedReads() const { return _failedReads; }

private:
    int _profile;
    HardwareSerial _modbusSerial;
    ModbusMaster _node;
    uint32_t _successfulReads;
    uint32_t _failedReads;

    // Profile-specific parsers
    bool readGrowattSPF(InverterTelemetry& telemetry);
    bool readMustPV1800(InverterTelemetry& telemetry);
    bool readFelicity(InverterTelemetry& telemetry);

    // Callbacks for RS485 Direction Control
    static void preTransmission();
    static void postTransmission();
};

#endif // MODBUS_INVERTER_H
