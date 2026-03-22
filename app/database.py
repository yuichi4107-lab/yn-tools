from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings


def _build_engine():
    url = settings.database_url
    kwargs = {"echo": settings.app_env == "development"}
    if url.startswith("postgresql"):
        kwargs["poolclass"] = NullPool
    return create_async_engine(url, **kwargs)


engine = _build_engine()

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
