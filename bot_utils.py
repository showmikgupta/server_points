import random
import os
import math
from uuid import uuid1

from pymongo import MongoClient
from dotenv import load_dotenv

from Item import Item
from ItemType import ItemType

load_dotenv()
CONNECTION_URL = os.getenv('MONGODB_CONNECTION_URL')

cluster = MongoClient(CONNECTION_URL)
db = cluster["UserData"]
user_data_collection = db["UserData"]
inventory_collection = db["Inventories"]

items = {
    "0": Item(0, 'ale', 10, ItemType.ALCOHOL, "Alchoholic drink", 3, 1),
    "1": Item(1, 'health potion', 20, ItemType.CONSUMABLE, "Restores HP over  time", 5, 1),
    "2": Item(2, 'long sword', 100, ItemType.WEAPON,
                  "Sword that attacks slower but does more damage than a basic sword", 1, 1),
    "3": Item(3, 'seashell', 1, ItemType.JUNK, "Natural objects you can find along the beach", 20, 1),
    "4": Item(4, 'hat', 5, ItemType.ARMOR, "Leather hat that offers minimal protection", 1, 1),
    "5": Item(5, 'message in a bottle', -1, ItemType.JUNK, "A secret message for sailors of the past", 3, 1),
    "6": Item(7, 'coconuts', 10, ItemType.CONSUMABLE, "Sweet and refreshing snack from the beach", 10, 1),
}

def item_lookup(item_id):
    return items[item_id]


def encode_userdata(user_id, points, level, xp, total_gift, inventory_id):
    """Encodes UserData objects to dictionaries so MongoDB can store UserData
    Args:
        userdata (UserData): Objects representing someone's user data
    Returns:
        dict: dictionary representation of someone's user data
    """
    return {
        'user_id': user_id,
        'points': points,
        'level': level,
        'xp': xp,
        'total_gift': total_gift,
        'inventory_id': inventory_id
    }


def gamble_points_basic(bet_amount):
    """Simple gambling function with a 1/3 chance to win double the bet amount

    Args:
        bet_amount (integer): The amount to bet

    Returns:
        integer: The amount won (negative if lost)
    """
    winning_val = random.randint(0, 2)
    return (bet_amount) if (winning_val == 1) else (bet_amount * -1)


def calculate_message_xp(message):
    """Calculated how many points a message is worth based on the content and length

    Args:
        message (discord.Message): Message to calculate the point value for

    Returns:
        integer: Point value of the message
    """
    points = 0
    points += 5 if message.mention_everyone else 0
    points += (len(message.attachments) * 5)
    points += (len(message.role_mentions) * 5)

    if 0 > len(message.content) <= 5:
        points += 5
    elif len(message.content) <= 10:
        points += 10
    else:
        points += 15

    return points


def calculate_levelup_points(level):
    """Determined how many points should be awarded when someone
       levels up based their updated level

    Args:
        level (integer): level of the user

    Returns:
        integer: Amount of points awarded to the user based on level
    """
    if 1 <= level <= 5:                 # F
        return 500
    elif 6 <= level <= 10:              # E
        return 900
    elif 11 <= level <= 15:             # D
        return 1500
    elif 16 <= level <= 18:             # C
        return 3000
    elif 19 <= level <= 21:             # B
        return 4800
    elif 22 <= level <= 24:             # A
        return 10000
    elif 25 <= level <= 26:             # S
        return 25000
    else:                               # SS
        return 50000


def get_user_ids(guild):
    """Get all the user ids of all members of a server

    Args:
        guild (discord.Guild): Server to get user ids from

    Returns:
        List[integer]: List of all user ids in a server
    """
    return [user.id for user in guild.members]


def get_userdata_doc(guild):
    """Gets the document (entry) related to the given guild from the database

    Args:
        guild (discord.Guild): Server to get document for

    Returns:
        dict: Dictionary representing the document for the server
    """
    return user_data_collection.find_one({'guild_id': guild.id})


def get_inventory_doc(guild):
    """Gets the inventory document related to the given guild

    Args:
        guild (discord.Guild): Server to get document for

    Returns:
        dict: Dictionary representing the document for the server
    """
    return inventory_collection.find_one({'guild_id': guild.id})


def create_guild_entry(guild):
    """Creates entries in two collections: UserData and Inventories for the given guild

    Args:
        guild (discord.Guild): Guild to create an entry for

    Returns:
        dict:  Most up to date member information
    """
    members = {}
    inventories = {}

    for user_id in get_user_ids(guild):
        inventory_id = str(uuid1())
        members[str(user_id)] = encode_userdata(user_id, 0, 1, 0, inventory_id)
        inventories[inventory_id] = {
            'id': inventory_id,
            'capacity': 20,
            'size': 0,
            'inventory': {}
        }

    user_data_collection.insert_one({
        'guild_id': guild.id,
        'guild_name': guild.name,
        'members': members
    })

    inventory_collection.insert_one({
        'guild_id': guild.id,
        'guild_name': guild.name,
        'inventories': inventories
    })

    return members


def create_user_entry(guild, user):
    """Creates two entries in different collections for the user's data and their inventory

    Args:
        guild (discord.Guild): Guild to add user data
        user (discord.User): User to create data for
    """
    doc = get_userdata_doc(guild)

    if doc is None:
        create_guild_entry(guild)
    else:
        inventory_id = str(uuid1())
        members = doc['members']
        members[str(user.id)] = encode_userdata(user.id, 0, 1, 0, inventory_id)

        user_data_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})

        inventory_doc = get_inventory_doc(guild)
        inventories = inventory_doc['inventories']
        inventories[inventory_id] = {
            'id': inventory_id,
            'capacity': 20,
            'size': 0,
            'inventory': {}
        }

        inventory_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'inventories': inventories
                }})


