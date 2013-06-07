import json
import time
from operator import itemgetter
import re
import threading
import urllib2

class Simulation(object):    
    #
    #Global Value which contain all the parameter of the simulation
    ##
    Attributs = {}
    #_getitem_
    #
    #GetItem Function Allow the object Simulation to work like a dictionnary in using Attributs like source of information
    def __getitem__(self, name):
        return self.Attributs[name]
        
    def getsim(self):
        return self.Attributs
    #_init_
    #
    #Create a new void simulation with all parameter at the base value 0 or "" only Monitor time get the value "N\A" (request of Vlimant)
    def _init_(self):
        self.Attributs = {}
        self.Attributs["SIMID"] = 0;
        self.Attributs["PDMV expected events"] = 0;
        self.Attributs["PDMV type"] = "";
        self.Attributs["PDMV status from reqmngr"] = "";
        self.Attributs["PDMV priority"] = 0;
        self.Attributs["PDMV running jobs"] = 0;
        self.Attributs["PDMV running days"] = 0;
        self.Attributs["PDMV evts in DAS"] = 0;
        self.Attributs["PDMV request name"] = "";
        self.Attributs["PDMV submission date"] = "";
        self.Attributs["PDMV completion eta in DAS"] = 0;
        self.Attributs["PDMV status in DAS"] = "";
        self.Attributs["PDMV prep id"] = "";
        self.Attributs["PDMV campaign"] = "";
        self.Attributs["PDMV data set name"] = "";
        self.Attributs["PDMV status"] = "";
        self.Attributs["PDMV request"] = "";
        self.Attributs["PDMV pd pattern"] = "";
        self.Attributs["PDMV present priority"] = 0;
        self.Attributs["PDMV completion in das"] = 0;
        self.Attributs["PDMV all jobs"] = 0;
        self.Attributs["PDMV pending jobs"] = 0;
        self.Attributs["PDMV monitor time"] = "N\A";
        self.Attributs["PDMV Perf"] = "";
        
    #toString()
    #
    #Allow to print a Simuation class in the format of a html table row
    def toString(self, typeA, ListOfColumns):
        
        if(typeA):
            String = '<tr class="un">'
        else:
            String = '<tr class="bis">'
        i = 0
        
        while(i < len(ListOfColumns)):
            if(int(ListOfColumns[i]) == 1):
                String = String + "<td>" + str(self.Attributs['SIMID']) + "</td>"
            if(int(ListOfColumns[i]) == 2):
                String = String + "<td>" + str(self.Attributs['PDMV expected events']) + "</td>"
            if(int(ListOfColumns[i]) == 3):
                String = String + "<td>" + self.Attributs["PDMV type"] + "</td>"
            if(int(ListOfColumns[i]) == 4):
                String = String + "<td>" + self.Attributs["PDMV status from reqmngr"] + "</td>"
            if(int(ListOfColumns[i]) == 5):
                String = String + "<td>" + str(self.Attributs["PDMV priority"]) + "</td>"
            if(int(ListOfColumns[i]) == 6):
                String = String + "<td>" + str(self.Attributs["PDMV running jobs"]) + "</td>"
            if(int(ListOfColumns[i]) == 7):
                String = String + "<td>" + str(self.Attributs["PDMV running days"]) + "</td>"
            if(int(ListOfColumns[i]) == 8):
                String = String + "<td>" + str(self.Attributs["PDMV evts in DAS"]) + "</td>"
            if(int(ListOfColumns[i]) == 9):
                #String = String + "<td>" + '<a href="https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/' + self.Attributs["PDMV request name"] + '">' + self.Attributs["PDMV request name"] + "</a></td>"
                #String = String + "<td>"+ '<a href="https://cmsweb.cern.ch/reqmgr/view/details/'+self.Attributs["PDMV request name"] + '"> details </a>' + '<a href="https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/'+ self.Attributs["PDMV request name"] + '">' + self.Attributs["PDMV request name"]+"</a> </td>"
                String = String + '<td><a href="https://cmsweb.cern.ch/reqmgr/view/details/%s">details</a> <a href="https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/%s"> %s </a> <a href=https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/%s.gif target=_blank><img src=https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/%s.gif alt="" width=100></a> </td>'%(self.Attributs["PDMV request name"],
                                                                                                                                                                                                                                                                                                                                                                                                                   self.Attributs["PDMV request name"],
                                                                                                                                                                                                                                                                                                                                                                                                                   self.Attributs["PDMV request name"],
                                                                                                                                                                                                                                                                                                                                                                                                                   self.Attributs["PDMV request name"],
                                                                                                                                                                                                                                                                                                                                                                                                                   self.Attributs["PDMV request name"])
                                                                                                                                                                                                                                                                                                                                                                                                                   
            if(int(ListOfColumns[i]) == 10):
                String = String + "<td>" + self.Attributs["PDMV submission date"] + "</td>"
            if(int(ListOfColumns[i]) == 11):
                String = String + "<td>" + str(self.Attributs["PDMV completion eta in DAS"]) + "</td>"
            if(int(ListOfColumns[i]) == 12):
                String = String + "<td>" + self.Attributs["PDMV status in DAS"] + "</td>"
            if(int(ListOfColumns[i]) == 13):
                String = String + "<td>" + '<a href="http://cms.cern.ch/iCMS/prep/requestmanagement?code=' + self.Attributs["PDMV prep id"] + '">' + self.Attributs["PDMV prep id"] + "</a></td>"
            if(int(ListOfColumns[i]) == 14):
                String = String + "<td>" + self.Attributs["PDMV campaign"] + '</td>'
            if(int(ListOfColumns[i]) == 15):
                String = String + '<td><a href="https://cmsweb.cern.ch/das/request?view=list&limit=10&instance=cms_dbs_prod_global&input=dataset+dataset=' + self.Attributs["PDMV data set name"] + '">' + self.Attributs["PDMV data set name"] + "</a></td>"
            if(int(ListOfColumns[i]) == 16):
                String = String + "<td>" + self.Attributs["PDMV status"] + "</td>"
            if(int(ListOfColumns[i]) == 17):
                String = String + "<td>" + self.Attributs["PDMV request"] + "</td>"
            if(int(ListOfColumns[i]) == 18):
                String = String + "<td>" + self.Attributs["PDMV pd pattern"] + "</td>"
            if(int(ListOfColumns[i]) == 19):
                String = String + "<td>" + str(self.Attributs["PDMV present priority"]) + "</td>"
            if(int(ListOfColumns[i]) == 20):
                String = String + "<td>" + self.ProgressBarFunc(self.Attributs["PDMV completion in das"]) + "</td>"
            if(int(ListOfColumns[i]) == 21):
                String = String + "<td>" + str(self.Attributs["PDMV all jobs"]) + "</td>"
            if(int(ListOfColumns[i]) == 22):
                String = String + "<td>" + str(self.Attributs["PDMV pending jobs"]) + "</td>"
            if(int(ListOfColumns[i]) == 23):
                String = String + "<td>" + str(self.Attributs["PDMV monitor time"]) + "</td>"
            if(int(ListOfColumns[i]) == 24):
                String = String + "<td>" + str(self.Attributs["PDMV Perf"]) + "</td>"
            i = i + 1
        String = String + "</tr> \n"
        return String
    
    
    #ProgressBarFunc
    #
    #Generate The Progress Bar of the object simulation which call this function
    def ProgressBarFunc(self, pourcentage):
        PourcentageValue = int(0.7 * pourcentage )#to ge a progressive color in the progressBar !
        return '<div class="progress"><div class="pre" style="background-color:' + self.RGBtoHex(PourcentageValue+ 39, PourcentageValue +77, PourcentageValue + 122) + ';height:20px; width:' + str(pourcentage * 1.5) + 'px;"><div class="text">' + str(pourcentage) + '%</div></div></div>'
    #RGBtoHex
    #
    #Convert a rgb color in HEX value, useful for the Progress Bar Color
    def RGBtoHex(self, r, g, b):
        return "#%02X%02X%02X" % (r, g, b)  
    
