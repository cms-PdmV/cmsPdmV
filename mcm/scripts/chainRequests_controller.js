angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [
      {text:'PrepId',select:true, db_name:'prepid'},
      {text:'Actions',select:true, db_name:''},
      {text:'Approval',select:true, db_name:'approval'},
      {text:'Chain',select:true, db_name:'chain'},
    ];
    $scope.update = [];
    $scope.chained_campaigns = [];
    $scope.filt = {};
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "chained_requests";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

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
              $http({method:'GET', url: 'public/restapi/requests/get_status_and_approval/'+prepid}).success(function(data,status){
                r_prepid=_.keys(data)[0];
                r_status = data[r_prepid];
                $scope.r_status[ r_prepid ] = r_status;
                status_map = {'submit-done': 'led-green.gif',
                              'submit-submitted': 'led-blue.gif',
                              'submit-approved': 'led-red.gif',
                              'approve-approved': 'led-orange.gif',
                              'define-defined': 'led-yellow.gif',
                              'validation-validation': 'led-purple.gif',
                              'validation-new': 'led-aqua.gif',
                              'none-new': 'led-gray.gif'}
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
    };

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          // alert('Object was deleted successfully.');
          $scope.setSuccess(status);
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
        $scope.setFailure(status);
      });
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
      //    'define' : 'icon-check',
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
        if ( _.keys($location.search()).indexOf('fields') != -1)
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
        $scope.selectionReady = true;
    };

    $scope.getData = function(){
      if ( $location.search()['searchByRequests'] )
      {
        $scope.superSearch();
      }else {
        var query = ""
        _.each($location.search(), function(value,key){
          if (key!= 'shown' && key != 'fields'){
            query += "&"+key+"="+value;
          }
        });
        $scope.got_results = false; //to display/hide the 'found n results' while reloading
        var parameters = "";
        if ($location.search()["from_notification"]){
          notification = $location.search()["from_notification"];
          page = $location.search()["page"]
          limit = $location.search()["limit"]
          if(page === undefined){
            page = 0
          }
          if(limit === undefined){
            limit = 20
          }
          parameters = "restapi/notifications/fetch_actions?notification_id=" + notification + "&page=" + page + "&limit=" + limit;
        }else if($location.search()["from_notification_group"]){
          group = $location.search()["from_notification_group"];
          page = $location.search()["page"]
          limit = $location.search()["limit"]
          if(page === undefined){
            page = 0
          }
          if(limit === undefined){
            limit = 20
          }
          parameters = "restapi/notifications/fetch_group_actions?group=" + group + "&page=" + page + "&limit=" + limit;
        }else if ($location.search()["from_ticket"]){
          ticket = $location.search()["from_ticket"];
          page = $location.search()["page"]
          limit = $location.search()["limit"]
          if(page === undefined){
            page = 0
          }
          if(limit === undefined){
            limit = 20
          }
          parameters = "restapi/chained_requests/from_ticket?ticket=" + ticket + "&page=" + page + "&limit=" + limit;
        } else {
          parameters = "search?db_name="+$scope.dbName+query+"&get_raw"
        }
        var promise = $http.get(parameters);
        promise.then(function(data){
          $scope.result_status = data.status;
          $scope.got_results = true;
          if (data.data.rows === undefined){
            $scope.result = data.data;
          }else{
            $scope.result = _.pluck(data.data.rows, 'doc');
          }
          $scope.parseColumns();
        },function(){
           alert("Error getting information");
        });
      }
    };

    $scope.$watch(function () {
          var loc_dict = $location.search();
          return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
        },
        function () {
            $scope.getData();
            $scope.selected_prepids = [];
        });

    $scope.flowChainedRequest = function(prepid, force, campaign){
      if (campaign != undefined) {
        var promise = $http.get("restapi/"+$scope.dbName+"/flow/"+prepid+force+"/"+campaign);
    } else {
        var promise = $http.get("restapi/"+$scope.dbName+"/flow/"+prepid+force);
    }
      promise.then(function(data){
        $scope.parse_report([data.data],status);
      }, function(data){
        $scope.setFailure(data.status);
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
          $scope.setFailure(status);
        });
      }else{
        alert("No requests selected");
      };
    };

    $scope.multiple_flow = function(opt){
      if ($scope.selected_prepids.length > 0){
        $http({method:'GET', url:'restapi/'+$scope.dbName+'/flow/'+$scope.selected_prepids.join()+opt}).success(function(data,status){
          $scope.parse_report(data,status);
        }).error(function(status){
          $scope.setFailure(status);
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
      if (!_.isArray(data)) //multiple inspecting 1 chain will return result of singe inspection
      { //we have to convert to list of results
        data = [data];
      }
      for (i=0; i<data.length; i++){
        $scope.action_status[data[i]['prepid']] = data[i]['results'];
        if ( data[i]['results'] == true)
        {
          $scope.action_report[data[i]['prepid']] = 'OK';
        } else
        {
          $scope.action_report[data[i]['prepid']] = data[i]['message'];
          to_reload=false;
        }
      };

      if (to_reload == true)
      {
        $scope.setSuccess(status);
      } else
      {
        $scope.setFailure(status);
      }
    };

    $scope.setFailure = function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    };

    $scope.setSuccess = function(status){
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = status;
      $scope.getData();
    };

    $scope.superSearch = function(){
      var search_data={
          searches: [
              {
                  db_name: 'requests',
                  return_field: 'member_of_chain',
                  search: {}
              },
              {
                  db_name: $scope.dbName,
                  use_previous_as: 'prepid',
                  search: {}
              }
          ]
      };
      _.each($location.search(),function(elem,key){
        if (key != "shown" && key != "searchByRequests" && key != "fields")
        {
            if(key == 'page' || key == 'limit' || key == 'get_raw') {
              search_data[key] = elem;
            } else {
                search_data.searches[0].search[key] = elem;
            }
        }
      });
      /*submit method*/
      $http({method:'POST', url:'multi_search', data: search_data}).success(function(data,status){
        $scope.result = data.results;
        $scope.result_status = data.status;
        $scope.got_results = true;
        $scope.parseColumns();
      }).error(function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });
    };

    $scope.upload = function(file){
      /*Upload a file to server*/
      $scope.got_results = false;
      $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
        $scope.result = data.results;
        $scope.result_status = data.status;
        $scope.got_results = true;
      }).error(function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
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
            _.each($scope.local_requests[chain],function(element, index){
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

    $scope.inject_chain = function(prepid)
    {
      var __url = "restapi/"+$scope.dbName+"/inject/"+prepid
      var promise = $http.get(__url);
      promise.then(function(data, status){
        $scope.parse_report([data.data], data.status);
      }, function(data){
        $scope.setFailure(data.status);
      })
    };

    $scope.force_done = function(prepid, action)
    {
      // Move chain request status to force_done or vice versa
      if (action == 'to_done')
      {
        var __url = "restapi/"+$scope.dbName+"/force_done/"+prepid
      }else
      {
        var __url = "restapi/"+$scope.dbName+"/back_forcedone/"+prepid
      }

      var promise = $http.get(__url);
      promise.then(function(data, status){
        $scope.parse_report(data.data, data.status);
      }, function(data){
        $scope.setFailure(data.status);
      })
    };

    $scope.add_to_forceflow = function(prepid)
    {
      // Add chain_req prepid to global list of chains to be force_flown
      var __url = "restapi/"+$scope.dbName+"/force_flow/"+prepid

      var promise = $http.get(__url);
      promise.then(function(data, status){
        $scope.parse_report(data.data, data.status);
      }, function(data){
        $scope.setFailure(data.status);
      })
    };

    $scope.remove_from_forceflow = function(prepid)
    {
      // Add chain_req prepid to global list of chains to be force_flown
      var __url = "restapi/"+$scope.dbName+"/remove_force_flow/"+prepid

      var promise = $http.delete(__url);
      promise.then(function(data, status){
        $scope.parse_report(data.data, data.status);
      }, function(data){
        $scope.setFailure(data.status);
      })
    };
}]);

