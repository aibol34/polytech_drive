import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env из каталога проекта (рядом с config.py), а не из текущей рабочей папки терминала.
_ROOT = Path(__file__).resolve().parent
# override=True: значения из .env перекрывают пустые переменные окружения (частая путаница в Windows).
load_dotenv(_ROOT / ".env", encoding="utf-8-sig", override=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-change-me-in-production"
    # «Запомнить меня»: срок cookie входа (дни). Браузер может сохранить логин/пароль отдельно через autocomplete.
    REMEMBER_COOKIE_DURATION = timedelta(days=int(os.environ.get("REMEMBER_COOKIE_DAYS", "365")))
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(Path(__file__).resolve().parent / "instance" / "polytech_drive.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    # Public folders/files only: list + download via ?key= (no OAuth). Restrict key to Drive API in Cloud Console.
    GOOGLE_DRIVE_API_KEY = os.environ.get("GOOGLE_DRIVE_API_KEY", "").strip()

    # Секунды для httplib2 (список файлов, скачивание). При «handshake timed out» увеличьте до 180–300.
    GOOGLE_HTTP_TIMEOUT = int(os.environ.get("GOOGLE_HTTP_TIMEOUT", "120"))

    PHOTOS_PER_PAGE = int(os.environ.get("PHOTOS_PER_PAGE", "24"))
    # Максимум фото в одном альбоме (импорт + ZIP «скачать всё»).
    MAX_PHOTOS_PER_ALBUM = int(os.environ.get("MAX_PHOTOS_PER_ALBUM", "5000"))
    ZIP_MAX_FILES = int(os.environ.get("ZIP_MAX_FILES", "5000"))
    MEDIA_CACHE_SECONDS = int(os.environ.get("MEDIA_CACHE_SECONDS", "86400"))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
