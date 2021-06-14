from logging import getLogger

from lxml import objectify

from lib.admin import is_mod
from lib.config import get_config
from lib.definitions import Room

# Load Configuration
config = get_config()

log = getLogger(__name__)


async def version_check(self, rms, xml, user, _):
    # Allow Further Communications
    comm_port = config['connection']['port']
    await user.send(
        f"<cross-domain-policy><allow-access-from domain='*' to-ports='{comm_port}' /></cross-domain-policy>")
    version = xml.body.ver.attrib['v']
    action = 'apiOK'
    if version != config['settings']['version']:
        action = 'apiKO'
    await user.send(f"<msg t='sys'><body action='{action}' r='0'></body></msg>")


async def login(self, rms, xml, user, _):
    msg = "<msg t='sys'><body action='logOK' r='0'><login n='{}' id='{}' mod='{}'/></body></msg>"
    name = f"guest_{user.id}"
    if xml.body.login.nick.text != "":
        name = xml.body.login.nick.text
    mod = 1 if is_mod(str(name).lower()) else 0
    async with self.lock:
        user.name = name
        user.mod = mod
    await user.send(msg.format(user.name, user.id, user.mod))


async def loadBuddyList(self, rms, xml, user, _):
    # Load Buddy List #TODO Implement Buddy list, currently returns emtpy response.
    msg = "<msg t='sys'><body action='bList' r='-1'><bList></bList></body></msg>"
    await user.send(msg)


async def getRoomList(self, rms, xml, user, _):
    msg = "<msg t='sys'><body action='rmList' r='0'><rmList>"
    for r in rms:
        room = rms[r]
        msg += f"<rm id='{room.id}' priv='{room.priv}' temp='{room.temp}' game='{room.game}' ucnt='{room.ucnt}' maxu='{room.maxu}' maxs='{room.maxs}'><n><![CDATA[{room.name}]]></n></rm>"
    msg += "</rmList></body></msg>"
    await user.send(msg)


# <msg t='sys'><body action='joinRoom' r='-1'><room id='1' pwd='' spec='0' leave='0' old='-1' /></body></msg>
async def join_room(self, rms, xml, user, counter, room_join_id=None):
    r = xml.body.room.attrib
    if room_join_id is not None:
        r = {'id': room_join_id}
    selected_room = rms[int(r['id'])]
    msg = f"<msg t='sys'><body action='joinOK' r='{r['id']}'><pid id='{user.id}'/><vars /><uLs r='{r['id']}'>"

    async with self.lock:
        if user.room == -1:
            await rms[1].add_user(user)
        else:  # move
            if room_join_id is not None:
                await rms[user.room].move_user(rms, user.id, room_join_id, user)
            else:
                await rms[user.room].move_user(rms, user.id, int(xml.body.room.attrib['id']), user)

    for u in selected_room.users:
        us = selected_room.users[u]
        msg += f"<u i='{us.id}' m='{us.mod}'><n><![CDATA[{us.name}]]></n><vars></vars></u>"
    msg += f"</uLs></body></msg>"
    await user.send(msg)
    if len(selected_room.users) > 1:
        for u in selected_room.users:
            await selected_room.users[u].send(
                f"<msg t='sys'><body action='uCount' r='{selected_room.id}' u='{selected_room.ucnt}'></body></msg>")
            if selected_room.users[u].id != user.id:
                await selected_room.users[u].send(
                    f"<msg t='sys'><body action='uER' r='{selected_room.id}'><u i ='{user.id}' m='0'><n><![CDATA[{user.name}]]></n><vars></vars></u></body></msg>")


