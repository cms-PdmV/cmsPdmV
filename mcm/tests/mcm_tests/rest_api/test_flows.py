"""
This module tests the API operations related with
the flows entity.
"""

import random
from mcm_tests.rest_api.api_tools import McMTesting, Roles, Environment
from mcm_tests.use_cases.full_injection.core import InjectToNanoAOD


class TestFlows:
    """
    Test the endpoints related to the flows API.
    """

    def _configure_as_role(self, role: Roles):
        """
        Create or mock some objects in McM to use in the
        assertions using a specific group of permissions.
        """
        self.env = Environment()
        self.mcm = McMTesting(config=self.env, role=role)
        self.injector = InjectToNanoAOD(mcm=self.mcm, environment=self.env)
        self.entities = self.injector.create(mocks=self.injector.mock())

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)

    def test_get(self):
        # The flow exists
        dr_flow = self.entities.get("flow_to_dr", {})
        from_db = self.mcm.get(object_type="flows", object_id=dr_flow.get("prepid"))
        assert from_db == dr_flow

        # The flow does not exist
        not_exists = self.mcm.get(object_type="flows", object_id="NotExists")
        assert not_exists == None

    def test_update(self):
        # The flow exists
        custom_note = "This is a sample note"
        dr_flow = self.entities.get("flow_to_dr", {})
        dr_flow["notes"] = custom_note
        update_result = self.mcm.update(object_type="flows", object_data=dr_flow)
        assert update_result.get("results") == True

        dr_flow = self.mcm.get(object_type="flows", object_id=dr_flow.get("prepid"))
        assert dr_flow["notes"] == custom_note

    def test_clone(self):
        dr_flow = self.entities.get("flow_to_dr", {})
        new_prepid = f"{dr_flow['prepid']}TestClone{random.randint(1,99999):05}"
        dr_flow["new_prepid"] = new_prepid
        clone_result = self.mcm.put(
            object_type="flows", object_data=dr_flow, method="clone"
        )
        assert clone_result.get("results") == True

        from_db = self.mcm.get(object_type="flows", object_id=new_prepid)
        assert (
            from_db != None
            and isinstance(from_db, dict)
            and from_db["prepid"] == new_prepid
        )

    def test_approve(self):
        dr_flow = self.entities.get("flow_to_dr", {})
        dr_flow["approval"] = "none"

        self.mcm.update(object_type="flows", object_data=dr_flow)
        dr_flow = self.mcm.get(object_type="flows", object_id=dr_flow.get("prepid"))
        assert dr_flow.get("approval") == "none"

        # Check next statuses
        for status in ["flow", "submit", "tasksubmit"]:
            approve_result = self.mcm._get(
                f"restapi/flows/approve/{dr_flow.get('prepid')}"
            )
            assert approve_result.get("results") == True

            dr_flow = self.mcm.get(object_type="flows", object_id=dr_flow.get("prepid"))
            assert dr_flow["approval"] == status

    def test_delete(self):
        # The flow is linked to a chained campaign
        dr_flow = self.entities.get("flow_to_dr", {})
        delete_result = self.mcm._delete(
            f"restapi/flows/delete/{dr_flow.get('prepid')}"
        )
        assert delete_result.get("results") == False

        # It is possible to delete flows only if they do not
        # have campaigns or requests linked.
        # Let's create another from scratch
        new_flow_prepid = f"flowTesting{random.randint(1,99999):05}"
        new_flow = {
            "prepid": new_flow_prepid,
            "allowed_campaigns": [],
            "next_campaign": "",
            "approval": "none",
            "request_parameters": {},
            "notes": "",
            "history": [],
        }
        new_flow = self.mcm.put(object_type="flows", object_data=new_flow)
        assert new_flow.get("results") == True
        delete_result = self.mcm._delete(f"restapi/flows/delete/{new_flow_prepid}")
        assert delete_result.get("results") == True


class TestFlowsAsProdMgr(TestFlows):
    """
    Test the API for the flows entity impersonating
    a production manager.
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER)


class TestFlowsAsUser(TestFlowsAsProdMgr):
    """
    Test the API for the flows entity impersonating
    a user.
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.USER)

    def test_update(self):
        custom_note = "This is a sample note"
        dr_flow = self.entities.get("flow_to_dr", {})
        dr_flow["notes"] = custom_note
        update_result = self.mcm.update(object_type="flows", object_data=dr_flow)
        assert (
            "You don't have the permission to access the requested resource."
            in update_result.get("message")
        )

    def test_clone(self):
        dr_flow = self.entities.get("flow_to_dr", {})
        new_prepid = f"{dr_flow['prepid']}TestClone{random.randint(1,99999):05}"
        dr_flow["new_prepid"] = new_prepid
        clone_result = self.mcm.put(
            object_type="flows", object_data=dr_flow, method="clone"
        )
        assert (
            "You don't have the permission to access the requested resource."
            in clone_result.get("message")
        )

    def test_approve(self):
        dr_flow = self.entities.get("flow_to_dr", {})
        approve_result = self.mcm._get(f"restapi/flows/approve/{dr_flow.get('prepid')}")
        assert (
            "You don't have the permission to access the requested resource."
            in approve_result.get("message")
        )

    def test_delete(self):
        # The flow is linked to a chained campaign
        dr_flow = self.entities.get("flow_to_dr", {})
        delete_result = self.mcm._delete(
            f"restapi/flows/delete/{dr_flow.get('prepid')}"
        )
        assert (
            "You don't have the permission to access the requested resource."
            in delete_result.get("message")
        )
