angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [
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

    $scope.getData = function(){
      var query = ""
      _.each($location.search(), function(value,key){
        if (key!= 'shown' && key != 'fields'){
          query += "&"+key+"="+value;
        }
      });
      var promise = $http.get("search?db_name="+$scope.dbName+query+"&get_raw");
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      promise.then(function(data){
        $scope.result = _.pluck(data.data.rows, 'doc');
        $scope.result_status = data.status;
        $scope.got_results = true;
        if ($scope.result.length != 0){
          columns = _.keys($scope.result[0]);
          rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
  //         $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
          _.each(rejected, function(v){
            add = true;
            _.each($scope.defaults, function(column){
              if (column.db_name == v){
                add = false;
              }
            });
            if (add){
              $scope.defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
          });
          if ( _.keys($location.search()).indexOf('fields') != -1)
          {
            _.each($scope.defaults, function(elem){
              elem.select = false;
            });
            _.each($location.search()['fields'].split(','), function(column){
              _.each($scope.defaults, function(elem){
                if ( elem.db_name == column )
                {
                  elem.select = true;
                }
              });
            });
          }
        }
          $scope.selectionReady = true;
      },function(){
         alert("Error getting information");
      });
    };

    $scope.delete = function(id)
    {
      $http({method:'DELETE', url:'restapi/'+$scope.dbName+'/delete/'+id})
        .success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData();
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
          $scope.getData();
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
        $scope.getData();
        $scope.selected_prepids = [];
    });

    $scope.objectToId = function(object_name) {
        return object_name.replace(/\//g, "")
    }
  }
]);
