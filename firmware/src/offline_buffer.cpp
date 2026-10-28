#include "offline_buffer.h"

#define BUFFER_MAGIC 0x534F4C41 // "SOLA"

OfflineFlashBuffer::OfflineFlashBuffer() : _initialized(false) {
    _mutex = xSemaphoreCreateMutex();
    memset(&_meta, 0, sizeof(BufferMetadata));
}

uint32_t OfflineFlashBuffer::calculateCrc(const BufferMetadata& meta) {
    // Simple fast 32-bit FNV-1a hash for metadata protection
    const uint8_t* data = (const uint8_t*)&meta;
    size_t length = sizeof(BufferMetadata) - sizeof(meta.crc);
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < length; i++) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

uint32_t OfflineFlashBuffer::getFileOffset(uint32_t index) {
    return index * sizeof(InverterTelemetry);
}

bool OfflineFlashBuffer::begin() {
    if (!LittleFS.begin(true)) {
        log_e("Failed to mount LittleFS for offline buffer! Attempting format...");
        if (!LittleFS.format() || !LittleFS.begin()) {
            log_e("Fatal: LittleFS format failed");
            return false;
        }
    }

    if (!loadMetadata()) {
        log_w("Buffer metadata missing or invalid. Initializing fresh buffer...");
        clear();
    }

    _initialized = true;
    log_i("OfflineFlashBuffer initialized. Pending records to flush: %u / %u",
          _meta.stored_count, MAX_OFFLINE_RECORDS);
    return true;
}

bool OfflineFlashBuffer::loadMetadata() {
    if (!LittleFS.exists(LITTLEFS_META_FILE)) {
        return false;
    }

    File metaFile = LittleFS.open(LITTLEFS_META_FILE, FILE_READ);
    if (!metaFile) return false;

    BufferMetadata temp;
    size_t bytesRead = metaFile.read((uint8_t*)&temp, sizeof(BufferMetadata));
    metaFile.close();

    if (bytesRead != sizeof(BufferMetadata)) return false;
    if (temp.magic != BUFFER_MAGIC) return false;
    if (temp.crc != calculateCrc(temp)) {
        log_w("Metadata CRC mismatch! Flash corrupted.");
        return false;
    }

    _meta = temp;
    return true;
}

bool OfflineFlashBuffer::saveMetadata() {
    _meta.magic = BUFFER_MAGIC;
    _meta.crc = calculateCrc(_meta);

    File metaFile = LittleFS.open(LITTLEFS_META_FILE, FILE_WRITE);
    if (!metaFile) {
        log_e("Failed to open meta file for writing!");
        return false;
    }

    size_t written = metaFile.write((const uint8_t*)&_meta, sizeof(BufferMetadata));
    metaFile.flush();
    metaFile.close();
    return (written == sizeof(BufferMetadata));
}

bool OfflineFlashBuffer::push(const InverterTelemetry& record) {
    if (!_initialized) return false;

    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) {
        log_e("OfflineFlashBuffer push timed out acquiring mutex");
        return false;
    }

    File dataFile = LittleFS.open(LITTLEFS_BUFFER_FILE, "r+");
    if (!dataFile) {
        dataFile = LittleFS.open(LITTLEFS_BUFFER_FILE, FILE_WRITE);
        if (!dataFile) {
            log_e("Failed to open buffer file for writing");
            xSemaphoreGive(_mutex);
            return false;
        }
    }

    uint32_t offset = getFileOffset(_meta.head_index);
    if (!dataFile.seek(offset, SeekSet)) {
        log_e("Failed to seek to slot offset: %u", offset);
        dataFile.close();
        xSemaphoreGive(_mutex);
        return false;
    }

    InverterTelemetry copy = record;
    copy.is_buffered = true; // Mark record as buffered historical telemetry

    size_t written = dataFile.write((const uint8_t*)&copy, sizeof(InverterTelemetry));
    dataFile.flush();
    dataFile.close();

    if (written != sizeof(InverterTelemetry)) {
        log_e("Incomplete write to offline buffer flash slot");
        xSemaphoreGive(_mutex);
        return false;
    }

    // Advance head index
    _meta.head_index = (_meta.head_index + 1) % MAX_OFFLINE_RECORDS;

    if (_meta.stored_count < MAX_OFFLINE_RECORDS) {
        _meta.stored_count++;
    } else {
        // Buffer full: drop oldest record by advancing tail
        _meta.tail_index = (_meta.tail_index + 1) % MAX_OFFLINE_RECORDS;
        log_w("Offline buffer full (%u records). Overwriting oldest telemetry.", MAX_OFFLINE_RECORDS);
    }

    saveMetadata();
    xSemaphoreGive(_mutex);
    return true;
}

bool OfflineFlashBuffer::peek(InverterTelemetry& record) {
    if (!_initialized || _meta.stored_count == 0) return false;

    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) return false;

    File dataFile = LittleFS.open(LITTLEFS_BUFFER_FILE, FILE_READ);
    if (!dataFile) {
        xSemaphoreGive(_mutex);
        return false;
    }

    uint32_t offset = getFileOffset(_meta.tail_index);
    if (!dataFile.seek(offset, SeekSet)) {
        dataFile.close();
        xSemaphoreGive(_mutex);
        return false;
    }

    size_t readBytes = dataFile.read((uint8_t*)&record, sizeof(InverterTelemetry));
    dataFile.close();
    xSemaphoreGive(_mutex);

    return (readBytes == sizeof(InverterTelemetry));
}

bool OfflineFlashBuffer::pop() {
    if (!_initialized || _meta.stored_count == 0) return false;

    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(500)) != pdTRUE) return false;

    _meta.tail_index = (_meta.tail_index + 1) % MAX_OFFLINE_RECORDS;
    if (_meta.stored_count > 0) {
        _meta.stored_count--;
    }

    saveMetadata();
    xSemaphoreGive(_mutex);
    return true;
}

uint32_t OfflineFlashBuffer::getPendingCount() {
    return _meta.stored_count;
}

bool OfflineFlashBuffer::isFull() const {
    return _meta.stored_count >= MAX_OFFLINE_RECORDS;
}

bool OfflineFlashBuffer::isEmpty() const {
    return _meta.stored_count == 0;
}

void OfflineFlashBuffer::clear() {
    if (xSemaphoreTake(_mutex, pdMS_TO_TICKS(1000)) == pdTRUE) {
        _meta.magic = BUFFER_MAGIC;
        _meta.head_index = 0;
        _meta.tail_index = 0;
        _meta.stored_count = 0;
        saveMetadata();

        if (LittleFS.exists(LITTLEFS_BUFFER_FILE)) {
            LittleFS.remove(LITTLEFS_BUFFER_FILE);
        }
        xSemaphoreGive(_mutex);
        log_i("Offline buffer cleared.");
    }
}
