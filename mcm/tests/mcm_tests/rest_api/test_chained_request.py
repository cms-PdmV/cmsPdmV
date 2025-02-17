"""
This module tests the API operations related with
the chained request entity.
"""

import pytest

from mcm_tests.fixtures import injection_to_reqmgr
from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest, InjectToNanoAOD


@pytest.mark.usefixtures("injection_to_reqmgr")
class TestChainedRequest:
    """
    Test the chained request entity.
    """

    def _configure_as_role(self, role: Roles):
        """
        Create or mock some objects in McM to use in the
        assertions using a specific group of permissions.
        """
        self.env = Environment()
        self.mcm = McMTesting(config=self.env, role=role)
        self.injector = InjectRootRequest(mcm=self.mcm, environment=self.env)
        self.entities = self.injector.create(mocks=self.injector.mock())
        self.injector.inject()

        # Get the chained requests from the ticket.
        ticket = self.entities["mccm_ticket"]
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket["prepid"])
        self.entities["chained_requests_prepids"] = list(ticket_data["generated_chains"])

    def _prepare_long_chained_request(self) -> dict:
        """
        Injects a chained request that includes several intermediate
        requests and steps to use in other test cases.
        """
        # Prepare a long chained request to operate.
        injector = InjectToNanoAOD(mcm=self.mcm, environment=self.env)
        entities_long_chain = injector.create(mocks=injector.mock())
        injector.inject()

        ticket = entities_long_chain["mccm_ticket"]
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket["prepid"])
        created_chains = list(ticket_data["generated_chains"])
        chained_request_prepid = created_chains[0]

        # Disable the `flag` to operate it.
        chained_request_data = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert chained_request_data is not None
        assert chained_request_data.get('prepid') == chained_request_prepid
        chained_request_data["action_parameters"]["flag"] = False

        update_result = self.mcm.update(object_type="chained_requests", object_data=chained_request_data)
        assert update_result.get("results") == True
        chained_request_data = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        return chained_request_data

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)

    def test_get(self):
        # Get the chained request from the ticket.
        created_chain_prepid = self.entities["chained_requests_prepids"][0]
        chained_request_data = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        assert chained_request_data is not None
        assert chained_request_data.get("prepid") == created_chain_prepid

    def test_update(self):
        created_chain_prepid = self.entities["chained_requests_prepids"][0]
        chained_request_data = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        chained_request_data["pwg"] = "SystemTesting"
        update_result = self.mcm.update(object_type="chained_requests", object_data=chained_request_data)
        assert update_result.get("results") == True

        chained_request_data = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        assert chained_request_data["pwg"] == "SystemTesting"

    def test_chained_composition(self):
        """
        This scenario checks several actions
        related to alter the composition of the chain
        like: rewind, rewind_to_root, force_done, back_forcedone
        and approve endpoints.
        """
        chained_request = self._prepare_long_chained_request()
        chained_request_prepid = chained_request["prepid"]

        # Rewind the chained request one step
        current_step = chained_request.get("step")
        rewind_result = self.mcm._get(f"restapi/chained_requests/rewind/{chained_request['prepid']}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert rewind_result.get("results") == True
        assert chained_request.get("step") == current_step - 1

        # Rewind to root
        rewind_root_result = self.mcm._get(f"restapi/chained_requests/rewind_to_root/{chained_request['prepid']}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert rewind_root_result.get("results") == True
        assert chained_request.get("step") == 0

        # Force the chained request to `done`
        # INFO: This only moves the chained request status to `force_done`
        # but the requests remain untouched, what is the purpose of this?
        to_force_done = self.mcm._get(f"restapi/chained_requests/force_done/{chained_request['prepid']}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert to_force_done.get("results") == True
        assert chained_request.get("status") == "force_done"

        # Move the chained request back to processing
        # INFO: Also for this!
        to_processing = self.mcm._get(f"restapi/chained_requests/back_forcedone/{chained_request['prepid']}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert to_processing.get("results") == True
        assert chained_request.get("status") == "processing"

        # Approve a chained request
        # INFO: The same issue, the status is not consistent
        # with the requests and its submission status.
        current_approval = chained_request.get("approval")
        approve_result = self.mcm.approve(object_type="chained_requests", object_id=chained_request_prepid)
        chained_request = self.mcm.get(object_type="chained_requests", object_id=chained_request_prepid)
        assert approve_result.get("results") == True
        assert chained_request.get("approval") != current_approval

    def test_delete(self):
        # Remove the chained request
        # Fails as the chained request is not disabled.
        created_chain_prepid = self.entities["chained_requests_prepids"][0]
        delete_result = self.mcm._delete(f"restapi/chained_requests/delete/{created_chain_prepid}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        assert delete_result.get("results") == False and "is not disabled" in delete_result.get("message")

        # Disable it
        chained_request["action_parameters"]["flag"] = False
        update_result = self.mcm.update(object_type="chained_requests", object_data=chained_request)
        assert update_result.get("results") == True

        # Root request is not reset
        delete_result = self.mcm._delete(f"restapi/chained_requests/delete/{created_chain_prepid}")
        chained_request = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        assert delete_result.get("results") == False 
        assert "will not be chained anymore" in delete_result.get("message")

        # Reset the root request and the chain
        result = self.injector.resubmitter._invalidator.invalidate_delete_cascade_requests(
            requests_prepid=chained_request.get("chain", []),
            remove_chain=True
        )
        chained_request = self.mcm.get(object_type="chained_requests", object_id=created_chain_prepid)
        assert chained_request == None
