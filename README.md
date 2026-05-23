# Theatre contacts Portugal

Mobile-friendly searchable directory for theatre-related contacts in Portugal.

## Files

- `index.html` — standalone searchable page.
- `artists-portugal-data.json` — structured contact data.
- `telegram_bot.py` — optional Telegram bot that searches the same data.
- `TELEGRAM_BOT_README.md` — bot setup notes.

## Local use

Open `index.html` in a browser.

## Telegram bot

Create a bot token with `@BotFather`, then run:

```bash
export TELEGRAM_BOT_TOKEN="your-token"
python3 telegram_bot.py
```
