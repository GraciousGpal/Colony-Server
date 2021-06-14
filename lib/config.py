from configparser import ConfigParser

config = ConfigParser()
config.read('config.ini')


def get_config():
    sections = config.sections()
    config_dict = {}
    for key in sections:
        config_dict[key] = dict(config[key])
    return config_dict
