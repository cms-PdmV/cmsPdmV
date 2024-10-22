"""
This module tests the API operations related with
the request entity.
"""

import json
from mcm_tests.rest_api.api_tools import McMTesting, Roles, Environment
from mcm_tests.use_cases.full_injection.core import InjectRootRequest


class TestRequests:
    """
    Test the endpoints related to the request API.
    """

    def _configure_as_role(self, role: Roles):
        """
        Create or mock some objects in McM to use in the
        assertions using a specific group of permissions.
        """
        self.env = Environment()
        self.mcm = McMTesting(config=self.env, role=role)
        self.injector = InjectRootRequest(mcm=self.mcm, environment=self.env)
        self.invalidator = self.injector.resubmitter._invalidator
    
        # Create the requests. 
        self.entities = self.injector.create(mocks=self.injector.mock())

    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR)

    def test_get(self):
        # Retrieve the request.
        root_request = self.entities["root_request"]
        retrieved_root_request = self.mcm.get(object_type="requests", object_id=root_request.get("prepid", ""))
        assert root_request == retrieved_root_request

    def test_reset_delete(self):
        # If the request is injected, it is required to invalidate it first
        # And reset the request
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        self.injector.inject()
        
        delete_result = self.mcm._delete(f"restapi/requests/delete/{root_request_prepid}")
        assert delete_result.get("results") == False
        assert (
            "Not possible to delete a request" in delete_result.get("message") 
            and "in status submitted" in delete_result.get("message")
        )

        invalidator = self.injector.resubmitter._invalidator
        invalidator.invalidate_delete_cascade_requests(requests_prepid=[root_request_prepid], remove_chain=True)
        reset_result = self.mcm.reset(root_request_prepid)
        assert reset_result == True

        root_request_data = self.mcm.get(object_type="requests", object_id=root_request_prepid)
        assert root_request_data.get("approval") == "none" and root_request_data.get("status") == "new"

        # Then, delete it
        delete_result = self.mcm._delete(f"restapi/requests/delete/{root_request_prepid}")
        assert delete_result.get("results") == True
        root_request_data = self.mcm.get(object_type="requests", object_id=root_request_prepid)
        assert root_request_data == None

    def test_clone(self):
        # The request does not exists
        not_exists_result = self.mcm._get("restapi/requests/clone/NotExists")
        assert (
            not_exists_result.get("results") == False
            and "cannot clone an inexisting id" in not_exists_result.get("message")
        )

        # Clone the request without extra changes
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        clone_result = self.mcm._get(f"restapi/requests/clone/{root_request_prepid}")
        new_prepid = clone_result.get("prepid")
        new_request_data = self.mcm.get(object_type="requests", object_id=new_prepid)
        
        assert clone_result.get("results") == True
        assert root_request_prepid != new_prepid
        assert new_request_data != None and isinstance(new_request_data, dict)
        assert root_request["member_of_campaign"] == new_request_data["member_of_campaign"]

        # Clone the request setting some custom parameters
        custom_note = "Testing"
        clone_result = self.mcm.clone_request({"prepid": root_request_prepid, "notes": custom_note})
        new_prepid = clone_result.get("prepid")
        new_request_data = self.mcm.get(object_type="requests", object_id=new_prepid)

        assert clone_result.get("results") == True
        assert root_request_prepid != new_prepid
        assert new_request_data != None and isinstance(new_request_data, dict)
        assert new_request_data.get("notes") == custom_note

    def test_inspect(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        inspect_result = self.mcm._get(f"restapi/requests/inspect/{root_request_prepid}")
        assert inspect_result.get("results") == False
        assert "cannot inspect a request in new status" in inspect_result.get("message")

        # Inject it
        self.injector.inject()

        # The test request does not have a valid dataset
        # registered on the CMS services, so a failure should 
        # be shown. Also, no record has been taken from Stats2.
        inspect_result = self.mcm._get(f"restapi/requests/inspect/{root_request_prepid}")
        assert inspect_result.get("results") == False
        assert "is malformed" in inspect_result.get("message")

    def test_update(self):
        custom_note = "Testing for update"
        root_request = self.entities["root_request"]
        root_request["notes"] = custom_note

        update_result = self.mcm.update(object_type="requests", object_data=root_request)
        request_data = self.mcm.get(object_type="requests", object_id=root_request.get("prepid", ""))
        
        assert update_result.get("results") == True
        assert request_data != None and isinstance(request_data, dict)
        assert request_data.get("notes") == custom_note

    def test_approve(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        current_approval = root_request.get("approval")

        # Approve the request one step
        approve_result = self.mcm.approve(object_type="requests", object_id=root_request_prepid)
        request_data = self.mcm.get(object_type="requests", object_id=root_request.get("prepid", ""))
        assert approve_result.get("results") == True
        assert request_data.get("approval") != current_approval

    def test_get_cms_drivers(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        drivers_result = self.mcm._get(f"restapi/requests/get_cmsDrivers/{root_request_prepid}")
        command = drivers_result.get("results")[0]
        assert "cmsDriver.py" in command

    def test_get_test(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")

        # This endpoints returns the script as `text`
        # FIXME: This should be also available as a `private` endpoint!
        endpoint_url = self.mcm.server + f"public/restapi/requests/get_test/{root_request_prepid}"
        test_script = self.mcm.session.get(url=endpoint_url).text
        
        assert test_script != ""
        assert f"EVENTS={root_request.get('total_events', 0)}" in test_script
        assert "cmsDriver.py" in test_script and "cmsRun" in test_script

    def test_get_setup(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")

        # This endpoints returns the script as `text`
        # FIXME: This should be also available as a `private` endpoint!
        endpoint_url = self.mcm.server + f"public/restapi/requests/get_setup/{root_request_prepid}"
        setup_script = self.mcm.session.get(url=endpoint_url).text
        
        assert setup_script != ""
        assert f"EVENTS={root_request.get('total_events', 0)}" in setup_script
        assert "cmsDriver.py" in setup_script
        assert "This script is used by McM when it performs automatic" in setup_script

    def test_get_inject(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")

        # This endpoints returns the script as `text`
        endpoint_url = self.mcm.server + f"restapi/requests/get_inject/{root_request_prepid}"
        inject_script = self.mcm.session.get(url=endpoint_url).text
        
        assert inject_script != ""
        assert "wmcontrol.py" in inject_script

    def test_get_searchable(self):
        search_options = self.mcm._get("restapi/requests/searchable")
        fields = [
            "energy", "dataset_name", "status", "approval", 
            "extension", "generators", "member_of_chain", "pwg", "process_string",
            "mcdb_id", "prepid", "flown_with", "member_of_campaign", "tags"
        ]
        assert set(search_options.keys()) == set(fields)

    def test_list_with_file(self):
        # FIXME: This endpoint should have another name!
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        request_from_range = self.mcm.get_range_of_requests(query=root_request_prepid)
        
        assert request_from_range
        assert request_from_range[0] == root_request

    def test_force_complete(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        add_force_complete = self.mcm._put("restapi/requests/add_forcecomplete", {"prepid": root_request_prepid})
        assert add_force_complete.get("results") == False
        assert "Cannot add a request which is not submitted" in add_force_complete.get("message")

        # Submit and inject
        self.injector.inject()

        add_force_complete = self.mcm._put("restapi/requests/add_forcecomplete", {"prepid": root_request_prepid})
        force_complete_list = self.mcm._get("restapi/requests/forcecomplete")
        assert add_force_complete.get("results") == True
        assert root_request_prepid in force_complete_list


class TestRequestsAsProdMgr(TestRequests):
    """
    Test the endpoints related to the request API
    impersonating a production manager.
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.PRODUCTION_MANAGER)

    def test_force_complete(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        add_force_complete = self.mcm._put("restapi/requests/add_forcecomplete", {"prepid": root_request_prepid})
        assert add_force_complete.get("results") == False
        assert "Cannot add a request which is not submitted" in add_force_complete.get("message")

        # Submit and inject
        self.injector.inject()

        add_force_complete = self.mcm._put("restapi/requests/add_forcecomplete", {"prepid": root_request_prepid})
        assert add_force_complete.get("results") == False
        assert "Request is below 50 percent completion" in add_force_complete.get("message")


class TestRequestsAsUser(TestRequestsAsProdMgr):
    """
    Test the endpoints related to the request API
    impersonating a user.
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.USER)

    def test_reset_delete(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        delete_result = self.mcm._delete(f"restapi/requests/delete/{root_request_prepid}")
        reset_result = self.mcm._get(f"restapi/requests/reset/{root_request_prepid}")
        assert (
            "You don't have the permission to access the requested resource" in delete_result.get("message") 
        )
        assert (
            "You don't have the permission to access the requested resource" in reset_result.get("message") 
        )

    def test_get_inject(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")

        endpoint_url = self.mcm.server + f"restapi/requests/get_inject/{root_request_prepid}"
        response = self.mcm.session.get(url=endpoint_url).json()
        assert (
            "You don't have the permission to access the requested resource" in response.get("message") 
        )

    def test_clone(self):
        # The request does not exists
        not_exists_result = self.mcm._get("restapi/requests/clone/NotExists")
        assert (
            "You don't have the permission to access the requested resource" in not_exists_result.get("message") 
        )

    def test_inspect(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        inspect_result = self.mcm._get(f"restapi/requests/inspect/{root_request_prepid}")
        assert (
            "You don't have the permission to access the requested resource" in inspect_result.get("message") 
        )

    def test_approve(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        approve_result = self.mcm.approve(object_type="requests", object_id=root_request_prepid)
        assert approve_result.get("results") == False
        assert "bad user admin level 0" in approve_result.get("message") 

    def test_force_complete(self):
        root_request = self.entities["root_request"]
        root_request_prepid = root_request.get("prepid", "")
        add_force_complete = self.mcm._put("restapi/requests/add_forcecomplete", {"prepid": root_request_prepid})
        force_complete_list = self.mcm._get("restapi/requests/forcecomplete")
        assert (
            "You don't have the permission to access the requested resource" in add_force_complete.get("message") 
        )
        assert (
            "You don't have the permission to access the requested resource" in force_complete_list.get("message") 
        )
