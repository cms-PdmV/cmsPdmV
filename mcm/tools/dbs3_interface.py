from tools.cmsweb_interface import cmsweb_interface
import itertools

class dbs3_interface:
    def __init__( self , dbs = 'global', proxy = '/afs/cern.ch/user/p/pdmvserv/private/personal/voms_proxy.cert'):
        self.url = 'https://cmsweb.cern.ch/dbs/prod/%s/DBSReader/'%dbs
        self.cmsweb = cmsweb_interface(proxy)

    def list_blocks(self, datasetname ):
        blocks = self.cmsweb.generic_call( self.url+"blocksummaries?dataset=%s&detail=true"%(datasetname))
        return blocks
    def match_stats(self, datasetname, total_stats, f_margin=0.05):
        all_blocks = self.list_blocks(datasetname)
        all_stats = sum(map(lambda i :  i['num_evernt'], all_blocks)) ## WTF !!!
        if total_stats > all_stats:
            print "More stats required than available"
            return [], all_stats
        elif total_stats > all_stats*0.95:
            print "Requiring almost the same as the available stats, not selecting"
            return [], all_stats
        else:
            ### need to cherry-pick blocks for stats
            ## make all possible combinations of blocks and stop at the first that matches by 5%, register the closest one on the way
            closest_diff = all_stats
            margin = int(total_stats * f_margin) ## to the 5% closest
            for combination in itertools.combinations( all_blocks, 10):
                s = sum(map(lambda b : b['num_evernt'], combination))
                how_close = abs(s - total_stats)
                if how_close < margin:
                    selected_blocks = combination
                    print "Found a closest match by %2f%%" % (f_margin*100)
                    break
                if how_close < closest_diff:
                    selected_blocks = combination
                    closest_diff = how_close
                    
            return map(lambda b : b['block_name'], selected_blocks), sum(map(lambda b : b['num_evernt'], selected_blocks))
        

