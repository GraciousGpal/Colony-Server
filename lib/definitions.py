import asyncio
from multiprocessing import Queue
from queue import Empty

import discord
from loguru import logger as log

from lib.exceptions import UserNotFoundInRoom

dc = discord.Client(intents=discord.Intents.default())

message_channel = Queue()


@dc.event
async def on_ready():
    log.info(f'{dc.user} has connected to Discord!')
    channel = dc.get_channel(934229000392433675)
    while True:
        try:
            # If `False`, the program is not blocked, it will throw the Queue.Empty exception.
            user = message_channel.get(False)
            await channel.send(f"{user} has joined the lobby!")
        except Empty:
            await asyncio.sleep(1)


class User:
    def __init__(self, reader, writer, id_):
        self.room = -1
        self.id = id_
        self.mod = 0
        self.name = ""
        self.password = ""
        self.race = 0
        self.rank = 1
        self.games_played = 0
        self.games_won = 0
        self.games_consecutive_wins = 0
        self.team = 0
        self.color = 0
        self.pts = 0
        self.reader = reader
        self.writer = writer
        self.address = writer.get_extra_info("peername")

    @staticmethod
    def clean(a):
        """
        Formats the message properly to the client format
        this function must be used before sending or client wont recognise
        """
        a = a + "\x00"
        try:
            a = a.encode("ascii")
        except UnicodeEncodeError:
            a = a.encode("UTF-8")
        return a

    async def send(self, data):
        """
        Send Data to the target
        :param data:
        :return:
        """
        data = self.clean(data)
        self.writer.write(data)
        log.debug(f"Sent: {data}")
        await self.writer.drain()


class Room:
    def __init__(self, name, id_):
        self.id = id_
        self.priv = 0
        self.temp = 0
        self.game = 0
        self.pwd = ""  # Room Password
        self.ucnt = 0  # User count
        self.maxu = 100  # Max User Count
        self.maxs = 0  # Max Spectator Count
        self.name = name
        self.gs = 0  # Game type
        self.random_factor = 0  # Random Factor
        self.room_leader = 0  # Room Leader
        self.users = {}
        self.usr_pos = [None, None, None, None]
        self.user_pos_id = [0, 0, 0, 0]
        self.remove_room = False
        self.client_version = 0
        self.ally = 0  # all chat or ally chat

    async def add_user(self, user: User):
        """
        Adds User to the room, sets user id and increments room user count.
        :param user:
        :return:
        """
        user.room = self.id
        self.users[user.id] = user
        self.ucnt += 1

    async def remove_user(self, user_id: int):
        """
        Removes User from room, decrements user count and check if room is empty
        :param user_id:
        :return:
        """
        user = self.users.pop(user_id)
        if user is not None:
            self.ucnt -= 1
            self.is_room_empy()
        else:
            raise UserNotFoundInRoom

    async def move_user(self, user_id: int, dst: int, user):
        """
        Moves a user from the room to the destination.
        :param user_id:
        :return:
        """
        if self.id == dst:
            user.room = self.id
            self.users[user.id] = user
            self.ucnt += 1
            return
        user = self.users.pop(user_id, None)
        if user is not None:
            self.ucnt -= 1
            user.room = dst
            rms[dst].users[user.id] = user
            rms[dst].ucnt += 1
            self.is_room_empy()
        else:
            raise UserNotFoundInRoom

    def is_room_empy(self):
        """
        Checks if the Room is Empty and Returns True/False
        :return:
        """
        if len(self.users) == 0 and self.id != 1 and self.id != 42:
            self.remove_room = True
            return True
        return False
    
    def is_user_in_room(self, user):
        """
        Checks if the user is in the room.
         :param user:
         :return:
        """
        return user.id in self.users


# Global Counter
counter = 1
current_guests_ids = []

# Default Rooms
rms = {1: Room("MLX_6_Lobby", 1), 42: Room("MLX_6_Team_Channel", 42)}


async def find_user(user=None, user_id=None, name=None):
    """
    Find a user in the room.
    :param user:
    :return:
    """
    if user is not None and isinstance(user, User):
        for room in rms.values():
            if user.id in room.users:
                return room.users[user.id]
    elif name is not None:
        for room in rms.values():
            for usr in room.users.values():
                if usr.name == name:
                    return usr
    else:
        for room in rms.values():
            for usr in room.users.values():
                if usr.id == user_id:
                    return room.users[user_id]
    return None