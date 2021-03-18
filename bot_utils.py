import random
import os

from pymongo import MongoClient
from dotenv import load_dotenv

from UserData import UserData

load_dotenv()
CONNECTION_URL = os.getenv('MONGODB_CONNECTION_URL')

cluster = MongoClient(CONNECTION_URL)
db = cluster["UserData"]
collection = db["UserData"]


def encode_userdata(userdata):
    return {
        '_type': 'UserData',
        'user_id': userdata.get_user_id(),
        'points': userdata.get_points(),
        'level': userdata.get_level(),
        'xp': userdata.get_xp()
    }


def decode_userdata(document):
    assert document['_type'] == 'UserData'
    user_id = document['user_id']
    points = document['points']
    level = document['level']
    xp = document['xp']

    return UserData(user_id, points, level, xp)


def gamble_points_basic(bet_amount):
    """Simple gambling function with a 1/3 chance to win double the bet amount

    Args:
        bet_amount (integer): The amount to bet

    Returns:
        integer: The amount won or lost
    """
    winning_val = random.randint(0, 2)
    return (bet_amount) if (winning_val == 1) else (bet_amount * -1)


def calculate_message_points(message):
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
        return 7000
    elif 25 <= level <= 26:             # S
        return 10000
    else:                               # SS
        return 50000


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

    for user_id in get_user_ids(guild):
        members[str(user_id)] = encode_userdata(UserData(user_id, 0, 1, 0))

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
        members = doc['members']
        members[str(user.id)] = encode_userdata(UserData(user.id, 0, 1, 0))

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
                user_data = decode_userdata(members[str(user.id)])
                user_data.update_points(points)
                members[str(user.id)] = encode_userdata(user_data)
        except KeyError:
            user_data = decode_userdata(members[str(user.id)])
            user_data.set_points(points)
            members[str(user.id)] = encode_userdata(user_data)

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
                user_data = decode_userdata(members[str(user.id)])
                user_data.update_xp(xp)
                # check to see if they crossed the threshold
                if needs_level_up(user_data.get_level()):
                    # level up
                    user_data.update_level(1)
                    # add points
                    award = calculate_levelup_points(user_data.get_level())
                    update_points(guild, user, award)
                members[str(user.id)] = encode_userdata(user_data)
        except KeyError:
            user_data = decode_userdata(members[str(user.id)])
            user_data.set_xp(xp)
            members[str(user.id)] = encode_userdata(user_data)

        collection.update_one(
            {'guild_id': guild.id},
            {"$set":
                {
                    'members': members
                }})
    else:
        members = create_guild_entry(guild)

    return members


def needs_level_up(current_level):
    return True


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
            return decode_userdata(members[str(user.id)]).get_points()
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
    doc = get_guild_doc(guild)

    if doc is None:
        create_guild_entry(guild)

        return 0
    else:
        members = doc['members']

        try:
            return decode_userdata(members[str(user.id)]).get_xp()
        except KeyError:
            create_user_entry(guild, user)

            return 0
