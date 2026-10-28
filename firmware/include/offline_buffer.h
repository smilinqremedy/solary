#ifndef OFFLINE_BUFFER_H
#define OFFLINE_BUFFER_H

#include <Arduino.h>
#include <LittleFS.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include "config.h"
#include "telemetry_types.h"

struct BufferMetadata {
    uint32_t magic;         // 0x534F4C41 ("SOLA")
    uint32_t head_index;    // Next write slot (0 to MAX_OFFLINE_RECORDS - 1)
    uint32_t tail_index;    // Next read/flush slot
    uint32_t stored_count;  // Total un-flushed records currently in queue
    uint32_t crc;           // Header checksum
};

class OfflineFlashBuffer {
public:
    OfflineFlashBuffer();
    bool begin();
    
    // Core Queue Operations
    bool push(const InverterTelemetry& record);
    bool peek(InverterTelemetry& record);
    bool pop();
    uint32_t getPendingCount();
    void clear();

    // Diagnostics
    bool isFull() const;
    bool isEmpty() const;

private:
    SemaphoreHandle_t _mutex;
    BufferMetadata _meta;
    bool _initialized;

    bool loadMetadata();
    bool saveMetadata();
    uint32_t calculateCrc(const BufferMetadata& meta);
    uint32_t getFileOffset(uint32_t index);
};

#endif // OFFLINE_BUFFER_H
