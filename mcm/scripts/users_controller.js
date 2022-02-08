angular.module('mcmApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
    function resultsCtrl($scope, $http, $location, $window) {
      $scope.columns = [
        { text: 'Username', select: true, db_name: 'username' },
        { text: 'Full name', select: true, db_name: 'fullname' },
        { text: 'Actions', select: false, db_name: '' },
        { text: 'Email', select: false, db_name: 'email' },
        { text: 'Role', select: true, db_name: 'role' },
        { text: 'PWG', select: true, db_name: 'pwg' }
      ];
      $scope.dbName = "users";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.addMe = function () {
        $http({ method: 'POST', url: 'restapi/' + $scope.dbName + '/add'}).success(function (data, status) {
          $scope.setSuccess(data.results);
          if (data.results) {
            $scope.getData();
          } else {
            $scope.openErrorModal(undefined, data['message']);
          }
        }).error(function (data, status) {
          $scope.openErrorModal(undefined, data['message']);
          $scope.setSuccess(false, status);
        });
      };
    }
  ]
);