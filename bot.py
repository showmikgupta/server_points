# bot.py
import os
from dotenv import load_dotenv  # used for getting environment vars
from discord.ext import commands  # functionality for bots
import discord

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

bot = commands.Bot(command_prefix='$')

# action to perform when bot is ready
@bot.event
async def on_ready():
	print("Bot is ready")

@bot.event
async def on_message(message):
    if message.content.lower() == "hello":
        await message.channel.send('Hi There 🎈🎉')

def run():
    bot.run(TOKEN)

run()