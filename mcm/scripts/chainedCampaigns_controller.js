angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Alias', select: true, db_name: 'alias' },
        { text: 'Campaigns', select: true, db_name: 'campaigns' }
      ];
      $scope.dbName = "chained_campaigns";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);

      $scope._ = _; //enable underscorejs to be accessed from HTML template

      $scope.openChainCreationModal = function () {
        const modal = $modal.open({
          templateUrl: "chainedCampaignCreateModal.html",
          controller: function ($scope, $modalInstance, $window, $http, errorModal, setSuccess) {
            $scope.pairs = [{ campaigns: [], flows: [], selectedCampaign: '', selectedFlow: { prepid: undefined } }]
            let promise = $http.get("search?db_name=campaigns&page=-1");
            promise.then(function (data) {
              $scope.pairs[0].campaigns = data.data.results.filter(campaign => campaign.root != 1).map(campaign => campaign.prepid);
            });
            $scope.updateFlow = function (index) {
              while ($scope.pairs.length > index + 1) {
                $scope.pairs.pop();
              }
              if ($scope.pairs[index].selectedFlow.prepid !== '') {
                $scope.pairs[index].campaigns = [$scope.pairs[index].selectedFlow.next];
                $scope.pairs[index].selectedCampaign = $scope.pairs[index].selectedFlow.next;
                $scope.updateCampaign(index);
              } else {
                $scope.pairs[index].selectedCampaign = '';
              }
            }
            $scope.updateCampaign = function (index) {
              while ($scope.pairs.length > index + 1) {
                $scope.pairs.pop()
              }
              let promise = $http.get("search?db_name=flows&page=-1&allowed_campaigns=" + $scope.pairs[index].selectedCampaign);
              promise.then(function (data) {
                let nextFlows = data.data.results.map(flow => { const x = { 'prepid': flow.prepid, 'next': flow.next_campaign }; return x });
                if (nextFlows.length > 0) {
                  nextFlows.unshift({ 'prepid': '', 'next': '' })
                  $scope.pairs.push({ campaigns: [], flows: [], selectedCampaign: '', selectedFlow: nextFlows[0] })
                  $scope.pairs[index + 1].flows = nextFlows;
                }
              });
            }
            $scope.save = function () {
              $scope.pairs = $scope.pairs.filter(pair => pair.selectedCampaign && pair.selectedCampaign !== '')
              let campaigns = $scope.pairs.map(pair => { const x = [pair.selectedCampaign, pair.selectedFlow.prepid]; return x; })
              $http({ method: 'PUT', url: 'restapi/chained_campaigns/save/', data: { 'campaigns': campaigns } }).success(function (data, status) {
                setSuccess(data["results"]);
                if (data.results) {
                  $window.location.href = 'edit?db_name=chained_campaigns&query=' + data.prepid;
                } else {
                  errorModal(data.prepid, data['message']);
                  setSuccess(false, status);
                }
              }).error(function (data, status) {
                errorModal(data.prepid, data['message']);
                setSuccess(false, status);
              });
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            }
          },
          resolve: {
            errorModal: function () { return $scope.openErrorModal; },
            setSuccess: function () { return $scope.setSuccess; },
          }
        });
      };
    }
  ]
);