// NEW for directive
// var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("loadFields", function($http, $location){
  return {
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '  <form class="form-inline">'+
    '    <span class="control-group navigation-form" ng-repeat="key in searchable_fields">'+
    '      <label style="width:140px;">{{key}}</label>'+
    '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <button type="button" class="btn btn-small" ng-click="getSearch();">Reload menus</button>'+
    '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '</div>'
    ,
    link: function(scope, element, attr){
      scope.listfields = {};
      scope.showUrl = false;
      scope.showOption = {};

      scope.searchable_fields = [
        'approval',
        'dataset_name',
        'last_status',
        'member_of_campaign',
        'prepid',
        'pwg',
        'status',
        'step'
      ];

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
      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        var searchURL = "restapi/chained_requests/unique_values/" + fieldName;
        searchURL += "?limit=10&group=true";
        searchURL += '&startkey=' + fieldValue + '&endkey=' + fieldValue + '\ufff0';

        var promise = $http.get(searchURL);
        return promise.then(function(data){
          return data.data.results;
        }, function(data){
          alert("Error getting suggestions for " + fieldName + " field (value=" + fieldValue + "): " + data.status);
        });
      };
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
    '    <span class="control-group navigation-form" ng-repeat="key in searchable_fields">'+
    '      <label style="width:140px;">{{key}}</label>'+
    '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '</div>'
    ,
    link: function (scope, element, attr) {
      scope.listfields = {};
      scope.showUrl = false;
      scope.showOption = {};

      scope.searchable_fields = [
        'status',
        'member_of_chain',
        'prepid',
        'extension',
        'tags',
        'energy',
        'mcdb_id',
        'flown_with',
        'pwg',
        'process_string',
        'generators',
        'member_of_campaign',
        'approval',
        'dataset_name'
      ];

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
      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        var searchURL = "restapi/requests/unique_values/" + fieldName;
        searchURL += "?limit=10&group=true";
        searchURL += '&startkey=' + fieldValue + '&endkey=' + fieldValue + '\ufff0';

        var promise = $http.get(searchURL);
        return promise.then(function(data){
          return data.data.results;
        }, function(data){
          alert("Error getting suggestions for " + fieldName + " field (value=" + fieldValue + "): " + data.status);
        });

        return {};
      };
    }
  }
});

