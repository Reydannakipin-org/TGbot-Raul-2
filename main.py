import asyncio
import logging
from aiogram import Bot, Dispatcher
from daemons.drawdaemon import daemon_loop
from config import config
from handlers.main_handlers import KeyboardHandler


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def start_bot():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(KeyboardHandler())
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