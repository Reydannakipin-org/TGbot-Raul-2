import asyncio
import logging
from aiogram import Bot, Dispatcher
from daemons.drawdaemon import daemon_loop
from config import config
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from handlers.admin_handlers import AdminHandler
from handlers.main_handlers import KeyboardHandler, FeedBackHandler


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def start_bot():
    """Главная функция запуска бота"""
    bot = Bot(token=config.BOT_TOKEN,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(bot=bot)

    dp.include_router(KeyboardHandler())
    dp.include_router(AdminHandler())
    dp.include_router(FeedBackHandler())
    logger.info('Запуск Telegram-бота...')
    await dp.start_polling(bot)


async def main():
    logger.info('Запуск основного приложения...')
    await asyncio.gather(
        daemon_loop(),
        start_bot()
    )


if __name__ == '__main__':
    asyncio.run(main())