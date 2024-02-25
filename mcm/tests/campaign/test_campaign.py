"""
This module tests the API operations related with
the campaign entity.
"""

import uuid
from pathlib import Path
from copy import deepcopy
import pytest
from tests.base_test_tools import Entity, EntityTest, api
from tests.api_tools import McM, Roles


class CampaignAPI(Entity):
    """
    Implements a simple test API client focused
    only on the campaign operations.
    """

    def __init__(self, mcm: McM) -> None:
        mock_path = Path("./tests/campaign/static/campaign.json").absolute()
        super().__init__(mock_path, mcm)
        self.object_type: str = "campaigns"

    def mockup(self):
        mock = deepcopy(self._original_mockup)
        suffix: str = str(uuid.uuid4()).split("-")[0]
        new_id: str = f"Test{mock.get('prepid', '')}R{suffix}"
        mock["_id"] = new_id
        mock["prepid"] = new_id
        return mock

    def create(self, mockup: dict):
        return self.mcm.put(self.object_type, mockup)

    def retrieve(self, mockup: dict):
        return self.mcm.get(self.object_type, mockup.get("prepid"))

    def update(self, mockup: dict):
        return self.mcm.update(self.object_type, mockup)

    def delete(self, mockup: dict):
        return self.mcm.delete(self.object_type, mockup.get("prepid"))

    def example(self):
        mockup = self.mockup()
        self.create(mockup)
        return self.retrieve(mockup)

    def cms_drivers(self, mockup: dict):
        """
        Retrieves the cms-sw commands for a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/get_cmsDrivers/<string:campaign_id>
        """
        endpoint = f"restapi/campaigns/get_cmsDrivers/{mockup.get('prepid')}"
        return self.mcm._get(endpoint)

    def inspect(self, mockup: dict):
        """
        Inspect all the requests in a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/inspect/<string:campaign_id>
        """
        endpoint = f"restapi/campaigns/inspect/{mockup.get('prepid')}"
        return self.mcm._get(endpoint)

    def status(self, mockup: dict):
        """
        Toggles the status for a campaign.
        Related to test the endpoint:
            - restapi/campaigns/status/<string:campaign_id>
        """
        endpoint = f"restapi/campaigns/status/{mockup.get('prepid')}"
        return self.mcm._get(endpoint)


class TestCampaign(EntityTest):
    """
    Test the campaign API.
    """

    @property
    def entity_api(self) -> CampaignAPI:
        mcm: McM = api.mcm_client(Roles.ADMINISTRATOR)
        return CampaignAPI(mcm)

    def test_create(self):
        # Invalid name
        invalid_mockup = self.entity_api.mockup()
        invalid_mockup["prepid"] = "Run3Campaign#1"
        content, response = self.entity_api.create(invalid_mockup)

        assert response.status_code == 200
        assert content["results"] == False

        # Valid campaign
        valid_mockup = self.entity_api.mockup()
        content, response = self.entity_api.create(valid_mockup)

        assert response.status_code == 200
        assert content["results"] == True

    def test_retrieve(self):
        # The campaign exists
        mockup = self.entity_api.mockup()
        self.entity_api.create(mockup)
        retrieved = self.entity_api.retrieve(mockup)
        del mockup["history"]
        del retrieved["history"]
        del retrieved["_rev"]

        assert mockup == retrieved

        # The campaign doesn't exists
        not_exists = self.entity_api.retrieve(self.entity_api.mockup())
        assert not_exists == None

    def test_update(self):
        # The campaign is updated to a valid status
        example = self.entity_api.example()
        example["cmssw_release"] = "CMSSW_14_0_0"
        content, response = self.entity_api.update(example)
        retrieved = self.entity_api.retrieve(example)

        assert response.status_code == 200
        assert content["results"] == True
        assert example["_rev"] != retrieved["_rev"]
        assert retrieved["cmssw_release"] == "CMSSW_14_0_0"

        # Update a campaign that doesn't exist.
        example = self.entity_api.example()
        example["prepid"] = "Run3Campaign#2"
        content, response = self.entity_api.update(example)

        assert response.status_code == 200
        assert content["results"] == False

    @pytest.mark.skip("Takes too much time to compute")
    def test_delete(self):
        pass

    def test_cmssw_drivers(self):
        example = self.entity_api.example()
        content, response = self.entity_api.cms_drivers(example)
        driver: str = content["results"][0]["default"]
        event_content = example["sequences"][0]["default"]["eventcontent"]
        event_content_param = ",".join(event_content)

        assert response.status_code == 200
        assert driver.startswith("cmsDriver.py")
        assert event_content_param in driver

        # The campaign doesn't exists
        mockup = self.entity_api.mockup()
        content, response = self.entity_api.cms_drivers(mockup)
        assert response.status_code == 200
        assert content["results"] == False

    @pytest.mark.skip("Takes too much time to computes and renders a html page")
    def test_inspect(self):
        pass

    def test_status(self):
        # Stop a valid campaign
        example = self.entity_api.example()
        content, response = self.entity_api.status(example)
        after_toggle = self.entity_api.retrieve(example)
        assert response.status_code == 200
        assert content["results"] == True
        assert after_toggle["status"] == "stopped"

        # Start an invalid campaign
        del after_toggle["cmssw_release"]
        self.entity_api.update(after_toggle)
        content, response = self.entity_api.status(example)
        assert response.status_code == 200
        assert content["results"] == False


