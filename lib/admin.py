from logging import getLogger

from lib.config import get_config

# Load Configuration
config = get_config()

log = getLogger(__name__)


def is_mod(name):
    return name in config['admin']['moderators'].split(',')
