"""
This module tests the API operations related with
the campaign entity.
"""

import uuid
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

from requests import Response
import pytest

import tests.campaign as campaign
from tests.api_tools import McM, Roles
from tests.base_test_tools import Entity, EntityTest, config


class CampaignAPI(Entity):
    """
    Implements a simple test API client focused
    only on the campaign operations.
    """

    def __init__(self, mcm: McM) -> None:
        mock_path: Path = files(campaign).joinpath("static/campaign.json")
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

    def cms_drivers(self, mockup: dict) -> tuple[dict, Response]:
        """
        Retrieves the cms-sw commands for a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/get_cmsDrivers/<string:campaign_id>

        Returns:
            tuple[dict, request.Response]: The cms-sw driver commands
                for each step to simulate and the HTTP response.
        """
        endpoint = f"restapi/campaigns/get_cmsDrivers/{mockup.get('prepid')}"
        http_res = self.mcm._get(endpoint)
        return http_res.json(), http_res

    def inspect(self, mockup: dict) -> tuple[dict, Response]:
        """
        Inspect all the requests in a given campaign.
        Related to test the endpoint:
            - restapi/campaigns/inspect/<string:campaign_id>

        Returns:
            tuple[str, request.Response]: The result of inspecting
                all the `request` linked to the `campaign`.
                This `inspect` process refers to synchronize the progress
                related to the `request` from ReqMgr2 (CMS' main request manager tool)
                to the McM application.
                
                Also, this returns the HTTP response object.
        """
        endpoint = f"restapi/campaigns/inspect/{mockup.get('prepid')}"
        http_res = self.mcm._get(endpoint)
        return http_res.text, http_res

    def toggle_status(self, mockup: dict) -> tuple[dict, Response]:
        """
        Toggles the status for a campaign.
        Related to test the endpoint:
            - restapi/campaigns/status/<string:campaign_id>

        Returns:
            tuple[dict, request.Response]: Result of the operation and description of error messages
                in case they happen. Format:
                - For sucessful execution: `{'results': True}`
                - In case of errors: `{'results': False, 'message': '<Description: str>`
                    - There are three common cases for the description:
                        - The campaign doesn't exists.
                        - Runtime exception when saving to the database.
                        - Any other exception.
                
                Also, this returns the HTTP response object.
        """
        endpoint = f"restapi/campaigns/status/{mockup.get('prepid')}"
        http_res = self.mcm._get(endpoint)
        return http_res.json(), http_res


class TestCampaign(EntityTest):
    """
    Test the campaign API.
    """

    @property
    def entity_api(self) -> CampaignAPI:
        mcm: McM = McM(config=config, role=Roles.ADMINISTRATOR)
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

    def test_delete(self):
        # The campaign exists
        example = self.entity_api.example()
        content, response = self.entity_api.delete(example)
        assert content["results"] == True
        assert response.status_code == 200

        # The campaign doesn't exists
        mockup = self.entity_api.mockup()
        content, response = self.entity_api.delete(mockup)
        assert content["results"] == False
        assert response.status_code == 200
        assert f"Cannot delete, {mockup['prepid']}" in content["message"]

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

    def test_inspect(self):
        # The campaign exists
        example = self.entity_api.example()
        content, response = self.entity_api.inspect(example)
        campaign_header: str = f"Starting campaign inspect of {example['prepid']}"
        campaign_footer: str = "Inspecting 0 requests on page 0"

        assert campaign_header in content
        assert campaign_footer in content
        assert response.status_code == 200

    def test_toggle_status(self):
        # Stop a valid campaign
        example = self.entity_api.example()
        content, response = self.entity_api.toggle_status(example)
        after_toggle = self.entity_api.retrieve(example)
        assert response.status_code == 200
        assert content["results"] == True
        assert after_toggle["status"] == "stopped"

        # Start an invalid campaign
        del after_toggle["cmssw_release"]
        self.entity_api.update(after_toggle)
        content, response = self.entity_api.toggle_status(example)
        assert response.status_code == 200
        assert content["results"] == False


class TestCampaignAsProdMgr(TestCampaign):
    """
    Test the API for the campaign entity impersonating
    a production manager.
    """

    @property
    def entity_api(self) -> CampaignAPI:
        mcm: McM = McM(config=config, role=Roles.PRODUCTION_MANAGER)
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
        mcm: McM = McM(config=config, role=Roles.USER)
        return CampaignAPI(mcm)

    @property
    def higher_role_entity_api(self) -> CampaignAPI:
        mcm: McM = McM(config=config, role=Roles.ADMINISTRATOR)
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

    def test_toggle_status(self):
        # Not enough permissions.
        example = self.higher_role_entity_api.example()
        _, response = self.entity_api.toggle_status(example)
        assert response.status_code == 403
