angular.module('mcmApp').controller('userController',
  ['$scope', '$http',
    function userController($scope, $http) {
      $scope.columns = [
        { text: 'Username', select: true, db_name: 'username' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Full name', select: true, db_name: 'fullname' },
        { text: 'Email', select: false, db_name: 'email' },
        { text: 'Role', select: true, db_name: 'role' },
        { text: 'PWG', select: true, db_name: 'pwg' }
      ];

      $scope.setDatabaseInfo('users', $scope.columns);
      $scope.addMe = function () {
        $http({ method: 'POST', url: 'restapi/users/add'}).then(function (data) {
          if (data.data.results) {
            $scope.getData();
          } else {
            $scope.openErrorModal(undefined, data.data.message);
          }
        }), function (data) {
          $scope.openErrorModal(undefined, data.data.message);
        };
      };

      $scope.roleChange = function (userDict, change) {
        let role = userDict['role'];
        role = $scope.roles[$scope.roles.indexOf(role) + change];
        userDict['role'] = role;
        $http({ method: 'POST', url: 'restapi/users/update', data: userDict}).then(function (data) {
          if (data.data.results) {
            $scope.getData();
          } else {
            $scope.openErrorModal(undefined, data.data.message);
          }
        }), function (data) {
          $scope.openErrorModal(undefined, data.data.message);
        };
      };
    }
  ]
);