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
async def on_member_join(member):
    doc = get_guild_doc(member.guild)

    if doc is None:
        create_guild_entry(member.guild)
    else:
        create_user_entry(member.guild, member)


@bot.event
async def on_typing(channel, user, when):
    update_points(channel.guild, user, points=5)

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    if (not message.content.startswith('$')) and (message.author.id != 818905677010305096):
        print(message.author.id)
        update_points(message.guild, message.author, points=calculate_points(message))


@bot.event
async def on_message_delete(message):
    update_points(message.guild, message.author, points=(-1 * calculate_points(message)))


@bot.event
async def on_message_edit(before, after):
    # calculate before points
    before_points = calculate_points(before)

    # calculate after points
    after_points = calculate_points(after)

    # update with the difference
    difference = after_points - before_points
    update_points(before.guild, before.author, points=difference)


@bot.event
async def on_reaction_add(reaction, user):
    update_points(reaction.message.guild, user, points = 5)


@bot.event
async def on_reaction_remove(reaction, user):
    update_points(reaction.message.guild, user, points = -5)

@bot.event
async def on_member_ban(guild, user):
    update_points(guild, user, reset=True)


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


def calculate_points(message):
    points = 0

    if message.mention_everyone:
        points += 5
    
    for attachment in message.attachments:
        points += 5
    
    for mention in message.mentions:
        points += 5

    for mention in message.role_mentions:
        points += 5

    if 0 > len(message.content) <= 5:
        points += 5
    elif len(message.content) <= 10:
        points += 10
    else:
        points += 15
    
    return points


def get_user_ids(guild):
    ids = []

    for user in guild.members:
        ids.append(user.id)

    return ids


def get_guild_doc(guild):
    query = {'guild_id': guild.id}
    return collection.find_one(query)


def create_guild_entry(guild):
    members = {}

    for user_id in get_user_ids(guild):
        members[str(user_id)] = 0
    
    post = {
        'guild_id': guild.id,
        'guild_name': guild.name,
        'members': members
    }

    collection.insert_one(post)


def create_user_entry(guild, user):
    query = {'guild_id': guild.id}
    doc = collection.find_one(query)

    if doc is None:
        create_guild_entry(guild)
    else:
        members = doc['members']
        members[str(user.id)] = 0

        collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }
            }
        )

# checks to see if data on the given server exists
# if it does exists, it attempts to update the users points
# if the user does not exist, then it will create data for the user
# if there is no data on the server, it will create a new entry for it and give everyone 0 points
def update_points(guild, user, points=0, reset=False):
    query = {'guild_id': guild.id}
    doc = collection.find_one(query)
    members = {}

    if doc is not None:
        members = doc['members']
        
        try:
            if reset:
                members[str(user.id)] = 0
            else:
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
                if reset:
                    members[str(user.id)] = 0
                else:
                    members[str(user.id)] = points
            else:
                members[str(user_id)] = 0
        
        post = {
            'guild_id': guild.id,
            'guild_name': guild.name,
            'members': members
        }

        collection.insert_one(post)

    return members


def get_points(guild, user):
    query = {'guild_id': guild.id}
    doc = collection.find_one(query)

    if doc is None:
        create_guild_entry(guild)

        return 0
    else:
        members = doc['members']

        try:
            return members[str(user.id)]
        except KeyError:
            create_user_entry(guild, user)

            return 0


run()