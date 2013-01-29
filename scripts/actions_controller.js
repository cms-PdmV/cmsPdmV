function resultsCtrl($scope, $http, $location){ 
    $scope.actions_defaults = [
        {text:'Actions',select:true, db_name:'prepid'}
//         {text:'Actions',select:true, db_name:''},
    ];
    $scope.chained_campaigns = ["prepid"];
    $scope.campaigns = [];
    $scope.show_well = false;
    if($location.search()["page"] === undefined){
        $location.search("page", 0);
        page = 0;
        $scope.list_page = 0;
    }else{
        page = $location.search()["page"];
        $scope.list_page = parseInt(page);
    }
    var promise = $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+page)
    promise.then(function(data){
        console.log(data);
        $scope.result = data.data.results; 
        if ($scope.result.length != 0){
        columns = _.keys($scope.result[0]);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
//         $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
        _.each(rejected, function(v){
            add = true;
            _.each($scope.actions_defaults, function(column){
            if (column.db_name == v){
                add = false;
            }
         });
            if (add){
//                 $scope.actions_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
        });
        }
        console.log($scope.actions_defaults);
    }, function(){
       console.log("Error"); 
    });
    var promise = $http.get('search/?db_name=chained_campaigns&query=""&page=-1')
    promise.then(function(data){
        _.each(data.data.results, function(v){
            $scope.chained_campaigns.push(v._id);
            $scope.actions_defaults.push({text:v._id, select:true, db_name:v._id});
            console.log('chained',v._id);
        });
        console.log($scope.actions_defaults);
    });
    
    promise = $http.get('search/?db_name=campaigns&query=""&page=-1')
    promise.then(function(data){
        _.each(data.data.results, function(v){
           $scope.campaigns.push(v.prepid); 
        });
        console.log($scope.campaigns);
    });
    
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
      var promise = $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+$scope.list_page)
          promise.then(function(data){
          console.log(data);
          $scope.result = data.data.results;
         }, function(){
             console.log("Error"); 
         });
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
var testApp = angular.module('testApp',[]);
testApp.directive("customPrepId", function ($rootScope) {
    return {
        restrict: 'E',
        replace: true,
        require: "ngModel",
        link: function (scope, element, attr, ctrl) {
            
            var to_our = function (lst) {
                 if (lst === undefined)
                      return [];
                
                 var x =  { 0: lst, 1: lst[1], 2: lst[2] };
//                     var x = {0: lst, 1:777, 2:7}
                return x;
            };
            
            var from_our = function (lst) {
                var out = [];
                if (lst[0] != undefined){
                    out.push(parseInt(lst[0]));
                    if (lst[2] != undefined){
                        out.push(0); //put second element;
                        out.push(parseInt(lst[2]));
                    }
                    if (lst[1] != undefined){
                        out[1] = parseInt(lst[1]);
                    }
                }
                return out;
            };
            
            scope.makeInput = function (value) {
                if (value) {
                    $rootScope.$broadcast("closeCustomPrepId", []);
                }
                
                scope.input_enabled = value;
                console.log(ctrl.$viewValue);
                scope.value = to_our(ctrl.$viewValue);
//                  console.log(scope.value);
            };
            
            scope.commit = function () {
               ctrl.$setViewValue(from_our(scope.value)); 
               scope.makeInput(false);
            }
            
            scope.$on("closeCustomPrepId", function () {
                if (scope.input_enabled)
                    scope.makeInput(false);
            });
            
            ctrl.$render = function () {
                scope.makeInput(false);
            };
        },
        template: ""
        + "<ng-form name='form'>"
        + "<div ng-switch on='input_enabled'>"
        + "  <span ng-switch-when='true'>"
        + "    <select class='input-mini' ng-disabled='value[0] == undefined' ng-model=value[0] style='margin-bottom: 0px; margin-left: 2px;'>"
        + "      <option ng-repeat='key in [0,1,2,3,4,5,6]' ng-selected ='value[0] == key'>{{key}}</option>"
        + "    </select>"
        + "    <input type='button' ng-class='{ \"btn-warning\": form.$invalid, \"btn-success\": form.$valid}' ng-disabled='!form.$valid' class='btn' ng-click='commit()' value='+' style='width: 17px; padding: 0px; height: 18px;' />"
        + "    <input type='number' ng-model='value[1]' style='margin-bottom: 0px; width: 80px;'/>"
        + "    <span class='input-append'>"
        +"       <input type='number' ng-model='value[2]' style='margin-bottom: 0px; width: 25px;'/>"
        +"       <span class='add-on'>%</span>"
        +"     </span>"
        + "  </span>"
        + "  <span ng-switch-default ng-click='makeInput(true, form.$valid)'>{{ value[0] }} </br>{{ value[1] }} </br>{{ value[2] }} </span>"
        + "</div>"
        + "</ng-form>"
    };
});
