angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.underscore = _;
      $scope.update = [];
      $scope.editingInfo = {};
      $scope.editableObject = {};

      const urlParams = $location.search()
      $scope.dbName = urlParams['db_name'];
      $scope.prepid = urlParams['prepid'];

      $scope.getObject = function () {
        let url = 'restapi/' + $scope.dbName + '/get_editable/' + $scope.prepid;
        $http.get(url).success(function (data) {
          if (data.results) {
            $scope.parseEditableObject(data.results);
          } else {
            $scope.openErrorModal(data.prepid, data['message']);
          }
        }).error(function (data, status) {
          $scope.openErrorModal(data.prepid, data['message']);
        });
      };
      setTimeout(() => {
        $scope.getObject();
      }, 1000);

      $scope.parseEditableObject = function(editableDict) {
        $scope.editingInfo = editableDict.editing_info;
        const hide = ['history', '_id', '_rev', 'next', 'reqmgr_name', 'config_id',
                      'output_dataset', 'member_of_chain', 'member_of_campaign',
                      'campaigns'];
        for (let attr of hide) {
          delete $scope.editingInfo[attr];
        }
        $scope.editableObject = editableDict.object;
      };

      $scope.openSequenceEdit = function(sequence, onSave) {
        $modal.open({
          templateUrl: 'editSequenceModal.html',
          controller: function ($scope, $modalInstance, $window, $http, sequence, onSave, attributeType) {
            $scope.sequence = JSON.parse(JSON.stringify(sequence));
            $scope.attributeType = attributeType;
            $scope.save = function () {
              onSave($scope.sequence);
              $modalInstance.close();
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            sequence: function () { return sequence; },
            onSave: function () { return onSave; },
            attributeType: function () { return $scope.attributeType; },
          }
        })
      };

      $scope.attributeType = function(attribute) {
        let type = typeof(attribute)
        if (type != 'object') {
          return type;
        }
        if (Array.isArray(attribute)) {
          return 'array';
        }
        return type;
      }

      $scope.deleteEditableObject = function () {
        let prepid = $scope.prepid;
        const action = function() {
          $http({method: 'DELETE', url: 'restapi/' + $scope.dbName + '/delete/' + prepid}).success(function (result, status) {
            if (result.results) {
              $window.location.href = $scope.database;
            } else {
              $scope.openErrorModal(prepid, result['message']);
            }
          }).error(function (data, status) {
            $scope.openErrorModal(prepid, data['message']);
          });
        }
        $scope.questionModal('Are you sure you want to delete ' + prepid, function() {
          action();
        });
      };

      $scope.booleanize_sequence = function (sequence) {
        _.each(sequence, function (value, key) {
          if (_.isString(value)) {
            switch (value.toLowerCase()) {
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

      $scope.submit_edit = function () {
        switch ($scope.dbName) {
          case "requests":
            _.each($scope.result["sequences"], function (sequence) {
              $scope.booleanize_sequence(sequence);
              if (_.isString(sequence["step"])) {
                sequence["step"] = sequence["step"].split(",");
              }
              if (_.isString(sequence["datatier"])) {
                sequence["datatier"] = sequence["datatier"].split(",");
              }
              if (_.isString(sequence["eventcontent"])) {
                sequence["eventcontent"] = sequence["eventcontent"].split(",");
              }
            });
            _.each($scope.result["time_event"], function (value, key) {
              $scope.result["time_event"][key] = parseFloat(value);
            });
            _.each($scope.result["size_event"], function (value, key) {
              $scope.result["size_event"][key] = parseFloat(value);
            });
            $scope.result["memory"] = parseFloat($scope.result["memory"]);
            $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function (tok) { return tok.value });
            break;
          case "campaigns":
            _.each($scope.result["sequences"], function (sequence) {
              _.each(sequence, function (subSequence, key) {
                if (key != "$$hashKey") //ignore angularhs hashkey
                {
                  $scope.booleanize_sequence(subSequence);
                  if (_.isString(subSequence["step"])) {
                    subSequence["step"] = subSequence["step"].split(",");
                  }
                  if (_.isString(subSequence["datatier"])) {
                    subSequence["datatier"] = subSequence["datatier"].split(",");
                  }
                  if (_.isString(subSequence["eventcontent"])) {
                    subSequence["eventcontent"] = subSequence["eventcontent"].split(",");
                  }
                }
              });
            });
            break;
          case "mccms":
            $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function (tok) { return tok.value });
            break;
          case "flows":
            _.each($scope.result["request_parameters"]["sequences"], function (sequence) {
              _.each(sequence, function (elem) {
                if (_.has(elem, "datatier")) {
                  if (_.isString(elem["datatier"])) {
                    elem["datatier"] = elem["datatier"].split(",");
                  }
                }
                if (_.has(elem, "eventcontent")) {
                  if (_.isString(elem["eventcontent"])) {
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
        $http({ 'method': method, url: 'restapi/' + $location.search()["db_name"] + '/update', data: angular.toJson($scope.result) }).success(function (data, status) {
          $scope.update["success"] = data["results"];
          $scope.update["fail"] = false;
          $scope.update["message"] = data["message"];
          $scope.update["status_code"] = status;
          if ($scope.update["success"] == false) {
            $scope.update["fail"] = true;
          } else {
            $scope.getData();
          }
        }).error(function (data, status) {
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });
      };

      $scope.editableFragment = function () {
        return $scope.not_editable_list.indexOf('Fragment') != -1;
      };

      $scope.hideSequence = function (roleNumber) {
        return false;
      };

      $scope.removeUserPWG = function (elem) {
        //console.log(_.without($scope.result["pwg"], elem));
        $scope.result["pwg"] = _.without($scope.result["pwg"], elem);
      };

      $scope.showAddUserPWG = function () {
        $scope.showSelectPWG = true;
        var promise = $http.get("restapi/users/get_pwg")
        promise.then(function (data) {
          $scope.all_pwgs = data.data.results;
        });
      };

      $scope.addUserPWG = function (elem) {
        if ($scope.result["pwg"].indexOf(elem) == -1) {
          $scope.result["pwg"].push(elem);
        }
      };

      $scope.addToken = function (tok) {
        $http({ method: 'PUT', url: 'restapi/tags/add/', data: JSON.stringify({ tag: tok.value }) })
      };
    }
  ]);

testApp.directive("customRequestsEdit", function ($http, $rootScope) {
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template:
      '<div>' +
      '  <ul>' +
      '    <li ng-repeat="elem in requests">' +
      '      <span ng-if="underscore.isArray(elem)">' +
      '        {{elem[0]}} <a ng-href="#" ng-click="removeFirstRequest($index)" ng-show="isEditable" title="Remove {{elem[0]}}"><i class="icon-minus"></i></a>' +
      '        <i class="icon-arrow-right"></i>' +
      '        {{elem[1]}} <a ng-href="#" ng-click="removeSecondRequest($index)" ng-show="isEditable" title="Remove {{elem[1]}}"><i class="icon-minus"></i></a>' +
      '      </span>' +
      '      <span ng-if="!underscore.isArray(elem)">' +
      '        {{elem}}' +
      '        <a ng-href="#" ng-click="removeRequest($index)" ng-show="isEditable" title="Remove {{elem}}"><i class="icon-minus"></i></a>' +
      '        <a ng-href="#" ng-click="showSearch($index)" ng-show="isEditable && !showSearchField[$index]" title="Make range"><i class="icon-plus"></i></a>' +
      '        <input type="text"' +
      '               style="margin: 0"' +
      '               ng-model="newRequestPrepid[$index]"' +
      '               ng-show="showSearchField[$index]"' +
      '               typeahead="suggestion for suggestion in preloadPossibleRequests($index, $viewValue)"' +
      '               typeahead-on-select=addRequest($index)>' +
      '        <a ng-href="#" ng-click="cancelSearch($index)" ng-show="isEditable && showSearchField[$index]" title="Cancel search"><i class="icon-minus"></i></a>' +
      '      </span>' +
      '    </li>' +
      '  </ul>' +
      '  <a ng-href="#" ng-click="showSearch(-1)" title="Add new request or range" ng-show="isEditable && !showSearchField[-1]"><i class="icon-plus"></i></a>' +
      '  <a ng-href="#" ng-click="cancelSearch(-1)" ng-show="isEditable && showSearchField[-1]" title="Cancel search"><i class="icon-minus"></i></a>' +
      '  <input type="text"' +
      '         style="margin: 0"' +
      '         ng-model="newRequestPrepid[-1]"' +
      '         ng-show="showSearchField[-1]"' +
      '         typeahead="suggestion for suggestion in preloadPossibleRequests(-1, $viewValue)"' +
      '         typeahead-on-select=addRequest(-1)>' +
      '</div>' +
      '',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function () {
        scope.requests = ctrl.$viewValue;
        scope.showSearchField = {};
        scope.newRequestPrepid = {};
        scope.isEditable = scope.not_editable_list.indexOf('Requests') == -1;
        scope.refreshCampaignsForChains();
      };
      scope.showSearch = function (index) {
        scope.showSearchField[index] = true;
      }
      scope.cancelSearch = function (index) {
        scope.showSearchField[index] = false;
        scope.newRequestPrepid[index] = undefined;
      };
      scope.refreshCampaignsForChains = function () {
        $rootScope.campaignsForChains = scope.requests.map(x => 'chain_' + (_.isArray(x) ? x[0] : x).split('-')[1] + '*');
      };
      scope.addRequest = function (index) {
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
      scope.removeRequest = function (index) {
        scope.requests.splice(index, 1);
        scope.refreshCampaignsForChains();
      }
      scope.removeFirstRequest = function (index) {
        scope.requests[index] = scope.requests[index][1];
      }
      scope.removeSecondRequest = function (index) {
        scope.requests[index] = scope.requests[index][0];
      }
      scope.preloadPossibleRequests = function (index, viewValue) {
        const firstPrepid = index != -1 ? scope.requests[index] : undefined;
        if (index != -1) {
          let pattern = firstPrepid.split('-');
          let sequence = viewValue.split('-');
          viewValue = pattern[0] + '-' + pattern[1] + '-' + (sequence.length == 3 ? sequence[2] : '');
        }
        const campaign = $rootScope.campaignsForRequests.length ? '&member_of_campaign=' + $rootScope.campaignsForRequests.join(',') : '';
        const promise = $http.get("search?db_name=requests&prepid=" + viewValue + "*" + campaign);
        return promise.then(function (data) {
          return data.data.results.map(x => x['prepid']).filter(x => x != firstPrepid);
        }, function (data) {
          alert("Error getting requests: " + data.data);
        });
      };
    }
  }
});

testApp.directive("customMccmChains", function ($http, $rootScope) {
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
      '<div>' +
      '  <ul>' +
      '    <li ng-repeat="chainedCampaign in chainedCampaigns">' +
      '      <span>' +
      '        {{chainedCampaign}}' +
      '        <a ng-href="#" ng-click="removeChain($index)" ng-show="isEditable">' +
      '          <i class="icon-remove-sign"></i>' +
      '        </a>' +
      '      <span>' +
      '    </li>' +
      '  </ul>' +
      '  <a ng-show="isEditable" ng-href="#" ng-click="showSearchField = !showSearchField">' +
      '    <i class="icon-plus" ng-hide="showSearchField"></i>' +
      '    <i class="icon-minus" ng-show="showSearchField"></i>' +
      '  </a>' +
      '  <input type="text"' +
      '         style="margin: 0"' +
      '         placeholder="chain_..."' +
      '         ng-model="newChainPrepid"' +
      '         ng-show="showSearchField"' +
      '         typeahead="suggestion for suggestion in preloadPossibleChains($viewValue)"' +
      '         typeahead-on-select=addChain(newChainPrepid)>' +
      '</div>' +
      '',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function () {
        scope.chainedCampaigns = ctrl.$viewValue;
        scope.isEditable = scope.not_editable_list.indexOf('Chains') == -1;
        scope.refreshCampaignsForRequests();
        scope.showSearchField = false;
        scope.newChainPrepid = "";
        scope.suggestionCache = {};
        scope.newestSuggestions = [];
      };
      scope.refreshCampaignsForRequests = function () {
        $rootScope.campaignsForRequests = scope.chainedCampaigns.map(x => x.split('_')[1]);
      };
      scope.removeChain = function (index) {
        scope.chainedCampaigns.splice(index, 1);
        scope.refreshCampaignsForRequests();
      };
      scope.addChain = function (item) {
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
      scope.preloadPossibleChains = function (viewValue) {
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
        return promise.then(function (data) {
          const suggestions = data.data.results.map(x => x.prepid);
          scope.suggestionCache[url] = suggestions;
          scope.newestSuggestions = suggestions.filter(x => scope.chainedCampaigns.indexOf(x) < 0);
          return scope.newestSuggestions;
        }, function (data) {
          alert("Error getting chained campaigns: " + data.data);
          return [];
        });
      };
    }
  }
});
