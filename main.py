import asyncio
from asyncio import start_server, run
from asyncio.exceptions import IncompleteReadError

from lxml import objectify

from lib.config import get_config
from lib.definitions import User, Room
from lib.events import eventHandlers
from lib.general_logging import setup_logging

# Logging
log = setup_logging()

# Load Configuration
config = get_config()

# Globals
counter = 1
rms = {1: Room("MLX_6_Lobby", 1), 42: Room("MLX_6_Team_Channel", 42)}


async def listen_for_messages(user: User):
    data = await user.reader.readuntil(b'\x00')
    try:
        message = data.decode('ascii')
    except UnicodeDecodeError:
        message = data.decode('utf-8')
    log.debug("Received :" + str(message))
    if len(message) == 0:
        log.info(f'{user.name}, {user.address} has disconnected')
        return
    return message


def get_commands(xml: objectify.ObjectifiedElement):
    return xml.body.attrib['action'], xml.body.attrib['r']


def parse_xml(message: str):
    try:
        xml = objectify.fromstring(message)
        return xml
    except Exception as e:
        log.error(f'Parse Error Occurred! ({e}) (message)')


async def call_handlers(self, rooms, command, xml, user, cntr):
    try:
        await eventHandlers[str(command)](self, rooms, xml, user, cntr)
    except KeyError as e:
        log.error(f"Command Failed to Execute! ({command}) ({e})")


async def ensure_disconnect(self, user):
    # Ensure Disconnection
    for room_id in rms:
        room = rms[room_id]
        if user.id in room.users:
            async with self.lock:
                await room.remove_user(user.id)
            for usr in room.users:
                await room.users[usr].send(
                    f"<msg t='sys'><body action='userGone' r='{user.room}'><user id='{user.id}' /></body></msg>")
                await room.users[usr].send(
                    f"<msg t='sys'><body action='uCount' r='{user.room}' u='{len(room.users)}'></body></msg>")
    log.info(f"Connection lost to {user.address}")


class Server:
    def __init__(self):
        self.user_count = 0
        self.lock = asyncio.Lock()

    async def handle(self, reader, writer):
        global counter
        async with self.lock:
            counter += 1
        user = User(reader, writer, counter)
        log.info(f'User {user.address} connected!')
        try:
            while True:
                try:
                    message = await listen_for_messages(user)
                except IncompleteReadError:
                    break
                if message is None:
                    break
                messages = message.split('\00')
                try:
                    messages.remove('')
                except ValueError:
                    pass
                for msg in messages:
                    xml = parse_xml(msg)
                    if xml is None:
                        continue
                    command, room = get_commands(xml)
                    try:
                        await call_handlers(self, rms, command, xml, user, counter)
                    except ConnectionResetError:
                        break
        finally:
            # Ensure Disconnection
            await ensure_disconnect(self, user)


async def main():
    server_obj = Server()
    server = await start_server(server_obj.handle, config['connection']['address'], config['connection']['port'])
    address = server.sockets[0].getsockname()
    log.info(f'Serving on Ip: {address[0]} Port: {address[1]}')
    async with server:
        await server.serve_forever()


run(main())
