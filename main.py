import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot import DetailBot
from app.config import load_settings
from app.db import Database


async def main():
    settings = load_settings()
    db = Database(settings.database_path, settings.timezone)
    await db.connect()
    await db.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    app = DetailBot(settings, db)
    try:
        await app.run(bot)
    finally:
        await bot.session.close()
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
