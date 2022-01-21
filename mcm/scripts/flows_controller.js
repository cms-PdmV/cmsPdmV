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

      $scope.nextApproval = function (prepid) {
        $scope.objectAction(undefined,
          [prepid],
          {method: 'POST',
           url: 'restapi/' + $scope.dbName + '/approve',
           data: {'prepid': prepid}});
      };
    }
  ]
);
