import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Allows basic imports before dependencies are installed.
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).expanduser()
DEFAULT_DATABASE_URL = f"sqlite+aiosqlite:///{DATA_DIR / 'app.db'}"

class Settings:
    # Telegram Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
    ADMIN_TELEGRAM_ID: int = int(os.getenv("ADMIN_TELEGRAM_ID", "123456789"))

    # Database Configuration
    DATA_DIR: Path = DATA_DIR
    DATABASE_URL: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    SQL_ECHO: bool = _as_bool(os.getenv("SQL_ECHO", "false"))

    # Cryptography Configuration (Fernet 32 url-safe base64 bytes key)
    # Keep this stable once Gmail accounts have been linked, or saved tokens
    # cannot be decrypted after restart.
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "uNqG8zS-uN1kR0S5Hjg9xH9oJkL4nM2oPqRstUvwxyA=")

    # Web URL configuration (used for unsubscribe links)
    WEB_URL: str = os.getenv("WEB_URL", "http://localhost:8000")

    # SMTP Configuration for Gmail App Passwords
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

settings = Settings()
