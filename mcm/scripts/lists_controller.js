angular.module('mcmApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.lists_defaults = [];
    $scope.dbName = 'lists';
    $scope.sort = {
      column: 'prepid',
      descending: false
    };

    $scope.getData = function(){
      var query = ""
      $scope.list_name = undefined;
      _.each($location.search(), function(value,key){
        if (key == "prepid") {
          $scope.list_name = value;
        }
        if (key!= 'shown' && key != 'fields' && key != 'prepid'){
          query += "&"+key+"="+value;
        }
      });

      $scope.list_overview = $scope.list_name === undefined
      if ($scope.list_overview) {
        $scope.lists_defaults = [
          {text:'List name',select:true, db_name:'prepid'},
          {text:'List size',select:true, db_name:'size'},
          {text:'Notes',select:true, db_name:'notes'}
        ];
      }
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var promise = $http.get("restapi/lists/get/" + ($scope.list_name !== undefined ? $scope.list_name : "_overview") + "?get_raw" + query);
      promise.then(function(data) {
        $scope.result_status = data.status;
        $scope.got_results = true;
        if ($scope.list_overview) {
          $scope.result = data.data.results;
        } else {
          $scope.result = data.data.results.value;
        }
        $scope.total_results = data.data.total_rows;
        if ($scope.result === undefined ){
          alert("Error getting information");
          return; //stop doing anything if results are undefined
        }
        if ($scope.list_name === "list_of_nonflowing_chains") {
          var today = new Date();
          var millisInDay = 1000 * 60 * 60 * 24;
          _.each($scope.result, function(part) {
            var doneSince = new Date(part['nonflowing_since'] * 1000);
            doneSince.setUTCHours(0,0,0,0);
            part['days'] = parseInt((today - doneSince) / millisInDay);
            part['nonflowing_since'] = doneSince.toISOString().slice(0, 10);
          });
          $scope.lists_defaults = [
            {text:'Chain PrepID', select:true, db_name:'chain'},
            {text:'Reason', select:true, db_name:'reason'},
            {text:'Nonflowing since', select:true, db_name:'nonflowing_since'},
            {text:'Nonflowing for days', select:true, db_name:'days'}
          ];
          $scope.result = $scope.result.sort(function(a,b) {return (a.nonflowing_since > b.nonflowing_since) ? 1 : ((b.nonflowing_since > a.nonflowing_since) ? -1 : 0);} ); 
        } else if ($scope.list_name === "list_of_forceflow") {
          $scope.lists_defaults = [
            {text:'Chained request PrepID', select:true, db_name:'_array_value_chain'}
          ];
        } else if ($scope.list_name === "list_of_forcecomplete") {
          $scope.lists_defaults = [
            {text:'Request PrepID', select:true, db_name:'_array_value_request'}
          ];
        }
        $scope.selectionReady = true;
      }, function() {
          alert("Error getting information");
      });
    };

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },function(){
      $scope.getData();
    });
  }
]);
