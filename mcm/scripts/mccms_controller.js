function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [
    {text:'Prepid', select:true, db_name:'prepid'},
    {text:'Actions', select:true, db_name:''},
    {text:'Meeting', select:true, db_name:'meeting'},
    {text:'Approval', select:false, db_name:'approval'},
    {text:'Status', select:false, db_name:'status'},
    {text:'Deadline', select:true, db_name:'deadline'},
    {text:'Block', select:true, db_name:'block'},
    {text:'Message ID', select:false, db_name:'message_id'},
    {text:'Notes', select:false, db_name:'notes'},
    {text:'Pwg', select:false, db_name:'pwg'},
    {text:'Requests', select:true, db_name:'requests'},
    {text:'Size', select:false, db_name:'size'},
    {text:'Chains', select:true, db_name:'chains'},
    {text:'History', select:false, db_name:'history'}
  ];
  $scope.update = [];

  $scope.dbName = "mccms";

  $scope.sort = {
    column: 'value.name',
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
    var query = "";
    _.each($location.search(), function(value,key){
      if (key!= 'shown' && key != 'fields'){
        query += "&"+key+"="+value;
      }
    });
    var promise = $http.get("search?db_name="+$scope.dbName+query+"&get_raw");
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    promise.then(function(data){
      $scope.result = _.pluck(data.data.rows, 'doc');
      $scope.result_status = data.status;
      $scope.got_results = true;
      if ($scope.result.length != 0){
        var columns = _.keys($scope.result[0]);
        var rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
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
    },function(){
       alert("Error getting information");
    });
  };

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData();
        $scope.selected_prepids = [];
    });

  $scope.cancel = function( mccm_id ){
      $http({method:'GET', url:'restapi/mccms/cancel/'+ mccm_id}).success(function(data,status){
	      if (data.results){
		  alert("Ticket canceled");
	      }else{
		  alert(data.message);
	      }
	  }).error(function(status){
		  alert("Could not cancel the ticket");
	      });
  };
  $scope.remove = function( mccm_id){
      $http({method:'DELETE', url:'restapi/mccms/delete/'+ mccm_id}).success(function(data,status){
	      if (data.results){
		  alert("Ticket deleted");
	      }else{
		  alert(data.message);
	      }
	  }).error(function(status){
		  alert("Could not delete the ticket");
	      });
  };
  $scope.generate = function( mccm_id, opt){
      console.log( mccm_id );

      var promise= $http.get("restapi/mccms/generate/"+mccm_id+opt);
      promise.then(function(data){
	      if (data.data.results){
		  alert("Everything went fine");
	      }
	      else{
		  alert(data.data.message);
	      }
	  },function(){
	      alert("Something went wrong");
	  });
  };

  $scope.isArray = function(obj){
    return angular.isArray(obj)
  };
  $scope.generateAllRequests = function (input_data)
  {
    var tmp_url = [];
    if (input_data.length > 0)
    {
      _.each(input_data, function (elem) {
        if (_.isArray(elem))
        {
          tmp_url.push(elem[0]+","+elem[1]);
        }else
        {
          tmp_url.push(elem);
        }
      });
      return tmp_url.join(";");
    }else
    {
      return "";
    }
  };
}

var ModalDemoCtrl = function ($scope, $http, $modal) {
  $scope.open = function () {

    var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name);
    promise.then(function(data){
	    var pwgs = data.data.results;
        $modal.open({
            templateUrl: "createMccmModal.html",
            controller: CreateMccmModalInstance,
            resolve: {
                pwgs: function() {
                    return pwgs;
                }
            }
        });
	}, function() {
        alert("Error while getting PWGs for user")
    });
  };


};

var CreateMccmModalInstance = function($scope, $modalInstance, $window, $http, pwgs) {

    $scope.mccms = {
        pwgs: pwgs,
        selectedPwg: pwgs[0]
    };

    $scope.close = function() {
        $modalInstance.dismiss();
    };

    $scope.save = function () {
        if ($scope.mccms.selectedPwg){
          $http({method: 'PUT', url:'restapi/mccms/save/', data:{prepid: $scope.mccms.selectedPwg, pwg: $scope.mccms.selectedPwg}})
              .success(function(data, stauts){
            if (data.results){
                $window.location.href ="edit?db_name=mccms&prepid="+data.prepid;
            }else{
                alert("Error:"+ data.message);
            }
          }).error(function(data,status){
            alert("Error:"+ status);
          });
        }else{
            alert("Error: no pwg defined!");
        }
        $modalInstance.close();
    };
};

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