import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.database import redis_client
from app.services.whatsapp_service import whatsapp_service

logger = logging.getLogger("RulesEngine")

class RulesEngine:
    @staticmethod
    def calculate_depletion_time_hours(
        battery_capacity_wh: float,
        current_soc_pct: float,
        cutoff_soc_pct: float,
        active_load_w: float
    ) -> float:
        """
        Calculates estimated time to battery cutoff depletion in hours:
        T_remaining = (Capacity_Wh * (SOC - Cutoff)) / Load_W
        """
        if active_load_w <= 0:
            return 999.0 # Infinite/no load

        usable_soc_fraction = (current_soc_pct - cutoff_soc_pct) / 100.0
        if usable_soc_fraction <= 0:
            return 0.0 # Depleted below cutoff

        usable_energy_wh = battery_capacity_wh * usable_soc_fraction
        return usable_energy_wh / active_load_w

    @staticmethod
    def format_hours_minutes(hours: float) -> str:
        if hours <= 0:
            return "0 minutes (Depleted)"
        total_mins = int(round(hours * 60))
        if total_mins < 60:
            return f"{total_mins} mins"
        h = total_mins // 60
        m = total_mins % 60
        return f"{h}h {m}m" if m > 0 else f"{h} hour{'s' if h > 1 else ''}"

    async def evaluate_telemetry(
        self,
        telemetry: Dict[str, Any],
        device_meta: Optional[Dict[str, Any]] = None,
        recipient_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main rules evaluation entrypoint executed upon telemetry ingestion.
        Returns evaluation results and triggered alert flags.
        """
        device_id = telemetry.get("device_id", "UNKNOWN")
        grid_status = bool(telemetry.get("grid_on", False))
        grid_v = float(telemetry.get("grid_v", 0.0))
        pv_w = float(telemetry.get("pv_w", 0.0))
        bat_soc = float(telemetry.get("bat_soc", 0.0))
        bat_v = float(telemetry.get("bat_v", 0.0))
        load_w = float(telemetry.get("load_w", 0.0))

        capacity_wh = float(device_meta.get("battery_capacity_wh", 10000.0)) if device_meta else 10000.0
        cutoff_soc = float(device_meta.get("battery_cutoff_soc", settings.DEFAULT_BATTERY_CUTOFF_SOC)) if device_meta else settings.DEFAULT_BATTERY_CUTOFF_SOC
        site_name = device_meta.get("site_name", f"Site {device_id}") if device_meta else f"Site {device_id}"

        results = {
            "device_id": device_id,
            "heavy_load_triggered": False,
            "grid_transition_triggered": False,
            "alerts": []
        }

        # ---------------------------------------------------------------------
        # RULE 1: Grid Transition Detection (NEPA Watcher)
        # ---------------------------------------------------------------------
        grid_state_key = f"device:{device_id}:last_grid_status"
        last_grid_status_str = await redis_client.get(grid_state_key)

        if last_grid_status_str is not None:
            last_grid_status = (last_grid_status_str == "1")
            if last_grid_status != grid_status:
                results["grid_transition_triggered"] = True
                if not grid_status:
                    # Transition: Grid Available -> Grid Down (NEPA Outage)
                    alert_msg = (
                        f"🔌 *GRID OUTAGE DETECTED (NEPA DOWN)* 🔌\n"
                        f"📍 *Site:* {site_name}\n"
                        f"Inverter has seamlessly switched to Battery & Solar.\n"
                        f"🔋 Battery: {bat_soc:.0f}% ({bat_v:.1f}V)\n"
                        f"☀️ Solar PV: {pv_w:,.0f} W\n"
                        f"🏠 Current Load: {load_w:,.0f} W\n"
                        f"_System operating on backup power._"
                    )
                    results["alerts"].append({"type": "GRID_OUTAGE", "message": alert_msg})
                    logger.info(f"Grid outage detected for device {device_id}")
                else:
                    # Transition: Grid Down -> Grid Available (NEPA Restored)
                    alert_msg = (
                        f"⚡ *GRID RESTORED (NEPA UP)* ⚡\n"
                        f"📍 *Site:* {site_name}\n"
                        f"AC Grid Voltage: {grid_v:.1f} V.\n"
                        f"Inverter switched to Grid Bypass & Battery Charging.\n"
                        f"🔋 Current SOC: {bat_soc:.0f}%\n"
                        f"_Batteries are safe and charging._"
                    )
                    results["alerts"].append({"type": "GRID_RESTORED", "message": alert_msg})
                    logger.info(f"Grid restoration detected for device {device_id}")

                if recipient_phone:
                    await whatsapp_service.send_text_message(recipient_phone, alert_msg)

        # Update latest grid status in Redis
        await redis_client.set(grid_state_key, "1" if grid_status else "0")

        # ---------------------------------------------------------------------
        # RULE 2: Critical Heavy Load Depletion Trigger
        # Condition: grid_status == 0 AND pv_w < 200 AND bat_soc < 40% AND load_w > 1500W
        # ---------------------------------------------------------------------
        is_heavy_load_condition = (
            (not grid_status) and
            (pv_w < settings.LOW_PV_THRESHOLD_WATTS) and
            (bat_soc < settings.CRITICAL_BATTERY_SOC) and
            (load_w > settings.HEAVY_LOAD_THRESHOLD_WATTS)
        )

        if is_heavy_load_condition:
            cooldown_key = f"cooldown:{device_id}:heavy_load"
            in_cooldown = await redis_client.exists(cooldown_key)

            hours_remaining = self.calculate_depletion_time_hours(
                battery_capacity_wh=capacity_wh,
                current_soc_pct=bat_soc,
                cutoff_soc_pct=cutoff_soc,
                active_load_w=load_w
            )
            time_str = self.format_hours_minutes(hours_remaining)

            results["heavy_load_triggered"] = True
            results["depletion_hours"] = hours_remaining

            if not in_cooldown:
                alert_msg = (
                    f"🚨 *CRITICAL BATTERY & HEAVY LOAD ALERT* 🚨\n"
                    f"📍 *Site:* {site_name}\n"
                    f"-----------------------------------------\n"
                    f"🔌 Grid: *DOWN* | ☀️ Solar: *{pv_w:.0f}W* (Minimal)\n"
                    f"🔋 Battery: *{bat_soc:.0f}%* (Cutoff limit: {cutoff_soc:.0f}%)\n"
                    f"⚡ Current Load: *{load_w:,.0f} W* (High Drain!)\n"
                    f"-----------------------------------------\n"
                    f"⏳ *Estimated Depletion:* *{time_str}*!\n\n"
                    f"⚠️ *Action Required:* Please turn off heavy appliances "
                    f"(Air Conditioners, Pumping Machines, Freezers, Heaters) "
                    f"to prevent an unexpected inverter shutdown!"
                )
                results["alerts"].append({"type": "HEAVY_LOAD_CRITICAL", "message": alert_msg})
                logger.warning(f"CRITICAL HEAVY LOAD for device {device_id}: {time_str} remaining")

                # Set 30-minute cooldown
                await redis_client.setex(cooldown_key, settings.ALERT_COOLDOWN_SECONDS, "1")

                if recipient_phone:
                    await whatsapp_service.send_text_message(recipient_phone, alert_msg)
            else:
                logger.info(f"Heavy load alert suppressed for {device_id} due to 30-min cooldown")

        return results

rules_engine = RulesEngine()
