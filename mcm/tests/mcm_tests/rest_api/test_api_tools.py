"""
Test the functionality provided via `api.py` module.
"""

import pytest

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.rest_api.base_test_tools import config


class TestEnvironment:
    """
    Test the different ways to instantiate
    the `Environment` class.
    """

    @property
    def mcm(self) -> McMTesting:
        if hasattr(self, "_mcm"):
            return self._mcm
        else:
            self._mcm = McMTesting(config=config, role=Roles.USER)
            return self._mcm

    def test_full_args(self):
        """
        Initialize the class only via constructor args.
        """
        config = Environment(
            mcm_couchdb_url="http://localhost:5984/",
            mcm_couchdb_credential="Basic dGVzdDp0ZXN0",
            mcm_couchdb_lucene_url="http://localhost:5985/",
            mcm_application_url="http://localhost:8000/",
        )
        assert config.mcm_couchdb_credential == "Basic dGVzdDp0ZXN0"

    def test_couchdb(self):
        """
        Check it is possible to contact with the CouchDB
        service.
        """
        response = self.mcm.session.get(url=config.mcm_couchdb_url)
        content = response.json()
        assert response.status_code == 200
        assert (
            content.get("vendor", {}).get("name", "")
            == "The Apache Software Foundation"
        )

    def test_lucene(self):
        """
        Check it is possible to contact with the
        CouchDB Lucene service
        """
        response = self.mcm.session.get(url=config.mcm_couchdb_lucene_url)
        content = response.json()
        assert response.status_code == 200
        assert "couchdb-lucene" in content

    def test_check_users(self):
        """
        Check the method that verifies the required
        mock users are already set.
        """
        assert self.mcm.check_test_users() == True
