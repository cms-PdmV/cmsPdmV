"""
This module tests the API operations related with
the invalidations entity.
"""

import types

import pytest
from rest.applications.mcm.invalidate_request import InvalidateDeleteRequests

from mcm_tests.fixtures import injection_to_reqmgr
from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest


@pytest.mark.usefixtures("injection_to_reqmgr")
class TestInvalidations:
    """
    Test the endpoints related to the invalidations API.
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
    
        # Create and inject a sample root request.
        # to invalidate in the further steps.
        self.entities = self.injector.create(mocks=self.injector.mock())
        self.injector.inject()

        # Monkey patch a custom invalidator
        # so that you can control the invalidation section.
        # Preprocess the requests and chained requests
        # so that invalidation records are available.
        def _custom_process_invalidation(self, request_prepids):
            pass

        custom_invalidator = InvalidateDeleteRequests(mcm=self.mcm)
        custom_invalidator._process_invalidation = types.MethodType(
            _custom_process_invalidation,
            custom_invalidator
        )
        root_request = self.entities["root_request"]
        custom_invalidator._invalidate_delete_root_request(
            root_prepid=root_request["prepid"],
            remove_chain=True
        )

        # Retrieve the invalidation records.
        self.invalidations = self.invalidator._get_invalidations(
            requests=[self.entities["root_request"]["prepid"]]
        )

    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR)

    def test_get(self):
        # Retrieve a root request.
        sample_invalidation = self.invalidations[0]
        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation["_id"])
        assert sample_invalidation == from_mcm
    
    def test_delete(self):
        # Delete an invalidation record.
        sample_invalidation = self.invalidations[0]
        self.mcm.delete(object_type="invalidations", object_id=sample_invalidation["_id"])
        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation["_id"])
        assert from_mcm == None, "The invalidation should not exist!"

    def test_acknowledge(self):
        # Set the status to acknowledge just by 
        # changing the attribute.
        sample_invalidation = self.invalidations[0]
        self.mcm._get(url=f"restapi/invalidations/acknowledge/{sample_invalidation['_id']}")
        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation['_id'])
        assert isinstance(from_mcm, dict), "The invalidation should exist!"
        assert from_mcm["status"] == "acknowledged", "Invalidation should be acknowledged"

    def test_update_status(self):
        """
        Check that the invalidation status
        can be updated and then be announced to
        other CMS services.
        """
        sample_invalidation = self.invalidations[0]
        
        # Move the invalidation to HOLD status
        to_hold = self.mcm._put("restapi/invalidations/new_to_hold", data=[sample_invalidation["_id"]])
        assert isinstance(to_hold, dict)
        assert to_hold["results"][0]["results"] == True

        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation['_id'])
        assert from_mcm["status"] == "hold"

        # Move the invalidation to NEW status
        from_hold_to_new = self.mcm._put("restapi/invalidations/hold_to_new", data=[sample_invalidation["_id"]])
        assert isinstance(from_hold_to_new, dict)

        # FIXME: These endpoints should have the same response format!
        assert from_hold_to_new["results"][0] == True

        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation['_id'])
        assert from_mcm["status"] == "new"

        # Clear the invalidations
        # Set the invalidation status as `announced` directly
        # in the document.
        self.mcm._put("restapi/invalidations/clear", data=[sample_invalidation["_id"]])
        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation['_id'])
        assert from_mcm["status"] == "announced"

    def test_announce(self):
        sample_invalidation = self.invalidations[0]

        # Announce the invalidation
        # Sending an email to stakeholders
        self.mcm._put("restapi/invalidations/announce", data=[sample_invalidation["_id"]])
        from_mcm = self.mcm.get(object_type="invalidations", object_id=sample_invalidation['_id'])
        assert from_mcm["status"] == "announced"


class TestInvalidationsAsProdMgr(TestInvalidations):
    """
    Test the endpoints related to the invalidations API
    impersonating a production manager.
    """

    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.PRODUCTION_MANAGER)

    def test_get(self):
        # Retrieve a root request.
        sample_invalidation = self.invalidations[0]
        from_mcm = self.mcm._get(url=f"restapi/invalidations/get/{sample_invalidation['_id']}")
        assert "You don't have the permission to access the requested resource." in from_mcm["message"]

    def test_delete(self):
        # Delete an invalidation record.
        sample_invalidation = self.invalidations[0]
        from_mcm = self.mcm._delete(url=f"restapi/invalidations/delete/{sample_invalidation['_id']}")
        assert "You don't have the permission to access the requested resource." in from_mcm["message"]

    def test_acknowledge(self):
        sample_invalidation = self.invalidations[0]
        from_mcm = self.mcm._get(url=f"restapi/invalidations/acknowledge/{sample_invalidation['_id']}")
        assert "You don't have the permission to access the requested resource." in from_mcm["message"]

    def test_update_status(self):
        """
        Check that the invalidation status
        can be updated and then be announced to
        other CMS services.
        """
        # FIXME: Avoid assertions that require
        # retrieving the document again to check the status
        # as the GET operation is only reserved for administrators
        # Should we downgrade the required permissions?
        sample_invalidation = self.invalidations[0]
        
        # Move the invalidation to HOLD status
        to_hold = self.mcm._put("restapi/invalidations/new_to_hold", data=[sample_invalidation["_id"]])
        assert isinstance(to_hold, dict)
        assert to_hold["results"][0]["results"] == True

        # Move the invalidation to NEW status
        from_hold_to_new = self.mcm._put("restapi/invalidations/hold_to_new", data=[sample_invalidation["_id"]])
        assert isinstance(from_hold_to_new, dict)
        assert from_hold_to_new["results"][0] == True

        # Clear the invalidations
        # Set the invalidation status as `announced` directly
        # in the document.
        clear_result = self.mcm._put("restapi/invalidations/clear", data=[sample_invalidation["_id"]])
        assert clear_result["results"] == True
        assert clear_result["requests_to_invalidate"][0]["_id"] == sample_invalidation["_id"]

    def test_announce(self):
        sample_invalidation = self.invalidations[0]
        # Announce the invalidation
        # Sending an email to stakeholders
        announce_result = self.mcm._put("restapi/invalidations/announce", data=[sample_invalidation["_id"]])
        assert announce_result["results"] == True
        assert announce_result["requests_to_invalidate"][0]["_id"] == sample_invalidation["_id"]


class TestInvalidationsAsUser(TestInvalidationsAsProdMgr):
    """
    Test the endpoints related to the invalidations API
    impersonating a user.
    """

    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.USER)

    def test_announce(self):
        sample_invalidation = self.invalidations[0]
        # Announce the invalidation
        # Sending an email to stakeholders
        from_mcm = self.mcm._put("restapi/invalidations/announce", data=[sample_invalidation["_id"]])
        assert "You don't have the permission to access the requested resource." in from_mcm["message"]

    def test_update_status(self):
        """
        Check that the invalidation status
        can be updated and then be announced to
        other CMS services.
        """
        sample_invalidation = self.invalidations[0]
        
        # Move the invalidation to HOLD status
        to_hold = self.mcm._put("restapi/invalidations/new_to_hold", data=[sample_invalidation["_id"]])
        assert "You don't have the permission to access the requested resource." in to_hold["message"]

        # Move the invalidation to NEW status
        from_hold_to_new = self.mcm._put("restapi/invalidations/hold_to_new", data=[sample_invalidation["_id"]])
        assert "You don't have the permission to access the requested resource." in from_hold_to_new["message"]

        # Clear the invalidations
        # Set the invalidation status as `announced` directly
        # in the document.
        from_mcm = self.mcm._put("restapi/invalidations/clear", data=[sample_invalidation["_id"]])
        assert "You don't have the permission to access the requested resource." in from_mcm["message"]
