from tools.cmsweb_interface import cmsweb_interface
import itertools

class dbs3_interface:
    def __init__( self , dbs = 'global', proxy = '/afs/cern.ch/user/p/pdmvserv/private/personal/voms_proxy.cert'):
        self.url = 'https://cmsweb.cern.ch/dbs/prod/%s/DBSReader/'%dbs
        self.cmsweb = cmsweb_interface(proxy)

    def list_blocks(self, datasetname ):
        blocks = self.cmsweb.generic_call( self.url+"blocksummaries?dataset=%s&detail=true"%(datasetname))
        return blocks

    def match_stats_by_lumi(self, datasetname, total_stats, f_margin=0.05):
        import time
        files = self.cmsweb.generic_call( self.url+"filesummaries?dataset=%s"%(datasetname))
        n_lumi=0
        all_stats=0
        for f in files:
            n_lumi+=f['num_lumi']
            all_stats+=f['num_event']
        events_per_lumi = all_stats / float(n_lumi)
        if total_stats > all_stats:
            print "More stats required than available"
            return {}, all_stats
        elif total_stats > all_stats*(1-f_margin):
            print "Requiring almost the same as the available stats, not selecting"
            return {}, all_stats
        else:
            fraction_to_get = (1+f_margin) * total_stats / float(all_stats)
            ## get the list of files of the ds
            files = self.cmsweb.generic_call(self.url+"files?dataset=%s&detail=true"%(datasetname))
            ## get a list of lumi-section per run#
            l_per_r={}
            for f in files:
                time.sleep(0.5)
                for info in self.cmsweb.generic_call( self.url+"filelumis?logical_file_name=%s"%f['logical_file_name']):
                    if info['run_num'] in l_per_r:
                        l_per_r[info['run_num']].extend(info['lumi_section_num'])
                    else:
                        l_per_r[info['run_num']] = info['lumi_section_num']

                        
            ##create a lumi-mask per run#                
            final_mask={}
            import random
            for (r,lumis) in l_per_r.items():
                ### make a random choice each time
                random.shuffle( lumis )
                n_to_pick = int(  len(lumis) * fraction_to_get )
                lumis_to_use = lumis[:n_to_pick]
                lumis_to_use.sort()
                lmask =[]
                start_l=None
                end_l =None
                ## improved to create explicit ranges
                for (ilumi,lumi) in enumerate(lumis_to_use):
                    if not start_l:
                        start_l = lumi
                    inextlumi = ilumi+1
                    if inextlumi < len(lumis_to_use):
                        next_lumi=lumis_to_use[inextlumi]
                        if lumi+1 == next_lumi:
                            pass
                        else:
                            end_l = lumi
                    else:
                        end_l = lumi
                    if end_l:
                        lmask.append( [ start_l, end_l] )
                        start_l=None
                        end_l =None

                final_mask[str(r)] = lmask
            return final_mask, total_stats
        

    def match_stats_by_block(self, datasetname, total_stats, f_margin=0.05):
        all_blocks = self.list_blocks(datasetname)
        all_stats = sum(map(lambda i :  i['num_evernt'], all_blocks)) ## WTF !!!
        if total_stats > all_stats:
            print "More stats required than available"
            return [], all_stats
        elif total_stats > all_stats*(1-f_margin):
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
        

