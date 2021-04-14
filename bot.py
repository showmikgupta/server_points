# bot.py
import asyncio
import os
import random
from datetime import datetime, timedelta
from operator import itemgetter
from threading import Timer

import discord
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

import bot_utils
from BottleItem import BottleItem
from DrinkItem import DrinkItem
from EdibleItem import EdibleItem
from FoodItem import FoodItem
from Item import Item
from ItemType import ItemType
from Shop import Shop
from VoiceActivity import VoiceActivity

BOT_ID = 818905677010305096
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

ALE = DrinkItem(0, 'ale', 15, ItemType.ALCOHOL,
                "A classic alchoholic drink made from the best ingredients on the island", 5, 0, 0, True)
COCONUT = FoodItem(1, 'coconut', 5,
                   ItemType.CONSUMABLE, "A refreshing snack that can be found at the beach", 10, .6, 10)
FISH = FoodItem(2, 'fish', 10, ItemType.CONSUMABLE,
                "Smelly and slimey delicacy of the ocean", 5, .1, 30)


# action to perform when bot is ready
@bot.event
async def on_ready():
    """action to perform when bot is ready"""
    print("Bot is ready")

    global active_guilds
    active_guilds = [guild.id for guild in bot.guilds]


@bot.event
async def on_guild_join(guild):
    """Action when the bot gets added to a new server

    Args:
        guild (discord.Guild): Server bot was added to
    """
    bot_utils.create_guild_entry(guild)
    active_guilds.append(guild.id)

    # send direct message to each user in the server
    for member in guild.members:
        await member.create_dm()
        embed = discord.Embed(title="Welcome to DisruptPoints (the name is WIP)!",
                              description="This bot encourages community engagement with a story that the player follows to uncover the truth of a mysterious world they find themselves in.\nType '$help' to get a list of all commands you can use. Only '$help' and '$shop' will work in this DM since the game store information per server you're on.\nTo use the other commands we recommend creating a channel for this bot and enter them there.", color=ACCENT_COLOR)
        await member.send(embed=embed)


# when a server changed its name, afk timeout, etc...
@bot.event
async def on_guild_update(before, after):
    """Action when server changes name, aft timeout, etc...

    Args:
        before (discord.Guild): Server information before the update
        after (discord.Guild): Server information after the update
    """

    # update guild information in the database
    user_data_collection.update_one({'guild_id': before.id},
                                    {"$set":
                                     {
                                         'guild_id': after.id,
                                         'guild_name': after.name
                                     }})


@bot.event
async def on_member_join(member):
    """Action when a new member join a server with the bot

    Args:
        member (discord.Member): New member the joined the server
    """
    bot_utils.create_user_entry(member.guild, member)

    # send new member a direct message
    await member.create_dm()
    embed = discord.Embed(title="Welcome to DisruptPoints (the name is WIP)!",
                          description="This bot encourages community engagement with a story that the player follows to uncover the truth of a mysterious world they find themselves in.\nType '$help' to get a list of all commands you can use. Only '$help' and '$shop' will work in this DM since the game store information per server you're on.\nTo use the other commands we recommend creating a channel for this bot and enter them there.", color=ACCENT_COLOR)
    await member.send(embed=embed)


@bot.event
async def on_member_remove(member):
    """Action when a member leaves/gets removed from a server with the bot

    Args:
        member (discord.Member): Member that left/got removed
    """
    bot_utils.remove_user_entry(member.guild, member)


@bot.event
async def on_typing(channel, user, when):
    bot_utils.update_xp(channel.guild, user, 5)


