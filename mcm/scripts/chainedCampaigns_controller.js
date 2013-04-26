function resultsCtrl($scope, $http, $location, $window){
    $scope.chainedCampaigns_defaults = [
      {text:'PrepId',select:true, db_name:'prepid'},
      {text:'Actions',select:true, db_name:''},
      {text:'Alias',select:true, db_name:'alias'},
      {text:'Campaigns',select:true, db_name:'campaigns'},
    ];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "chained_campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
       
    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    $scope._ = _; //enable underscorejs to be accessed from HTML template
    $scope.selectedAll = false;

    if($location.search()["page"] === undefined){
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else{
      page = $location.search()["page"];
      $scope.list_page = parseInt(page);
    }
    $scope.select_all_well = function(){
      $scope.selectedCount = true;
      var selectedCount = 0
      _.each($scope.chainedCampaigns_defaults, function(elem){
        if (elem.select){
          selectedCount +=1;
        }
        elem.select = true;
      });
      if (selectedCount == _.size($scope.chainedCampaigns_defaults)){
      _.each($scope.chainedCampaigns_defaults, function(elem){
        elem.select = false;
      });
      $scope.chainedCampaigns_defaults[0].select = true; //set prepid to be enabled by default
      $scope.chainedCampaigns_defaults[1].select = true; // set actions to be enabled
      $scope.chainedCampaigns_defaults[2].select = true; // set actions to be enabled
      $scope.chainedCampaigns_defaults[3].select = true; // set actions to be enabled
      $scope.selectedCount = false;
      }
    };

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
    }
    else{
      $scope.show_well = true;
    }
  };    
   
  $scope.filterResults = function(){
    var data =_.filter($scope.result, function(element){
      return element["valid"];
    });
    if ($scope.role(3)){
      return data;
    }else{
      return $scope.result;
    }
  };

  $scope.$watch('list_page', function(){
      var query = ""
      _.each($location.search(), function(value,key){
        query += "&"+key+"="+value
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
	// remove those with valid = False when !role(3);
      // $scope.valid_result = _.filter(data.data.results, function(element){
      //   return element["valid"];
      //  });
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
    }, function(){ alert("Error getting information"); });
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
    $scope.shouldBeOpen = false;
      $http({method: 'PUT', url:'restapi/chained_requests/save/', data:{member_of_campaign:$scope.prepId, pwg: $scope.selectedPwg}}).success(function(data, stauts){
        $window.location.href ="edit?db_name=chained_requests&query="+data.results;
      }).error(function(data,status){
        alert("Error:"+ status);
        console.log(data, status);
      });
    };
  $scope.createChainedCampaign = function(){
    $http({method: 'PUT', url:'restapi/chained_campaigns/save/', data:{prepid: $scope.campaignId}}).success(function(data, status){
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
    '          <th style="padding: 0px;">Step</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
    '          <td style="padding: 0px;">{{elem.step}}</td>'+
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