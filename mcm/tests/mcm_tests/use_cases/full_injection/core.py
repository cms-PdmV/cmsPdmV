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


class MockBase:
    """
    Provides some methods for creating mock objects to inject MC samples.
    """

    @classmethod
    def _create_mock_campaign(
        cls,
        mock_path: Path,
        cms_sw_release: str,
        era: str,
        prepid_pattern: str,
        placeholder: str,
        no_output: bool,
    ) -> dict:
        """
        Create a mock campaign to use in further steps.

        Args:
            mock_path: Path to the mock schema for the campaign.
            cms_sw_release: CMSSW release for the campaign, e.g. CMSSW_10_6_12.
            era: Campaign's era, e.g. Run3.
            prepid_pattern: PrepID to set for the campaign, e.g. RunIISummer19UL16wmLHEGEN.
            placeholder: A placeholder to replace with a random number to avoid document collisions.
            no_ouput: Indicates if the campaign does (or does not) keep output for its sequences.

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

        mock["cmssw_release"] = cms_sw_release
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
        Create a mock flow to link two campaigns,
        the `initial_campaign` and the `next_campaign`.

        Args:
            mock_path: Path to the mock schema for the flow.
            initial_campaign: PrepID for the initial campaign to link.
            next_campaign: PrepID for the next campaign to link.
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
        cms_sw_release: str,
        era: str,
        root_campaign_prepid: str,
        keeps_output: bool,
    ) -> dict:
        """
        Create a mock root request.

        Args:
            mock_path: Path to the mock schema for the root request.
            cms_sw_release: CMSSW release to use for the request.
            era: Campaign's era.
            root_campaign_prepid: Campaign's PrepID of the root campaign.
            keeps_output: Indicates if the request creates and keeps its
                output dataset.

        Returns:
            Root request mock.
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        # Tweak some attributes.
        mock["cmssw_release"] = cms_sw_release
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
        Create a mock for a MccM ticket to use in the test.

        Args:
            mock_path: Path to the mock schema for the ticket.
            chained_campaign_prepid: ID of the chained campaign to use in the ticket
                as a template to generate a chained request instance.
            root_request_prepid: ID of the root request to include in the ticket
                as the first request.

        Returns:
            MccM ticket mock.
        """
        with open(mock_path, encoding="utf-8") as f:
            mock = json.load(fp=f)

        mock["chains"] = [chained_campaign_prepid]
        mock["prepid"] = f"PPD-2024Dec02-{random.randint(1,99999):05}"
        mock["requests"] = [root_request_prepid]
        return mock
    
    def mock(self) -> dict:
        """
        Create all necessary mock objects for the MC sample.
        """
        raise NotImplementedError("Overwrite this in a specific scenario")


class InjectorBase:
    """
    Provides some common methods to inject the testing scenario.
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        self.mcm = mcm
        self.environment = environment
        self.entities: dict[str, dict] = {}
        self.logger = LoggerFactory.getLogger(f"mcm_tests.{self.__class__.__name__}")
        self.resubmitter = ChainRequestResubmitter(mcm=mcm)

    def inject(self) -> None:
        """
        Inject the requests described in the MccM ticket to ReqMgr2.
        """
        if not self.entities:
            raise ValueError(
                (
                    "There are no entities to use for injecting the ticket. "
                    "Create them first in the application before injecting the scenario. "
                )
            )

        root_request = self.entities["root_request"]
        mccm_ticket = self.entities["mccm_ticket"]
        campaign = self.entities["campaign_to_reserve"]

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

    def _create_chained_campaign(self, chained_campaign: dict) -> dict:
        """
        Create a chained campaign in the McM application.

        Args:
            chained_campaign: Chained campaign schema.

        Returns:
            Created chained campaign object.
        """
        chained_campaign_creation = self.mcm.put(
            object_type="chained_campaigns", object_data=chained_campaign
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


class MocksForRun3Injection(MockBase):
    """
    Create several mock objects to simulate and inject a MC sample
    related to the Run3 era.

    The MC sample to create is based on the objects related to the
    following chained campaign
    - chain_Run3Summer23BPixGS_flowRun3Summer23BPixDRPremix_flowRun3Summer23BPixMiniAODv4_flowRun3Summer23BPixNanoAODv12
    """

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.cms_sw_release = "CMSSW_13_0_17"

        # The following era must be valid based on the cms-sw release
        # It could be available at: Configuration/Applications/python/cmsDriverOptions.py#L271
        self.era = "Run3"

        # Campaigns
        self._root_campaign: Path = files(current_module).joinpath(
            "static/RunIII/gs_root_campaign.json"
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

        # MccM ticket
        self._mccm_ticket: Path = files(current_module).joinpath(
            "static/mccm_ticket.json"
        )

        # Flows
        self._flow_to_dr: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_dr.json"
        )
        self._flow_to_miniaod: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_miniaod.json"
        )
        self._flow_to_nanoaod: Path = files(current_module).joinpath(
            "static/RunIII/flow_to_nanoaod.json"
        )

        # Root request
        self._root_request: Path = files(current_module).joinpath(
            "static/RunIII/root_request.json"
        )

    def mock(self) -> dict:
        # Campaigns
        root_campaign = self._create_mock_campaign(
            mock_path=self._root_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="Run3SystemTesting$BPixGS",
            placeholder="$",
            no_output=False
        )
        dr_campaign = self._create_mock_campaign(
            mock_path=self._dr_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="Run3SystemTesting$BPixDRPremix",
            placeholder="$",
            no_output=False
        )
        miniaod_campaign = self._create_mock_campaign(
            mock_path=self._miniaod_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="Run3SystemTesting$BPixMiniAODv4",
            placeholder="$",
            no_output=False
        )
        nanoaod_campaign = self._create_mock_campaign(
            mock_path=self._nanoaod_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="Run3SystemTesting$BPixNanoAODv12",
            placeholder="$",
            no_output=False
        )
        root_request = self._create_mock_root_request(
            mock_path=self._root_request,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            root_campaign_prepid=root_campaign["prepid"],
            keeps_output=True
        )

        return {
            "campaign": root_campaign,
            "dr_campaign": dr_campaign,
            "miniaod_campaign": miniaod_campaign,
            "nanoaod_campaign": nanoaod_campaign,
            "root_request": root_request
        }


