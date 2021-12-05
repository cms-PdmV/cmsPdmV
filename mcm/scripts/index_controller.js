angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$window',
  function resultsCtrl($scope, $http, $window) {
    $scope.searchForm = {};

    $scope.preloadPrepids = function (viewValue, database) {
      const promise = $http.get("search/?db_name=" + database + "&page=0&limit=10&include_fields=prepid&prepid=" + viewValue + "*");
      return promise.then(function(data){
        return data.data.results.map(x => x.prepid);
      }, function(data){
        console.error("Error fetching prepids: " + data.status);
        return [];
      });
    };

    $scope.preloadUniques = function(viewValue, database) {
      var promise = $http.get("restapi/requests/unique_values/" + database + "?key=" + viewValue);
      return promise.then(function(data){
        return data.data.results;
      }, function(data){
        console.error("Error fetching suggestions: " + data.status);
        return [];
      });
    };

    $scope.searchRequests = function (){
      const prepid  = $scope.searchForm.prepid;
      const dataset = $scope.searchForm.dataset;
      const tags = $scope.searchForm.tags;
      let query = [];
      if (prepid && prepid.length){
        query.push("prepid=" + prepid);
      }
      if (dataset && dataset.length){
        query.push("dataset_name=" + dataset);
      }
      if (tags && tags.length){
        query.push("tags=" + tags);
      }
      if (query.length){
        $window.location.href = "requests?" + query.join('&');
      }
    };

    $scope.searchTickets = function (){
      const prepid  = $scope.searchForm.ticket;
      if (prepid && prepid.length){
        $window.location.href = "mccms?prepid=" + prepid;
      }
    };
}]);
