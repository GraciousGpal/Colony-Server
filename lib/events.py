from asyncio import sleep
from loguru import logger as log
from sys import exit as sys_exit
from xml.etree import ElementTree as Et
from lxml import objectify

import lib.definitions as d
from lib.admin import is_mod
from lib.config import get_config
from lib.definitions import Room

# Load Configuration
from lib.exceptions import NewVarCase

config = get_config()


async def enable_communication(self, xml, user):
    """
    Allows the user to communicate to the server and sets user client version.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    comm_port = config["connection"]["port"]
    await user.send(
        f"<cross-domain-policy><allow-access-from domain='*' to-ports='{comm_port}' /></cross-domain-policy>"
    )
    version = xml.body.ver.attrib["v"]

    async with self.lock:
        user.client_version = int(version)

    await user.send("<msg t='sys'><body action='apiOK' r='0'></body></msg>")


async def login(self, xml, user):
    """
    Logins in the user and Checks if the user client version matches the server.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    msg = "<msg t='sys'><body action='logOK' r='0'><login n='{}' id='{}' mod='{}'/></body></msg>"
    if xml.body.login.nick.text != "":
        name = xml.body.login.nick.text
    else:
        name = f"guest_{user.id}"
        async with self.lock:
            d.current_guests_ids.append(user.id)
    mod = 1 if is_mod(str(name).lower()) else 0
    user_db_data = self.database.get_user_info(name)
    async with self.lock:
        user.name = name
        user.mod = mod
        if user_db_data is not None:
            user.id = user_db_data[0]
    await user.send(msg.format(user.name, user.id, user.mod))
    log.info(f"{user.name}({user.id}) logged in!")

    # Kick User if Version does not Match
    if user.client_version != int(self.version):
        await send_admin_message(
            user, msg="You do not have the Latest Version of the Game!"
        )
        await sleep(5)
        user.writer.close()
    # Create a new entry for user if not exists
    if "guest_" not in user.name:
        self.database.add_user(user.name)
    d.message_channel.put(user.name, block=False)

    # Buddy Join Event
    if "guest_" not in user.name:
        buddies = self.database.get_buddies(user.name)
        for buddy_name in buddies:
            usr_found = await d.find_user(name=buddy_name)
            if usr_found is not None:
                msg_bu = f"<msg t='sys'><body action='bUpd' r='-1'><b s='1' i='{user.id}'><n><![CDATA[{user.name}]]></n></b></body></msg>"
                await usr_found.send(msg_bu)


async def send_admin_message(user, msg):
    """
    Sends the user an admin message.
    :param user:
    :param msg:
    :return:
    """
    await user.send(
        f"<msg t='sys'><body action='dmnMsg' r='{user.room}'><user id='{user.id}'"
        f" /><txt><![CDATA[{msg}]]></txt></body></msg>"
    )


async def load_buddy_list(self, xml, user):
    """
    Loads buddies for the specified user.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    # Load Buddy List
    buddies = self.database.get_buddies(user.name)
    data_out = ""
    for buddy in buddies:
        bdy = await d.find_user(name=buddy)
        if bdy:
            data_out += f"<b s='1' i='{bdy.id}'><n><![CDATA[{buddy}]]></n></b>"
        else:
            data_out += f"<b s='0' i='-1'><n><![CDATA[{buddy}]]></n></b>"
    msg = f"<msg t='sys'><body action='bList' r='-1'><bList>{data_out}</bList></body></msg>"
    await user.send(msg)


async def get_room_list(self, xml, user):
    """
    Returns a list of all the rooms.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    msg = "<msg t='sys'><body action='rmList' r='0'><rmList>"
    rms = {k: d.rms[k] for k in d.rms if not d.rms[k].is_room_empy()}
    for r in rms:
        room = rms[r]
        msg += (
            f"<rm id='{room.id}' priv='{room.priv}' temp='{room.temp}'"
            f" game='{room.game}' ucnt='{room.ucnt}' maxu='{room.maxu}' "
            f"maxs='{room.maxs}'><n><![CDATA[{room.name}]]></n></rm>"
        )
    msg += "</rmList></body></msg>"
    await user.send(msg)


