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

    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
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
        if (data["results"]){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData();
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
      $scope.selectedCount = false;
      }
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
    $scope.showing_well = function(){
      if ($scope.show_well){
        $scope.show_well = false;
      }
      else{
        $scope.show_well = true;
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
      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query)
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
              // for(i=0;i<$scope.defaults.length-binary_shown.length;i++){
              //   binary_shown += "0";
              // }
              _.each($scope.defaults, function(column){
                column_index = $scope.defaults.indexOf(column);
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
      }, function(){
        alert("Error getting information");
      });
    };

    $scope.$watch('list_page', function(){
      $scope.getData();
    });

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.defaults, function(column){ //iterate all columns
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
  $scope.open = function (id) {
      
    var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name)
    promise.then(function(data){
	    $scope.pwgs = data.data.results;
	    //if ($scope.pwgs.length==0){
	    //$scope.pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP','TSG','SMP'];
	    //}
	    $scope.selectedPwg= $scope.pwgs[0];
	    $scope.shouldBeOpen = true;
	    $scope.prepId = id;
	});

  };

  $scope.close = function () {

    $scope.shouldBeOpen = false;
  };
    $scope.save = function () {
    console.log($scope.selectedPwg, $scope.prepId);
    $scope.shouldBeOpen = false;
    if ($scope.selectedPwg){
      $http({method: 'PUT', url:'restapi/requests/save/', data:{member_of_campaign:$scope.prepId, pwg: $scope.selectedPwg}}).success(function(data, stauts){
        console.log(data, status);
	if (data.results){
	    $window.location.href ="edit?db_name=requests&query="+data.prepid;
	}else{
	    alert("Error:"+ data.message);
	}
      }).error(function(data,status){
        alert("Error:"+ status);
        console.log(data, status);
      });
    }else{
	alert("Error: no pwg defined");
    }
    };
    
    $scope.createCampaign = function(){
      $http({method: 'PUT', url:'restapi/campaigns/save/', data:{prepid: $scope.campaignId}}).success(function(data, status){
        console.log(data, status);
        $scope.update["success"] = data.results;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = status;
        $scope.getData();
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