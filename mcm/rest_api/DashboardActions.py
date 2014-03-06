#!/usr/bin/env python

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from json import dumps
import os
import time
from couchdb_layer.mcm_database import database
from collections import defaultdict
from tools.user_management import access_rights

class GetBjobs(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args):
        """
        Get bjobs information regarding the batch jobs
        """
        ssh_exec = ssh_executor()
        try:
            stdin, stdout, stderr = ssh_exec.execute(self.create_command(args))
            out = stdout.read()
            err = stderr.read()
            if err:
                if "No job found in job group" in err:  # so the shown string is consistent with production
                    return dumps({"results": 'No unfinished job found'})
                return dumps({"results": err})
            return dumps({"results": out})
        finally:
            ssh_exec.close_executor()

    def create_command(self, options):
        bcmd = 'bjobs'
        for opt in options:
            if '-g' in opt:
                bcmd += ' -g ' + '/' + '/'.join(opt.split()[1:])
            else:
                bcmd += opt
        return bcmd


class GetLogFeed(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args):
        """
        Gets a number of lines from given log.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        name = os.path.join('logs', args[0].split(os.pathsep)[-1])
        nlines = -1
        if len(args) > 1:
            nlines = int(args[1])
        return dumps(self.read_logs(name, nlines))

    def read_logs(self, name, nlines):

        with open(name) as log_file:
            try:
                data = log_file.readlines()
            except IOError as ex:
                self.logger.error('Could not access logs: "{0}". Reason: {1}'.format(name, ex))
                return {"results": "Error: Could not access logs."}

        if nlines > 0:
            data = data[-nlines:]
        return {"results": ''.join(data)}


class GetRevision(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user

    def GET(self, *args):
        """ 
        returns the current tag of the software running
        """
        revision=os.getenv('MCM_REVISION')
        return revision


class GetStartTime(RESTResource):
    def __init__(self, time):
        self.time = time

    def GET(self, *args):
        return dumps({"results": self.time})


class GetLogs(RESTResource):
    def __init__(self):
        self.access_limit = access_rights.user
        self.path = "logs"

    def GET(self, *args):
        """
        Gets a list of logs sorted by date.
        """

        files_dates = sorted([{"name": filename, "modified": os.path.getmtime(os.path.join(self.path, filename))}
                              for filename in os.listdir(self.path)
                              if os.path.isfile(os.path.join(self.path, filename))], key=lambda x: x["modified"],
                             reverse=True)

        return dumps({"results": files_dates})

class GetStats(RESTResource):
    def __init__(self,with_data=False):
        self.access_limit = access_rights.user
        self.countDummy=0
        self.ramunas = with_data

    def fakeId(self):
        self.countDummy+=1
        return 'X'*(5-len("%d"%(self.countDummy)))+"%d"%(self.countDummy)
    
    def __createDummyRequest(self, req, memberOfCampaign, status="upcoming",total=None):
        fake_r = {}
        fake_r['status']= status
        fake_r['member_of_campaign']=memberOfCampaign
        for member in ['pwg','priority','total_events']:
            fake_r[member]=req[member]
        if total is not None:
            fake_r['total_events'] =total
        fake_r['prepid'] = '-'.join([req['pwg'], memberOfCampaign, self.fakeId()])
        fake_r['cloned_from'] = req['prepid']
        self.logger.error("Total events is %s for %s"%( fake_r['total_events'], req['prepid']))
        return fake_r


    def GET(self, *args):
        """
        Get a bunch of stat information, as a test
        """

        def render( fcns, divs):
            display='''\
<html>
  <head>
    <script type="text/javascript" src="https://www.google.com/jsapi"></script>
    <script type="text/javascript">
      google.load("visualization", "1", {packages:["corechart"]});
      google.load('visualization', '1', {packages:['gauge']});
      google.setOnLoadCallback(drawChart);
      function drawChart() {
         %s
      }
    </script>
  </head>
  <body>
    %s
  </body>
</html>
'''% ( fcns, divs )
            return display

        def oneChart( title, data, opt=''):
            var_name=title.replace(",","")
            opt_s=''
            if opt=='log':
                opt_s=',vAxis: {logScale:true}'

            fcn='''\
        var %s = google.visualization.arrayToDataTable( %s );
        var formatter = new google.visualization.NumberFormat({fractionDigits:0});
        for (var i=1;i<%s.getNumberOfColumns();i++){
           formatter.format( %s ,i);
        };
        var options_chart_%s = {
          title: "Status for %s",
          hAxis: {title: "Campaign", titleTextStyle: {color: "red"}}%s
        };

        var chart_%s = new google.visualization.ColumnChart(document.getElementById("chart_div_%s"));
        chart_%s.draw(%s, options_chart_%s);
        '''%( var_name, dumps(data), 
              var_name,
              var_name,
              var_name,
              title,
              opt_s,
              var_name,var_name,
              var_name,var_name,var_name)
            div='<div id="chart_div_%s" style="width: 100%%; height: 500px;"></div>\n'%( var_name )
            return (fcn,div)

        def oneGauge( title, data):
            h = int(250 * (len(data)/5. +1))
            fcn='''\
        var %s = google.visualization.arrayToDataTable( %s );                                                                                                                                                                                                                               var options_gauge = {
          height: %d,
          redFrom: 90, redTo: 100,
          yellowFrom:75, yellowTo: 90,
          minorTicks: 5
        };
        var gauge_%s = new google.visualization.Gauge(document.getElementById('gauge_div_%s'));
        gauge_%s.draw(%s,options_gauge)
        '''%( title, dumps(data),
              h,
              title,title,
              title,title)

            div='<div id="gauge_div_%s"></div>\n'%( title )
            return (fcn,div)



        rdb = database('requests')
        crdb =database('chained_requests')
        ccdb =database('chained_campaigns')
        #fdb = database('flows')
        cdb = database('campaigns')

        html="<html><body>\n"
        html+="This is a stats page internal to McM\n"

        counts = defaultdict(lambda: defaultdict(int) )
        counts_e = defaultdict(lambda: defaultdict(int) )
        sums = defaultdict(int) 

        statuses=['new', 'validation', 'defined', 'approved' , 'submitted', 'done', 'upcoming']
        data = []
        data.append( ['Step'] + statuses )
        data_g=[['Label','Value']]

        def human( n ):
            if n<1000:
                return "%s" % n
            elif n>=1000 and n<1000000:
                order = 1
            elif n>=1000000 and n<1000000000:
                order = 2
            else:
                order = 3
            norm = pow(10,3*order)
            value = float(n)/norm
            letter = {1:'k',2:'M',3:'B'}
            return "%.1f %s" % (value,letter[order])

        main_arg = args[0]
        if main_arg == 'all':
            a_date=None
            if len(args)>1:
                a_date=args[1]
                a_date_t = time.mktime( time.strptime( a_date , "%Y-%m-%d-%H-%M" ))
            statuses.remove('upcoming')
            data[-1].remove('upcoming')
            all_r = rdb.get_all()
            #all_r = rdb.queries(['member_of_campaign==Summer12'])
            for mcm_r in all_r:
                last_status=mcm_r['status']
                if a_date:
                    for h in mcm_r['history']:
                        h['date'] = time.mktime( time.strptime( h['updater']['submission_date'], "%Y-%m-%d-%H-%M" ))

                    sh =  filter(lambda h : h['date']< a_date_t and h['action']=='set status', mcm_r['history'])
                    if len(sh):
                        last_status=sh[-1]['step']
                    else:
                        #this request had no status at the time
                        #continue
                        last_status='new'

                counts[str(mcm_r['member_of_campaign'])] [last_status] +=1
                to_add=mcm_r['total_events']
                #if last_status in ['submitted','done']:
                #    to_add=mcm_r['completed_events']
                try:
                    counts_e[str(mcm_r['member_of_campaign'])] [last_status] += int(to_add)
                except:
                    self.logger.error('cannot seem to be able to digest "%s" for %s' % (to_add, mcm_r['prepid']))

            table=''
            if a_date:
                table+='Status of the campaigns on %s <br>\n'%( time.asctime(time.gmtime(a_date_t)))
            table+='<table style="font-size: 30px;" border=1><thead><tr><th> Campaign </th>'
            for s in statuses:
                table+="<th> %s </th>"%(s)
            table+="</tr></thead>\n"
            for c in sorted(counts.keys()):
                a=0
                entry=[]
                entry.append( c ) # step[1] is the flow name       
                table+="<tr><td> %s </td>"%(c)
                for s in statuses:
                    entry.append( counts_e[c][s] )
                    a+=counts_e[c][s]
                    table+="<td> %s </td>" %( human(counts_e[c][s]))
                if not a:
                    g=100.
                else:
                    g = int(float(counts_e[c]['done']) / float(a) * 100.)
                data.append(entry)
                data_g.append([c,g])
                table+="</tr>\n"
            table+="</table>"
            (f,d)=oneChart('all', data, opt='log')
            (f1,d1)=oneGauge( 'main_g', data_g)
            f+=f1
            d+=d1
            ## add a simple table per campaign
            d+="<br>\n<br>\n" + table

            return render( f,d)

        arg_list = main_arg.split(',')

        #reduction to only cc
        while True:
            again=False
            for arg in arg_list:
                if not arg.startswith('chain'):
                    # this is a flow, or a campaign : does not matter for the query
                    ccs = ccdb.queries(['contains==%s'%( arg)])
                    arg_list.extend( map (lambda cc: cc['prepid'], ccs))
                    arg_list.remove( arg )
                    again=True
                    break
            if not again:
                break

        ## arg_list contains only chained campaigns
        steps=[] #what are the successive campaigns
        all_cr=[] #what are the chained requests to look at
        all_cc={}
        #unique it
        arg_list= list(set(arg_list))

        ## collect all crs
        for a_cc in arg_list:
            if not ccdb.document_exists( a_cc ):
                ## try to see if that's a flow
                return "%s does not exists" %( a_cc )
            mcm_cc = ccdb.get( a_cc) 
            all_cc[a_cc] = mcm_cc ## keep it in mind
            all_cr.extend( crdb.queries(['member_of_campaign==%s'%a_cc]))
            these_steps = map(lambda s : s[0], mcm_cc['campaigns'])
            if len(steps)==0:
                steps=these_steps
            else:
                ## concatenate to existing steps
                ##add possible steps at the beginning
                connection=0
                while not steps[connection] in these_steps:
                    #self.logger.error('looking at %s and %s'%( these_steps, steps))
                    connection+=1

                new_start= these_steps.index( steps[connection] )
                if new_start!=0:
                    #they do not start at the same campaign
                    for where in range(new_start):
                        steps.insert(where, these_steps[where])
                ##verify strict overlapping ==> does not function properly and limits the flexibility
                for check in range(new_start, len(these_steps)):
                    #if check > len(steps) and these_steps[check] not in steps:
                    #    steps.append( these_steps[check] )
                    if these_steps[check] not  in steps:
                        steps.append( these_steps[check] )

                    #if steps[check]!=these_steps[check]:
                    #    return "%s cannot be consistently added, as part of %s, at %s"% ( these_steps, steps, check)


        ## preload all requests !!!
        all_requests = {}
        for step in steps:
            for r in rdb.queries(['member_of_campaign==%s'%( step)] ):
                all_requests[r['prepid']] = r

        already_counted=set() ## avoid double counting
        #the list of requests to be emitted to d3js
        list_of_request_for_ramunas=[]

        for cr in all_cr:
            upcoming=0
            if len(cr['chain'])==0:
                ## crap data
                continue
            #stop_at=cr['step']
            stop_at=len(cr['chain'])-1
            for (r_i,r) in enumerate(cr['chain']):
                if r_i > stop_at:
                    ## this is a reserved request, will count as upcoming later
                    continue

                mcm_r = all_requests[r]
                upcoming=mcm_r['total_events']
                if r in already_counted:
                    continue
                else:
                    already_counted.add(r)

                counts[str(mcm_r['member_of_campaign'])] [mcm_r['status']] +=1
                if mcm_r['status'] in ['done']:
                    counts_e[str(mcm_r['member_of_campaign'])] [mcm_r['status']] += mcm_r['completed_events']
                elif  mcm_r['status'] in ['submitted']:
                    ##split the stat in done and submitted accordingly
                    counts_e[str(mcm_r['member_of_campaign'])] ['done'] += mcm_r['completed_events']
                    counts_e[str(mcm_r['member_of_campaign'])] ['submitted'] += max([0, mcm_r['total_events'] - mcm_r['completed_events']])
                else:
                    counts_e[str(mcm_r['member_of_campaign'])] [mcm_r['status']] += mcm_r['total_events']
                
                ## manipulation of total_events => completed ?
                ## splitting of the request into done=completed_events and submitted=max([0, mcm_r['total_events'] - mcm_r['completed_events']]) ?
                ## add it to emit
                for member in mcm_r.keys():
                    if member not in ['prepid','pwg','priority','total_events','status','member_of_campaign']:
                        mcm_r.pop(member)
                list_of_request_for_ramunas.append( mcm_r )

            for noyet in all_cc[cr['member_of_campaign']]['campaigns'][stop_at+1:]:
                #self.logger.log( '%s if saying %s'%( cr['prepid'], all_cc[cr['member_of_campaign']]['campaigns'][cr['step']+1:])) 
                counts_e[ noyet[0] ]['upcoming']+=upcoming
                ## create a fake request with the proper member of campaign
                processing_r = all_requests[ cr['chain'][ stop_at ] ]

                fake_one = self.__createDummyRequest( processing_r, noyet[0] )
                #fake_one = self.__createDummyRequest( processing_r, noyet[0], total=upcoming )
                list_of_request_for_ramunas.append( fake_one )
                

            #fill up the rest with upcoming
            #for noyet in steps[ len(cr['chain']):]:
            #    counts_e[str(noyet)]['upcoming'] += upcoming

        for step in steps:
            entry=[]
            entry.append( step )
            for s in statuses:
                entry.append( counts_e[step][s] )
            data.append(entry)


        (f,d)=oneChart( ','.join(arg_list), data)
        data_g=[['Label','Value']]


        table='<table style="font-size: 30px;" border=1><thead><tr><th> Campaign / Status </th>'
        for s in statuses:
            table+="<th> %s </th>"%(s)
        table+="</tr></thead>\n"
        for step in steps:
        #for step in mcm_cc['campaigns']:
            a=0
            table+="<tr><td> %s </td>"%(step)
            for s in statuses:
                a+=counts_e[step][s]
                table+="<td> %s </td>" %( human( counts_e[step][s] ))
            if not a: 
                g=100.
            else:
                g = int(float(counts_e[step]['done']) / float(a) * 100.)
            data_g.append( [step,g ])
            table+="</tr>\n"
        table+="</table>"

        (f1,d1)=oneGauge( 'g_g', data_g)
        f+=f1
        d+=d1
        d+="<br>\n<br>\n" + table
        if self.ramunas:
            return dumps({"results":list_of_request_for_ramunas})
        else:
            return render( f,d)

        """
        all_r = rdb.get_all()
        #all_r = rdb.queries(['member_of_campaign==Summer12'])

        to_count=['type','member_of_campaign','status']
        to_sum= ['total_events','completed_events']
        for r in all_r:
            for c in to_count:
                counts[c][r[c]]+=1 
            for s in to_sum:
                sums[s]+= r[s]
        """
                      

                      

        # html+="Counts<br>\n"
        # html+="<ul>\n"
        # for c in counts:
        #     html+="<li> %s </li>\n" % c
        #     html+="<ul>\n"
        #     for (n,v) in counts[c].items():
        #         html+="<li> %15s : %10d </li>\n" % ( n, v )
        #     html+="</ul>"
        # html+="</ul>"
        # html+="<ul>\n"
        # for (n,v) in sums.items():
        #     html+="<li> %15s : %10d </li>\n" % ( n, v )
        # html+="</ul>"
        #
        #
        # html+="</body></html>"
        # return html

