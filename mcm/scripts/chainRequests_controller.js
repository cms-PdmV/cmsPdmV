function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [
    {text:'PrepId',select:true, db_name:'prepid'},
    {text:'Actions',select:true, db_name:''},
    {text:'Approval',select:true, db_name:'approval'},
 	  {text:'Chain',select:true, db_name:'chain'},
  ];
  $scope.update = [];
  $scope.show_well = false;
  $scope.chained_campaigns = [];
  $scope.filt = {};
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "chained_requests";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }
  
  $scope.searchable_fields = [{"name":"generators", "value":""},{"name":"energy", "value":""},{"name":"notes", "value":""},{"name":"dataset_name", "value":""},{"name":"pwg","value":""},{"name":"status", "value":""},{"name":"approval","value":""}];
  $search_data = {};
  $scope.new = {};
  $scope.selectedAll = false;
  $scope.underscore = _;
  $scope.puce = {};
  $scope.r_status = {};
  $scope.selected_prepids = [];
  $scope.action_report = {};
  $scope.action_status = {};
  $scope.local_requests = {};
  $scope.tabsettings = {
    "view":{
      active:false
    },
    "search":{
      active:false
    },
    "navigation":{
      active:false
    },
    "navigation2":{
      active:false
    }
  };

  if($location.search()["page"] === undefined){
    page = 0;
    $location.search("page", 0);
    $scope.list_page = 0;
  }else{
    page = $location.search()["page"];
    $scope.list_page = parseInt(page);
  }

  $scope.load_puce = function(prepid){
    for (i=0;i<$scope.result.length;i++){
	    if ($scope.result[i].prepid == prepid ){
		    chains = $scope.result[i].chain;
		     //console.log("Found chain",chains);
		    for (i=0; i<chains.length; i++){
		      prepid=chains[i];
		      // if already present. remove it to redisplay properly
		      if (_.keys($scope.puce).indexOf(prepid)!=-1 && $scope.puce [ prepid ]!= undefined ){
			      $scope.puce [ prepid ] = undefined;
			      $scope.r_status [ prepid ] = undefined;
		      }else{
			      $scope.puce[prepid] = 'processing-bg.gif';
			      $http({method:'GET', url: 'public/restapi/requests/get_status/'+prepid}).success(function(data,status){
				      r_prepid=_.keys(data)[0];
				      r_status = data[r_prepid];
				      $scope.r_status[ r_prepid ] = r_status;
				      status_map = { 'done' : 'led-green.gif',
						     'submitted' : 'led-blue.gif',
						     'approved' : 'led-orange.gif',
						     'defined' : 'led-orange.gif',
						     'validation' : 'led-red.gif',
						     'new' : 'led-red.gif'}
				      if (status_map[r_status]){
				        $scope.puce[ r_prepid ] = status_map[r_status];
              }else{
				        $scope.puce[ r_prepid ] = 'icon-question-sign';
				      }
				      //console.log("puce",$scope.puce);
			      }).error(function(status){
				      alert('cannot get status for '+r_prepid);
				    });
		      }
		    }
	    }
	  }
	//i = $scope.result.indexOf(prepid);
	//this_one=$scope.result[i];
	//console.log($scope.result)
	//	console.log(prepid,i,this_one);
	//["puce"] = ['icon-signal','icon-signal'];
  };

  $scope.delete_object = function(db, value){
    $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
      if (data["results"]){
        alert('Object was deleted successfully.');
      }else{
        alert('Could not delete because '+data['message']);
      }
    }).error(function(status){
      alert('Error no.' + status + '. Could not delete object.');
    });
  };

  $scope.single_step = function(step, prepid, extra){
    $http({method:'GET', url: 'restapi/'+$scope.dbName+'/'+step+'/'+prepid+extra}).success(function(data,status){
      $scope.parse_report([data],status);
    }).error(function(status){
      $scope.set_fail(status);
    });
  };

  $scope.select_all_well = function(){
    $scope.selectedCount = true;
    var selectedCount = 0
    _.each($scope.defaults, function(elem){
      if (elem.select){
        selectedCount +=1;
      }
      elem.select = true;
    });
    if (selectedCount == _.size($scope.defaults)){
      _.each($scope.defaults, function(elem){
        elem.select = false;
      });
      $scope.defaults[0].select = true; //set prepid to be enabled by default
      $scope.defaults[1].select = true; // set actions to be enabled
      $scope.defaults[2].select = true; // set actions to be enabled
      $scope.defaults[3].select = true; // set actions to be enabled
      $scope.selectedCount = false;
    }
  };

  $scope.delete_edit = function(id){
    $scope.delete_object($location.search()["db_name"], id);
  };

  $scope.sort = {
    column: 'prepid',
      descending: false
  };

  $scope.selectedCls = function(column) {
    return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
  };

  $scope.changeSorting = function(column) {
    var sort = $scope.sort;
    if (sort.column == column) {
      sort.descending = !sort.descending;
    } else {
      sort.column = column;
      sort.descending = false;
    }
  };

  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }
    else{
      $scope.show_well = true;
    }
  };

  $scope.statusIcon = function(value){
    icons = {'new' :  'icon-edit',
	       'validation' : 'icon-eye-open',
	       'defined' : 'icon-check',
	       'approved' : 'icon-share',
	       'submitted' : 'icon-inbox',
	       'injected' : 'icon-envelope',
	       'done' : 'icon-ok'
    }
    if (icons[value]){
	    return icons[value] ;
    }else{
	    return "icon-question-sign" ;
    }
  };

  $scope.approvalIcon = function(value){
    icons = { 'none':'icon-off',
		//'validation' : 'icon-eye-open',
		//		'define' : 'icon-check',
		  'flow' : 'icon-share',
		  'submit' : 'icon-ok'}
    if (icons[value]){
      return icons[value] ;
    }else{
	    return "icon-question-sign";
    }
  };
  $scope.parseColumns = function()
  {
    if ($scope.result.length != 0){
      columns = _.keys($scope.result[0]);
      rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
//       $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
      _.each(rejected, function(v){
        add = true;
        _.each($scope.defaults, function(column){
          if (column.db_name == v){
            add = false;
          }
        });
        if (add){
          $scope.defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
        }
      });
      if ( _.keys($location.search()).indexOf('fields') == -1)
      {
        var shown = "";
        if ($.cookie($scope.dbName+"shown") !== undefined){
          shown = $.cookie($scope.dbName+"shown");
        }
        if ($location.search()["shown"] !== undefined){
          shown = $location.search()["shown"]
        }
        if (shown != ""){
          $location.search("shown", shown);
          binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
          _.each($scope.defaults, function(column){
            column_index = $scope.defaults.indexOf(column);
            binary_bit = binary_shown.charAt(column_index);
            if (binary_bit!= ""){ //if not empty -> we have more columns than binary number length
              if (binary_bit == 1){
                column.select = true;
              }else{
                column.select = false;
              }
            }else{ //if the binary index isnt available -> this means that column "by default" was not selected
              column.select = false;
            }
          });
        }
      }
      else
      {
        _.each($scope.defaults, function(elem){
          elem.select = false;
        });
        _.each($location.search()['fields'].split(','), function(column){
          _.each($scope.defaults, function(elem){
            if ( elem.db_name == column )
            {
              elem.select = true;
            }
          });
        });
      }
    }
  };

  $scope.getData = function(){
    if ( ! $location.search()['searchByRequests']){
      var query = ""
      _.each($location.search(), function(value,key){
        if (key!= 'shown' && key != 'fields'){
          query += "&"+key+"="+value;
        }
      });
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
      promise.then(function(data){
        $scope.got_results = true;
        $scope.result = data.data.results;
        $scope.parseColumns();
      },function(){
         alert("Error getting information");
      });
    }else{
      var list_of_chain = [];
      //lets get requests data
      var query = ""
      _.each($location.search(), function(value, key){
        if (key != 'shown' && key != 'fields' && key != 'searchByRequests'){
          query += "&"+key+"="+value;
        }
      });
      var promise1 = $http.get("search/?db_name=requests"+query);
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      promise1.then(function(data){  //we get data from requests DB;
        if (data.data.results.length != 0)
        {
          _.each(data.data.results, function(elem){
            list_of_chain = _.union(list_of_chain, elem.member_of_chain); //parse it and make a list of unique chained requests
          });
          var promise2 = $http.get("restapi/"+$scope.dbName+"/get/"+list_of_chain.join(",")); //we get chained requests as ussual
          promise2.then(function(data){
            $scope.got_results = true;
            $scope.result = data.data.results;
            $scope.parseColumns();
          },function(){
             alert("Error getting information");
          });
        }else{
          $scope.result = [];
          $scope.got_results = true;
        }
      });
    }
  };
  $scope.$watch('list_page', function(){
    if($location.search()["supersearch"])
    {
      
      _.each($location.search(),function(elem,key){
      if(key != "supersearch" || key != "page"){
        _.each($scope.searchable_fields, function(el){
          if (el["name"] == key)
          {
            el["value"] = elem;
          }
        });
      }
      });
      $scope.superSearch($scope.searchable_fields);
    }else
    {
      $scope.getData();
    }
    $scope.selected_prepids = [];
  });

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.defaults, function(column){ //iterate all columns
      if(column.select){
        bin_string ="1"+bin_string; //if selected add 1 to binary interpretation
      }else{
        bin_string ="0"+bin_string;
      }
    });
    $location.search("shown",parseInt(bin_string,2)); //put into url the interger of binary interpretation
  };
  
  $scope.previous_page = function(current_page){
    if (current_page >-1){
      $location.search("page", current_page-1);
      $scope.list_page = current_page-1;
    }
  };

  $scope.next_page = function(current_page){
    if ($scope.result.length !=0){
      $location.search("page", current_page+1);
      $scope.list_page = current_page+1;
    }
  };

  $scope.flowChainedRequest = function(prepid, force){
    var promise = $http.get("restapi/"+$scope.dbName+"/flow/"+prepid+force);
    promise.then(function(data){
      $scope.parse_report([data.data],status);
    }, function(data){
      $scope.set_fail(data.status);
    });
  };

  $scope.add_to_selected_list = function(prepid){
    if (_.contains($scope.selected_prepids, prepid)){
        $scope.selected_prepids = _.without($scope.selected_prepids,prepid)
    }else
        $scope.selected_prepids.push(prepid);
  };

  $scope.multiple_step = function(step, extra){
    if ($scope.selected_prepids.length > 0){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/'+step+'/'+$scope.selected_prepids.join()+extra}).success(function(data,status){
        $scope.parse_report(data,status);
      }).error(function(status){
        $scope.set_fail(status);
      });
    }else{
      alert("No requests selected");
    };
  };

  $scope.multiple_flow = function(){
    if ($scope.selected_prepids.length > 0){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/flow/'+$scope.selected_prepids.join()}).success(function(data,status){
        $scope.parse_report(data,status);
      }).error(function(status){
        $scope.set_fail(status);
      });
    }else{
      alert("No requests selected");
    };
  };
 
  $scope.multiple_load = function(){
    for (i_load=0; i_load< $scope.selected_prepids.length; i_load++){
	    $scope.load_puce( $scope.selected_prepids[i_load] );
    }
  };

  $scope.toggleAll = function(){
    if ($scope.selected_prepids.length != $scope.result.length){
      _.each($scope.result, function(v){
        $scope.selected_prepids.push(v.prepid);
      });
      $scope.selected_prepids = _.uniq($scope.selected_prepids);
    }else{
      $scope.selected_prepids = [];
    }
  };
  $scope.parse_report = function(data,status){
    to_reload=true;
    for (i=0;i<data.length;i++){
    $scope.action_status[data[i]['prepid']] = data[i]['results'];
    if ( data[i]['results'] == true)
        {
      $scope.action_report[data[i]['prepid']] = 'OK';
        }
    else
        {
      $scope.action_report[data[i]['prepid']] = data[i]['message'];
      to_reload=false;
        }
      }      
      if (to_reload == true)
    {
        $scope.set_success(status);
    }
      else
    {
        $scope.set_fail(status);
    }
  };
  $scope.set_fail = function(status){
    $scope.update["success"] = false;
    $scope.update["fail"] = true; 
    $scope.update["status_code"] = status; 
  };
  $scope.set_success = function(status){
    $scope.update["success"] = true;
    $scope.update["fail"] = false; 
    $scope.update["status_code"] = status; 
    $scope.getData();
  };
  $scope.saveCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    if($location.search()["shown"]){
      $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 })
    }
  };
  $scope.useCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    var shown = $.cookie(cookie_name);
    binary_shown = parseInt(shown).toString(2).split('').reverse().join('');
    _.each($scope.defaults, function(elem,index){
      if (binary_shown.charAt(index) == 1){
        elem.select = true;
      }else{
        elem.select = false;
      }
    });
  };
  $scope.superSearch = function(data){
    _.each($location.search(),function(elem,key){
      $location.search(key,null);
    });
    var search_data={};
    _.each($scope.searchable_fields, function(elem){
      if (elem.value !=""){
        $location.search(elem.name,elem.value);
        search_data[elem.name] = elem.value;
      }
    });
    $location.search("supersearch",true);
    /*submit method*/
    $http({method:'PUT', url:'restapi/requests/search/'+$scope.dbName, data: search_data}).success(function(data,status){
      $scope.result = data.results;
      $scope.got_results = true;
      $scope.parseColumns();
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    }); 
   };
  $scope.upload = function(file){
    /*Upload a file to server*/
    $scope.got_results = false;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
      $scope.result = data.results;
      $scope.got_results = true;
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };
  $scope.preloadRequest = function(chain, load_single)
  {
    var url = "restapi/requests/get/"+chain;
    if ( !_.has($scope.local_requests,chain) ){
      var promise = $http.get(url);
      promise.then( function(data){
        var local_data = data.data.results.reqmgr_name;
        $scope.local_requests[chain] = local_data;
        if (load_single != "")
        {
          // console.log($scope.local_requests[chain]);
          _.each($scope.local_requests[chain],function(element, index){
            // console.log("braodcast: ",element.name, index, load_single);
            $scope.$broadcast('loadDataSet', [element.name, index, load_single]);
          });
        }
      },function(data){
        console.log("error",data);
      });
    }  
  };
  $scope.multiple_inspect = function()
  {
    _.each($scope.selected_prepids, function(selected_id){
        _.each($scope.result, function(element){
          if( element.prepid == selected_id)
          {
            //works!
            _.each($scope.r_status, function(v,k){
              //also wroks
              if (element.chain.indexOf(k)!= -1)
              {
                if (v =="submitted")
                {
                  $scope.preloadRequest(k,element.prepid);
                }
              }
            });              
          }
        });
    });
  };
};

