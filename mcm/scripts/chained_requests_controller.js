angular.module('mcmApp').controller('chainedRequestController',
  ['$scope', '$http',
    function chainedRequestController($scope, $http) {
      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Enabled', select: true, db_name: 'enabled' },
        { text: 'Chain', select: true, db_name: 'chain' },
      ];

      $scope.setDatabaseInfo('chained_requests', $scope.columns);
      $scope.shortView = {};
      $scope.selectedItems = [];

      $scope.validate = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        $scope.objectAction(undefined,
          prepids,
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/validate',
           data: {'prepid': prepids}});
      };

      $scope.toggleEnabled = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to toggle enabled status of ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
          prepids,
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/toggle_enabled',
           data: {'prepid': prepids}});
      };

      $scope.rewind = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to rewind ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
          prepids,
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/rewind',
           data: {'prepid': prepids}});
      };

      $scope.rewindToRoot = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to rewind ' + $scope.promptPrepid(prepids) + ' to root?';
        $scope.objectAction(message,
          prepids,
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/rewind_to_root',
           data: {'prepid': prepids}});
      };

      $scope.flow = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to flow ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
          prepids,
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/flow',
           data: {'prepid': prepids}});
      };

      $scope.loadShortView = function (prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let prepidsToFetch = [];
        for (let prepid of prepids) {
          if (!$scope.shortView[prepid]) {
            prepidsToFetch.push(prepid);
          }
        }
        if (!prepidsToFetch.length) {
          for (let prepid of prepids) {
            delete $scope.shortView[prepid];
          }
          return;
        }
        let chains = $scope.result.filter(x => prepidsToFetch.includes(x.prepid));
        let requests = [...new Set(chains.map(x => x.chain).flat())];
        const statusMap = {
          'submit-done': 'led-green.gif',
          'submit-submitted': 'led-blue.gif',
          'submit-approved': 'led-red.gif',
          'approve-approved': 'led-orange.gif',
          'define-defined': 'led-yellow.gif',
          'validation-validation': 'led-purple.gif',
          'validation-new': 'led-aqua.gif',
          'none-new': 'led-gray.gif'
        }
        const chunkify = function (items, chuckSize, callback) {
          for (i = 0, j = items.length; i < j; i += chuckSize) {
            callback(items.slice(i, i + chuckSize));
          }
        };
        chunkify(requests, 50, function (requestsChunk) {
          for (let chain of chains) {
            for (let request of requestsChunk) {
              if (chain.chain.includes(request)) {
                if (!$scope.shortView[chain.prepid]) {
                  $scope.shortView[chain.prepid] = {};
                }
                $scope.shortView[chain.prepid][request] = ['Loading...', 'processing-bg.gif']
              }
            }
          }
          $http({ method: 'GET', url: 'public/restapi/requests/get_status_and_approval/' + requestsChunk.join(',') }).then(function (data) {
            for (let chain of chains) {
              for (let request of requestsChunk) {
                if ($scope.shortView[chain.prepid][request]) {
                  let requestStatus = data.data[request];
                  if (statusMap[requestStatus]) {
                    $scope.shortView[chain.prepid][request] = [requestStatus, statusMap[requestStatus]];
                  } else {
                    $scope.shortView[chain.prepid][request] = ['Error status', 'led-cup-red-close.gif'];
                  }
                }
              }
            }
          }, function (data) {});
        });
      };

      $scope.openReserveChainModal = function (chainedRequest) {
        let chainedRequests = chainedRequest == 'selected' ? $scope.result.filter(x => $scope.selectedItems.includes(x.prepid)): [chainedRequest];
        $uibModal.open({
          templateUrl: 'reserveChainModal.html',
          controller: function ($scope, $uibModalInstance, $http, chainedRequests, objectAction) {
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
              $uibModalInstance.close();
            };
            $scope.cancel = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            chainedRequests: function () { return chainedRequests; },
            objectAction: function() { return $scope.objectAction; },
          }
        });
      };

      $scope.toggleSelection = function (prepid) {
        if ($scope.selectedItems.includes(prepid)) {
          $scope.selectedItems = $scope.selectedItems.filter(x => x != prepid);
        } else {
          $scope.selectedItems.push(prepid);
        }
      };

      $scope.toggleAll = function () {
        if ($scope.selectedItems.length != $scope.result.length) {
          $scope.selectedItems = $scope.result.map(x => x.prepid);
        } else {
          $scope.selectedItems = [];
        }
      };

      $scope.upload = function (file) {
        /*Upload a file to server*/
        $scope.got_results = false;
        $http({ method: 'PUT', url: 'restapi/' + $scope.database + '/listwithfile', data: file }).success(function (data, status) {
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
