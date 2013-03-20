function resultsCtrl($scope, $http, $location, $timeout, $window){
    $scope.buttonHide = false;
    $scope.prepid = $location.search()["prepid"];
    console.log($scope.prepid);
    $scope.injection = "";
    $scope.logInfo = "";
    $scope.batchNumber = $location.search()["batchNum"];

    $scope.inject = function(){
      $scope.buttonHide= true;
      $scope.getLog();
      var promise1 = $http.get('restapi/requests/inject/'+$scope.prepid+'/'+$scope.batchNumber)
      promise1.then(function(data){
        console.log(data);
        $scope.injection = data.data;
        $scope.injectError = false;
      }, function(data){ //if there was an error in inject request
      	$scope.injection = data.data;
      	$scope.injectError = true;
      	console.log(data);
      });
    };
    $scope.getLog = function(){
    	stop = $timeout(function(){
          var promise = $http.get('restapi/requests/injectlog/'+$scope.prepid) //get log
          promise.then(function(data){
            $scope.logInfo = data.data;
            window.scrollTo(0, document.body.scrollHeight); //scroll to bottom of the page
            console.log(data);
            if ($scope.injection == ""){
              $scope.getLog();
            }
          });
        }, 3000);
    };

    $scope.$watch("batchNumber", function(){
      if ($scope.batchNumber === undefined){ //if no batch number -> remove param from url
        $location.search("batchNum", null);
      }else{
        $location.search("batchNum", $scope.batchNumber); //else put input value to URL
      };
    });

}
var testApp = angular.module('testApp',[]).config(function($locationProvider){$locationProvider.html5Mode(true);});
