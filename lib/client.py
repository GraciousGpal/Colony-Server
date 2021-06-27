import urllib.error
import urllib.request
from asyncio import start_server, run, Lock
from asyncio.exceptions import IncompleteReadError

from lxml import objectify

import lib.definitions as d
from lib.config import get_config
from lib.definitions import User
from lib.events import event_handlers
from lib.general_logging import setup_logging

# Logging
log = setup_logging()

# Load Configuration
config = get_config()


def get_latest_version():
    """
    Gets the latest version no from the website, if it fails fall back to default value.
    :return:
    """
    try:
        with urllib.request.urlopen(
                "https://colony-game.000webhostapp.com/version"
        ) as f:
            return int(f.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(e.reason)
        return config["settings"]["version"]


async def listen_for_messages(user: User):
    """
    Reads Data from user stream until null terminator is found.
    :param user:
    :return:
    """
    data = await user.reader.readuntil(b"\x00")
    try:
        message = data.decode("ascii")
    except UnicodeDecodeError:
        message = data.decode("utf-8")
    log.debug("Received :%s", str(message))
    if len(message) == 0:
        log.info("%s, %s has disconnected", user.name, user.address)
        return
    return message


def get_commands(xml: objectify.ObjectifiedElement):
    """
    Returns an action and the room from the xml string.
    :param xml:
    :return:
    """
    return xml.body.attrib["action"]


def parse_xml(message: str):
    """
    Convert xml to a dictionary like object from string.
    :param message:
    :return:
    """
    try:
        xml = objectify.fromstring(message)
        return xml
    except Exception as e:
        log.error("Parse Error Occurred! (%s) (message)", e)


async def call_handlers(self, command, xml, user):
    """
    Calls the correct handler function given a command from xml.
    :param self:
    :param command:
    :param xml:
    :param user:
    :return:
    """
    try:
        await event_handlers[str(command)](self, xml, user)
    except KeyError as e:
        log.error("Command Failed to Execute! (%s) (%s)", command, e)


async def ensure_disconnect(self, user):
    """
    Makes sure the user is removed from all rooms and other clients in the same room are notified.
    :param self:
    :param user:
    :return:
    """
    for room_id in d.rms:
        room = d.rms[room_id]
        if user.id in room.users:
            async with self.lock:
                await room.remove_user(user.id)
            for usr in room.users:
                await room.users[usr].send(
                    f"<msg t='sys'><body action='userGone' r='{user.room}'><user id='{user.id}' /></body></msg>"
                )
                await room.users[usr].send(
                    f"<msg t='sys'><body action='uCount' r='{user.room}' u='{len(room.users)}'></body></msg>"
                )
    log.info("Connection lost to %s", user.address)


class Server:
    def __init__(self):
        self.user_count = 0
        self.lock = Lock()
        self.version = get_latest_version()

    async def handle(self, reader, writer):
        """
        Handles in coming packets from the user.
        :param reader:
        :param writer:
        :return:
        """
        async with self.lock:
            d.counter += 1
        user = User(reader, writer, d.counter)
        log.info("User %s connected!", user.address)
        try:
            while True:
                try:
                    message = await listen_for_messages(user)
                except IncompleteReadError:
                    break
                if message is None:
                    break
                messages = message.split("\00")
                try:
                    messages.remove("")
                except ValueError:
                    pass
                for msg in messages:
                    if msg == "<policy-file-request/>":
                        await user.send(
                            f"<cross-domain-policy><allow-access-from domain='*'"
                            f" to-ports='{config['connection']['port']}' /></cross-domain-policy>"
                        )
                        continue
                    xml = parse_xml(msg)
                    if xml is None:
                        continue
                    command = get_commands(xml)
                    try:
                        await call_handlers(self, command, xml, user)
                    except ConnectionResetError:
                        break
        finally:
            # Ensure Disconnection
            await ensure_disconnect(self, user)


async def main():
    """
    Main Loop of the Program initializes Server object, pass in config parameters and starts listening for users
    :return:
    """
    server_obj = Server()
    server = await start_server(
        server_obj.handle, config["connection"]["address"], config["connection"]["port"]
    )
    address = server.sockets[0].getsockname()
    log.info("Serving on Ip: %s Port: %s", address[0], address[1])
    async with server:
        await server.serve_forever()


def start():
    """
    Starts the main function and the program.
    :return:
    """
    run(main())
