"""
Module that contains global config singleton
"""
import logging
from configparser import ConfigParser


class Config():
    """
    Global config holder
    """

    __config = None
    __logger = logging.getLogger()

    @classmethod
    def load(cls, filename, section):
        """
        Get config as a dictionary
        Load only one section
        """
        parser = ConfigParser()
        parser.read(filename)
        config = dict(parser.items(section))
        for key, value in dict(config).items():
            if value.lower() in ('true', 'false'):
                config[key] = value.lower() == 'true'
            elif value.isdigit():
                config[key] = int(value)

        cls.__config = config
        import json
        cls.__logger.debug(json.dumps(config, indent=2, sort_keys=True))

    @classmethod
    def get(cls, key):
        """
        Get a string from config
        """
        if not cls.__config:
            cls.__logger.warning('Config is not loaded or empty!')
            return None

        return cls.__config[key]

    @classmethod
    def set(cls, key, value):
        """
        Set value in config
        """
        if not cls.__config:
            cls.__logger.warning('Config is not loaded or empty!')
            return

        cls.__config[key] = value
