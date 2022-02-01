angular.module('testApp').controller('resultCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
  function resultCtrl($scope, $http, $location, $window, $modal){

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
        $scope.type_list = ["MCReproc","Prod","LHE"];
        break;
      case "chained_requests":
        $scope.not_editable_list = ["Prepid", "Chain","Approval","Member of campaign","Pwg"];
        break;
      case "chained_campaigns":
        $scope.not_editable_list = ["Prepid", "Campaigns"];
        break;
      case "flows":
        $scope.not_editable_list = ["Prepid", "Approval"];
        $scope.allCampaigns = []
        var promise = $http.get("search?db_name=campaigns&page=-1"); //get list of all campaigns for flow editing
        promise.then(function(data){
          $scope.allCampaigns = data.data.results.map(x => x.prepid);
        },function(){
          alert("Error getting all campaign list for flows");
        });
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
          _.each($scope.result["size_event"], function(value, key){
            $scope.result["size_event"][key] = parseFloat(value);
          });
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
        case "flows":
          _.each($scope.result["request_parameters"]["sequences"], function(sequence){
            _.each(sequence, function(elem){
              if (_.has( elem, "datatier")){
                if(_.isString(elem["datatier"])){
                  elem["datatier"] = elem["datatier"].split(",");
                }
              }
              if (_.has(elem, "eventcontent")){
                if(_.isString(elem["eventcontent"])){
                  elem["eventcontent"] = elem["eventcontent"].split(",");
                }
              }
            });
          });
          break;
        default:
          break;
      }
      let method = $scope.prepid && $scope.prepid.length ? 'POST' : 'PUT';
      $http({'method': method, url:'restapi/'+$location.search()["db_name"]+'/update',data:angular.toJson($scope.result)}).success(function(data,status){
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
      var isSure = $modal.open({
        templateUrl: 'isSureModal.html',
        controller: ModalIsSureCtrl,
        resolve: {
          prepid: function() {
            return id;
          },
          action: function() {
            return 'delete';
          }
        }
      });
      isSure.result.then(function() {
        $scope.delete_object($location.search()["db_name"], id);
      });
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
          columns = _.keys($scope.result).sort();
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
    '    <li ng-repeat="elem in requests">'+
    '      <span ng-if="underscore.isArray(elem)">'+
    '        {{elem[0]}} <a ng-href="#" ng-click="removeFirstRequest($index)" ng-show="isEditable" title="Remove {{elem[0]}}"><i class="icon-minus"></i></a>' +
    '        <i class="icon-arrow-right"></i>'+
    '        {{elem[1]}} <a ng-href="#" ng-click="removeSecondRequest($index)" ng-show="isEditable" title="Remove {{elem[1]}}"><i class="icon-minus"></i></a>'+
    '      </span>'+
    '      <span ng-if="!underscore.isArray(elem)">'+
    '        {{elem}}'+
    '        <a ng-href="#" ng-click="removeRequest($index)" ng-show="isEditable" title="Remove {{elem}}"><i class="icon-minus"></i></a>'+
    '        <a ng-href="#" ng-click="showSearch($index)" ng-show="isEditable && !showSearchField[$index]" title="Make range"><i class="icon-plus"></i></a>'+
    '        <input type="text"'+
    '               style="margin: 0"'+
    '               ng-model="newRequestPrepid[$index]"'+
    '               ng-show="showSearchField[$index]"'+
    '               typeahead="suggestion for suggestion in preloadPossibleRequests($index, $viewValue)"'+
    '               typeahead-on-select=addRequest($index)>'+
    '        <a ng-href="#" ng-click="cancelSearch($index)" ng-show="isEditable && showSearchField[$index]" title="Cancel search"><i class="icon-minus"></i></a>'+
    '      </span>'+
    '    </li>'+
    '  </ul>'+
    '  <a ng-href="#" ng-click="showSearch(-1)" title="Add new request or range" ng-show="isEditable && !showSearchField[-1]"><i class="icon-plus"></i></a>'+
    '  <a ng-href="#" ng-click="cancelSearch(-1)" ng-show="isEditable && showSearchField[-1]" title="Cancel search"><i class="icon-minus"></i></a>'+
    '  <input type="text"'+
    '         style="margin: 0"'+
    '         ng-model="newRequestPrepid[-1]"'+
    '         ng-show="showSearchField[-1]"'+
    '         typeahead="suggestion for suggestion in preloadPossibleRequests(-1, $viewValue)"'+
    '         typeahead-on-select=addRequest(-1)>'+
    '</div>'+
    '',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.requests = ctrl.$viewValue;
        scope.showSearchField = {};
        scope.newRequestPrepid = {};
        scope.isEditable = scope.not_editable_list.indexOf('Requests') == -1;
        scope.refreshCampaignsForChains();
      };
      scope.showSearch = function(index) {
        scope.showSearchField[index] = true;
      }
      scope.cancelSearch = function(index) {
        scope.showSearchField[index] = false;
        scope.newRequestPrepid[index] = undefined;
      };
      scope.refreshCampaignsForChains = function() {
        $rootScope.campaignsForChains = scope.requests.map(x => 'chain_' + (_.isArray(x) ? x[0] : x).split('-')[1] + '*');
      };
      scope.addRequest = function(index) {
        const newPrepid = scope.newRequestPrepid[index].trim();
        if (!newPrepid || !newPrepid.length) {
          return
        }
        if (index == -1) {
          scope.requests.push(newPrepid);
        } else {
          scope.requests[index] = [scope.requests[index], newPrepid];
        }
        scope.cancelSearch(index);
        scope.refreshCampaignsForChains();
      };
      scope.removeRequest = function(index) {
        scope.requests.splice(index, 1);
        scope.refreshCampaignsForChains();
      }
      scope.removeFirstRequest = function(index) {
        scope.requests[index] = scope.requests[index][1];
      }
      scope.removeSecondRequest = function(index) {
        scope.requests[index] = scope.requests[index][0];
      }
      scope.preloadPossibleRequests = function(index, viewValue) {
        const firstPrepid = index != -1 ? scope.requests[index] : undefined;
        if (index != -1) {
          let pattern = firstPrepid.split('-');
          let sequence = viewValue.split('-');
          viewValue = pattern[0] + '-' + pattern[1] + '-' + (sequence.length == 3 ? sequence[2] : '');
        }
        const campaign = $rootScope.campaignsForRequests.length ? '&member_of_campaign=' + $rootScope.campaignsForRequests.join(',') : '';
        const promise = $http.get("search?db_name=requests&prepid=" + viewValue + "*" + campaign);
        return promise.then(function(data){
          return data.data.results.map(x => x['prepid']).filter(x => x != firstPrepid);
        }, function(data){
          alert("Error getting requests: " + data.data);
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
    '    <li ng-repeat="chainedCampaign in chainedCampaigns">'+
    '      <span>'+
    '        {{chainedCampaign}}'+
    '        <a ng-href="#" ng-click="removeChain($index)" ng-show="isEditable">'+
    '          <i class="icon-remove-sign"></i>'+
    '        </a>'+
    '      <span>'+
    '    </li>'+
    '  </ul>'+
    '  <a ng-show="isEditable" ng-href="#" ng-click="showSearchField = !showSearchField">'+
    '    <i class="icon-plus" ng-hide="showSearchField"></i>'+
    '    <i class="icon-minus" ng-show="showSearchField"></i>'+
    '  </a>'+
    '  <input type="text"'+
    '         style="margin: 0"'+
    '         placeholder="chain_..."'+
    '         ng-model="newChainPrepid"'+
    '         ng-show="showSearchField"'+
    '         typeahead="suggestion for suggestion in preloadPossibleChains($viewValue)"'+
    '         typeahead-on-select=addChain(newChainPrepid)>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.chainedCampaigns = ctrl.$viewValue;
        scope.isEditable = scope.not_editable_list.indexOf('Chains') == -1;
        scope.refreshCampaignsForRequests();
        scope.showSearchField = false;
        scope.newChainPrepid = "";
        scope.suggestionCache = {};
        scope.newestSuggestions = [];
      };
      scope.refreshCampaignsForRequests = function() {
        $rootScope.campaignsForRequests = scope.chainedCampaigns.map(x => x.split('_')[1]);
      };
      scope.removeChain = function(index) {
        scope.chainedCampaigns.splice(index,1);
        scope.refreshCampaignsForRequests();
      };
      scope.addChain = function(item) {
        if (!item || !item.trim().length) {
          return
        }
        if (scope.newestSuggestions.indexOf(item) < 0) {
          return
        }
        scope.chainedCampaigns.push(item);
        scope.refreshCampaignsForRequests();
        scope.newChainPrepid = "";
        scope.showSearchField = false;
      };
      scope.preloadPossibleChains = function(viewValue) {
        if (!viewValue.length) {
          return [];
        }
        const campaign = $rootScope.campaignsForChains.length ? '&prepid___=' + $rootScope.campaignsForChains.join(',') : '';
        const url = "search/?db_name=chained_campaigns&enabled=true&prepid=" + viewValue + "*" + campaign;
        if (scope.suggestionCache[url]) {
          const suggestions = scope.suggestionCache[url];
          scope.newestSuggestions = suggestions.filter(x => scope.chainedCampaigns.indexOf(x) < 0);
          return scope.newestSuggestions;
        }
        const promise = $http.get(url);
        return promise.then(function(data){
          const suggestions = data.data.results.map(x => x.prepid);
          scope.suggestionCache[url] = suggestions;
          scope.newestSuggestions = suggestions.filter(x => scope.chainedCampaigns.indexOf(x) < 0);
          return scope.newestSuggestions;
        }, function(data){
          alert("Error getting chained campaigns: " + data.data);
          return [];
        });
      };
    }
  }
});
