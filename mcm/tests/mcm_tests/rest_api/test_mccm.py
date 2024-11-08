"""
This module tests the API operations related with
the MccM entity (tickets).
"""

import pytest

from mcm_tests.fixtures import injection_to_reqmgr
from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest, InjectToNanoAOD


class TestMccM:
    """
    Test the MccM entity.
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

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)

    def test_get(self):
        ticket = self.entities["mccm_ticket"]
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert ticket_data and isinstance(ticket_data, dict)
        assert ticket_data == ticket

    def test_cancel(self):
        # Set the ticket status to 'cancelled'
        ticket = self.entities["mccm_ticket"]
        cancel_result = self.mcm._get(f"restapi/mccms/cancel/{ticket['prepid']}")
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert cancel_result.get("results") == True
        assert ticket_data.get("status") == "cancelled"

        # Set the ticket status back to 'new'
        uncancel_result = self.mcm._get(f"restapi/mccms/cancel/{ticket['prepid']}")
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert uncancel_result.get("results") == True
        assert ticket_data.get("status") == "new"

    def test_delete(self):
        # The ticket does not exists!
        delete_result = self.mcm._delete("restapi/mccms/delete/NotExists")
        assert delete_result.get("results") == False
        assert "does not exist" in delete_result.get("message")

        # The ticket is in status 'new'
        ticket = self.entities["mccm_ticket"]
        delete_result = self.mcm._delete(f"restapi/mccms/delete/{ticket['prepid']}")
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert delete_result.get("results") == True
        assert not ticket_data

    def test_generate(self):
        # The ticket does not exists!
        generate_result = self.mcm._get("restapi/mccms/generate/NotExists")
        assert generate_result.get("results") == False
        assert "does not exist" in generate_result.get("message")

        ticket = self.entities["mccm_ticket"]
        generate_result = self.mcm._get(f"restapi/mccms/generate/{ticket['prepid']}?reserve=true")
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert generate_result.get("results") == True
        assert ticket_data.get("generated_chains"), "No chained request was created"

    def test_editable(self):
        # The status is 'new', fields can be editable.
        ticket = self.entities["mccm_ticket"]
        editable_fields = self.mcm._get(f"restapi/mccms/editable/{ticket['prepid']}").get("results")
        expected_editable = {
            '_id': True, 
            'block': True, 
            'chains': True, 
            'generated_chains': False, 
            'history': True, 
            'meeting': False, 
            'notes': True, 
            'prepid': False, 
            'pwg': False, 
            'repetitions': True, 
            'requests': True, 
            'status': False, 
            'tags': True, 
            'threshold': True, 
            'total_events': True
        }
        assert editable_fields == expected_editable

        # Any other status make the ticket to be uneditable.
        cancel_result = self.mcm._get(f"restapi/mccms/cancel/{ticket['prepid']}")
        editable_fields = self.mcm._get(f"restapi/mccms/editable/{ticket['prepid']}").get("results")
        assert cancel_result.get("results") == True
        assert all(value == False for value in editable_fields.values()), "No field should be editable!"

    @pytest.mark.usefixtures("injection_to_reqmgr")
    def test_check_all_approved(self):
        # No request related to this ticket has been created
        # or it is not submit approval
        ticket = self.entities["mccm_ticket"]
        check_all_result = self.mcm._get(f"restapi/mccms/check_all_approved/{ticket['prepid']}")
        assert check_all_result.get("results") == False

        # Reserve the ticket and submit
        self.injector.inject()
        check_all_result = self.mcm._get(f"restapi/mccms/check_all_approved/{ticket['prepid']}")
        assert check_all_result.get("results") == True

    def test_update_total_events(self):
        update_events_result = self.mcm._get(f"restapi/mccms/update_total_events/NotExists")
        assert update_events_result.get("results") == False
        assert "does not exist" in update_events_result.get("message")

        ticket = self.entities["mccm_ticket"]
        update_events_result = self.mcm._get(f"restapi/mccms/update_total_events/{ticket['prepid']}")
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))
        assert update_events_result.get("results") == True
        assert ticket.get("total_events") == 0
        assert ticket_data.get("total_events") > 0

    def test_update(self):
        custom_note = "Test for update endpoint"
        ticket = self.entities["mccm_ticket"]
        ticket["notes"] = custom_note
        update_result = self.mcm.update(object_type="mccms", object_data=ticket)
        ticket_data = self.mcm.get(object_type="mccms", object_id=ticket.get("prepid", ""))

        assert update_result.get("results") == True
        assert ticket_data.get("notes") == custom_note


class TestMccMAsProdMgr(TestMccM):
    """
    Test the endpoints related to the MccM API
    impersonating a production manager.
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.PRODUCTION_MANAGER)


class TestMccMAsUser(TestMccMAsProdMgr):
    """
    Test the endpoints related to the MccM API
    impersonating a User
    """

    def setup_method(self, method):
        self._configure_as_role(role=Roles.ADMINISTRATOR)
        self.mcm = McMTesting(config=self.env, role=Roles.USER)

    def test_cancel(self):
        ticket = self.entities["mccm_ticket"]
        cancel_result = self.mcm._get(f"restapi/mccms/cancel/{ticket['prepid']}")
        assert (
            "You don't have the permission to access the requested resource"
            in cancel_result.get("message")
        )

    def test_delete(self):
        delete_result = self.mcm._delete("restapi/mccms/delete/NotExists")
        assert (
            "You don't have the permission to access the requested resource"
            in delete_result.get("message")
        )

    def test_generate(self):
        generate_result = self.mcm._get("restapi/mccms/generate/NotExists")
        assert (
            "You don't have the permission to access the requested resource"
            in generate_result.get("message")
        )

    def test_check_all_approved(self):
        ticket = self.entities["mccm_ticket"]
        check_all_result = self.mcm._get(f"restapi/mccms/check_all_approved/{ticket['prepid']}")
        assert (
            "You don't have the permission to access the requested resource"
            in check_all_result.get("message")
        )

    def test_update_total_events(self):
        update_events_result = self.mcm._get(f"restapi/mccms/update_total_events/NotExists")
        assert (
            "You don't have the permission to access the requested resource"
            in update_events_result.get("message")
        )

    def test_update(self):
        ticket = self.entities["mccm_ticket"]
        update_result = self.mcm.update(object_type="mccms", object_data=ticket)
        assert (
            "You don't have the permission to access the requested resource"
            in update_result.get("message")
        )

    def test_editable(self):
        ticket = self.entities["mccm_ticket"]
        editable_fields = self.mcm._get(f"restapi/mccms/editable/{ticket['prepid']}").get("results")
        expected_editable = {
            '_id': True, 
            'block': True, 
            'chains': True, 
            'generated_chains': False, 
            'history': True, 
            'meeting': False, 
            'notes': True, 
            'prepid': False, 
            'pwg': False, 
            'repetitions': True, 
            'requests': True, 
            'status': False, 
            'tags': True, 
            'threshold': True, 
            'total_events': True
        }
        assert editable_fields == expected_editable
