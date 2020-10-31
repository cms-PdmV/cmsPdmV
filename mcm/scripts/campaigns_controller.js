angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
  function resultsCtrl($scope, $http, $location, $window, $modal){

    $scope.dataColumns = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
	      //{text:'Approval',select:true, db_name:'approval'},
        //{text:'Status',select:true, db_name:'status'},
        //{text:'Type',select:true, db_name:'type'},
        //{text:'ProdType',select:true, db_name:'production_type'},
        {text:'CMSSW Release',select:true, db_name:'cmssw_release'},
        {text:'Energy',select:true, db_name:'energy'},
        {text:'Next',select:true, db_name:'next'},
        {text:'Notes',select:true, db_name:'notes'},
    ];
    $scope.dataColumnRename = {
      'www': 'WWW'
    };

    $scope.update = [];
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    console.log('Set dbName to ' + $scope.dbName)
    $scope.new = {};

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData($scope);
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
	    $scope.getData($scope);
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
	    $scope.getData($scope);
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
  $scope.open_isSureModal = function(action, prepid){
    var isSure = $modal.open( {
       templateUrl: 'isSureModal.html',
        controller: ModalIsSureCtrl,
        resolve: {
          prepid: function() {
            return prepid;
          },
          action: function() {
            return action;
          }
        }
    });
    isSure.result.then(function() {
      switch (action) {
        case "delete":
          $scope.delete_object('campaigns', prepid);
          break;
        default:
          break;
      }
    });
  };

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData($scope);
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
        $scope.getData($scope);
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