from os import listdir
from os.path import isfile, join
from colorama import Fore
from scapy.layers.inet import TCP
from scapy.packet import Raw
from scapy.utils import rdpcap


def print_http_payload(packet, filter_port=25565):
    """
    Print the HTTP payload of a packet if it has both TCP and Raw layers.

    Args:
        packet: The packet to analyze.
        filter_port: The port number to filter packets by (default is 25565).
    """
    if packet.haslayer(TCP) and packet.haslayer(Raw):
        if packet[TCP].dport == 25565 or packet[TCP].sport == 25565:
            src = packet[TCP].sport
            dst = packet[TCP].dport
            if int(src) == int(filter_port):
                print(f"{Fore.RED}{src} --> {dst}")
            else:
                print(f"{Fore.GREEN}{src} --> {dst}")
            ascii_string = str(packet[Raw].load)
            print(ascii_string)


def analyse_shark_dump(data):
    """
    Analyzes a Shark dump file.

    Args:
        data (str): The path to the Shark dump file.

    Returns:
        None
    """
    a = rdpcap(data)
    sessions = a.sessions()
    for session in sessions:
        for packet_ in sessions[session]:
            print_http_payload(packet_)


if __name__ == "__main__":
    dump_path = "snaps"

    dump_files = [f for f in listdir(dump_path) if "pcapng" in f and "buddy_leaves3.pcapng" in f]
    print(dump_files)
    for file in dump_files:
        print(f"------Analyzing: {file}------")
        analyse_shark_dump(f"{dump_path}/{file}")
        print("------End of analysis------\n")