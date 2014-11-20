function resultsCtrl($scope, $http, $location, $window, $modal){
  $scope.defaults = [
    {text:'Subject', select:true, db_name:'subject'}
  ];
  $scope.update = [];

  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "news";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }

  $scope.sort = {
    column: 'value.username',
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
      if (key != 'shown' && key != 'fields'){
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

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData();
        $scope.selected_prepids = [];
    });

  $scope.openModal = function () {
      var newNewsModal = $modal.open({
          templateUrl: 'addNewsModal.html',
          controller: function($scope, $modalInstance) {
              $scope.modal = {
                  news: {
                      text: "",
                      subject: ""
                  }
              };
              $scope.save = function() {
                  $modalInstance.close($scope.modal.news);
              };
              $scope.close = function() {
                  $modalInstance.dismiss();
              }
          }
      });

      newNewsModal.result.then(function(news) {
          $http({method: 'PUT', url:'restapi/news/save/', data:news})
              .success(function(data, status){
            $scope.update["success"] = data.results;
            $scope.update["fail"] = !data.results;
            $scope.update["status_code"] = status;
            $scope.getData();
          }).error(function(data,status){
            $scope.update["success"] = false;
            $scope.update["fail"] = true;
            $scope.update["status_code"] = status;
          });
      });
  };
}

