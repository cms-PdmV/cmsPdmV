angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Approval', select: true, db_name: 'approval' },
        { text: 'Allowed Campaigns', select: true, db_name: 'allowed_campaigns' },
        { text: 'Next Campaign', select: true, db_name: 'next_campaign' }
      ];
      $scope.dbName = "flows";
      $scope.actionMessage = {};
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.approvalIcon = function (value) {
        icons = {
          'none': 'icon-off',
          'flow': 'icon-share',
          'submit': 'icon-ok'
        }
        if (icons[value]) {
          return icons[value];
        }
        return "icon-question-sign";
      };
      $scope.setLoading = function(prepids, loading) {
        for (let prepid of prepids) {
          $scope.actionMessage[prepid] = loading ? 'loading' : '';
        }
      }

      $scope.nextApproval = function (prepid) {
        $scope.setLoading([prepid], true);
        $http({ method: 'POST', url: 'restapi/' + $scope.dbName + '/approve/' + prepid }).success(function (data, status) {
          $scope.actionMessage[prepid] = data.results ? 'OK' : data.message;
          if (data.results) {
            $scope.getData();
          }
        }).error(function (data, status) {
          $scope.openErrorModal(prepid, data['message']);
          $scope.setLoading([prepid], false);
        });
      };
    }
  ]
);
