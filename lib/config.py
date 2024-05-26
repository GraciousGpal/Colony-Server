from configparser import ConfigParser

config = ConfigParser()
config.read("config.ini")


def get_config() -> dict:
    """
    Loads the configuration file config.ini and returns a dictionary with keys and its values.
    :return:
    """
    sections = config.sections()
    config_dict = {}
    for key in sections:
        config_dict[key] = dict(config[key])
    return config_dict
