import tempfile
import time
from pathlib import Path

# Make sure the McM package is installed:
# https://github.com/cms-PdmV/mcm_scripts?tab=readme-ov-file#build-package
from rest import McM

cookie_file = Path(tempfile.TemporaryDirectory().name) / Path("cookie.txt")
mcm = McM(dev=False, cookie=cookie_file)

list_of_nonflowing = mcm.get('lists', 'list_of_nonflowing_chains', method='get')
list_of_nonflowing = list_of_nonflowing['value']
print('List of nonflowing length: %d' % (len(list_of_nonflowing)))
new_list_of_nonflowing = []

current_timestamp = time.time()
force_complete_threshold = current_timestamp - 90 * 24 * 60 * 60
for nonflowing_chain in list_of_nonflowing:
    print('Processing %s' % (nonflowing_chain['chain']))
    chain_prepid = nonflowing_chain['chain']
    nonflowing_since = nonflowing_chain['nonflowing_since']
    if force_complete_threshold > nonflowing_since:
        print('Force done %s because it\'s nonflowing since %s' % (chain_prepid,
                                                                   time.strftime('%Y-%m-%d', time.localtime(nonflowing_since))))
        try:
            print(mcm.get('chained_requests', chain_prepid.strip(), method='force_done'))
        except:
            print('Something went wrong while processing %s' % chain_prepid)
            # list_of_nonflowing.remove(nonflowing_chain)

        time.sleep(0.1)
    else:
        print('Keep %s because it\'s nonflowing since %s' % (chain_prepid,
                                                             time.strftime('%Y-%m-%d', time.localtime(nonflowing_since))))
        new_list_of_nonflowing.append(nonflowing_chain)

old_nonflowing = mcm.get('lists', 'list_of_nonflowing_chains', method='get')
if len(old_nonflowing['value']) != len(new_list_of_nonflowing):
    print('New list will be uploaded')
    old_nonflowing['value'] = new_list_of_nonflowing
    print(mcm.update('lists', old_nonflowing))
