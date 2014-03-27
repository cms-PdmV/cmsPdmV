function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [
    {text:'UserName', select:true, db_name:'username'},
    {text:'Full name', select:true, db_name:'fullname'},
    {text:'Actions', select:false, db_name:''},
    {text:'Email', select:false, db_name:'email'},
    {text:'Role', select:true, db_name:'role'},
    {text:'Pwg', select:true, db_name:'pwg'}
  ];
  $scope.update = [];
  $scope.all_pwgs = [];

  $scope.show_well = false;
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "users";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }


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
      $scope.defaults[3].select = true; // set actions to be enabled
      $scope.selectedCount = false;
    }
  };

  $scope.sort = {
    column: 'value.username',
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
    }else{
      $scope.show_well = true;
    }
  };

  $scope.getData = function(){
    var query = ""
    _.each($location.search(), function(value,key){
      if (key!= 'shown' && key != 'fields'){
        query += "&"+key+"="+value;
      }
    });
    var promise = $http.get("search?db_name="+$scope.dbName+query+"&get_raw");
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    promise.then(function(data){
      $scope.result = _.pluck(data.data.rows, 'doc');
      $scope.got_results = true;
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

  $scope.askrole = function(pwg){
      // pwg should be taken from a drop down
   //    var promise_pwg = $http.get("restapi/users/get_pwg")
   //    promise_pwg.then(function(data){
	  //     //$scope.all_pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP','TSG','SMP'];
	  //     $scope.all_pwgs = data.data.results;
	  //     console.log( $scope.all_pwgs );
	  // });

      var promise = $http.get("restapi/users/ask_role/"+pwg);
      promise.then(function(data, status){
	      $scope.update["success"] = true;
	      $scope.update["fail"] = false;
	      $scope.update["status_code"] = data.status;
	      $scope.update["results"] = data.data.results;
	      $scope.getData();
	  },function(data, status){
	      $scope.update["success"] = false;
	      $scope.update["fail"] = true;
	      $scope.update["status_code"] = data.status;
	  });
  };

  $scope.changeRole = function(username,step){
    var promise = $http.get("restapi/users/change_role/"+username+"/"+step);
    promise.then(function(data, status){
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = data.status;
      $scope.update["results"] = data.data.results;
      $scope.getData();
      //$window.location.reload();
    },function(data, status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = data.status;
    });
  };

  $scope.addMe = function(){
    var promise = $http.get("restapi/users/add_role");
    promise.then(function(data, status){
      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = data.status;
      $scope.getData();
    },function(data, status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = data.status;
    });
  };
  $scope.saveCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    if($location.search()["shown"]){
      $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 })
    }
  };

  $scope.pwgModal = false;
  $scope.closePwgModal = function()
  {
    $scope.newPWG = "------";
    $scope.pwgModal = false;
  };
  $scope.openPwgModal = function(curr_pwgs)
  {
    console.log(curr_pwgs);
    $scope.newPWG = "------";
    if ($scope.all_pwgs.length == 0)
    {
      var promise = $http.get("restapi/users/get_pwg")
      promise.then(function(data){
        $scope.all_pwgs = _.difference(data.data.results, curr_pwgs);
        $scope.all_pwgs.splice(0,0,"------");
        $scope.newPWG = $scope.all_pwgs[0];
        $scope.pwgModal = true;
      });
    }
    else
    {
      $scope.newPWG = $scope.all_pwgs[0];
      $scope.pwgModal = true;
    }
  };
  $scope.selectPwg = function()
  {
    if ($scope.newPWG != "------")
    {
     $scope.askrole($scope.newPWG);
    }
    $scope.closePwgModal();
  };

}

var ModalDemoCtrl = function ($scope, $http, $window) {
  $scope.mailContent = "";
  $scope.mailSubject = "";
  $scope.openPWGNotify = function (pwg) {
    $scope.notifyModal = true;
    $scope.pwg = pwg;
  };

  $scope.closePWGNotify = function () {
    $scope.notifyModal = false;
    $scope.mailContent = "";
    $scope.mailSubject = "";
  };
  $scope.pwgNotify = function () {
    if(!$scope.mailContent.length && !$scope.mailSubject.length) {
        alert("Cannot send empty message with empty subject");
        return;
    }
    $scope.notifyModal = false;
    $http({method: 'PUT', url:'restapi/users/notify_pwg', data:{pwg: $scope.pwg, subject:$scope.mailSubject, content: $scope.mailContent}})
        .success(function(data, status){
            console.log(data);
            alert("Notification sent");
        }).error(function(data,status){
            alert("Error:"+ status);
        });
    $scope.mailContent = "";
    $scope.mailSubject = "";
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
//     '          <td style="padding: 0px;"><a rel="tooltip" title={{elem.message}}><i class="icon-info-sign"></i></a></td>'+
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
// var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});