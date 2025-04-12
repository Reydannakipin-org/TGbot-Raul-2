import asyncio
from aiogram import Bot, Dispatcher
from utils.google_sheets import get_sheet
from config import config


async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(bot=bot)
    # dp.include_router()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())




