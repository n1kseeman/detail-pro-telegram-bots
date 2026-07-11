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
    client_bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    admin_bot = Bot(settings.admin_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    client_app = DetailBot(settings, db, is_admin_bot=False)
    admin_app = DetailBot(settings, db, is_admin_bot=True)
    client_app.client_bot = admin_app.client_bot = client_bot
    client_app.admin_bot = admin_app.admin_bot = admin_bot
    try:
        await asyncio.gather(client_app.run(client_bot), admin_app.run(admin_bot))
    finally:
        await client_bot.session.close()
        await admin_bot.session.close()
        await db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
