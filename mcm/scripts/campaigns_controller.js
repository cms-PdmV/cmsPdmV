angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){

    $scope.defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
	      //{text:'Approval',select:true, db_name:'approval'},
        //{text:'Status',select:true, db_name:'status'},
        //{text:'Type',select:true, db_name:'type'},
        //{text:'ProdType',select:true, db_name:'production_type'},
        {text:'CMSSW Release',select:true, db_name:'cmssw_release'},
        {text:'Energy',select:true, db_name:'energy'},
	      {text:'Next',select:true, db_name:'next'},
	      {text:'Notes',select:true, db_name:'notes'}
    ];

    $scope.update = [];
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    $scope.new = {};

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData();
        }else{
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        }
        }).error(function(status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
          alert('Error no.' + status + '. Could not delete object.');
        });
    };

    $scope.delete_edit = function(id){
        $scope.delete_object($scope.dbName, id);
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

    $scope.single_step = function(step, prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/'+step+'/'+prepid}).success(function(data,status){
        $scope.update["success"] = data["results"];
	if ($scope.update["success"] == true){
	    $scope.update["fail"] = false;
	    $scope.update["status_code"] = data["results"];
	    $scope.getData();
	}else{
	    $scope.update["success"] = false;
	    $scope.update["fail"] = true;
	    $scope.update["status_code"] = data.message;
	}
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    $scope.next_status = function(prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/status/'+prepid}).success(function(data,status){
        $scope.update["success"] = data["results"];
	if ($scope.update["success"] == true){
	    $scope.update["fail"] = false;
	    $scope.update["status_code"] = data["results"];
	    $scope.getData();
	}else{
	    $scope.update["success"] = false;
	    $scope.update["fail"] = true;
	    $scope.update["status_code"] = data.message;
	}
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };

    $scope.getData = function(){
      var query = ""
      _.each($location.search(), function(value,key){
        if ( (key != 'shown') && (key != 'fields') ){
          query += "&"+key+"="+value;
        }
      });
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var promise = $http.get("search?"+ "db_name="+$scope.dbName+query + "&get_raw")
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
//           $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
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
          if ( _.keys($location.search()).indexOf('fields') != -1)
          {
            _.each($scope.defaults, function(elem){
              elem.select = false;
            });
            _.each($location.search()['fields'].split(','), function(column){
              _.each($scope.defaults, function(elem){
                if ( elem.db_name == column )
                {
                  elem.select = true;
                }
              });
            });
          }
        }
          $scope.selectionReady = true;
      }, function(){
        alert("Error getting information");
      });
    };

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData();
    });
}]);

angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$modal',
  function ModalDemoCtrl($scope, $http, $modal) {
    $scope.openRequestCreator = function (id) {
      var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name);
      promise.then(function(data){
	      var pwgs = data.data.results;
          $modal.open({
            templateUrl: 'createRequestModal.html',
            controller: ModalCreateRequest,
            resolve: {
              pwgs: function(){
                return pwgs;
              },
              selectedPwg: function(){
                return pwgs[0];
              },
              prepid: function() {
                return id;
              }
            }
          })
	    });
    };

    $scope.openCampaignCreator = function () {
      var campaignModal = $modal.open( {
        templateUrl: 'createCampaignModal.html',
        controller: ModalCreateCampaign
      });
      campaignModal.result.then(function(campaignId) {
        $http({method: 'PUT', url:'restapi/campaigns/save/', data:{prepid: campaignId}}).success(function(data, status){
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $scope.getData();
      }).error(function(data,status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
      })
    };

    var ModalCreateRequest = function($scope, $modalInstance, $window, $http, pwgs, selectedPwg, prepid) {
      $scope.prepid = prepid;
      $scope.pwgs = pwgs;
      $scope.pwg = {
        selected: selectedPwg
      };
      $scope.save = function () {
        if ($scope.pwg.selected) {
            $http({method: 'PUT', url: 'restapi/requests/save/', data: {member_of_campaign: $scope.prepid, pwg: $scope.pwg.selected}}).success(function (data, stauts) {
              if (data.results) {
                $window.location.href = "edit?db_name=requests&query=" + data.prepid;
              } else {
                alert("Error:" + data.message);
              }
              }).error(function (data, status) {
                alert("Error:" + status);
              });
        } else {
          alert("Error: No PWG defined!");
        }
        $modalInstance.close();
      };
      $scope.close = function() {
        $modalInstance.dismiss();
      }
    };

    var ModalCreateCampaign = function($scope, $modalInstance, $http) {
      $scope.campaign = {
        id: ""
      };
      $scope.close = function() {
        $modalInstance.dismiss();
      };
      $scope.save = function() {
        $modalInstance.close($scope.campaign.id);
      }
    };
}]);

// NEW for directive
// var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
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
    '          <li><b>{{key}}</b>: <div style="width:600px;overflow:auto"><pre>{{value}}</pre></div></li>'+
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