"""
This module provides pre-configured HTTP requests
to consume a desired endpoint.
"""

from __future__ import annotations

import logging
import os
import sys
from copy import deepcopy
from enum import Enum

from requests import Response
from rest import McM as McMClient


class Roles(Enum):
    """
    User roles available in McM
    """

    USER = "user"
    GENERATOR_CONTACT = "generator_contact"
    GENERATOR_CONVENER = "generator_convener"
    PRODUCTION_MANAGER = "production_manager"
    ADMINISTRATOR = "administrator"


class Environment:
    """
    Wraps some configuration variables about the test environment.
    """

    def __init__(
        self,
        mcm_couchdb_url: str = "",
        mcm_couchdb_credential: str = "",
        mcm_couchdb_lucene_url: str = "",
        mcm_application_url: str = "",
    ) -> None:
        """
        Instantiate the API request client.

        Attributes:
            mcm_couchdb_url (str): McM database URL.
                Retrieved from the environment variable `MCM_COUCHDB_URL` by default.
            mcm_couchdb_credential (str): Credentials to write data in
                CouchDB. If it is not provided, it will be retrieved it from
                `COUCH_CRED`
            mcm_couchdb_lucene_url (str): McM search engine URL.
                If it is not provided, it will be retrieved it from
                `MCM_LUCENE_URL`.
            mcm_application_url (str): McM web application URL.
                If it is not provided, it will be retrieved it from
                - Host: MCM_HOST
                - Port: MCM_PORT
        Raises:
            ValueError: In case some of the required attributes finish to be empty.
        """
        self.mcm_couchdb_url = mcm_couchdb_url or os.getenv("MCM_COUCHDB_URL", "")
        self.mcm_couchdb_credential = mcm_couchdb_credential or os.getenv(
            "COUCH_CRED", ""
        )
        self.mcm_couchdb_lucene_url = mcm_couchdb_lucene_url or os.getenv(
            "MCM_LUCENE_URL", ""
        )
        self.mcm_application_url = mcm_application_url

        # Check the attributes are properly set
        error_msg: list[str] = []

        if not self.mcm_couchdb_url:
            error_msg += [
                "Set the CouchDB connection url via constructor args or the `MCM_COUCHDB_URL` variable"
            ]
        if not self.mcm_couchdb_credential:
            error_msg += [
                "Set the CouchDB basic credentials via constructor args or `COUCH_CRED` variable"
            ]
        if not self.mcm_couchdb_lucene_url:
            error_msg += [
                "Set the CouchDB Lucene connection url via constructor args or `MCM_LUCENE_URL` variable"
            ]
        if not self.mcm_application_url:
            # Check if it is possible to form it from environment
            # variables.
            host_from_env: str = os.getenv("MCM_HOST", "")
            port_from_env: str = os.getenv("MCM_PORT", "")
            if host_from_env and port_from_env:
                self.mcm_application_url = f"http://{host_from_env}:{port_from_env}/"
            else:
                error_msg += [
                    (
                        "Set the McM application url via constructor args "
                        "or set the enviroment variables `MCM_HOST` and `MCM_PORT`"
                    )
                ]

        # Check and raise
        if error_msg:
            compress_msg = "\n".join(error_msg)
            raise ValueError(compress_msg)


class McMTesting(McMClient):
    """
    A simple version for McM REST client adapted to
    be used for building the test cases.

    Arguments:
        config (Environment): Test environment configuration.
        role (Roles): User role to impersonate when performing the
            requests.
    """

    def __init__(self, config: Environment, role: Roles):
        super().__init__(id=None)
        self.config = config
        self.role: Roles = role
        self.logger = self._logger()

        # Configure the right target server
        self.server = self.config.mcm_application_url
        credential_headers = {
            # McM
            # INFO: Include also the email, firstname and lastname
            # otherwise, the web server will fail to properly assign
            # permissions.
            "Adfs-Login": role.value,
            "Adfs-Email": "example@example.com",
            "Adfs-Firstname": role.value,
            "Adfs-Lastname": role.value,
            # CouchDB
            "Authorization": self.config.mcm_couchdb_credential
        }
        self.session.headers.update(credential_headers)
        if not self.check_test_users():
            self._include_test_users()

    def _logger(self) -> logging.Logger:
        """
        Returns a logger for the class
        """
        logger = logging.getLogger("mcm-rest-client")
        formatter = logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s")
        handler = logging.StreamHandler(sys.stdout)

        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        logger.addHandler(handler)
        return logger

    def check_test_users(self) -> bool:
        """
        Checks that there is one user per role
        available in the database.

        Returns:
            True if there is one user per role,
                False otherwise.
        """
        full_url: str = self.config.mcm_couchdb_url + "users/_find"
        all_roles = [r.value for r in Roles]
        query = {"selector": {"_id": {"$in": all_roles}}}
        response = self.session.post(url=full_url, json=query)
        content = response.json()
        docs = content.get("docs", [])
        return len(docs) == len(all_roles)

    def _include_test_users(self):
        """
        Includes one test user per available role.
        """
        new_user_mock = {
            "notes": "I am test user :)",
            "seen_notifications": [],
            "pwg": [],
            "email": "example@example.com",
            "history": [],
        }
        new_users: list[dict] = []
        all_roles = [r.value for r in Roles]

        for role in all_roles:
            new_user = deepcopy(new_user_mock)
            new_user["_id"] = role
            new_user["username"] = role
            new_user["role"] = role
            new_user["fullname"] = role
            new_users.append(new_user)

        # Send the request.
        full_url: str = self.config.mcm_couchdb_url + "users/_bulk_docs"
        self.session.post(url=full_url, json={"docs": new_users})
