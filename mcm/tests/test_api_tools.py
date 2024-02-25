"""
Test the functionality provided via `api.py` module.
"""

import pytest
from tests.base_test_tools import api
from tests.api_tools import APIRequest, Roles


class TestAPIRequestInit:
    """
    Test the different ways to instantiate
    the `APIRequest` class.
    """

    def test_init_empty(self):
        """
        Initialize the class with no attributes.
        """
        with pytest.raises(RuntimeError):
            APIRequest()

    def test_some_provided_args(self):
        """
        Initialize the class with some attributes
        provided via the constructor but not all.
        """
        with pytest.raises(RuntimeError):
            APIRequest(mcm_application_url="http://localhost:5984/")

    def test_full_args(self):
        """
        Initialize the class only via constructor args.
        """
        api = APIRequest(
            mcm_couchdb_url="http://localhost:5984/",
            mcm_couchdb_credential="Basic dGVzdDp0ZXN0",
            mcm_couchdb_lucene_url="http://localhost:5985/",
            mcm_application_url="http://localhost:8000/",
            mockup=True,
        )
        assert api.mcm_couchdb_credential == "Basic dGVzdDp0ZXN0"


class TestAPIRequestHTTP:
    """
    Test the functionality to perform HTTP request
    to the McM underlying components.
    """

    def test_couchdb(self):
        """
        Check it is possible to contact with the CouchDB
        service.
        """
        response = api.couchdb_request(endpoint="", method="GET")
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
        response = api.lucene_request(endpoint="", method="GET")
        content = response.json()
        assert response.status_code == 200
        assert "couchdb-lucene" in content

    def test_check_users(self):
        """
        Check the method that verifies the required
        mock users are already set.
        """
        assert api.check_test_users() == True

    def test_mcm_user_request(self):
        """
        Check that the user is properly interpreted by McM.
        """
        user_endpoint = "restapi/users/get_role"
        for role in Roles:
            response = api.mcm_request(
                endpoint=user_endpoint, method="GET", as_role=role
            )
            content = response.json()
            assert content.get("role", "") == role.value

    def test_mcm_client(self):
        user_endpoint = "restapi/users/get_role"
        for role in Roles:
            mcm_client = api.mcm_client(role)
            content, response = mcm_client._get(url=user_endpoint)
            assert content.get("role", "") == role.value
            assert response.status_code == 200
