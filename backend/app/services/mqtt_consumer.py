import asyncio
import json
import logging
from datetime import datetime
import aiomqtt
from sqlalchemy import text, select
from app.config import settings
from app.database import AsyncSessionLocal, redis_client
from app.models.schema import TelemetryData, Device, User
from app.services.rules_engine import rules_engine

logger = logging.getLogger("MqttConsumer")

class MqttIngestionWorker:
    def __init__(self):
        self.host = settings.MQTT_BROKER_HOST
        self.port = settings.MQTT_BROKER_PORT
        self.username = settings.MQTT_USERNAME
        self.password = settings.MQTT_PASSWORD
        self.running = False

    async def start(self):
        """Continuous MQTT ingestion loop with automatic reconnection."""
        self.running = True
        logger.info(f"Connecting to MQTT Broker at {self.host}:{self.port}...")

        while self.running:
            try:
                async with aiomqtt.Client(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    keepalive=60
                ) as client:
                    logger.info("Connected to EMQX / MQTT broker. Subscribing to telemetry topics...")
                    await client.subscribe("devices/+/telemetry")
                    await client.subscribe("devices/+/telemetry/historical")

                    async for message in client.messages:
                        if not self.running:
                            break
                        await self._process_message(message)
            except aiomqtt.MqttError as err:
                logger.warning(f"MQTT connection lost: {err}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in MQTT loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    def stop(self):
        self.running = False

    async def _process_message(self, message):
        topic = str(message.topic)
        payload_str = message.payload.decode("utf-8")

        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning(f"Malformed JSON on {topic}: {payload_str}")
            return

        device_id = data.get("device_id")
        if not device_id:
            # Fallback parse device_id from topic
            parts = topic.split("/")
            device_id = parts[1] if len(parts) > 1 else "UNKNOWN"
            data["device_id"] = device_id

        # Update Redis cache with latest device state
        await redis_client.set(f"device:{device_id}:latest", json.dumps(data))

        # Persist to TimescaleDB
        ts = data.get("timestamp")
        sample_time = datetime.utcfromtimestamp(ts) if ts else datetime.utcnow()

        async with AsyncSessionLocal() as session:
            try:
                record = TelemetryData(
                    time=sample_time,
                    device_id=device_id,
                    grid_voltage_v=float(data.get("grid_v", 0.0)),
                    grid_status=bool(data.get("grid_on", False)),
                    pv_voltage_v=float(data.get("pv_v", 0.0)),
                    pv_power_w=float(data.get("pv_w", 0.0)),
                    battery_voltage_v=float(data.get("bat_v", 0.0)),
                    battery_soc_pct=float(data.get("bat_soc", 0.0)),
                    battery_current_a=float(data.get("bat_a", 0.0)),
                    output_active_power_w=float(data.get("load_w", 0.0)),
                    inverter_temp_c=float(data.get("temp_c", 0.0)),
                    fault_code=int(data.get("fault_code", 0)),
                    is_buffered=bool(data.get("buffered", False))
                )
                session.add(record)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to write telemetry to DB: {e}")

            # Fetch device metadata and user phone number for alerting
            device_meta = None
            recipient_phone = None
            try:
                stmt = select(Device, User).outerjoin(User, Device.user_id == User.id).where(Device.device_id == device_id)
                res = await session.execute(stmt)
                row = res.first()
                if row:
                    dev, usr = row
                    device_meta = {
                        "site_name": dev.site_name,
                        "battery_capacity_wh": dev.battery_capacity_wh,
                        "battery_cutoff_soc": dev.battery_cutoff_soc,
                        "battery_type": dev.battery_type
                    }
                    if usr and usr.phone_number:
                        recipient_phone = usr.phone_number
            except Exception as e:
                logger.debug(f"Device query fallback: {e}")

        # Run predictive rules engine evaluation
        try:
            await rules_engine.evaluate_telemetry(
                telemetry=data,
                device_meta=device_meta,
                recipient_phone=recipient_phone
            )
        except Exception as e:
            logger.error(f"Rules engine evaluation error: {e}", exc_info=True)

mqtt_worker = MqttIngestionWorker()
