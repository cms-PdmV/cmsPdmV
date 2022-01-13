angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {
      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Approval', select: true, db_name: 'approval' },
        { text: 'Chain', select: true, db_name: 'chain' },
      ];

      $scope.dbName = "chained_requests";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);

      $scope.actionMessage = {};
      $scope.underscore = _;
      $scope.shortView = {};

      $scope.tabsettings = {
        "view": {
          active: false
        },
        "search": {
          active: false
        },
        "navigation": {
          active: false
        },
        "navigation2": {
          active: false
        }
      };

      $scope.actionPrompt = function (action, prepid) {
        $scope.openIsSureModal($scope.dbName, prepid, action, function (database, prepid, action) {
          $scope.objectAction(action, prepid);
        });
      }

      $scope.objectAction = function (action, prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid = [prepid];
        for (let prepid of prepids) {
          // Reset messages
          $scope.actionMessage[prepid] = 'loading';
        }
        $http({ method: 'GET', url: 'restapi/chained_requests/' + action + '/' + prepids.join(',') }).success(function (data, status) {
          let results = prepids.length == 1 ? [data] : data;
          let shouldGetData = false;
          for (let result of results) {
            $scope.actionMessage[result.prepid] = result.results ? 'OK' : result.message;
            shouldGetData = shouldGetData || !!result.results;
          }
          if (shouldGetData) {
            $scope.getData();
          }
        }).error(function (data, status) {
          $scope.openErrorModal(undefined, data['message'])
        });
      };

      $scope.setLoading = function(prepids, loading) {
        for (let prepid of prepids) {
          $scope.actionMessage[prepid] = loading ? 'loading' : '';
        }
      }

      $scope.rewindToRoot = function(prepids) {
        $scope.questionModal('Are you sure you want to rewind to root?', function() {
          $scope.setLoading(prepids, true);
          $http({ method: 'POST', url: 'restapi/chained_requests/rewind_to_root', data: {'prepid': prepids}}).success(function (data, status) {
            let results = prepids.length == 1 ? [data] : data;
            let shouldGetData = false;
            for (let result of results) {
              $scope.actionMessage[result.prepid] = result.results ? 'OK' : result.message;
              shouldGetData = shouldGetData || !!result.results;
            }
            if (shouldGetData) {
              $scope.getData();
            }
          }).error(function (data, status) {
            $scope.openErrorModal(undefined, data['message']);
            $scope.setLoading(prepids, false);
          });
        });
      };

      $scope.rewind = function(prepids) {
        $scope.questionModal('Are you sure you want to rewind?', function() {
          $scope.setLoading(prepids, true);
          $http({ method: 'POST', url: 'restapi/chained_requests/rewind', data: {'prepid': prepids}}).success(function (data, status) {
            let results = prepids.length == 1 ? [data] : data;
            let shouldGetData = false;
            for (let result of results) {
              $scope.actionMessage[result.prepid] = result.results ? 'OK' : result.message;
              shouldGetData = shouldGetData || !!result.results;
            }
            if (shouldGetData) {
              $scope.getData();
            }
          }).error(function (data, status) {
            $scope.openErrorModal(undefined, data['message']);
            $scope.setLoading(prepids, false);
          });
        });
      };

      $scope.flow = function(prepids) {
        $scope.questionModal('Are you sure you want to flow?', function() {
          $scope.setLoading(prepids, true);
          $http({ method: 'POST', url: 'restapi/chained_requests/flow', data: {'prepid': prepids}}).success(function (data, status) {
            let results = prepids.length == 1 ? [data] : data;
            let shouldGetData = false;
            for (let result of results) {
              $scope.actionMessage[result.prepid] = result.results ? 'OK' : result.message;
              shouldGetData = shouldGetData || !!result.results;
            }
            if (shouldGetData) {
              $scope.getData();
            }
          }).error(function (data, status) {
            $scope.openErrorModal(undefined, data['message']);
            $scope.setLoading(prepids, false);
          });
        });
      };

      $scope.loadShortView = function (prepid) {
        let prepids = new Set(prepid == 'selected' ? $scope.selected_prepids : prepid = [prepid]);
        let chains = $scope.result.filter(x => prepids.has(x.prepid));
        let cached = new Set(Object.keys($scope.shortView));
        let requests = [...new Set(chains.map(x => x.chain).flat().filter(x => !cached.has(x)))];
        if (!requests.length) {
          return;
        }
        const status_map = {
          'submit-done': 'led-green.gif',
          'submit-submitted': 'led-blue.gif',
          'submit-approved': 'led-red.gif',
          'approve-approved': 'led-orange.gif',
          'define-defined': 'led-yellow.gif',
          'validation-validation': 'led-purple.gif',
          'validation-new': 'led-aqua.gif',
          'none-new': 'led-gray.gif'
        }
        for (let prepid of requests) {
          $scope.shortView[prepid] = ['Loading...', 'processing-bg.gif'];
        }
        const chunkify = function (items, chuckSize, callback) {
          for (i = 0, j = items.length; i < j; i += chuckSize) {
            callback(items.slice(i, i + chuckSize));
          }
        };
        chunkify(requests, 50, function (chunk) {
          $http({ method: 'GET', url: 'public/restapi/requests/get_status_and_approval/' + chunk.join(',') }).success(function (data, status) {
            for (let prepid in data) {
              let requestStatus = data[prepid];
              if (status_map[requestStatus]) {
                $scope.shortView[prepid] = [requestStatus, status_map[requestStatus]];
              } else {
                $scope.shortView[prepid] = [requestStatus, 'icon-question-sign'];
              }
            }
          }).error(function (status) {
            for (let prepid in chunk) {
              delete $scope.shortView[prepid];
            }
          });
        });
      };

      $scope.statusIcon = function (value) {
        icons = {
          'new': 'icon-edit',
          'validation': 'icon-eye-open',
          'defined': 'icon-check',
          'approved': 'icon-share',
          'submitted': 'icon-inbox',
          'injected': 'icon-envelope',
          'done': 'icon-ok'
        }
        if (icons[value]) {
          return icons[value];
        } else {
          return "icon-question-sign";
        }
      };

      $scope.approvalIcon = function (value) {
        icons = {
          'none': 'icon-off',
          'flow': 'icon-share',
          'submit': 'icon-ok'
        }
        if (icons[value]) {
          return icons[value];
        } else {
          return "icon-question-sign";
        }
      };

      $scope.$watch(function () {
        var loc_dict = $location.search();
        return "page" + loc_dict["page"] + "limit" + loc_dict["limit"];
      }, function () {
        $scope.getData();
        $scope.selected_prepids = [];
      });

      $scope.openReserveChainModal = function (chainedRequest) {
        let chainedRequests = chainedRequest == 'selected' ? $scope.result.filter(x => $scope.selected_prepids.includes(x.prepid)): [chainedRequest];
        $modal.open({
          templateUrl: 'reserveChainModal.html',
          controller: function ($scope, $modalInstance, $http, chainedRequests, objectAction) {
            $scope.chainedRequests = chainedRequests.map(x => Object({'prepid': x.prepid,
                                                                      'member_of_campaign': x.member_of_campaign,
                                                                      'campaigns': ['---'],
                                                                      'campaign': []}))
            let chainedCampaigns = [...$scope.chainedRequests.map(x => x.member_of_campaign)]
            for (let chainedCampaignPrepid of chainedCampaigns) {
              $http.get("restapi/chained_campaigns/get/" + chainedCampaignPrepid).then(function (data) {
                let chainedCampaign = data.data.results;
                for (let chainedRequest of $scope.chainedRequests) {
                  if (chainedRequest.member_of_campaign == chainedCampaign.prepid) {
                    chainedRequest.campaigns = ['---'].concat(chainedCampaign.campaigns.map(x => x[0]));
                    chainedRequest.campaign = chainedRequest.campaigns[0];
                  }
                }
              });
            }
            $scope.confirm = function () {
              for (let chainedRequest of $scope.chainedRequests) {
                if (chainedRequest.campaign == undefined || chainedRequest.campaign == '---') {
                  objectAction('flow', chainedRequest.prepid + '/reserve');
                } else {
                  objectAction('flow', chainedRequest.prepid + '/reserve/' + chainedRequest.campaign);
                }
              }
              $modalInstance.close();
            };
            $scope.cancel = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            chainedRequests: function () { return chainedRequests; },
            objectAction: function() { return $scope.objectAction; },
          }
        });
      };

      $scope.add_to_selected_list = function (prepid) {
        if (_.contains($scope.selected_prepids, prepid)) {
          $scope.selected_prepids = _.without($scope.selected_prepids, prepid)
        } else
          $scope.selected_prepids.push(prepid);
      };

      $scope.toggleAll = function () {
        if ($scope.selected_prepids.length != $scope.result.length) {
          _.each($scope.result, function (v) {
            $scope.selected_prepids.push(v.prepid);
          });
          $scope.selected_prepids = _.uniq($scope.selected_prepids);
        } else {
          $scope.selected_prepids = [];
        }
      };

      $scope.upload = function (file) {
        /*Upload a file to server*/
        $scope.got_results = false;
        $http({ method: 'PUT', url: 'restapi/' + $scope.dbName + '/listwithfile', data: file }).success(function (data, status) {
          $scope.result = data.results;
          $scope.result_status = data.status;
          $scope.got_results = true;
        }).error(function (data, status) {
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = data.status;
        });
      };
    }]);

