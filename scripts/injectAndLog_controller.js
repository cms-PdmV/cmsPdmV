function resultsCtrl($scope, $http, $location, $timeout, $window){
    $scope.buttonHide = false;
    $scope.prepid = $location.search()["prepid"];
    $scope.injection = "";
    $scope.logInfo = "";
    // $scope.batchNumber = $location.search()["batchNum"];

    $scope.inject = function(){
      $scope.buttonHide= true;
      $scope.getLog();
      var promise1 = $http.get('restapi/requests/inject/'+$scope.prepid)
      promise1.then(function(data){
        $scope.injection = data.data;
        $scope.injectError = false;
      }, function(data){ //if there was an error in inject request
      	$scope.injection = data.data;
      	$scope.injectError = true;
      });
    };
    $scope.getLog = function(){
    	stop = $timeout(function(){
          var promise = $http.get('restapi/requests/injectlog/'+$scope.prepid) //get log
          promise.then(function(data){
            $scope.logInfo = data.data;
            window.scrollTo(0, document.body.scrollHeight); //scroll to bottom of the page
            if ($scope.injection == ""){
              $scope.getLog();
            }
          });
        }, 3000);
    };

}
var testApp = angular.module('testApp',[]).config(function($locationProvider){$locationProvider.html5Mode(true);});
