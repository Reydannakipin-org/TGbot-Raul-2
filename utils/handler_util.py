""" Для абстрактных функций в хендлерах"""
from datetime import date
from sqlalchemy.future import select

from database.db import get_async_engine, get_async_sessionmaker
from users.models import Participant, Settings


async def async_add_user(user_id: int, name: str) -> str:
    engine = get_async_engine()
    async_session = get_async_sessionmaker(engine)
    async with async_session() as session:
        result = await session.execute(select(Participant).where(Participant.tg_id == str(user_id)))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            return "exists"
        new_user = Participant(tg_id=str(user_id), name=name)
        session.add(new_user)
        await session.commit()
    return "added"


async def async_delete_user(user_id: int) -> bool:
    engine = get_async_engine()
    async_session = get_async_sessionmaker(engine)
    async with async_session() as session:
        result = await session.execute(select(Participant).where(Participant.tg_id == str(user_id)))
        user = result.scalar_one_or_none()
        if not user:
            return False
        await session.delete(user)
        await session.commit()
    return True


async def async_list_users() -> list:
    engine = get_async_engine()
    async_session = get_async_sessionmaker(engine)
    async with async_session() as session:
        result = await session.execute(select(Participant))
        users = result.scalars().all()
    return users


async def async_update_frequency(frequency: int) -> bool:
    engine = get_async_engine()
    async_session = get_async_sessionmaker(engine)
    async with async_session() as session:
        result = await session.execute(select(Settings))
        settings = result.scalar_one_or_none()
        if settings:
            settings.frequency_in_weeks = frequency
        else:
            current_day = date.today().weekday()
            settings = Settings(day_of_week=current_day, frequency_in_weeks=frequency)
            session.add(settings)
        await session.commit()
    return True


async def async_set_user_pause(tg_id: int, pause_start: date, pause_end: date) -> bool:
    engine = get_async_engine()
    async_session = get_async_sessionmaker(engine)
    async with async_session() as session:
        result = await session.execute(select(Participant).where(Participant.tg_id == str(tg_id)))
        user = result.scalar_one_or_none()
        if not user:
            return False
        user.exclude_start = pause_start
        user.exclude_end = pause_end
        await session.commit()
    return True
