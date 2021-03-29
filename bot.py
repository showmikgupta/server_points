# bot.py
import random
import os
import operator
from uuid import uuid1
from threading import Timer
import asyncio

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
user_data_collection = db["UserData"]
inventory_collection = db["Inventories"]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents)

active_guilds = []
ongoing_calls = {}  # holds information on people in ongoing calls
main_shop = Shop("Main Shop")

ALE = Item(0, 'ale', 10, ItemType.ALCOHOL, "Alchoholic drink", 3)
HEALTH_POTION = Item(1, 'health potion', 20,
                     ItemType.CONSUMABLE, "Restores HP over  time", 5)
LONG_SWORD = Item(2, 'long sword', 100, ItemType.WEAPON,
                  "Sword that attacks slower but does more damage than a basic sword", 1)


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
    user_data_collection.update_one({'guild_id': before.id},
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
    bot_utils.update_xp(guild, user, 0, reset=True)
    bot_utils.update_points(guild, user, 0, reset=True)


@bot.event
async def on_member_unban(guild, user):
    bot_utils.update_xp(guild, user, 0, reset=True)
    bot_utils.update_points(guild, user, 0, reset=True)


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
            money_sent = bot_utils.send_points(
                ctx.guild, ctx.author.id, recipient_user_id, amount)

            if money_sent:
                recipient_user = await bot.fetch_user(recipient_user_id)
                embed = discord.Embed(
                    title='Points Gifted', description=f"{ctx.author.name} gifted {recipient_user.name} {amount} points", color=WIN_COLOR)
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Error", description='You already hit the gifting limit for today or your request would push you over the limit', color=ERROR_COLOR)
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


@bot.command(name='inventory', help='Displays the current inventory of the user')
async def display_inventory(ctx):
    doc = bot_utils.get_guild_doc(ctx.guild)
    inventory_id = doc['members'][str(ctx.author.id)]['inventory_id']
    inventory_doc = bot_utils.get_guild_inventory(ctx.guild)
    inventories = inventory_doc['inventories']
    inventory_info = inventories[str(inventory_id)]
    inventory = inventory_info['inventory']

    embed = discord.Embed(title=f"{ctx.author.name}'s Inventory",
                          description="You have the following items:",
                          color=ACCENT_COLOR)

    # for loop busted wtf
    for item_id, item_quantity in inventory.items():
        item_name = bot_utils.item_lookup(item_id).name
        embed.add_field(name=item_name.title(),
                        value=item_quantity, inline=True)

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


@bot.command(name='buy', help='Buy an item from the shop.\n$buy "name of shop item in quotes" quantity"\nquantity defaults to 1')
async def buy(ctx, name, quantity=1):
    # see if name exists in the Shop
    item = None
    name = name.lower()

    for shop_item in main_shop.items:
        if name == shop_item.name:
            item = shop_item
            break

    if item is None:
        embed = discord.Embed(
            title="Error", description='The shop does not sell this item', color=ERROR_COLOR)
        await ctx.send(embed=embed)
        return

    # see if quantity <= max_quantity
    try:
        quantity = int(quantity)
    except ValueError:
        # Error: enter a number
        embed = discord.Embed(
            title="Error", description='Invalid quantity requested', color=ERROR_COLOR)
        await ctx.send(embed=embed)
        return

    success = await add_to_inventory(ctx, item.id, quantity, output=True)

    if success:
        bot_utils.update_points(
            ctx.guild, ctx.author, -1 * quantity * item.price)


@bot.command(name='explore', help='explore')
async def explore(ctx, location):
    if location.lower() == 'beach':
        embed = discord.Embed(
            title="Exploring", description='You have now entered the beach', color=ACCENT_COLOR)
        await ctx.send(embed=embed)
        await ctx.send(file=discord.File('images/entering_beach.gif'))

        item_probs = {
            "3": 50,
            "4": 10,
            "5": 30,
            "6": 25
        }

        item_found = None

        for i in range(3):
            item_to_check = str(random.randint(3, 6))
            success_condition = random.randint(0, 100)

            if 1 <= success_condition <= item_probs[item_to_check]:
                item_found = bot_utils.item_lookup(item_to_check)
                await add_to_inventory(ctx, item_to_check, 1, output=False)

        description = ""

        if item_found is not None:
            description += f'You found a(n) {item_found.name.title()}\n'
        else:
            description += 'You found nothing.\n'

        description += 'You have now exited the beach'

        await asyncio.sleep(7)
        embed = discord.Embed(title="Returning to town",
                              description=description, color=ACCENT_COLOR)
        await ctx.send(embed=embed)
        await ctx.send(file=discord.File('images/returning_to_town.gif'))


@bot.command(name='cheers', help='Gives someone an alcoholic beverage if you one if your inventory')
async def cheers(ctx, person):
    recipient_id = ctx.message.mentions[0].id
    alcohol_quantity = check_inventory(ctx, item_type=ItemType.ALCOHOL)

    if alcohol_quantity == 0:
        embed = discord.Embed(title="Low on booze",
                              description="You don't have any alcohol to use to cheers someone", color=ERROR_COLOR)
        await ctx.send(embed=embed)
    else:
        remove_from_inventory(ctx, ItemType.ALCOHOL, 1)
        recipient_id = f'<@{recipient_id}>'

        await ctx.send(f'Cheers {recipient_id}! {ctx.author.name} sent you some booze.')
        await ctx.send(file=discord.File('images/cheers.gif'))


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


def start_gift_reset_timer():
    current_time = datetime.now()
    tomorrow = current_time + timedelta(days=1)
    reset_time = tomorrow.replace(hour=0, minute=0, second=0)
    delta = reset_time - current_time
    secs = delta.total_seconds()
    t = Timer(secs, reset_total_gift)
    t.start()


def reset_total_gift():
    docs = user_data_collection.find({})

    for doc in docs:
        members = doc['members']

        for user_id, user_data in members.items():
            user_data['total_gift'] = 0

        user_data_collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'members': members
                }})

    start_gift_reset_timer()


