function resultsCtrl($scope, $http, $location, $window){
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "batches";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }

  $scope.puce = {};
  $scope.r_status = {};
  $scope.update = [];
  $scope.filt = {}; //define an empty filter
  $scope.local_requests = {};
  $scope.underscore = _;

  $scope.batches_defaults = [
    {text:'PrepId',select:true, db_name:'prepid'},
    {text:'Actions',select:false, db_name:''},
    {text:'Status',select:true, db_name:'status'},
    {text:'Requests',select:true, db_name:'requests'},
    {text:'Notes',select:true, db_name:'notes'}

  ];

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

  //watch length of pending HTTP requests -> if there are display loading;
  $scope.$watch(function(){ return $http.pendingRequests.length;}, function(v){
    //if HTTP requests pending == 0
     $scope.pendingHTTP = !(v==0);
  });
  $scope.getData = function(){
    var query = "";
    _.each($location.search(), function(value,key){
      if (key!= 'shown' && key != 'fields'){
        query += "&"+key+"="+value;
      }
    });
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    var promise = $http.get("search?"+ "db_name="+$scope.dbName+query+"&get_raw");
    promise.then(function(data){
      $scope.got_results = true;
      $scope.result = _.pluck(data.data.rows, 'doc');
      if ($scope.result.length != 0){
        columns = _.keys($scope.result[0]);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
        _.each(rejected, function(v){
            add = true;
            _.each($scope.batches_defaults, function(column){
            if (column.db_name == v){
                add = false;
            }
         });
            if (add){
                $scope.batches_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
        });
        if ( _.keys($location.search()).indexOf('fields') != -1)
        {
          _.each($scope.batches_defaults, function(elem){
            elem.select = false;
          });
          _.each($location.search()['fields'].split(','), function(column){
            _.each($scope.batches_defaults, function(elem){
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
       alert("Error getting main information");
      });
  };

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData();
    });


    $scope.announce = function(prepid){
      alert("Batch to be announced:"+prepid);
    };

  $scope.resetBatch = function(batch_id ){
      $http({method:'GET', url: 'restapi/batches/reset/'+batch_id}).success(function(data,status){
	      $scope.getData();
	      alert('successfully resetted the batch');
	  }).error(function(status){
		  alert('failed');
	      });
  };

  $scope.loadStats = function(batch_requests){
      _.each( batch_requests, function(elem,index){
	      $http({method:'GET', url: 'public/restapi/requests/get_status/'+elem.content.pdmv_prep_id}).success(function(data,status){
		      r_prepid=_.keys(data)[0];
		      r_status = data[r_prepid];
		      $scope.r_status[ r_prepid ] = r_status;
		      status_map = { 'done' : 'led-green.gif',
				     'submitted' : 'led-blue.gif',
				     'approved' : 'led-orange.gif',
				     'defined' : 'led-orange.gif',
				     'validation' : 'led-red.gif',
				     'new' : 'led-red.gif'}

		      if (status_map[r_status]){
			  $scope.puce[ r_prepid ] = status_map[r_status];
		      }else{
			  $scope.puce[ r_prepid ] = 'icon-question-sign';
		      }

		  }).error(function(status){
			  alert('cannot get status for '+elem.content.pdmv_prep_id);
		      });
	  });
  };
  $scope.inspect = function(batchid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/inspect/'+batchid}).success(function(data,status){
	      $scope.getData();
	  }).error(function(status){
		  alert('Cannot inspect '+batchid);
	      });
  };

  $scope.hold = function(batchid) {
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/hold/'+batchid}).success(function(data,status){
	    $scope.getData();
	  }).error(function(status){
		  alert('Cannot hold or release '+batchid);
	  });
  };

  $scope.preloadRequest = function (chain, load_single, number) {
    var url = "restapi/requests/get/"+chain;
    if ( !_.has($scope.local_requests,chain) ){
      var promise = $http.get(url);
      promise.then( function(data){
        $scope.local_requests[chain] = data.data.results.reqmgr_name;
        if (load_single != "")
        {
          _.each($scope.local_requests[chain], function (element) {
            $scope.$broadcast('loadDataSet', [element.name, number, load_single]);
          });
        }
      },function(data){
        alert("error " + data.results);
      });
    }  
  };

  $scope.broadcast_inspect = function (requests_data, column_id) {
    _.each(requests_data, function (element, index){
      if ($scope.r_status[element.content.pdmv_prep_id] == "submitted")
      {
        $scope.preloadRequest(element.content.pdmv_prep_id, column_id, index);
      }
    });
  };
  $scope.generateAllRequests = function (input_data)
  {
    var tmp_url = [];
    if (input_data.length > 0)
    {
      _.each(input_data, function (elem) {
          tmp_url.push(elem.content.pdmv_prep_id);
      });
      tmp_url = _.uniq(tmp_url);
      return tmp_url.join(";");
    }else
    {
      return "";
    }
  };

}

var ModalDemoCtrl = function ($scope, $http, $modal) {
  $scope.announceModal = function (id) {
      var announceModal = $modal.open( {
         templateUrl: 'announceModal.html',
          controller: ModalAnnounceCtrl,
          resolve: {
              prepid: function() {
                  return id;
              },
              type: function() {
                  return "Announce";
              }
          }
      });

      announceModal.result.then(function (data) {
        $http({method: 'PUT', url:'restapi/batches/announce', data:{prepid: data.prepid, notes: data.mail}}).success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["results"] = data.results;
          $scope.update["status_code"] = status;
          $scope.getData();
          //   $window.location.href ="edit?db_name=requests&query="+data.results;
        }).error(function(data,status){
          alert("Error:"+ status);
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });

      })
  };

  $scope.isSureModal = function(action, prepid) {
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

      isSure.result.then(function () {
        switch (action){
          case "delete":
            alert("Not yet in RestAPI!");
            break;
          case "reset":
            $scope.resetBatch(prepid);
            break;
          default:
            alert("Unknown action!");
            break;
        }
      })
  };

  $scope.openNotifyModal = function (id) {
      var notifyModal = $modal.open( {
         templateUrl: 'announceModal.html',
          controller: ModalAnnounceCtrl,
          resolve: {
              prepid: function() {
                  return id;
              },
              type: function() {
                  return "Notify";
              }
          }
      });

      notifyModal.result.then(function (data) {
        $http({method: 'PUT', url:'restapi/batches/notify', data:{prepid: data.prepid, notes: data.mail}}).success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["results"] = data.results;
          $scope.update["status_code"] = status;
        }).error(function(data,status){
          alert("Error:"+ status);
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });
      })
  };

};

var ModalAnnounceCtrl = function($scope, $modalInstance, prepid, type) {
    $scope.prepid = prepid;
    $scope.type = type;
    $scope.mail = {
        mailContent: ""
    };

    $scope.send = function() {
        $modalInstance.close({prepid: $scope.prepid, mail:$scope.mail.mailContent})
    };

    $scope.close = function() {
        $modalInstance.dismiss();
    }
};


// var testApp = angular.module('testApp',['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
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