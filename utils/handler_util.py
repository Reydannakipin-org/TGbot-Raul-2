""" Для абстрактных функций в хендлерах"""

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from users.models import Settings


async def update_frequency_in_weeks(session: AsyncSession, weeks: int, day_of_week: int = 0):
    result = await session.execute(
        select(Settings).filter(Settings.day_of_week == day_of_week)
    )
    setting = result.scalars().first()

    if setting:
        setting.frequency_in_weeks = weeks
        await session.commit()
    else:
        new_setting = Settings(day_of_week=day_of_week, frequency_in_weeks=weeks)
        session.add(new_setting)
        await session.commit()