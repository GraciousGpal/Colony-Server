from lxml import objectify


def get_array_objects(dict_obj):
    arrays = {}
    if "array" in dict_obj.obj.obj.attrib["o"].lower():
        for obj in dict_obj.obj.obj:
            arrays[obj.attrib["o"]] = []
            for var in obj.var:
                arrays[obj.attrib["o"]].append(var.text)
    return arrays


def get_room_vars(obj):
    vars = {}
    for var in obj.var:
        vars[var.attrib["n"]] = var.text
    return vars

# Insert Sample Packet here
# msg1 = "<msg t='sys'><body action='asObjG' r='6'><![CDATA[<dataObj><var n='_$$_' t='s'>5</var><var n='id' t='s'>killUnit</var><obj t='o' o='sub'><var n='p' t='n'>0</var><var n='ran' t='n'>0</var><var n='id' t='s'>p1_154</var></obj></dataObj>]]></body></msg>"
# ms1 = "<msg t='sys'><body action='bList' r='-1'><bList><b s='0' i='-1'><n><![CDATA[uddy Lightblitz]]></n></b><b s='0' i='-1'><n><![CDATA[Lightblitz ]]></n></b></bList></body></msg>"
# ms1 = "<msg t='sys'><body action='addB' r='-1'><n>Lightblitz</n></body></msg>"
ms1 = "<msg t='sys'><body action='userGone' r='1'><user id='6' /></body></msg>"
ms2 = "<msg t='sys'><body action='joinRoom' r='1'><room id='8' pwd='' spec='0' leave='1' old='1' /></body></msg>"
tests = [ms2, ms2]
for msg in tests:
    xml = objectify.fromstring(msg)
    room_details = xml.body.room.attrib
    print(xml)
