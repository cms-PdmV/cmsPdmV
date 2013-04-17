function resultsCtrl($scope, $http, $location, $window){
    $scope.flows_defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
        {text:'Approval',select:true, db_name:'approval'},
        {text:'Allowed Campaigns',select:true, db_name:'allowed_campaigns'},
        {text:'Next Campaign',select:true, db_name:'next_campaign'},
    ];
    $scope.user = {name: "guest", role:"user"}
// GET username and role
      var promise = $http.get("restapi/users/get_roles");
       promise.then(function(data){
        $scope.user.name = data.data.username;
        $scope.user.role = data.data.roles[0];
        $scope.user.roleIndex = parseInt(data.data.role_index);
    }, function(data){
        alert("Error getting user information. Error: "+data.status);
    });
// Endo of user info request
    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "flows";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    if($location.search()["query"] === undefined){
      $location.search("query",'""');
    }
    $scope.underscore = _;
    $scope.selectedAll = false;

    if($location.search()["page"] === undefined){
        page = 0;
        $location.search("page", 0);
        $scope.list_page = 0;
    }else{
        page = $location.search()["page"];
        $scope.list_page = parseInt(page);
    }
    
    
    $scope.delete_object = function(db, value){
        $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
            if (data["results"]){
                $scope.update["success"] = data.results;
                $scope.update["fail"] = false;
                $scope.update["status_code"] = status;
                $window.location.reload();
            }else{
                $scope.update["success"] = false;
                $scope.update["fail"] = true;
                $scope.update["status_code"] = status;
            }
        }).error(function(status){
            alert('Error no.' + status + '. Could not delete object.');
        });
    };
    $scope.next_step = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+prepid}).success(function(data,status){
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $window.location.reload();
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };

    $scope.reset_flow = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+prepid+'/0'}).success(function(data,status){
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $window.location.reload();
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };

    $scope.select_all_well = function(){
      $scope.selectedCount = true;
      var selectedCount = 0
      _.each($scope.flows_defaults, function(elem){
        if (elem.select){
          selectedCount +=1;
        }
        elem.select = true;
      });
      if (selectedCount == _.size($scope.flows_defaults)){
      _.each($scope.flows_defaults, function(elem){
        elem.select = false;
      });
      $scope.flows_defaults[0].select = true; //set prepid to be enabled by default
      $scope.flows_defaults[1].select = true; // set actions to be enabled
      $scope.selectedCount = false;
      }
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
            $scope.show_well = true;
        }
    };    

   $scope.$watch('list_page', function(){
      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+"&query="+$location.search()["query"]+"&page="+page)
      promise.then(function(data){
        $scope.result = data.data.results; 
        if ($scope.result.length != 0){
          columns = _.keys($scope.result[0]);
          rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
          $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
          _.each(rejected, function(v){
            add = true;
            _.each($scope.flows_defaults, function(column){
              if (column.db_name == v){
                add = false;
              }
            });
            if (add){
              $scope.flows_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
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
  $scope.role = function(priority){
    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
  };
}

// NEW for directive
var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customHistory", function(){
  return {
    require: 'ngModel',
    template: 
    '<div>'+
    '  <div ng-hide="show_history">'+
    '    <input type="button" value="Show" ng-click="show_history=true;">'+
    '  </div>'+
    '  <div ng-show="show_history">'+
    '    <input type="button" value="Hide" ng-click="show_history=false;">'+
    '    <table class="table table-bordered" style="margin-bottom: 0px;">'+
    '      <thead>'+
    '        <tr>'+
    '          <th style="padding: 0px;">Action</th>'+
//     '          <th style="padding: 0px;">Message</th>'+
//     '          <th style="padding: 0px;">Step</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
//     '          <td style="padding: 0px;">{{elem.step}}</td>'+
//     '          <td style="padding: 0px;"><a rel="tooltip" title={{elem.message}}><i class="icon-info-sign"></i></a></td>'+
    '          <td style="padding: 0px;">{{elem.updater.submission_date}}</td>'+
    '          <td style="padding: 0px;">'+
    '              <div ng-switch="elem.updater.author_name">'+
    '                <div ng-switch-when="">{{elem.updater.author_username}}</div>'+
    '                <div ng-switch-default>{{elem.updater.author_name}}</div>'+
    '              </div>'+
    '          </td>'+
    '        </tr>'+
    '      </tbody>'+
    '    </table>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});