@bot.event
async def on_message(message):
    # if message is a command, process the command
    await bot.process_commands(message)

    # if the command is not a command and the message is not coming from the bot, update users xp
    if (not message.content.startswith('$')) and (message.author.id != BOT_ID):
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
    bot_utils.update_xp(after.guild, before.author, difference)


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
    """Action when someones voice state changes. Handles all point collection whem
       a user is in a voice call.

    Args:
        member (discord.Member): Member whose voice state changed
        before (discord.VoiceState): Previous voice state
        after (discord.VoiceState): Current voice state
    """
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
        # error if the user did not enter an integer
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
            # check to see if money was successfully sent to the recipient
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
    doc = bot_utils.get_userdata_doc(ctx.guild)
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
    doc = bot_utils.get_userdata_doc(ctx.guild)
    inventory_id = doc['members'][str(ctx.author.id)]['inventory_id']
    inventory_doc = bot_utils.get_inventory_doc(ctx.guild)
    inventories = inventory_doc['inventories']
    inventory_info = inventories[str(inventory_id)]
    inventory = inventory_info['inventory']

    embed = discord.Embed(title=f"{ctx.author.name}'s Inventory",
                          description=f"Capacity: {inventory_info['size']}/{inventory_info['capacity']}\nYou have the following items:",
                          color=ACCENT_COLOR)

    # for loop busted wtf
    for item_id, item_quantity in inventory.items():
        item_name = bot_utils.item_lookup(item_id)['name']
        embed.add_field(name=item_name.title(),
                        value=item_quantity, inline=True)

    await ctx.send(embed=embed)


@bot.command(name='rank', help='Displays user current rank and exp')
async def rank(ctx):
    doc = bot_utils.get_userdata_doc(ctx.guild)
    xp = doc['members'][str(ctx.author.id)]['xp']
    rank = bot_utils.get_rank(doc['members'][str(ctx.author.id)]['level'])

    embed = discord.Embed(title=f"{ctx.author.name}'s Rank",
                          description=f"Rank: {rank}\nXP: {xp}",
                          color=ACCENT_COLOR)
    await ctx.send(embed=embed)


@bot.command(name='shop', help='Displays what you can buy in the store\nTo buy enter "$buy <name> <quantity: default to 1 if omitted>"')
async def shop(ctx):
    embed = discord.Embed(title=f"{main_shop.name}",
                          description="Explore the shop for basic starting items\nTo buy enter '$buy <name> <quantity: default to 1 if omitted>'",
                          color=ACCENT_COLOR)

    for item in main_shop.items:
        embed.add_field(name=item.name.title(), value=item.price, inline=True)

    await ctx.send(embed=embed)


