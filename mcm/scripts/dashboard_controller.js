function resultsCtrl($scope, $http, $location, $window){
    $scope.update_stats = [];
    $scope.update_batch = [];
    $scope.update_logs = [];
    $scope.bjobsOptions = {bjobsOutput:"", bjobsGroup: groupName()};
    $scope.tabsettings={
        batch:{
            active:true
        },
        stats:{
            active:false
        },
        logs:{
            active:false
        }
    };
    $scope.logs = {
        type : 'error',
        lines : 10
    };

    function groupName(){
        if($scope.isDevMachine())
            return " -g dev";
        else
            return " -g prod"
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
    }

    $scope.getBjobsData = function(){
        var bjobs_options_array = removeEmptyString($scope.bjobsOptions);
        var bjobs_options = bjobs_options_array.join("/");
        var promise = $http.get("restapi/dashboard/get_bjobs/" + bjobs_options.toString());
        promise.then(function(data, status){
            $scope.update_batch["success"] = true;
            $scope.update_batch["fail"] = false;
            $scope.update_batch["status_code"] = data.status;
            $scope.results = data.data.results
        }, function(data, status){
            $scope.update_batch["success"] = false;
            $scope.update_batch["fail"] = true;
            $scope.update_batch["status_code"] = data.status;
    })};

    $scope.getLogData = function(log_name){
        var lines = $scope.logs.lines>100?-1:$scope.logs.lines;
        var promise = $http.get("restapi/dashboard/get_log_feed/" + log_name + "/" + lines);
        promise.then(function(data, status){
            $scope.update_logs["success"] = true;
            $scope.update_logs["fail"] = false;
            $scope.update_logs["status_code"] = data.status;
            $scope.logs.results = data.data.results
        }, function(data, status){
            $scope.update_logs["success"] = false;
            $scope.update_logs["fail"] = true;
            $scope.update_logs["status_code"] = data.status;
    })};

    $scope.getLines = function(line_number){
     return line_number>100?"All":line_number
    };

    $scope.$watch('tabsettings.batch.active', function(){
        if($scope.tabsettings.batch.active) {
            $scope.getBjobsData();
            $scope.batch_int_id = setInterval($scope.getBjobsData, 60000);
        } else {
            clearInterval($scope.batch_int_id);
        }
    }, true);

//    $scope.$watch('tabsettings.stats.active', function(){
//    });

    function getLog() {
        if($scope.tabsettings.logs.active) {
            clearInterval($scope.logs.int_id);
            $scope.getLogData($scope.logs.type);
            $scope.logs.int_id = setInterval(function() { $scope.getLogData($scope.logs.type); }, 60000);
        } else {
            clearInterval($scope.logs.int_id);
        }
    }

    $scope.$watch('logs.type', function(){
        getLog()
    });

    $scope.$watch('tabsettings.logs.active', function(){
        getLog()
    });

    $scope.$watch('bjobsOptions', function(){
        $scope.getBjobsData();
    }, true);

    $scope.$watch('logs.sliding', function() {
        if(!$scope.logs.sliding)
            $scope.getLogData($scope.logs.type)
    });

}
