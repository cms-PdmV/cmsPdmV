import json
import pytest


@pytest.fixture
def load_sample_data() -> list[dict]:
    """
    Load the sample workflows from Stats2 for a McM request.
    """
    workflows_path = "sample_workflows.json"
    with open(workflows_path, encoding="utf-8") as f:
        workflows = json.load(f)
    return workflows


# Isolate the function so that it is possible to execute this
# script without providing environment variables for the application
# and meeting other requirements.
def _attempt_filter_workflows(mcm_reqmgr_name_list, stats_workflows):
    """
    Attempts to pick the latest injected workflows using the records available
    in McM. After an injection process finishes, only the latest workflow name
    is available on the `reqmgr_name` attribute with no content.

    Note this filter process is not idempotent. In case the request has been
    updated with previous data from Stats2, it is not possible to get the latest
    workflow and nothing will be filtered. Such behavior is acceptable.

    Args:
        mcm_reqmgr_name_list (list[str]): List of ReqMgr2 workflow names available for
            the request in McM.
        stats_workflows (list[dict]): Stats2 workflow records related to the McM
            request.

    Returns:
        list[dict]: Stats2 workflows possibly filtered by the latest injected
            workflow. This could return the original list if the reference to
            the latest injected workflow is not available or an empty list if
            the latest injected workflow was not found in the provided list.
    """
    stats_workflows_dict = {
        stats_workflow.get('RequestName'): stats_workflow
        for stats_workflow in stats_workflows
    }
    workflows_to_consider = [
        stats_workflows_dict.get(mcm_reqmgr_name)
        for mcm_reqmgr_name in mcm_reqmgr_name_list
        if stats_workflows_dict.get(mcm_reqmgr_name)
    ]

    print("Workflows to consider: %s", [doc.get('RequestName') for doc in workflows_to_consider])
    try:
        # Pick the time related to the `new` transition
        reference_time_of_new = min([
            stats_doc.get('RequestTransition')[0].get('UpdateTime')
            for stats_doc in workflows_to_consider
        ])
    except:
        # There's no record for the latest injected workflow in Stats2.
        return []

    stats_reqmgr_name_list = [
        reqmgr_name
        for reqmgr_name, content in stats_workflows_dict.items()
        if content.get('RequestTransition') and
            len(content['RequestTransition']) > 0 and
            content['RequestTransition'][0].get('UpdateTime') is not None and
            content['RequestTransition'][0]['UpdateTime'] >= reference_time_of_new
    ]
    print(
        "The following workflows may not be related to the last injection: %s",
        set(stats_workflows_dict.keys()) - set(stats_reqmgr_name_list)
    )

    return stats_reqmgr_name_list


def test_workflow_not_found(load_sample_data):
    """
    Check that an empty list is retrieved if the current workflow
    is not available in the Stats2 records.
    """
    workflows = load_sample_data
    filtered_workflows = _attempt_filter_workflows(["NotFound"], workflows)
    assert filtered_workflows == []


def test_first_workflow(load_sample_data):
    """
    Check all workflows are taken if the request
    was previously updated with its data from Stats2.
    """
    workflows = load_sample_data
    stats_workflows_dict = {
        stats_workflow.get('RequestName'): stats_workflow
        for stats_workflow in workflows
    }
    filtered_workflows = _attempt_filter_workflows(stats_workflows_dict.keys(), workflows)
    assert filtered_workflows == list(stats_workflows_dict.keys())


def test_filter_last_workflow(load_sample_data):
    """
    Check only the latest workflows are taken if the
    request provides the workflow names related to the last
    injection.
    """
    workflows = load_sample_data
    latest_injection = ["pdmvserv_task_TSG-Run3Summer23wmLHEGS-00022__v1_T_240324_024809_7105"]
    filtered_workflows = _attempt_filter_workflows(latest_injection, workflows)
    assert filtered_workflows == [
        "pdmvserv_task_TSG-Run3Summer23wmLHEGS-00022__v1_T_240324_024809_7105",
        "cmsunified_task_TSG-Run3Summer23wmLHEGS-00022__v1_T_240324_131348_9030"
    ]

    # Just the last
    last_workflow = ["cmsunified_task_TSG-Run3Summer23wmLHEGS-00022__v1_T_240324_131348_9030"]
    filtered_workflows = _attempt_filter_workflows(last_workflow, workflows)
    assert filtered_workflows == last_workflow