def game_room(rm_id):
    if d.rms[rm_id].random_factor != 0:
        return True
    return False


async def join_room(self, xml, user, room_join_id=None):
    """
    Makes a user join a room and update other users of the change.
    :param self:
    :param xml:
    :param user:
    :param room_join_id:
    :return:
    """
    r = xml.body.room.attrib
    if room_join_id is not None:
        r = {"id": room_join_id}
    selected_room = d.rms[int(r["id"])]
    msg = f"<msg t='sys'><body action='joinOK' r='{r['id']}'><pid id='{user.id}'/>"
    if game_room(selected_room.id):
        msg += "<vars>"
        properties = {
            "gameStart": (0, "b"),
            "gs": (d.rms[selected_room.id].gs, "n"),
            "randomFactor": (d.rms[selected_room.id].random_factor, "n"),
            "roomLeader": (d.rms[selected_room.id].room_leader, "n"),
        }
        for p in properties:
            msg += f"<var n='{p}' t='{properties[p][1]}'><![CDATA[{properties[p][0]}]]></var>"
        msg += f"</vars><uLs r='{r['id']}'>"
    else:
        msg += f"<vars /><uLs r='{r['id']}'>"

    async with self.lock:
        if user.room == -1:
            await d.rms[1].add_user(user)
        else:  # move
            if room_join_id is not None:
                await d.rms[user.room].move_user(user.id, room_join_id, user)
            else:
                await d.rms[user.room].move_user(
                    user.id, int(xml.body.room.attrib["id"]), user
                )

        # Remove Empty Rooms
        for r in d.rms.copy():
            room_to_be_removed = d.rms[r].id
            if d.rms[r].remove_room:
                removed_room = d.rms.pop(r, None)
                if removed_room is None:
                    log.error("Room not found in the dict!")

                for rm in d.rms:
                    for u in d.rms[rm].users:
                        await (
                            d.rms[rm]
                            .users[u]
                            .send(
                                f"<msg t='sys'><body action='roomDel'><rm id='{room_to_be_removed}'/></body></msg>"
                            )
                        )

    for u in selected_room.users:
        us = selected_room.users[u]
        msg += (
            f"<u i='{us.id}' m='{us.mod}'><n><![CDATA[{us.name}]]></n><vars></vars></u>"
        )
    msg += "</uLs></body></msg>"
    await user.send(msg)
    if len(selected_room.users) > 1:
        for u in selected_room.users:
            await selected_room.users[u].send(
                f"<msg t='sys'><body action='uCount' r='{selected_room.id}' u='{selected_room.ucnt}'></body></msg>"
            )
            if selected_room.users[u].id != user.id:
                await selected_room.users[u].send(
                    f"<msg t='sys'><body action='uER' r='{selected_room.id}'><u i ='{user.id}' m='{user.mod}' s='0'"
                    f" p='2'><n><![CDATA[{user.name}]]></n><vars><var n='rank' t='n'><![CDATA[{user.rank}]]></var>"
                    f"<var n='gamesPlayed' t='n'><![CDATA[{user.games_played}]]></var></vars></u></body></msg>"
                )

            # New user receives existing users' details
            if selected_room.users[u].id != user.id:  # Exclude the new user
                await user.send(
                    f"<msg t='sys'><body action='uER' r='{selected_room.id}'><u i ='{selected_room.users[u].id}' m='{selected_room.users[u].mod}' s='0'"
                    f" p='2'><n><![CDATA[{selected_room.users[u].name}]]></n><vars><var n='rank' t='n'><![CDATA[{selected_room.users[u].rank}]]></var>"
                    f"<var n='gamesPlayed' t='n'><![CDATA[{selected_room.users[u].games_played}]]></var></vars></u></body></msg>"
                )

    # Display welcome message when user enters main lobby.
    if int(d.rms[user.room].id) == 1:
        # await user.send(
        #    f"<msg t='sys'><body action='pubMsg' r='{d.rms[user.room].id}'><user id='{user.id}' /><txt>"
        #    f"<![CDATA[{config['welcome']['message']}]]></txt></body></msg>"
        # )

        welcome_msg = (
            f"<font size='20' color='#008000'>{config['welcome']['message']}</font>"
        )

        welcome_msg = f"<msg t='sys'><body action='prvMsg' r='{d.rms[user.room].id}'><user id='-1' /><txt><![CDATA[ColonyBot!!&amp;&amp;!!<br>{welcome_msg}]]></txt></body></msg>"
        await user.send(welcome_msg)

    log.info(
        f"User ({user.id}, {user.name}) Joined {d.rms[user.room].name} ({d.rms[user.room].id})"
    )


