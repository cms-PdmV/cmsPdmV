angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.dataColumns = [
      {text:'Object', select:true, db_name:'object'},
      {text:'Actions', select:false, db_name:''},
      {text:'Type', select:true, db_name:'type'},
      {text:'Status', select:true, db_name:'status'}
    ];

    $scope.update = {};
    $scope.selected_objects = [];

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "invalidations";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.sort = {
      column: 'value.object',
      descending: false
    };

    $scope.selectedCls = function(column) {
      return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };

    $scope.changeSorting = function(column) {
      var sort = $scope.sort;
      if (sort.column == column) {
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };

    $scope.delete = function(id)
    {
      $http({method:'DELETE', url:'restapi/'+$scope.dbName+'/delete/'+id})
        .success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData($scope);
      }).error(function(data, status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
      });
    };

    $scope.do_action = function(prepid, action_name)
    {
      __to_send_data = null;
      if (_.isArray(prepid))
      {
        __to_send_data = prepid;
      }else
      {
        __to_send_data = [prepid];
      }
      if (__to_send_data.length ==0 )
      {
        alert("No prepids were selected");
        return;
      }
      $http({method:'PUT', url:'restapi/'+$scope.dbName+'/'+action_name,
        data:JSON.stringify(__to_send_data)})
        .success(function(data, status){
          $scope.update["success"] = data["results"];
          $scope.update["fail"] = !data["results"];
          $scope.update["status_code"] = status;
          $scope.getData($scope);
      }).error(function(data, status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
      });
    };

    $scope.add_to_selected_list = function(obj_id)
    {
      if (_.contains($scope.selected_objects, obj_id)){
        $scope.selected_objects = _.without($scope.selected_objects, obj_id);
      }else{
        $scope.selected_objects.push(obj_id);
      }
    };

    $scope.toggleAll = function(){
      if ($scope.selected_objects.length != $scope.result.length){
        _.each($scope.result, function(v){
          $scope.selected_objects.push(v._id);
        });
        $scope.selected_objects = _.uniq($scope.selected_objects);
      }else{
        $scope.selected_objects = [];
      }
    };

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
     function(){
        $scope.getData($scope);
        $scope.selected_prepids = [];
    });

    $scope.objectToId = function(object_name) {
        return object_name.replace(/\//g, "")
    }
  }
]);
