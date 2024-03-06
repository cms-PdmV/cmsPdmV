"""
This module provides pre-configured HTTP requests
to consume a desired endpoint.
"""

from __future__ import annotations
import sys
import os
import logging
from copy import deepcopy
from enum import Enum
from requests import Request, Response, Session


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
                CouchDB. If it is not provided, it will be tried to retrieve it from
                `COUCH_CRED`
            mcm_couchdb_lucene_url (str): McM search engine URL.
                If it is not provided, it will be tried to retrieve it from
                `MCM_LUCENE_URL`.
            mcm_application_url (str): McM web application URL.
                If it is not provided, it will be tried to retrieve it from
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
                "Please set the CouchDB basic credentials via constructor args or `COUCH_CRED` variable"
            ]
        if not self.mcm_couchdb_lucene_url:
            error_msg += [
                "Please set the CouchDB Lucene connection url via constructor args or `MCM_LUCENE_URL` variable"
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
                        "Please set the McM application url via constructor args "
                        "or set the enviroment variables `MCM_HOST` and `MCM_PORT`"
                    )
                ]

        # Check and raise
        if error_msg:
            compress_msg = "\n".join(error_msg)
            raise ValueError(compress_msg)


class McM:
    """
    A simple version for McM REST client adapted to
    be used for building the test cases.

    Arguments:
        config (Environment): Test environment configuration.
        role (Roles): User role to impersonate when performing the
            requests.
    """

    def __init__(self, config: Environment, role: Roles):
        self.config = config
        self.role: Roles = role
        self.logger = self.__logger()
        self.mcm_requests = self.__session({"Adfs-Login": role.value})
        self.lucene_requests = self.__session()
        self.couchdb_requests = self.__session(
            {"Authorization": self.config.mcm_couchdb_credential}
        )
        if not self.check_test_users():
            self.__include_test_users()

    def __logger(self) -> logging.Logger:
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

    def __session(self, headers: dict = {}) -> Session:
        """
        Create a pre-configured `request.Session` object.

        Args:
            headers (dict): Headers to include in the pre-configured session.
        """
        s = Session()
        s.headers.update(headers)
        return s

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
        response = self.couchdb_requests.post(url=full_url, json=query)
        content = response.json()
        docs = content.get("docs", [])
        return len(docs) == len(all_roles)

    def __include_test_users(self):
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
            new_user["fullname"] = f"Test user for role: {role}"
            new_users.append(new_user)

        # Send the request.
        full_url: str = self.config.mcm_couchdb_url + "users/_bulk_docs"
        self.couchdb_requests.post(url=full_url, json={"docs": new_users})

    def _get(self, url) -> tuple[dict, Response]:
        full_url: str = self.config.mcm_application_url + url
        response = self.mcm_requests.get(url=full_url)
        return response.json(), response

    def _put(self, url, data) -> tuple[dict, Response]:
        full_url: str = self.config.mcm_application_url + url
        response = self.mcm_requests.put(url=full_url, json=data)
        return response.json(), response

    def _delete(self, url) -> tuple[dict, Response]:
        full_url: str = self.config.mcm_application_url + url
        response = self.mcm_requests.delete(full_url)
        return response.json(), response

    # McM methods
    def get(
        self, object_type, object_id=None, query="", method="get", page=-1
    ) -> dict | None:
        """
        Get data from McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_id - usually prep id of desired object
        query - query to be run in order to receive an object, e.g. tags=M17p1A, multiple parameters can be used with & tags=M17p1A&pwg=HIG
        method - action to be performed, such as get, migrate or inspect
        page - which page to be fetched. -1 means no paginantion, return all results
        """
        object_type = object_type.strip()
        if object_id:
            object_id = object_id.strip()
            self.logger.debug(
                "Object ID %s provided, method is %s, database %s",
                object_id,
                method,
                object_type,
            )
            url = "restapi/%s/%s/%s" % (object_type, method, object_id)
            res, _ = self._get(url)
            return res.get("results") or None
        elif query:
            if page != -1:
                self.logger.debug(
                    "Fetching page %s of %s for query %s", page, object_type, query
                )
                url = "search/?db_name=%s&limit=50&page=%d&%s" % (
                    object_type,
                    page,
                    query,
                )
                res, _ = self._get(url)
                results = res.get("results", [])
                self.logger.debug(
                    "Found %s %s in page %s for query %s",
                    len(results),
                    object_type,
                    page,
                    query,
                )
                return results
            else:
                self.logger.debug(
                    "Page not given, will use pagination to build response"
                )
                page_results = [{}]
                results = []
                page = 0
                while page_results:
                    page_results, _ = self.get(
                        object_type=object_type, query=query, method=method, page=page
                    )
                    results += page_results
                    page += 1

                return results
        else:
            self.logger.error("Neither object ID, nor query is given, doing nothing...")

    def update(self, object_type, object_data) -> tuple[dict, Response]:
        """
        Update data in McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_data - new JSON of an object to be updated
        """
        return self.put(object_type, object_data, method="update")

    def put(self, object_type, object_data, method="save") -> tuple[dict, Response]:
        """
        Put data into McM
        object_type - [chained_campaigns, chained_requests, campaigns, requests, flows, etc.]
        object_data - new JSON of an object to be updated
        method - action to be performed, default is 'save'
        """
        url = f"restapi/{object_type}/{method}"
        res = self._put(url, object_data)
        return res

    def delete(self, object_type, object_id):
        url = "restapi/%s/delete/%s" % (object_type, object_id)
        return self._delete(url)
