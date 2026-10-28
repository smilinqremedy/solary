import asyncio
import time
import math
import logging
from typing import Dict, Any, List
from datetime import datetime
from app.config import settings
from app.database import redis_client, AsyncSessionLocal
from app.models.schema import TelemetryData, Device, User
from app.services.rules_engine import rules_engine
from app.services.analytics_service import analytics_service

logger = logging.getLogger("LiveSimulator")

class LiveTelemetrySimulator:
    def __init__(self):
        self.device_id = "NG-INV-00124"
        self.running = False
        
        # State variables
        self.grid_on = True
        self.grid_v = 226.4
        self.pv_w = 2650.0
        self.pv_v = 76.2
        self.bat_v = 52.8
        self.bat_soc = 86.0
        self.bat_a = 16.4
        self.load_w = 680.0
        self.temp_c = 38.2
        self.fault_code = 0
        self.wifi_connected = True
        self.buffered_count = 0
        
        # Simulation step counter
        self.step = 0
        self.recent_alerts: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []

    def set_scenario(self, scenario: str) -> str:
        """Modifies live simulation parameters to demonstrate Nigerian grid events."""
        if scenario == "toggle_grid":
            self.grid_on = not self.grid_on
            self.grid_v = 228.0 if self.grid_on else 0.0
            return f"Grid toggled: {'⚡ AVAILABLE (228V)' if self.grid_on else '🔌 OUTAGE (NEPA DOWN)'}"

        elif scenario == "heavy_load":
            self.load_w = 2750.0 # High inductive load (AC + Freezer + Pumping)
            if not self.grid_on:
                self.bat_a = -52.0
            return f"Heavy Load Injected: {self.load_w:,.0f} W"

        elif scenario == "normal_load":
            self.load_w = 650.0
            return f"Load normalized: {self.load_w:,.0f} W"

        elif scenario == "cloud_drop":
            self.pv_w = 120.0 # Low irradiance
            self.pv_v = 34.0
            return f"Solar irradiance dropped to {self.pv_w} W (Heavy cloud cover)"

        elif scenario == "sunshine":
            self.pv_w = 3100.0 # Peak tropical sunshine
            self.pv_v = 78.5
            return f"Solar generation surged to {self.pv_w:,.0f} W (Peak sunshine)"

        elif scenario == "low_battery":
            self.bat_soc = 32.0
            self.bat_v = 49.2
            return f"Battery SOC set to critical 32% ({self.bat_v}V)"

        elif scenario == "toggle_wifi":
            self.wifi_connected = not self.wifi_connected
            if not self.wifi_connected:
                return "Wi-Fi link disconnected. ESP32 LittleFS circular buffer is now accumulating offline records!"
            else:
                flushed = self.buffered_count
                self.buffered_count = 0
                return f"Wi-Fi link restored. Flushed {flushed} offline records to cloud MQTT!"

        return "Unknown scenario"

    def get_current_telemetry(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "timestamp": int(time.time()),
            "grid_v": round(self.grid_v, 1),
            "grid_on": self.grid_on,
            "pv_v": round(self.pv_v, 1),
            "pv_w": int(round(self.pv_w)),
            "bat_v": round(self.bat_v, 1),
            "bat_soc": int(round(self.bat_soc)),
            "bat_a": round(self.bat_a, 1),
            "load_w": int(round(self.load_w)),
            "temp_c": round(self.temp_c, 1),
            "fault_code": self.fault_code,
            "wifi_connected": self.wifi_connected,
            "buffered_count": self.buffered_count
        }

    async def start(self):
        self.running = True
        logger.info("Live Telemetry Simulator started. Generating real-time 5-second inverter telemetry...")

        # Add initial welcome in chat history
        self.chat_history.append({
            "sender": "bot",
            "time": datetime.now().strftime("%H:%M:%S"),
            "text": "👋 *Solary Energy Intelligence Assistant is Online!*\nSolary is monitoring Lekki Phase 1 Hybrid Inverter 24/7.\nReply *Status*, *Health*, or *Savings* anytime."
        })

        while self.running:
            self.step += 1
            now = time.time()

            # Natural slight oscillations to mimic real-world solar sensor noise
            noise = math.sin(self.step * 0.2) * 15.0
            temp_noise = math.cos(self.step * 0.1) * 0.4
            self.temp_c = 37.5 + temp_noise

            if self.grid_on:
                self.grid_v = 224.0 + math.sin(self.step * 0.15) * 4.5
            else:
                self.grid_v = 0.0

            # Dynamic battery charge/discharge behavior
            if self.grid_on:
                # Grid available: Inverter charges battery or runs load
                net_power = (self.pv_w - self.load_w) + 1200.0 # grid charger boost
                if net_power > 0:
                    self.bat_a = min(40.0, net_power / max(self.bat_v, 48.0))
                    self.bat_soc = min(100.0, self.bat_soc + 0.15)
                else:
                    self.bat_a = 0.0
            else:
                # Inverter in battery backup mode (NEPA down)
                net_power = self.pv_w - self.load_w
                if net_power >= 0:
                    self.bat_a = net_power / max(self.bat_v, 48.0)
                    self.bat_soc = min(100.0, self.bat_soc + 0.08)
                else:
                    self.bat_a = net_power / max(self.bat_v, 48.0) # Negative current = discharge
                    soc_drain = (abs(net_power) / 10000.0) * (3.0 / 3600.0) * 100.0
                    self.bat_soc = max(10.0, self.bat_soc - soc_drain)

            self.bat_v = 47.0 + (self.bat_soc / 100.0) * 6.5

            if not self.wifi_connected:
                self.buffered_count = min(1500, self.buffered_count + 1)

            telemetry = self.get_current_telemetry()

            # Cache to Redis
            try:
                import json
                await redis_client.set(f"device:{self.device_id}:latest", json.dumps(telemetry))
            except Exception:
                pass

            # Evaluate rules engine
            device_meta = {
                "site_name": "Lekki Phase 1 Residential Hybrid",
                "battery_capacity_wh": 10000.0,
                "battery_cutoff_soc": 10.0,
                "battery_type": "LiFePO4 (48V 200Ah)"
            }

            eval_results = await rules_engine.evaluate_telemetry(
                telemetry=telemetry,
                device_meta=device_meta,
                recipient_phone="+2348031234567"
            )

            # If alerts triggered, record to live history
            for alert in eval_results.get("alerts", []):
                alert_entry = {
                    "type": alert["type"],
                    "message": alert["message"],
                    "time": datetime.now().strftime("%H:%M:%S")
                }
                self.recent_alerts.append(alert_entry)
                self.chat_history.append({
                    "sender": "bot",
                    "time": alert_entry["time"],
                    "text": alert["message"]
                })
                logger.info(f"Live Alert Generated: {alert['type']}")

            # Sleep 2.5 seconds per simulation cycle
            await asyncio.sleep(2.5)

    def stop(self):
        self.running = False

live_simulator = LiveTelemetrySimulator()
