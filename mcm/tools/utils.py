"""
Common utils
"""


def clean_split(string, separator=',', maxsplit=-1):
    """
    Split a string by separator and collect only non-empty values
    """
    return [x.strip() for x in string.split(separator, maxsplit) if x.strip()]


def expand_range(start, end):
    """
    Expand a given range to all ids
    E.g. start=AAA-00001 and end=AAA-00005 would return all the ids between
    00001 and 00005 -> AAA-00001, AAA-00002, AAA-00003, AAA-00004, AAA-00005
    """
    start = start.split('-')
    end = end.split('-')
    range_start = int(start[-1])
    range_end = int(end[-1])
    numbers = range(range_start, range_end + 1)
    start = '-'.join(start[:-1])
    end = '-'.join(end[:-1])
    if start != end:
        raise Exception('Invalid range "%s-..." != "%s-..."' % (start, end))

    if range_start > range_end:
        raise Exception('Invalid range ...-%05d > ...-%05d' % (range_start, range_end))

    return ['%s-%05d' % (start, n) for n in numbers]