async def set_usr_variables(self, xml, user):
    """
    Sets User variables and updates other users of the changes.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    user = d.rms[user.room].users[user.id]
    room = d.rms[user.room].users
    usr_vars = {
        "userName": user.name,
        "race": user.race,
        "team": user.team,
        "color": user.color,
        "pts": user.pts,
        "gamesConsecutiveWins": user.games_consecutive_wins,
        "gamesWon": user.games_won,
        "gamesPlayed": user.games_played,
        "rank": user.rank,
    }
    for var in xml.body.vars.var:
        if var.attrib["n"] in usr_vars:
            async with self.lock:
                setattr(user, var.attrib["n"], var.text)
        else:
            raise NewVarCase(var.attrib["n"])

    for usr_id in room:
        for room_ in d.rms:
            for user_id in d.rms[room_].users:
                await (
                    d.rms[room_]
                    .users[user_id]
                    .send(
                        f"<msg t='sys'><body action='uCount' "
                        f"r='{d.rms[user.room].id}' u='{d.rms[user.room].ucnt}'></body></msg>"
                    )
                )
        if room[usr_id].id != room[usr_id].id:
            await room[usr_id].send(
                f"<msg t='sys'><body action='uVarsUpdate' r='{room[usr_id].room}'><user id='{room[usr_id].id}' />"
                f"<vars></vars></body></msg>"
            )


def check_for_commands(string: str):
    """
    Checks the message for a string command
    :param string:
    :return:
    """
    prefix = "/"
    commands = ["restart", "update", "showrooms"]
    pr_cmd = [f"{prefix}{x}" for x in commands]
    for cmd in pr_cmd:
        if cmd in string or cmd == string:
            return cmd
    return None


async def notify_all_users(msg):
    """
    Sends a message to all connected users.
    :param msg:
    :return:
    """
    for room in d.rms:
        for usr in d.rms[room].users:
            await send_admin_message(d.rms[room].users[usr], msg)


async def restart(user, sleep_time=10):
    """
    Exits the subprocess with code 42 causing the main thread to restart subprocess.
    :param user:
    :param sleep_time:
    :return:
    """
    log.info(f"Restart Triggered by {user.name} id: (user.id) addr: ({user.address})")
    await notify_all_users(f"Server is about to restart in {sleep_time}s.")
    await sleep(sleep_time)
    sys_exit(42)


async def update(user, sleep_time=10):
    """
    Exits the subprocess with code 43 causing the main thread to execute 'git pull' and restart subprocess.
    :param user:
    :param sleep_time:
    :return:
    """
    log.info(f"Update Triggered by {user.name} id: ({user.id}) addr: ({user.address})")
    await notify_all_users(
        f"Server is about to restart for an update in {sleep_time}s."
    )
    await sleep(sleep_time)
    sys_exit(43)


async def show_rooms(user):
    """
    Prints a list of rooms with users in lobby
    :param user:
    :return:
    """
    msg = ""
    for room in d.rms:
        msg += (
            f"{d.rms[room].name} ({d.rms[room].id}):"
            f" [{[(d.rms[room].users[usr].name, d.rms[room].users[usr].id) for usr in d.rms[room].users]}]\n"
        )
    for usr_id in d.rms[user.room].users:
        await (
            d.rms[user.room]
            .users[usr_id]
            .send(
                f"<msg t='sys'><body action='pubMsg' r='{d.rms[user.room].id}'>"
                f"<user id='{user.id}' /><txt><![CDATA[{msg}]]></txt></body></msg>"
            )
        )


async def process_custom_commands(cmd, user):
    """
    Execute text commands from in game chat room.
    :param cmd:
    :param user:
    :return:
    """
    if cmd is not None and is_mod(user.name):
        if cmd == "/restart":
            await restart(user)
        if cmd == "/update":
            await restart(user)
    if cmd == "/showrooms":
        await show_rooms(user)


async def publish_message(self, xml, user):
    """
    Sends a message to users in the room or execute string commands.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    cmd = check_for_commands(xml.body.txt)
    await process_custom_commands(cmd, user)
    room = d.rms[user.room].users
    for usr_id in room:
        await room[usr_id].send(
            f"<msg t='sys'><body action='pubMsg' r='{d.rms[user.room].id}'>"
            f"<user id='{user.id}' /><txt><![CDATA[{xml.body.txt}]]></txt></body></msg>"
        )


