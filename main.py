import discord
from discord.ext import commands
from config import DISCORD_TOKEN
import os
from utils.http_server import start_http_server

class MyBot(commands.Bot):
    async def setup_hook(self):
        # Automatically load cogs
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                await self.load_extension(f"cogs.{filename[:-3]}")
        await self.tree.sync()

intents = discord.Intents.default()
intents.message_content = True

bot = MyBot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

start_http_server()

bot.run(DISCORD_TOKEN)