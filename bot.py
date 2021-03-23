# bot.py
import os
import operator
from threading import Timer

from dotenv import load_dotenv
from discord.ext import commands
import discord
from pymongo import MongoClient
from datetime import datetime, timedelta

import bot_utils
from VoiceActivity import VoiceActivity
from UserData import UserData
from Shop import Shop
from Item import Item
from ItemType import ItemType

UPDATE_DOCS = False
ERROR_COLOR = LOSE_COLOR = 0xFF0000
WIN_COLOR = 0x00FF00
ACCENT_COLOR = 0xFFD700

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
main_shop = Shop("Main Shop")


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


# create new entry for the server
@bot.event
async def on_guild_join(guild):
    bot_utils.create_guild_entry(guild)
    active_guilds.append(guild.id)

    for member in guild.members:
        await member.create_dm()
        await member.dm_channel.send(
            "Welcome to DisruptPoints (name is WIP).\nType '!help' for a lsit of commands"
        )


# when a server changed its name, afk timeout, etc...
@bot.event
async def on_guild_update(before, after):
    collection.update_one({'guild_id': before.id},
                          {"$set":
                              {
                                  'guild_id': after.id,
                                  'guild_name': after.name
                              }})


@bot.event
async def on_member_join(member):
    bot_utils.create_user_entry(member.guild, member)
    await member.create_dm()
    await member.dm_channel.send(
        "Welcome to DisruptPoints (name is WIP).\nType '!help' for a lsit of commands"
    )


@bot.event
async def on_member_remove(member):
    bot_utils.remove_user_entry(member.guild, member)


@bot.event
async def on_typing(channel, user, when):
    bot_utils.update_xp(channel.guild, user, 5)


@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if (not message.content.startswith('$')) and (message.author.id != 818905677010305096):
        bot_utils.update_xp(message.guild, message.author,
                            bot_utils.calculate_message_xp(message))


@bot.event
async def on_message_delete(message):
    bot_utils.update_xp(message.guild, message.author,
                        (-1 * bot_utils.calculate_message_xp(message)))


@bot.event
async def on_message_edit(before, after):
    # calculate before points
    before_points = bot_utils.calculate_message_xp(before)

    # calculate after points
    after_points = bot_utils.calculate_message_xp(after)

    # update with the difference
    difference = after_points - before_points
    bot_utils.update_xp(before.guild, before.author, difference)


@bot.event
async def on_reaction_add(reaction, user):
    bot_utils.update_xp(reaction.message.guild, user, 5)


@bot.event
async def on_reaction_remove(reaction, user):
    bot_utils.update_xp(reaction.message.guild, user, -5)


@bot.event
async def on_member_ban(guild, user):
    bot_utils.update_xp(guild, user, reset=True)
    bot_utils.update_points(guild, user, reset=True)


@bot.event
async def on_member_unban(guild, user):
    bot_utils.update_xp(guild, user, reset=True)
    bot_utils.update_points(guild, user, reset=True)


@bot.event
async def on_voice_state_update(member, before, after):
    if str(member.id) in ongoing_calls.keys():  # if the call is ongoing
        if after.channel is None:  # disconnecting from a call
            points = ongoing_calls[str(member.id)].get_points()
            bot_utils.update_xp(before.channel.guild, member, points)
            del ongoing_calls[str(member.id)]
        elif after.channel.guild.id not in active_guilds:  # another server
            points = ongoing_calls[str(member.id)].get_points()
            bot_utils.update_xp(before.channel.guild, member, points)
            del ongoing_calls[str(member.id)]
        elif after.afk:
            ongoing_calls[str(member.id)].go_afk()
        elif after.self_mute or after.mute:  # if muted
            ongoing_calls[str(member.id)].mute()
        elif after.self_deaf or after.deaf:  # if deafened
            ongoing_calls[str(member.id)].deafen()
        elif not after.self_mute or not after.mute:  # if unmuted
            ongoing_calls[str(member.id)].unmute()
        elif not after.self_deaf or not after.deaf:  # if undeafened
            ongoing_calls[str(member.id)].undeafen()
        elif not after.afk:
            ongoing_calls[str(member.id)].unafk()
        else:
            print("something else happened")
    else:
        if after.channel is None:
            return
        if after.channel.guild is not None:  # if joining a call
            muted = deafened = afk = False

            if after.mute or before.self_mute:
                muted = True
            if after.deaf or before.self_deaf:
                deafened = True
            if after.afk:
                deafened = True

            activity = VoiceActivity(after.channel.guild, member, muted,
                                     deafened, afk)
            ongoing_calls[str(member.id)] = activity
        else:
            print("something else happened p2")


@bot.command(name='points', help='Displays how many server points a user has')
async def points(ctx):
    points = bot_utils.get_points(ctx.guild, ctx.author)
    embed = discord.Embed(title=f"{ctx.author.name}'s Point Total",
                          description=f'Points: {points}', color=ACCENT_COLOR)
    await ctx.send(embed=embed)


@bot.command(name='gift')
async def gift_points(ctx, recipient, amount):
    # make sure recipient exists in the server
    recipient_user_id = recipient[3:][:-1]
    recipient_user_id = int(recipient_user_id)

    # convert the amount (string) into an integer
    try:
        amount = int(amount)
    except ValueError:
        embed = discord.Embed(
            title="Error", description='Invalid amount entered', color=ERROR_COLOR)
        await ctx.send(embed=embed)
        return

    # check senders balance
    senders_balance = bot_utils.get_points(ctx.guild, ctx.author)

    if senders_balance >= amount:
        # add amount to recipient and subtract from sender --> reupdate db
        if ctx.author.id == recipient_user_id:
            embed = discord.Embed(
                title='Error', description="You can not gift yourself points", color=ERROR_COLOR)
            await ctx.send(embed=embed)
            return
        else:
            bot_utils.send_points(ctx.guild, ctx.author.id,
                                  recipient_user_id, amount)

        recipient_user = await bot.fetch_user(recipient_user_id)
        embed = discord.Embed(
            title='Points Gifted', description=f"{ctx.author.name} gifted {recipient_user.name} {amount} points", color=WIN_COLOR)
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error", description='Insufficient Points', color=ERROR_COLOR)
        await ctx.send(embed=embed)