class MocksForRun2Injection(MockBase):
    """
    Create several mock objects to simulate and inject a MC sample
    related to the Run2 era.

    The MC sample to create is based on the objects related to the
    following chained campaign
    - chain_RunIISummer19UL16wmLHEGEN_flowRunIISummer19UL16SIM_flowRunIISummer19UL16DIGIEpsilonPU_
        flowRunIISummer19UL16HLT_flowRunIISummer19UL16RECO_flowRunIISummer19UL16MiniAOD_
        flowRunIISummer19UL16JMENtuplesNanoAOD

    This scenario includes several steps "out of the common" structure
    like SIM, DIGI, HLT and RECO. Some of them using old releases
    related to old architectures.
    """

    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.cms_sw_release = "CMSSW_10_6_12"
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
            "static/mccm_ticket.json"
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

    def mock(self) -> dict:
        # Campaigns
        root_campaign = self._create_mock_campaign(
            mock_path=self._root_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$wmLHEGEN",
            placeholder="$",
            no_output=True,
        )
        sim_campaign = self._create_mock_campaign(
            mock_path=self._sim_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$SIM",
            placeholder="$",
            no_output=True,
        )
        digi_campaign = self._create_mock_campaign(
            mock_path=self._digi_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$DIGI",
            placeholder="$",
            no_output=True,
        )
        hlt_campaign = self._create_mock_campaign(
            mock_path=self._hlt_campaign,
            cms_sw_release="CMSSW_8_0_33_UL",  # This requires an older release!
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$HLT",
            placeholder="$",
            no_output=True,
        )
        reco_campaign = self._create_mock_campaign(
            mock_path=self._reco_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$RECO",
            placeholder="$",
            no_output=True,
        )
        miniaod_campaign = self._create_mock_campaign(
            mock_path=self._miniaod_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$MiniAOD",
            placeholder="$",
            no_output=True,
        )
        nanoaod_campaign = self._create_mock_campaign(
            mock_path=self._nanoaod_campaign,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            prepid_pattern="RunIISystemTesting19UL$NanoAOD",
            placeholder="$",
            no_output=True,
        )
        root_request = self._create_mock_root_request(
            mock_path=self._root_request,
            cms_sw_release=self.cms_sw_release,
            era=self.era,
            root_campaign_prepid=root_campaign["prepid"],
            keeps_output=True,
        )

        return {
            "campaign": root_campaign,
            "sim_campaign": sim_campaign,
            "digi_campaign": digi_campaign,
            "hlt_campaign": hlt_campaign,
            "reco_campaign": reco_campaign,
            "miniaod_campaign": miniaod_campaign,
            "nanoaod_campaign": nanoaod_campaign,
            "root_request": root_request,
        }


