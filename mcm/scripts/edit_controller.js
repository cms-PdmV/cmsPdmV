angular.module('testApp').controller('resultCtrl',
  ['$scope', '$http', '$location', '$window',
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
        $scope.not_editable_list = ["Prepid", "Pwg", "Total events"];
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
          _.each($scope.result["time_event"], function(value, key){
            $scope.result["time_event"][key] = parseFloat(value);
          });
          $scope.result["size_event"] = parseFloat($scope.result["size_event"]);
          $scope.result["memory"] = parseFloat($scope.result["memory"]);
          $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
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
  }
]);

testApp.directive("customActionParameters", function($http, $rootScope){
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '   <h6 style="display: inline;">Block number:</h6>' +
    '   <select class="input-mini ng-pristine ng-valid ng-empty ng-touched" ng-model="action_parameters.block_number" ng-options="key for key in [1,2,3,4,5,6]">' +
    '   <option value="?" selected="selected"></option>' +
    '     <option label="1" value="number:1">1</option>' +
    '     <option label="2" value="number:2">2</option>' +
    '     <option label="3" value="number:3">3</option>' +
    '     <option label="4" value="number:4">4</option>' +
    '     <option label="5" value="number:5">5</option>' +
    '     <option label="6" value="number:6">6</option>' +
    '   </select>' +
    '   <br></br>' +
    '   <h6 style="display: inline;">Staged:</h6>' +
    '   <input type="number" style="width: 50px;" ng-model="action_parameters.staged" class="ng-valid ng-touched ng-not-empty ng-dirty ng-valid-number">' +
    '   <br></br>' +
    '   <h6 style="display: inline;">Threshold:</h6>' +
    '   <span class="input-append">' +
    '     <input type="number" style="width: 50px;" ng-model="action_parameters.threshold" class="ng-valid ng-not-empty ng-dirty ng-valid-number ng-touched">' +
    '     <span class="add-on">%</span>' +
    '   </span>' +
    '   <br></br>' +
    '   <h6 style="display: inline;">Flag:</h6>' +
    '   <input type="checkbox" ng-model="action_parameters.flag" class="ng-pristine ng-valid ng-not-empty ng-touched">' +
    '</div>',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.action_parameters = ctrl.$viewValue;
      };
    }
  }
});

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
    '          <input type="text" ng-model="tmpRequest[$index]" ng-show="show_new[$index]" typeahead="id for id in preloadPossibleRequests($viewValue)">'+
    '          <a ng-href="#" ng-click="saveNewRequest($index)" ng-show="show_new[$index]"><i class="icon-plus-sign" rel="tooltip" title="Add id to list"></i></a>'+
    '          <font color="red" ng-show="bad_sub_request">Wrong request</font>'+
    '        </span>'+
    '      </span>'+
    '    </li>'+
    '  </ul>'+
    '  <a ng-href="#" ng-click ="toggleNewRequest(\'new\')" ng-hide="show_new[\'new\'] || not_editable_list.indexOf(\'Requests\')!=-1"><i class="icon-plus"></i></a>'+
    '  <a ng-href="#" ng-click="toggleNewRequest(\'new\')" ng-show="show_new[\'new\']"><i class="icon-minus-sign"></i></a>'+
    '  <input type="text" ng-model="tmpRequest[\'new\']" ng-show="show_new[\'new\']" typeahead="id for id in preloadPossibleRequests($viewValue)">'+
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
        if (typeof($rootScope.root_campaign) == "undefined"){
          $rootScope.root_campaign = "";
        }
        $rootScope.request_list_length = scope.requests_data.length;
        scope.bad_request = false;
        scope.bad_sub_request = false;
        if (scope.requests_data.length != 0 && $rootScope.root_campaign == "")
        {
          switch(_.isArray(scope.requests_data[0])){
            case true:
              $rootScope.root_campaign = scope.requests_data[0][0].split("-")[1];
              break;
            default:
              $rootScope.root_campaign = scope.requests_data[0].split("-")[1];
              break;
          };
          $rootScope.$broadcast('refreshChains', $rootScope.root_campaign);
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
      };
      scope.saveNewRequest = function (index)
      {
        if (scope.possible_requests.indexOf(scope.tmpRequest[index]) == -1 || scope.lookForDuplicates(scope.tmpRequest[index]))
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
      scope.lookForDuplicates = function (id){
        for (var index=0; index < scope.requests_data.length; index++){
          if(_.isArray(scope.requests_data[index])){
            if(scope.requests_data[index][0] == id || scope.requests_data[index][1] == id){
              return true;
            }
          }else{
            if(scope.requests_data[index] == id){
              return true;
            }
          }
        }
        return false;
      }
      scope.pushNewRequest = function()
      {
        if (scope.possible_requests.indexOf(scope.tmpRequest["new"]) == -1 || scope.lookForDuplicates(scope.tmpRequest["new"]))
        {
          scope.bad_request = true;
        }else{
          scope.bad_request = false;
          scope.requests_data.push(scope.tmpRequest["new"]);
          $rootScope.request_list_length = scope.requests_data.length;
          if(scope.requests_data.length == 1){
            $rootScope.root_campaign = scope.tmpRequest["new"].split("-")[1];
            $rootScope.$broadcast('refreshChains', $rootScope.root_campaign);
          }
          scope.toggleNewRequest('new');
          scope.tmpRequest["new"] = "";
        }
      };
      scope.removeOldRequest = function (index)
      {
        if (_.isArray(scope.requests_data[index]))
        {
          scope.requests_data[index] = scope.requests_data[index][0];
        }else
        {
          scope.requests_data.splice(index,1);
        }
        scope.show_new[index] = false;
        $rootScope.request_list_length = scope.requests_data.length;
        if (scope.requests_data.length == 0 && $rootScope.chain_list_length == 0)
        {
          $rootScope.root_campaign = "";
          $rootScope.$broadcast('noRequestsSelected');
        };
      };
      scope.preloadPossibleRequests = function (viewValue)
      {
        var campaign_name = $rootScope.root_campaign == "" ? '*' : $rootScope.root_campaign;
        var promise = $http.get("restapi/requests/search_view?limit=10&requestPrepId=" + viewValue + "&memberOfCampaign=" + campaign_name);
        return promise.then(function(data){
          data = JSON.parse(data.data)
          results = JSON.parse(data)
          scope.possible_requests = results.results;
          return scope.possible_requests;
        }, function(data){
          alert("Error getting list of possible requests: " + data.data);
        });
      };
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
    '      <input type="text" ng-model="new_chain" ng-show="add_chain" typeahead="id for id in preloadPossibleChains($viewValue)">'+
    '      <a ng-href="#">'+
    '        <i class="icon-plus-sign" ng-click="pushNewMcMChain()" ng-show="add_chain"></i>'+
    '      </a>'+
    '      <font color="red" ng-show="bad_sub_chain">Wrong request</font>'+
    '    </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.chain_data = ctrl.$viewValue;
        if (typeof($rootScope.root_campaign) == "undefined"){
          $rootScope.root_campaign = "";
        }
        if (scope.chain_data.length != 0 && $rootScope.root_campaign == "")
        {
          if(scope.chain_data[0].startsWith("chain_")){
            $rootScope.root_campaign = scope.chain_data[0].split('_')[1];
          }else{
            scope.getPrepIdFromAlias(scope.chain_data[0]);
          }
        }
        $rootScope.chain_list_length = scope.chain_data.length;
        scope.new_chain = "";
        scope.list_of_chained_campaigns = [];
        scope.chained_campaigns_from_requests = [];
        scope.bad_sub_chain = false;
      };
      scope.toggleAddNewChain = function(){
        if($rootScope.root_campaign != "" && scope.chained_campaigns_from_requests.length == 0){
          scope.refreshChains($rootScope.root_campaign);
        }
        scope.add_chain = !scope.add_chain;
      };
      scope.remove = function(index){
        scope.chain_data.splice(index,1);
        $rootScope.chain_list_length = scope.chain_data.length;
        if (scope.chain_data.length == 0 && $rootScope.request_list_length == 0)
        {
          $rootScope.root_campaign = "";
          scope.chained_campaigns_from_requests = [];
        }
      }
      scope.searchChain = function(chain)
      {
        for (var index=0; index < scope.list_of_chained_campaigns.length; index++){
          var element = scope.list_of_chained_campaigns[index];
          if(element[0] == chain || element[1] == chain){
            return element;
          }
        }
        return [];
      };
      scope.pushNewMcMChain = function()
      {
        var chain = scope.searchChain(scope.new_chain); 
        if(chain.length == 0 || scope.chain_data.indexOf(chain[0]) != -1 || scope.chain_data.indexOf(chain[1]) != -1){
          scope.bad_sub_chain = true;
          return;
        }
        scope.bad_sub_chain = false;
        scope.chain_data.push(scope.new_chain);
        if(scope.chain_data.length == 1){
          $rootScope.root_campaign = chain[0].split('_')[1];
          scope.refreshChains($rootScope.root_campaign);
        }
        scope.new_chain = "";
      };
      scope.listFilter = function (list, value, search_by){
        var result_list = [];
        if(typeof(list) == "undefined"){
          return [];
        }
        var search_index = search_by == 'alias' ? 1 : 0;
        for (var index=0; index < list.length; index++){
          if(list[index][search_index] != "" && list[index][search_index].includes(value,0)){
            var toPush = list[index][search_index];
            result_list.push(toPush);
          } else if (list[index][0].includes(value,0)){
            result_list.push(list[index][0]);
          }
        }
        return result_list;
      };
      scope.preloadPossibleChains = function(viewValue)
      {
        if($rootScope.request_list_length > 0 && scope.chained_campaigns_from_requests.length == 0){
          //There are no chains for the selected requests, we don't want to do searches while the user is typing
          return [];
        }
        var search_by = viewValue.includes('chain', 0) ? 'prepid' : 'alias';
        if(scope.chained_campaigns_from_requests.length > 0){
          scope.list_of_chained_campaigns = scope.chained_campaigns_from_requests;
          return scope.listFilter(scope.list_of_chained_campaigns, viewValue, search_by);
        }
        var promise = scope.getChains(viewValue, search_by);
        return promise.then(function(data) {
          scope.list_of_chained_campaigns = data;
          return scope.listFilter(data, viewValue, search_by);
        }, function(data) {
        });
      };
      scope.getChains = function (viewValue, search_by){
        var promise = $http.get("search/?db_name=chained_campaigns&valid=true&page=0&limit=10&include_fields=prepid,alias&" + search_by + "=" + viewValue + "*");
        return promise.then(function(data){
          return scope.parseChainData(data);
        }, function(data){
          alert("Error getting list of possible chains: " + data.data);
        }); 
      };
      scope.getPrepIdFromAlias = function (alias){
        var promise = $http.get("search/?db_name=chained_campaigns&valid=true&page=-1&include_fields=prepid&alias=" + alias);
        promise.then(function(data){
            var prepid = scope.parseChainData(data);
            if(prepid.length > 0){
              if(_.isArray(prepid[0])){
                $rootScope.root_campaign = prepid[0][0].split('_')[1];
              }else{
                $rootScope.root_campaign = prepid[0].split('_')[1];
              }
              scope.refreshChains($rootScope.root_campaign);
            }
        }, function(data){
          alert("Error getting the prepid for alias");
        }); 
      };
      scope.parseChainData = function (data){
        var chains = [];
        scope.chained_campaigns_from_requests = [];
        for (var index = 0; index <  data.data.results.length; index++){
          var doc = data.data.results[index];
          chains.push([doc['prepid'], doc['alias']]);
        }
        return chains;
      };
      scope.refreshChains = function (root_campaign)
      {
        var promise = $http.get("search/?db_name=chained_campaigns&valid=true&page=-1&include_fields=prepid,alias&prepid=*" + root_campaign + "*");
        promise.then(function(data){
          scope.chained_campaigns_from_requests = scope.parseChainData(data);
        }, function(data){
          alert("Error getting list of possible chains: " + data.data);
        });
      };
      scope.$on('refreshChains', function(event, chain){
        if(scope.chained_campaigns_from_requests.length == 0){
          scope.refreshChains(chain);
        }
      });
      scope.$on('noRequestsSelected', function(event){
        if(scope.chain_data.length == 0){
          scope.chained_campaigns_from_requests = [];
        }
      });
    }
  }
});