# <msg t='sys'><body action='setUvars' r='1'><vars><var n='rank' t='n'><![CDATA[1]]></var><var n='gamesPlayed' t='n'><![CDATA[4]]></var></vars></body></msg>
async def set_usr_variables(self, rms, xml, user, _):
    user = rms[user.room].users[user.id]
    room = rms[user.room].users
    for var in xml.body.vars.var:
        if var.attrib['n'] == "rank":
            async with self.lock:
                user.rank = var.text
        elif var.attrib['n'] == 'gamesPlayed':
            async with self.lock:
                user.rank = var.text
        elif var.attrib['n'] == 'gamesWon':
            async with self.lock:
                user.gamesWon = var.text
        elif var.attrib['n'] == 'gamesConsecutiveWins':
            async with self.lock:
                user.gamesConsecutiveWins = var.text
        else:
            raise Exception(f"Found a new var case.({var})")

    for usr_id in room:
        for room_ in rms:
            for user_id in rms[room_].users:
                await rms[room_].users[user_id].send(
                    f"<msg t='sys'><body action='uCount' r='{rms[user.room].id}' u='{rms[user.room].ucnt}'></body></msg>")
        if room[usr_id].id != room[usr_id].id:
            await room[usr_id].send(
                f"<msg t='sys'><body action='uVarsUpdate' r='{room[usr_id].room}'><user id='{room[usr_id].id}' /><vars></vars></body></msg>")


async def publish_message(self, rms, xml, user, _):
    room = rms[user.room].users
    for usr_id in room:
        await room[usr_id].send(
            f"<msg t='sys'><body action='pubMsg' r='{rms[user.room].id}'><user id='{user.id}' /><txt><![CDATA[{xml.body.txt}]]></txt></body></msg>")


# b"<msg t='sys'><body action='roomAdd' r='0'><rm id='5' priv='0' temp='1' game='1' max='4' spec='4' limbo='0'><name><![CDATA[MLX_6_Limbo]]></name><vars /></rm></body></msg>\x00"
async def create_room(self, rms, xml, user, counter, game_room=False):
    async with self.lock:
        counter += 1
    msg = f"<msg t='sys'><body action='roomAdd' r='{rms[user.room].id}'>"
    msg += f"<rm id = '{counter}' priv = '0' temp = '{xml.body.room.attrib['tmp']}' game = '{xml.body.room.attrib['gam']}' max = '4' spec = '{xml.body.room.attrib['spec']}' limbo = '0' ><name><![CDATA[{xml.body.room.name.text}]]></name><vars /></rm></body></msg>"
    async with self.lock:
        rms[counter] = Room(xml.body.room.name.text, counter)
        rms[counter].temp = xml.body.room.attrib['tmp']
        rms[counter].game = xml.body.room.attrib['gam']
        rms[counter].maxu = 4
        rms[counter].maxs = xml.body.room.attrib['spec']
    for usr_id in rms[user.room].users:
        await rms[user.room].users[usr_id].send(msg)
    await join_room(self, rms, xml, user, counter, counter)


# 2021-06-12 00:27:38,358 - root - DEBUG - Received :<msg t='sys'><body action='setRvars' r='1'><vars><var n='roomLeader' t='n' pr='0' pe='0'><![CDATA[1]]></var><var n='randomFactor' t='n' pr='0' pe='0'><![CDATA[2.2130795242264867]]></var><var n='gs' t='n' pr='0' pe='0'><![CDATA[0]]></var><var n='gameStart' t='b' pr='0' pe='0'><![CDATA[0]]></var></vars></body></msg>
async def set_room_variables(self, rms, xml, user, _):
    msg = f"<msg t='sys'><body action='rVarsUpdate' r='{user.room}'><vars>"
    for x in xml.body.vars.var:
        msg += f"<var n='{x.attrib['n']}' t='{x.attrib['t']}'><![CDATA[{xml.body.vars.var.text}]]></var>"
        if x.attrib['n'] == 'gs':
            async with self.lock:
                rms[user.room].gs = xml.body.vars.var.text
    msg += "</vars></body></msg>"
    await user.send(msg)


