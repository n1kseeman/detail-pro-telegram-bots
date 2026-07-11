import asyncio
import tempfile

from app.db import Database
from app.bot import DetailBot
from app.config import Settings


async def scenario():
    with tempfile.NamedTemporaryFile(suffix=".db") as file:
        db = Database(file.name)
        await db.connect(); await db.init()
        fields = dict(user_id=1, services="Мойка", brand="BMW", model="X5", car_year="2020", plate="", body_type="", comment="", photos="[]", phone="+375", date="2030-01-01", time="10:00")
        assert await db.create_appointment(fields)
        assert await db.create_appointment({**fields, "user_id": 2}) is None
        await db.set_status(1, "cancelled")
        assert await db.create_appointment({**fields, "user_id": 2})
        await db.close()


def test_slot_is_reserved_once_and_released_on_cancel():
    asyncio.run(scenario())


def test_admin_access_is_limited_to_the_separate_admin_bot():
    settings = Settings("client", "admin", {10}, -1001234567890, "manager", "", "Detail Pro", ":memory:", "Europe/Minsk")
    db = Database(":memory:")
    assert not DetailBot(settings, db, is_admin_bot=False).admin(10)
    assert DetailBot(settings, db, is_admin_bot=True).admin(10)
