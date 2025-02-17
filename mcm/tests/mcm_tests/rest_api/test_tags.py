"""
This module tests the API operations related with
the tags entity.
"""

import time

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles


class TestTags:
    """
    Test the tags entity.
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

    def test_tags(self):
        """
        Create, retrieve and delete tags use to label requests on
        the application.
        """
        get_tags = lambda: self.mcm._get("restapi/tags/get_all").get("tags")
        assert get_tags() == []

        new_tag = f"Testing#{int(time.time())}"
        include_tag = self.mcm._put("restapi/tags/add", data={"tag": new_tag})
        assert include_tag["results"] == True
        assert new_tag in get_tags()

        remove_tag = self.mcm._put("restapi/tags/remove", data={"tag": new_tag})
        assert remove_tag["results"] == True
        assert get_tags() == []


class TestTagsAsProdMgr(TestTags):
    """
    Test the API for the tags entity impersonating
    a production manager.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)


class TestTagsAsUser(TestTags):
    """
    Test the API for the tags entity impersonating
    a user.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.USER, create=True)

    def test_tags(self):
        """
        Create, retrieve and delete tags use to label requests on
        the application.
        """
        get_tags = self.mcm._get("restapi/tags/get_all")
        assert "You don't have the permission to access the requested resource" in get_tags["message"]

        include_tag = self.mcm._put("restapi/tags/add", data={"tag": "Testing"})
        assert "You don't have the permission to access the requested resource" in include_tag["message"]

        remove_tag = self.mcm._put("restapi/tags/remove", data={"tag": "Testing"})
        assert "You don't have the permission to access the requested resource" in remove_tag["message"]
