from lxml import objectify


def get_array_objects(dict_obj):
    arrays = {}
    if 'array' in dict_obj.obj.obj.attrib['o'].lower():
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

def asObj_(self, rms, xml, user, _):
    dict_format_obj = objectify.fromstring(xml.body.text)
    rm_vars = get_room_vars(dict_format_obj)
    rm_vars['rm_id'] = xml.body.attrib['r']
    # Insert Logic


# Insert Sample Packet here
msg1 = "<msg t='sys'><body action='asObjG' r='6'><![CDATA[<dataObj><var n='_$$_' t='s'>5</var><var n='id' t='s'>killUnit</var><obj t='o' o='sub'><var n='p' t='n'>0</var><var n='ran' t='n'>0</var><var n='id' t='s'>p1_154</var></obj></dataObj>]]></body></msg>"
tests = [msg1]
for msg in tests:
    xml = objectify.fromstring(msg)
    asObj_(None, None, xml, None, None)
