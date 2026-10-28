#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// =============================================================================
// DEVICE IDENTITY & HARDWARE CONFIGURATION
// =============================================================================
#define DEVICE_ID "NG-INV-00124"
#define FIRMWARE_VERSION "v1.2.0-prod"
#define HARDWARE_REVISION "ESP32-SOLAR-REV2"

// Status Indicators
#define LED_WIFI_PIN       2   // Built-in Blue LED: Wi-Fi status
#define LED_MODBUS_PIN     15  // Green LED: RS485 communication activity
#define LED_ALERT_PIN      13  // Red LED: Fault or offline buffer warning

// UART2 - RS485 / MAX485 Communication
#define RS485_RX_PIN       16  // RO (Receiver Output) of MAX485
#define RS485_TX_PIN       17  // DI (Driver Input) of MAX485
#define RS485_DE_RE_PIN    4   // DE & RE tied together: HIGH = TX, LOW = RX
#define RS485_BAUD_RATE    9600
#define RS485_SERIAL_CONF  SERIAL_8N1
#define MODBUS_SLAVE_ID    1
#define MODBUS_POLL_MS     5000  // 5 seconds polling interval

// UART1 - GSM/LTE Cellular Fallback (SIM800L / A7670E)
#define GSM_RX_PIN         25
#define GSM_TX_PIN         26
#define GSM_PWR_PIN        27
#define GSM_RST_PIN        14
#define GSM_BAUD_RATE      115200
#define GSM_APN            "web.gprs.mtnnigeria.net" // Default APN for MTN Nigeria
#define GSM_APN_USER       ""
#define GSM_APN_PASS       ""

// =============================================================================
// INVERTER PROTOCOL PROFILE
// Supported: 1 = Growatt SPF 3000/5000 ES, 2 = Must PV1800/PH1800, 3 = Felicity Solar
// =============================================================================
#define INVERTER_PROFILE_GROWATT_SPF  1
#define INVERTER_PROFILE_MUST_PV1800  2
#define INVERTER_PROFILE_FELICITY     3

#ifndef ACTIVE_INVERTER_PROFILE
#define ACTIVE_INVERTER_PROFILE INVERTER_PROFILE_GROWATT_SPF
#endif

// =============================================================================
// MQTT & TLS SECURITY CONFIGURATION
// =============================================================================
#define MQTT_BROKER_HOST   "broker.energyintelligence.ng"
#define MQTT_BROKER_PORT   8883 // MQTTS TLS port (use 1883 for insecure dev)
#define MQTT_CLIENT_ID     "ESP32-" DEVICE_ID
#define MQTT_USERNAME      DEVICE_ID
#define MQTT_AUTH_TOKEN    "eyJh...ng_jwt_pre_shared_token..."

// Topic Architecture
#define MQTT_TOPIC_TELEMETRY    "devices/" DEVICE_ID "/telemetry"
#define MQTT_TOPIC_HISTORICAL   "devices/" DEVICE_ID "/telemetry/historical"
#define MQTT_TOPIC_STATUS       "devices/" DEVICE_ID "/status"
#define MQTT_TOPIC_COMMANDS     "devices/" DEVICE_ID "/commands/#"

#define MQTT_KEEPALIVE_SEC 30
#define MQTT_RETRY_INTERVAL_MS 5000

// =============================================================================
// OFFLINE BUFFER (LITTLEFS CIRCULAR QUEUE)
// =============================================================================
#define LITTLEFS_BUFFER_FILE     "/telemetry_buffer.bin"
#define LITTLEFS_META_FILE       "/telemetry_meta.bin"
#define MAX_OFFLINE_RECORDS      1500  // ~2 hours of 5s intervals (approx 180 KB)
#define BUFFER_FLUSH_BATCH_SIZE  5     // Flush 5 records per MQTT loop iteration

// =============================================================================
// WATCHDOG & TASK TIMINGS
// =============================================================================
#define WDT_TIMEOUT_SECONDS      15    // Hardware Task Watchdog timeout
#define NETWORK_FAILOVER_TIMEOUT 60000 // 60 seconds without Wi-Fi triggers GSM fallback

