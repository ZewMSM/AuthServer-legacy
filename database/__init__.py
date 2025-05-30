import logging

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from os import environ

from database.db_classes import *

logger = logging.getLogger('Database')
engine = create_async_engine(f'postgresql+asyncpg://{environ.get("POSTGRES_USER")}:{environ.get("POSTGRES_PASSWD")}@'
                             f'{environ.get("POSTGRES_HOST")}:{environ.get("POSTGRES_PORT")}/{environ.get("POSTGRES_NAME")}', echo=True)
Session = async_sessionmaker(bind=engine, expire_on_commit=False)
RedisSession = aioredis.Redis(host=environ.get("REDIS_AUTH_HOST"), port=int(environ.get("REDIS_AUTH_PORT")))


async def init_database():
    global Session, engine

    logger.info("Initializing database...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
