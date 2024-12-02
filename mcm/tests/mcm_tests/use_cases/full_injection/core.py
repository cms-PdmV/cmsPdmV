"""
This module provides some helper utilities
to create some campaigns, flows, chained campaigns, root requests,
chained requests and tickets so that tests can easily create
all the objects to simulate a full MC injection from scratch.
"""

import json
import random
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Union

from rest import McM
from rest.applications.mcm.resubmission import ChainRequestResubmitter
from rest.utils.logger import LoggerFactory

import mcm_tests.use_cases.full_injection as current_module
from mcm_tests.rest_api.api_tools import Environment


class MocksForInjection:
    """
    This class handles the creation of several mocks required for
    injection tests.
    """

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.cms_sw_version = "CMSSW_13_0_17"

        # The following era must be valid based on the cms-sw release
        # It could be available at: Configuration/Applications/python/cmsDriverOptions.py#L271
        self.era = "Run3"

        self._gs_root_campaign: Path = files(current_module).joinpath(
            "static/RunIII/gs_root_campaign.json"
        )
        self._root_request: Path = files(current_module).joinpath(
            "static/RunIII/root_request.json"
        )
        self._mccm_ticket: Path = files(current_module).joinpath(
            "static/RunIII/mccm_ticket.json"
        )
        self._dr_campaign: Path = files(current_module).joinpath(
            "static/RunIII/dr_campaign.json"
        )
        self._miniaod_campaign: Path = files(current_module).joinpath(
            "static/RunIII/miniaod_campaign.json"
        )
        self._nanoaod_campaign: Path = files(current_module).joinpath(
            "static/RunIII/nanoaod_campaign.json"
        )
        self._flow_to_dr: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_dr.json"
        )
        self._flow_to_miniaod: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_miniaod.json"
        )
        self._flow_to_nanoaod: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_nanoaod.json"
        )

    def _create_mock_campaign(self) -> dict:
        """
        This creates a mock root campaign to use in further steps.
        """
        with open(self._gs_root_campaign, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["status"] = "started"
        mock["prepid"] = f"Run3SystemTesting{random.randint(1, 9999)}BPixGS"
        mock["no_output"] = False  # For this use case, output must be kept.
        mock["sequences"][0]["default"]["era"] = self.era
        mock["cmssw_release"] = self.cms_sw_version
        mock["notes"] = (
            f"This campaign was created for testing purposes at: {datetime.now()}"
        )

        return mock

    def _create_dr_campaign(self) -> dict:
        """
        This creates a mock DR campaign to use in further steps.
        """
        with open(self._dr_campaign, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["status"] = "started"
        mock["prepid"] = f"Run3SystemTesting{random.randint(1, 9999)}BPixDRPremix"
        mock["no_output"] = False  # For this use case, output must be kept.

        # Set the "era" across all sequences
        for idx, _ in enumerate(mock["sequences"]):
            mock["sequences"][idx]["default"]["era"] = self.era

        mock["cmssw_release"] = self.cms_sw_version
        mock["notes"] = (
            f"This DR campaign was created for testing purposes at: {datetime.now()}"
        )

        return mock

    def _create_miniaod_campaign(self) -> dict:
        """
        This creates a mock MiniAOD campaign to use in further steps.
        """
        with open(self._miniaod_campaign, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["status"] = "started"
        mock["prepid"] = f"Run3SystemTesting{random.randint(1, 9999)}BPixMiniAODv4"
        mock["no_output"] = False  # For this use case, output must be kept.

        # Set the "era" across all sequences
        for idx, _ in enumerate(mock["sequences"]):
            mock["sequences"][idx]["default"]["era"] = self.era

        mock["cmssw_release"] = self.cms_sw_version
        mock["notes"] = (
            f"This MiniAOD campaign was created for testing purposes at: {datetime.now()}"
        )

        return mock

    def _create_nanoaod_campaign(self) -> dict:
        """
        This creates a mock NanoAOD campaign to use in further steps.
        """
        with open(self._miniaod_campaign, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["status"] = "started"
        mock["prepid"] = f"Run3SystemTesting{random.randint(1, 9999)}BPixNanoAODv12"
        mock["no_output"] = False  # For this use case, output must be kept.

        # Set the "era" across all sequences
        for idx, _ in enumerate(mock["sequences"]):
            mock["sequences"][idx]["default"]["era"] = self.era

        mock["cmssw_release"] = self.cms_sw_version
        mock["notes"] = (
            f"This NanoAOD campaign was created for testing purposes at: {datetime.now()}"
        )

        return mock

    def _create_mock_root_request(self, root_campaign: dict) -> dict:
        """
        This creates a mock root request to use in the test.

        Args:
            root_campaign: Root campaign to link this request with.
        """
        campaign_prepid = root_campaign["prepid"]
        with open(self._root_request, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["cmssw_release"] = self.cms_sw_version
        mock["sequences"][0]["era"] = self.era
        mock["keep_output"] = [True]  # For this use case, output must be kept.
        mock["prepid"] = f"PPD-{campaign_prepid}-{random.randint(1,99999):05}"
        mock["notes"] = (
            f"This root request was created for testing purposes at: {datetime.now()}"
        )
        mock["member_of_campaign"] = campaign_prepid

        return mock

    def _create_mock_mccm_ticket(
        self, chained_campaign: str, root_request: str
    ) -> dict:
        """
        This creates a mock MccM ticket to use in the test.

        Args:
            chained_campaign: ID of the chained campaign to use in the ticket.
            root_request: ID of the Root request to include in the ticket.
        """
        with open(self._mccm_ticket, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["chains"] = [chained_campaign]
        mock["prepid"] = f"PPD-2024Aug02-{random.randint(1,99999):05}"
        mock["requests"] = [root_request]

        return mock

    def _create_mock_flow_to_dr(
        self, initial_campaign: str, next_campaign: str
    ) -> dict:
        """
        This creates a mock flow to connect the root campaign and the DR one.

        Args:
            initial_campaign: Root campaign ID.
            next_campaign: DR campaign ID.
        """
        with open(self._flow_to_dr, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["prepid"] = f"flow{next_campaign}"  # Just to follow the convention
        mock["allowed_campaigns"] = [initial_campaign]
        mock["notes"] = (
            f"This flow from root campaign to DR was created for testing purposes at: {datetime.now()}"
        )
        mock["next_campaign"] = next_campaign
        mock["approval"] = (
            "tasksubmit"  # This enables to use the flow without any manual approval.
        )

        # INFO: Do not keep the output to avoid issues with Stats2 application.
        # Yes, this is a really highly-coupled behavior :'(

        # This is going to overwrite this attribute in both campaigns.
        mock["request_parameters"]["keep_output"] = [False, False]

        return mock

    def _create_mock_flow_to_miniaod(
        self, initial_campaign: str, next_campaign: str
    ) -> dict:
        """
        This creates a mock flow to connect the DR campaign and the MiniAOD one.

        Args:
            initial_campaign: DR campaign ID.
            next_campaign: MiniAOD campaign ID.
        """
        with open(self._flow_to_miniaod, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["prepid"] = f"flow{next_campaign}"  # Just to follow the convention
        mock["allowed_campaigns"] = [initial_campaign]
        mock["notes"] = (
            f"This flow from DR campaign to MiniAOD was created for testing purposes at: {datetime.now()}"
        )
        mock["next_campaign"] = next_campaign
        mock["approval"] = (
            "tasksubmit"  # This enables to use the flow without any manual approval.
        )
        mock["request_parameters"]["keep_output"] = [True]

        return mock

    def _create_mock_flow_to_nanoaod(
        self, initial_campaign: str, next_campaign: str
    ) -> dict:
        """
        This creates a mock flow to connect the DR campaign and the MiniAOD one.

        Args:
            initial_campaign: MiniAOD campaign ID.
            next_campaign: NanoAOD campaign ID.
        """
        with open(self._flow_to_nanoaod, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["prepid"] = f"flow{next_campaign}"  # Just to follow the convention
        mock["allowed_campaigns"] = [initial_campaign]
        mock["notes"] = (
            f"This flow from a MiniAOD campaign to NanoAOD was created for testing purposes at: {datetime.now()}"
        )
        mock["next_campaign"] = next_campaign
        mock["approval"] = (
            "tasksubmit"  # This enables to use the flow without any manual approval.
        )
        mock["request_parameters"]["keep_output"] = [True]

        return mock

    def mock(self) -> dict:
        """
        Creates all the mocks required for the test case
        """
        campaign = self._create_mock_campaign()
        root_request = self._create_mock_root_request(root_campaign=campaign)
        dr_campaign = self._create_dr_campaign()
        miniaod_campaign = self._create_miniaod_campaign()
        nanoaod_campaign = self._create_nanoaod_campaign()

        return {
            "campaign": campaign,
            "root_request": root_request,
            "dr_campaign": dr_campaign,
            "miniaod_campaign": miniaod_campaign,
            "nanoaod_campaign": nanoaod_campaign,
        }


class MocksForRun2Injection:
    """
    This class creates several objects to submit
    a long chained request with other steps rather than
    the usual like SIM, DIGI, HLT and RECO.

    For creating most of the elements, it uses as template
    the chained campaign:

    - chain_RunIISummer19UL16wmLHEGEN_flowRunIISummer19UL16SIM_flowRunIISummer19UL16DIGIEpsilonPU_
        flowRunIISummer19UL16HLT_flowRunIISummer19UL16RECO_flowRunIISummer19UL16MiniAOD_flowRunIISummer19UL16JMENtuplesNanoAOD
    """

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.cms_sw_version = "CMSSW_10_6_12"
        self.era = "Run2_2016"

        # Campaigns
        self._root_campaign: Path = files(current_module).joinpath(
            "static/RunII/root_campaign.json"
        )
        self._sim_campaign: Path = files(current_module).joinpath(
            "static/RunII/sim_campaign.json"
        )
        self._digi_campaign: Path = files(current_module).joinpath(
            "static/RunII/digi_campaign.json"
        )
        self._hlt_campaign: Path = files(current_module).joinpath(
            "static/RunII/hlt_campaign.json"
        )
        self._reco_campaign: Path = files(current_module).joinpath(
            "static/RunII/reco_campaign.json"
        )
        self._miniaod_campaign: Path = files(current_module).joinpath(
            "static/RunII/miniaod_campaign.json"
        )
        self._nanoaod_campaign: Path = files(current_module).joinpath(
            "static/RunII/nanoaod_campaign.json"
        )

        # MccM ticket
        self._mccm_ticket: Path = files(current_module).joinpath(
            "static/RunIII/mccm_ticket.json"
        )

        # Flows
        self._flow_to_sim: Path = files(current_module).joinpath(
            "static/RunII/flow_to_sim.json"
        )
        self._flow_to_digi: Path = files(current_module).joinpath(
            "static/RunII/flow_to_digi.json"
        )
        self._flow_to_hlt: Path = files(current_module).joinpath(
            "static/RunII/flow_to_hlt.json"
        )
        self._flow_to_reco: Path = files(current_module).joinpath(
            "static/RunII/flow_to_reco.json"
        )
        self._flow_to_miniaod: Path = files(current_module).joinpath(
            "static/RunII/flow_to_miniaod.json"
        )
        self._flow_to_nanoaod: Path = files(current_module).joinpath(
            "static/RunII/flow_to_nanoaod.json"
        )

        # Root request
        self._root_request: Path = files(current_module).joinpath(
            "static/RunII/root_request.json"
        )

    @classmethod
    def _create_mock_campaign(
        cls,
        mock_path: Path,
        cms_sw_version: str,
        era: str,
        prepid_pattern: str,
        placeholder: str,
        no_output: bool,
    ) -> dict:
        """
        This creates a mock campaign to use in further steps.

        Args:
            mock_path: Path to the mock schema for the campaign.
            cms_sw_version: CMSSW release for the campaign, e.g: CMSSW_10_6_12
            era: Campaign's era, e.g: Run3
            prepid_pattern: PrepID to set for the campaign, e.g: RunIISummer19UL16wmLHEGEN
            placeholder: A placeholder to replace with a random number to avoid document colissions.
            no_ouput: Indicate if the campaign keeps or not output for its sequence.

        Returns:
            Campaign mock
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["status"] = "started"
        mock["prepid"] = prepid_pattern.replace(
            placeholder, str(random.randint(1, 99999))
        )  # Make it unique!
        mock["no_output"] = no_output

        # Set the "era" across all sequences
        for idx, _ in enumerate(mock["sequences"]):
            mock["sequences"][idx]["default"]["era"] = era

        mock["cmssw_release"] = cms_sw_version
        mock["notes"] = (
            f"This campaign was created for testing purposes at: {datetime.now()}"
        )
        return mock

    @classmethod
    def _create_mock_flow(
        cls,
        mock_path: Path,
        initial_campaign: str,
        next_campaign: str,
        keeps_output: Union[list[bool], None] = None,
    ) -> dict:
        """
        This creates a mock flow to use to link two campaigns:
        the `initial_campaign` and the `next_campaign`.

        Args:
            mock_path: Path to the mock schema for the flow.
            initial_campaign: Initial campaign to link.
            next_campaign: Next campaign to link.
            keeps_output: Indicates if the campaigns should keep output.

        Returns:
            Flow mock
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["prepid"] = f"flow{next_campaign}"  # Just to follow the convention
        mock["allowed_campaigns"] = [initial_campaign]
        mock["notes"] = (
            f"This flow was created for testing purposes at: {datetime.now()}"
        )
        mock["next_campaign"] = next_campaign
        mock["approval"] = (
            "tasksubmit"  # This enables to use the flow without any manual approval.
        )
        if keeps_output:
            mock["request_parameters"]["keep_output"] = keeps_output

        return mock

    @classmethod
    def _create_mock_root_request(
        cls,
        mock_path: Path,
        cms_sw_version: str,
        era: str,
        root_campaign_prepid: str,
        keeps_output: bool,
    ) -> dict:
        """
        This creates a mock root request.

        Args:
            mock_path: Path to the mock schema for the root request.
            cms_sw_version: CMSSW release to use for the request.
            era: Campaign era.
            root_campaign_prepid: Campaign ID for the root campaign in the
                chained campaign.
            keeps_output: Indicates if the request creates and keeps its
                output dataset.

        Returns:
            Root request mock
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["cmssw_release"] = cms_sw_version
        mock["sequences"][0]["era"] = era
        mock["keep_output"] = [keeps_output]  # For this use case, output must be kept.
        mock["prepid"] = f"PPD-{root_campaign_prepid}-{random.randint(1,99999):05}"
        mock["notes"] = (
            f"This request was created for testing purposes at: {datetime.now()}"
        )
        mock["member_of_campaign"] = root_campaign_prepid
        return mock

    @classmethod
    def _create_mock_mccm_ticket(
        cls, mock_path: Path, chained_campaign_prepid: str, root_request_prepid: str
    ) -> dict:
        """
        This creates a mock MccM ticket to use in the test.

        Args:
            mock_path: Path to the mock schema for the root request.
            chained_campaign_prepid: ID of the chained campaign to use in the ticket.
            root_request_prepid: ID of the Root request to include in the ticket.
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["chains"] = [chained_campaign_prepid]
        mock["prepid"] = f"PPD-2024Dec02-{random.randint(1,99999):05}"
        mock["requests"] = [root_request_prepid]
        return mock

    def mock(self) -> dict:
        """
        Creates all the mocks required for the test case
        """
        # Campaigns
        root_campaign = self._create_mock_campaign(
            mock_path=self._root_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$wmLHEGEN",
            placeholder="$",
            no_output=True,
        )
        sim_campaign = self._create_mock_campaign(
            mock_path=self._sim_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$SIM",
            placeholder="$",
            no_output=True,
        )
        digi_campaign = self._create_mock_campaign(
            mock_path=self._digi_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$DIGI",
            placeholder="$",
            no_output=True,
        )
        hlt_campaign = self._create_mock_campaign(
            mock_path=self._hlt_campaign,
            cms_sw_version="CMSSW_8_0_33_UL", # This requires an older release!
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$HLT",
            placeholder="$",
            no_output=True,
        )
        reco_campaign = self._create_mock_campaign(
            mock_path=self._reco_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$RECO",
            placeholder="$",
            no_output=True,
        )
        miniaod_campaign = self._create_mock_campaign(
            mock_path=self._miniaod_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$MiniAOD",
            placeholder="$",
            no_output=True,
        )
        nanoaod_campaign = self._create_mock_campaign(
            mock_path=self._nanoaod_campaign,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$NanoAOD",
            placeholder="$",
            no_output=True,
        )
        root_request = self._create_mock_root_request(
            mock_path=self._root_request,
            cms_sw_version=self.cms_sw_version,
            era=self.era,
            root_campaign_prepid=root_campaign["prepid"],
            keeps_output=True,
        )

        return {
            "root_campaign": root_campaign,
            "sim_campaign": sim_campaign,
            "digi_campaign": digi_campaign,
            "hlt_campaign": hlt_campaign,
            "reco_campaign": reco_campaign,
            "miniaod_campaign": miniaod_campaign,
            "nanoaod_campaign": nanoaod_campaign,
            "root_request": root_request,
        }


class InjectRootRequest(MocksForInjection):
    """
    This class handles the creation of all the elements
    required to inject a root request from scratch. Creating
    a campaign, root request, a MccM ticket, and reserving the
    chained request to inject it to ReqMgr2.

    For creating most of the elements, it uses as template
    the chained campaign:
    - chain_Run3Summer23BPixGS_flowRun3Summer23BPixDRPremix_flowRun3Summer23BPixMiniAODv4_flowRun3Summer23BPixNanoAODv12
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        super().__init__()
        self.logger = LoggerFactory.getLogger("mcm_tests.InjectRootRequest")
        self.mcm = mcm
        self.environment = environment
        self.resubmitter = ChainRequestResubmitter(mcm=mcm)

    def create(self, mocks: dict) -> dict:
        """
        Creates the objects in the McM application
        using the mocks.
        """
        campaign = mocks["campaign"]
        root_request = mocks["root_request"]

        # Create the objects
        campaign_creation = self.mcm.put(object_type="campaigns", object_data=campaign)
        if not campaign_creation or not campaign_creation.get("results"):
            print("Campaign creation: ", campaign_creation)
            raise RuntimeError("Unable to create the root campaign")

        request_creation = self.mcm.put(
            object_type="requests", object_data=root_request
        )
        if not request_creation or not request_creation.get("results"):
            raise RuntimeError("Unable to create the root request")

        # Include the correct id for the root request.
        # The McM application overwrites this value using a sequence generator,
        # so the prepid suffix differs from the mock one.
        root_request_prepid = request_creation["prepid"]

        # Include the correct root request id in the ticket.
        mccm_ticket = self._create_mock_mccm_ticket(
            chained_campaign=f"chain_{campaign['prepid']}",
            root_request=root_request_prepid,
        )
        ticket_creation = self.mcm.put(object_type="mccms", object_data=mccm_ticket)
        if not ticket_creation or not ticket_creation.get("results"):
            raise RuntimeError("Unable to create the MccM ticket")

        # Retrieve the objects
        campaign_created = self.mcm.get(
            object_type="campaigns", object_id=campaign["prepid"]
        )
        root_request_created = self.mcm.get(
            object_type="requests", object_id=request_creation["prepid"]
        )
        mccm_ticket_created = self.mcm.get(
            object_type="mccms", object_id=ticket_creation["prepid"]
        )

        # Store as entities
        entities = {
            "campaign": campaign_created,
            "root_request": root_request_created,
            "mccm_ticket": mccm_ticket_created,
        }

        for type, value in entities.items():
            if isinstance(value, dict) and value.get("prepid"):
                continue
            else:
                raise ValueError(f"{type} was not properly created")

        self.entities = entities
        return self.entities

    def inject(self) -> None:
        """
        Performs the steps required to achieve the root
        request injection via tickets.
        """
        root_request = self.entities["root_request"]
        mccm_ticket = self.entities["mccm_ticket"]
        campaign = self.entities["campaign"]

        # Skip the validation for the root request.
        # FIXME: There is an error on McM's web server side.
        # The application's cache for the `settings` database does not store
        # the latest `_rev` ID. The last triggers a `revision clash` error in the
        # database.

        # To skip this, just take the document directly from the database
        database_url = self.environment.mcm_couchdb_url
        document_url = "settings/validation_bypass"
        validation_bypass = self.mcm.session.get(url=database_url + document_url).json()
        self.logger.info(
            "Including root request (%s) in the validation bypass list",
            root_request["prepid"],
        )
        if not validation_bypass:
            raise ValueError("Unable to retrieve the validation bypass list")

        validation_bypass["value"] += [root_request["prepid"]]
        update_result = self.mcm.update(
            object_type="settings", object_data=validation_bypass
        )
        if not update_result or not update_result.get("results"):
            raise RuntimeError(
                "Unable to include the request in the validation bypass list"
            )

        # Approve the request until approve/approved
        self.logger.info(
            "Approving root request (%s) until approve/approved", root_request["prepid"]
        )
        self.resubmitter._approve_request_until(
            request_prepid=root_request["prepid"], approval="approve", status="approved"
        )

        # Reserve the chained request in the ticket.
        self.logger.info(
            "Reserving chain requests for ticket (%s)", mccm_ticket["prepid"]
        )
        reserve_result = self.mcm._get(
            f"restapi/mccms/generate/{mccm_ticket['prepid']}?reserve=true&limit={campaign['prepid']}"
        )
        if not reserve_result or not reserve_result.get("results"):
            print("Error reserving chained requests: ", reserve_result)
            raise RuntimeError(
                "Unable to generate the chained request in the MccM ticket"
            )

        # Pick the root request and inject it
        self.logger.info(
            "Injecting chained request by moving the root request (%s) to submit/submitted",
            root_request["prepid"],
        )
        self.resubmitter._approve_request_until(
            request_prepid=root_request["prepid"], approval="submit", status="submitted"
        )

    def cleanup(self) -> None:
        """
        Deletes most of the created resources.
        """
        if not self.entities:
            raise ValueError("No resource was created in the McM application!")

        root_request = self.entities["root_request"]
        campaign = self.entities["campaign"]

        # Invalidate the workflow in ReqMgr2, remove the chained request
        # and the root request.
        self.resubmitter._invalidator.invalidate_delete_cascade_requests(
            requests_prepid=[root_request["prepid"]], remove_root=True
        )

        # Ideally, we should also delete the ticket.
        # But it is not possible unless changes are perform at database level.
        # So, let's skip this.

        # Delete the chained campaign and the campaign
        chained_campaign = f"chain_{campaign['prepid']}"
        self.mcm.delete(object_type="chained_campaigns", object_id=chained_campaign)
        self.mcm.delete(object_type="campaigns", object_id=campaign["prepid"])


class InjectToNanoAOD(MocksForInjection):
    """
    This class handles the creation of all the elements
    required to inject several MC samples up to the NanoAOD data tier root from scratch.
    Creating campaigns, flows, chained campaigns, root requests, a MccM ticket and reserving the
    chained request to inject it to ReqMgr2.

    For creating most of the elements, it uses the following
    chained campaign as a template:
    - chain_Run3Summer23BPixGS_flowRun3Summer23BPixDRPremix_flowRun3Summer23BPixMiniAODv4_flowRun3Summer23BPixNanoAODv12
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        super().__init__()
        self.logger = LoggerFactory.getLogger("mcm_tests.InjectToNanoAOD")
        self.mcm = mcm
        self.environment = environment
        self.resubmitter = ChainRequestResubmitter(mcm=mcm)

    def _create_chained_campaign_to_nanoaod(self, entities: dict) -> dict:
        """
        Creates a chained campaign that integrates all the steps
        to produce samples from the root campaign to the NanoAOD campaign
        using the campaigns and flows created in previous steps.

        Args:
            entities: An object that includes all the data required to perform this step.
        """
        # Campaigns
        campaign = entities["campaign"]["prepid"]
        dr_campaign = entities["dr_campaign"]["prepid"]
        miniaod_campaign = entities["miniaod_campaign"]["prepid"]
        nanoaod_campaign = entities["nanoaod_campaign"]["prepid"]

        # Flows
        flow_to_dr = entities["flow_to_dr"]["prepid"]
        flow_to_miniaod = entities["flow_to_miniaod"]["prepid"]
        flow_to_nanoaod = entities["flow_to_nanoaod"]["prepid"]

        # Create the chained campaign
        chained_campaign_mock = {
            "campaigns": [
                [campaign, None],
                [dr_campaign, flow_to_dr],
                [miniaod_campaign, flow_to_miniaod],
                [nanoaod_campaign, flow_to_nanoaod],
            ]
        }

        chained_campaign_creation = self.mcm.put(
            object_type="chained_campaigns", object_data=chained_campaign_mock
        )
        if not chained_campaign_creation or not chained_campaign_creation.get(
            "results"
        ):
            raise RuntimeError(f"Unable to create the chained campaign")

        # Update some parameters
        chained_campaign_id = chained_campaign_creation["prepid"]

        chained_campaign = self.mcm.get(
            object_type="chained_campaigns", object_id=chained_campaign_id
        )
        chained_campaign["action_parameters"][
            "block_number"
        ] = 1  # Give the highest priority for processing
        chained_campaign["action_parameters"][
            "flag"
        ] = True  # Enable the chained campaign
        chained_campaign_update = self.mcm.update(
            object_type="chained_campaigns", object_data=chained_campaign
        )
        if not chained_campaign_update or not chained_campaign_update.get("results"):
            raise RuntimeError("Unable to update the chained campaign attributes")

        return self.mcm.get(
            object_type="chained_campaigns", object_id=chained_campaign_id
        )

    def create(self, mocks: dict) -> dict:
        """
        Creates the objects in the McM application
        using the mocks.
        """
        entities = {}
        root_request = mocks["root_request"]

        # Create the objects
        campaigns_to_create = [
            "campaign",
            "dr_campaign",
            "miniaod_campaign",
            "nanoaod_campaign",
        ]
        for campaign in campaigns_to_create:
            campaign_mock = mocks[campaign]

            campaign_creation = self.mcm.put(
                object_type="campaigns", object_data=campaign_mock
            )
            if not campaign_creation or not campaign_creation.get("results"):
                raise RuntimeError(
                    f"Unable to create campaign ({campaign}): ", campaign_creation
                )

            # Save the created document
            entities[campaign] = self.mcm.get(
                object_type="campaigns", object_id=campaign_mock["prepid"]
            )

        request_creation = self.mcm.put(
            object_type="requests", object_data=root_request
        )
        if not request_creation or not request_creation.get("results"):
            raise RuntimeError("Unable to create the root request")

        # Root request ID assigned by the McM application.
        root_request_prepid = request_creation["prepid"]
        entities["root_request"] = self.mcm.get(
            object_type="requests", object_id=root_request_prepid
        )

        # Create the flows
        flows_to_create = {
            "flow_to_dr": (
                entities["campaign"]["prepid"],
                entities["dr_campaign"]["prepid"],
                self._create_mock_flow_to_dr,
            ),
            "flow_to_miniaod": (
                entities["dr_campaign"]["prepid"],
                entities["miniaod_campaign"]["prepid"],
                self._create_mock_flow_to_miniaod,
            ),
            "flow_to_nanoaod": (
                entities["miniaod_campaign"]["prepid"],
                entities["nanoaod_campaign"]["prepid"],
                self._create_mock_flow_to_nanoaod,
            ),
        }
        for flow_to_create, range_campaign in flows_to_create.items():
            initial_campaign, next_campaign, mock_function = range_campaign
            mock = mock_function(
                initial_campaign=initial_campaign, next_campaign=next_campaign
            )

            flow_creation = self.mcm.put(object_type="flows", object_data=mock)
            if not flow_creation or not flow_creation.get("results"):
                raise RuntimeError(
                    f"Unable to create flow ({flow_to_create}): ", flow_creation
                )

            # Save the created document
            entities[flow_to_create] = self.mcm.get(
                object_type="flows", object_id=mock["prepid"]
            )

        # Create the chained campaign
        entities["chained_campaign"] = self._create_chained_campaign_to_nanoaod(
            entities=entities
        )

        # Create the ticket
        # Include the correct root request id in the ticket.
        mccm_ticket = self._create_mock_mccm_ticket(
            chained_campaign=entities["chained_campaign"]["prepid"],
            root_request=root_request_prepid,
        )
        ticket_creation = self.mcm.put(object_type="mccms", object_data=mccm_ticket)
        if not ticket_creation or not ticket_creation.get("results"):
            raise RuntimeError("Unable to create the MccM ticket")

        entities["mccm_ticket"] = self.mcm.get(
            object_type="mccms", object_id=ticket_creation["prepid"]
        )

        for type, value in entities.items():
            if isinstance(value, dict) and value.get("prepid"):
                continue
            else:
                raise ValueError(f"{type} was not properly created")

        self.entities = entities
        return self.entities

    def inject(self) -> None:
        """
        Performs the necessary steps to get the injection of all
        the requests related to the chained campaign through tickets.
        """
        root_request = self.entities["root_request"]
        mccm_ticket = self.entities["mccm_ticket"]

        # Skip the validation for the root request.
        # FIXME: There is an error on McM's web server side.
        # The application's cache for the `settings` database does not store
        # the latest `_rev` ID. The last triggers a `revision clash` error in the
        # database.

        # To skip this, just take the document directly from the database
        database_url = self.environment.mcm_couchdb_url
        document_url = "settings/validation_bypass"
        validation_bypass = self.mcm.session.get(url=database_url + document_url).json()
        self.logger.info(
            "Including root request (%s) in the validation bypass list",
            root_request["prepid"],
        )
        if not validation_bypass:
            raise ValueError("Unable to retrieve the validation bypass list")

        validation_bypass["value"] += [root_request["prepid"]]
        update_result = self.mcm.update(
            object_type="settings", object_data=validation_bypass
        )
        if not update_result or not update_result.get("results"):
            raise RuntimeError(
                "Unable to include the request in the validation bypass list"
            )

        # Reserve the chained request in the ticket.
        self.logger.info(
            "Reserving chain requests for ticket (%s)", mccm_ticket["prepid"]
        )
        reserve_up_to = self.entities["chained_campaign"]["prepid"]
        reserve_result = self.mcm._get(
            f"restapi/mccms/generate/{mccm_ticket['prepid']}?reserve=true&limit={reserve_up_to}"
        )
        if not reserve_result or not reserve_result.get("results"):
            print("Error reserving chained requests: ", reserve_result)
            raise RuntimeError(
                "Unable to generate the chained request in the MccM ticket"
            )

        # Pick all the request in the chained request linked to the ticket
        # set them to approve/approved
        ticket_data = self.mcm.get(object_type="mccms", object_id=mccm_ticket["prepid"])
        chained_requests_prepids: list[str] = list(ticket_data["generated_chains"])
        for chr in chained_requests_prepids:
            chained_request_data = self.mcm.get(
                object_type="chained_requests", object_id=chr
            )
            requests_in_chain: list[str] = chained_request_data["chain"]
            for request in requests_in_chain:
                # Approve the request until approve/approved
                self.logger.info(
                    "Approving request (%s) until approve/approved", request
                )
                self.resubmitter._approve_request_until(
                    request_prepid=request, approval="approve", status="approved"
                )

        # Let the magic happen :)
        # Pick the root request and inject it
        self.logger.info(
            "Injecting chained request by moving the root request (%s) to submit/submitted",
            root_request["prepid"],
        )
        self.resubmitter._approve_request_until(
            request_prepid=root_request["prepid"], approval="submit", status="submitted"
        )

    def cleanup(self) -> None:
        """
        Deletes most of the created resources.
        """
        if not self.entities:
            raise ValueError("No resources were created in the McM application!")

        # Invalidate the workflow in ReqMgr2, remove the chained request
        # and the root request.
        root_request = self.entities["root_request"]
        self.resubmitter._invalidator.invalidate_delete_cascade_requests(
            requests_prepid=[root_request["prepid"]], remove_root=True
        )

        # Ideally, we should also delete the ticket.
        # But it is not possible unless changes are perform at database level.
        # So, let's skip this.

        # Delete the chained campaign and the flows
        # INFO: Note that the order is strict!
        resources = [
            ("campaigns", "campaign"),
            ("campaigns", "dr_campaign"),
            ("flows", "flow_to_dr"),
            ("campaigns", "miniaod_campaign"),
            ("flows", "flow_to_miniaod"),
            ("campaigns", "nanoaod_campaign"),
            ("flows", "flow_to_nanoaod"),
            ("chained_campaigns", "chained_campaign"),
        ]
        for res in reversed(resources):
            resource_type, resource_key = res
            object_id = self.entities[resource_key]["prepid"]
            self.mcm.delete(object_type=resource_type, object_id=object_id)


class InjectRun2Requests(MocksForRun2Injection):
    """
    This class creates and injects a chained request including unusual
    steps from the most common sequence: GEN > DR > MiniAOD > NanoAOD.
    Its elements, campaigns and flows are based on the following chained
    campaign.

    - chain_RunIISummer19UL16wmLHEGEN_flowRunIISummer19UL16SIM_flowRunIISummer19UL16DIGIEpsilonPU_
        flowRunIISummer19UL16HLT_flowRunIISummer19UL16RECO_flowRunIISummer19UL16MiniAOD_flowRunIISummer19UL16JMENtuplesNanoAOD
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        super().__init__()
        self.logger = LoggerFactory.getLogger(f"mcm_tests.{self.__class__.__name__}")
        self.mcm = mcm
        self.environment = environment
        self.resubmitter = ChainRequestResubmitter(mcm=mcm)

    def _create_chained_campaign_to_nanoaod(self, entities: dict) -> dict:
        """
        Creates a chained campaign that integrates all the steps
        to produce samples from the root campaign to the NanoAOD campaign
        using the campaigns and flows created in previous steps.

        Args:
            entities: An object that includes all campaigns and flows required.
        """
        # Campaigns
        root_campaign = entities["root_campaign"]["prepid"]
        sim_campaign = entities["sim_campaign"]["prepid"]
        digi_campaign = entities["digi_campaign"]["prepid"]
        hlt_campaign = entities["hlt_campaign"]["prepid"]
        reco_campaign = entities["reco_campaign"]["prepid"]
        miniaod_campaign = entities["miniaod_campaign"]["prepid"]
        nanoaod_campaign = entities["nanoaod_campaign"]["prepid"]

        # Flows
        flow_to_sim = entities["flow_to_sim"]["prepid"]
        flow_to_digi = entities["flow_to_digi"]["prepid"]
        flow_to_hlt = entities["flow_to_hlt"]["prepid"]
        flow_to_reco = entities["flow_to_reco"]["prepid"]
        flow_to_miniaod = entities["flow_to_miniaod"]["prepid"]
        flow_to_nanoaod = entities["flow_to_nanoaod"]["prepid"]

        # Create the chained campaign
        # INFO: Refactor this to always receive directly the schema!
        chained_campaign_mock = {
            "campaigns": [
                [root_campaign, None],
                [sim_campaign, flow_to_sim],
                [digi_campaign, flow_to_digi],
                [hlt_campaign, flow_to_hlt],
                [reco_campaign, flow_to_reco],
                [miniaod_campaign, flow_to_miniaod],
                [nanoaod_campaign, flow_to_nanoaod],
            ],
            "do_not_check_cmssw_versions": True,
        }

        chained_campaign_creation = self.mcm.put(
            object_type="chained_campaigns", object_data=chained_campaign_mock
        )
        if not chained_campaign_creation or not chained_campaign_creation.get(
            "results"
        ):
            raise RuntimeError(f"Unable to create the chained campaign")

        # Update some parameters
        chained_campaign_id = chained_campaign_creation["prepid"]

        chained_campaign = self.mcm.get(
            object_type="chained_campaigns", object_id=chained_campaign_id
        )
        chained_campaign["action_parameters"][
            "block_number"
        ] = 1  # Give the highest priority for processing
        chained_campaign["action_parameters"][
            "flag"
        ] = True  # Enable the chained campaign
        chained_campaign_update = self.mcm.update(
            object_type="chained_campaigns", object_data=chained_campaign
        )
        if not chained_campaign_update or not chained_campaign_update.get("results"):
            raise RuntimeError("Unable to update the chained campaign attributes")

        return self.mcm.get(
            object_type="chained_campaigns", object_id=chained_campaign_id
        )

    def create(self, mocks: dict) -> dict:
        """
        Creates the objects in the McM application
        using the mocks.
        """
        entities = {}
        root_request = mocks["root_request"]

        # Create the campaigns
        campaigns_to_create = [
            "root_campaign",
            "sim_campaign",
            "digi_campaign",
            "hlt_campaign",
            "reco_campaign",
            "miniaod_campaign",
            "nanoaod_campaign",
        ]
        for campaign in campaigns_to_create:
            campaign_mock = mocks[campaign]
            campaign_creation = self.mcm.put(
                object_type="campaigns", object_data=campaign_mock
            )
            if not campaign_creation or not campaign_creation.get("results"):
                raise RuntimeError(
                    f"Unable to create campaign ({campaign}): ", campaign_creation
                )

            # Save the created document
            entities[campaign] = self.mcm.get(
                object_type="campaigns", object_id=campaign_mock["prepid"]
            )

        # Create the root request
        request_creation = self.mcm.put(
            object_type="requests", object_data=root_request
        )
        if not request_creation or not request_creation.get("results"):
            raise RuntimeError("Unable to create the root request")

        # Root request ID assigned by the McM application.
        root_request_prepid = request_creation["prepid"]
        entities["root_request"] = self.mcm.get(
            object_type="requests", object_id=root_request_prepid
        )

        # Create the flows
        flow_to_sim = self._create_mock_flow(
            mock_path=self._flow_to_sim,
            initial_campaign=mocks["root_campaign"]["prepid"],
            next_campaign=mocks["sim_campaign"]["prepid"],
        )
        flow_to_digi = self._create_mock_flow(
            mock_path=self._flow_to_digi,
            initial_campaign=mocks["sim_campaign"]["prepid"],
            next_campaign=mocks["digi_campaign"]["prepid"],
            keeps_output=[False],
        )
        flow_to_hlt = self._create_mock_flow(
            mock_path=self._flow_to_hlt,
            initial_campaign=mocks["digi_campaign"]["prepid"],
            next_campaign=mocks["hlt_campaign"]["prepid"],
        )
        flow_to_reco = self._create_mock_flow(
            mock_path=self._flow_to_reco,
            initial_campaign=mocks["hlt_campaign"]["prepid"],
            next_campaign=mocks["reco_campaign"]["prepid"],
        )
        flow_to_miniaod = self._create_mock_flow(
            mock_path=self._flow_to_miniaod,
            initial_campaign=mocks["reco_campaign"]["prepid"],
            next_campaign=mocks["miniaod_campaign"]["prepid"],
            keeps_output=[True]
        )
        flow_to_nanoaod = self._create_mock_flow(
            mock_path=self._flow_to_miniaod,
            initial_campaign=mocks["miniaod_campaign"]["prepid"],
            next_campaign=mocks["nanoaod_campaign"]["prepid"],
            keeps_output=[True]
        )
        flows_to_create = {
            "flow_to_sim": flow_to_sim,
            "flow_to_digi": flow_to_digi,
            "flow_to_hlt": flow_to_hlt,
            "flow_to_reco": flow_to_reco,
            "flow_to_miniaod": flow_to_miniaod,
            "flow_to_nanoaod": flow_to_nanoaod,
        }
        for flow_name, flow_object in flows_to_create.items():
            flow_creation = self.mcm.put(object_type="flows", object_data=flow_object)
            if not flow_creation or not flow_creation.get("results"):
                raise RuntimeError(
                    f"Unable to create flow ({flow_name}): ", flow_creation
                )

            # Save the created document
            entities[flow_name] = self.mcm.get(
                object_type="flows", object_id=flow_object["prepid"]
            )

        # Create the chained campaign
        entities["chained_campaign"] = self._create_chained_campaign_to_nanoaod(
            entities=entities
        )

        # Create the ticket
        # Include the correct root request id in the ticket.
        mccm_ticket = self._create_mock_mccm_ticket(
            mock_path=self._mccm_ticket,
            chained_campaign_prepid=entities["chained_campaign"]["prepid"],
            root_request_prepid=root_request_prepid,
        )
        ticket_creation = self.mcm.put(object_type="mccms", object_data=mccm_ticket)
        if not ticket_creation or not ticket_creation.get("results"):
            raise RuntimeError("Unable to create the MccM ticket")

        entities["mccm_ticket"] = self.mcm.get(
            object_type="mccms", object_id=ticket_creation["prepid"]
        )

        for type, value in entities.items():
            if isinstance(value, dict) and value.get("prepid"):
                continue
            else:
                raise ValueError(f"{type} was not properly created")

        self.entities = entities
        return self.entities

    def inject(self) -> None:
        """
        Performs the necessary steps to get the injection of all
        the requests related to the chained campaign through tickets.
        """
        root_request = self.entities["root_request"]
        mccm_ticket = self.entities["mccm_ticket"]

        # Skip the validation for the root request.
        # FIXME: There is an error on McM's web server side.
        # The application's cache for the `settings` database does not store
        # the latest `_rev` ID. The last triggers a `revision clash` error in the
        # database.

        # To skip this, just take the document directly from the database
        database_url = self.environment.mcm_couchdb_url
        document_url = "settings/validation_bypass"
        validation_bypass = self.mcm.session.get(url=database_url + document_url).json()
        self.logger.info(
            "Including root request (%s) in the validation bypass list",
            root_request["prepid"],
        )
        if not validation_bypass:
            raise ValueError("Unable to retrieve the validation bypass list")

        validation_bypass["value"] += [root_request["prepid"]]
        update_result = self.mcm.update(
            object_type="settings", object_data=validation_bypass
        )
        if not update_result or not update_result.get("results"):
            raise RuntimeError(
                "Unable to include the request in the validation bypass list"
            )

        # Reserve the chained request in the ticket.
        self.logger.info(
            "Reserving chain requests for ticket (%s)", mccm_ticket["prepid"]
        )
        reserve_up_to = self.entities["chained_campaign"]["prepid"]
        reserve_result = self.mcm._get(
            f"restapi/mccms/generate/{mccm_ticket['prepid']}?reserve=true&limit={reserve_up_to}"
        )
        if not reserve_result or not reserve_result.get("results"):
            print("Error reserving chained requests: ", reserve_result)
            raise RuntimeError(
                "Unable to generate the chained request in the MccM ticket"
            )

        # Pick all the request in the chained request linked to the ticket
        # set them to approve/approved
        ticket_data = self.mcm.get(object_type="mccms", object_id=mccm_ticket["prepid"])
        chained_requests_prepids: list[str] = list(ticket_data["generated_chains"])
        for chr in chained_requests_prepids:
            chained_request_data = self.mcm.get(
                object_type="chained_requests", object_id=chr
            )
            requests_in_chain: list[str] = chained_request_data["chain"]
            for request in requests_in_chain:
                # Approve the request until approve/approved
                self.logger.info(
                    "Approving request (%s) until approve/approved", request
                )
                self.resubmitter._approve_request_until(
                    request_prepid=request, approval="approve", status="approved"
                )

        # Let the magic happen :)
        # Pick the root request and inject it
        self.logger.info(
            "Injecting chained request by moving the root request (%s) to submit/submitted",
            root_request["prepid"],
        )
        self.resubmitter._approve_request_until(
            request_prepid=root_request["prepid"], approval="submit", status="submitted"
        )

    def cleanup(self) -> None:
        """
        Deletes most of the created resources.
        """
        if not self.entities:
            raise ValueError("No resources were created in the McM application!")

        # Invalidate the workflow in ReqMgr2, remove the chained request
        # and the root request.
        root_request = self.entities["root_request"]
        self.resubmitter._invalidator.invalidate_delete_cascade_requests(
            requests_prepid=[root_request["prepid"]], remove_root=True
        )

        # Ideally, we should also delete the ticket.
        # But it is not possible unless changes are perform at database level.
        # So, let's skip this.

        # Delete the chained campaign and the flows
        # INFO: Note that the order is strict!
        resources = [
            ("campaigns", "root_campaign"),
            ("campaigns", "sim_campaign"),
            ("flows", "flow_to_sim"),
            ("campaigns", "digi_campaign"),
            ("flows", "flow_to_digi"),
            ("campaigns", "hlt_campaign"),
            ("flows", "flow_to_hlt"),
            ("campaigns", "reco_campaign"),
            ("flows", "flow_to_reco"),
            ("campaigns", "miniaod_campaign"),
            ("flows", "flow_to_miniaod"),
            ("campaigns", "nanoaod_campaign"),
            ("flows", "flow_to_nanoaod"),
            ("chained_campaigns", "chained_campaign"),
        ]
        for res in reversed(resources):
            resource_type, resource_key = res
            object_id = self.entities[resource_key]["prepid"]
            self.mcm.delete(object_type=resource_type, object_id=object_id)
