"""
This module tests the API operations related with
the campaign entity.
"""

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest


class CampaignAPI:
    """
    Implements some extra operations not related to CRUD
    operations.
    """
    def __init__(self, mcm: McMTesting) -> None:
        self.mcm = mcm
        self.object_type: str = "campaigns"

    def cms_drivers(self, mockup: dict) -> dict:
        """
        Retrieves the cms-sw commands for a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/get_cmsDrivers/<string:campaign_id>

        Returns:
            dict: The cms-sw driver commands for each step to simulate.
        """
        endpoint = f"restapi/campaigns/get_cmsDrivers/{mockup.get('prepid')}"
        return self.mcm._get(endpoint)

    def inspect(self, mockup: dict) -> str:
        """
        Inspect all the requests in a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/inspect/<string:campaign_id>

        Returns:
            str: The result of inspecting all the `request` linked to the `campaign`.
                This `inspect` process refers to synchronize the progress
                related to the `request` from ReqMgr2 (CMS' main request manager tool)
                to the McM application.
        """
        endpoint = f"restapi/campaigns/inspect/{mockup.get('prepid')}"
        http_res = self.mcm.session.get(self.mcm.server + endpoint)
        return http_res.text

    def toggle_status(self, mockup: dict) -> dict:
        """
        Toggles the status for a campaign.
        Related to test the endpoint:
            - restapi/campaigns/status/<string:campaign_id>

        Returns:
            dict: Result of the operation and description of error messages
                in case they happen. Format:
                - For sucessful execution: `{'results': True}`
                - In case of errors: `{'results': False, 'message': '<Description: str>`
                    - There are three common cases for the description:
                        - The campaign doesn't exists.
                        - Runtime exception when saving to the database.
                        - Any other exception.
        """
        endpoint = f"restapi/campaigns/status/{mockup.get('prepid')}"
        return self.mcm._get(endpoint)


class TestCampaign:
    """
    Test the campaign API.
    """

    def _configure_as_role(self, role: Roles, create: bool):
        """
        Create or mock some objects in McM to use in the
        assertions using a specific group of permissions.
        """
        env = Environment()
        mcm = McMTesting(config=env, role=role)
        api = CampaignAPI(mcm=mcm)
        injector = InjectRootRequest(mcm=mcm, environment=env)

        self.mcm = mcm
        self.env = env
        self.api = api
        self.injector = injector
        self.mocks = injector.mock()

        if create:
            # Only use the campaign without any other linked entity.
            entities = injector.create(mocks=self.mocks)
            mcm.delete(object_type="mccms", object_id=entities["mccm_ticket"]["prepid"])
            mcm.delete(object_type="requests", object_id=entities["root_request"]["prepid"])
            self.entities = {"campaign": entities["campaign"]}

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
        self.mcm.delete(object_type="campaigns", object_id=self.entities["campaign"]["prepid"])

    def test_retrieve(self):
        # The campaign exists
        mockup = self.mocks["campaign"]
        retrieved = self.mcm.get(object_type=self.api.object_type, object_id=mockup["prepid"])
        del mockup["history"]
        del retrieved["history"]
        del retrieved["_rev"]
        del retrieved["_id"]

        assert mockup == retrieved

        # The campaign doesn't exists
        not_exists = self.mcm.get(object_type=self.api.object_type, object_id="NotExists")
        assert not_exists == None

    def test_update(self):
        # The campaign is updated to a valid status
        example = self.entities["campaign"]
        example["cmssw_release"] = "CMSSW_14_0_0"
        content = self.mcm.update(object_type=self.api.object_type, object_data=example)
        retrieved = self.mcm.get(object_type=self.api.object_type, object_id=example["prepid"])

        assert content["results"] == True
        assert example["_rev"] != retrieved["_rev"]
        assert retrieved["cmssw_release"] == "CMSSW_14_0_0"

        # Update a campaign that doesn't exist.
        example["prepid"] = "Run3Campaign#2"
        content = self.mcm.update(object_type=self.api.object_type, object_data=example)

        assert content["results"] == False

    def test_delete(self):
        # The campaign exists
        example = self.entities["campaign"]
        self.mcm.delete(object_type=self.api.object_type, object_id=example["prepid"])
        retrieved = self.mcm.get(object_type=self.api.object_type, object_id=example["prepid"])
        assert retrieved == None

    def test_cmssw_drivers(self):
        example = self.entities["campaign"]
        content = self.api.cms_drivers(example)
        driver: str = content["results"][0]["default"]
        event_content = example["sequences"][0]["default"]["eventcontent"]
        event_content_param = ",".join(event_content)

        assert driver.startswith("cmsDriver.py")
        assert event_content_param in driver

        # The campaign doesn't exists
        example["prepid"] = "Run3Campaign#2"
        content = self.api.cms_drivers(example)
        assert content["results"] == False

    def test_inspect(self):
        # The campaign exists
        example = self.entities["campaign"]
        content = self.api.inspect(example)
        campaign_header: str = f"Starting campaign inspect of {example['prepid']}"
        campaign_footer: str = "Inspecting 0 requests on page 0"

        assert campaign_header in content
        assert campaign_footer in content

    def test_toggle_status(self):
        # Stop a valid campaign
        example = self.entities["campaign"]
        content = self.api.toggle_status(example)
        after_toggle = self.mcm.get(object_type=self.api.object_type, object_id=example["prepid"])
        assert content["results"] == True
        assert after_toggle["status"] == "stopped"

        # Start an invalid campaign
        del after_toggle["cmssw_release"]
        self.mcm.update(object_type=self.api.object_type, object_data=after_toggle)
        content = self.api.toggle_status(example)
        assert content["results"] == False


