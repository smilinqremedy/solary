import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.config import settings
from app.models.schema import Base

logger = logging.getLogger("Database")

# Determine database URL with fallback to local async SQLite if postgres is not reachable
db_url = settings.DATABASE_URL
if os.getenv("USE_SQLITE", "false").lower() == "true":
    db_url = "sqlite+aiosqlite:///./solar_intelligence.db"

engine = create_async_engine(
    db_url,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Redis client setup with graceful fallback to fakeredis for self-contained execution
redis_client = None

try:
    import redis.asyncio as aioredis
    _raw_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client = _raw_redis
except Exception:
    pass

def get_redis_client():
    global redis_client
    if redis_client is None:
        try:
            import fakeredis.aioredis
            redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            logger.info("Using in-memory high-performance FakeRedis instance for local standalone operation.")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
    return redis_client

redis_client = get_redis_client()

async def init_db():
    """Initializes tables and configures TimescaleDB Hypertable when available."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                await conn.execute(text(
                    "SELECT create_hypertable('telemetry_data', 'time', if_not_exists => TRUE);"
                ))
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed ({e}). Falling back to local high-performance SQLite engine...")
        engine = create_async_engine("sqlite+aiosqlite:///./solar_intelligence.db", echo=False)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite local database initialized successfully at ./solar_intelligence.db")

async def get_db():
    """FastAPI dependency for obtaining async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
