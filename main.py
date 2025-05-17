import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import config
from daemons.drawdaemon import daemon_loop, init_db
from handlers.admin_handlers import AdminHandler
from handlers.main_handlers import MainHandler, FeedBackHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def start_bot(bot: Bot):
    """Запуск Telegram-бота"""
    dp = Dispatcher(bot=bot)
    dp.include_router(MainHandler())
    dp.include_router(AdminHandler())
    dp.include_router(FeedBackHandler())

    logger.info('Запуск Telegram-бота...')
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def main():
    logger.info('Запуск основного приложения...')
    await init_db()
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    await asyncio.gather(
        daemon_loop(bot),
        start_bot(bot)
    )

if __name__ == '__main__':
    asyncio.run(main())