class TestCampaignAsProdMgr(TestCampaign):
    """
    Test the API for the campaign entity impersonating
    a production manager.
    """
    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.PRODUCTION_MANAGER, create=True)
        
    def test_delete(self):
        # This role is not able to delete the campaign
        example = self.entities["campaign"]
        self.mcm.delete(object_type=self.api.object_type, object_id=example["prepid"])
        retrieved = self.mcm.get(object_type=self.api.object_type, object_id=example["prepid"])
        assert retrieved == example


class TestCampaignAsUser(TestCampaignAsProdMgr):
    """
    Test the API for the campaign entity
    with the user role.
    """
    def setup_method(self, method):
        """
        Create some objects to perform the assertions
        based on the Root Request scenario.
        """
        self._configure_as_role(role=Roles.ADMINISTRATOR, create=True)
        self.mcm_as_user = McMTesting(config=self.env, role=Roles.USER)
        self.api_as_user = CampaignAPI(mcm=self.mcm_as_user)

    def test_create(self):
        # Not enough permissions.
        invalid_mockup = self.mocks["campaign"]
        invalid_mockup["prepid"] = "Run3Campaign#1"
        content = self.mcm_as_user.put(object_type=self.api.object_type, object_data=invalid_mockup)
        assert "You don't have the permission to access the requested resource" in content["message"]

    def test_retrieve(self):
        example = self.entities["campaign"]
        retrieved = self.mcm_as_user.get(object_type=self.api.object_type, object_id=example["prepid"])
        assert example == retrieved

    def test_update(self):
        # Not enough permissions.
        example = self.entities["campaign"]
        example["cmssw_release"] = "NotExist"
        content = self.mcm_as_user.update(object_type=self.api.object_type, object_data=example)
        assert "You don't have the permission to access the requested resource" in content["message"]

    def test_delete(self):
        # INFO: The user role is not able to create anything, just skip this.
        pass

    def test_cmssw_drivers(self):
        example = self.mocks["campaign"]
        content = self.api_as_user.cms_drivers(example)
        driver: str = content["results"][0]["default"]
        event_content = example["sequences"][0]["default"]["eventcontent"]
        event_content_param = ",".join(event_content)

        assert driver.startswith("cmsDriver.py")
        assert event_content_param in driver

        # The campaign doesn't exists
        mockup = self.mocks["campaign"]
        mockup["prepid"] = "NotExist"
        content = self.api_as_user.cms_drivers(mockup)
        assert content["results"] == False

    def test_inspect(self):
        # Not enough permissions.
        example = self.entities["campaign"]
        content = self.api_as_user.inspect(example)
        assert "You don't have the permission to access the requested resource" in content

    def test_toggle_status(self):
        # Not enough permissions.
        example = self.entities["campaign"]
        content = self.api_as_user.toggle_status(example)
        assert "You don't have the permission to access the requested resource" in content["message"]