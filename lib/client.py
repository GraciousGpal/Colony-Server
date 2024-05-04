import os
import urllib.error
import urllib.request
from asyncio import start_server, run, Lock
from asyncio.exceptions import IncompleteReadError
from charset_normalizer import from_bytes
from loguru import logger as log
from lxml import objectify

import lib.definitions as d
from lib.config import get_config
from lib.definitions import User
from lib.events import event_handlers
from lib.database import UserDatabase
# Load Configuration
config = get_config()
# Set Logging Level
os.environ["LOGURU_LEVEL"] = "DEBUG" if config['logging']['level'] == "debug" else "INFO"


def get_latest_version() -> int:
    """
    Gets the latest version no from the website, if it fails fall back to default value.
    :return:
    """
    try:
        with urllib.request.urlopen(
                "https://raw.githubusercontent.com/SynthKittenDev/Colony-Player/main/gameVersion"
        ) as f:
            return int(f.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(e.reason)
        return config["settings"]["version"]


def append_new_line(file_name: str, text_to_append: str) -> None:
    """Append given text as a new line at the end of file"""
    # Open the file in append & read mode ('a+')
    with open(file_name, "a+") as file_object:
        # Move read cursor to the start of file.
        file_object.seek(0)
        # If file is not empty then append '\n'
        data = file_object.read(100)
        if len(data) > 0:
            file_object.write("\n")
        # Append text at the end of file
        file_object.write(text_to_append)


async def listen_for_messages(user: User) -> None:
    """
    Reads Data from user stream until null terminator is found.
    :param user:
    :return:
    """
    data = await user.reader.readuntil(b"\x00")
    try:
        message = data.decode("ascii")
    except UnicodeDecodeError:
        try:
            message = data.decode("utf-8")
        except UnicodeDecodeError:
            try:
                log.warning("Using fallback")
                message = from_bytes(data).best()
                log.warning(f"Decode failed on : {str(message)}")
                # Write the failed data into file for analysis later on.
                append_new_line('unparsed.log', data)
            except Exception:
                return ""

    log.debug(f"Received :{str(message)}")
    if len(message) == 0:
        log.info(f"{user.name}, {user.address} has disconnected")
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
        log.error(f"Parse Error Occurred! ({e}) (message)", )


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
        log.error(f"Command Failed to Execute! ({command}) ({e})")


async def ensure_disconnect(self, user):
    """
    Makes sure the user is removed from all rooms and other clients in the same room are notified.
    :param self:
    :param user:
    :return:
    """
    try:
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
        # Buddy Exit Event
        if "guest_" not in user.name:
            buddies = self.database.get_buddies(user.name)
            for buddy_name in buddies:
                usr_found = await d.find_user(name=buddy_name)
                if usr_found is not None:
                    msg_bu = f"<msg t='sys'><body action='bUpd' r='-1'><b s='0' i='-1'><n><![CDATA[{user.name}]]></n></b></body></msg>"
                    await usr_found.send(msg_bu)
    except Exception as e:
        log.error(f"Error in ensure_disconnect! ({e})")
    finally:
        if user.id in d.current_guests_ids:
            async with self.lock:
                d.current_guests_ids.remove(user.id)
        log.info(f"Connection lost to {user.address}")


class Server:
    def __init__(self):
        self.user_count = 0
        self.lock = Lock()
        self.version = get_latest_version()
        self.database = UserDatabase(db_name=config["database"]["path"])


    async def get_new_id(self):
        """
        Get a new id for the user.
        :return:
        """
        counter = 0
        counters = self.database.get_all_ids()
        while True:
            counter += 1
            if counter not in counters:
                break
        async with self.lock:
            while True:
                counter += 1
                if counter not in d.current_guests_ids:
                    break
        return counter

    async def handle(self, reader, writer):
        """
        Handles in coming packets from the user.
        :param reader:
        :param writer:
        :return:
        """
        new_id = await self.get_new_id()
        user = User(reader, writer, new_id)
        log.info(f"User {user.address} connected!")
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
                
                try:
                    await self._process_messages(messages, user)
                except ConnectionResetError:
                    break
        finally:
            # Ensure Disconnection
            await ensure_disconnect(self, user)
    
    async def _process_messages(self, messages, user):
        """
        Send the connection string and processes the messages.
        :param messages:
        :param user:
        :return:
        """
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
            
            await call_handlers(self, command, xml, user)


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
    log.info(f"Serving on Ip: {address[0]} Port: {address[1]}")
    async with server:
        await server.serve_forever()


def start():
    """
    Starts the main function and the program.
    :return:
    """
    run(main())


def launch_discord():
    d.dc.run(os.getenv('DISCORD_API'))
