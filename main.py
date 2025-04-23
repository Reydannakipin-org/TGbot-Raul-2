import asyncio
from aiogram import Bot, Dispatcher
from config import config
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from handlers.main_handlers import KeyboardHandler, FeedBackHandler


async def main():
    """Главная функция запуска бота"""
    bot = Bot(token=config.BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(bot=bot)

    dp.include_router(KeyboardHandler())
    dp.include_router(FeedBackHandler())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())