def populate_shop():
    main_shop.items.append(ALE)
    main_shop.items.append(HEALTH_POTION)
    main_shop.items.append(LONG_SWORD)


def run():
    if UPDATE_DOCS:
        upgrade_database()

    start_points_timer()
    start_gift_reset_timer()
    populate_shop()
    bot.run(TOKEN)


def upgrade_database():
    docs = user_data_collection.find({})

    for doc in docs:
        updated_members = {}
        inventories = {}
        members = doc['members']

        for user_id in members.keys():
            points = members[user_id]['points'] + 10000
            level = members[user_id]['level']
            xp = members[user_id]['xp']
            inventory_id = str(uuid1())

            updated_members[user_id] = bot_utils.encode_userdata(
                UserData(user_id, points, level, xp, inventory_id))
            inventories[inventory_id] = {
                'id': inventory_id,
                'capacity': 20,
                'size': 0,
                'inventory': {}
            }

        user_data_collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'members': updated_members
                }})

        inventory_collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'inventories': inventories
                }})


async def add_to_inventory(ctx, item_id, quantity, output=True):
    if type(item_id) == int:
        item_id = str(item_id)

    item = bot_utils.item_lookup(item_id)

    if quantity <= item.max_quantity:
        inventory_id = bot_utils.get_user_inventory_id(
            ctx.guild, ctx.author)  # get users inventory id from userdata db
        # get all inventory data from the users guild
        inventory_doc = bot_utils.get_guild_inventory(ctx.guild)
        # get the users inventory information
        inventory_data = inventory_doc['inventories'][inventory_id]

        if inventory_data['size'] + quantity <= inventory_data['capacity']:
            try:
                current_quantity = inventory_data['inventory'][item_id]
            except KeyError:
                current_quantity = 0

            if current_quantity + quantity <= item.max_quantity:
                try:
                    inventory_data['inventory'][item_id] += quantity
                except KeyError:
                    inventory_data['inventory'][item_id] = quantity

                inventory_data['size'] += quantity

                inventory_collection.update_one(
                    {'guild_id': ctx.guild.id},
                    {"$set":
                     {
                         'inventories': inventory_doc['inventories']
                     }})

                if output:
                    embed = discord.Embed(title='Inventory Update',
                                          description=f"Added {quantity} of {item.name.title()} to your inventory", color=ACCENT_COLOR)
                    await ctx.send(embed=embed)

                return True
            else:
                # you can only have max in your inventory. you currently have x
                if output:
                    embed = discord.Embed(title='Inventory Update Error',
                                          description=f"The most amount of {item.name.title()} you can hold is {item.max_quantity}. You currently have {inventory_data['inventory'][item_id]}", color=ERROR_COLOR)
                    await ctx.send(embed=embed)

                return False
        else:
            # not enough space in inventory
            if output:
                embed = discord.Embed(title='Inventory Update Error',
                                      description="You don't have enough space in your inventory", color=ERROR_COLOR)
                await ctx.send(embed=embed)

            return False
    else:
        # you cant buy that many of this item
        if output:
            embed = discord.Embed(title='Inventory Update Error',
                                  description=f"The most amount of {item.name.title()} you can buy is {item.max_quantity}", color=ERROR_COLOR)
            await ctx.send(embed=embed)

        return False


def remove_from_inventory(ctx, item_type, quantity, item_id=None):
    inventory_id = bot_utils.get_user_inventory_id(ctx.guild, ctx.author)
    inventory_doc = bot_utils.get_guild_inventory(ctx.guild)
    inventory_info = inventory_doc['inventories'][inventory_id]

    if inventory_info['size'] == 0:
        return False
    else:
        if item_id is None:
            for item_id in inventory_info['inventory'].keys():
                if bot_utils.item_lookup(item_id).type == item_type:
                    inventory_info['inventory'][item_id] -= quantity
                    inventory_info['size'] -= quantity
        else:
            for item_id in inventory_info['inventory'].keys():
                if bot_utils.item_lookup(item_id).id == item_id:
                    inventory_info['inventory'][item_id] -= quantity
                    inventory_info['size'] -= quantity

        inventory_collection.update_one(
            {'guild_id': ctx.guild.id},
            {"$set":
                {
                    'inventories': inventory_doc['inventories']
                }})

        return True


def check_inventory(ctx, item_type=None, item_id=None):
    inventory_id = bot_utils.get_user_inventory_id(ctx.guild, ctx.author)
    inventory_doc = bot_utils.get_guild_inventory(ctx.guild)
    inventory_info = inventory_doc['inventories'][inventory_id]

    if inventory_info['size'] == 0:
        # nothing in inventory to give
        return 0
    else:
        if item_id is None:
            count = 0

            for item_id, quantity in inventory_info['inventory'].items():
                if bot_utils.item_lookup(item_id).type == item_type:
                    count += quantity

            return count
        else:
            for item_id, quantity in inventory_info['inventory'].items():
                if bot_utils.item_lookup(item_id).id == int(item_id):
                    return quantity
