"""
This module tests the API operations related with
the settings entity.
"""

import time
from mcm_tests.rest_api.api_tools import McMTesting, Roles, Environment


class TestSettings:
    """
    Test the settings entity.
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
        Check it is possible to retrieve a configuration value.
        """
        not_exists = self.mcm.get(object_type="settings", object_id="NotExists")
        assert not_exists == None

        # The following parameter exists in the default configuration.
        max_validations = self.mcm.get(object_type="settings", object_id="max_validations").get("value")
        assert isinstance(max_validations, int)
        assert max_validations > 0

    def test_create(self):
        """
        Check it is possible to create a configuration
        setting in the application.
        """
        setting_id = f"test_setting_{int(time.time())}"
        new_setting = {"_id": setting_id, "prepid": setting_id, "value": "Hello", "notes": "Testing setting"}
        result = self.mcm.put(object_type="settings", object_data=new_setting)
        assert result["results"] == True

        created = self.mcm.get(object_type="settings", object_id=setting_id)
        assert new_setting == created

    def update_test_not_working(self):
        # FIXME: There is an error in the server.
        # When a new setting is created using the `save` method, the request
        # data is set in the cache. It misses the `_rev` attribute CouchDB gives.
        # Without it, it is not possible to update the created document.
        # Details: https://github.com/cms-PdmV/cmsPdmV/blob/9d10daa2dc3d2801d7a6041147e24bc3b3fbc104/mcm/tools/settings.py#L30-L32
        pass


class TestSettingsAsProdMgr(TestSettings):
    """
    Test the API for the settings entity impersonating
    a production manager.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)

    def test_create(self):
        # Not enought permissions
        setting_id = f"test_setting_{int(time.time())}"
        new_setting = {"_id": setting_id, "prepid": setting_id, "value": "Hello", "notes": "Testing setting"}
        result = self.mcm.put(object_type="settings", object_data=new_setting)
        assert "You don't have the permission to access the requested resource." in result["message"]


class TestSettingsAsUser(TestSettingsAsProdMgr):
    """
    Test the API for the settings entity impersonating
    a user.
    """
    def setup_method(self, method):
        self._configure_as_role(role=Roles.USER, create=True)

    def test_retrieve(self):
        """
        Check it is possible to retrieve a configuration value.
        """
        # Not enought permissions
        not_exists = self.mcm._get("restapi/settings/get/NotExists")
        assert "You don't have the permission to access the requested resource." in not_exists["message"]
