angular.module('mcmApp').controller('settingController',
  ['$scope',
    function settingController($scope) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Value', select: true, db_name: 'value' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.setDatabaseInfo('settings', $scope.columns);

      $scope.stringify = function(item) {
        return JSON.stringify(item, null, 2);
      }
    }
  ]
);