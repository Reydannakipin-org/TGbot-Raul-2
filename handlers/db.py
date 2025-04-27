from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


def get_async_engine():
    return create_async_engine('sqlite+aiosqlite:///random_coffee.db', echo=True)


def get_async_sessionmaker(engine):
    return sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)