"""
This module tests the API operations related with
the chained campaign entity.
"""

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest


class TestChainedCampaign:
    """
    Test the chained campaign entity.
    """

    def _configure_as_role(self, role: Roles, create: bool):
        """
        Create or mock some objects in McM to use in the
        assertions using a specific group of permissions.
        """
        env = Environment()
        mcm = McMTesting(config=env, role=role)
        injector = InjectRootRequest(mcm=mcm, environment=env)

        self.mcm = mcm
        self.env = env
        self.injector = injector
        self.mocks = injector.mock()

        if create:
            # Automatically, McM creates a chained campaign
            # for the root campaign. Let's use it to check the assertions
            entities = injector.create(mocks=self.mocks)
            campaign = entities["campaign"]
            mcm.delete(object_type="mccms", object_id=entities["mccm_ticket"]["prepid"])
            mcm.delete(object_type="requests", object_id=entities["root_request"]["prepid"])

            self.entities = {"campaign": campaign}

            # Its ID follows the next rule
            self.chained_campaign_prepid = f"chain_{campaign.get('prepid')}"


    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR, create=True)
        
    def teardown_method(self, method):
        """
        Clean up resources in McM
        """
        self.mcm.delete(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        self.mcm.delete(object_type="campaigns", object_id=self.entities["campaign"]["prepid"])

    def test_retrieve(self):
        # The chained campaign already exists
        campaign = self.entities["campaign"]
        retrieved = self.mcm.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        assert isinstance(retrieved, dict) and retrieved
        assert campaign["prepid"] in retrieved["campaigns"][0]

        not_exists = self.mcm.get(object_type="chained_campaigns", object_id="NotExists")
        assert not_exists == None

    def test_update(self):
        example = self.mcm.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        example["notes"] = "Updated"
        content = self.mcm.update(object_type="chained_campaigns", object_data=example)
        retrieved = self.mcm.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)

        assert content["results"] == True
        assert retrieved["notes"] == "Updated"

        # Update a chained campaign that doesn't exist.
        retrieved["prepid"] = "Run3Campaign#2"
        content = self.mcm.update(object_type="chained_campaigns", object_data=retrieved)

        assert content["results"] == False

    def test_delete(self):
        example = self.mcm.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        self.mcm.delete(object_type="chained_campaigns", object_id=example["prepid"])
        retrieved = self.mcm.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        assert retrieved == None


class TestChainedCampaignAsProdMgr(TestChainedCampaign):
    """
    Test the API for the chained campaign entity impersonating
    a production manager.
    """
    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)
        

class TestCampaignAsUser(TestChainedCampaignAsProdMgr):
    """
    Test the API for the chained campaign entity
    with the user role.
    """
    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR, create=True)
        self.mcm_as_user = McMTesting(config=self.env, role=Roles.USER)

    def test_retrieve(self):
        campaign = self.entities["campaign"]
        retrieved = self.mcm_as_user.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        assert isinstance(retrieved, dict) and retrieved
        assert campaign["prepid"] in retrieved["campaigns"][0]

        not_exists = self.mcm_as_user.get(object_type="chained_campaigns", object_id="NotExists")
        assert not_exists == None

    def test_update(self):
        # Not enough permissions.
        example = self.mcm_as_user.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        example["notes"] = "NotExist"
        content = self.mcm_as_user.update(object_type="chained_campaigns", object_data=example)
        assert "You don't have the permission to access the requested resource" in content["message"]

    def test_delete(self):
        # Not enough permissions.
        example = self.mcm_as_user.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        self.mcm_as_user.delete(object_type="chained_campaigns", object_id=example["prepid"])
        retrieved = self.mcm_as_user.get(object_type="chained_campaigns", object_id=self.chained_campaign_prepid)
        assert retrieved == example