class TestCampaignAsProdMgr(TestCampaign):
    """
    Test the API for the campaign entity impersonating
    a production manager.
    """

    @property
    def entity_api(self) -> CampaignAPI:
        mcm: McM = api.mcm_client(Roles.PRODUCTION_MANAGER)
        return CampaignAPI(mcm)

    def test_delete(self):
        # Not enough permissions.
        example = self.entity_api.example()
        _, response = self.entity_api.delete(example)
        assert response.status_code == 403


class TestCampaignAsUser(TestCampaignAsProdMgr):
    """
    Test the API for the campaign entity
    with the user role.
    """

    @property
    def entity_api(self) -> CampaignAPI:
        mcm: McM = api.mcm_client(Roles.USER)
        return CampaignAPI(mcm)

    @property
    def higher_role_entity_api(self) -> CampaignAPI:
        mcm: McM = api.mcm_client(Roles.ADMINISTRATOR)
        return CampaignAPI(mcm)

    def test_create(self):
        # Not enough permissions.
        invalid_mockup = self.entity_api.mockup()
        invalid_mockup["prepid"] = "Run3Campaign#1"
        _, response = self.entity_api.create(invalid_mockup)
        assert response.status_code == 403

    def test_retrieve(self):
        example = self.higher_role_entity_api.example()
        retrieved = self.entity_api.retrieve(example)
        assert example == retrieved

    def test_update(self):
        # Not enough permissions.
        mockup = self.entity_api.mockup()
        _, response = self.entity_api.update(mockup)
        assert response.status_code == 403

    def test_delete(self):
        # Not enough permissions.
        example = self.entity_api.mockup()
        _, response = self.entity_api.delete(example)
        assert response.status_code == 403

    def test_cmssw_drivers(self):
        example = self.higher_role_entity_api.example()
        content, response = self.entity_api.cms_drivers(example)
        driver: str = content["results"][0]["default"]
        event_content = example["sequences"][0]["default"]["eventcontent"]
        event_content_param = ",".join(event_content)

        assert response.status_code == 200
        assert driver.startswith("cmsDriver.py")
        assert event_content_param in driver

        # The campaign doesn't exists
        mockup = self.entity_api.mockup()
        content, response = self.entity_api.cms_drivers(mockup)
        assert response.status_code == 200
        assert content["results"] == False

    def test_inspect(self):
        # Not enough permissions.
        example = self.higher_role_entity_api.example()
        _, response = self.entity_api.inspect(example)
        assert response.status_code == 403

    def test_status(self):
        # Not enough permissions.
        example = self.higher_role_entity_api.example()
        _, response = self.entity_api.status(example)
        assert response.status_code == 403