# <msg t='sys'><body action='asObj' r='11'><![CDATA[<dataObj><var n='id' t='s'>updateTeamDisplay</var><obj t='o' o='sub'><obj t='a' o='array'><var n='0' t='s'>None</var><var n='1' t='s'>None</var><var n='2' t='s'>None</var><var n='3' t='s'>None</var></obj></obj></dataObj>]]></body></msg>
async def asObj_(self, rms, xml, user, _):
    room_id = xml.body.attrib['r']
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars['rm_id'] = room_id

    if rm_vars['id'] == 'updateIncome':
        # Get User Position and "Race"
        user_data = {}
        for var in dict_format_obj.obj.var:
            user_data[var.attrib['n']] = var.text
        msg = f"<msg t='sys'><body action='dataObj' r='{room_id}'><user id='{user.id}' /><dataObj>" \
              f"<![CDATA[<dataObj><var n='id' t='s'>updateIncome</var><obj t='o' o='sub'><var n='pos'" \
              f" t='n'>{user_data['pos']}</var><var n='race' t='n'>{user_data['race']}</var></obj></dataObj>]]></dataObj></body></msg>"
        await user.send(msg)

    if rm_vars['id'] == 'updateTeamDisplay':
        array = get_array_objects(dict_format_obj, xml.body.text)
        array_key = 'arrayId' if 'arrayId' in array else 'array'
        for idx, var in enumerate(array[array_key]):
            async with self.lock:
                rms[int(room_id)].usr_pos[int(idx)] = var


# b"<msg t='sys'><body action='dataObj' r='6'><user id='5'
# /><dataObj><![CDATA[<dataObj><var n='id' t='s'>killUnit</var>
# <obj o='sub' t='a'><var n='id' t='s'>p1_154</var>
# <var n='ran' t='n'>0</var><var n='p' t='n'>0</var></obj></dataObj>]]>
# </dataObj></body></msg>\x00"
async def kill_unit(self, rms, xml, user, rm_vars, dict_format_obj):
    data = {}
    for var in dict_format_obj.obj.var:
        data[var.attrib['n']] = (var.text, var.attrib['t'])
    msg = f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}'/><dataObj><![CDATA[<dataObj><var n='id' t='s'>killUnit</var><obj o='sub' t='a'>"
    for item in data:
        msg += f"<var n='{item}' t='{data[item][1]}'>{data[item][0]}</var>"
    msg = f"{msg}]]></dataObj></body></msg>"
    for usr in rms[int(rm_vars['rm_id'])].users:
        await rms[int(rm_vars['rm_id'])].users[usr].send(msg)


# b"<msg t='sys'><body action='asObjG' r='11'><![CDATA[<dataObj><var n='_$$_' t='s'>19</var><obj t='o' o='sub'><obj t='a' o='array'><var n='0' t='s'>None</var><var n='1' t='s'>None</var><var n='2' t='s'>None</var><var n='3' t='s'>None</var></obj></obj><var n='id' t='s'>updateTeamDisplay</var></dataObj>]]></body></msg>\x00"
async def asObjG_(self, rms, xml, user, counter):
    room_id = xml.body.attrib['r']
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars['rm_id'] = room_id

    if rm_vars['id'] == 'updateTeamDisplay':
        await updateTeamDisplay(self, rms, xml, rm_vars, dict_format_obj)

    if rm_vars['id'] == 'beginGame':
        await beginGame(self, rms, xml, user, rm_vars, dict_format_obj, counter)

    if rm_vars['id'] == 'killUnit':
        await kill_unit(self, rms, xml, user, rm_vars, dict_format_obj)


async def updateTeamDisplay(self, rms, xml, rm_vars, dict_obj):
    arrays = get_array_objects(dict_obj, xml.body.text)
    msg = f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}' /><dataObj><![CDATA[<dataObj><var n='id' t='s'>updateTeamDisplay</var><obj t='o' o='sub'><obj t='a' o='array'>"
    for idx, item in enumerate(arrays['array']):
        msg += f"<var n='{idx}' t='s'>{item}</var>"
    msg += "</obj></obj></dataObj>]]></dataObj></body></msg>"
    async with self.lock:
        for idx, var in enumerate(arrays['array']):
            rms[int(rm_vars['rm_id'])].usr_pos[idx] = var
    for usr in rms[int(rm_vars['rm_id'])].users:
        await rms[int(rm_vars['rm_id'])].users[usr].send(msg)


