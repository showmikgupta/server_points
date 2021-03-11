# bot.py
import os
from dotenv import load_dotenv  # used for getting environment vars
from discord.ext import commands  # functionality for bots
import discord
import pymongo
from pymongo import MongoClient

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CONNECTION_URL = os.getenv('MONGODB_CONNECTION_URL')

# connecting to MongoDB Atlas
cluster = MongoClient(CONNECTION_URL)
db = cluster["UserData"]
collection = db["UserData"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents)


# action to perform when bot is ready
@bot.event
async def on_ready():
    print("Bot is ready")
    # post = {'guild_id': 809478788046913616,
    #         'guild_name': 'Disrupt Studios Test Server',
    #         'members': {
    #             '164516819221217280': 100
    #         }}
    # collection.insert_one(post)


@bot.event
async def on_typing(channel, user, when):
    update_points(channel.guild, user, points=10)


@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if len(message.content) > 5:
        update_points(message.channel, message.author, points=10)


@bot.command(name='points', help='Displays how many server points a user has')
async def points(ctx):
    query = {'guild_id': ctx.guild.id}  # search criteria to see if there is any data on the given server
    doc = collection.find_one(query)  # searching database
    members = update_points(ctx.guild, ctx.author, points=0)  # get all members and their points in a dictionary
    points = 0
    
    for user_id in members:
        if user_id == str(ctx.author.id):
            points = members[user_id]
            break

    await ctx.send(f'{ctx.author} has {points} points')

def run():
    bot.run(TOKEN)


def get_user_ids(guild):
    ids = []

    for user in guild.members:
        ids.append(user.id)

    return ids


def create_new_document(guild):
    members = {}

    for user_id in get_user_ids(guild):
        members[str(user_id)] = 0
    
    post = {
        'guild_id': guild.id,
        'guild_name': guild.name,
        'members': members
    }

    collection.insert_one(post)


# checks to see if data on the given server exists
# if it does exists, it attempts to update the users points
# if the user does not exist, then it will create data for the user
# if there is no data on the server, it will create a new entry for it and give everyone 0 points
def update_points(guild, user, points):
    query = {'guild_id': guild.id}
    doc = collection.find_one(query)
    members = {}

    if doc is not None:
        members = doc['members']
        
        try:
            members[str(user.id)] += points
        except KeyError:
            members[str(user.id)] = points

        collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }
            }
        )
    else:
        members = {}

        for user_id in get_user_ids(guild):
            if user_id == user.id:
                members[str(user_id)] = points
            else:
                members[str(user_id)] = 0
        
        post = {
            'guild_id': guild.id,
            'guild_name': guild.name,
            'members': members
        }

        collection.insert_one(post)

    return members

run()