async def create_room(self, xml, user):
    """
    Creates a room that users can join.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    async with self.lock:
        d.counter += 1

    msg = f"<msg t='sys'><body action='roomAdd' r='{d.rms[user.room].id}'>"
    msg += (
        f"<rm id = '{d.counter}' priv = '0' temp = '{xml.body.room.attrib['tmp']}'"
        f" game = '{xml.body.room.attrib['gam']}' max = '4' spec = '{xml.body.room.attrib['spec']}'"
        f" limbo = '0' ><name><![CDATA[{xml.body.room.name.text}]]></name><vars /></rm></body></msg>"
    )

    async with self.lock:
        d.rms[d.counter] = Room(xml.body.room.name.text, d.counter)
        d.rms[d.counter].temp = xml.body.room.attrib["tmp"]
        d.rms[d.counter].game = xml.body.room.attrib["gam"]
        d.rms[d.counter].maxu = 4
        d.rms[d.counter].maxs = xml.body.room.attrib["spec"]
    for usr_id in d.rms[user.room].users:
        await d.rms[user.room].users[usr_id].send(msg)
    log.info(f"{user.name}({user.id}) created the room {d.rms[d.counter].name}")
    if int(xml.body.attrib["r"]) in d.rms:
        await join_room(self, xml, user, d.counter)

        try:
            room_exited = int(xml.body.room.attrib["exit"])
            msg = f"<msg t='sys'><body action='userGone' r='{room_exited}'><user id='{user.id}' /></body></msg>"
            for usr_id in d.rms[room_exited].users:
                await d.rms[room_exited].users[usr_id].send(msg)
        except Exception as e:
            log.error(e)


async def set_room_variables(self, xml, user):
    """TODO Finish Implementation
    Set Variables in a room.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    msg = f"<msg t='sys'><body action='rVarsUpdate' r='{user.room}'><vars>"
    for x in xml.body.vars.var:
        msg += f"<var n='{x.attrib['n']}' t='{x.attrib['t']}'><![CDATA[{xml.body.vars.var.text}]]></var>"
        if x.attrib["n"] == "gs":
            async with self.lock:
                d.rms[user.room].gs = x.text
        elif x.attrib["n"] == "roomLeader":
            async with self.lock:
                d.rms[user.room].room_leader = x.text
        elif x.attrib["n"] == "randomFactor":
            async with self.lock:
                d.rms[user.room].random_factor = x.text
    msg += "</vars></body></msg>"
    await user.send(msg)


async def as_obj(self, xml, user):
    """
    Processes certain action script objects and sends them to clients
    :param self:
    :param xml:
    :param user:
    :return:
    """
    room_id = xml.body.attrib["r"]
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars["rm_id"] = room_id

    if rm_vars["id"] == "updateIncome":
        # Get User Position and "Race"
        user_data = {}
        for var in dict_format_obj.obj.var:
            user_data[var.attrib["n"]] = var.text
        msg = (
            f"<msg t='sys'><body action='dataObj' r='{room_id}'><user id='{user.id}' /><dataObj>"
            f"<![CDATA[<dataObj><var n='id' t='s'>updateIncome</var><obj t='o' o='sub'><var n='pos'"
            f" t='n'>{user_data['pos']}</var><var n='race' t='n'>{user_data['race']}</var></obj>"
            f"</dataObj>]]></dataObj></body></msg>"
        )

        for usr in d.rms[int(rm_vars["rm_id"])].users:
            if int(user.id) != int(usr):
                await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)

    elif rm_vars["id"] == "sendChat":
        await send_ally_chat(user, rm_vars, dict_format_obj)

    if rm_vars["id"] == "updateTeamDisplay":
        array = get_array_objects(dict_format_obj, xml.body.text)
        array_key = "arrayId" if "arrayId" in array else "array"
        for idx, var in enumerate(array[array_key]):
            async with self.lock:
                d.rms[int(room_id)].usr_pos[int(idx)] = var


