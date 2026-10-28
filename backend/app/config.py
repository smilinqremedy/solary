import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Solary - IoT Solar Energy Intelligence & WhatsApp Alerting Platform"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database (TimescaleDB / PostgreSQL)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:postgres_password@localhost:5432/solar_intelligence"
    )
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL", 
        "postgresql://postgres:postgres_password@localhost:5432/solar_intelligence"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # MQTT Broker (EMQX)
    MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "localhost")
    MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    MQTT_USERNAME: str = os.getenv("MQTT_USERNAME", "admin")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "public")
    
    # Meta WhatsApp Cloud API
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "EAAX...meta_cloud_api_token...")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "109876543210987")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "meta_app_secret_hex")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "solar_intelligence_verify_token_2026")
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v19.0"

    # Nigerian Energy Economics Defaults
    DEFAULT_FUEL_PRICE_NAIRA_PER_LITER: float = float(os.getenv("FUEL_PRICE_NGN", "1150.0"))
    GENERATOR_LITERS_PER_KWH: float = 0.35  # Standard small/medium petrol generator efficiency
    DEFAULT_BATTERY_CUTOFF_SOC: float = 10.0  # Cutoff SOC percentage (e.g. 10% for LiFePO4)
    HEAVY_LOAD_THRESHOLD_WATTS: float = 1500.0
    LOW_PV_THRESHOLD_WATTS: float = 200.0
    CRITICAL_BATTERY_SOC: float = 40.0
    ALERT_COOLDOWN_SECONDS: int = 1800  # 30-minute spam protection cooldown

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
