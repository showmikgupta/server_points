import random
import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
CONNECTION_URL = os.getenv('MONGODB_CONNECTION_URL')

cluster = MongoClient(CONNECTION_URL)
db = cluster["UserData"]
collection = db["UserData"]


def gamble_points_basic(bet_amount):
    """Simple gambling function with a 1/3 chance to win double the bet amount

    Args:
        bet_amount (integer): The amount to bet

    Returns:
        integer: The amount won or lost
    """
    winning_val = random.randint(0, 2)
    return (bet_amount) if (winning_val == 1) else (bet_amount * -1)


def calculate_points(message):
    """Calculated how many points a message is worth based on the content and length

    Args:
        message (discord.Message): Message to calculate the point value for

    Returns:
        integer: Point value of the message
    """
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
    """Get all the user ids of all members of a server

    Args:
        guild (discord.Guild): Server to get user ids from

    Returns:
        List[integer]: List of all user ids in a server
    """
    ids = []

    for user in guild.members:
        ids.append(user.id)

    return ids


def get_guild_doc(guild):
    """Gets the document (entry) related to the given guild from the database

    Args:
        guild (discord.Guild): Server to get document for

    Returns:
        dict: Dictionary representing the document for the server
    """
    query = {'guild_id': guild.id}
    return collection.find_one(query)


def create_guild_entry(guild):
    """Creates a document (entry) for the given server

    Args:
        guild (discord.Guild): Guild to create an entry for

    Returns:
        dict:  Most up to date member information
    """
    members = {}
    member_info = {
        'points': 0,
        'xp': 0,
        'level': 0
    }

    for user_id in get_user_ids(guild):
        members[str(user_id)] = member_info

    post = {
        'guild_id': guild.id,
        'guild_name': guild.name,
        'members': members
    }

    collection.insert_one(post)
    return members


def create_user_entry(guild, user):
    """Creates an entry for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to add user data
        user (discord.User): User to create data for
    """
    doc = get_guild_doc(guild)

    if doc is None:
        create_guild_entry(guild)
    else:
        member_info = {
            'points': 0,
            'xp': 0,
            'level': 0
        }

        members = doc['members']
        members[str(user.id)] = member_info

        collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})


def remove_user_entry(guild, user):
    """Removes a user entry for the given guild

    Args:
        guild (discord.Guild): Guild to remove user data from
        user (discord.User): User to remove data for
    """
    doc = get_guild_doc(guild)

    if doc is not None:
        members = doc['members']
        del members[str(user.id)]

        collection.update_one(
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
    doc = get_guild_doc(guild)
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

        collection.update_one(
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
    doc = get_guild_doc(guild)
    members = {}

    if doc is not None:
        members = doc['members']

        try:
            if reset:
                create_user_entry(guild, user)
            else:
                members[str(user.id)]['xp'] += xp
        except KeyError:
            members[str(user.id)]['xp'] = xp

        collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})
    else:
        members = create_guild_entry(guild)

    return members


def get_points(guild, user):
    """Gets the points total for the given user in the given guild

    Args:
        guild (discord.Guild): Guild to get user data for
        user (discord.User): User to get points total for

    Returns:
        integer: Users point total
    """
    doc = get_guild_doc(guild)

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