var ModalDropdownCtrl = function($scope, $modalInstance, $http, prepid, member_of_campaign) {
    $scope.loadingData = true;
    $scope.campaignListDropdown = ["--------"];
    $scope.dropdownSelector = $scope.campaignListDropdown[0];
    var promiseDeep = $http.get("search?db_name=chained_campaigns&get_raw&prepid=" +
       member_of_campaign)

    promiseDeep.then(function(d){
      d.data.rows[0].doc.campaigns.forEach(function(c) {
        $scope.campaignListDropdown.push(c[0]);
      });
      $scope.loadingData = false;
    });
    $scope.toggle_prepid = prepid;

    $scope.confirm = function(id) {
      $modalInstance.close(id);
    };
    $scope.cancel = function() {
      $modalInstance.dismiss();
    };
};

var MultipleReserveCtrl = function($scope, $modalInstance, $http, selected_prepids) {
  $scope.campaignListDropdown = ["--------"];
  $scope.dropdownSelector = $scope.campaignListDropdown[0];

  // we should get unique list of member_of campaign for thse chained_request
  // then retrieve a list of chained_campaigns as retrieved in reserve modal
  //   and unique the campaign list

  var __chains = [];

  _.each(selected_prepids, function(elem){
    //pwd-chain_camp-id we parse out the chain_campaign prepid
    var __local_split = elem.split("-");
    __chains.push(__local_split[1]);
  });
  // unique to query only for needed chained_campaigns
  __chains = _.uniq(__chains);

  $scope.loadingData = true;
  _.each(__chains, function(elem){
    var promise = $http.get("search?db_name=chained_campaigns&get_raw&prepid=" +
        elem);

    promise.then(function(data){
      data.data.rows[0].doc.campaigns.forEach(function(c) {
        //we add campaign only once, to not have duplicates
        if ($scope.campaignListDropdown.indexOf(c[0]) == -1) {
          $scope.campaignListDropdown.push(c[0]);
        }
      });
    // here should be failure handling
    });
  });
  $scope.loadingData = false;

  $scope.confirm = function(id){
    $modalInstance.close(id);
  }
  $scope.cancel = function() {
      $modalInstance.dismiss();
    };
};
angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$modal',
  function ModalDemoCtrl($scope, $http, $modal) {
    $scope.dropdownModal = function(prepid, member_of_campaign) {
      var isConfirmed = $modal.open({
        templateUrl: 'dropdownModal.html',
        controller: ModalDropdownCtrl,
        resolve: {
          prepid: function() {
            return prepid;
          },
          member_of_campaign: function(){
            return member_of_campaign;
          }
        }
      });

      isConfirmed.result.then(function (campaign) {
        if (campaign == undefined || campaign == ["--------"]) {
          $scope.flowChainedRequest(prepid, '/reserve');
        } else {
          $scope.flowChainedRequest(prepid, '/reserve', campaign);
        }
      });
    };
    // multiple selection modal -> we pass list of campaigns, and for selected prepids
    // we should do a reserve method for eatch
    $scope.multipleDropDownModal = function(selected_prepids){
      var multiple_reservation = $modal.open({
        templateUrl: 'dropdownModal.html',
        controller: MultipleReserveCtrl,
        resolve: {
          selected_prepids: function(){
            return selected_prepids;
          }
        }
      });

      multiple_reservation.result.then(function (campaign) {
        //here we trigger reservation for multiple selected chains to selected campaign
        _.each(selected_prepids, function (elem) {
          if (campaign == undefined || campaign == ["--------"]) {
            $scope.flowChainedRequest(elem, '/reserve');
          } else {
            $scope.flowChainedRequest(elem, '/reserve', campaign);
          }
        });
      });
    };

    $scope.isSureModal = function (action, prepid) {
      var isSure = $modal.open({
        templateUrl: 'isSureModal.html',
        controller: ModalIsSureCtrl,
        resolve: {
          prepid: function () {
            return prepid;
          },
          action: function () {
            return action;
          }
        }
      });

      isSure.result.then(function () {
        switch (action) {
        case "delete":
          $scope.delete_object('chained_requests', prepid);
          break;
        case "reset":
          $scope.single_step('approve', prepid, '/0');
          break;
        case "validate":
          $scope.single_step('test', prepid, '');
          break;
        case "next step":
          $scope.single_step('approve', prepid, '');
          break;
        case "soft reset":
          $scope.single_step('soft_reset', prepid, '');
          break;
        case "rewind":
          $scope.single_step('rewind', prepid, '');
          break;
        case "rewind to root":
          $scope.single_step('rewind_to_root', prepid, '');
          break;
        case "flow":
          $scope.flowChainedRequest(prepid, '');
          break;
        case "force flow":
          $scope.flowChainedRequest(prepid, '/force');
          break;
        case "reserve":
          $scope.flowChainedRequest(prepid, '/reserve');
          break;
        default:
          alert('Unknown action!');
          break;
        };
      });
    };
}]);
