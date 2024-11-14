"""
This module tests the API operations related with
the lists entity.
"""

import time

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles


class TestLists:
    """
    Test the lists entity.
    """

    def _configure_as_role(self, role: Roles, create: bool):
        """
        Configure a session to McM impersonating a role.
        """
        env = Environment()
        mcm = McMTesting(config=env, role=role)

        self.mcm = mcm
        self.env = env

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR, create=True)

    def test_retrieve(self):
        """
        Check it is possible to retrieve a special list of request.
        """
        list_of_force_complete = self.mcm.get(object_type="lists", object_id="list_of_forcecomplete")
        assert "list_of_forcecomplete" == list_of_force_complete.get("prepid")
        assert "list_of_forcecomplete" == list_of_force_complete.get("_id")

        value = list_of_force_complete.get("value")
        assert isinstance(value, list)
        assert value == [], "This list should be empty, are you sure the target enviroment is a testing one?"

    def test_update(self):
        """
        Creates or updates a list with new requests.
        """
        new_list_id = f'list_of_testing_requests_{int(time.time())}'
        new_list = {
            '_id': new_list_id,
            'prepid': new_list_id,
            'notes': 'New lists', 
            'value': []
        }
        result = self.mcm.update(object_type="lists", object_data=new_list)
        assert result["results"] == True

        created = self.mcm.get(object_type="lists", object_id=new_list_id)
        test = created.copy()
        del test["_rev"]
        assert test == new_list

        created["notes"] = "Another message"
        result = self.mcm.update(object_type="lists", object_data=created)
        assert result["results"] == True

        updated = self.mcm.get(object_type="lists", object_id=new_list_id)
        assert updated["notes"] == "Another message"


class TestListsAsProdMgr(TestLists):
    """
    Test the API for the lists entity impersonating
    a production manager.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)

    def test_update(self):
        """
        Creates or updates a list with new requests.
        """
        new_list_id = f'list_of_testing_requests_{int(time.time())}'
        new_list = {
            '_id': new_list_id,
            'prepid': new_list_id,
            'notes': 'New lists', 
            'value': []
        }
        result = self.mcm.update(object_type="lists", object_data=new_list)
        assert "You don't have the permission to access the requested resource." in result["message"]

class TestListsAsUser(TestListsAsProdMgr):
    """
    Test the API for the list entity impersonating
    a user.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.USER, create=True)