async def beginGame(self, rms, xml, user, rm_vars, dict_obj, counter):
    arrays = get_array_objects(dict_obj, xml.body.text)
    rm_vars['randName'] = dict_obj.obj.var.text
    msg = f"<msg t='sys'><body action='dataObj' r='{rm_vars['rm_id']}'><user id='{rm_vars['_$$_']}' /><dataObj><![CDATA[<dataObj><var n='id' t='s'>beginGame</var><obj t='o' o='sub'><var n='randName' t='s'>{rm_vars['randName']}</var>"
    for type in arrays:
        msg += f"<obj t='a' o='{type}'>"
        for idx, item in enumerate(arrays[type]):
            msg += f"<var n='{idx}' t='s'>{item}</var>"
        msg += "</obj>"
    msg += "</obj></dataObj>]]></dataObj></body></msg>"
    # TODO Need logic for player checks
    for usr in rms[int(rm_vars['rm_id'])].users:
        await rms[int(rm_vars['rm_id'])].users[usr].send(msg)


async def xtReq_(self, rms, xml, user, counter):
    room_id = xml.body.attrib['r']
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars['rm_id'] = room_id

    if "cmd" in rm_vars:
        data_to_send = {}
        da = [5, 0, 0, 0, 0, 0, 0, 0]

        if rm_vars['cmd'] == 's':
            async with self.lock:
                # Set user ids and position.
                arrays = get_array_objects(dict_format_obj, xml.body.text)
                rms[int(rm_vars['rm_id'])].user_pos_id = arrays['setArray']
        if rm_vars['cmd'] == 'm':
            for var in dict_format_obj.obj.var:
                data_to_send[var.attrib['n']] = var.text

            da[1] = room_id
            da[2] = data_to_send['option']  # TODO Implement Cancel Function
            da[3] = data_to_send['pos']
            da[4] = data_to_send['cmd']

            # Used by Buildings
            if data_to_send['cmd'] == "0":
                building_vars = {}
                for var in dict_format_obj.obj.obj.var:
                    building_vars[var.attrib['n']] = var.text
                da[5] = building_vars['building']
                da[6] = int(building_vars['cancelOrder'])
                da[7] = int(building_vars['auto'])

            # Used by Units
            elif data_to_send['cmd'] == "1":
                unit_vars = {'random': []}
                for var in dict_format_obj.obj.obj.var:
                    unit_vars[var.attrib['n']] = var.text
                for var in dict_format_obj.obj.obj.obj.var:
                    unit_vars['random'].append(var.text)

                da[5] = unit_vars['setId']
                for idx, item in enumerate(unit_vars['random']):
                    idx = idx + 6
                    da[idx] = item

            # Used by Missiles
            elif data_to_send['cmd'] == "2":
                missile_vars = {}
                for var in dict_format_obj.obj.obj.var:
                    missile_vars[var.attrib['n']] = var.text
                da[5] = missile_vars['tar']
                da[6] = missile_vars['px']
                da[7] = missile_vars['py']

            msg = '%xt%'
            for item in da:
                msg += f"{item}%"
            users = rms[int(rm_vars['rm_id'])].users
            for usr in users:
                await  users[usr].send(msg)


def get_array_objects(dict_obj, xml_text):
    arrays = {}
    # dict_obj.obj.obj.attrib['o']: # xml_text.body.text:
    if 'array' in xml_text.lower():
        for obj in dict_obj.obj.obj:
            arrays[obj.attrib['o']] = []
            for var in obj.var:
                arrays[obj.attrib['o']].append(var.text)
    return arrays


def get_room_vars(obj):
    vars = {}
    for var in obj.var:
        vars[var.attrib['n']] = var.text
    return vars


# <msg t='sys'><body action='roomDel'><rm id='9'/></body></msg

eventHandlers = {
    'verChk': version_check,
    'login': login,
    'loadB': loadBuddyList,
    'getRmList': getRoomList,
    'joinRoom': join_room,
    'setUvars': set_usr_variables,
    'pubMsg': publish_message,
    'createRoom': create_room,
    'setRvars': set_room_variables,
    'asObj': asObj_,
    'asObjG': asObjG_,
    'xtReq': xtReq_
}