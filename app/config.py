import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
    SESSION_COOKIE_NAME = "fvi_session"
    TRAY_LIMIT = 50

    @classmethod
    def validate(cls):
        required = (
            "SECRET_KEY",
            "ADMIN_PASSWORD",
            "DB_HOST",
            "DB_USER",
            "DB_PASSWORD",
            "DB_NAME",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )

class DBConfig:
    HOST = os.environ.get("DB_HOST")
    USER = os.environ.get("DB_USER")
    PASSWORD = os.environ.get("DB_PASSWORD")
    DATABASE = os.environ.get("DB_NAME")
    PORT = int(os.environ.get("DB_PORT", 3306))
