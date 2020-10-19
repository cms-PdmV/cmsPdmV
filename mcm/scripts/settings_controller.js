angular.module('testApp').controller('resultsCtrl',
  ['$scope','$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.dataColumns = [
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
