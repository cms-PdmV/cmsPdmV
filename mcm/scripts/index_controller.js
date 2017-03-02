angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
  	$scope.form_data = {};

  	$scope.parseResponse = function (data, search_by){
  		var results = [];
  		var docs = data.data.results;
    	for (var index in docs){
      		var doc = docs[index];
      		results.push(doc[search_by]);
    	}
    	return results;
  	};

  	$scope.preloadPrepids = function (viewValue, database){
    	var promise = $http.get("search/?db_name=" + database + "&page=0&limit=10&include_fields=prepid&prepid=" + viewValue + "*");
        return promise.then(function(data){
          return $scope.parseResponse(data, 'prepid');
        }, function(data){
          alert("Error getting list of possible search parameters: " + data.status);
        });
    };

    $scope.preloadUniques = function(viewValue, search_by)
    {
      var promise = $http.get("restapi/requests/unique_values/"+search_by+"?limit=10&startkey=" + viewValue);
      return promise.then(function(data){
      	return data.data.results;
      }, function(data){
        alert("Error getting searchable fields: "+data.status);
      });
    };

    $scope.redirectToRequests = function (){
    	var request  = $scope.form_data.request;
    	var dataset = $scope.form_data.dataset;
    	var tags = $scope.form_data.tags;
      var ticket = $scope.form_data.ticket;
      var path = "mccms?";
      if (typeof(ticket) != 'undefined' && ticket != ""){
        path += "prepid=" + ticket;
        $window.location.href = path;
        return;
      }
      var path = "requests?";
    	if (typeof(request) != 'undefined' && request != ""){
    		path += "prepid=" + request + "&";
    	}
    	if (typeof(dataset) != 'undefined' && dataset != ""){
    		path += "dataset_name=" + dataset + "&";
    	}
    	if (typeof(tags) != 'undefined' && tags != ""){
    		path += "tags=" + tags;
    	}
    	if (path != "requests?"){
    		$window.location.href = path;
    	}
    };

}]);