class HomePage(object): 
   
    
  
    #index
    #Main function generate the main page
    def index(self, ResToPrint=50, Page=1, SortValue="", Order=False, ID="", EE="", Ty="", SR="", Pr="", RJ="", RD="", EID="", RN="", SuD="", ED="", StD="", PI="", Ca="", DN="", St="", Re="", Pa="", PP="", CD="", AJ="", PJ="", MT="", PF="", Col="15-20-7-11-2-8-4-5-23-9" , Graphic=""): 
        t0 = time.time()  ###original Col="15-20-14-10-7-11-2-8-16-4-5-23"
        MustDrawGraphics = 0
        ColumnForGraph = []
        EventExpectedTot = 0
        EventATM = 0
        ListSearch = []
        ListOfS = []
        if(Graphic != ""):
            ColumnForGraph = Graphic.split("-")
            MustDrawGraphics = len(ColumnForGraph)
        ListOfColumns = Col.split("-")
        if(ID != ""):
            ListSearch.append(ID)
            ListOfS.append(0)
        if(EE != ""):
            ListSearch.append(EE)
            ListOfS.append(1)
        if(Ty != ""):
            ListSearch.append(Ty)
            ListOfS.append(2)
        if(SR != ""):
            ListSearch.append(SR)
            ListOfS.append(3)
        if(Pr != ""):
            ListSearch.append(Pr)
            ListOfS.append(4)
        if(RJ != ""):  
            ListSearch.append(RJ)
            ListOfS.append(5)
        if(RD != ""):
            ListSearch.append(RD)
            ListOfS.append(6)
        if(EID != ""):
            ListSearch.append(EID)
            ListOfS.append(7)
        if(RN != ""):
            ListSearch.append(RN)
            ListOfS.append(8)
        if(SuD != ""):
            ListSearch.append(SuD)
            ListOfS.append(9)
        if(ED != ""):
            ListSearch.append(ED)
            ListOfS.append(10)
        if(StD != ""):
            ListSearch.append(StD)
            ListOfS.append(11)
        if(PI != ""):
            ListSearch.append(PI)
            ListOfS.append(12)
        if(Ca != ""):
            ListSearch.append(Ca)
            ListOfS.append(13)
        if(DN != ""):
            ListSearch.append(DN)
            ListOfS.append(14)
        if(St != ""):
            ListSearch.append(St)
            ListOfS.append(15)
        if(Re != ""):
            ListSearch.append(Re)
            ListOfS.append(16)
        if(Pa != ""):
            ListSearch.append(Pa)
            ListOfS.append(17)
        if(PP != ""):
            ListSearch.append(PP)
            ListOfS.append(18)
        if(CD != ""):
            ListSearch.append(CD)
            ListOfS.append(19)
        if(AJ != ""):
            ListSearch.append(AJ)
            ListOfS.append(20)
        if(PJ != ""):
            ListSearch.append(PJ)
            ListOfS.append(21)
        if(MT != ""):
            ListSearch.append(MT)
            ListOfS.append(22)
        if(PF != ""):
            ListSearch.append(PF)
            ListOfS.append(23)
        try :
            ResToPrint = int(''.join(ResToPrint))
            if(ResToPrint < 0):
                ResToPrint = ResToPrint * -1
            Page = int(''.join(Page))
            if(Page == 0):
                Page = 1
            elif(Page < 0):
                Page = Page * -1
        except:
            ResToPrint = 50
            Page = 1
            SortValue = ""   
        try :
            """
            if(len(ListOfS) > 0):
                ListTemp = list(ListOfSimulations)
                #Increment = 0
                #while(Increment < len(ListSearch) ):
                #    ''.join(ListSearch[Increment])
                #    Increment = Increment + 1
                Increment = 0    
                while(Increment < len(ListOfS)):
                    print("Iteration %s"%(Increment))
                    IncrementC = 0
                    if(type(ListTemp[Increment].Attributs[ListOfAttributs[ListOfS[Increment]]]) == str):
                        ExprToSearch = re.compile(ListSearch[IncrementC])
                        while(IncrementC < len(ListTemp)):
                            if(ExprToSearch.search(ListTemp[IncrementC].Attributs[ListOfAttributs[ListOfS[Increment]]] ) == None):
                                ListTemp.remove(ListTemp[IncrementC])
                                IncrementC = IncrementC - 1
                            else:   
                                if(ListTemp[Increment].Attributs["PDMV expected events"] > 0):
                                    EventExpectedTot = EventExpectedTot + ListTemp[IncrementC].Attributs["PDMV expected events"] 
                                    EventATM = EventATM + ListTemp[IncrementC].Attributs["PDMV evts in DAS"]
                            IncrementC = IncrementC + 1
                    else:
                        while(IncrementC < len(ListTemp)):
                            if(self.ExprSearchEngine(ListSearch[Increment], ListTemp[IncrementC].Attributs[ListOfAttributs[ListOfS[Increment]]]) == 0):
                                ListTemp.remove(ListTemp[IncrementC])
                                IncrementC = IncrementC - 1
                            else:   
                                if(ListTemp[Increment].Attributs["PDMV expected events"] > 0):
                                    EventExpectedTot = EventExpectedTot + ListTemp[Increment].Attributs["PDMV expected events"] 
                                    EventATM = EventATM + ListTemp[Increment].Attributs["PDMV evts in DAS"]
                            IncrementC = IncrementC + 1
                    Increment = Increment + 1

                    
            else:
                i = 0
                ListTemp = ListOfSimulations
                while(i < len(ListTemp)):
                    if(ListTemp[i].Attributs["PDMV expected events"]!= -1):
                        EventExpectedTot = EventExpectedTot + ListTemp[i].Attributs["PDMV expected events"]
                        EventATM = EventATM + ListTemp[i].Attributs["PDMV evts in DAS"]

                    i = i + 1
            """
            ListTemp = list(ListOfSimulations)
            ## implement the search
            for (index,Search) in enumerate(ListSearch):
                Search_Index = ListOfS[index]
                print "Search",Search_Index,Search
                print "\t",len(ListTemp),"elements"
                Search_Attribute = ListOfAttributs[Search_Index]
                print Search_Attribute
                def matching_element(element,search_attr,search_key,search):
                    if type(element.Attributs[search_attr]) == str:
                        ExprToSearch = re.compile(search)
                        return ExprToSearch.search( element.Attributs[search_attr]) != None
                    else:
                        return self.ExprSearchEngine(search, element.Attributs[search_attr]) != 0
                ListTemp = filter( lambda el : matching_element(el, Search_Attribute, Search_Index, Search)==True, ListTemp)

            #anyways, calculate the total number of events and expected from selected
            for items in ListTemp:
                EventExpectedTot+=items.Attributs["PDMV expected events"]
                EventATM+=items.Attributs["PDMV evts in DAS"]
                
        except :
            print "failing EventExpectedTot and EventATM"
            print traceback.format_exc()
            pass
        #print "Counting:",EventATM,EventExpectedTot
        if EventExpectedTot==0:
            CompletionGauge = 0
        else:
            CompletionGauge = int(float(EventATM * 100.0) / float(EventExpectedTot))
            
        if(CompletionGauge > 100):
            CompletionGauge = 100
        if(SortValue != ""):
            if(''.join(Order) == "True"):
                ListTemp.sort(key=itemgetter(ListOfAttributs[int(SortValue) - 1]), reverse=True)
            else:
                ListTemp.sort(key=itemgetter(ListOfAttributs[int(SortValue) - 1]), reverse=False)
        TableHTML = self.ReturnResult(ListTemp, ID, EE, Ty, SR, Pr, RJ, RD, EID, RN, SuD, ED, StD, PI, Ca, DN, St, Re, Pa, PP, CD, AJ, PJ, MT, PF, ListOfColumns,Page,ResToPrint)
        HistoCompl = self.ScaleAndValue(ListTemp, 19, 20, 100)
        i = 0
        HistoPerso = ()
        if(MustDrawGraphics == 1):
            HistoPerso = self.ScaleAndValue(ListTemp, int(ColumnForGraph[0]) - 1, 20)
        elif(MustDrawGraphics == 2):
            HistoPerso=self.ScaleAndValueScatter(ListTemp, int(ColumnForGraph[0]) - 1, int(ColumnForGraph[1]) - 1, 20)
        return '''
        <!DOCTYPE HTML>
        <html>
        <head>
        <title>A CMS monitoring tool website</title>
        <meta name="description" content="This is a CMS monitoring tool website"/>
        <meta name="keywords" content="HTML,CSS,XML,JavaScript"/>
        <meta name="author" content="Guillaume Lastecoueres"/>
        <meta charset="UTF-8" />
        <link rel ="stylesheet" type="text/css" href="style.css"/>
        <script type="text/javascript" src="js/main.js"></script>
        <script type="text/javascript" src="js/d3.v2.min.js"></script>
        </head>
        <body onKeyDown="IsGraph(event.keyCode);" onKeyPress="if (event.keyCode == 13) document.ACMTWSmenu.submit();">
        <div id='holder'></div>
        <div id='holderB'></div> 
        <h3 class="title">A CMS Monitoring Website</h3>
        <div class="headermenu"><h4>Menu</h4></div>
        <form name="ACMTWSmenu" action="." method="get">
        <div class="menu">
        Result to print :<input class="inme" type="number" name="ResToPrint" value="''' + str(ResToPrint) + '''"/><br>
        Page :  <input class="inme" type="number" name="Page" value="''' + str(Page) + '''" /> 
        <input  type="hidden" name="SortValue" value="''' +  SortValue + '''">
        <input  type="hidden" name="Order" value="''' + str(Order) + '''"><br><br><br><a href="#" onclick="document.forms['ACMTWSmenu'].submit();">Print</a>  
        <input  type="hidden" name="Graphic" value="">
        <input  type="hidden" name="Col" value="''' + Col + '''">
        <input  type="submit" style="display:none"/> 
         <a href='#' onclick='if(ListColToDRaw[1] != ""){
                document.forms["ACMTWSmenu"].Graphic.value = ListColToDRaw[0] + "-" + ListColToDRaw[1];
            } else {
                document.forms["ACMTWSmenu"].Graphic.value = ListColToDRaw[0]
            }
           document.forms["ACMTWSmenu"].submit();'>Graph</a>
        <span id="AccordionContainer">
        <span onclick="runAccordion(1);">
        <span class="PanelA">
        <a>Columns</a> 
        </span>
        </span>
        <span  id="PanelAContent">
        Dataset name <input type="checkbox"  onClick="AddCol('15');" ''' + self.CheckedOrNot(ListOfColumns, 15) + '''/><br>
        Completion DAS <input type="checkbox" onClick="AddCol('20');" ''' + self.CheckedOrNot(ListOfColumns, 20) + '''/><br>
        Campaign <input type="checkbox" onClick="AddCol('14');" ''' + self.CheckedOrNot(ListOfColumns, 14) + '''/><br>
        Submission date <input type="checkbox" onClick="AddCol('10');" ''' + self.CheckedOrNot(ListOfColumns, 10) + '''/><br>    
        Running days <input type="checkbox" onClick="AddCol('7');" ''' + self.CheckedOrNot(ListOfColumns, 7) + '''/><br>
        ETA DAS <input type="checkbox" onClick="AddCol('11');" ''' + self.CheckedOrNot(ListOfColumns, 11) + '''/><br>
        Expected Events <input type="checkbox" onClick="AddCol('2');" ''' + self.CheckedOrNot(ListOfColumns, 2) + '''/><br>
        Events DAS <input type="checkbox" onClick="AddCol('8');" ''' + self.CheckedOrNot(ListOfColumns, 8) + '''/><br>
        Status <input type="checkbox" onClick="AddCol('16');" ''' + self.CheckedOrNot(ListOfColumns, 16) + '''/><br>
        Status ReqMngr <input type="checkbox" onClick="AddCol('4');" ''' + self.CheckedOrNot(ListOfColumns, 4) + '''/><br>
        Priority <input type="checkbox" onClick="AddCol('5');" ''' + self.CheckedOrNot(ListOfColumns, 5) + '''/><br>
        Present Priority <input type="checkbox" onClick="AddCol('19');" ''' + self.CheckedOrNot(ListOfColumns, 19) + '''/><br>
        Type <input type="checkbox" onClick="AddCol('3');" ''' + self.CheckedOrNot(ListOfColumns, 3) + '''/><br>
        Prep ID <input type="checkbox" onClick="AddCol('13');" ''' + self.CheckedOrNot(ListOfColumns, 13) + '''/><br>
        Request name <input type="checkbox" onClick="AddCol('9');" ''' + self.CheckedOrNot(ListOfColumns, 9) + '''/><br>
        ID <input type="checkbox" onClick="AddCol('1');" ''' + self.CheckedOrNot(ListOfColumns, 1) + '''/><br>
        Running jobs <input type="checkbox" onClick="AddCol('6');" ''' + self.CheckedOrNot(ListOfColumns, 6) + '''/><br>
        Status DAS <input type="checkbox" onClick="AddCol('12');" ''' + self.CheckedOrNot(ListOfColumns, 12) + '''/><br>
        Request <input type="checkbox" onClick="AddCol('17');" ''' + self.CheckedOrNot(ListOfColumns, 17) + '''/><br>
        All jobs <input type="checkbox" onClick="AddCol('21');" ''' + self.CheckedOrNot(ListOfColumns, 21) + '''/><br>
        Pending jobs <input type="checkbox" onClick="AddCol('22');" ''' + self.CheckedOrNot(ListOfColumns, 22) + '''/><br>
        Monitor Time <input type="checkbox" onClick="AddCol('23');" ''' + self.CheckedOrNot(ListOfColumns, 23) + '''/><br>
        Performance report <input type="checkbox" onClick="AddCol('24');" ''' + self.CheckedOrNot(ListOfColumns, 24) + '''/><br>
        </span>
        </span>
        
        </div>
        
        <table>
        ''' + TableHTML + '''</table>
        </form>
      
        <div id='Graphic' onClick="var Graph = document.getElementById('Graphic');Graph.style.visibility='hidden';document.ACMTWSmenu.Graphic.value=''" ;">
        </div>
        <script>
              HistogramC(''' + str(HistoCompl[0]) + ''','''+str(HistoCompl[1])+''',"#holder",600,250,"'''+str(HistoCompl[2])+'''");
              createGauge("#holderB", "Completion",''' + str(CompletionGauge) + ''');   
        ''' + self.DrawMeAGraph(MustDrawGraphics, HistoPerso) + '''
        </script>
        <p> about ''' + str(len(ListTemp)) + ''' results ( 
        ''' + str(time.time() - t0) + ''') seconds<br>
        Last HeartBeat ''' + DateHeartBeat + '''</p>
        </body>
        </html>
        '''
       

        
    def DrawMeAGraph(self, NbVar, ValueGraphA=""):
        Javascript = "";
        if(NbVar == 1):
            Javascript = '''  Val=''' + str(ValueGraphA) + '''
            GraphPopup = document.getElementById('Graphic');
            GraphPopup.style.visibility='visible';
            var SizeThis= GetSizeWindow();
            HistogramC(''' + str(ValueGraphA[0]) + ''',''' + str(ValueGraphA[1]) + ''',"#Graphic",0.8*SizeThis[0],0.75*SizeThis[1],"''' + str(ValueGraphA[2]) + '''");
            GraphPopup.on
            window.onkeydown = function(event){
           
            if(GraphPopup.style.visibility=='visible')
            {
                if(event.keyCode==37)
                {
                    if(Start>0)
                    {
                        Start=Start-1;
                        Redraw();
                    }
                }
                if(event.keyCode==39)
                {
                    if(Start<''' + str(len(ValueGraphA[0]) - 6) + ''')
                    {
                        Start=Start+1;
                        Redraw();
                    }
                }
                return false;
            }
            }
            function Redraw(){
            GraphPopup = document.getElementById('Graphic');
            GraphPopup.style.visibility='visible';
            GraphPopup.innerHTML = "" ; 
            var SizeThis= GetSizeWindow();
            HistogramC(''' + str(ValueGraphA[0]) + ''',''' + str(ValueGraphA[1]) + ''',"#Graphic",0.8*SizeThis[0],0.75*SizeThis[1],"''' + str(ValueGraphA[2]) + '''");
            }
            window.onresize =function(event){
            Redraw();}'''
        elif(NbVar == 2):
            Javascript = '''
            Data='''+str(ValueGraphA[0])+'''
            ScaleA='''+str(ValueGraphA[1])+'''
            ScaleB='''+str(ValueGraphA[2])+'''
            Label="'''+str(ValueGraphA[3])+'''"
            GraphPopup = document.getElementById('Graphic');
            GraphPopup.style.visibility='visible';
            var SizeThis= GetSizeWindow();
            ScatterPlotC(Data,ScaleA,ScaleB,'#Graphic',0.8*SizeThis[0], 0.75*SizeThis[1],Label);
            window.onresize = function(event) {
            GraphPopup = document.getElementById('Graphic');
            GraphPopup.style.visibility='visible';
            GraphPopup.innerHTML = "" ; 
            var SizeThis= GetSizeWindow();
            ScatterPlotC(Data,ScaleA,ScaleB,'#Graphic',0.8*SizeThis[0], 0.75*SizeThis[1],Label);
            }'''    
        return Javascript
    
    def ScaleAndValueScatter(self, ListA, IndA, IndB, Bins):
        if(len(ListA)>0):
            TypeA = 0
            MaxA=0
            MaxB=0
            TypeB = 0
            i = 0
            Data = []
            Indice = -1
            ValA = ListA[0].Attributs[ListOfAttributs[IndA]]
            ValB = ListA[0].Attributs[ListOfAttributs[IndB]]
            if(type(ValA) == type(0)or(type(ValA) == type(0.0))):
                TypeA = 1
            if(type(ValB) == type(0)or(type(ValB) == type(0.0))):
                TypeB = 1
            if(TypeA):
                i=0
                while(i < len(ListA)):
                        if(MaxA < ListA[i].Attributs[ListOfAttributs[IndA]]):
                            MaxA = ListA[i].Attributs[ListOfAttributs[IndA]]
                        i = i + 1
                StepA = float(MaxA) / float(Bins)
                Round = str(StepA).split(".")
                if((len(Round) > 1)and(int(Round[1]) > 0)):
                    StepA = int(Round[0]) + 1
            if(TypeB):
                i=0
                while(i < len(ListA)):
                        if(MaxB < ListA[i].Attributs[ListOfAttributs[IndB]]):
                            MaxB = ListA[i].Attributs[ListOfAttributs[IndB]]
                        i = i + 1
                StepB = float(MaxB) / float(Bins)
                Round = str(StepB).split(".")
                if((len(Round) > 1)and(int(Round[1]) > 0)):
                    StepB = int(Round[0]) + 1
            i=0
            while(i < len(ListA)):
                if(TypeA and TypeB):
                    ValA = ListA[i].Attributs[ListOfAttributs[IndA]]//StepA
                    ValB = ListA[i].Attributs[ListOfAttributs[IndB]]//StepB  
                elif(TypeA):
                    ValA = ListA[i].Attributs[ListOfAttributs[IndA]]//StepA
                    ValB = ListA[i].Attributs[ListOfAttributs[IndB]]    
                elif(TypeB):
                    ValA = ListA[i].Attributs[ListOfAttributs[IndA]]
                    ValB = ListA[i].Attributs[ListOfAttributs[IndB]]//StepB  
                else:
                    ValA = ListA[i].Attributs[ListOfAttributs[IndA]]
                    ValB = ListA[i].Attributs[ListOfAttributs[IndB]]    
                if(TypeA and ValA>=Bins):
                    ValA=Bins-1
                if(TypeB and ValB>=Bins):
                    ValB=Bins-1
                Indice = self.IsTupleInData(Data, ValA, ValB)
                
                if(Indice == -1):
                        Data.append([ValA, ValB, 1])          
                else:
                    Data[Indice][2] = Data[Indice][2] + 1
                i = i + 1;
            ScaleA=[]
            ScaleB=[]
            if(TypeA):
                i = 0
                while(i <= (Bins * StepA)+1):
                    ScaleA.append(i)
                    i = i + StepA
            if(TypeB):
                i = 0
                while(i <= Bins * StepB):
                    ScaleB.append(i)
                    i = i + StepB
                    
            return (Data, ScaleA,ScaleB, str(ListOfAttributs[IndA]+"/"+ListOfAttributs[IndB]))
                            
                        
    def IsTupleInData(self, Data, ValA, ValB):
        i = 0
        while(i < len(Data)):
            if((Data[i][0] == ValA)and(Data[i][1] == ValB)):
                return i
            i = i + 1
        return -1
                
                    
    def ScaleAndValue(self, ListA, Ind, Bins, Max=0):
        i = 0
        ValuesA = []
        ScaleA = []
        if(len(ListA) > 0):
            if(type(ListA[i].Attributs[ListOfAttributs[Ind]]) == type(0)or(type(ListA[i].Attributs[ListOfAttributs[Ind]]) == type(0.0))):
                while(i < Bins):
                    ValuesA.append(0);
                    i = i + 1
                i = 0
                if(Max == 0):
                    while(i < len(ListA)):
                        if(Max < ListA[i].Attributs[ListOfAttributs[Ind]]):
                            Max = ListA[i].Attributs[ListOfAttributs[Ind]]
                        i = i + 1
                i = 0
                Step = float(Max) / float(Bins)
                Round = str(Step).split(".")
                if((len(Round) > 1)and(int(Round[1]) > 0)):
                    Step = int(Round[0]) + 1
                
                while(i < len(ListA)):
                    if(ListA[i].Attributs[ListOfAttributs[Ind]] >= Max):
                        ValuesA[Bins - 1] = ValuesA[Bins - 1] + 1
                    elif(ListA[i].Attributs[ListOfAttributs[Ind]] < 0):
                        ValuesA[0] = ValuesA[0] + 1
                    else:
                        ValuesA[int(ListA[i].Attributs[ListOfAttributs[Ind]] // Step)] = ValuesA[int(ListA[i].Attributs[ListOfAttributs[Ind]] // Step)] +1
                    i = i + 1
                i=0
                while(i <= Bins * Step):
                    ScaleA.append(i)
                    i = i + Step
            else:
                while(i < len(ListA)):
                    if(ScaleA.count(str(ListA[i].Attributs[ListOfAttributs[Ind]])) == 0):
                        ScaleA.append(str(ListA[i].Attributs[ListOfAttributs[Ind]]))
                        ValuesA.append(1)
                    else:
                        ValuesA[ScaleA.index(str(ListA[i].Attributs[ListOfAttributs[Ind]]))] = ValuesA[ScaleA.index(str(ListA[i].Attributs[ListOfAttributs[Ind]]))] + 1
                    i = i + 1
        return (ValuesA, ScaleA, ListOfAttributs[Ind]);
        
    def MaxProtected(self, List):
        if(len(List) > 0):
            return str(max(List))
        else :
            return "0"
        
    def CheckedOrNot(self, listA, eltofind):
        String = ""
        i = 0
        while(i < len(listA)):
            if(int(listA[i]) == eltofind):
                String = 'checked="checked"'
                i = len(listA)
            i = i + 1
        return String
    def ExprSearchEngine(self, expr, chaine):
        try :
            expr = expr.lower()
            expr = expr.replace("value", "")
            ListConditionOr = expr.split("or")
            Victory = 0
            IncrementA = 0
            while(IncrementA < len(ListConditionOr)):
                ListConditionAnd = ListConditionOr[IncrementA].split("and")
                IncrementB = 0
                PreVictory = 1 
                while(IncrementB < len(ListConditionAnd)):
                    if(PreVictory == 1):
                        expr = ListConditionAnd[IncrementB]
                        expr = expr.strip()
                        if(expr.find(">=") != -1):
                            Position = expr.find(">=")
                            expr = expr.replace(">=", "")
                            if(Position == 0):
                                if(float(expr) > float(chaine)):
                                    PreVictory = 0
                            else:
                                if(float(expr) < float(chaine)):
                                    PreVictory = 0
                        elif(expr.find("<=") != -1):
                            Position = expr.find("<=")
                            expr = expr.replace("<=", "")
                            if(Position == 0):
                                if(float(expr) < float(chaine)):
                                    PreVictory = 0
                            else:
                                if(float(expr) > float(chaine)):
                                    PreVictory = 0
                        elif(expr.find("<") != -1):
                            Position = expr.find("<")
                            expr = expr.replace("<", "")
                            if(Position == 0):
                                if(float(expr) <= float(chaine)):
                                    PreVictory = 0
                            else:
                                if(float(expr) >= float(chaine)):
                                    PreVictory = 0
                        elif(expr.find(">") != -1):
                            Position = expr.find(">")
                            expr = expr.replace(">", "")
                            if(Position == 0):
                                if(float(expr) >= float(chaine)):
                                    PreVictory = 0
                            else:
                                if(float(expr) <= float(chaine)):
                                    PreVictory = 0
                        else:
                            expr = expr.replace("=", "")
                            if(float(expr) != float(chaine)):
                                PreVictory = 0
                    IncrementB = IncrementB + 1
                if(PreVictory == 1):
                    Victory = 1
                    IncrementB = len(ListConditionAnd)
                    IncrementA = len(ListConditionOr)
                IncrementA = IncrementA + 1 
            return Victory
        except:
            return 1
    
    def ReturnResult(self, ListB, ID, EE, Ty, SR, Pr, RJ, RD, EID, RN, SuD, ED, StD, PI, Ca, DN, St, Re, Pa, PP, CD, AJ, PJ, MT, PF, ListOfColumns,Page,ResultToPrint):
        String = "<tr>"
        i = 0
        while(i < len(ListOfColumns)): 
            if(int(ListOfColumns[i]) == 1):
                String = String + '''<th id="S1"><p><span class="s2" onClick="SortChangeValueB('1','False');"></span>  <span onClick="SelectCol('1');">ID  </span><span class="s3" onClick="SortChangeValueB('1','True');"></span></p><input type="text" onClick="" name="ID" value="''' + str(ID) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 2):
                String = String + '''<th id="S2"><p><span class="s2" onClick="SortChangeValueB('2','False');"></span>  <span onClick="SelectCol('2');">Expected Events</span>   <span class="s3" onClick="SortChangeValueB('2','True');"></span></p><input type="text" onClick="" name="EE" value="''' + str(EE) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 3):
                String = String + '''<th id="S3"><p><span class="s2" onClick="SortChangeValueB('3','False');"></span>  <span onClick="SelectCol('3');"> Type </span>  <span class="s3" onClick="SortChangeValueB('3','True');"></span></p><input type="text" onClick="" name="Ty" value="''' + str(Ty) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 4):
                String = String + '''<th id="S4"><p><span class="s2" onClick="SortChangeValueB('4','False');"></span>  <span onClick="SelectCol('4');">Status ReqMngr</span><span class="s3" onClick="SortChangeValueB('4','True');"></span></p><input type="text" onClick="" name="SR" value="''' + str(SR) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 5):
                String = String + '''<th id="S5"><p><span class="s2" onClick="SortChangeValueB('5','False');"></span>  <span onClick="SelectCol('5');">Priority </span><span class="s3" onClick="SortChangeValueB('5','True');"></span></p><input type="text" onClick="" name="Pr" value="''' + str(Pr) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 6):
                String = String + '''<th id="S6"><p><span class="s2" onClick="SortChangeValueB('6','False');"></span>  <span onClick="SelectCol('6');">Running jobs </span><span class="s3" onClick="SortChangeValueB('6','True');"></span></p><input type="text" onClick="" name="RJ" value="''' + str(RJ) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 7):
                String = String + '''<th id="S7"><p><span class="s2" onClick="SortChangeValueB('7','False');"></span>  <span onClick="SelectCol('7');"> Running days </span><span class="s3" onClick="SortChangeValueB('7','True');"></span></p><input type="text" onClick="" name="RD" value="''' + str(RD) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 8):
                String = String + '''<th id="S8"><p><span class="s2" onClick="SortChangeValueB('8','False');"></span> <span onClick="SelectCol('8');"> Events DAS  </span><span class="s3" onClick="SortChangeValueB('8','True');"></span></p><input type="text" onClick="" name="EID" value="''' + str(EID) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 9):
                String = String + '''<th id="S9"><p><span class="s2" onClick="SortChangeValueB('9','False');"></span> <span onClick="SelectCol('9');"> Request name  </span><span class="s3" onClick="SortChangeValueB('9','True');"></span></p><input type="text" onClick="" name="RN" value="''' + str(RN) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 10):    
                String = String + '''<th id="S10"><p><span class="s2" onClick="SortChangeValueB('10','False');"></span> <span onClick="SelectCol('10');"> Submission date  </span><span class="s3" onClick="SortChangeValueB('10','True');"></span></p><input type="text" onClick="" name="SuD" value="''' + str(SuD) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 11):
                String = String + '''<th id="S11"><p><span class="s2" onClick="SortChangeValueB('11','False');"></span>  <span onClick="SelectCol('11');">ETA DAS  </span><span class="s3" onClick="SortChangeValueB('11','True');"></span></p><input type="text" onClick="" name="ED" value="''' + str(ED) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 12):
                String = String + '''<th  id="S12"><p><span class="s2" onClick="SortChangeValueB('12','False');"></span> <span onClick="SelectCol('12');"> Status DAS  </span><span class="s3" onClick="SortChangeValueB('12','True');"></span></p><input type="text" onClick="" name="StD" value="''' + str(StD) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 13):
                String = String + '''<th id="S13"><p><span class="s2" onClick="SortChangeValueB('13','False');"></span>  <span onClick="SelectCol('13');">Prep ID  </span><span class="s3" onClick="SortChangeValueB('13','True');"></span></p><input type="text" onClick="" name="PI" value="''' + str(PI) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 14):
                String = String + '''<th  id="S14"><p><span class="s2" onClick="SortChangeValueB('14','False');"></span> <span onClick="SelectCol('14');"> Campaign  </span><span class="s3" onClick="SortChangeValueB('14','True');"></span></p><input type="text" onClick="" name="Ca" value="''' + str(Ca) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 15):
                String = String + '''<th id="S15"><p><span class="s2" onClick="SortChangeValueB('15','False');"></span>  <span onClick="SelectCol('15');">Dataset name </span> <span class="s3" onClick="SortChangeValueB('15','True');"></span></p><input type="text" onClick="" name="DN" value="''' + str(DN) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 16):
                String = String + '''<th  id="S16"><p><span class="s2" onClick="SortChangeValueB('16','False');"></span>  <span onClick="SelectCol('16');">Status </span> <span class="s3" onClick="SortChangeValueB('16','True');"></span></p><input type="text" onClick="" name="St" value="''' + str(St) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 17):
                String = String + '''<th  id="S17"><p><span class="s2" onClick="SortChangeValueB('17','False');"></span>  <span onClick="SelectCol('17');">Request </span> <span class="s3" onClick="SortChangeValueB('17','True');"></span></p><input type="text" onClick="" name="Re" value="''' + str(Re) + '''"/></th>'''
            #if(int(ListOfColumns[i]) == 18):
                #String = String + '''<th  id="S18"><p><span class="s2" onClick="SortChangeValueB('18','False');"></span>  <span onClick="SelectCol('18');">Pattern </span> <span class="s3" onClick="SortChangeValueB('18','True');"></span></p><input type="text" onClick="" name="Pa" value="''' + str(Pa) + '''"/></th>''' # not used anymore
            if(int(ListOfColumns[i]) == 19):
                String = String + '''<th  id="S19"><p><span class="s2" onClick="SortChangeValueB('19','False');"></span>  <span onClick="SelectCol('19');">Present Priority </span> <span class="s3" onClick="SortChangeValueB('19','True');"></span></p><input type="text" onClick="" name="PP" value="''' + str(PP) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 20):
                String = String + '''<th  id="S20"><p><span class="s2" onClick="SortChangeValueB('20','False');"></span>  <span onClick="SelectCol('20');">Completion DAS </span><span class="s3" onClick="SortChangeValueB('20','True');"></span></p><input type="text" onClick="" name="CD" value="''' + str(CD) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 21):
                String = String + '''<th  id="S21"><p><span class="s2" onClick="SortChangeValueB('21','False');"></span>  <span onClick="SelectCol('21');">All jobs </span> <span class="s3" onClick="SortChangeValueB('21','True');"></span></p><input type="text" onClick="" name="AJ" value="''' + str(AJ) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 22):
                String = String + '''<th  id="S22"><p><span class="s2" onClick="SortChangeValueB('22','False');"></span>  <span onClick="SelectCol('22');">Pending jobs </span> <span class="s3" onClick="SortChangeValueB('22','True');"></span></p><input type="text" onClick="" name="PJ" value="''' + str(PJ) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 23):
                String = String + '''<th  id="S23"><p><span class="s2" onClick="SortChangeValueB('23','False');"></span>  <span onClick="SelectCol('23');">Monitor Time </span> <span class="s3" onClick="SortChangeValueB('23','True');"></span></p><input type="text" onClick="" name="MT" value="''' + str(MT) + '''"/></th>'''
            if(int(ListOfColumns[i]) == 24):
                String = String + '''<th  id="S24"><p><span class="s2" onClick="SortChangeValueB('24','False');"></span>  <span onClick="SelectCol('24');">Performance report</span> <span class="s3" onClick="SortChangeValueB('24','True');"></span></p><input type="text" onClick="" name="PF" value="''' + str(PF) + '''"/></th>'''
            
            i = i + 1
        String = String + "</tr>"
        From = (Page - 1) * ResultToPrint
        To = Page * ResultToPrint
        while((From < To)and(From < len(ListB))):
            String = String + ListB[From].toString((From % 2), ListOfColumns)
            From = From + 1
        return String
    index.exposed = True 
   
