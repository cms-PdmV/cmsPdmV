function resultsCtrl($scope, $http, $location, $window){
  $scope.user = {name: "quest", role:"user"}
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "batches";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }
  if($location.search()["query"] === undefined){
  	$location.search("query",'""');
  }
  $scope.update = [];
// GET username and role
  var promise = $http.get("restapi/users/get_roles");
  promise.then(function(data){
    $scope.user.name = data.data.username;
    $scope.user.role = data.data.roles[0];
  },function(data){
    alert("Error getting user information. Error: "+data.status);
  });
  var promise = $http.get("restapi/users/get_all_roles");
  promise.then(function(data){
    $scope.all_roles = data.data;
  },function(data){
    alert("Error getting user information. Error: "+data.status);
  });
// Endo of user info request
       
  $scope.batches_defaults = [
    {text:'PrepId',select:true, db_name:'prepid'},
    {text:'Actions',select:false, db_name:''},
    {text:'Requests',select:true, db_name:'requests'},
    {text:'Notes',select:true, db_name:'notes'},
    {text:'Status',select:true, db_name:'status'},
  ];

  $scope.show_well = false;
  if($location.search()["page"] === undefined){
    $location.search("page", 0);
    page = 0;
    $scope.list_page = 0;
  }else{
    page = $location.search()["page"];
    $scope.list_page = parseInt(page);
  }
  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }else{
      $scope.show_well = true;
     }
  };
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
  $scope.sort = {
    column: 'prepid',
    descending: false
  };

  $scope.selectedCls = function(column) {
    return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
  };
    
  $scope.changeSorting = function(column) {
    var sort = $scope.sort;
    if (sort.column == column){
      sort.descending = !sort.descending;
    }else{
       sort.column = column;
       sort.descending = false;
     }
  };
  $scope.role = function(priority){
    if(priority > _.indexOf($scope.all_roles, $scope.user.role)){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
  };
  $scope.select_all_well = function(){
    $scope.selectedCount = true;
    var selectedCount = 0
    _.each($scope.batches_defaults, function(elem){
      if (elem.select){
        selectedCount +=1;
      }
      elem.select = true;
    });
    if (selectedCount == _.size($scope.batches_defaults)){
    _.each($scope.batches_defaults, function(elem){
      elem.select = false;
    });
    $scope.batches_defaults[0].select = true; //set prepid to be enabled by default
    $scope.selectedCount = false;
    }
  };
  $scope.$watch('list_page', function(){
    console.log("modified");
    var promise = $http.get("search/?"+ "db_name="+$scope.dbName+"&query="+$location.search()['query']+"&page="+$scope.list_page)
    promise.then(function(data){
      $scope.result = data.data.results; 
      if ($scope.result.length != 0){
        columns = _.keys($scope.result[0]);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
        _.each(rejected, function(v){
            add = true;
            _.each($scope.defaults, function(column){
            if (column.db_name == v){
                add = false;
            }
         });
            if (add){
                $scope.batches_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
        });
        }
    }, function(){
       alert("Error getting main information");
    });
    });
    $scope.delete_object = function(db, prepid){
      alert("Not yet in RestAPI!" + db+": "+prepid);
    };
    $scope.announce = function(prepid){
      alert("Batch to be announced:"+prepid);
    };
};
var ModalDemoCtrl = function ($scope, $http, $window) {
  $scope.mailContent = "";
  $scope.open = function (id) {
    $scope.shouldBeOpen = true;
    $scope.prepId = id;
  };

  $scope.close = function () {
    $scope.shouldBeOpen = false;
    $scope.mailContent = "";
  };
  $scope.save = function () {
    console.log($scope.prepId, $scope.mailContent);
    $scope.shouldBeOpen = false;
    console.log({prepid: $scope.prepId, notes: $scope.mailContent});
    $http({method: 'PUT', url:'restapi/batches/announce', data:{prepid: $scope.prepId, notes: $scope.mailContent}}).success(function(data, status){
      console.log(data, status);
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["results"] = data.results;
      $scope.update["status_code"] = status;
      $window.location.reload();
      //   $window.location.href ="edit2?db_name=requests&query="+data.results;
    }).error(function(data,status){
      alert("Error:"+ status);
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
      console.log(data, status);
    });
    $scope.mailContent = "";
  };
};
var testApp = angular.module('testApp',['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
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
    '          <th style="padding: 0px;">Message</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
    '          <td style="padding: 0px;"><a rel="tooltip" title={{elem.message}}><i class="icon-info-sign"></i></a></td>'+
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