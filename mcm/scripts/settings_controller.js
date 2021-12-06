angular.module('testApp').controller('resultsCtrl',
  ['$scope','$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [
      {text:'Prepid', select:true, db_name:'prepid'},
      {text:'Actions', select:false, db_name:''},
      {text:'Value', select:true, db_name:'value'},
      {text:'Notes', select:true, db_name:'notes'}
    ];
    $scope.update = [];

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "settings";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.sort = {
      column: 'value.prepid',
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
        $scope.result = data.data.results;
        $scope.total_results = data.data.total_rows;
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

      $scope.objectToId = function(object_name) {
        return object_name.replace(/\//g, "")
      }
  }
]);
