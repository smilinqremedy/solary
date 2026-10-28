import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db, redis_client, AsyncSessionLocal
from app.models.schema import Device, User
from app.api.whatsapp_webhook import router as whatsapp_router
from app.api.telemetry_api import router as telemetry_router
from app.api.live_dashboard_api import router as live_dashboard_router
from app.services.mqtt_consumer import mqtt_worker
from app.services.live_telemetry_simulator import live_simulator
from sqlalchemy import select

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SolarIntelligenceApp")

async def seed_demo_data():
    """Seeds default demo device and user for instant evaluation."""
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(Device).where(Device.device_id == "NG-INV-00124"))
            if not res.scalar_one_or_none():
                user = User(
                    full_name="Olumide Adebayo",
                    phone_number="+2348031234567",
                    email="olumide@example.ng",
                    role="client"
                )
                session.add(user)
                await session.flush()

                device = Device(
                    device_id="NG-INV-00124",
                    user_id=user.id,
                    site_name="Lekki Phase 1 Residential Hybrid",
                    city="Lagos",
                    inverter_model="Growatt SPF 5000 ES",
                    battery_capacity_wh=10000.0,
                    battery_cutoff_soc=10.0,
                    battery_type="LiFePO4 (48V 200Ah)"
                )
                session.add(device)
                await session.commit()
                logger.info("Seeded initial demo device NG-INV-00124 with Lekki Phase 1 profile.")
    except Exception as e:
        logger.warning(f"Demo seeding fallback: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Solar Intelligence Platform...")
    await init_db()
    await seed_demo_data()

    # Launch background live simulator task
    simulator_task = asyncio.create_task(live_simulator.start())

    # Attempt MQTT worker connection
    mqtt_task = asyncio.create_task(mqtt_worker.start())

    yield

    logger.info("Shutting down Solar Intelligence Platform...")
    live_simulator.stop()
    simulator_task.cancel()
    mqtt_worker.stop()
    mqtt_task.cancel()
    if hasattr(redis_client, "aclose"):
        await redis_client.aclose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="IoT Energy Intelligence & WhatsApp Alerting Platform tailored for the Nigerian solar/inverter market.",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(live_dashboard_router)
app.include_router(whatsapp_router, prefix=settings.API_V1_PREFIX)
app.include_router(telemetry_router, prefix=settings.API_V1_PREFIX)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "region": "Nigeria (WAT)",
        "fuel_price_benchmark_ngn": settings.DEFAULT_FUEL_PRICE_NAIRA_PER_LITER
    }
