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


class APIRequest:
    """
    Provides some utilities to perform HTTP request for consuming
    endpoints in the McM application impersonating a user or interacting
    with the database.
    """

    def __init__(
        self,
        mcm_couchdb_url: str = "",
        mcm_couchdb_credential: str = "",
        mcm_couchdb_lucene_url: str = "",
        mcm_application_url: str = "",
        mockup: bool = False,
    ) -> None:
        """
        Instantiate the API request client.

        Attributes:
            mcm_couchdb_url (str): McM database URL.
                If it is not provided, it will be tried to retrieve it from
                `MCM_COUCHDB_URL`.
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
            mockup (bool): If True, the creation/validation of mock users
                will not be perform
        Raises:
            RuntimeError: In case some of the required attributes finish to be empty.
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
                "Please the CouchDB connection url via constructor args or `MCM_COUCHDB_URL` variable"
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
            raise RuntimeError(compress_msg)

        # Check the required mock users are available
        # Otherwise, create them
        if not mockup:
            if not self.check_test_users():
                self.__include_test_users()

    def __http_request(
        self,
        base: str,
        endpoint: str,
        method: str,
        data: dict = {},
        headers: dict = {},
    ) -> Response:
        """
        Executes a HTTP request.

        Args:
            base (str): Base URL, e.g: http://localhost:5984/
            endpoint (str): Endpoint to consume, e.g: entity/document?p=1
            method (str): HTTP method, e.g: POST
            data (dict | None): Data to include in the request body.
            headers (dict): Request headers
        """
        session = Session()
        full_url: str = base + endpoint
        req = Request(method=method, url=full_url, headers=headers, json=data)
        prepared_req = session.prepare_request(req)
        return session.send(prepared_req)

    def couchdb_request(
        self, endpoint: str, method: str, data: dict = {}, headers: dict = {}
    ) -> Response:
        """
        Sends a HTTP request to CouchDB.

        Args:
            endpoint (str): Endpoint to consume, e.g: entity/document?p=1
            method (str): HTTP method, e.g: POST
            data (dict | None): Data to include in the request body.
            headers (dict): Request headers
        """
        couchdb_headers = {"Authorization": self.mcm_couchdb_credential}
        full_headers = {**headers, **couchdb_headers}
        return self.__http_request(
            base=self.mcm_couchdb_url,
            endpoint=endpoint,
            method=method,
            data=data,
            headers=full_headers,
        )

    def mcm_request(
        self,
        endpoint: str,
        method: str,
        as_role: Roles | None = None,
        data: dict = {},
        headers: dict = {},
    ) -> Response:
        """
        Sends a HTTP request to McM web application.

        Args:
            endpoint (str): Endpoint to consume, e.g: entity/document?p=1
            method (str): HTTP method, e.g: POST
            as_role (Roles | None): Role to impersonate for the request.
            data (dict | None): Data to include in the request body.
            headers (dict): Request headers
        """
        full_headers = {**headers}
        if as_role:
            user_headers = {"Adfs-Login": as_role.value}
            full_headers.update(user_headers)

        return self.__http_request(
            base=self.mcm_application_url,
            endpoint=endpoint,
            method=method,
            data=data,
            headers=full_headers,
        )

    def lucene_request(
        self, endpoint: str, method: str, data: dict = {}, headers: dict = {}
    ) -> Response:
        """
        Sends a HTTP request to CouchDB Lucene.

        Args:
            endpoint (str): Endpoint to consume, e.g: entity/document?p=1
            method (str): HTTP method, e.g: POST
            data (dict | None): Data to include in the request body.
            headers (dict): Request headers
        """
        return self.__http_request(
            base=self.mcm_couchdb_lucene_url,
            endpoint=endpoint,
            method=method,
            data=data,
            headers=headers,
        )

    def check_test_users(self) -> bool:
        """
        Checks that there is one user per role
        available in the database.

        Returns:
            True if there is one user per role,
                False otherwise.
        """
        all_roles = [r.value for r in Roles]
        query = {"selector": {"_id": {"$in": all_roles}}}
        response = self.couchdb_request(
            endpoint="users/_find", method="POST", data=query
        )
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
            new_users += [new_user]

        # Send the request.
        self.couchdb_request(
            endpoint="users/_bulk_docs", method="POST", data={"docs": new_users}
        )

    def mcm_client(self, role: Roles) -> McM:
        """
        Return an instance of the McM client to perform requests
        to the web application.

        Args:
            role (Roles): Role to impersonate in the requests.
        """
        return McM(api=self, role=role)


class McM:
    """
    A simple version for McM REST client adapted to
    be used for building the test cases.

    Arguments:
        api (APIRequest): Client to perform HTTP requests.
        role (Roles): User role to impersonate when performing the
            requests.
    """

    def __init__(self, api: APIRequest, role: Roles):
        self.api: APIRequest = api
        self.role: Roles = role
        self.logger = self.__logger()

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

    def _get(self, url) -> tuple[dict, Response]:
        response = self.api.mcm_request(endpoint=url, method="GET", as_role=self.role)
        return response.json(), response

    def _put(self, url, data) -> tuple[dict, Response]:
        response = self.api.mcm_request(
            endpoint=url, method="PUT", data=data, as_role=self.role
        )
        return response.json(), response

    def _delete(self, url) -> tuple[dict, Response]:
        response = self.api.mcm_request(
            endpoint=url, method="DELETE", as_role=self.role
        )
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
            result = res.get("results")
            if not result:
                return None

            return result
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
        url = "restapi/%s/%s" % (object_type, method)
        res = self._put(url, object_data)
        return res

    def approve(self, object_type, object_id, level=None):
        if level is None:
            url = "restapi/%s/approve/%s" % (object_type, object_id)
        else:
            url = "restapi/%s/approve/%s/%d" % (object_type, object_id, level)

        return self._get(url)

    def clone_request(self, object_data):
        return self.put("requests", object_data, method="clone")

    def get_range_of_requests(self, query) -> tuple[dict | None, Response]:
        res, response = self._put(
            "restapi/requests/listwithfile", data={"contents": query}
        )
        return res.get("results", None), response

    def delete(self, object_type, object_id):
        url = "restapi/%s/delete/%s" % (object_type, object_id)
        return self._delete(url)

    def forceflow(self, prepid) -> tuple[dict | None, Response]:
        """
        Forceflow a chained request with given prepid
        """
        res, response = self._get("restapi/chained_requests/flow/%s/force" % (prepid))
        return res.get("results", None), response

    def reset(self, prepid) -> tuple[dict | None, Response]:
        """
        Reset a request
        """
        res, response = self._get("restapi/requests/reset/%s" % (prepid))
        return res.get("results", None), response

    def soft_reset(self, prepid) -> tuple[dict | None, Response]:
        """
        Soft reset a request
        """
        res, response = self._get("restapi/requests/soft_reset/%s" % (prepid))
        return res.get("results", None), response

    def option_reset(self, prepid) -> tuple[dict | None, Response]:
        """
        Option reset a request
        """
        res, response = self._get("restapi/requests/option_reset/%s" % (prepid))
        return res.get("results", None), response

    def ticket_generate(self, ticket_prepid) -> tuple[dict | None, Response]:
        """
        Generate chains for a ticket
        """
        res, response = self._get("restapi/mccms/generate/%s" % (ticket_prepid))
        return res.get("results", None), response

    def ticket_generate_reserve(self, ticket_prepid) -> tuple[dict | None, Response]:
        """
        Generate and reserve chains for a ticket
        """
        res, response = self._get("restapi/mccms/generate/%s/reserve" % (ticket_prepid))
        return res.get("results", None), response

    def rewind(self, chained_request_prepid) -> tuple[dict | None, Response]:
        """
        Rewind a chained request
        """
        res, response = self._get(
            "restapi/chained_requests/rewind/%s" % (chained_request_prepid)
        )
        return res.get("results", None), response

    def flow(self, chained_request_prepid) -> tuple[dict | None, Response]:
        """
        Flow a chained request
        """
        res, response = self._get(
            "restapi/chained_requests/flow/%s" % (chained_request_prepid)
        )
        return res.get("results", None), response

    def root_requests_from_ticket(self, ticket_prepid) -> tuple[dict | None, Response]:
        """
        Return list of all root (first ones in the chain) requests of a ticket
        """
        mccm = self.get("mccms", ticket_prepid)
        query = ""
        for root_request in mccm.get("requests", []):
            if isinstance(root_request, str):
                query += "%s\n" % (root_request)
            elif isinstance(root_request, list):
                # List always contains two elements - start and end of a range
                query += "%s -> %s\n" % (root_request[0], root_request[1])
            else:
                self.logger.error(
                    "%s is of unsupported type %s", root_request, type(root_request)
                )

        requests = self.get_range_of_requests(query)
        return requests
