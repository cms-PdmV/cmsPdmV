angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.flows_defaults = [
      {text:'PrepId',select:true, db_name:'prepid'},
      {text:'Actions',select:true, db_name:''},
      {text:'Approval',select:true, db_name:'approval'},
      {text:'Allowed Campaigns',select:true, db_name:'allowed_campaigns'},
      {text:'Next Campaign',select:true, db_name:'next_campaign'}
    ];

    $scope.update = [];
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "flows";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.underscore = _;

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

     $scope.setFailure = function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    };

    $scope.setSuccess = function(status){
  	  $scope.update["success"] = true;
  	  $scope.update["fail"] = false;
  	  $scope.update["status_code"] = status;
  	  $scope.getData();
    };

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          $scope.setSuccess(status);
        }else{
          $scope.setFailure(status);
        }
      }).error(function(status){
        alert('Error no.' + status + '. Could not delete object.');
      });
    };

    $scope.next_step = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+prepid})
           .success(function(data, status){
            $scope.setSuccess(status);
              }).error(function(status){
            $scope.setFailure(status);
           });
    };

    $scope.reset_flow = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+prepid+'/0'})
           .success(function(data, status){
            $scope.setSuccess(status);
              }).error(function(status){
            $scope.setFailure(status);
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

    $scope.getData = function(){
      var query = ""
      _.each($location.search(), function(value,key){
        if (key!= 'shown' && key != 'fields'){
          query += "&"+key+"="+value;
        }
      });
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var promise = $http.get("search?"+ "db_name="+$scope.dbName+query+"&get_raw");
      promise.then(function(data){
        $scope.result_status = data.status;
        $scope.got_results = true;
        $scope.result = _.pluck(data.data.rows, 'doc');
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
          if ( _.keys($location.search()).indexOf('fields') != -1)
          {
            _.each($scope.flows_defaults, function(elem){
              elem.select = false;
            });
            _.each($location.search()['fields'].split(','), function(column){
              _.each($scope.flows_defaults, function(elem){
                if ( elem.db_name == column )
                {
                  elem.select = true;
                }
              });
            });
          }
        }
          $scope.selectionReady = true;
      }, function(){ alert("Error getting information"); });
    };

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },function(){
      $scope.getData();
    });
  }]);

angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$modal',
  function ModalDemoCtrl($scope, $http, $modal){
    $scope.open = function () {
      var flowCreationModal = $modal.open({
          templateUrl: "flowCreateModal.html",
          controller: CreateFlowModalInstance
      });
      flowCreationModal.result.then(function(flowId) {
          console.log(flowId);
          $http({method: 'PUT', url:'restapi/flows/save/', data:{prepid: flowId}})
              .success(function(data, status){
                if (data["results"] == true)
                {
                  $scope.setSuccess(status);
                }
                else{
                  $scope.setFailure(status);
                }
              }).error(function(data,status){
                $scope.setFailure(status);
           });
      })
    };

    $scope.createFlow = function(){
    };
}]);

var CreateFlowModalInstance = function($scope, $modalInstance) {
    $scope.flow = {flowId: ""};
    $scope.close = function() {
        $modalInstance.dismiss();
    };
    $scope.save = function() {
        $modalInstance.close($scope.flow.flowId);
    }

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
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
    '          <td style="padding: 0px;">{{elem.updater.submission_date}}</td>'+
    '          <td style="padding: 0px;">'+
    '              <div ng-switch="elem.updater.author_name">'+
    '                <div ng-switch-when="">{{elem.updater.author_username}}</div>'+
    '                <div ng-switch-default>{{elem.updater.author_name}}</div>'+
    '              </div>'+
    '          </td>'+
    '          <td style="padding: 0px;">{{elem.step}}</td>'+
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