async def kill_unit(rm_vars, dict_format_obj):
    """
    Kills a Unit and updates other users in the room of the change.
    :param rm_vars:
    :param dict_format_obj:
    :return:
    """
    data = {}
    for var in dict_format_obj.obj.var:
        data[var.attrib["n"]] = (var.text, var.attrib["t"])
    msg = (
        f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}'/><dataObj>"
        f"<![CDATA[<dataObj><var n='id' t='s'>killUnit</var><obj o='sub' t='a'>"
    )
    for item in data:
        msg += f"<var n='{item}' t='{data[item][1]}'>{data[item][0]}</var>"
    msg = f"{msg}</obj></dataObj>]]></dataObj></body></msg>"
    for usr in d.rms[int(rm_vars["rm_id"])].users:
        await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)


async def send_ally_chat(user, rm_vars, dict_format_obj, ally=False):
    """
    Sends messages in a game room to allies or all users.
    :param ally:
    :param user:
    :param rm_vars:
    :param dict_format_obj:
    :return:
    """
    msg = (
        f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'>"
        f"<user id='{user.id if not ally else rm_vars['_$$_']}' />"
        f"<dataObj><![CDATA[<dataObj><obj t='o' o='sub'>"
    )
    for var in dict_format_obj.obj.var:
        msg += f"<var n='{var.attrib['n']}' t='{var.attrib['t']}'>{var.text}</var>"
    msg = f"{msg}</obj><var n='id' t='s'>{rm_vars['id']}</var></dataObj>]]></dataObj></body></msg>"

    for usr in d.rms[int(rm_vars["rm_id"])].users:
        if ally:
            if int(usr) == int(rm_vars["_$$_"]):
                await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)
        else:
            if usr == user.id:
                continue
            await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)


