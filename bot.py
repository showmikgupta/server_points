# bot.py
import os
from dotenv import load_dotenv
from discord.ext import commands
import discord
from pymongo import MongoClient
from datetime import datetime, timedelta
from threading import Timer
import voice_activity as va
import bot_utils

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


# create new entry for the server
@bot.event
async def on_guild_join(guild):
    bot_utils.create_guild_entry(guild)
    active_guilds.append(guild.id)


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


@bot.event
async def on_member_remove(member):
    bot_utils.remove_user_entry(member.guild, member)


@bot.event
async def on_typing(channel, user, when):
    bot_utils.update_points(channel.guild, user, points=5)


@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if (not message.content.startswith('$')) and (message.author.id != 818905677010305096):
        bot_utils.update_points(message.guild, message.author, bot_utils.calculate_points(message))


@bot.event
async def on_message_delete(message):
    bot_utils.update_points(message.guild, message.author,
                            (-1 * bot_utils.calculate_points(message)))


@bot.event
async def on_message_edit(before, after):
    # calculate before points
    before_points = bot_utils.calculate_points(before)

    # calculate after points
    after_points = bot_utils.calculate_points(after)

    # update with the difference
    difference = after_points - before_points
    bot_utils.update_points(before.guild, before.author, points=difference)


@bot.event
async def on_reaction_add(reaction, user):
    bot_utils.update_points(reaction.message.guild, user, 5)


@bot.event
async def on_reaction_remove(reaction, user):
    bot_utils.update_points(reaction.message.guild, user, -5)


@bot.event
async def on_member_ban(guild, user):
    bot_utils.update_points(guild, user, reset=True)


@bot.event
async def on_member_unban(guild, user):
    bot_utils.update_points(guild, user, reset=True)


@bot.event
async def on_voice_state_update(member, before, after):
    if str(member.id) in ongoing_calls.keys():  # if the call is ongoing
        if after.channel is None:  # disconnecting from a call
            points = ongoing_calls[str(member.id)].get_points()
            bot_utils.update_points(before.channel.guild, member, points)
            del ongoing_calls[str(member.id)]
        elif after.channel.guild.id not in active_guilds:  # another server
            points = ongoing_calls[str(member.id)].get_points()
            bot_utils.update_points(before.channel.guild, member, points)
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

            activity = va.VoiceActivityNode(after.channel.guild, member, muted,
                                            deafened, afk)
            ongoing_calls[str(member.id)] = activity
        else:
            print("something else happened p2")


@bot.command(name='points', help='Displays how many server points a user has')
async def points(ctx):
    points = bot_utils.get_points(ctx.guild, ctx.author)
    embed = discord.Embed(title=f"{ctx.author.name}'s Point Total",
                          description=f'Points: {points}', color=0xFFD700)
    await ctx.send(embed=embed)


@bot.command(name='gamble', help='Gamble a certain amount of server points')
async def gamble(ctx, amount):
    doc = bot_utils.get_guild_doc(ctx.guild)
    user_points = doc['members'][str(ctx.author.id)]
    min_amount = 1000

    if user_points < min_amount:
        embed = discord.Embed(title='Error',
                              description='Must have atleast 1000 points to gamble', color=0xFFD700)
        await ctx.send(embed=embed)
    elif amount == 'all':
        winnings = bot_utils.gamble_points_basic(user_points)
        bot_utils.update_points(ctx.guild, ctx.author, winnings)

        if winnings > 0:
            embed = discord.Embed(title='Gamble Results',
                                  description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=0x00FF00)
        else:
            embed = discord.Embed(title='Gamble Results',
                                  description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=0xFF0000)

        await ctx.send(embed=embed)
    else:
        try:
            amount = int(amount)

            if min_amount <= amount <= user_points:
                winnings = bot_utils.gamble_points_basic(amount)
                bot_utils.update_points(ctx.guild, ctx.author, winnings)

                if winnings > 0:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You won {winnings} points! You now have {user_points + winnings} points now', color=0x00FF00)
                else:
                    embed = discord.Embed(title='Gamble Results',
                                          description=f'You lost {amount} points! You now have {user_points + winnings} points now', color=0xFF0000)
            elif amount < min_amount:
                embed = discord.Embed(title='Error',
                                      description='The minimum amount to bet is 1000 server points', color=0xFFD700)
            elif amount > user_points:
                embed = discord.Embed(title='Error',
                                      description='You can only gamble the points you have', color=0xFFD700)

            await ctx.send(embed=embed)
        except ValueError:
            embed = discord.Embed(title='Error',
                                  description='Invalid value entered', color=0xFFD700)
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

def run():
    start_points_timer()
    bot.run(TOKEN)
