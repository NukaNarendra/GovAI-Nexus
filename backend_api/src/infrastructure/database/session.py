import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

from src.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# HARDCODED FOR SQLITE TESTING TO BYPASS REPLIT'S HIDDEN SECRETS
SQLITE_URL = "sqlite+aiosqlite:///./enterprise_governance.db"


class DatabaseManager:
    def __init__(self):
        # CHANGED: Using SQLITE_URL instead of settings.DATABASE_URL
        self.engine = create_async_engine(
            SQLITE_URL, echo=False, future=True, pool_pre_ping=True
        )
        self.async_session_maker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def check_connection(self) -> bool:
        try:
            async with self.async_session_maker() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False

    async def dispose_engine(self) -> None:
        if self.engine:
            await self.engine.dispose()


db_manager = DatabaseManager()