async def as_obj_g(self, xml, user):
    """
    Handler for action script objects in a game.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    room_id = xml.body.attrib["r"]
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars["rm_id"] = room_id

    if rm_vars["id"] == "updateTeamDisplay":
        await update_team_display(self, xml, rm_vars, dict_format_obj)

    elif rm_vars["id"] == "beginGame":
        await begin_game(xml, rm_vars, dict_format_obj)

    elif rm_vars["id"] == "killUnit":
        await kill_unit(rm_vars, dict_format_obj)

    elif rm_vars["id"] == "orderUnit":
        await order_unit(rm_vars, dict_format_obj)

    elif rm_vars["id"] == "sendChat":
        await send_ally_chat(user, rm_vars, dict_format_obj, True)

    elif rm_vars["id"] == "sendTeamChat":
        log.warning(f"sendTeamChat: {xml}")
    elif rm_vars["id"] == "getKicked":
        user_id_to_kick = rm_vars["_$$_"]
        if user_id_to_kick is not None and user_id_to_kick != "":
            await kick_user(xml, int(user_id_to_kick))

    else:  # TODO Remove once project is feature complete
        raise NewVarCase(rm_vars["id"])


async def kick_user(xml, user_id):
    """
    Kick a user from the room.
    """
    room_id = int(xml.body.attrib["r"])
    msg = f"<msg t='sys'><body action='dataObj' r='{room_id}'><user id='{user_id}' /><dataObj><![CDATA[<dataObj><obj o='sub' t='a'></obj><var n='id' t='s'>getKicked</var></dataObj>]]></dataObj></body></msg>"
    exit_msg = f"<msg t='sys'><body action='userGone' r='{room_id}'><user id='{user_id}' /></body></msg>"
    found_user = await d.find_user(user_id=user_id)
    if found_user is not None:
        await found_user.send(msg)
        for usr_id in d.rms[room_id].users:
            await d.rms[room_id].users[usr_id].send(exit_msg)


async def order_unit(rm_vars, dict_format_obj):
    """
    Process orders given to units and relays it to other users in room.
    :param rm_vars:
    :param dict_format_obj:
    :return:
    """
    unt_cmd = dict_format_obj.obj.var.text
    msg = (
        f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}' />"
        f"<dataObj><![CDATA[<dataObj>"
        f"<var n='id' t='s'>orderUnit</var><obj o='sub' t='a'>"
        f"<var n='id' t='n'>{unt_cmd}</var><obj o='orderArray' t='a'>"
    )

    for x in dict_format_obj.obj.obj.var:
        msg += f"<var n='{x.attrib['n']}' t='{x.attrib['t']}'>{x.text}</var>"
    msg += "</obj></obj></dataObj>]]></dataObj></body></msg>"

    for usr in d.rms[int(rm_vars["rm_id"])].users:
        await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)


async def update_team_display(self, xml, rm_vars, dict_obj):
    arrays = get_array_objects(dict_obj, xml.body.text)
    msg = (
        f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}' />"
        f"<dataObj><![CDATA[<dataObj><var n='id' t='s'>updateTeamDisplay</var>"
        f"<obj t='o' o='sub'><obj t='a' o='array'>"
    )
    for idx, item in enumerate(arrays["array"]):
        msg += f"<var n='{idx}' t='s'>{item}</var>"
    msg += "</obj></obj></dataObj>]]></dataObj></body></msg>"
    async with self.lock:
        for idx, var in enumerate(arrays["array"]):
            d.rms[int(rm_vars["rm_id"])].usr_pos[idx] = var
    for usr in d.rms[int(rm_vars["rm_id"])].users:
        await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)


async def begin_game(xml, rm_vars, dict_obj):
    """
    Initiates a game from a room
    :param xml:
    :param rm_vars:
    :param dict_obj:
    :return:
    """
    arrays = get_array_objects(dict_obj, xml.body.text)
    rm_vars["randName"] = dict_obj.obj.var.text
    msg = (
        f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}' /><dataObj>"
        f"<![CDATA[<dataObj><var n='id' t='s'>beginGame</var><obj t='o' o='sub'>"
        f"<var n='randName' t='s'>{rm_vars['randName']}</var>"
    )
    for obj_type in arrays:
        msg += f"<obj t='a' o='{obj_type}'>"
        for idx, item in enumerate(arrays[obj_type]):
            msg += f"<var n='{idx}' t='s'>{item}</var>"
        msg += "</obj>"
    msg += "</obj></dataObj>]]></dataObj></body></msg>"
    for usr in d.rms[int(rm_vars["rm_id"])].users:
        await d.rms[int(rm_vars["rm_id"])].users[usr].send(msg)

    user_names = [
        (
            d.rms[int(rm_vars["rm_id"])].users[user].name,
            d.rms[int(rm_vars["rm_id"])].users[user].id,
        )
        for user in d.rms[int(rm_vars["rm_id"])].users
    ]
    log.info(
        f"A game has started in room {d.rms[int(rm_vars['rm_id'])].name}({rm_vars['rm_id']}) with {user_names}"
    )


async def xt_req(self, xml, user):
    """
    Handles in game communication which is done using arrays.
    Function takes an xml object and send users in the room an array.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    room_id = xml.body.attrib["r"]
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars["rm_id"] = room_id
    tree = Et.ElementTree(Et.fromstring(xml.body.text))
    if "cmd" in rm_vars:
        data_to_send = {}
        da = [5, 0, 0, 0, 0, 0, 0, 0]

        if rm_vars["cmd"] == "s":
            async with self.lock:
                # Set user ids and position.
                arrays = get_array_objects(dict_format_obj, xml.body.text)
                d.rms[int(rm_vars["rm_id"])].user_pos_id = arrays["setArray"]
        if rm_vars["cmd"] == "m":
            for var in dict_format_obj.obj.var:
                data_to_send[var.attrib["n"]] = var.text

            da[1] = room_id
            da[2] = ""
            if "option" in data_to_send:
                da[2] = data_to_send["option"]
            da[3] = data_to_send["pos"]
            da[4] = data_to_send["cmd"]

            # Used by Buildings
            if data_to_send["cmd"] == "0":
                building_vars = {}
                for var in tree.findall("obj/obj/var"):
                    building_vars[var.attrib["n"]] = var.text
                da[5] = building_vars["building"]
                da[6] = int(building_vars["cancelOrder"])
                da[7] = int(building_vars["auto"])

            # Used by Units
            elif data_to_send["cmd"] == "1":
                unit_vars = {"random": []}
                for var in dict_format_obj.obj.obj.var:
                    unit_vars[var.attrib["n"]] = var.text
                for var in dict_format_obj.obj.obj.obj.var:
                    unit_vars["random"].append(var.text)

                da[5] = unit_vars["setId"]
                da_m = da[:6]
                for idx, item in enumerate(unit_vars["random"]):
                    if len(unit_vars["random"]) > 2:
                        da_m.append(item)
                    else:
                        idx = idx + 6
                        da[idx] = item
                if len(unit_vars["random"]) > 2:
                    da = da_m

            # Used by Missiles
            elif data_to_send["cmd"] == "2":
                missile_vars = {}
                for var in dict_format_obj.obj.obj.var:
                    missile_vars[var.attrib["n"]] = var.text
                da[5] = missile_vars["tar"]
                da[6] = missile_vars["px"]
                da[7] = missile_vars["py"]

            msg = "%xt%"
            for item in da:
                msg += f"{item}%"
            users = d.rms[int(rm_vars["rm_id"])].users
            for usr in users:
                await users[usr].send(msg)


