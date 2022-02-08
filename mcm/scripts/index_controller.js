angular.module('mcmApp').controller('indexController',
  ['$scope', '$http', '$window',
  function indexController($scope, $http, $window) {
    $scope.requestPrepid = '';
    $scope.requestDataset = '';
    $scope.requestTag = '';
    $scope.mccmPrepid = '';

    $scope.loadSuggestions = function(database, attribute, value) {
      return $http.get(`restapi/${database}/unique_values?attribute=${attribute}&value=${value}`).then(function(data) {
        console.log(data.data.results);
        return data.data.results;
      }, function(data){
        console.error(`Error fetching suggestions: ${data.status}`);
        return [];
      });
    };

    $scope.searchRequests = function (){
      let query = [];
      if ($scope.requestPrepid.length){
        query.push(`prepid=${$scope.requestPrepid}`);
      }
      if ($scope.requestDataset.length){
        query.push(`dataset_name=${$scope.requestDataset}`);
      }
      if ($scope.requestTag.length){
        query.push(`tags=${$scope.requestTag}`);
      }
      if (query.length){
        $window.location.href = `requests?${query.join('&')}`;
      }
    };

    $scope.searchTickets = function (){
      if ($scope.mccmPrepid.length){
        $window.location.href = `mccms?prepid=${$scope.mccmPrepid}`;
      }
    };

    $scope.openItem = function(database, attribute, value) {
      $window.location.href = `${database}?${attribute}=${value}`;
    }
}]);