// =============================================================================
// ROOT CA CERTIFICATE (EMQX / Let's Encrypt ISRG Root X1)
// =============================================================================
static const char ROOT_CA_CERT[] PROGMEM = 
"-----BEGIN CERTIFICATE-----\n"
"MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw\n"
"TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh\n"
"cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4\n"
"WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu\n"
"ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY\n"
"MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oQ6xtns2aCEQgjQgd\n"
"1IESxYialZwe019949Wbld5hrCR21a420bmg7LA91THSJa+ZOMTx+386mNRQXGCm\n"
"hur+wAjmbIOfqgdf0856aYXcGzpDLcnBoNs51ZwOKJWU4aV3qxDYMV3EHrmQSbiW\n"
"df/OI50hFIxHzhnwh2Q222T532/ckW60NN119S/SdUBEJ0CX1qHTMjyR5ypWUMW/\n"
"Ganq085tgCXFFVXXmVSU63qgEnnZ8EB+ni0MWjuv8pN6APW30aKEHYcT9izHY9aw\n"
"dWl073+qlAMXY+WwtWG+kS8YKyCHpuRVKy0VOSEhcdGuNNNHGmtb8yWtKnvqmEkj\n"
"1WDGn3qyuv2UMDZhYZmV8nZXkoQI8766dbzkxn88195FWtwUT5AHKDGbqiScgwAc\n"
"ogJbGLitnkBg0US6s2v307Z3/71Tfl0Y+2JEsrvVW38mScqJnZ014krWXUxIE1lf\n"
"249UExFrAhv379vOMXtBIXE9SEaYZy96wVSaxWVa39NtOsViTUqwmgW8048AbZFa\n"
"AtCmeUzlPOgiW2TnmaHQLMQkrEQCpWCgg8Y9GoffLkt0dV508CA8z07uUM8HFVyo\n"
"69KE4YfZVcnetpRKkNsnHUAjLnWDuuosiVNnlZ++4450ez4GhZZWVbqtvUDKkd18\n"
"FzZTWL4P309OX07KwS+Ib5s5AgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV\n"
"HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAjGi130hhWVjTANBgkq\n"
"hkiG9w0BAQsFAAOCAgEAVR9YqbyheerMSny3Z858c78BH7HSPJYPgPDcCh00EPLB\n"
"CL7W5tWDmaMuySTNEx4RNcfVMrxPVDKGzD5x0KKmoR62zCGUSDQuv26x6GCU61Ox\n"
"ano3WBfeBZONzfDRAhmUVHJVUVFA0bP32EP6UnMmIGwE8246RE/6MX4WgF/CSDDF\n"
"vfbqPNioAgNW6PfKsxIPNXfZAZxw62ctfYK2962A/Rv3vnPEIoN4NWgCTPN50b4e\n"
"Hg5bZs5Z/+ah5HEVnygtv6Ke8vPWuk305B5zn0BQcph895eOMIvEB83xEH369ChG\n"
"CVNz9XVpegfr45cGCVWyPtnyIjYJaKKA2wdxHnRNZ23zn0n4GQhGwVCU2znGNZks\n"
"OWdymUSuaZXKODYz1BhSRPVEBaY+1S77T20BgawgChGvONjGNgymnFCEymTQMNIZ\n"
"NZWC9CAhuVWvdW6oSpHYdc84FU8NxsCEb7YueREmx5671dbzkeKUbRHVPLa9drjq\n"
"9APX6mquvpoP0YZZMSTYzqxY/DQxTx+XM01xENAzlT0iqK52YYhnPnOmYT0bLDNX\n"
"U4KwHgUybVI5Db42ahr8eLH5g9zz2mbNWNWGCdgqwAXGYC3q5C00Ok5OGnNwtDLm\n"
"WJ375ck2a3x40TXh5KWOmhROWU7Stx8KJW200+sjUWDDCnAZZiZvnuUCnvDXB5E=\n"
"-----END CERTIFICATE-----\n";

#endif // CONFIG_H
