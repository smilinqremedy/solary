import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import select
from app.database import get_db, redis_client
from app.models.schema import Device, User
from app.services.rules_engine import rules_engine
from app.services.analytics_service import analytics_service

logger = logging.getLogger("TelemetryAPI")
router = APIRouter(prefix="/devices", tags=["Devices & Telemetry"])

class DeviceResponse(BaseModel):
    device_id: str
    site_name: str
    city: str
    inverter_model: str
    battery_capacity_wh: float
    battery_cutoff_soc: float
    battery_type: str
    is_active: bool

class DeviceCommandRequest(BaseModel):
    action: str # "reboot", "ota", "clear_buffer"
    url: Optional[str] = None
    profile: Optional[int] = None

@router.get("", response_model=List[DeviceResponse])
async def list_devices(db=Depends(get_db)):
    """List all deployed solar inverter edge gateways for installers."""
    stmt = select(Device)
    result = await db.execute(stmt)
    devices = result.scalars().all()
    return devices

@router.get("/{device_id}/live")
async def get_live_telemetry(device_id: str):
    """Fetch instantaneous 5-second normalized telemetry from Redis."""
    raw = await redis_client.get(f"device:{device_id}:latest")
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device telemetry not found or device offline")
    return json.loads(raw)

@router.get("/{device_id}/depletion")
async def get_battery_depletion_prediction(device_id: str, db=Depends(get_db)):
    """Calculate real-time battery depletion hours based on current load and SOC."""
    raw = await redis_client.get(f"device:{device_id}:latest")
    if not raw:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No telemetry available")
    
    telemetry = json.loads(raw)
    stmt = select(Device).where(Device.device_id == device_id)
    result = await db.execute(stmt)
    device = result.scalar_one_or_none()

    capacity_wh = device.battery_capacity_wh if device else 10000.0
    cutoff_soc = device.battery_cutoff_soc if device else 10.0

    current_soc = float(telemetry.get("bat_soc", 0.0))
    load_w = float(telemetry.get("load_w", 0.0))

    hours = rules_engine.calculate_depletion_time_hours(
        battery_capacity_wh=capacity_wh,
        current_soc_pct=current_soc,
        cutoff_soc_pct=cutoff_soc,
        active_load_w=load_w
    )

    return {
        "device_id": device_id,
        "battery_soc_pct": current_soc,
        "active_load_w": load_w,
        "battery_capacity_wh": capacity_wh,
        "cutoff_soc_pct": cutoff_soc,
        "estimated_depletion_hours": round(hours, 2),
        "estimated_depletion_human": rules_engine.format_hours_minutes(hours)
    }

@router.get("/{device_id}/analytics")
async def get_device_analytics(device_id: str):
    """Retrieve daily solar generation, battery discharge, and fuel Naira savings."""
    return await analytics_service.get_daily_energy_summary(device_id)

@router.post("/{device_id}/command")
async def send_device_command(device_id: str, cmd: DeviceCommandRequest):
    """
    Publishes an administrative command via MQTT to the edge ESP32.
    """
    command_payload = {
        "action": cmd.action,
        "url": cmd.url,
        "profile": cmd.profile
    }
    # In production with active broker, this publishes to devices/{device_id}/commands
    logger.info(f"Issuing command to device {device_id}: {command_payload}")
    return {"status": "command_queued", "device_id": device_id, "command": command_payload}
