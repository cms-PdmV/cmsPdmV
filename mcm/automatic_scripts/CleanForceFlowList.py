import tempfile
from pathlib import Path

# Make sure the McM package is installed:
# https://github.com/cms-PdmV/mcm_scripts?tab=readme-ov-file#build-package
from rest import McM

cookie_file = Path(tempfile.TemporaryDirectory().name) / Path("cookie.txt")
mcm = McM(dev=False, cookie=cookie_file)

forceflow = mcm.get('lists', 'list_of_forceflow', method='get')
list_of_forceflow = forceflow['value']
new_list_of_forceflow = list(list_of_forceflow)
for chain_prepid in list_of_forceflow:
    chained_request = mcm.get('chained_requests', chain_prepid)
    # print(json.dumps(chained_request, indent=4))
    if chained_request is None or len(chained_request) == 0:
        print('Delete %s because it does not exist' % (chain_prepid))
        new_list_of_forceflow.remove(chain_prepid)
    else:
        chain_list = chained_request.get('chain', [])
        if len(chain_list) == 0:
            print('%s chain is empty' % (chain_prepid))
            continue

        last_request = mcm.get('requests', chain_list[-1])
        if last_request is None or len(last_request) == 0:
            print('Weird, last request %s is None' % (chain_list[-1]))
            continue

        if last_request.get('status') == 'done':
            print('Delete %s because it\'s last request %s is done' % (chain_prepid, chain_list[-1]))
            new_list_of_forceflow.remove(chain_prepid)
        else:
            print('Keep %s' % (chain_prepid))

print('New list:\n%s' % (new_list_of_forceflow))
forceflow['value'] = new_list_of_forceflow
print(mcm.put('lists', forceflow, method='update'))
