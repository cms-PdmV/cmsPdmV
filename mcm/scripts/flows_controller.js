angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$modal', '$location', '$window',
  function resultsCtrl($scope, $http, $modal, $location, $window){
    $scope.dataColumns = [
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
  	  $scope.getData($scope);
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

    $scope.openCloneModal = function(id)
    {
      var cloneModal = $modal.open({
        templateUrl: 'cloneModal.html',
        controller: CloneModalInstance,
        resolve: {
          prepid : function() {
            return id;
          }
        }
      });

      cloneModal.result.then(function(input_dict)
      {
        $http({method:'PUT', url:'restapi/'+$scope.dbName+'/clone/', data:input_dict}).success(function(data,status){
          $scope.update["success"] = data["results"];
          $scope.update["fail"] = !data["results"];
          $scope.update["status_code"] = status;
          if (data["message"])
          {
            $scope.update["status_code"] = data["message"];
          }
          if (data["prepid"])
          {
            $window.open("edit?db_name=flows&query="+data["prepid"]);
          }
          $scope.update["message"] = data;
        }).error(function(data,status){
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
          $scope.update["message"] = data;
        });
      });
    }

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },function(){
      $scope.getData($scope);
    });
  }]);

angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$modal', '$location',
  function ModalDemoCtrl($scope, $http, $modal, $location){
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
                  $location.url('flows?prepid=' + flowId);
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

var CloneModalInstance = function($http, $scope, $modalInstance, prepid) {
  $scope.data = {
    oldPrepid: prepid,
    newPrepid: ''
  };

  $scope.clone = function() {
    $modalInstance.close({"prepid":$scope.data.oldPrepid, "new_prepid":$scope.data.newPrepid});
  };

  $scope.close = function() {
    $modalInstance.dismiss();
  };
};

// NEW for directive
//var testApp = angular.module('testApp', []).config(function($locationProvider){$locationProvider.html5Mode(true);});
