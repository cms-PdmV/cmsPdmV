function resultsCtrl($scope, $http, $location, $window, $route){
  $scope.defaults = [
    {text:'Prepid', select:true, db_name:'prepid'},
    {text:'Actions', select:true, db_name:''},
    {text:'Meeting', select:true, db_name:'meeting'},
    {text:'Approval', select:true, db_name:'approval'},
    {text:'Status', select:true, db_name:'status'},
    {text:'Deadline', select:true, db_name:'deadline'},
    {text:'Block', select:true, db_name:'block'},
    {text:'Message ID', select:false, db_name:'message_id'},
    {text:'Notes', select:false, db_name:'notes'},
    {text:'Pwg', select:true, db_name:'pwg'},
    {text:'Requests', select:true, db_name:'requests'},
    {text:'Size', select:false, db_name:'size'},
    {text:'History', select:false, db_name:'history'}
  ];
  $scope.update = [];

  $scope.show_well = false;
  $scope.dbName = "mccms";

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
      $scope.defaults[0].select = true;
      $scope.defaults[1].select = true;
      $scope.defaults[2].select = true;
      $scope.defaults[3].select = true;
      $scope.defaults[4].select = true;
      $scope.defaults[5].select = true;
      $scope.defaults[6].select = true;
      $scope.defaults[9].select = true;
      $scope.defaults[10].select = true;
      $scope.selectedCount = false;
    }
  };

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

  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }else{
      $scope.show_well = true;
    }
  };

  $scope.getData = function(){
    var query = "";
    _.each($location.search(), function(value,key){
      if (key!= 'shown' && key != 'fields'){
        query += "&"+key+"="+value;
      }
    });
    var promise = $http.get("search/?db_name="+$scope.dbName+query);
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    promise.then(function(data){
      $scope.result = data.data.results;
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

  $scope.isArray = function(obj){
      return angular.isArray(obj)
  };
}

var ModalDemoCtrl = function ($scope, $http, $window) {
  $scope.open = function (id) {

    var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name);
    promise.then(function(data){
	    $scope.pwgs = data.data.results;
	    $scope.selectedPwg= $scope.pwgs[0];
	    $scope.shouldBeOpen = true;
	    $scope.prepId = id;
	});

  };

    $scope.close = function () {
        $scope.shouldBeOpen = false;
    };

    $scope.save = function () {
        $scope.shouldBeOpen = false;
        if ($scope.selectedPwg){
          $http({method: 'PUT', url:'restapi/mccms/save/', data:{prepid: $scope.selectedPwg, pwg: $scope.selectedPwg}})
              .success(function(data, stauts){
            console.log(data, status);
            if (data.results){
                $window.location.href ="edit?db_name=mccms&prepid="+data.prepid;
            }else{
                alert("Error:"+ data.message);
                console.log(data, status);
            }
          }).error(function(data,status){
            alert("Error:"+ status);
            console.log(data, status);
          });
        }else{
            alert("Error: no pwg defined!");
        }
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