// NEW for directive
// var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customHistory", function(){
  return {
    require: 'ngModel',
    template: 
    '<div>'+
    '  <div ng-hide="show_history">'+
    '    <input type="button" value="Show" ng-click="show_history=true;">'+
    '  </div>'+
    '  <div ng-show="show_history">'+
    '    <input type="button" value="Hide" ng-click="show_history=false;">'+
    '    <table class="table table-bordered" style="margin-bottom: 0px;">'+
    '      <thead>'+
    '        <tr>'+
    '          <th style="padding: 0px;">Action</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
    '          <td style="padding: 0px;">{{elem.updater.submission_date}}</td>'+
    '          <td style="padding: 0px;">'+
    '              <div ng-switch="elem.updater.author_name">'+
    '                <div ng-switch-when="">{{elem.updater.author_username}}</div>'+
    '                <div ng-switch-default>{{elem.updater.author_name}}</div>'+
    '              </div>'+
    '          </td>'+
   '          <td style="padding: 0px;">{{elem.step}}</td>'+  
    '        </tr>'+
    '      </tbody>'+
    '    </table>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});
testApp.directive("loadFields", function($http, $location){
  return {
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '  <form class="form-inline">'+
    '    <span class="control-group" ng-repeat="(key,value) in searchable">'+
    '      <label style="width:140px;">{{key}}</label>'+
    //'      <select ng-model="listfields[key]">'+
    //'        <option ng-repeat="elem in value">{{elem}}</option>'+
    //'      </select>'+
    '      <input class="input-medium" type="text" ng-hide="showOption[key]" ng-model="listfields[key]" typeahead="state for state in value | filter: $viewValue | limitTo: 10" style="width: 185px;">'+
    //'      <a class="btn btn-mini" ng-href="#" ng-click="toggleSelectOption(key)"><i class="icon-arrow-down"></i></a>'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <button type="button" class="btn btn-small" ng-click="getSearch();">Reload menus</button>'+
    '  <img ng-show="loadingData" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '   <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '</div>'
    ,
    link: function(scope, element, attr){
      scope.listfields = {};
      scope.showUrl = false;
      scope.showOption = {};

      scope.getSearch = function () {
        scope.listfields = {};
        scope.showUrl = false;
        var promise = $http.get("restapi/"+scope.dbName+"/searchable/do");
        scope.loadingData = true;
        promise.then(function(data){
          scope.loadingData = false;
          scope.searchable = data.data;
          _.each(scope.searchable, function(element,key){
            element.unshift("------"); //lets insert into begining of array an default value to not include in search
            scope.listfields[key] = "------";
          });
        }, function(data){
          scope.loadingData = false;
          alert("Error getting searchable fields: "+data.status);
        });
      };
      scope.cleanSearchUrl = function () {
        _.each($location.search(),function(elem,key){
          $location.search(key,null);
        });
        $location.search("page",0);
      };
      scope.getUrl = function () {
        scope.cleanSearchUrl();
         //var url = "?";
        _.each(scope.listfields, function(value, key){
          if (value != ""){
            //url += key +"=" +value+"&";
            $location.search(key,String(value));
          }else{
            $location.search(key,null);//.remove(key);
          }
        });
        scope.getData();
      };
      scope.$watch('tabsettings.navigation.active', function(){
        if (scope.tabsettings.navigation.active)
        {
          if (!scope.searchable) //get searchable fields only if undefined -> save time for 2nd time open of pane
          {
            var promise = $http.get("restapi/"+scope.dbName+"/searchable");
            scope.loadingData = true;
            promise.then(function(data){
              scope.loadingData = false;
              scope.searchable = data.data;
            }, function(data){
              scope.loadingData = false;
              alert("Error getting searchable fields: "+data.status);
            });
          }
        }
      },true);
    }
  }
});
testApp.directive("loadRequestsFields", function($http, $location){
  return {
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '  <form class="form-inline">'+
    '    <span class="control-group" ng-repeat="(key,value) in searchable">'+
    '      <label style="width:140px;">{{key}}</label>'+
    //'      <select bindonce ng-options="elem for elem in value" ng-model="listfields[key]" ng-show="showOption[key]" style="width: 164px;">'+
    //'      </select>'+
    '      <input class="input-medium" type="text" ng-hide="showOption[key]" ng-model="listfields[key]" typeahead="state for state in value | filter: $viewValue | limitTo: 10" style="width: 185px;">'+
    //'      <a class="btn btn-mini" ng-href="#" ng-click="toggleSelectOption(key)"><i class="icon-arrow-down"></i></a>'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <button type="button" class="btn btn-small" ng-click="getSearch();">Reload menus</button>'+
    '  <img ng-show="loadingData" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '   <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '</div>',
    link: function (scope, element, attr) {
      scope.listfields = {};
      scope.showUrl = false;
      scope.showOption = {};

      scope.getSearch = function () {
        scope.listfields = {};
        scope.showUrl = false;
        var promise = $http.get("restapi/requests/searchable/do");
        scope.loadingData = true;
        promise.then(function(data){
          scope.loadingData = false;
          scope.searchable = data.data;
          _.each(scope.searchable, function(element,key){
            element.unshift("------"); //lets insert into begining of array an default value to not include in search
            scope.listfields[key] = "------";
          });
        }, function(data){
          scope.loadingData = false;
          alert("Error getting searchable fields: "+data.status);
        });
      };
      scope.cleanSearchUrl = function () {
        _.each($location.search(),function(elem,key){
          $location.search(key,null);
        });
        $location.search("page",0);
      };
      scope.getUrl = function () {
        scope.cleanSearchUrl();
        _.each(scope.listfields, function(value, key){
          if (value != ""){
            $location.search(key, String(value));
          }else{
            $location.search(key, null);//.remove(key);
          }
        });
        $location.search("searchByRequests", true);
        scope.getData();
      };
      scope.toggleSelectOption = function(option){
        if (scope.showOption[option])
        {
          scope.showOption[option] = false;
        }else
        {
          scope.showOption[option] = true;
        }
      };
      scope.$watch('tabsettings.navigation2.active', function(){
        $location.search("searchByRequests",null);//.remove(key);
        if (scope.tabsettings.navigation2.active)
        {
          if (!scope.searchable) //get searchable fields only if undefined -> save time for 2nd time open of pane
          {
            var promise = $http.get("restapi/requests/searchable");
            scope.loadingData = true;
            promise.then(function(data){
              scope.loadingData = false;
              scope.searchable = data.data;
            }, function(data){
              scope.loadingData = false;
              alert("Error getting searchable fields: "+data.status);
            });
          }
        }
      },true);
    }
  }
});