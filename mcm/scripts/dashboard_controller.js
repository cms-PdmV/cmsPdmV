angular.module('mcmApp').controller('dashboardController',
  ['$scope', '$http', '$location', '$window',
    function dashboardController($scope, $http, $location, $window) {
      $scope.validationInfo = '';
      $scope.submissionInfo = {};
      $scope.locksInfo = {};
      $scope.startTime = '';
      $scope.getValidationInfo = function () {
        $http.get("restapi/system/validation_info").then(function (data) {
          $scope.validationInfo = data.data.results;
        }, function (data) {
          $scope.validationInfo = '';
        });
      };
      $scope.getSubmissionInfo = function () {
        $http.get("restapi/system/submission_info").then(function (data) {
          $scope.submissionInfo = data.data;
        }, function (data) {
          $scope.submissionInfo = {};
        });
      };
      $scope.getLocksInfo = function () {
        $http.get("restapi/system/locks_info").then(function (data) {
          $scope.locksInfo = data.data.results;
        }, function (data) {
          $scope.locksInfo = {};
        });
      };
      $scope.getStartTime = function () {
        $http.get("restapi/system/start_time").then(function (data) {
          $scope.startTime = data.data.results;
        }, function (data) {
          $scope.startTime = {};
        });
      };

      $scope.getValidationInfo();
      $scope.getSubmissionInfo();
      $scope.getLocksInfo();
      $scope.getStartTime();
    }
  ]);
