"""
This test group checks the full MC sample injection process
described by the `core.py` module.
"""

import pytest

from mcm_tests.fixtures import (
    able_to_access_internal_resources,
    injection_to_reqmgr,
    nanoaod_injector,
    root_request_injector,
    authenticate_by_stdin,
    mcm_client,
)
from mcm_tests.use_cases.full_injection.core import InjectRootRequest, InjectToNanoAOD


@pytest.mark.usefixtures(
    "injection_to_reqmgr", "able_to_access_internal_resources"
)
class TestInjectRootRequest:
    """
    Check that it is possible to inject a root request
    from scratch.
    """

    def test_root_requests_injector(
        self, root_request_injector: InjectRootRequest
    ) -> None:
        """
        Check the behavior to inject a root request from scratch.
        """
        # Retrieve some mock elements
        mocks = root_request_injector.mock()

        # Create the elements in McM
        root_request_injector.create(mocks=mocks)

        # Perform the injection
        root_request_injector.inject()

        # Check that the chained request were properly submitted to ReqMgr2.
        mccm_ticket_data = root_request_injector.entities.get("mccm_ticket")
        mccm_ticket = root_request_injector.mcm.get(
            object_type="mccms", object_id=mccm_ticket_data["prepid"]
        )
        assert mccm_ticket and isinstance(mccm_ticket, dict), "Ticket data not found"

        chained_requests = mccm_ticket.get("generated_chains")
        assert chained_requests and isinstance(
            chained_requests, dict
        ), "Chained request was not reserved"
        assert (
            len(chained_requests) == 1
        ), "More than one chained request was generated. This is not expected"

        chained_request_prepid = list(chained_requests.keys())[0]
        chained_request = root_request_injector.mcm.get(
            object_type="chained_requests", object_id=chained_request_prepid
        )
        assert chained_request and isinstance(
            chained_request, dict
        ), "Chained request not found"

        requests_in_chain = chained_request.get("chain", [])
        assert requests_in_chain, "The request list should not be empty"
        assert (
            len(requests_in_chain) == 1
        ), "Only the root request should be available in the chained request"

        for request_prepid in requests_in_chain:
            request = root_request_injector.mcm.get(
                object_type="requests", object_id=request_prepid
            )
            assert request and isinstance(request, dict), "Request should be available"

            request_approval = request.get("approval")
            request_status = request.get("status")
            assert request_approval == "submit" and request_status == "submitted"

            # INFO: In the future, we could also include features
            # to check the submission in ReqMgr2 directly.
            # At this point, just check that the `reqmgr_name` is included
            # in the document.
            assert request.get(
                "reqmgr_name", []
            ), "No workflow name was recorded inside the request"

        # Clean up
        root_request_injector.cleanup()


@pytest.mark.usefixtures(
    "injection_to_reqmgr", "able_to_access_internal_resources"
)
class TestInjectToNanoAOD:
    """
    Check that it is possible to inject a root request
    to NanoAOD from scratch.
    """

    def test_nanoaod_injector(self, nanoaod_injector: InjectToNanoAOD) -> None:
        """
        Check the behavior to inject a root request from scratch.
        """
        # Retrieve some mock elements
        mocks = nanoaod_injector.mock()

        # Create the elements in McM
        nanoaod_injector.create(mocks=mocks)

        # Perform the injection
        nanoaod_injector.inject()

        # Check that the chained request was properly submitted to ReqMgr2.
        mccm_ticket_data = nanoaod_injector.entities.get("mccm_ticket")
        mccm_ticket = nanoaod_injector.mcm.get(
            object_type="mccms", object_id=mccm_ticket_data["prepid"]
        )
        assert mccm_ticket and isinstance(mccm_ticket, dict), "Ticket data not found"

        chained_requests = mccm_ticket.get("generated_chains")
        assert chained_requests and isinstance(
            chained_requests, dict
        ), "Chained request was not reserved"
        assert (
            len(chained_requests) == 1
        ), "More than one chained request was generated. This is not expected"

        chained_request_prepid = list(chained_requests.keys())[0]
        chained_request = nanoaod_injector.mcm.get(
            object_type="chained_requests", object_id=chained_request_prepid
        )
        assert chained_request and isinstance(
            chained_request, dict
        ), "Chained request not found"

        requests_in_chain = chained_request.get("chain", [])
        assert requests_in_chain, "The request list should not be empty"
        assert (
            len(requests_in_chain) == 4
        ), "Four requests should be created: Root request, DR, MiniAOD and NanoAOD"

        for request_prepid in requests_in_chain:
            request = nanoaod_injector.mcm.get(
                object_type="requests", object_id=request_prepid
            )
            assert request and isinstance(request, dict), "Request should be available"

            request_approval = request.get("approval")
            request_status = request.get("status")
            assert request_approval == "submit" and request_status == "submitted"

            # INFO: In the future, we could also include features
            # to check the submission in ReqMgr2 directly.
            # At this point, just check that the `reqmgr_name` is included
            # in the document.
            assert request.get(
                "reqmgr_name", []
            ), "No workflow name was recorded inside the request"

        # Clean up
        nanoaod_injector.cleanup()
