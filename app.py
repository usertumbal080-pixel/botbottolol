"""
Free Fire Like Bot — Discord Bot
Command: /like <uid> <region>
"""

import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from flask import Flask
import threading

load_dotenv()

TOKEN  = os.environ.get("TOKEN", "")
PREFIX = os.environ.get("PREFIX", "!")

# ── Bot setup ─────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ── Flask keepalive (untuk Railway/Render agar tidak sleep) ──────────────────

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

# ── Events ────────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Bot online: {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Sync error: {e}")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="Free Fire Likes 🔥"
        )
    )

# ── Load cogs ─────────────────────────────────────────────────────────────────

async def main():
    async with bot:
        await bot.load_extension("cogs.like_commands")
        # Jalankan Flask di thread terpisah
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
