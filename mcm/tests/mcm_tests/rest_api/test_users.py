"""
This module tests the API operations related with
the users entity.
"""

import time

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles


class TestUsers:
    """
    Test the users entity.
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

    def test_get_role(self):
        """
        Check the current role of the user is the expected
        """
        retrieved_role = self.mcm._get("restapi/users/get_role")
        assert retrieved_role.get("role") == self.mcm.role.value

    def test_get_pwg(self):
        """
        Check the user's physics working group (pwg)
        """
        current_pwg = self.mcm._get("restapi/users/get_pwg").get("results")
        assert len(current_pwg) >= 32 
        assert "PPD" in current_pwg

        only_pwd = self.mcm._get(f"restapi/users/get_pwg/{self.mcm.role.value}").get("results")
        assert only_pwd == current_pwg

    def test_update(self):
        """
        Update the user's information
        """
        user_info = self.mcm.get(object_type="users", object_id=self.mcm.role.value)
        current_time = str(int(time.time()))
        user_info["notes"] = current_time
        result = self.mcm.put(object_type="users", object_data=user_info)
        assert result["results"] == True
        
        user_info = self.mcm.get(object_type="users", object_id=self.mcm.role.value)
        assert user_info["notes"] == current_time

    def test_new_user(self):
        """
        Creates a new user and set its permissions.
        This checks the following operations: save, change_role, get
        """
        user_id = str(time.time())
        new_user_mock = {
            "notes": "I am test user :)",
            "seen_notifications": [],
            "pwg": [],
            "email": "cms-mcm-testing-noreply@cern.ch",
            "history": [],
            "_id": user_id,
            "username": user_id,
            "role": Roles.USER.value,
            "fullname": user_id
        }
        create_result = self.mcm.put(object_type="users", object_data=new_user_mock)
        print(create_result)
        assert create_result["results"] == True

        # Increase the role by one
        increase_role = self.mcm._get(f"restapi/users/change_role/{user_id}/1")
        assert increase_role["results"] == True

        # Get the user's data
        test_user = self.mcm.get(object_type="users", object_id=user_id)
        assert test_user["role"] == Roles.GENERATOR_CONTACT.value


class TestUsersAsProdMgr(TestUsers):
    def setup_method(self, method):
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)


class TestUsersAsUser(TestUsersAsProdMgr):
    def setup_method(self, method):
        self._configure_as_role(role=Roles.USER, create=True)

    def test_get_pwg(self):
        """
        Check the user's physics working group (pwg)
        """
        current_pwg = self.mcm._get(f"restapi/users/get_pwg/{self.mcm.role.value}").get("results")
        assert current_pwg == []

    def test_update(self):
        """
        Update the user's information
        """
        user_info = self.mcm.get(object_type="users", object_id=self.mcm.role.value)
        current_time = str(int(time.time()))
        user_info["notes"] = current_time
        result = self.mcm.put(object_type="users", object_data=user_info)
        assert "You don't have the permission to access the requested resource" in result["message"]

    def test_new_user(self):
        """
        Creates a new user and set its permissions.
        This checks the following operations: save, change_role, get
        """
        user_id = str(time.time())
        new_user_mock = {
            "notes": "I am test user :)",
            "seen_notifications": [],
            "pwg": [],
            "email": "cms-mcm-testing-noreply@cern.ch",
            "history": [],
            "_id": user_id,
            "username": user_id,
            "role": Roles.USER.value,
            "fullname": user_id
        }
        create_result = self.mcm.put(object_type="users", object_data=new_user_mock)
        assert "You don't have the permission to access the requested resource" in create_result["message"]