@bot.command(name='gamble', help='Gamble a certain amount of server points')
async def gamble(ctx, amount):
    doc = bot_utils.get_guild_doc(ctx.guild)
    user_points = doc['members'][str(ctx.author.id)]['points']
    min_amount = 1000

    if user_points < min_amount:
        embed = discord.Embed(title='Error',
                              description='Must have atleast 1000 points to gamble', color=ERROR_COLOR)
        await ctx.send(embed=embed)
    elif amount == 'all':
        winnings = bot_utils.gamble_points_basic(user_points)
        bot_utils.update_points(ctx.guild, ctx.author, winnings)

        if winnings > 0:
            embed = discord.Embed(title='Gamble Results',
                                  description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=WIN_COLOR)
        else:
            embed = discord.Embed(title='Gamble Results',
                                  description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=LOSE_COLOR)

        await ctx.send(embed=embed)
    else:
        try:
            amount = int(amount)

            if min_amount <= amount <= user_points:
                winnings = bot_utils.gamble_points_basic(amount)
                bot_utils.update_points(ctx.guild, ctx.author, winnings)

                if winnings > 0:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=WIN_COLOR)
                else:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=LOSE_COLOR)
            elif amount < min_amount:
                embed = discord.Embed(title='Error',
                                      description='The minimum amount to bet is 1000 server points', color=ERROR_COLOR)
            elif amount > user_points:
                embed = discord.Embed(title='Error',
                                      description='You can only gamble the points you have', color=ERROR_COLOR)

            await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title='Error',
                                  description='Invalid value entered', color=ERROR_COLOR)
            await ctx.send(embed=embed)


@bot.command(name='rank', help='Displays user current rank and exp')
async def rank(ctx):
    xp = bot_utils.get_xp(ctx.guild, ctx.author)
    doc = bot_utils.get_guild_doc(ctx.guild)
    members = doc['members']
    user_info = members[str(ctx.author.id)]
    user_data = bot_utils.decode_userdata(user_info)
    rank = user_data.get_rank()
    embed = discord.Embed(title=f"{ctx.author.name}'s Rank",
                          description=f"Rank: {rank}\nXP: {xp}",
                          color=ACCENT_COLOR)
    await ctx.send(embed=embed)


@bot.command(name='shop', help='Displays what you can buy in the store\nTo buy enter "$buy <name in lowercase>"')
async def shop(ctx):
    embed = discord.Embed(title=f"{main_shop.name}",
                          description="Explore the shop for basic starting items\nTo buy enter '$buy <name in lowercase>'",
                          color=ACCENT_COLOR)

    for item in main_shop.items:
        embed.add_field(name=item.name.title(), value=item.price, inline=True)

    await ctx.send(embed=embed)


@bot.command(name='leaderboard', help='Displays the top ten users with the most xp')
async def leaderboard(ctx):
    # get all user data
    doc = bot_utils.get_guild_doc(ctx.guild)
    members = doc['members']

    # get xp for all users
    xp = []

    for (user_id, user_data) in members.items():
        xp.append(bot_utils.decode_userdata(user_data))

    # Sort the XP from greatest to least
    sorted_xp = sorted(xp, key=operator.attrgetter('xp'))
    sorted_xp.reverse()

    # display top 10
    leaderboard_string = ""
    counter = 1

    for user_data in sorted_xp:
        username = await bot.fetch_user(user_data.get_user_id())

        if not username.bot:
            leaderboard_string += f"{counter}. {username.name} | {user_data.get_xp()}\n"
            counter += 1

            if counter == 11:
                break

    embed = discord.Embed(title='XP Leaderboard',
                          description=leaderboard_string, color=ACCENT_COLOR)
    await ctx.send(embed=embed)


def add_call_points():
    for user_id in ongoing_calls.keys():
        ongoing_calls[user_id].add_points()

    start_points_timer()


def start_points_timer():
    x = datetime.now()
    y = x + timedelta(minutes=15)
    delta = y - x
    secs = delta.total_seconds()
    t = Timer(secs, add_call_points)
    t.start()


def populate_shop():
    ale = Item(0, 'ale', 10, ItemType.CONSUMABLE, "Alchoholic drink", 3)
    health_potion = Item(1, 'health potion', 20,
                         ItemType.CONSUMABLE, "Restores HP over  time", 5)
    long_sword = Item(2, 'long sword', 100, ItemType.WEAPON,
                      "Sword that attacks slower but does more damage than a basic sword", 1)

    main_shop.items.append(ale)
    main_shop.items.append(health_potion)
    main_shop.items.append(long_sword)


def run():
    if UPDATE_DOCS:
        upgrade_database()

    start_points_timer()
    populate_shop()
    bot.run(TOKEN)


def upgrade_database():
    docs = collection.find({})

    for doc in docs:
        updated_members = {}
        members = doc['members']

        for user_id in members.keys():
            points = members[user_id]['points']
            level = members[user_id]['level']
            xp = members[user_id]['xp']

            updated_members[user_id] = bot_utils.encode_userdata(
                UserData(user_id, points, level, xp))

        collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'members': updated_members
                }})
