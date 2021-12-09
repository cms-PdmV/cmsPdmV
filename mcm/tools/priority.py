"""
This module provides number mapping from priority block to actual priority
"""
import logging
from connection_wrapper import ConnectionWrapper
from tools.config_manager import Config


# Priority block to actual priority map
priority_blocks = {1: 110000,
                   2: 90000,
                   3: 85000,
                   4: 80000,
                   5: 70000,
                   6: 63000}


def block_to_priority(block):
    """
    Return priority number for given block
    """
    block = int(block)
    if block in priority_blocks:
        return priority_blocks[block]

    return 20000


def change_priority(workflows):
    """
    Change priority for given dictionary of workflow names and priority
    """
    logger = logging.getLogger('mcm_error')
    reqmgr_host = Config.get('reqmgr_host')
    grid_cert = Config.get('grid_cert')
    grid_key = Config.get('grid_key')
    connection = ConnectionWrapper(host=reqmgr_host,
                                   keep_open=True,
                                   cert_file=grid_cert,
                                   key_file=grid_key)
    try:
        responses = {}
        for workflow_name, priority in workflows.items():
            logger.info('Changing "%s" priority to %s', workflow_name, priority)
            response = connection.api('PUT',
                                    '/reqmgr2/data/request/%s' % (workflow_name),
                                    {'RequestPriority': priority})
            responses[workflow_name] = response
    finally:
        connection.close()

    return responses
