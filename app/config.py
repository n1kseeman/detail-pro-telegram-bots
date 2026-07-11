from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_group_id: int | None
    manager_username: str
    manager_phone: str
    center_name: str
    database_path: str
    timezone: str


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("Заполните BOT_TOKEN в .env.")
    group_raw = os.getenv("ADMIN_GROUP_ID", "").strip()
    try:
        admin_group_id = int(group_raw) if group_raw else None
    except ValueError as error:
        raise RuntimeError("ADMIN_GROUP_ID должен быть числовым Telegram chat ID, например -1001234567890.") from error
    db_path = os.getenv("DATABASE_PATH", "data/detail_pro.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return Settings(token, admin_group_id, os.getenv("MANAGER_USERNAME", "detailpro_manager").lstrip("@"), os.getenv("MANAGER_PHONE", ""), os.getenv("CENTER_NAME", "Detail Pro"), db_path, os.getenv("TIMEZONE", "Europe/Minsk"))