def remove_user_entry(guild, user):
    """Removes a user entry for the given guild

    Args:
        guild (discord.Guild): Guild to remove user data from
        user (discord.User): User to remove data for
    """
    doc = get_userdata_doc(guild)

    if doc is not None:
        members = doc['members']
        del members[str(user.id)]

        user_data_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})


def update_points(guild, user, points, reset=False):
    """Updates point value for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to update
        user (discord.User): User to update
        points (int): Amount of points to add to current value
        reset (bool, optional): Flag to determine if user data should be reset. Defaults to False.

    Returns:
        dict: Most up to date member information
    """
    doc = get_userdata_doc(guild)
    members = {}

    if doc is not None:
        members = doc['members']

        try:
            if reset:
                create_user_entry(guild, user)
            else:
                members[str(user.id)]['points'] += points
        except KeyError:
            members[str(user.id)]['points'] = points

        user_data_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})
    else:
        members = create_guild_entry(guild)

    return members


def update_xp(guild, user, xp, reset=False):
    """Updates xp value for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to update
        user (discord.User): User to update
        points (int): Amount of xp to add to current value
        reset (bool, optional): Flag to determine if user data should be reset. Defaults to False.

    Returns:
        dict: Most up to date member information
    """
    doc = get_userdata_doc(guild)
    members = {}

    if doc is not None:
        members = doc['members']

        try:
            if reset:
                create_user_entry(guild, user)
            else:
                members[str(user.id)]['xp'] += xp

                # check to see if they crossed the threshold
                if needs_level_up(members[str(user.id)]['level'], members[str(user.id)]['xp']):
                    # level up
                    members[str(user.id)]['level'] += 1

                    # add points
                    members[str(user.id)]['points'] += calculate_levelup_points(members[str(user.id)]['level'])
        except KeyError:
            members[str(user.id)]['xp'] = xp

        user_data_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})
    else:
        members = create_guild_entry(guild)

    return members


def needs_level_up(level, xp):
    if xp >= quadratic_level_fx(level):
        return True
    else:
        return False


def quadratic_level_fx(x):
    return (40 * (x**2)) + (25 * x)  # 40x^2 + 25x


def quadratic_level_fx_basic(x):
    scale_factor = 1
    return .2 * scale_factor * (x**2)


def log_level_fx(x):
    scale_factor = 1
    return 10 * scale_factor * math.log(x, 2)


def get_rank(level):
    if level == 1:
        return "F5"
    if level == 2:
        return "F4"
    if level == 3:
        return "F3"
    if level == 4:
        return "F2"
    if level == 5:
        return "F1"
    if level == 6:
        return "E5"
    if level == 7:
        return "E4"
    if level == 8:
        return "E3"
    if level == 9:
        return "E2"
    if level == 10:
        return "E1"
    if level == 11:
        return "D5"
    if level == 12:
        return "D4"
    if level == 13:
        return "D3"
    if level == 14:
        return "D2"
    if level == 15:
        return "D1"
    if level == 16:
        return "C3"
    if level == 17:
        return "C2"
    if level == 18:
        return "C1"
    if level == 19:
        return "B3"
    if level == 20:
        return "B2"
    if level == 21:
        return "B1"
    if level == 22:
        return "A3"
    if level == 23:
        return "A2"
    if level == 24:
        return "A1"
    if level == 25:
        return "S2"
    if level == 26:
        return "S1"
    if level == 27:
        return "SS"


def get_points(guild, user):
    """Gets the points total for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to get user data for
        user (discord.User): User to get points total for

    Returns:
        integer: Users point total
    """
    doc = get_userdata_doc(guild)

    if doc is None:
        create_guild_entry(guild)

        return 0
    else:
        members = doc['members']

        try:
            return members[str(user.id)]['points']
        except KeyError:
            create_user_entry(guild, user)

            return 0


def get_xp(guild, user):
    """Gets the xp total for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to get user data for
        user (discord.User): User to get points total for

    Returns:
        integer: Users xp total
    """
    doc = get_userdata_doc(guild)

    if doc is None:
        create_guild_entry(guild)

        return 0
    else:
        members = doc['members']

        try:
            return members[str(user.id)]['xp']
        except KeyError:
            create_user_entry(guild, user)

            return 0


def send_points(guild, sender_id, recipient_id, amount):
    doc = get_userdata_doc(guild)
    members = doc['members']
    sender_data = members[str(sender_id)]
    recipient_data = members[str(recipient_id)]
    limit = 1000  # maximum points allowed to be gifted per day
    total_gift = sender_data['total_gift']

    if total_gift > limit or amount + total_gift > limit:
        return False
    else:
        # updates sender total points and increases total gift
        sender_data['total_gift'] += amount
        sender_data['points'] -= amount

        recipient_data['points'] += amount

        members[str(sender_id)] = sender_data
        members[str(recipient_id)] = recipient_data

        user_data_collection.update_one(
            {'guild_id': guild.id},
            {"$set":
             {
                 'members': members
             }})

        return True


def get_user_inventory_id(guild, user):
    doc = get_userdata_doc(guild)
    return doc['members'][str(user.id)]['inventory_id']
