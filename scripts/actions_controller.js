function resultsCtrl($scope, $http, $location){ 
    console.log($location.search());
    $scope.actions_defaults = [
        {text:'Actions',select:true, db_name:'prepid'}
//         {text:'Actions',select:true, db_name:''},
    ];
    $scope.campaigns = ["------"];
    $scope.selectedOption = "------";
    $scope.selected_campaign = "";
    $scope.generatingAllIcon = false;
//     $scope.chained_requests = [];
//     $scope.chained_campaigns = [];
//     $scope.toBeUpdated = {};
//     $scope.watch("selected_campaign", function(){
//        console.log("selected campaign pasikeite:", $scope.selected_campaign); 
//     });
    $scope.getChainCampainTEXT = function(alias, id){
        if (alias != ""){
          return alias;
        }else{
          return id;
        }
    }
    
    $scope.select_campaign = function(){
        $scope.rootCampaign = [];
        //set the well to have only ChainedCampaigns which includes selectedOption
        if ($scope.selectedOption == "------"){ //if to show all chained campains -> push all to well values
          console.log("selected to show all");
          tmp = [{text:'Actions',select:true, db_name:'prepid'}];
          _.each($scope.chained_campaigns, function(v){
            name = $scope.getChainCampainTEXT(v.alias,v._id);
            tmp.push({text:name, select:v.valid, db_name:v._id});
          });
          $scope.actions_defaults = tmp;
        }
        else{
          console.log("if selected not ------");
            var to_remove_list = [];
            var to_add_list = [];
             _.each($scope.chained_campaigns, function(chain_campaign){
               var remove = true;
               name = $scope.getChainCampainTEXT(chain_campaign.alias, chain_campaign._id);
               for (i=0; i< chain_campaign.campaigns.length; i++){
                 if (_.indexOf(chain_campaign.campaigns[i],$scope.selectedOption) != -1){ //if chained campaing includes selected campaign
                   to_add_list.push({id:chain_campaign._id, alias:chain_campaign.alias, valid: chain_campaign.valid});
                   i = chain_campaign.campaigns.length+1;
                   $scope.rootCampaign.push(chain_campaign.campaigns[0][0]); //push a root campaigs name
                   remove = false; //if we add a campaign that means we dont want it to be removed.
                 }
               }
               if (remove){
                 to_remove_list.push(name);
               }
             });
          $scope.rootCampaign = _.uniq($scope.rootCampaign);
          $scope.actions_defaults = _.filter($scope.actions_defaults, function(element){ //filter all actions from well
            if (element.text != 'Actions'){    //leave actions column
              return (_.indexOf(to_remove_list, element.text) == -1) //if column not in to_add_list -> remove it (a.k.a its in to_be_removed list)
            }else{
              return true;
            }             
          });
           _.each(to_add_list, function(element){ //add columns to the default actions. iterating 1by1
             var add = true; //set default add value to true
             _.each($scope.actions_defaults, function(action){ //iterate over actions to check if to-be added value isn't in it already
                 if (action.text == $scope.getChainCampainTEXT(element.alias,element.id)){ //if element is in actions
                     add = false;  //then set add to FALSE
                }
            });
             if (add){ //if we really desided to add an element -> lets add it. else - nothing to add.
               if (element.valid){
                 $scope.actions_defaults.push({text:$scope.getChainCampainTEXT(element.alias,element.id), select:true, db_name:element.id});
               }else{
                 $scope.actions_defaults.push({text:$scope.getChainCampainTEXT(element.alias,element.id), select:false, db_name:element.id});
               }
               add = false;
             }
           });
        }
    };
    
    $scope.show_well = false;
    if($location.search()["page"] === undefined){
        $location.search("page", 0);
        page = 0;
        $scope.list_page = 0;
    }else{
        page = $location.search()["page"];
        $scope.list_page = parseInt(page);
    }
    var promise = $http.get('search/?db_name=chained_campaigns&query=""&page=-1')
    promise.then(function(data){
         $scope.chained_campaigns = data.data.results;
        _.each(data.data.results, function(v){
            $scope.actions_defaults.push({text:$scope.getChainCampainTEXT(v.alias,v._id), select:v.valid, db_name:v._id});
        });
    });

    promise = $http.get('restapi/campaigns/get_all')
    promise.then(function(data){
        _.each(data.data.results, function(v){
           $scope.campaigns.push(v.value);
        });
    });
  $scope.showing_well = function(){
        if ($scope.show_well){
          $scope.show_well = false;
        }
        else{
//             console.log("true");
            $scope.show_well = true;
        }
    };
    
    $scope.$watch('list_page', function(){
      console.log("modified");
      var promise = $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+$scope.list_page)
          promise.then(function(data){
            $scope.result = data.data.results;
            if ($scope.result.length != 0){
            columns = _.keys($scope.result[0]);
            rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
            $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
            _.each(rejected, function(v){
                add = true;
                _.each($scope.actions_defaults, function(column){
                if (column.db_name == v){
                    add = false;
                  }
                });
                if (add){
//                     $scope.actions_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
                }
              });
            }
//             console.log($scope.actions_defaults);
         }, function(){
             console.log("Error"); 
         });
    });
    
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
  $scope.showingAction = function(member_of_campaign){
    if ($scope.selectedOption == "------"){
        return true;
    }else{
        if (member_of_campaign == $scope.rootCampaign[0]){
            return true;
        }
        else{
            return false;
        }
    }
  };
  $scope.updatedValues = function(member_of_campaign){
    console.log(member_of_campaign);
//      console.log("CR: ",$scope.chained_requests);
//      console.log("CC : ",$scope.chained_campaigns);
  };
  $scope.generateRequests = function(id){
    console.log(id);
    var generateUrl = "";
    if ( id.indexOf("chain_") !=-1){
        generateUrl = "/restapi/chained_campaigns/generate_chained_requests/"+id;
    }else {
        generateUrl = "/restapi/actions/generate_chained_requests/"+id;
    };
//      $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+$scope.list_page)
    promise = $http.get(generateUrl);
    promise.then(function(data){
      console.log(data);
    }, function(data){
        alert("Error: ", data.status);
    });
  };
  $scope.generateAllRequests = function(){
    console.log("Generate all!");
    $scope.generatingAllIcon = true;
    generateUrl = "/restapi/actions/generate_all_chained_requests";
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.generatingAllIcon = false;
      console.log(data);
    }, function(data){
        $scope.generatingAllIcon = false;
        alert("Error: ", data.status);
    });
  };
}
var testApp = angular.module('testApp',[]).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customPrepId", function ($rootScope, $http) {
    return {
        restrict: 'E',
        replace: true,
        require: "ngModel",
        link: function (scope, element, attr, ctrl) {
          ctrl.$render = function(){
//             scope.chainCampaignValues = scope.chained_campaigns.member_of_campaign;
//             scope.chainReqValues = scope.chained_campaigns.member_of_campaign;
            scope.actionInfo = ctrl.$viewValue;
            scope.originalInfo = _.clone(scope.actionInfo);
//             scope.toBeUpdated = {block_number: "", staged:"",threshold:""}; //define a variable to localy bind data
            scope.displayBox = false;
          };
          scope.showInput = function(){
            if (scope.displayBox){
              scope.displayBox = false;
            } else{
              scope.displayBox = true;
            };
          };
          
          scope.close = function(){
            scope.actionInfo = _.clone(scope.originalInfo);
            scope.showInput();
          };
          
          scope.commit = function(){
             ctrl.$viewValue.block_number = parseInt(ctrl.$viewValue.block_number);
//             ctrl.$viewValue.staged = scope.toBeUpdated.staged;
//             ctrl.$viewValue.threshold = scope.toBeUpdated.threshold;
            scope.showInput();
//             restapi/actions/update
            $http({method:'PUT', url:'/restapi/actions/update/',data:angular.toJson(scope.result)}).success(function(data,status){
              console.log(data,status);
//               $scope.update["success"] = data["results"];
//               $scope.update["fail"] = false;
//               $scope.update["status_code"] = status;
            }).error(function(data,status){
//               $scope.update["success"] = false;
//               $scope.update["fail"] = true;
//               $scope.update["status_code"] = status;
                    alert("Error: ", status);
            });
            
          };
        },
        template:
        '<div ng-switch="actionInfo === "undefined"">'+
        '  <div ng-switch-when="false">'+
        '      <input type="checkbox" ng-model="actionInfo.flag"/>'+
        '      <a ng-click="showInput();" ng-hide="displayBox">'+
        '        <i class="icon-wrench"></i>'+
        '      </a>'+
         '    <div ng-show="displayBox">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.block_number == key">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.staged" />'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px; ng-model="actionInfo.threshold" />'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '      <a ng-click="commit();">'+
        '        <i class="icon-envelope"></i>'+
        '      </a>'+
        '      <a ng-click="close();">'+
        '        <i class="icon-minus"></i>'+
        '      </a>'+
        '    </div>'+
        '  </div>'+
        '  <div ng-switch-when="true">'+
        '  </div>'+
        '</div>'
    };
});
