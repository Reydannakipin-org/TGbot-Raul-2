import asyncio
from aiogram import Bot, Dispatcher
from config import config
from handlers.main_handlers import KeyboardHandler


async def main():
    """Главная функция запуска бота"""
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(bot=bot)
    dp.include_router(KeyboardHandler())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())




