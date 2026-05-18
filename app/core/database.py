import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

load_dotenv()

# Docker compose injects DATABASE_URL directly — use it first
DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("DATABASE_URL_DOCKER")
    or os.getenv("DATABASE_URL_LOCAL")
)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Check your .env file.")

print("Using DB:", DATABASE_URL)

# ── Sync engine — used only by ingestion scripts ──────────────
engine        = create_engine(DATABASE_URL)
SessionLocal  = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base          = declarative_base()

# ── Async engine — used by ALL FastAPI routes ─────────────────
ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
async_engine       = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal  = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """FastAPI dependency — used by both analytics and forecast routes."""
    async with AsyncSessionLocal() as session:
        yield session