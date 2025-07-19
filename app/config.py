import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS: List[int] = [int(id_) for id_ in os.getenv("ADMIN_IDS", "").split(",") if id_.strip()]

# URL для подключения к PostgreSQL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@db:5432/tatar_youth"
)

# Настройки пагинации
EVENTS_PER_PAGE = 5
PARTICIPANTS_PER_PAGE = 10