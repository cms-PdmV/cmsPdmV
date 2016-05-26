function resultCtrl($scope, $http, $location, $window){

    $scope.defaults = [];
    $scope.underscore = _;
    $scope.update = [];
    $scope.chained_campaigns = [];

    $scope.dbName = $location.search()["db_name"];
    $scope.prepid = $location.search()["prepid"];
    if ($scope.prepid === undefined){
      $scope.prepid = $location.search()["query"];
    }

    switch($scope.dbName)
    {
      case "campaigns":
        $scope.not_editable_list = ["Prepid", "Member of campaign","Completed events", "Status","Approval","Next", "Total events"];
        $scope.type_list = ["MCReproc","Prod","LHE"];
        break;
      case "requests":
        $scope.not_editable_list = ["Cmssw release", "Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version"]; //user non-editable columns
        var promise = $http.get("restapi/requests/editable/"+$scope.prepid)
        promise.then(function(data){
          $scope.parseEditableObject(data.data.results);
        });
        break;
      case "chained_requests":
        $scope.not_editable_list = ["Prepid", "Chain","Approval","Member of campaign","Pwg"];
        break;
      case "chained_campaigns":
        $scope.not_editable_list = ["Prepid", "Campaigns"];
        break;
      case "flows":
        $scope.not_editable_list = ["Prepid", "Approval"];
        var promise = $http.get("restapi/campaigns/listall"); //get list of all campaigns for flow editing
          promise.then(function(data){
          $scope.allCampaigns = data.data.results;
        },function(){
          alert("Error getting all campaign list for flows");
        });
        break;
      case "news":
        $scope.not_editable_list = ["Author", "Date"];
        break;
      case "settings":
        $scope.not_editable_list = ["Prepid"];
        break;
      case "users":
        $scope.not_editable_list = ["Username", "Role"];
        break;
      case "mccms":
	      $scope.not_editable_list = ["Prepid", "Pwg"];
        var promise = $http.get("restapi/mccms/editable/"+$scope.prepid)
        promise.then(function(data){
          $scope.parseEditableObject(data.data.results);
        });
        break;
      default:
        $scope.not_editable_list = [];
        break;
    }

    if($location.search()["page"] === undefined){
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else{
      page = $location.search()["page"];
      $scope.list_page = parseInt(page);
    }

    $scope.parseEditableObject = function(editable){
      _.each(editable, function(elem,key){
        if (elem == false){
          if (key[0] != "_"){ //if its not mandatory couchDB values eg. _id,_rev
            column_name = key[0].toUpperCase()+key.substring(1).replace(/\_/g,' ')
            if($scope.not_editable_list.indexOf(column_name) ==-1){
              $scope.not_editable_list.push(column_name);
            }
          }
        }
      });
    };

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          alert('Object was deleted successfully.');
        }else{
          alert('Could not save data to database.');
        }
      }).error(function(status){
        alert('Error no.' + status + '. Could not delete object.');
      });
    };

    $scope.booleanize_sequence = function(sequence){
      _.each(sequence, function(value, key){
        if (_.isString(value))
        {
          switch(value.toLowerCase()){
            case "true":
              sequence[key] = true;
              break;
            case "false":
              sequence[key] = false;
              break;
            default:
              break;
          }
        }
      });
    };

    function isInt(n) {
       return typeof n === 'number' && n % 1 == 0;
    }

    function parseSettingValue (string_value) {
        if(!isNaN(string_value)) {
            return +string_value
        } else {
            switch(string_value.toLowerCase()){
            case "true":
              return true;
            case "false":
              return false;
            default:
              break;
          }
        }
        return string_value
    }

    $scope.submit_edit = function(){
      switch($scope.dbName){
        case "requests":
          _.each($scope.result["sequences"], function(sequence){
            $scope.booleanize_sequence(sequence);
            if (_.isString(sequence["step"]))
            {
              sequence["step"] = sequence["step"].split(",");
            }
            if (_.isString(sequence["datatier"]))
            {
              sequence["datatier"] = sequence["datatier"].split(",");
            }
            if (_.isString(sequence["eventcontent"]))
            {
              sequence["eventcontent"] = sequence["eventcontent"].split(",");
            }
          });
         $scope.result["time_event"] = parseFloat($scope.result["time_event"]);
         $scope.result["size_event"] = parseFloat($scope.result["size_event"]);
         $scope.result["memory"] = parseFloat($scope.result["memory"]);
         $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
  //$scope.listify_blocks();
          break;
        case "campaigns":
          _.each($scope.result["sequences"], function(sequence){
            _.each(sequence, function(subSequence, key){
              if (key != "$$hashKey") //ignore angularhs hashkey
              {
                $scope.booleanize_sequence(subSequence);
                if (_.isString(subSequence["step"]))
                {
                  subSequence["step"] = subSequence["step"].split(",");
                }
                if (_.isString(subSequence["datatier"]))
                {
                  subSequence["datatier"] = subSequence["datatier"].split(",");
                }
                if (_.isString(subSequence["eventcontent"]))
                {
                  subSequence["eventcontent"] = subSequence["eventcontent"].split(",");
                }
              }
            });
          });
          break;
        case "mccms":
          $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
          break;
        default:
          break;
      }
      $http({method:'PUT', url:'restapi/'+$location.search()["db_name"]+'/update',data:angular.toJson($scope.result)}).success(function(data,status){
        $scope.update["success"] = data["results"];
        $scope.update["fail"] = false;
        $scope.update["message"] = data["message"];
        $scope.update["status_code"] = status;
        if ($scope.update["success"] == false){
          $scope.update["fail"] = true;
        }else{
          $scope.getData();
        }
      }).error(function(data,status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    $scope.delete_edit = function(id){
      $scope.delete_object($location.search()["db_name"], id);
    };
    $scope.display_approvals = function(data){
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
      if (sort.column == column){
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };


  $scope.getData = function(){
    var promise = $http.get("restapi/"+ $location.search()["db_name"]+"/get/"+$scope.prepid)
    promise.then(function(data){
      $scope.result = data.data.results;
      if ($scope.result.length != 0){
        columns = _.keys($scope.result);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
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
        setTimeout(function(){ //update fragment field
          codemirror = document.querySelector('.CodeMirror');
          if (codemirror != null){
            _.each(angular.element(codemirror),function(elem){
              elem.CodeMirror.refresh();
            });
          }
        },300);
        //});
      }
    }, function(){ alert("Error getting information"); });
  };

   $scope.$watch('list_page', function(){
    $scope.getData();
   });

  $scope.editableFragment = function(){
    return $scope.not_editable_list.indexOf('Fragment')!=-1;
  };
  $scope.hideSequence = function(roleNumber){
    if ($scope.role(roleNumber)){
      return true; //if we hide by role -> hide
    }else{ //else we check if sequence is in editable list
      if ($scope.not_editable_list.indexOf("Sequences")!=-1){
        return true; //if its in list -> hide
      }else{
        return false; //else let be displayed: ng-hide=false
      }
    }
  };
  $scope.removeUserPWG = function(elem){
    //console.log(_.without($scope.result["pwg"], elem));
    $scope.result["pwg"] = _.without($scope.result["pwg"], elem);
  };
  $scope.showAddUserPWG = function(){
    $scope.showSelectPWG = true;
    var promise = $http.get("restapi/users/get_pwg")
    promise.then(function(data){
	    $scope.all_pwgs = data.data.results;
	});

  };
  $scope.addUserPWG = function(elem){
    if($scope.result["pwg"].indexOf(elem) == -1){
      $scope.result["pwg"].push(elem);
    }
  };

  $scope.addToken = function(tok) {
      $http({method:'PUT', url:'restapi/tags/add/', data:JSON.stringify({tag:tok.value})})
  };

  $scope.removeToken = function(tok) {
      // for now let's store all tags, can be changed in future for some checks
//      $http({method:'PUT', url:'restapi/tags/remove/', data:JSON.stringify({tag:tok.value})})
  }
}

testApp.directive("customRequestsEdit", function($http, $rootScope){
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '  <ul>'+
    '    <li ng-repeat="elem in requests_data">'+
    '      <span ng-switch on="underscore.isArray(elem)">'+
    '        <span ng-switch-when="true">'+
    '        {{elem[0]}} <i class="icon-arrow-right"></i> {{elem[1]}}'+
    '          <a ng-href="#" ng-click="removeOldRequest($index)" rel="tooltip" title="Remove last from list"><i class="icon-minus"></i></a>'+
    '        </span>'+
    '        <span ng-switch-when="false">'+
    '          {{elem}}'+
    '          <a ng-href="#" ng-click="removeOldRequest($index)" ng-hide="show_new[$index] || not_editable_list.indexOf(\'Requests\')!=-1" rel="tooltip" title="Remove itself" ><i class="icon-minus"></i></a>'+
    '          <a ng-href="#" ng-click="addNewRequest($index)" ng-hide="show_new[$index] || not_editable_list.indexOf(\'Requests\')!=-1" rel="tooltip" title="Add new"><i class="icon-plus"></i></a>'+
    '          <a ng-href="#" ng-click="toggleNewRequest($index)" ng-show="show_new[$index]" rel="tooltip" title="Close input"><i class="icon-minus-sign"></i></a>'+
    '          <input type="text" ng-model="tmpRequest[$index]" ng-show="show_new[$index]" typeahead="id for id in possible_sub_requests[$index] | filter: $viewValue | limitTo: 10">'+
    '          <a ng-href="#" ng-click="saveNewRequest($index)" ng-show="show_new[$index]"><i class="icon-plus-sign" rel="tooltip" title="Add id to list"></i></a>'+
    '          <font color="red" ng-show="bad_sub_request">Wrong request</font>'+
    '        </span>'+
    '      </span>'+
    '    </li>'+
    '  </ul>'+
    '  <a ng-href="#" ng-click ="toggleNewRequest(\'new\')" ng-hide="show_new[\'new\'] || not_editable_list.indexOf(\'Requests\')!=-1"><i class="icon-plus"></i></a>'+
    '  <a ng-href="#" ng-click="toggleNewRequest(\'new\')" ng-show="show_new[\'new\']"><i class="icon-minus-sign"></i></a>'+
    '  <input type="text" ng-model="tmpRequest[\'new\']" ng-show="show_new[\'new\']" typeahead="id for id in possible_requests | filter: $viewValue | limitTo: 10">'+
    '  <a ng-href="#" ng-click="pushNewRequest()" ng-show="show_new[\'new\']"><i class="icon-plus-sign"></i></a>'+
    '  <font color="red" ng-show="bad_request">Wrong request</font>'+
    '</div>'+
    '',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.requests_data = ctrl.$viewValue;
        scope.show_new = {};
        scope.tmpRequest = {};
        scope.possible_requests = [];
        scope.campaign_name = "";
        scope.bad_request = false;
        scope.bad_sub_request = false;
        scope.possible_sub_requests = {};
        if (scope.requests_data.length != 0)
        {
          switch(_.isArray(scope.requests_data[0])){
            case true:
              scope.campaign_name = scope.requests_data[0][0].split("-")[1];
              break;
            default:
              scope.campaign_name = scope.requests_data[0].split("-")[1];
              break;
          };
        scope.preloadRequests(scope.campaign_name);
        $rootScope.$broadcast('loadChains', scope.campaign_name);
        }else{
          scope.preloadAllRequests();
        };
      };
      scope.toggleNewRequest = function (elem)
      {
        if(scope.show_new[elem] == true)
        {
          scope.show_new[elem] = false;
        }else
        {
          scope.show_new[elem] = true;
        }
      };
      scope.addNewRequest = function (elem)
      {
        scope.toggleNewRequest(elem);
        scope.possible_sub_requests[elem] = [];
        var __pwg = scope.requests_data[elem].split("-")[0];
        _.each(scope.possible_requests, function (el)
        {
          if (el.split('-')[0] == __pwg)
          {
            scope.possible_sub_requests[elem].push(el);
          }
        });
      };
      scope.saveNewRequest = function (index)
      {
        if (scope.possible_sub_requests[index].indexOf(scope.tmpRequest[index]) == -1)
        {
          scope.bad_sub_request = true;
        }else{
          scope.bad_sub_request = false;
          var __request = scope.requests_data[index];
          scope.requests_data[index] = [];
          scope.requests_data[index].push(__request);
          scope.requests_data[index].push(scope.tmpRequest[index]);
          scope.show_new[__request] = false;
        }
      };
      scope.pushNewRequest = function()
      {
        var preload = false;
        if (scope.possible_requests.indexOf(scope.tmpRequest["new"]) == -1)
        {
          scope.bad_request = true;
        }else{
          if (scope.requests_data.length == 0)
          {
            preload = true;
          }
          scope.bad_request = false;
          scope.requests_data.push(scope.tmpRequest["new"]);
          scope.toggleNewRequest('new');
          scope.campaign_name = scope.tmpRequest["new"].split("-")[1];
          scope.tmpRequest["new"] = "";
          $rootScope.$broadcast('refreshChains', scope.campaign_name);
        }
        if (preload)
        {
          var parsed_campaign = scope.requests_data[0].split("-")[1];
          scope.preloadRequests(parsed_campaign);
        };
      };
      scope.removeOldRequest = function (index)
      {
        if (_.isArray(scope.requests_data[index]))
        {
          scope.requests_data[index] = scope.requests_data[index][0]
        }else
        {
          scope.requests_data.splice(index,1);
        }
        scope.show_new[index] = false;
        if (scope.requests_data.length == 0)
        {
          if (scope.result['chains'].length == 0)
          {
            scope.preloadAllRequests();
            $rootScope.$broadcast('refreshChains', "_");
          }else
          {
            var parsed_campaign = scope.result['chains'][0].split("_")[1];
            scope.preloadRequests(parsed_campaign);
          };
        };
      };
      scope.preloadRequests = function (id)
      {
        if (scope.requests_data.length != 0)
        {
          id = scope.campaign_name;
        };
        var promise = $http.get("restapi/requests/search_view/member_of_campaign/" + id);
        promise.then(function(data){
          scope.possible_requests = data.data.results;
        }, function(data){
          alert("Error getting list of possible requests: " + data.data);
        });
      };
      scope.preloadAllRequests = function ()
      {
        var promise = $http.get("restapi/requests/search_view/all");
        promise.then(function(data){
          scope.possible_requests = data.data.results;
        }, function(data){
          alert("Error getting list of possible requests: " + data.data);
        });
      };

      scope.$on('loadRequests', function(event, chain){
        scope.preloadRequests(chain);
      });
    }
  }
});

