angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$timeout', '$window',
  function resultsCtrl($scope, $http, $location, $timeout, $window){
    $scope.user = {name: "guest", role: "user"}
    $scope.dbName = "requests";
    $scope.nextUpdate = true;

    if ($location.search()["prepid"]){
      $scope.prepid = $location.search()["prepid"].split(",");
    }else{
      $scope.prepid = [];
    };

    $scope.timeToUpdate = 5;
    //initiate table //
    $scope.data = {};
    _.each($scope.prepid, function(v){
      $scope.data[v] = {"prepid": v, "check_me": false};
    });

    $scope.data[$scope.prepid[$scope.prepid.length-1]]["check_me"] = true;

    // GET username and role
    var promise = $http.get("restapi/users/get_role");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.role;
      $scope.user.roleIndex = parseInt(data.data.role_index);
    },function(data){
      alert("Error getting user information. Error: "+data.status);
    });
    // Endo of user info request
    $scope.showNexttime = function(){
      if ($scope.timeToUpdate != 0){ //if time left remove 1 second and do the same with 1 second delay
        $timeout(function(){
          $scope.timeToUpdate = $scope.timeToUpdate - 1;
          $scope.showNexttime();
        },1000);
      }else{
        $scope.timeToUpdate = 5;
      }
    };

    $scope.timeLoop = $scope.showNexttime();
    var logLoop = $window.setInterval(function(){ //after 20seconds initiate full check
      console.log("inside");
      if ($scope.prepid.length == 0){
        $window.clearInterval(logLoop); //close loging if no prepid to check
        return;
      }
      // $window.clearInterval($scope.timeLoop);
      $timeout.cancel($scope.timeLoop);
      $scope.nextUpdate = false;
      $timeout(function(){
        _.each($scope.prepid, function(elem){ //check each request 1 by 1 with different timeout.
          //console.log('talk to me',elem,$scope.data[elem]);
          if ($scope.data[elem] === undefined){
            $scope.data[elem] = {"prepid": elem};
          }

          if ($scope.data[elem]["check_me"]){
            $scope.data[elem]["checking_status"] = true;
            $scope.data[elem]["checking_log"] = true;
            $scope.data[elem]["check_me"]=false;
            next_index=$scope.prepid.indexOf(elem) - 1;
            promise = $http.get("public/restapi/requests/get_status/"+elem);
            promise.then(function(data){
              $scope.data[elem]["status"] = data.data[elem];
              if (data.data[elem] != "approved"){ //if element not approved -> do not get a status;
                $scope.prepid.splice($scope.prepid.indexOf($scope.data[elem]["prepid"]),1);  //remove element from prepid lists if status != approved
              }
              $scope.data[elem]["checking_status"] = false;
              //     //get log!
              promise1 = $http.get('restapi/requests/injectlog/'+elem+'/5'); //get log
              promise1.then(function(data){
                //var parsedLog = data.data.split("<br>");
                //$scope.data[elem]["log"] = parsedLog.slice(parsedLog.length-10,parsedLog.length).join("<br>"); //display last 10 lines of log
                $scope.data[elem]["log"] = data.data
                $scope.data[elem]["checking_log"] = false;
                $scope.nextUpdate = true;
                $scope.timeLoop = $scope.showNexttime();
                if (next_index < 0)
                {
                  next_index = $scope.prepid.length-1;
                };
                if (next_index >= $scope.prepid.length)
                {
                  next_index = 0;
                };
                if ($scope.prepid.length != 0) {
                  $scope.data[$scope.prepid[next_index]]['check_me'] = true;
                }
                },function(data){
                  alert("Error getting request log. Error"+data.status);
                  $scope.data[elem]["checking_log"] = false;
              }); //end of promise1
            },function(data){
              alert("Error getting request status. Error: "+data.status);
            }); //end of promise
          }
        }); //end of _each
      }); //end of timeout
    }, 5000); //pause for 5 sec for logloop
  }
]);
