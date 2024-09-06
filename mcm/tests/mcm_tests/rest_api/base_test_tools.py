"""
This module has some pre-configured base modules
to build the required test cases and provide
its configuration.
"""

from __future__ import annotations

import abc
import json
from pathlib import Path

from requests import Response

from mcm_tests.rest_api.api_tools import Environment, McMTesting

# Default configuration for the test environment
config = Environment(
    mcm_couchdb_url="http://localhost:5984/",
    mcm_couchdb_credential="Basic dGVzdDp0ZXN0",
    mcm_couchdb_lucene_url="http://localhost:5985/",
    mcm_application_url="http://localhost:8000/",
)


class Entity(abc.ABC):
    """
    Minimum common operations to test the API related to
    one McM entity/concept, e.g: campaigns, requests,
    chain_requests, etc.
    """

    def __init__(self, mockup_path: Path, mcm: McMTesting) -> None:
        self._mockup_path = mockup_path
        self._original_mockup: dict = self.__load_mockup()
        self.mcm: McMTesting = mcm

    def __load_mockup(self) -> dict:
        """
        Loads the provided mockup object for creating
        new records for the entity.
        """
        with open(self._mockup_path, encoding="utf-8") as f:
            return json.load(f)

    @abc.abstractmethod
    def mockup(self) -> dict:
        """
        Create a valid mockup object for the entity
        so that it is unique and new for the McM application.
        """
        pass

    @abc.abstractmethod
    def create(self, mockup: dict) -> tuple[dict, Response]:
        """
        Create valid entity record in the McM application.
        """
        pass

    @abc.abstractmethod
    def retrieve(self, mockup: dict) -> dict | list[dict]:
        """
        Retrieve valid entity record in the McM application.
        """
        pass

    @abc.abstractmethod
    def update(self, mockup: dict) -> tuple[dict, Response]:
        """
        Update one entity record in the McM application.
        """
        pass

    @abc.abstractmethod
    def delete(self, mockup: dict) -> tuple[dict, Response]:
        """
        Delete one entity record in the McM application.
        """
        pass

    @abc.abstractmethod
    def example(self) -> dict:
        """
        Automatically creates an example record
        for the entity without requiring any external
        input then retrieves it from McM application.
        """
        pass


class EntityTest(abc.ABC):
    """
    Minimum test cases to implement per each
    McM entity/concept, e.g: campaigns, requests,
    chain_requests, etc.'
    """

    @property
    @abc.abstractmethod
    def entity_api(self) -> Entity:
        """
        API client for the entity to test.
        """
        pass

    @abc.abstractmethod
    def test_create(self):
        """
        Test the creation of the entity
        also provides test cases to check
        the proper functionality for the schema validation.
        """
        pass

    @abc.abstractmethod
    def test_retrieve(self):
        """
        Test the retrieval of records related to the entity
        also provides test cases to check the behavior
        when it is attempted to retrieve a
        record that doesn't exists.
        """
        pass

    @abc.abstractmethod
    def test_update(self):
        """
        Test the update of records related to the entity
        also provides test cases to check the behavior
        when it is attempted to update the record
        to an invalid status or attempted to update a
        record that doesn't exists.
        """
        pass

    @abc.abstractmethod
    def test_delete(self):
        """
        Test the deletion of records related to the entity
        also provides test cases to check the behavior
        when it is attempted to delete a record that doesn't exists.
        """
        pass