@bot.command(name='buy', help='Buy an item from the shop.\n$buy "name of shop item in quotes" quantity"\nquantity defaults to 1')
async def buy(ctx, name, quantity=1):
    # see if name exists in the Shop
    name = name.lower()
    item = bot_utils.check_item_exists(name)

    if item is None:
        embed = discord.Embed(
            title="Error", description='The shop does not sell this item', color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # see if quantity <= max_quantity
    try:
        quantity = int(quantity)
    except ValueError:
        # Error: enter a number
        embed = discord.Embed(
            title="Error", description='Invalid quantity requested', color=ERROR_COLOR)
        await ctx.send(embed=embed)
        return

    success = await add_to_inventory(ctx, bot_utils.item_id_lookup(name), quantity, output=True)

    if success:
        bot_utils.update_points(
            ctx.guild, ctx.author, -1 * quantity * item['price'])


@bot.command(name='explore', help='explore')
async def explore(ctx, location):
    doc = bot_utils.get_userdata_doc(ctx.guild)
    currentUserEnergy = doc['members'][str(ctx.author.id)]['energy']
    beachEnergyCost = 5
    pondEnergyCost = 1
    # location2EnergyCost = .15
    # location3EnergyCost = .25
    # location4EnergyCost = .50
    if location.lower() == 'beach':
        if currentUserEnergy >= beachEnergyCost:
            # consume energy
            doc['members'][str(ctx.author.id)]['energy'] -= beachEnergyCost

            embed = discord.Embed(
                title="Exploring", description='You have now entered the beach... It will take some time to find some items. Patience is key.', color=ACCENT_COLOR)
            await ctx.send(embed=embed)
            await ctx.send(file=discord.File('images/entering_beach.gif'))

            item_ids = ["1", "2", "3", "4", "5", "6",
                        "7", "8", "9", "10", "11", "12", "13", ]
            item_found = None

            for _ in range(7):
                item_to_check = random.randint(0, 12)
                success_condition = random.randint(0, 100)
                item_found = bot_utils.item_lookup(item_ids[item_to_check])

                if 1 <= success_condition < (item_found['probability'] * 100):
                    await add_to_inventory(ctx, item_ids[item_to_check], 1, output=False)
                    break
                else:
                    item_found = None

            description = ""

            if item_found is not None:
                description += f'You found a(n) {item_found["name"].title()}\n'
            else:
                description += 'You found nothing.\n'

            description += 'You have now exited the beach'

            # await asyncio.sleep(5)
            embed = discord.Embed(title="Returning to town",
                                  description=description, color=ACCENT_COLOR)
            await ctx.send(embed=embed)
            await ctx.send(file=discord.File('images/returning_to_town.gif'))

            user_data_collection.update_one(
                {'guild_id': doc['guild_id']},
                {"$set":
                 {
                     'members': doc['members']
                 }})
        else:
            embed = discord.Embed(title="Low on energy",
                                  description=f"You don't have enough energy to explore right now. Go eat something.\nCurrent energy: {currentUserEnergy}", color=ERROR_COLOR)
            await ctx.send(embed=embed)

    elif location.lower() == 'pond':
        if currentUserEnergy >= pondEnergyCost:
            # consume energy
            doc['members'][str(ctx.author.id)]['energy'] -= pondEnergyCost

            embed = discord.Embed(
                title="Exploring", description='You have now entered the pond... It will take some time to find some items. Patience is key.', color=ACCENT_COLOR)
            await ctx.send(embed=embed)
            await ctx.send(file=discord.File('images/entering_pond.gif'))

            item_ids = ["13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24"]  # Edit Item Numbers
            item_found = None

            for _ in range(7):
                item_to_check = random.randint(0, 8)  # Edit Range
                success_condition = random.randint(0, 100)
                item_found = bot_utils.item_lookup(item_ids[item_to_check])

                if 1 <= success_condition < (item_found['probability'] * 100):
                    await add_to_inventory(ctx, item_ids[item_to_check], 1, output=False)
                    break
                else:
                    item_found = None

            description = ""

            if item_found is not None:
                description += f'You found a(n) {item_found["name"].title()}\n'
            else:
                description += 'You found nothing.\n'

            description += 'You have now exited the pond'

            # await asyncio.sleep(5)
            embed = discord.Embed(title="Returning to town",
                                  description=description, color=ACCENT_COLOR)
            await ctx.send(embed=embed)
            await ctx.send(file=discord.File('images/returning_to_town.gif'))

            user_data_collection.update_one(
                {'guild_id': doc['guild_id']},
                {"$set":
                    {
                        'members': doc['members']
                    }})
        else:
            embed = discord.Embed(title="Low on energy",
                                  description=f"You don't have enough energy to explore right now. Go eat something.\nCurrent energy: {currentUserEnergy}", color=ERROR_COLOR)
            await ctx.send(embed=embed)

@bot.command(name='consume', help='Consumes a food item to restore energy')
async def consume(ctx, item_name):  # ex: $consume "coconut"
    # checking to see if the item exists in general
    item_name = item_name.lower()
    item = bot_utils.check_item_exists(item_name)

    if item is None:
        embed = discord.Embed(title="Error",
                              description="Item can't be found", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # check to see if item exists in inventory
    item_id = bot_utils.check_item_exists_inventory(
        ctx.guild, ctx.author, item_name)

    if item_id == -1:
        embed = discord.Embed(title="Error",
                              description="Item can't be found", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # access to item name and id as well as the object
    if item['type'] != "FoodItem" and item['type'] != "DrinkItem":
        embed = discord.Embed(title="Error",
                              description=f"You can't eat {item_name.title()}, {ctx.author.name}", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    item_energy = item['energy']

    # add energy to user
    doc = bot_utils.get_userdata_doc(ctx.guild)
    current_energy = doc['members'][str(ctx.author.id)]['energy']

    if current_energy < 100:
        if current_energy + item_energy > 100:
            embed = discord.Embed(title="Delicious!",
                                  description=f"You gained {100 - current_energy} energy", color=ACCENT_COLOR)
            await ctx.send(embed=embed)

            doc['members'][str(ctx.author.id)]['energy'] = 100
        else:
            embed = discord.Embed(title="Delicious!",
                                  description=f"You gained {item_energy} energy", color=ACCENT_COLOR)
            await ctx.send(embed=embed)

            doc['members'][str(ctx.author.id)]['energy'] += item_energy

        # remove item from inventory
        remove_from_inventory(ctx.guild, ctx.author, item_id)
    else:
        embed = discord.Embed(title="Error",
                              description="You're already have max energy", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # update db
    user_data_collection.update_one(
        {'guild_id': doc['guild_id']},
        {"$set":
         {
             'members': doc['members']
         }})


@bot.command(name='energy', help='Shows your current energy level')
async def display_energy(ctx):
    embed = discord.Embed(title="Energy",
                          description=f"You have {bot_utils.get_user_energy(ctx.guild, ctx.author)} energy remaining", color=ACCENT_COLOR)
    await ctx.send(embed=embed)


@bot.command(name='remove', help='Removes an item from your inventory')
async def remove_inventory(ctx, item_name):  # ex: $remove "coconut"
    item_name = item_name.lower()

    # check to see if exists in the game
    item = bot_utils.check_item_exists(item_name)

    if item is None:
        embed = discord.Embed(title="Error",
                              description="Item can't be found", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # check to see if exists in the inventory
    item_id = bot_utils.check_item_exists_inventory(
        ctx.guild, ctx.author, item_name)

    if item_id == -1:
        embed = discord.Embed(title="Error",
                              description="Item not in your inventory", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # remove item and decrease size
    remove_from_inventory(ctx.guild, ctx.author, item_id)
    await display_inventory(ctx)


@bot.command(name='cheers', help='Gives someone an alcoholic beverage if you one if your inventory')
async def cheers(ctx, person):
    recipient_id = ctx.message.mentions[0].id
    alcohol_id = check_alcohol(ctx.guild, ctx.author)

    if alcohol_id:
        remove_from_inventory(ctx.guild, ctx.author, alcohol_id, 1)
        recipient_id = f'<@{recipient_id}>'

        await ctx.send(f'Cheers {recipient_id}! {ctx.author.name} sent you some booze.')
        await ctx.send(file=discord.File('images/cheers.gif'))
    else:
        embed = discord.Embed(title="Low on booze",
                              description="You don't have any alcohol to use to cheers someone", color=ERROR_COLOR)
        await ctx.send(embed=embed)


@bot.command(name='read', help='Reads and item that contains a message')
async def read_item(ctx, item_name):
    item_name = item_name.lower()
    item = bot_utils.check_item_exists(item_name)

    if item is None:
        # error: item does not exist in your inventory
        embed = discord.Embed(title="Error",
                              description="Item can't be found", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    # check to see if item exists in inventory
    item_id = bot_utils.check_item_exists_inventory(
        ctx.guild, ctx.author, item_name)

    if item_id == -1:
        embed = discord.Embed(title="Error",
                              description="Item not in your inventory", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    if item['type'] != 'BottleItem':
        # error: item is not something that can be read
        embed = discord.Embed(title="Error",
                              description="That's not something that you can read", color=ERROR_COLOR)
        return await ctx.send(embed=embed)

    embed = discord.Embed(title=f"Message in a Bottle: {item['name'].title()}",
                          description=item['message'], color=ACCENT_COLOR)
    await ctx.send(file=discord.File('images/opening_message.gif'))
    await ctx.send(embed=embed)


@bot.command(name='leaderboard', help='Displays the top ten users with the most xp')
async def leaderboard(ctx):
    # get all user data
    doc = bot_utils.get_userdata_doc(ctx.guild)
    members = doc['members']

    # get xp for all users
    xp = [members[key] for key in members.keys()]

    # Sort the XP from greatest to least
    xp.sort(key=itemgetter('xp'), reverse=True)

    # display top 10
    leaderboard_string = ""
    counter = 1

    for user_data in xp:
        username = await bot.fetch_user(user_data['user_id'])

        if not username.bot:
            name = username.name
            rank = bot_utils.get_rank(user_data['level'])

            leaderboard_string += f"{counter}. {name} --- {rank} --- {user_data['xp']}\n"
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

        for user_id in members.keys():
            members[user_id]['total_gift'] = 0

        user_data_collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'members': members
                }})

    start_gift_reset_timer()


def populate_shop():
    main_shop.items.append(ALE)
    main_shop.items.append(COCONUT)
    main_shop.items.append(FISH)


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
        # inventories = {}
        members = doc['members']

        for user_id in members.keys():
            points = members[user_id]['points']
            level = members[user_id]['level']
            xp = members[user_id]['xp']
            total_gift = members[user_id]['total_gift']
            inventory_id = members[user_id]['inventory_id']
            energy = 100

            userdata = bot_utils.encode_userdata(
                user_id, points, level, xp, total_gift, inventory_id, energy)
            updated_members[user_id] = userdata

            # inventories[inventory_id] = {
            #     'id': inventory_id,
            #     'capacity': 20,
            #     'size': 0,
            #     'inventory': {}
            # }

        user_data_collection.update_one(
            {'guild_id': doc['guild_id']},
            {"$set":
                {
                    'members': updated_members
                }})

        # inventory_collection.update_one(
        #     {'guild_id': doc['guild_id']},
        #     {"$set":
        #         {
        #             'inventories': inventories
        #         }})


async def add_to_inventory(ctx, item_id, quantity, output=True):
    if type(item_id) == int:
        item_id = str(item_id)

    item = bot_utils.item_lookup(item_id)

    if quantity <= item['max_quantity']:
        inventory_id = bot_utils.get_user_inventory_id(ctx.guild, ctx.author)
        inventory_doc = bot_utils.get_inventory_doc(ctx.guild)
        inventory_data = inventory_doc['inventories'][inventory_id]

        if inventory_data['size'] + quantity <= inventory_data['capacity']:
            try:
                current_quantity = inventory_data['inventory'][item_id]
            except KeyError:
                current_quantity = 0

            if current_quantity + quantity <= item['max_quantity']:
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
                                          description=f"Added {quantity} of {item['name'].title()} to your inventory", color=ACCENT_COLOR)
                    await ctx.send(embed=embed)

                return True
            else:
                # you can only have max in your inventory. you currently have x
                if output:
                    embed = discord.Embed(title='Inventory Update Error',
                                          description=f"The most amount of {item['name'].title()} you can hold is {item['max_quantity']}. You currently have {inventory_data['inventory'][item_id]}", color=ERROR_COLOR)
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
                                  description=f"The most amount of {item['name'].title()} you can buy is {item['max_quantity']}", color=ERROR_COLOR)
            await ctx.send(embed=embed)

        return False


def remove_from_inventory(guild, user, item_id, quantity=1):
    inventory_id = bot_utils.get_user_inventory_id(guild, user)
    inventory_doc = bot_utils.get_inventory_doc(guild)
    inventory_info = inventory_doc['inventories'][inventory_id]

    if inventory_info['size'] == 0:
        return False
    else:
        try:
            if inventory_info['inventory'][item_id] - quantity >= 0:
                inventory_info['size'] -= quantity
                inventory_info['inventory'][item_id] -= quantity
            else:
                inventory_info['size'] -= inventory_info['inventory'][item_id]
                inventory_info['inventory'][item_id] = 0

            if inventory_info['inventory'][item_id] == 0:
                del inventory_info['inventory'][item_id]

        except KeyError:
            return False

        inventory_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'inventories': inventory_doc['inventories']
                }})

        return True


def check_alcohol(guild, user):
    inventory_id = bot_utils.get_user_inventory_id(guild, user)
    inventory_doc = bot_utils.get_inventory_doc(guild)
    inventory_info = inventory_doc['inventories'][inventory_id]

    if inventory_info['size'] == 0:
        # nothing in inventory to give
        return None

    for item_id in inventory_info['inventory'].keys():
        item = bot_utils.item_lookup(item_id)

        if item['type'] == 'DrinkItem' and item['is_alcohol']:
            return item_id

    return None


def check_inventory(ctx, item_type=None, item_id=None):
    inventory_id = bot_utils.get_user_inventory_id(ctx.guild, ctx.author)
    inventory_doc = bot_utils.get_inventory_doc(ctx.guild)
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
