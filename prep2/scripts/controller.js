function resultsCtrl($scope, $http, $location, $window){
//     http://prep-test.cern.ch/search/?db_name=campaigns&query=%22%22&page=0
    $scope.defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
	//{text:'Approval',select:true, db_name:'approval'},
        //{text:'Status',select:true, db_name:'status'},
        //{text:'Type',select:true, db_name:'type'},
        //{text:'ProdType',select:true, db_name:'production_type'},
        {text:'SW Release',select:true, db_name:'cmssw_release'},
        {text:'Energy',select:true, db_name:'energy'},
	{text:'Next',select:true, db_name:'next'},
	{text:'Notes',select:true, db_name:'notes'}
    ];
    $scope.user = {name: "guest", role:"user"}
// GET username and role
    var promise = $http.get("restapi/users/get_roles");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.roles[0];
      $scope.user.roleIndex = parseInt(data.data.role_index);
    },function(data){
      alert("Error getting user information. Error: "+data.status);
    });
// Endo of user info request
    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    if($location.search()["query"] === undefined){
      $location.search("query",'""');
    }
    $scope.new = {};

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
            console.log(data,status);
            if (data["results"]){
                $scope.update["success"] = true;
                $scope.update["fail"] = false;
                $scope.update["status_code"] = status;
                $window.location.reload();
//                 alert('Object was deleted successfully.');
            }else{
                $scope.update["success"] = false;
                $scope.update["fail"] = true;
                $scope.update["status_code"] = status;
//                 alert('Could not save data to database.');
            }
        }).error(function(status){
            $scope.update["success"] = false;
            $scope.update["fail"] = true;
            $scope.update["status_code"] = status;
            alert('Error no.' + status + '. Could not delete object.');
        });
    };
    
    $scope.submit_edit = function(){
        console.log("submit function");
        console.log($scope.result);
        $http({method:'PUT', url:'restapi/'+$scope.dbName+'/update/',data:JSON.stringify($scope.result[1])}).success(function(data,status){
            console.log(data,status);
            $scope.update["success"] = data["results"];
            $scope.update["fail"] = false;
            $scope.update["status_code"] = status;
        }).error(function(data,status){
            $scope.update["success"] = false;
            $scope.update["fail"] = true;
            $scope.update["status_code"] = status;
        });
    };
    $scope.select_all_well = function(){
      $scope.selectedCount = true;
      var selectedCount = 0
      _.each($scope.defaults, function(elem){
        if (elem.select){
          selectedCount +=1;
        }
        elem.select = true;
      });
      if (selectedCount == _.size($scope.defaults)){
      _.each($scope.defaults, function(elem){
        elem.select = false;
      });
      $scope.defaults[0].select = true; //set prepid to be enabled by default
      $scope.defaults[1].select = true; // set actions to be enabled
      $scope.defaults[2].select = true; // set actions to be enabled
      $scope.defaults[3].select = true; // set actions to be enabled
      $scope.defaults[4].select = true; // set actions to be enabled
      $scope.defaults[5].select = true; // set actions to be enabled
      $scope.defaults[6].select = true; // set actions to be enabled
      $scope.selectedCount = false;
      }
    };

    $scope.delete_edit = function(id){
        console.log("delete some from edit");
        $scope.delete_object($scope.dbName, id);
    };
    $scope.display_approvals = function(data){
        console.log(data);
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
    $scope.single_step = function(step, prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/'+step+'/'+prepid}).success(function(data,status){
         $scope.update["success"] = data["results"];
         $scope.update["fail"] = false;
         $scope.update["status_code"] = data["results"];
         $window.location.reload();
      }).error(function(status){
         $scope.update["success"] = false;
         $scope.update["fail"] = true;
         $scope.update["status_code"] = status;
      });
    };
    $scope.next_status = function(prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/status/'+prepid}).success(function(data,status){
         $scope.update["success"] = data["results"];
         $scope.update["fail"] = false;
         $scope.update["status_code"] = data["results"];
         $window.location.reload();
      }).error(function(status){
         $scope.update["success"] = false;
         $scope.update["fail"] = true;
         $scope.update["status_code"] = status;
      });
    };
    
   $scope.$watch('list_page', function(){
      console.log("modified");
      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+"&query="+$location.search()["query"]+"&page="+$scope.list_page)
       promise.then(function(data){
        console.log(data);
        $scope.result = data.data.results; 
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
        }
        console.log($scope.requests_defaults);
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
  $scope.submit_create = function(){
    console.log($scope.new);    
    alert('to be imporved');
  };
  $scope.role = function(priority){
    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
  };
};

var ModalDemoCtrl = function ($scope, $http, $window) {
  $scope.pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP'];
  $scope.selectedPwg= 'BPH';
  $scope.open = function (id) {
    $scope.shouldBeOpen = true;
    $scope.prepId = id;
  };

  $scope.close = function () {
    $scope.selectedPwg= 'BPH';
    $scope.shouldBeOpen = false;
  };
    $scope.save = function () {
    console.log($scope.selectedPwg, $scope.prepId);
    $scope.shouldBeOpen = false;
      $http({method: 'PUT', url:'restapi/requests/save/', data:{member_of_campaign:$scope.prepId, pwg: $scope.selectedPwg}}).success(function(data, stauts){
        console.log(data, status);
        $window.location.href ="edit?db_name=requests&query="+data.results;
      }).error(function(data,status){
        alert("Error:"+ status);
        console.log(data, status);
      });
    };
    $scope.createCampaign = function(){
      $http({method: 'PUT', url:'restapi/campaigns/save/', data:{prepid: $scope.campaignId}}).success(function(data, status){
        console.log(data, status);
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $window.location.reload();
//         $window.location.href ="edit?db_name=campaigns&query="+data.results;
      }).error(function(data,status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
      });
      $scope.shouldBeOpen = false;
  };
};
// NEW for directive
var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("inlineEditable", function(){
  return{
      require: 'ngModel',
      template: 
      '<textarea ng-model="whatever_value" ng-change="update()" style="width: 390px; height: 152px;">'+
      '</textarea>',
      link: function(scope, element, attrs, ctrl){
       
       ctrl.$render = function () {
            scope.whatever_value = JSON.stringify(ctrl.$viewValue, null, 4);
       }
       
       scope.update = function () {
           var object = null;
           try {
               object = JSON.parse(scope.whatever_value);
               ctrl.$setViewValue(scope.whatever_value);
               ctrl.$setValidity("bad_json", true);
           } catch (err) {
               ctrl.$setValidity("bad_json", false);
           }
       }
    }
  }
});
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
testApp.directive("sequenceDisplay", function($http){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="show_sequence">'+
    '    <a rel="tooltip" title="Show" ng-click="getCmsDriver();show_sequence=true;">'+
    '     <i class="icon-eye-open"></i>'+
    '    </a>'+
	//    '    <input type="button" value="Show" ng-click="getCmsDriver();show_sequence=true;">'+
    '  </div>'+
    '  <div ng-show="show_sequence">'+
	//    '    <input type="button" value="Hide" ng-click="show_sequence=false;">'+
    '    <a rel="tooltip" title="Hide" ng-click="show_sequence=false;">'+
    '     <i class="icon-remove"></i>'+  
    '    </a>'+     
    '    <ul>'+
    '      <li ng-repeat="sequence in driver">'+
    '        <ul ng-repeat="(key,value) in sequence">'+
    '          <li><b>{{key}}</b>: {{value}}</li>'+
    '        </ul>'+
    '      </li>'+
    '    </ul>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_sequence = false;
        scope.sequencePrepId = ctrl.$viewValue;
      };
      scope.getCmsDriver = function(){
        if (scope.driver ===undefined){
          var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.sequencePrepId);
          promise.then(function(data){
            scope.driver = data.data.results;
          }, function(data){
             alert("Error: ", data.status);
        });
       }
     };
   }
  }
});