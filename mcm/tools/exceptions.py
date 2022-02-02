"""
Module for McM exceptions
"""

class McMException(Exception):
    """
    Base class for all McM exceptions
    """
    pass


class NotFoundException(McMException):
    """
    Exception when an object could not be found in the database
    """
    def __init__(self, object_id):
        self.message = f'Object "{object_id}" could not be found in the database'

    def __str__(self) -> str:
        return self.message


class CouldNotSaveException(McMException):
    """
    Exception when an object could not be saved to the databse
    """
    def __init__(self, object_id):
        self.message = f'Object "{object_id}" could not be saved to the database'

    def __str__(self) -> str:
        return self.message


class BadAttributeException(McMException):
    """
    Exception when an invalid attribute is found
    """
    def __init__(self, message):
        self.message = message

    def __str__(self) -> str:
        return self.message


class InvalidActionException(McMException):
    """
    Exception when an invalid action is being performed
    """
    def __init__(self, message):
        self.message = message

    def __str__(self) -> str:
        return self.message
