 
function resultsCtrl($scope, $http, $location){
    $scope.chainedCampaigns_defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
        {text:'Chain',select:true, db_name:'campaigns'},
        {text:'Energy',select:true, db_name:'energy'},
    ];

    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    $scope._ = _;
    if($location.search()["page"] === undefined){
        page = 0;
        $location.search("page", 0);
        $scope.list_page = 0;
    }else{
        page = $location.search()["page"];
        $scope.list_page = parseInt(page);
    }
    
    
    $scope.delete_object = function(db, value){
        $http({method:'DELETE', url:'/restapi/'+db+'/delete/'+value}).success(function(data,status){
            console.log(data,status);
            if (data["results"]){
                alert('Object was deleted successfully.');
            }else{
                alert('Could not save data to database.');
            }
        }).error(function(status){
            alert('Error no.' + status + '. Could not delete object.');
        });
    };
    $scope.sort = {
        column: 'prepid',
        descending: false
    };

    $scope.selectedCls = function(column) {
        return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };
    
    $scope.changeSorting = function(column) {
        var sort = $scope.sort;
        if (sort.column == column) {
            sort.descending = !sort.descending;
        } else {
            sort.column = column;
            sort.descending = false;
        }
    };
    $scope.showing_well = function(){
        if ($scope.show_well){
          $scope.show_well = false;
        }
        else{
            console.log("true");
            $scope.show_well = true;
        }
    };    

   $scope.$watch('list_page', function(){
      console.log("modified");
      var promise = $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+page)
      promise.then(function(data){
        console.log(data);
        $scope.result = data.data.results; 
        if ($scope.result.length != 0){
          columns = _.keys($scope.result[0]);
          rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
          $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
          _.each(rejected, function(v){
            add = true;
            _.each($scope.chainedCampaigns_defaults, function(column){
              if (column.db_name == v){
                add = false;
              }
            });
            if (add){
              $scope.chainedCampaigns_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
          });
        }
      }, function(){ alert("Error"); });
  });
    
  $scope.previous_page = function(current_page){
      if (current_page >-1){
        $location.search("page", current_page-1);
        $scope.list_page = current_page-1;
      }
  };
  $scope.next_page = function(current_page){
      if ($scope.result.length !=0){
        $location.search("page", current_page+1);
        $scope.list_page = current_page+1;
      }
  };
}

// NEW for directive
var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});