class Initializer(object):
    
    def Actualization(self):
        possible_source = ['file','web','db']
        source = 'db'
        if source == 'web':
            response = urllib2.urlopen('http://vlimant.web.cern.ch/vlimant/Directory/summer12/stats/stats_json.txt')
            jsonContent = json.loads(response.read())
        elif source =='file':
            JSONFile = open('/build/Media/stats_json.txt', 'r') #default value
            #JSONFile = open('stats_json.txt', 'r') # for local tests only
            jsonContent = json.loads(JSONFile.read())
        elif source == 'db':
            ### NEW super cool stuff
            dbData = urllib2.urlopen('http://cms-pdmv-stats:5984/stats/_all_docs?include_docs=true')
            jsonContent = map(lambda c: c['doc'], filter(lambda r : not r['id'].startswith('_'), json.loads(dbData.read())['rows']))
        
        ## no L = Content.split("{'pdmv")
        i = 1    
        while(i < len(jsonContent)):
            Sim = Simulation()
            Sim._init_()
            Sim.Attributs["SIMID"] = i
            ### print jsonContent[i]
            #noSim.Attributs["PDMV expected events"] = self.getInt(L[i], 'ts": ')
            Sim.Attributs["PDMV expected events"] = int(jsonContent[i]["pdmv_expected_events"])
            #noSim.Attributs["PDMV type"] = self.getStr(L[i], 'pe": ')
            Sim.Attributs["PDMV type"] = str(jsonContent[i]["pdmv_type"])
            #noSim.Attributs["PDMV status from reqmngr"] = self.getStr(L[i], 'gr": ')
            Sim.Attributs["PDMV status from reqmngr"] = str(jsonContent[i]["pdmv_status_from_reqmngr"])
            #noSim.Attributs["PDMV priority"] = self.getInt(L[i], 'v_priority": ')
            Sim.Attributs["PDMV priority"] = int(jsonContent[i]["pdmv_priority"])
            #noSim.Attributs["PDMV running jobs"] = self.getInt(L[i], 'ning_jobs": ')
            Sim.Attributs["PDMV running jobs"] = int(jsonContent[i]["pdmv_running_jobs"])
            #noSim.Attributs["PDMV running days"] = self.getInt(L[i], 'ys": ')
            Sim.Attributs["PDMV running days"] = int(jsonContent[i]["pdmv_running_days"])
            #noSim.Attributs["PDMV evts in DAS"] = self.getInt(L[i], 'ts_in_DAS": ')
            Sim.Attributs["PDMV evts in DAS"] = int(jsonContent[i]["pdmv_evts_in_DAS"])
            #noSim.Attributs["PDMV request name"] = self.getStr(L[i], 'st_name": ')
            Sim.Attributs["PDMV request name"] = str(jsonContent[i]["pdmv_request_name"])
            #noSim.Attributs["PDMV submission date"] = self.getStr(L[i], 'n_date": ')
            Sim.Attributs["PDMV submission date"] = str(jsonContent[i]["pdmv_submission_date"])
            #noSim.Attributs["PDMV completion eta in DAS"] = self.getFloat(L[i], 'ta_in_DAS": ')
            Sim.Attributs["PDMV completion eta in DAS"] = float(jsonContent[i]["pdmv_completion_eta_in_DAS"])
            #noSim.Attributs["PDMV status in DAS"] = self.getStr(L[i], 'us_in_DAS": ')
            Sim.Attributs["PDMV status in DAS"] = str(jsonContent[i]["pdmv_status_in_DAS"])
            #noSim.Attributs["PDMV prep id"] = self.getStr(L[i], 'p_id": ')
            Sim.Attributs["PDMV prep id"] = str(jsonContent[i]["pdmv_prep_id"])
            #noSim.Attributs["PDMV campaign"] = self.getStr(L[i], 'gn": ')
            Sim.Attributs["PDMV campaign"] = str(jsonContent[i]["pdmv_campaign"])
            #noDataSetName_Before_treatment = self.getStr(L[i], 'et_name": ')
            DataSetName_Before_treatment = str(jsonContent[i]["pdmv_dataset_name"])
            if((DataSetName_Before_treatment == "None Yet")or(DataSetName_Before_treatment == "?")):
                DataSetName_Before_treatment = ""
            Sim.Attributs["PDMV data set name"] = DataSetName_Before_treatment
            #noSim.Attributs["PDMV status"] = self.getStr(L[i], 'us": ')
            Sim.Attributs["PDMV status"] = str(jsonContent[i]["pdmv_status"])
            #noSim.Attributs["PDMV request"] = self.getStr(L[i], 't_id": ')
            Sim.Attributs["PDMV request"] = str(jsonContent[i]["pdmv_request"]["request_id"])
            #noSim.Attributs["PDMV pd_pattern"] = self.getStr(L[i], 'rn": ')
            #noSim.Attributs["PDMV present priority"] = self.getInt(L[i], 't_priority": ')
            Sim.Attributs["PDMV present priority"] = int(jsonContent[i]["pdmv_present_priority"])
            #noCompletion_in_DAS_Before_Treatement = self.getFloat(L[i], 'ion_in_DAS": ')
            Completion_in_DAS_Before_Treatement = float(jsonContent[i]["pdmv_completion_in_DAS"])
            if(Completion_in_DAS_Before_Treatement <= 0):
                Completion_in_DAS_Before_Treatement = +0.0
            elif(Completion_in_DAS_Before_Treatement > 100):
                Completion_in_DAS_Before_Treatement = 100.0
            Sim.Attributs["PDMV completion in das"] = Completion_in_DAS_Before_Treatement
            #noSim.Attributs["PDMV all jobs"] = self.getInt(L[i], 'l_jobs": ')
            Sim.Attributs["PDMV all jobs"] = int(jsonContent[i]["pdmv_all_jobs"])
            #noSim.Attributs["PDMV pending jobs"] = self.getInt(L[i], 'ding_jobs": ')
            Sim.Attributs["PDMV pending jobs"] = int(jsonContent[i]["pdmv_pending_jobs"])
            #noSim.Attributs["PDMV monitor time"] = self.getStr(L[i], 'time": ')
            Sim.Attributs["PDMV monitor time"] = str(jsonContent[i]["pdmv_monitor_time"])
            if 'pdmv_performance' in jsonContent[i]:
                adds_on=[]
                for (step,value) in jsonContent[i]['pdmv_performance'].items():
                    adds_on.append('%s: %.2f s/evt'%(step.split('/')[-1],value))
                Sim.Attributs["PDMV Perf"] = ', '.join(adds_on)

            ## put in at the end
            ListOfSimulationsTemp.append(Sim)
            i = i + 1
        del(ListOfSimulations[:])
        i = 0
        while(i < len(ListOfSimulationsTemp)):
            ListOfSimulations.append(ListOfSimulationsTemp[i])
            i = i + 1
        threading.Timer(900,self.Actualization).start() 
        global DateHeartBeat 
        DateHeartBeat = time.strftime('%d/%m/%y %H:%M', time.localtime())  
        del(ListOfSimulationsTemp[:])
      
    def getStr(self, string, key):
        i = string.find(key)
        loopIndicator = 0
        length = len(key)
        subString = []
        while((string[loopIndicator + i + length] != ",")and(string[loopIndicator + i + length] != "}")):
            subString.append(string[i + loopIndicator + length])
            loopIndicator = loopIndicator + 1
            if("'" in subString):
                subString.remove("'")
        return str(''.join(subString))
    
    def getInt(self, string, key):
        i = string.find(key)
        loopIndicator = 0
        length = len(key)
        subString = []
        while((string[loopIndicator + i + length] != ",")and(string[loopIndicator + i + length] != "}")):
            subString.append(string[i + loopIndicator + length])
            loopIndicator = loopIndicator + 1
            if("'" in subString):
                subString.remove("'")
        return int(''.join(subString))
    def getFloat(self, string, key):
        position = string.find(key)
        loopIndicator = 0
        length = len(key)
        PreCalcIndice = position + length 
        subString = []
        while((string[loopIndicator + PreCalcIndice] != ",")and(string[loopIndicator + PreCalcIndice] != "}")):
            subString.append(string[loopIndicator + PreCalcIndice])
            loopIndicator = loopIndicator + 1
            if("'" in subString):
                subString.remove("'")
        return float(''.join(subString))

    Actualization.exposer = True 

DateHeartBeat = "Heart Attack"
ListOfSimulationsTemp = list()
ListOfSimulations = list()
ListOfAttributs = ["SIMID",  #0
                   "PDMV expected events",
                   "PDMV type",
                   "PDMV status from reqmngr",
                   "PDMV priority",
                   "PDMV running jobs",
                   "PDMV running days", #6
                   "PDMV evts in DAS", #7
                   "PDMV request name", #8
                   "PDMV submission date", #9
                   "PDMV completion eta in DAS", #10
                   "PDMV status in DAS",
                   "PDMV prep id",
                   "PDMV campaign",
                   "PDMV data set name",
                   "PDMV status",
                   "PDMV request",
                   "PDMV pd pattern",
                   "PDMV present priority",
                   "PDMV completion in das",
                   "PDMV all jobs",#20
                   "PDMV pending jobs",#21
                   "PDMV monitor time", #22
                   "PDMV Perf"]  #23