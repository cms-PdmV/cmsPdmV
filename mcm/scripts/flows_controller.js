angular.module('mcmApp').controller('flowController',
  ['$scope',
    function flowController($scope) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Approval', select: true, db_name: 'approval' },
        { text: 'Allowed Campaigns', select: true, db_name: 'allowed_campaigns' },
        { text: 'Next Campaign', select: true, db_name: 'next_campaign' }
      ];
      $scope.setDatabaseInfo('flows', $scope.columns);

      $scope.nextApproval = function (prepid) {
        $scope.objectAction(undefined,
          [prepid],
          {method: 'POST',
           url: 'restapi/' + $scope.database + '/type',
           data: {'prepid': prepid}});
      };
    }
  ]
);
