"""
Module that contains global config singleton
"""
from configparser import ConfigParser, DEFAULTSECT


class Config():
    """
    Global config holder
    """

    __config = None
    __section = DEFAULTSECT

    @classmethod
    def load(cls, filename, section):
        """
        Get config as a dictionary
        Load only one section
        """
        Config.__config = ConfigParser()
        Config.__config.read(filename)
        Config.__section = section

    @classmethod
    def get(cls, key):
        """
        Get a string from config
        """
        return cls.__config.get(Config.__section, key)

    @classmethod
    def getint(cls, key):
        """
        Get an int from config
        """
        return cls.__config.getint(Config.__section, key)
        
    @classmethod
    def getfloat(cls, key):
        """
        Get a float from config
        """
        return cls.__config.getfloat(Config.__section, key)
        
    @classmethod
    def getbool(cls, key):
        """
        Get a boolean from config
        """
        return cls.__config.getboolean(Config.__section, key)
