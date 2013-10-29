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
  $scope.batches_defaults = [
    {text:'PrepId',select:true, db_name:'prepid'},
    {text:'Actions',select:false, db_name:''},
    {text:'Status',select:true, db_name:'status'},
    {text:'Requests',select:true, db_name:'requests'},
    {text:'Notes',select:true, db_name:'notes'},

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

  //watch length of pending HTTP requests -> if there are display loading;
  $scope.$watch(function(){ return $http.pendingRequests.length;}, function(v){
    if (v == 0){  //if HTTP requests pending == 0
      $scope.pendingHTTP = false;
    }else{
      $scope.pendingHTTP = true;
    }
  });
  $scope.getData = function(){
    var query = ""
    _.each($location.search(), function(value,key){
      if (key!= 'shown' && key != 'fields'){
        query += "&"+key+"="+value;
      }
    });
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
    promise.then(function(data){
      $scope.got_results = true;
      $scope.result = data.data.results; 
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
        if ( _.keys($location.search()).indexOf('fields') == -1)
        {
          var shown = "";
          if ($.cookie($scope.dbName+"shown") !== undefined){
            shown = $.cookie($scope.dbName+"shown");
          }
          if ($location.search()["shown"] !== undefined){
            shown = $location.search()["shown"]
          }
          if (shown != ""){
            $location.search("shown", shown);
            binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
            _.each($scope.batches_defaults, function(column){
              column_index = $scope.batches_defaults.indexOf(column);
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
        else
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
    }, function(){
       alert("Error getting main information");
      });
  };
  $scope.$watch('list_page', function(){
  $scope.getData();
    });

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.batches_defaults, function(column){ //iterate all columns
      if(column.select){
        bin_string ="1"+bin_string; //if selected add 1 to binary interpretation
      }else{
        bin_string ="0"+bin_string;
      }
    });
    $location.search("shown",parseInt(bin_string,2)); //put into url the interger of binary interpretation
  };

    $scope.delete_object = function(db, prepid){
      alert("Not yet in RestAPI!" + db+": "+prepid);
    };

    $scope.announce = function(prepid){
      alert("Batch to be announced:"+prepid);
    };
  /*Is Sure modal actions*/
  $scope.open_isSureModal = function(action, prepid){
    $scope.isSure_Modal = true;
    $scope.toggle_prepid = prepid;
    $scope.modal_action = action;
  };
  $scope.closeisSureModal = function(){
    $scope.isSure_Modal = false;
  };
  $scope.sureTotoggle = function(){
    $scope.isSure_Modal = false;
    switch ($scope.modal_action){
      case "delete":
        $scope.delete_object('batches', $scope.toggle_prepid);
        break;
      case "reset":
        $scope.resetBatch($scope.toggle_prepid);
        break;
      default:
        // alert to announce that uknown action is asked???
        break;
    }
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
      //console.log( batch_requests);
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
  $scope.saveCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    if($location.search()["shown"]){
      $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 })
    }
  };
  $scope.useCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    var shown = $.cookie(cookie_name);
    binary_shown = parseInt(shown).toString(2).split('').reverse().join('');
    _.each($scope.batches_defaults, function(elem,index){
      if (binary_shown.charAt(index) == 1){
        elem.select = true;
      }else{
        elem.select = false;
      }
    });
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
    $scope.shouldBeOpen = false;
    $http({method: 'PUT', url:'restapi/batches/announce', data:{prepid: $scope.prepId, notes: $scope.mailContent}}).success(function(data, status){
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
    $scope.mailContent = "";
  };
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