import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
from apocalypse_bot.core.bot import bot

if not TOKEN:
    raise RuntimeError("Discord bot token environment variable is missing (DISCORD_TOKEN/BOT_TOKEN/TOKEN).")

bot.run(TOKEN)
