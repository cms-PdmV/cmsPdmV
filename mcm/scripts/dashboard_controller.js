angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){

    $scope.update = [];
    $scope.bjobsOptions = {bjobsOutput:"", bjobsWide:" -wide"};
    $scope.turn_off_button_clicked = false;
    $scope.clear_rest_button_clicked = false;
    $scope.tabsettings={
      batch:{
        active:true
      },
      logs:{
        active:false
      }
    };

    $scope.logs = {
      lines : 10,
      list: [
          {name: 'error', modified: ''},
          {name: 'inject', modified: ''},
          {name: 'access', modified: ''}
          ]
    };

    $scope.selectedLog = $scope.logs.list[0];
    $scope.fontSize = 12;
    $scope.items = [];
    for(var i = 9;i<18;i++){
      $scope.items.push(i)
    }

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "dashboard";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    function removeEmptyString(dict){
      var output_array = [];
      var arr = Object.keys(dict).map(function(key){
        return dict[key];
      });
      arr.forEach(function(elem) {
        if (elem) {
          output_array.push(elem)
        }
      });
      return output_array
    };

    $scope.resetRestCounter = function() {
      $scope.clear_rest_button_clicked = true;
      var promise = $http.get("restapi/control/reset_rest_counter");
      promise.then(function(){
        alert("REST counters reset");
        $scope.clear_rest_button_clicked = false;
      }, function(){
        alert("Error resetting REST counters");
        $scope.clear_rest_button_clicked = false;
      });
    };

    $scope.openPage = function(address) {
      $window.open(address);
    };

    $scope.getBjobsData = function(){
      var bjobs_options_array = removeEmptyString($scope.bjobsOptions);
      var bjobs_options = bjobs_options_array.join(",");
      var promise = $http.get("restapi/dashboard/get_bjobs/" + bjobs_options.toString());
      promise.then(function(data, status){
        $scope.update["success"] = true;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data.status;
        $scope.results = data.data.results
      }, function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });

      var promise2 = $http.get("restapi/dashboard/queue_info");
      promise2.then(function(data, status){
        $scope.update["success"] = true;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data.status;
        $scope.queue_info = data.data;
      }, function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });
    };

    $scope.getLogData = function(log_name){
      if (log_name.includes(".log"))
      {
        // the first time DOM object is initialized and tries to get_feed with default name which is wrong
        var lines = $scope.logs.lines>100?'':$scope.logs.lines;
        var promise = $http.get("restapi/dashboard/get_log_feed/" + log_name + "/" + lines);
        promise.then(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = data.status;
          $scope.logs.results = data.data.results
        }, function(data, status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = data.status;
        });
      }
    };

    $scope.getCacheInfo = function(){
      var promise = $http.get("restapi/control/cache_info");
      promise.then(function(data, status){
        $scope.cacheInfo = data.data.results;
      }, function(data, status){
        $scope.cacheInfo = {};
      });
    };

    $scope.getLines = function(line_number){
      return line_number>100?"All":line_number
    };

    $scope.$watch('tabsettings.batch.active', function(){
      if($scope.tabsettings.batch.active) {
        $scope.getBjobsData();
        //$scope.batch_int_id = setInterval($scope.getBjobsData, 60000);
      } else {
        clearInterval($scope.batch_int_id);
      }
    }, true);

    $scope.$watch('tabsettings.cache.active', function(){
      if($scope.tabsettings.batch.active) {
        $scope.getCacheInfo();
      }
    }, true);

    function getLog() {
      if($scope.tabsettings.logs.active) {
        clearInterval($scope.logs.int_id);
        $scope.getLogData(($scope.logs.list[$scope.getLogIndex()]).name);
        $scope.logs.int_id = setInterval(function() { $scope.getLogData(($scope.logs.list[$scope.getLogIndex()]).name); }, 60000);
      } else {
        clearInterval($scope.logs.int_id);
      }
    };

    $scope.getLogs = function(){
      var promise = $http.get("restapi/dashboard/get_logs");
      promise.then(function(data){
        $scope.logs.list =  data.data.results;
        $scope.selectedLog = $scope.logs.list[0];
      }, function(data){
        alert("Error getting logs list: " +data.status);
      });
    };

    $scope.getLogIndex = function() {
      return document.getElementById('selectLog').selectedIndex==undefined?0:document.getElementById('selectLog').selectedIndex;
    }

    $scope.$watch('logs.type', function(){
      getLog();
    });

    $scope.$watch('tabsettings.logs.active', function(){
      getLog();
      $scope.getLogs();
    });

    $scope.$watch('bjobsOptions', function(){
      $scope.getBjobsData();
    }, true);

    $scope.$watch('logs.sliding', function() {
      if(!$scope.logs.sliding)
      {
        if(!(($scope.logs.list[$scope.getLogIndex()])==undefined))
        {
          $scope.getLogData(($scope.logs.list[$scope.getLogIndex()]).name);
        }
      }
    });

    $scope.selectValue = function() {
      return document.getElementById("selectFont").value;
    };

    function checkDisplayLog() {
      if (document.getElementById('selectLog')!=null)
      {
        return document.getElementById('selectLog').selectedIndex;
      }
      else
      {
        return -2
      }
    };

    $scope.$watch("fontSize", function() {
      var pres = Array.prototype.slice.call(document.getElementsByClassName("fontPre"));
      pres.forEach(function(elem){
        elem.style.fontSize = $scope.fontSize + "px";
      });
    });
  }
]);
