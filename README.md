# ☀️ Solary: IoT Solar Energy Intelligence & WhatsApp Alerting Platform

[![Product Name: Solary](https://img.shields.io/badge/Platform-Solary-amber.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Microcontroller](https://img.shields.io/badge/Microcontroller-ESP32--WROOM--32-blue.svg)](https://www.espressif.com/)
[![Protocol](https://img.shields.io/badge/Protocol-Modbus_RTU_%2F_MQTTS_8883-orange.svg)]()
[![Cloud API](https://img.shields.io/badge/Meta-WhatsApp_Cloud_API-green.svg)](https://developers.facebook.com/docs/whatsapp/cloud-api)
[![Framework](https://img.shields.io/badge/Backend-FastAPI_%2F_TimescaleDB_%2F_Redis-teal.svg)](https://fastapi.tiangolo.com/)

**Solary** is an end-to-end, production-grade IoT Energy Intelligence and Conversational WhatsApp Alerting Platform engineered specifically for the Nigerian solar/inverter market.

Solary continuously extracts normalized telemetry from hybrid solar inverters and battery banks via RS485 / Modbus RTU using an ESP32 microcontroller, publishes telemetry to an MQTT broker over TLS, processes anomalies with a predictive rules engine, and delivers conversational analytics and critical alerts to homeowners and installers via the **Meta WhatsApp Cloud API**.

---

## 📑 Table of Contents
1. [Nigerian Market Context & Engineering Challenges](#1-nigerian-market-context--engineering-challenges)
2. [End-to-End System Architecture](#2-end-to-end-system-architecture)
3. [Module 1: Edge Firmware (ESP32)](#3-module-1-edge-firmware-esp32)
   - [Hardware Wiring & Pinout Guide](#hardware-wiring--pinout-guide)
   - [FreeRTOS Multi-Tasking Architecture](#freertos-multi-tasking-architecture)
   - [Offline Circular Flash Storage (LittleFS Buffer)](#offline-circular-flash-storage-littlefs-buffer)
   - [Failover Network Stack (Wi-Fi + GSM/LTE)](#failover-network-stack-wi-fi--gsmlte)
   - [MQTT JSON Telemetry Specification](#mqtt-json-telemetry-specification)
4. [Inverter Modbus Register Mapping](#4-inverter-modbus-register-mapping)
5. [Module 2: Cloud Ingestion, Database & Rules Engine](#5-module-2-cloud-ingestion-database--rules-engine)
   - [Critical Heavy Load & Depletion Formula](#critical-heavy-load--depletion-formula)
   - [NEPA Grid Transition Watcher](#nepa-grid-transition-watcher)
   - [Midnight Summary & Fuel Savings Formula](#midnight-summary--fuel-savings-formula)
6. [Module 3: WhatsApp Bot Interface (Meta Cloud API)](#6-module-3-whatsapp-bot-interface-meta-cloud-api)
   - [Webhook Verification & HMAC SHA-256 Security](#webhook-verification--hmac-sha-256-security)
   - [Interactive Conversational Commands](#interactive-conversational-commands)
7. [Quick Start & Deployment](#7-quick-start--deployment)

---

## 1. Nigerian Market Context & Engineering Challenges

In Nigeria, over 70% of residential and commercial solar installations operate in a uniquely demanding environment:
- **Frequent Grid Outages (NEPA/PHCN Drops):** The national grid collapses or experiences load-shedding multiple times weekly. Inverters frequently transition between grid bypass, battery inversion, and solar blending.
- **Generator Co-existence & Fuel Economics:** Fuel prices (PMS / Petrol) have surged to **~₦1,150+ per liter**. Homeowners need tangible justification for their solar investments in terms of daily generator fuel liters displaced and Naira saved.
- **Unattended Battery Depletion:** When the grid drops at night or during heavy cloud cover, unmonitored heavy inductive loads (air conditioners, pumping machines, deep freezers) drain lithium/gel battery banks to zero within minutes, risking sudden blackout and premature battery degradation.
- **Telco Downtime & Local Internet Blackouts:** Grid collapse often causes nearby cellular base stations to drop or home Wi-Fi routers to lose power for 30 minutes to 2 hours. **Edge telemetry cannot be lost during connectivity blackouts.**

This platform was architected specifically to solve these challenges with edge resilience, offline flash queueing, automated failover, and conversational WhatsApp notifications where Nigerians already communicate.

---

## 2. End-to-End System Architecture

```mermaid
flowchart TD
    subgraph EdgeTier ["ESP32 Edge Gateway (C++ FreeRTOS)"]
        INV["Hybrid Inverter\n(Growatt / Must / Felicity)"]
        MAX["MAX485 / SP3485\n(UART2: GPIO16/17, DE/RE: GPIO4)"]
        T1["Task 1: Modbus Polling (Core 1, 5s)"]
        T2["Task 2: Net & MQTT (Core 0)"]
        T3["Task 3: Watchdog (Core 0, 15s)"]
        BUF["LittleFS Offline Buffer\n(1,500 records / 2-hr ring)"]
        NET{"Wi-Fi Available?"}
        WIFI["Wi-Fi STA\n(Captive Portal Fallback)"]
        GSM["Cellular GSM/LTE\n(SIM800L / A7670E)"]

        INV -->|RS485 / Modbus RTU 9600 8N1| MAX
        MAX --> T1
        T1 -->|FreeRTOS Queue| T2
        T2 -->|Connection Lost| BUF
        BUF -->|Auto-Flush on Reconnect| T2
        T2 --> NET
        NET -->|Yes| WIFI
        NET -->|No (60s timeout)| GSM
    end

    subgraph CloudTier ["Cloud Infrastructure (Docker Compose)"]
        BRK["EMQX Broker (MQTTS 8883 / TLS)"]
        ING["FastAPI Ingestion Worker\n(aiomqtt consumer)"]
        TSDB[("TimescaleDB / PostgreSQL\n(Time-series Hypertables)")]
        REDIS[("Redis Cache & Rate Limiter\n(30-min Cooldowns & State)")]
        RULES["Predictive Rules Engine\n(Depletion & Grid Watcher)"]
        ANALYTICS["Midnight Analytics Service\n(Fuel & Naira Savings)"]

        WIFI -->|MQTTS TLS| BRK
        GSM -->|MQTTS TLS| BRK
        BRK --> ING
        ING --> TSDB
        ING --> REDIS
        ING --> RULES
        RULES --> REDIS
        ANALYTICS --> TSDB
    end

    subgraph InterfaceTier ["Conversational & Management Layer"]
        META["Meta WhatsApp Cloud API\n(HMAC-SHA256 Webhook)"]
        BOT["WhatsApp Interactive Assistant\n(Status, Health, Savings)"]
        DASH["B2B Installer REST API\n(/api/v1/devices)"]
        USER(("Homeowner WhatsApp\n(+234...)"))
        INSTALLER(("Solar Installer / Tech\n(Fleet Monitoring)"))

        RULES -->|Critical Alert Dispatch| META
        ANALYTICS -->|Midnight Summary Dispatch| META
        META <--> BOT
        BOT <--> REDIS
        BOT <--> TSDB
        META <--> USER
        DASH <--> INSTALLER
    end
```

---

## 3. Module 1: Edge Firmware (ESP32)

The edge firmware is implemented in production-grade C++ targeting the **ESP32-WROOM-32** dual-core microcontroller (240MHz, 4MB Flash).

### Hardware Wiring & Pinout Guide

| ESP32 GPIO Pin | Module / Interface | Description / Direction |
| :--- | :--- | :--- |
| **GPIO 16** | MAX485 `RO` | Hardware UART2 RX (Receives RS485 from Inverter) |
| **GPIO 17** | MAX485 `DI` | Hardware UART2 TX (Transmits RS485 to Inverter) |
| **GPIO 4** | MAX485 `DE` & `RE` | Direction Control (HIGH = Transmit, LOW = Receive) |
| **GPIO 25** | SIM800L / A7670E `TXD` | Hardware UART1 RX (Cellular fallback) |
| **GPIO 26** | SIM800L / A7670E `RXD` | Hardware UART1 TX (Cellular fallback) |
| **GPIO 27** | GSM Modem `PWRKEY` | Modem Power Key Pulse control |
| **GPIO 14** | GSM Modem `RST` | Hardware Reset line for cellular modem |
| **GPIO 2** | Built-in Blue LED | Wi-Fi / Network Status Indicator |
| **GPIO 15** | External Green LED | Modbus RS485 Communication Activity |
| **GPIO 13** | External Red LED | Offline Buffer Flush / Inverter Error Indicator |

#### Inverter Communication Port Pinout (RJ45 / Terminal)

```
       RJ45 Male Plug (Standard T-568B)
        ┌───┬───┬───┬───┬───┬───┬───┬───┐
Pin #:  │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │
        └───┴───┴───┴───┴───┴───┴───┴───┘
```
- **Growatt SPF 3000/5000 ES:** Pin 1 = `RS485-B` (D-), Pin 2 = `RS485-A` (D+), Pin 8 = `GND`.
- **Must Solar PV1800/PH1800:** Pin 7 = `RS485-A` (D+), Pin 8 = `RS485-B` (D-), Pin 6 = `GND`.
- **Felicity Solar IVEM:** Pin 1 = `RS485-A` (D+), Pin 2 = `RS485-B` (D-).

> [!IMPORTANT]
> Always place a **120Ω termination resistor** across `RS485-A` and `RS485-B` at the edge gateway to eliminate signal reflections on cable runs exceeding 5 meters.

---

### FreeRTOS Multi-Tasking Architecture

To guarantee that network drops or cryptographic TLS handshakes never stall time-critical Modbus polling, the firmware isolates responsibilities into three dedicated FreeRTOS tasks pinned across the ESP32 dual cores:

1. **Task 1: `modbusPollingTask` (Core 1, Priority 3 - High)**
   - Executes deterministically every 5,000ms using `vTaskDelayUntil()`.
   - Polls the inverter's Modbus RTU registers via MAX485 with microsecond DE/RE line toggling.
   - Normalizes physical metrics and places the frame into FreeRTOS `xQueueTelemetry` (depth 10).
   - Feeds the hardware Task Watchdog Timer (TWDT).

2. **Task 2: `networkMqttTask` (Core 0, Priority 2 - Medium)**
   - Manages Wi-Fi STA and GSM cellular failover state machine.
   - Establishes MQTTS over TLS (port 8883) with X.509 Root CA verification.
   - Dequeues frames from `xQueueTelemetry`:
     - If MQTT is online: publishes real-time JSON to `devices/{device_id}/telemetry`.
     - Then drains the LittleFS offline buffer in batches of 5 records to `devices/{device_id}/telemetry/historical`.
     - If network/broker is offline: immediately appends the record into the LittleFS flash queue.
   - Listens for remote administrative commands (Signed OTA firmware upgrades, remote reboot).

3. **Task 3: `watchdogTask` (Core 0, Priority 1 - Low)**
   - Monitors FreeRTOS thread health and free heap integrity.
   - Drives system status LEDs (heartbeat, buffer alert).
   - Enforces a 15-second hardware restart via ESP-IDF Task Watchdog Timer if any task deadlocks.

---

### Offline Circular Flash Storage (LittleFS Buffer)

To withstand Nigerian power drops where both Wi-Fi and local cellular towers lose auxiliary power:
- The firmware partitions 1.5 MB of ESP32 flash memory for **LittleFS**.
- Stores up to **1,500 telemetry records** (representing **2 continuous hours** of 5-second sampling).
- Telemetry records are stored in a binary packed struct (`InverterTelemetry`, ~56 bytes per record) to reduce flash wear and write latency to under 2ms.
- An atomic metadata header (`telemetry_meta.bin`) tracks `head_index`, `tail_index`, and `stored_count` with **32-bit FNV-1a CRC checksums**.
- If the buffer reaches maximum capacity before reconnection, it adopts an automatic **FIFO circular overwrite** strategy (oldest telemetry is retired first to preserve the latest emergency window).
- Upon link restoration, the buffer drains at 5 records per loop to avoid network congestion while real-time publishing continues uninterrupted.

---

### Failover Network Stack (Wi-Fi + GSM/LTE)

1. **Primary Interface (Wi-Fi):**
   - Connects to home/business Wi-Fi with static/DHCP configuration.
   - If Wi-Fi credentials are unset or the access point disappears, it starts an on-demand **`WiFiManager` Captive Portal AP** (`NG-Solar-Setup-NG-INV-00124`) with a 120-second timeout.
2. **Cellular Fallback (GSM / LTE):**
   - If Wi-Fi remains down for > 60 seconds (`NETWORK_FAILOVER_TIMEOUT`), the firmware switches power to the cellular modem (SIM800L or A7670E) via GPIO27.
   - Attaches GPRS over APN (`web.gprs.mtnnigeria.net` for MTN, `airtelgprs.com` for Airtel).
   - Seamlessly maintains MQTTS connection until Wi-Fi availability is re-verified.

---

### MQTT JSON Telemetry Specification

The edge gateway structures its real-time telemetry payload into a compact JSON schema:

```json
{
  "device_id": "NG-INV-00124",
  "timestamp": 1729854000,
  "grid_v": 224.5,
  "grid_on": true,
  "pv_w": 2450,
  "bat_v": 52.4,
  "bat_soc": 82,
  "bat_a": 15.2,
  "load_w": 620,
  "temp_c": 38.2,
  "fault_code": 0
}
```

When flushed from the LittleFS offline queue, records append `"buffered": true` to distinguish historical data from live feeds:

```json
{
  "device_id": "NG-INV-00124",
  "timestamp": 1729849200,
  "grid_v": 0.0,
  "grid_on": false,
  "pv_w": 180,
  "bat_v": 49.8,
  "bat_soc": 38,
  "bat_a": -24.6,
  "load_w": 1850,
  "temp_c": 39.5,
  "fault_code": 0,
  "buffered": true
}
```

---

## 4. Inverter Modbus Register Mapping

The edge gateway normalizes register layouts across major hybrid inverter brands deployed in Nigeria:

| Normalized Field | Unit | Growatt SPF 3000/5000 ES (FC 0x04) | Must PV1800 / PH1800 (FC 0x03) | Felicity Solar IVEM (FC 0x03) |
| :--- | :--- | :--- | :--- | :--- |
| `grid_voltage_v` | Volts | Reg 20 (Scale: 0.1) | Reg 10107 (Scale: 0.1) | Reg 200 (Scale: 0.1) |
| `grid_status` | Boolean | Reg 20 > 90V && Reg 0 != 0 | Reg 10107 > 90V | Reg 200 > 85V |
| `pv_voltage_v` | Volts | Reg 1 (Scale: 0.1) | Reg 10115 (Scale: 0.1) | Reg 202 (Scale: 0.1) |
| `pv_power_w` | Watts | Reg 3 & 4 (32-bit, Scale: 0.1) | Reg 10116 (Scale: 1.0) | Reg 203 (Scale: 1.0) |
| `battery_voltage_v` | Volts | Reg 17 (Scale: 0.01) | Reg 10104 (Scale: 0.1) | Reg 204 (Scale: 0.1) |
| `battery_soc_pct` | % | Reg 18 (Scale: 1.0) | Reg 10106 (Scale: 1.0) | Reg 205 (Scale: 1.0) |
| `battery_current_a` | Amps | Reg 29 (Scale: 0.1, Signed) | Reg 10105 (Scale: 0.1, Signed) | Reg 206 (Scale: 0.1, Signed) |
| `output_active_power_w`| Watts | Reg 22 (Scale: 0.1) | Reg 10110 (Scale: 1.0) | Reg 208 (Scale: 1.0) |
| `inverter_temp_c` | °C | Reg 25 (Scale: 0.1) | Reg 10121 (Scale: 0.1) | Reg 210 (Scale: 0.1) |
| `fault_code` | Hex/Int | Reg 44 | Reg 10123 | Reg 212 |

---

## 5. Module 2: Cloud Ingestion, Database & Rules Engine

The cloud tier is built with **FastAPI**, **TimescaleDB / PostgreSQL**, and **Redis**.

### Critical Heavy Load & Depletion Formula

When the national grid drops, solar irradiance is low, and the household runs high-wattage inductive loads, battery depletion occurs rapidly.

#### Trigger Condition:
$$\text{grid\_status} == 0 \quad \text{AND} \quad \text{pv\_power\_w} < 200\text{W} \quad \text{AND} \quad \text{battery\_soc\_pct} < 40\% \quad \text{AND} \quad \text{load\_w} > 1500\text{W}$$

#### Predictive Depletion Calculation:
$$T_{\text{remaining}} = \frac{\text{Battery Capacity (Wh)} \times \left(\frac{\text{Current SOC} - \text{Cutoff SOC}}{100}\right)}{\text{Active Load (W)}}$$

*Example:* A 10,000 Wh (10 kWh) LiFePO4 battery bank with 10% cutoff, current SOC at 35%, and a heavy load of 2,500W:
$$T_{\text{remaining}} = \frac{10000 \times (0.35 - 0.10)}{2500} = \frac{2500}{2500} = 1.0\text{ hour (60 minutes)}$$

#### Spam Prevention (30-Minute Cooldown):
To prevent message bombing when loads fluctuate around 1,500W, the rules engine sets a Redis key:
`cooldown:{device_id}:heavy_load` with TTL = 1,800 seconds (30 minutes).

#### Dispatched WhatsApp Alert:
```
🚨 CRITICAL BATTERY & HEAVY LOAD ALERT 🚨
📍 Site: Lekki Phase 1 Residential Hybrid
-----------------------------------------
🔌 Grid: DOWN | ☀️ Solar: 120W (Minimal)
🔋 Battery: 35% (Cutoff limit: 10%)
⚡ Current Load: 2,500 W (High Drain!)
-----------------------------------------
⏳ Estimated Depletion: 1 hour!

⚠️ Action Required: Please turn off heavy appliances
(Air Conditioners, Pumping Machines, Freezers, Heaters)
to prevent an unexpected inverter shutdown!
```

---

### NEPA Grid Transition Watcher

Transitions between the national grid and battery power are tracked in Redis (`device:{device_id}:last_grid_status`):
- **Grid Available ➔ Grid Down:** Dispatches an immediate outage alert so users are aware that their home is running exclusively on backup power.
- **Grid Down ➔ Grid Available:** Dispatches a restoration alert confirming grid voltage and indicating that batteries are entering bypass/charging mode.

---

### Midnight Summary & Fuel Savings Formula

At 00:00 midnight WAT, the analytics worker computes the 24-hour integrals from TimescaleDB:
- $\text{Daily Solar Yield (kWh)} = \int_0^{24} \text{PV Power}(t) \, dt$
- $\text{Battery Discharge (kWh)} = \int_0^{24} |\text{Battery Power}_{\text{discharge}}(t)| \, dt$

#### Generator Fuel Displacement Calculation:
Small and medium petrol generators common in Nigeria consume approximately **0.35 Liters of petrol per kWh** generated:
$$\text{Fuel Displaced (Liters)} = \text{Solar Yield (kWh)} \times 0.35$$
$$\text{Money Saved (₦)} = \text{Fuel Displaced (Liters)} \times \text{Fuel Price per Liter (e.g. ₦1,150)}$$

*Example for an 18.5 kWh solar day:*
$$\text{Fuel Displaced} = 18.5 \times 0.35 = 6.48\text{ Liters}$$
$$\text{Daily Money Saved} = 6.48 \times 1,150 = \mathbf{₦7,452.00}$$
$$\text{Estimated Monthly Savings} \approx \mathbf{₦223,560.00 / month}$$

---

## 6. Module 3: WhatsApp Bot Interface (Meta Cloud API)

### Webhook Verification & HMAC SHA-256 Security

The backend exposes `GET /api/v1/whatsapp/webhook` for Meta challenge registration and `POST /api/v1/whatsapp/webhook` for inbound messages.
Every incoming webhook is verified by computing the **HMAC-SHA256 signature** over the raw request payload with the Meta App Secret and matching it against the `X-Hub-Signature-256` header.

### Interactive Conversational Commands

Homeowners and facility managers can query their solar system naturally:

| User Query | Action / System Response |
| :--- | :--- |
| **`"Status"`** or **`"1"`** | Returns real-time Grid status, Solar W, Battery %, Battery Mode (Charging/Discharging), Current Load W, and Inverter Temp. |
| **`"Health"`** or **`"2"`** | Runs cell voltage sag analysis under load, checks operating temperature against thermal limits, and reports estimated cycle count. |
| **`"Savings"`** or **`"3"`** | Summarizes today's and this month's solar kWh yield, petrol generator liters displaced, and Naira money saved. |
| *Any other message* | Returns the interactive welcome and help menu with guided commands. |

#### Conversational WhatsApp Sample:
```
⚡ SOLAR ENERGY STATUS ⚡
📍 Site: Lekki Phase 1 Residential Hybrid
----------------------------------
🔌 Grid (NEPA): 🔴 Down / Outage
☀️ Solar Generation: 3,420 W
🔋 Battery: 86% (52.6V) - ⚡ Charging
🏠 Facility Load: 1,120 W
🌡️ Inverter Temp: 37.8°C
----------------------------------
💡 Summary: Solar is actively supplying load & topping up battery.

Reply 'Savings' for fuel ROI or 'Health' for battery check.
```

---

## 7. Quick Start & Deployment

### Edge Gateway Setup (PlatformIO)

1. Clone repository and navigate to firmware directory:
   ```bash
   cd nigeria-solar-intelligence/firmware
   ```
2. Build and flash the firmware to your ESP32-WROOM-32 via USB:
   ```bash
   pio run -t upload -t monitor
   ```
3. Connect to the Wi-Fi setup AP (`NG-Solar-Setup-NG-INV-00124`) using a phone to configure local Wi-Fi, or insert an MTN/Airtel SIM card for automatic cellular failover.

### Cloud Infrastructure Setup (Docker Compose)

1. Copy `.env.example` and set your credentials:
   ```bash
   cd nigeria-solar-intelligence
   cp .env.example .env
   ```
2. Launch EMQX Broker, TimescaleDB, Redis, and FastAPI Backend:
   ```bash
   docker-compose up -d --build
   ```
3. Check container status:
   ```bash
   docker-compose ps
   ```
4. Access services:
   - **FastAPI Documentation:** `http://localhost:8000/docs`
   - **EMQX Web Dashboard:** `http://localhost:18083` (Default login: `admin` / `public`)
   - **Health Check:** `http://localhost:8000/health`

### Running Unit Tests

Verify the rules engine, predictive depletion formulas, fuel savings math, and HMAC signature algorithms:
```bash
python3 -m unittest discover tests
```

---

## 📜 Architectural Summary & Hardware Bill of Materials (BOM)

| Component | Recommended Model | Est. Cost (NGN) |
| :--- | :--- | :--- |
| Microcontroller | ESP32-WROOM-32D Development Board | ~₦4,500 |
| RS485 Transceiver | MAX485 or SP3485 (3.3V compatible) | ~₦1,200 |
| Cellular Modem | SIM800L or A7670E 4G LTE Module | ~₦9,500 |
| Power Supply | Mini 12V/48V to 5V 3A DC-DC Buck Converter (powered from battery bus) | ~₦3,000 |
| Enclosure | IP65 Wall-mount Din-Rail Enclosure | ~₦3,500 |
| **Total Hardware Cost** | **Complete Industrial IoT Edge Node** | **~₦21,700 ($14 USD)** |

---

## 🛡️ License
Released under the MIT License. Built for energy resilience across Nigeria and emerging solar markets.
