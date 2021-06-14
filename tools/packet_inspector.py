import codecs
import logging

import pyshark
from colorama import init, Fore

init(convert=True)
logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.DEBUG)
log = logging.getLogger(__name__)

port = 25565
cap = pyshark.LiveCapture(interface='\\Device\\NPF_Loopback',  # WireShark should be installed for this to work.
                          display_filter=f'tcp.port == {port} || udp.port == {port}')

# Print packets with data in them and show receiver and sender.
for packets in cap.sniff_continuously():
    if packets['tcp'].Flags == '0x00000018':
        src = packets['tcp'].srcport
        dst = packets['tcp'].dstport
        if int(src) == int(port):
            print(f"{Fore.RED}{src} --> {dst}")
        else:
            print(f"{Fore.GREEN}{src} --> {dst}")
        ascii_string = codecs.decode(packets['Data'].data, "hex")
        print(ascii_string)

cap.close()
