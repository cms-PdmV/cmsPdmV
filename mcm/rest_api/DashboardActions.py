#!/usr/bin/env python

from RestAPIMethod import RESTResource
from tools.ssh_executor import ssh_executor
from json import dumps
import os
from couchdb_layer.prep_database import database
from collections import defaultdict

class GetBjobs(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)

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
        self.authenticator.set_limit(0)

    def GET(self, *args):
        """
        Gets a number of lines from given log.
        """
        if not args:
            self.logger.error('No arguments were given')
            return dumps({"results": 'Error: No arguments were given'})
        name = os.path.join('logs', args[0])
        nlines = -1
        if len(args) > 1:
            nlines = int(args[1])
        return self.read_logs(name, nlines)

    def read_logs(self, name, nlines):

        with open(name) as log_file:
            try:
                data = log_file.readlines()
            except IOError as ex:
                self.logger.error('Could not access logs: "{0}". Reason: {1}'.format(name, ex))
                return dumps({"results": "Error: Could not access logs."})

        if nlines > 0:
            data = data[-nlines:]
        return dumps({"results": ''.join(data)})


class GetLogs(RESTResource):
    def __init__(self):
        self.authenticator.set_limit(0)
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
    def __init__(self):
        self.access_limit = 4

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
            if opt=='log':
                opt_s=',vAxis: {logScale:true}'

            fcn='''\
        var %s = google.visualization.arrayToDataTable( %s );

        var options_chart_%s = {
          title: "Status for %s",
          hAxis: {title: "Campaign", titleTextStyle: {color: "red"}}%s
        };

        var chart_%s = new google.visualization.ColumnChart(document.getElementById("chart_div_%s"));
        chart_%s.draw(%s, options_chart_%s);
        '''%( title, dumps(data), 
              title,
              title,
              opt_s,
              title,title,
              title,title,title )
            div='<div id="chart_div_%s" style="width: 100%%; height: 500px;"></div>\n'%( title )
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
        cdb = database('campaigns')

        html="<html><body>\n"
        html+="This is a stats page internal to McM\n"

        counts = defaultdict(lambda: defaultdict(int) )
        counts_e = defaultdict(lambda: defaultdict(int) )
        sums = defaultdict(int) 

        statuses=['new', 'validation', 'approved' , 'submitted', 'done']
        data = []
        data.append( ['Step'] + statuses )
        data_g=[['Label','Value']]

        a_cc = args[0]
        if a_cc == 'all':
            all_r = rdb.get_all()
            #all_r = rdb.queries(['member_of_campaign==Summer12'])
            for mcm_r in all_r:
                counts[str(mcm_r['member_of_campaign'])] [mcm_r['status']] +=1
                to_add=mcm_r['total_events']
                if mcm_r['status'] in ['submitted','done']:
                    to_add=mcm_r['completed_events']
                try:
                    counts_e[str(mcm_r['member_of_campaign'])] [mcm_r['status']] += int(to_add)
                except:
                    self.logger.error('cannot seem to be able to digest "%s" for %s' % (to_add, mcm_r['prepid']))

                    
            for c in sorted(counts.keys()):
                a=0
                entry=[]
                entry.append( c ) # step[1] is the flow name       
                for s in statuses:
                    entry.append( counts_e[c][s] )
                    a+=counts_e[c][s]
                if not a:
                    g=0.
                else:
                    g = int(float(counts_e[c]['done']) / float(a) * 100.)
                data.append(entry)
                data_g.append([c,g])


            (f,d)=oneChart('all', data, opt='log')
            (f1,d1)=oneGauge( a_cc+'_g', data_g)
            f+=f1
            d+=d1
            return render( f,d)
            
            
        if not ccdb.document_exists( a_cc ):
            return "%s does not exists" %( a_cc )
        mcm_cc = ccdb.get( a_cc )
        all_cr = crdb.queries(['member_of_campaign==%s'%a_cc])

        for cc in all_cr:
            for r in cc['chain']:
                mcm_r = rdb.get(r)
                counts[str(mcm_r['member_of_campaign'])] [mcm_r['status']] +=1
                if mcm_r['status'] in ['submitted','done']:
                    counts_e[str(mcm_r['member_of_campaign'])] [mcm_r['status']] += mcm_r['completed_events']
                else:
                    counts_e[str(mcm_r['member_of_campaign'])] [mcm_r['status']] += mcm_r['total_events']
                
        for step in mcm_cc['campaigns']:
            entry=[]
            entry.append( step[0] ) # step[1] is the flow name
            for s in statuses:
                entry.append( counts_e[step[0]][s] )
            data.append(entry)


        (f,d)=oneChart( a_cc, data)
        data_g=[['Label','Value']]
        for step in mcm_cc['campaigns']:
            a=0
            for s in statuses:
                a+=counts_e[step[0]][s]
            if not a: 
                g=0.
            else:
                g = int(float(counts_e[step[0]]['done']) / float(a) * 100.)
            data_g.append( [step[0],g ])
        (f1,d1)=oneGauge( a_cc+'_g', data_g)
        f+=f1
        d+=d1
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
                      

                      

        html+="Counts<br>\n"
        html+="<ul>\n"
        for c in counts:
            html+="<li> %s </li>\n" % c
            html+="<ul>\n"
            for (n,v) in counts[c].items():
                html+="<li> %15s : %10d </li>\n" % ( n, v )
            html+="</ul>"                
        html+="</ul>"
        html+="<ul>\n"
        for (n,v) in sums.items():
            html+="<li> %15s : %10d </li>\n" % ( n, v )
        html+="</ul>"


        html+="</body></html>"
        return html
