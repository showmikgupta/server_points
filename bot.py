# bot.py
import os
from dotenv import load_dotenv  # used for getting environment vars
from discord.ext import commands  # functionality for bots
import discord
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer
import voice_activity as va
import random

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CONNECTION_URL = os.getenv('MONGODB_CONNECTION_URL')

# connecting to MongoDB Atlas
cluster = MongoClient(CONNECTION_URL)
db = cluster["UserData"]
collection = db["UserData"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents)

active_guilds = []
ongoing_calls = {}  # holds information on people in ongoing calls


@bot.event
async def on_error(event, *args, **kwargs):
    message = args[0]  # Gets the message object
    await bot.send_message(message.channel, f"You caused an error!\n{message}")


# action to perform when bot is ready
@bot.event
async def on_ready():
    print("Bot is ready")
    
    for guild in bot.guilds:
        active_guilds.append(guild.id)

    print(active_guilds)


# create new entry for the server
@bot.event
async def on_guild_join(guild):
    create_guild_entry(guild)
    active_guilds.append(guild)


@bot.event
async def on_guild_update(before, after):
    collection.update_one(
            {'guild_id': before.id},
            {"$set":
                {
                    'guild_id': after.id,
                    'guild_name': after.name
                }})


@bot.event
async def on_member_join(member):
    create_user_entry(member.guild, member)


@bot.event
async def on_member_remove(member):
    remove_user_entry(member.guild, member)


@bot.event
async def on_typing(channel, user, when):
    update_points(channel.guild, user, points=5)


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    if (not message.content.startswith('$')) and \
       (message.author.id != 818905677010305096):
        update_points(message.guild, message.author, calculate_points(message))


@bot.event
async def on_message_delete(message):
    update_points(message.guild, message.author,
                  (-1 * calculate_points(message)))


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
    update_points(reaction.message.guild, user, 5)


@bot.event
async def on_reaction_remove(reaction, user):
    update_points(reaction.message.guild, user, -5)


@bot.event
async def on_member_ban(guild, user):
    update_points(guild, user, reset=True)


@bot.event
async def on_member_unban(guild, user):
    update_points(guild, user, reset=True)


@bot.event
async def on_voice_state_update(member, before, after):
    print("voice state updating")
    if str(member.id) in ongoing_calls.keys():  # if the call is ongoing
        print("entry already exists")
        if after.channel is None:  # disconnecting from a call
            print("disconnecting")
            points = ongoing_calls[str(member.id)].get_points()
            update_points(before.channel.guild, member, points)
            del ongoing_calls[str(member.id)]
        elif after.channel.guild.id not in active_guilds:  # another server
            print("going to another channel in a different server")
            print(after.channel.guild.id)
            points = ongoing_calls[str(member.id)].get_points()
            update_points(before.channel.guild, member, points)
            del ongoing_calls[str(member.id)]
        elif after.afk:
            print("going afk")
            print(ongoing_calls[str(member.id)])
            ongoing_calls[str(member.id)].go_afk()
        elif after.self_mute or after.mute:  # if muted
            print("muted")
            ongoing_calls[str(member.id)].mute()
        elif after.self_deaf or after.deaf:  # if deafened
            print("deafened")
            ongoing_calls[str(member.id)].deafen()
        elif not after.self_mute or not after.mute:  # if unmuted
            print("unmuted")
            ongoing_calls[str(member.id)].unmute()
        elif not after.self_deaf or not after.deaf:  # if undeafened
            print("undeafened")
            ongoing_calls[str(member.id)].undeafen()
        elif not after.afk:
            print("not afk")
            ongoing_calls[str(member.id)].unafk()
        else:
            print("something else happened")
    else:
        if after.channel is None:
            print("after channel none")
            return
        if after.channel.guild is not None:  # if joining a call
            muted = deafened = afk = False

            if after.mute or before.self_mute:
                muted = True
            if after.deaf or before.self_deaf:
                deafened = True
            if after.afk:
                deafened = True

            activity = va.VoiceActivityNode(after.channel.guild, member, muted,
                                            deafened, afk)
            print("created a new VA")
            ongoing_calls[str(member.id)] = activity
        else:
            print("something else happened p2")


def add_call_points():
    for user_id in ongoing_calls.keys():
        ongoing_calls[user_id].add_points()
    
    start_points_timer()


def start_points_timer():
    x = datetime.now()
    y = x + timedelta(minutes=15)
    delta = y-x
    secs = delta.total_seconds()
    t = Timer(secs, add_call_points)
    t.start()


@bot.command(name='points', help='Displays how many server points a user has')
async def points(ctx):
    points = get_points(ctx.guild, ctx.author)
    await ctx.send(f'{ctx.author} has {points} points')


@bot.command(name='gamble', help='Gamble a certain amount of server points')
async def gamble(ctx, amount):
    doc = get_guild_doc(ctx.guild)
    user_points = doc['members'][str(ctx.author.id)]
    min_amount = 1000

    if amount == 'all':
        if user_points >= min_amount:
            winnings = gamble_points_basic(user_points)
            update_points(ctx.guild, ctx.author, winnings)

            if winnings > 0:
                embed = discord.Embed(title='Gamble Results',
                                      description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=0x00FF00)
            else:
                embed = discord.Embed(title='Gamble Results',
                                      description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=0xFF0000)
    else:
        try:
            amount = int(amount)
            
            if min_amount <= amount <= user_points:
                winnings = gamble_points_basic(amount)
                update_points(ctx.guild, ctx.author, winnings)

                if winnings > 0:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=0x00FF00)
                else:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=0xFF0000)
            elif amount < 1000:
                embed = discord.Embed(title='Error',
                                      description='Must have atleast 1000 points to gamble', color=0xFFD700)
            elif amount > user_points:
                embed = discord.Embed(title='Error',
                                      description='You can only gamble the points you have', color=0xFFD700)
            
            await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title='Error',
                                  description='Invalid value entered', color=0xFFD700)
            await ctx.send(embed=embed)


def gamble_points_basic(points):
    return (points * 2) if (random.randint(0, 2) == 1) else (points * -1)


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
                }})


def remove_user_entry(guild, user):
    query = {'guild_id': guild.id}
    doc = collection.find_one(query)

    members = doc['members']
    del members[str(user.id)]

    collection.update_one(
        {'guild_id': guild.id},
        {"$set":
            {
                'members': members
            }})


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
                }})
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


def run():
    start_points_timer()
    bot.run(TOKEN)
