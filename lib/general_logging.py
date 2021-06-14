import logging
import sys

from lib.config import get_config

config = get_config()


def setup_logging():
    root = logging.getLogger()
    level = logging.INFO
    if config['logging']['level'] == "debug":
        level = logging.DEBUG
    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    return root
