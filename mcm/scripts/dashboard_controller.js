angular.module('mcmApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
    function resultsCtrl($scope, $http, $location, $window) {
      $scope.validation_info = {};
      $scope.submission_info = {}
      $scope.getValidationInfo = function () {
        $http.get("restapi/dashboard/get_validation_info").then(function (data, status) {
          $scope.validation_info = data.data;
        }, function (data, status) {
          $scope.validation_info = {};
        });
      };
      $scope.getSubmissionInfo = function () {
        $http.get("restapi/dashboard/get_submission_info").then(function (data, status) {
          $scope.submission_info = data.data;
        }, function (data, status) {
          $scope.submission_info = {};
        });
      };

      $scope.getValidationInfo();
      $scope.getSubmissionInfo();
    }
  ]);