def get_array_objects(dict_obj, xml_text):
    """
    Returns all array objects contained in the xml.
    :param dict_obj:
    :param xml_text:
    :return:
    """
    arrays = {}
    if "array" in xml_text.lower():
        for obj in dict_obj.obj.obj:
            arrays[obj.attrib["o"]] = []
            for var in obj.var:
                arrays[obj.attrib["o"]].append(var.text)
    return arrays


def get_room_vars(obj):
    """
    Get Room Variables
    :param obj:
    :return:
    """
    rm_vars = {}
    for var in obj.var:
        rm_vars[var.attrib["n"]] = var.text
    return rm_vars


async def add_to_buddy_list(self, xml, user):
    """
    Adds a user to the buddy list.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    if self.database.get_user_info(xml.body.n.text) is not None:
        self.database.add_buddy(user.name, xml.body.n.text)
        msg = f"<msg t='sys'><body action='bAdd' r='-1'><b s='1' i='0'><n><![CDATA[{xml.body.n.text}]]></n></b></body></msg>"
        await user.send(msg)
    else:
        log.error(f"User {user.name} not found in database!")


async def send_private_message(self, xml, user):
    """
    Sends a private message to a user.
    :param self:
    :param xml:
    :param user:
    :return:
    """
    try:
        msg_obj = xml.body.txt.text
        target_user_id = xml.body.txt.attrib["rcp"]
        target_msg = msg_obj.split("!")[-1]

        target_user = await d.find_user(user_id=int(target_user_id))
        if target_user is None:
            log.error("User not found in Rooms")
            return
        log.info(f"Private Message from {user.name} to {target_user.name}")
        msg = f"<msg t='sys'><body action='prvMsg' r='{target_user.room}'><user id='{target_user.id}' /><txt><![CDATA[{user.name}!!&amp;&amp;!!{target_msg}]]></txt></body></msg>"
        await target_user.send(msg)
    except Exception as e:
        log.error(f"Error: {e}")


# Dictionary of Client Commands mapped to their handling functions
event_handlers = {
    "verChk": enable_communication,
    "login": login,
    "loadB": load_buddy_list,
    "addB": add_to_buddy_list,
    "prvMsg": send_private_message,
    "getRmList": get_room_list,
    "joinRoom": join_room,
    "setUvars": set_usr_variables,
    "pubMsg": publish_message,
    "createRoom": create_room,
    "setRvars": set_room_variables,
    "asObj": as_obj,
    "asObjG": as_obj_g,
    "xtReq": xt_req,
}
