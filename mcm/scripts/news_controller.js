function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [
    {text:'Subject', select:true, db_name:'subject'},
  ];
  $scope.update = [];

  $scope.show_well = false;
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "news";
  }else{
    $scope.dbName = $location.search()["db_name"];
  }
  
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
      if (key!= 'shown'){
        query += "&"+key+"="+value;
      }
    });
    var promise = $http.get("search/?db_name="+$scope.dbName+query);
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    promise.then(function(data){
      $scope.result = data.data.results;
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
  $scope.openModal = function () {
    $scope.show_new_modal = true;
    $scope.news_1 = {};
  };
};

// var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);}); 
testApp.directive("addNew", function($http){
  return {
    replace: true,
    restrict: 'EA',
    template:
        '<div modal="show_new_modal" close="close()">'+
        '  <div class="modal-header">'+
        '    <h4>Create a new New</h4>'+
        '  </div>  <!--end of modal header-->'+
        '  <div class="modal-body">'+
        '    <div>'+
        '      New\'s subject: <input type="text" ng-model="news_1.subject"></input>'+
        '    </div>'+
        '    <div>'+
        '      New\'s text: <textarea ng-model="news_1.text" style="width: 510px; height: 187px;"></textarea>'+
        '    </div>'+
        '  </div> <!--end of modal body-->'+
        '  <div class="modal-footer">'+
        '    <button class="btn btn-success" ng-click="createNew()">Create</button>'+
        '    <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
        '  </div> <!--end of modal footer-->'+
        '</div>'
    ,
    link: function(scope, element, attr){
    	scope.close = function(){
    		scope.show_new_modal = false;
    	};
        scope.createNew = function(){
          console.log('lets create!', scope.news);
          $http({method: 'PUT', url:'restapi/news/save/', data:scope.news_1}).success(function(data, status){
            console.log(data, status);
            scope.update["success"] = data.results;
            scope.update["fail"] = false;
            scope.update["status_code"] = status;
            scope.getData();
          }).error(function(data,status){
            scope.update["success"] = false;
            scope.update["fail"] = true;
            scope.update["status_code"] = status;
          });
          scope.close();
        };
    }
  }
});
