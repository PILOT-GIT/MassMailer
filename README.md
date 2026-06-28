# Gmail Campaign Telegram Bot

This guide lists the commands to set up, run, and manage the project locally.

Local setup uses SQLite by default. Postgres is also supported by setting `DATABASE_URL`.

## 1. Prerequisites

Make sure you have:

- Python 3.10+
- pip
- Git

## 2. Clone and enter the project

```bash
git clone <repo-url>
cd agyclipg
```

## 3. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
```

## 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## 5. Configure environment variables

Create a `.env` file in the project root and add your credentials:

```dotenv
BOT_TOKEN=your-telegram-bot-token
ADMIN_TELEGRAM_ID=your-telegram-user-id
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
```

## 6. Initialize the database

```bash
python scripts/init_db.py
```

If you want to start from a fresh local database:

```bash
rm -f data/app.db
python scripts/init_db.py
```

## 7. Run the bot and web helper

```bash
python main.py
```

The app starts:

- the Telegram bot
- the background scheduler
- the FastAPI helper on `http://localhost:8000`

## 8. Stop the app

Press `Ctrl+C` in the terminal where the app is running.

## 9. Useful commands

Activate the virtual environment later:

```bash
source .venv/bin/activate
```

Install dependencies again after updates:

```bash
python -m pip install -r requirements.txt
```

Reinitialize the database:

```bash
python scripts/init_db.py
```

Check your Python version:

```bash
python --version
```

## 10. How to use the Telegram bot

Once the app is running, open Telegram and find your bot by its username.

### Start the bot

Send:

```text
/start
```

The bot will greet you and open the main dashboard.

### Open the menu manually

You can also use:

```text
/menu
```

This shows the main menu with buttons for:

- Campaigns
- Target Lists
- Gmail Accounts
- Profile & Compliance

### Example usage flow

1. Start the bot with `/start`.
2. Tap the Campaigns button.
3. Choose Create Campaign.
4. Follow the prompts to set up your campaign.
5. Use Target Lists to upload or view subscriber lists.
6. Use Gmail Accounts to connect or review sender accounts.
7. Use Profile & Compliance to set your physical mailing address.

### Example commands

```text
/start
/menu
```

### Notes

- The bot is mainly driven by inline buttons and menu prompts.
- You do not need to type complex commands for most actions.
- If the bot is running locally, it will respond only after the app process started successfully.

## 11. Database options

Default local database:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
```

Postgres example:

```dotenv
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/postgres
```
