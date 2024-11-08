"""
This module groups some fixtures to use
in different `pytest` test modules.
"""

import os

import pytest
from pytest import FixtureRequest
from rest import McM

from mcm_tests.rest_api.api_tools import Environment, McMTesting, Roles
from mcm_tests.use_cases.full_injection.core import InjectRootRequest, InjectToNanoAOD


@pytest.fixture
def authenticate_by_stdin(request: FixtureRequest) -> bool:
    """
    Check if the user has enabled the `stdin` to authenticate
    actions.
    """
    enabled = request.config.option.capture == "no"
    return enabled


@pytest.fixture
def stdin_enabled(authenticate_by_stdin: bool) -> None:
    """
    Check if the current execution allows to
    provide values by `stdin` interactions.

    Args:
        request: Pytest request fixture.
    """
    if not authenticate_by_stdin:
        reason = (
            "Standard input is disabled, it is not possible to "
            "capture human interactions to know when they completed "
            "the authentication flow..."
        )
        pytest.skip(reason)


@pytest.fixture(autouse=True)
def injection_to_reqmgr() -> None:
    """
    Executes or skips this test group based on the
    execution environment, if it is configured to
    submit request to CMS O&C ReqMgr2 application.
    """
    reqmgr2_available = bool(os.getenv("REQMGR2_ENABLED"))
    if not reqmgr2_available:
        raise pytest.skip(
            reason="The environment is not configured to submit request to ReqMgr2!"
        )


@pytest.fixture(autouse=True)
def able_to_access_internal_resources() -> None:
    """
    Checks that the test runtime environment is being executed
    inside CERN internal network, as some resources are only accessible
    within it.
    """
    return bool(os.getenv("ABLE_TO_ACCESS_INTERNAL_RESOURCES"))


@pytest.fixture()
def mcm_client(
    authenticate_by_stdin: bool, 
    able_to_access_internal_resources: bool
) -> tuple[McM, Environment]:
    """
    Retrieves a testing `Environment` configuration and a
    `McM` session pointing to the live `development` McM web application
    instance.
    """
    if authenticate_by_stdin:
        if not able_to_access_internal_resources:
            raise pytest.skip(
                "Execute this test with a test environment deployed inside CERN internal network!"
            )

        test_environment = Environment(
            mcm_couchdb_url="http://vocms0485.cern.ch:5984/",
            mcm_couchdb_lucene_url="<Not Required>",
            mcm_application_url="https://cms-pdmv-dev.web.cern.ch/mcm/",
            mcm_couchdb_credential="<Not Required>",
        )
        mcm_session = McM(id=McM.OIDC, dev=True)
        return (mcm_session, test_environment)
    else:
        test_environment = Environment()
        mcm_session = McMTesting(config=test_environment, role=Roles.ADMINISTRATOR)
        return (mcm_session, test_environment)


@pytest.fixture()
def root_request_injector(
    mcm_client: tuple[McM, Environment]
) -> InjectRootRequest:
    """
    Configures an injection handler to submit root request
    from scratch, deleting all the elements after use.
    """
    mcm, environment = mcm_client
    return InjectRootRequest(mcm=mcm, environment=environment)


@pytest.fixture()
def nanoaod_injector(
    mcm_client: tuple[McM, Environment]
) -> InjectToNanoAOD:
    """
    Configures an injector handler to submit a complete MC production sample
    from root requests to NanoAOD samples creating the intermediate campaigns,
    flows, chained campaigns, chained requests and tickets.
    """
    mcm, environment = mcm_client
    return InjectToNanoAOD(mcm=mcm, environment=environment)