class InjectRootRequest(InjectorBase, MocksForRun3Injection):
    """
    Creates and injects a MC sample including only the root request to ReqMgr2.
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        InjectorBase.__init__(self, mcm=mcm, environment=environment)
        MocksForRun3Injection.__init__(self)

    def create(self, mocks: dict) -> dict:
        """
        Create the entities for the scenario in the McM application
        using the provided mocks.
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
            mock_path=self._mccm_ticket,
            chained_campaign_prepid=f"chain_{campaign['prepid']}",
            root_request_prepid=root_request_prepid,
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

        # Reserve up to the following campaign
        entities["campaign_to_reserve"] = campaign_created

        for type, value in entities.items():
            if isinstance(value, dict) and value.get("prepid"):
                continue
            else:
                raise ValueError(f"{type} was not properly created")

        self.entities = entities
        return self.entities

    def cleanup(self) -> None:
        """
        Delete most of the created resources.
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


class InjectToNanoAOD(InjectorBase, MocksForRun3Injection):
    """
    Creates and injects a MC sample including several request
    up to the NanoAOD data tier related to the Run3 sample to ReqMgr2.
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        InjectorBase.__init__(self, mcm=mcm, environment=environment)
        MocksForRun3Injection.__init__(self)

    def _create_chained_campaign(self, entities: dict) -> dict:
        """
        Create a chained campaign that integrates all the steps
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

        return super()._create_chained_campaign(chained_campaign=chained_campaign_mock)

    def create(self, mocks: dict) -> dict:
        """
        Create the entities for the scenario in the McM application
        using the provided mocks.
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
        flow_to_dr = self._create_mock_flow(
            mock_path=self._flow_to_dr,
            initial_campaign=entities["campaign"]["prepid"],
            next_campaign=entities["dr_campaign"]["prepid"],
            keeps_output=[False, False]
        )
        flow_to_miniaod = self._create_mock_flow(
            mock_path=self._flow_to_miniaod,
            initial_campaign=entities["dr_campaign"]["prepid"],
            next_campaign=entities["miniaod_campaign"]["prepid"],
            keeps_output=[True]
        )
        flow_to_nanoaod = self._create_mock_flow(
            mock_path=self._flow_to_nanoaod,
            initial_campaign=entities["miniaod_campaign"]["prepid"],
            next_campaign=entities["nanoaod_campaign"]["prepid"],
            keeps_output=[True]
        )
        flows_to_create = {
            "flow_to_dr": flow_to_dr,
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
        entities["chained_campaign"] = self._create_chained_campaign(
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

        # Reserve up to the following campaign
        entities["campaign_to_reserve"] = entities["nanoaod_campaign"]

        self.entities = entities
        return self.entities

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


class InjectRun2Requests(InjectorBase, MocksForRun2Injection):
    """
    Creates and injects a MC sample including several request
    up to the NanoAOD data tier related to the Run2 sample to ReqMgr2.
    """

    def __init__(self, mcm: McM, environment: Environment) -> None:
        InjectorBase.__init__(self, mcm=mcm, environment=environment)
        MocksForRun2Injection.__init__(self)

    def _create_chained_campaign(self, entities: dict) -> dict:
        """
        Create a chained campaign that integrates all the steps
        to produce samples from the root campaign to the NanoAOD campaign
        using the campaigns and flows created in previous steps.

        Args:
            entities: An object that includes all campaigns and flows required.
        """
        # Campaigns
        root_campaign = entities["campaign"]["prepid"]
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

        return super()._create_chained_campaign(chained_campaign=chained_campaign_mock)

    def create(self, mocks: dict) -> dict:
        """
        Create the entities for the scenario in the McM application
        using the provided mocks.
        """
        entities = {}
        root_request = mocks["root_request"]

        # Create the campaigns
        campaigns_to_create = [
            "campaign",
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
            initial_campaign=entities["campaign"]["prepid"],
            next_campaign=entities["sim_campaign"]["prepid"],
        )
        flow_to_digi = self._create_mock_flow(
            mock_path=self._flow_to_digi,
            initial_campaign=entities["sim_campaign"]["prepid"],
            next_campaign=entities["digi_campaign"]["prepid"],
            keeps_output=[False],
        )
        flow_to_hlt = self._create_mock_flow(
            mock_path=self._flow_to_hlt,
            initial_campaign=entities["digi_campaign"]["prepid"],
            next_campaign=entities["hlt_campaign"]["prepid"],
        )
        flow_to_reco = self._create_mock_flow(
            mock_path=self._flow_to_reco,
            initial_campaign=entities["hlt_campaign"]["prepid"],
            next_campaign=entities["reco_campaign"]["prepid"],
        )
        flow_to_miniaod = self._create_mock_flow(
            mock_path=self._flow_to_miniaod,
            initial_campaign=entities["reco_campaign"]["prepid"],
            next_campaign=entities["miniaod_campaign"]["prepid"],
            keeps_output=[True],
        )
        flow_to_nanoaod = self._create_mock_flow(
            mock_path=self._flow_to_miniaod,
            initial_campaign=entities["miniaod_campaign"]["prepid"],
            next_campaign=entities["nanoaod_campaign"]["prepid"],
            keeps_output=[True],
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
        entities["chained_campaign"] = self._create_chained_campaign(
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

        # Reserve up to the following campaign
        entities["campaign_to_reserve"] = entities["nanoaod_campaign"]

        self.entities = entities
        return self.entities

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
