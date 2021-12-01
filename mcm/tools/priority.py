"""
This module provides number mapping from priority block to actual priority
"""

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
