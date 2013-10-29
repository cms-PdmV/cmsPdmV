function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [
    {text:'Prepid', select:true, db_name:'prepid'},
    {text:'Actions', select:false, db_name:''},
    {text:'Value', select:true, db_name:'value'},
    {text:'Notes', select:true, db_name:'notes'}
  ];
  $scope.update = [];

  $scope.show_well = false;
  if ($location.search()["db_name"] === undefined){
    $scope.dbName = "settings";
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
      $scope.defaults[0].select = true; // set object to be enabled by default
      $scope.defaults[1].select = true; // set type to be enabled
      $scope.defaults[2].select = true; // set status to be enabled
      $scope.selectedCount = false;
    }
  };

  $scope.sort = {
    column: 'value.prepid',
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

    $scope.objectToId = function(object_name) {
        return object_name.replace(/\//g, "")
    }
};