// NEW for directive
// var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("loadFields", function ($http, $location) {
  return {
    replace: true,
    restrict: 'E',
    template:
      '<div>' +
      '  <form class="form-inline">' +
      '    <span class="control-group navigation-form" ng-repeat="key in searchable_fields">' +
      '      <label style="width:140px;">{{key}}</label>' +
      '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">' +
      '    </span>' +
      '  </form>' +
      '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>' +
      '  <button type="button" class="btn btn-small" ng-click="getSearch();">Reload menus</button>' +
      '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>' +
      '</div>'
    ,
    link: function (scope, element, attr) {
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
        var promise = $http.get("restapi/" + scope.dbName + "/searchable/do");
        scope.loadingData = true;
        promise.then(function (data) {
          scope.loadingData = false;
          scope.searchable = data.data;
          _.each(scope.searchable, function (element, key) {
            element.unshift("------"); //lets insert into begining of array an default value to not include in search
            scope.listfields[key] = "------";
          });
        }, function (data) {
          scope.loadingData = false;
          alert("Error getting searchable fields: " + data.status);
        });
      };
      scope.cleanSearchUrl = function () {
        _.each($location.search(), function (elem, key) {
          $location.search(key, null);
        });
        $location.search("page", 0);
      };
      scope.getUrl = function () {
        scope.cleanSearchUrl();
        //var url = "?";
        _.each(scope.listfields, function (value, key) {
          if (value != "") {
            //url += key +"=" +value+"&";
            $location.search(key, String(value));
          } else {
            $location.search(key, null);//.remove(key);
          }
        });
        scope.getData();
      };
      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        const searchURL = "restapi/chained_requests/unique_values/" + fieldName + "?key=" + fieldValue;
        return $http.get(searchURL).then(function (data) {
          return data.data.results;
        }, function (data) {
          alert("Error getting suggestions for " + fieldName + "=" + fieldValue + ": " + data.status);
        });
      };
    }
  }
});
testApp.directive("loadRequestsFields", function ($http, $location) {
  return {
    replace: true,
    restrict: 'E',
    template:
      '<div>' +
      '  <form class="form-inline">' +
      '    <span class="control-group navigation-form" ng-repeat="key in searchable_fields">' +
      '      <label style="width:140px;">{{key}}</label>' +
      '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">' +
      '    </span>' +
      '  </form>' +
      '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>' +
      '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>' +
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
        _.each($location.search(), function (elem, key) {
          $location.search(key, null);
        });
        $location.search("page", 0);
      };
      scope.getUrl = function () {
        scope.cleanSearchUrl();
        _.each(scope.listfields, function (value, key) {
          if (value != "") {
            $location.search(key, String(value));
          } else {
            $location.search(key, null);//.remove(key);
          }
        });
        $location.search("searchByRequests", true);
        scope.getData();
      };
      scope.toggleSelectOption = function (option) {
        if (scope.showOption[option]) {
          scope.showOption[option] = false;
        } else {
          scope.showOption[option] = true;
        }
      };
      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        const searchURL = "restapi/chained_requests/unique_values/" + fieldName + "?key=" + fieldValue;
        return $http.get(searchURL).then(function (data) {
          return data.data.results;
        }, function (data) {
          alert("Error getting suggestions for " + fieldName + "=" + fieldValue + ": " + data.status);
        });
      };
    }
  }
});
