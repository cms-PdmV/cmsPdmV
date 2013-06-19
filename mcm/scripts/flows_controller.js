function resultsCtrl($scope, $http, $location, $window){
  $scope.flows_defaults = [
    {text:'PrepId',select:true, db_name:'prepid'},
    {text:'Actions',select:true, db_name:''},
    {text:'Approval',select:true, db_name:'approval'},
    {text:'Allowed Campaigns',select:true, db_name:'allowed_campaigns'},
    {text:'Next Campaign',select:true, db_name:'next_campaign'},
  ];
  $scope.update = [];
  $scope.show_well = false;
  $scope.chained_campaigns = [];
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "flows";
  }else{
    $scope.dbName = $location.search()["db_name"];
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

  $scope.approvalIcon = function(value){
    icons = { 'none':'icon-off',
		  'flow' : 'icon-share',
		  'submit' : 'icon-ok'
	  }
	  if (icons[value]){
	    return icons[value];
	  }else{
	    return  "icon-question-sign";
	  }
  };    
    
  $scope.delete_object = function(db, value){
    $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
      if (data["results"]){
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $scope.getData();
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
      $scope.getData();
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
      $scope.getData();
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
      $scope.flows_defaults[2].select = true; // set actions to be enabled
      $scope.flows_defaults[3].select = true; // set actions to be enabled
      $scope.flows_defaults[4].select = true; // set actions to be enabled
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
    }else{
      sort.column = column;
      sort.descending = false;
    }
  };

  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }else{
      $scope.show_well = true;
    }
  };
  $scope.getData = function(){
    var query = ""
    _.each($location.search(), function(value,key){
      if (key!= 'shown'){
        query += "&"+key+"="+value;
      }
    });
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
    promise.then(function(data){
      $scope.got_results = true;
      $scope.result = data.data.results;
      if ($scope.result === undefined ){
        alert('The following url-search key(s) is/are not valid : '+_.keys(data.data));
        return; //stop doing anything if results are undefined
      }
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
        var shown = "";
        if ($.cookie($scope.dbName+"shown") !== undefined){
          shown = $.cookie($scope.dbName+"shown");
          $location.search("shown", shown);
        }
        if ($location.search()["shown"] !== undefined){
          shown = $location.search()["shown"]
        }
        if (shown != ""){
          binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
          _.each($scope.flows_defaults, function(column){
            column_index = $scope.flows_defaults.indexOf(column);
            binary_bit = binary_shown.charAt(column_index);
            if (binary_bit!= ""){ //if not empty -> we have more columns than binary number length
              if (binary_bit == 1){
                column.select = true;
              }else{
                column.select = false;
              }
            }else{ //if the binary index isnt available -> this means that column "by default" was not selected
              column.select = false;
            }
          });
        }
      }
    }, function(){ alert("Error getting information"); });
  };
  $scope.$watch('list_page', function(){
  $scope.getData();
  });

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.flows_defaults, function(column){ //iterate all columns
      if(column.select){
        bin_string ="1"+bin_string; //if selected add 1 to binary interpretation
      }else{
        bin_string ="0"+bin_string;
      }
    });
    $location.search("shown",parseInt(bin_string,2)); //put into url the interger of binary interpretation
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
  $scope.saveCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    if($location.search()["shown"]){
      $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 })
    }
  };
};
var ModalDemoCtrl = function ($scope, $http, $window) {
  $scope.open = function () {
    $scope.shouldBeOpen = true;
  };

  $scope.close = function () {
    $scope.shouldBeOpen = false;
  };

  $scope.createFlow = function(){
    $http({method: 'PUT', url:'restapi/flows/save/', data:{prepid: $scope.flowId}}).success(function(data, status){
      $scope.update["success"] = data.results;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = status;
      $scope.getData();
// //    $window.location.href ="edit?db_name=campaigns&query="+data.results;
     }).error(function(data,status){
         // console.log(data,status);
         $scope.update["success"] = false;
         $scope.update["fail"] = true;
         $scope.update["status_code"] = status;
     });
    $scope.shouldBeOpen = false;
  };
};
// NEW for directive
//var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
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