testApp.directive("customMccmChains", function($http, $rootScope){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in chain_data">'+
    '     <span>'+
    '       {{elem}}'+
    '       <a ng-href="#" ng-click="remove($index)" ng-hide="not_editable_list.indexOf(\'Chains\')!=-1">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(\'Chains\')!=-1">'+
    '      <a ng-href="#" ng-click="toggleAddNewChain();">'+
    '        <i class="icon-plus" ng-hide="add_chain"></i>'+
    '        <i class="icon-minus" ng-show="add_chain"></i>'+
    '      </a>'+
    '      <select id="mySel" class="input-xxlarge" ng-model="new_chain" ng-show="add_chain">'+
    '        <option ng-repeat="elem in list_of_chained_campaigns track by $index" value="{{elem}}">{{alias_map[elem]}}</option>'+
    '      </select>'+
    '      <a ng-href="#">'+
    '        <i class="icon-plus-sign" ng-click="pushNewMcMChain()" ng-show="add_chain"></i>'+
    '      </a>'+
    '    </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.chain_data = ctrl.$viewValue;
        if (scope.chain_data.length != 0)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
          if (scope.result['requests'].length == 0)
          {
            $rootScope.$broadcast('loadRequests', scope.root_campaign);
          }
        }else{
          scope.root_campaign = "_";
        }
        scope.new_chain = "";
        scope.list_of_chained_campaigns = [];
        scope.alias_map = {};
        scope.original_chain_list = [];
        scope.getChains(scope.root_campaign);
        scope.show_error = false;
      };
      scope.toggleAddNewChain = function(){
        if(scope.add_chain)
        {
          scope.add_chain = false;
        }else{
          scope.add_chain = true;
        }
      };
      scope.getChains = function(root_campaign)
      {
        if (scope.list_of_chained_campaigns.length == 0)
        {
		      var promise = $http.get("search/?db_name=chained_campaigns&valid=true&page=-1");
          promise.then(function (data) {
            _.each(data.data.results, function (elem) {
              if (elem.alias != "") //lets construct alais map
              {
                scope.alias_map[elem.prepid] = elem.alias;
                // we need to store original prepid when fetching requests!
                scope.alias_map[elem.alias] = elem.prepid;
              }else{
                scope.alias_map[elem.prepid] = elem.prepid;
              }
              scope.original_chain_list.push(elem.prepid);
              if (elem.prepid.split("_")[1] == root_campaign)
              {
                if (scope.chain_data.indexOf(elem.prepid) == -1) //add only if its not already in chains -> in chain we display normal prepid no fcking ALIAS
                {
                  scope.list_of_chained_campaigns.push(elem.prepid);
                }
              }else if (root_campaign == "_")
              {
                scope.list_of_chained_campaigns.push(elem.prepid);
              }
            }, function(data){
              alert("Error getting chained campaigns: " + data);
            });
            scope.list_of_chained_campaigns = _.uniq(scope.list_of_chained_campaigns);
            scope.original_chain_list = _.uniq(scope.original_chain_list);
            scope.list_of_chained_campaigns.sort(); //sort list to be in ascending order
            scope.new_chain = scope.list_of_chained_campaigns[0];
            $("#mySel").select2({dropdownAutoWidth : true});
          });
        }
      };
      scope.remove = function(index){
        //scope.list_of_chained_campaigns.push(scope.chain_data[index]);
        scope.chain_data.splice(index,1);
        if (scope.chain_data.length != 0)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
        }else{
          scope.root_campaign = "_";
          $rootScope.$broadcast('loadRequests', "");
        }
        scope.list_of_chained_campaigns = scope.original_chain_list;
        scope.parseRootChains();
      }
      scope.pushNewMcMChain = function()
      {
        scope.show_error = false;
        scope.chain_data.push(scope.alias_map[scope.new_chain]);
        if (scope.chain_data[0].indexOf('_') != -1)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
        }else
        {
          scope.root_campaign = scope.alias_map[scope.chain_data[0]].split('_')[1];
        }
        $rootScope.$broadcast('loadRequests', scope.root_campaign);
        scope.list_of_chained_campaigns.splice(scope.list_of_chained_campaigns.indexOf(scope.new_chain), 1); //lets remove not to duplicate
        //scope.add_chain = false; //uncomment if we cant to close select field after each new chain_campaign addition
        scope.parseRootChains();
        scope.new_chain = scope.list_of_chained_campaigns[0];
      };
      scope.parseRootChains = function ()
      {
        var to_remove = [];
        _.each(scope.list_of_chained_campaigns, function (elem, index)
        {
          if (elem.split("_")[1] != scope.root_campaign)
          {
            to_remove.push(elem);
          }
        });
        if (scope.root_campaign != "_"){
          scope.list_of_chained_campaigns = _.difference(scope.list_of_chained_campaigns, to_remove);
        }else{
          scope.list_of_chained_campaigns = scope.original_chain_list;
        }
        scope.list_of_chained_campaigns.sort(); //re-sort the list in select fields
        scope.new_chain = scope.list_of_chained_campaigns[0];
      };

      scope.$on('loadChains', function(event, chain){
        scope.getChains(chain);
        scope.parseRootChains();
      });
      scope.$on('refreshChains', function(event, chain){
        //scope.getChains(chain);
        scope.root_campaign = chain;
        scope.parseRootChains();
      });
    }
  }
});
