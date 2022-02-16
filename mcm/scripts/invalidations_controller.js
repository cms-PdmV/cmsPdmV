angular.module('mcmApp').controller('invalidationController',
  ['$scope', '$http', '$location', '$window',
    function invalidationController($scope, $http, $location, $window) {
      $scope.columns = [
        { text: 'Object', select: true, db_name: 'object' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Type', select: true, db_name: 'type' },
        { text: 'Prepid', select: true, db_name: 'prepid' },
      ];
      $scope.setDatabaseInfo('invalidations', $scope.columns);
      $scope.selectedItems = [];

    }
  ]);
