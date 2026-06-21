# Gmail Campaign Telegram Bot

Local setup now works with SQLite by default. Postgres is still supported by setting `DATABASE_URL`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Update `.env` with your real Telegram bot token and Telegram user ID:

```dotenv
BOT_TOKEN=your-telegram-bot-token
ADMIN_TELEGRAM_ID=your-telegram-user-id
```

Initialize the local database:

```bash
python scripts/init_db.py
```

Run the bot and web helper:

```bash
python main.py
```

The FastAPI helper listens on `http://localhost:8000`.

## Database

Default local database:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
```

Postgres example:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres
```
