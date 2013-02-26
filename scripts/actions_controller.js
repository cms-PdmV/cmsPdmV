function resultsCtrl($scope, $http, $location){ 
    console.log($location.search());
    $scope.actions_defaults = [
        {text:'Actions',select:true, db_name:'prepid'}
//         {text:'Actions',select:true, db_name:''},
    ];
    $scope.campaigns = ["------"];
    $scope.selectedOption = "------";
    $scope.selected_campaign = "";
//     $scope.chained_requests = [];
//     $scope.chained_campaigns = [];
//     $scope.toBeUpdated = {};
//     $scope.watch("selected_campaign", function(){
//        console.log("selected campaign pasikeite:", $scope.selected_campaign); 
//     });
    $scope.select_campaign = function(){
        console.log($scope.actions_defaults);
        console.log($scope.chained_campaigns);
        //set the well to have only ChainedCampaigns which includes selectedOption
        if ($scope.selectedOption == "------"){ //if to show all chained campains -> push all to well values
          console.log("selected to show all");
          tmp = [{text:'Actions',select:true, db_name:'prepid'}];
          _.each($scope.chained_campaigns, function(v){
            tmp.push({text:v._id, select:true, db_name:v._id});
            $scope.actions_defaults = tmp;
          });
        }
        else{
          console.log("if selected not ------");
            var to_remove_list = [];
            var to_add_list = [];
          _.each($scope.chained_campaigns, function(chain_campaign){ //iterate all chained campaigns
            for (i=0; i< chain_campaign.campaigns.length;i++){
                if (_.isString(chain_campaign.campaigns[i])){
                  if (chain_campaign.campaigns[i]== $scope.selectedOption){
                      to_add_list.push({id:chain_campaign._id, alias:chain_campaign.alaias});
                      i = chain_campaign.campaigns.length+1;
                  }else{
//                       console.log("String: ",i," : ",to_add_list,to_remove_list, "pushing: ",chain_campaign._id);
                      to_remove_list.push(chain_campaign._id);
                }
                }else{
                if (_.indexOf(chain_campaign.campaigns[i],$scope.selectedOption) != -1){ //if chained campaing includes selected campaign
                  to_add_list.push({id:chain_campaign._id, alias:chain_campaign.alaias});
                  i = chain_campaign.campaigns.length+1;
                  if (_.indexOf(to_remove_list,chain_campaign._id) !=-1){
                    to_remove_list = _.without(to_remove_list, chain_campaign._id);
                  }
                }
                else{
//                   console.log(i," : ",to_add_list,to_remove_list, "pushing: ",chain_campaign._id);
                  if (_.indexOf(to_remove_list,chain_campaign._id) ==-1){
                    to_remove_list.push(chain_campaign._id);
                  }
                }
              }
            }
            console.log(to_add_list,to_remove_list);
          });
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
                 if (action.text == element.id){ //if element is in actions
                     add = false;  //then set add to FALSE
                }
            });
             if (add){ //if we really desided to add an element -> lets add it. else - nothing to add.
               $scope.actions_defaults.push({text:element.id, select:true, db_name:element.id});
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
//         $scope.chained_campaigns = data.data.results;
        _.each(data.data.results, function(v){
            $scope.actions_defaults.push({text:v._id, select:true, db_name:v._id});
        });
    });

    promise = $http.get('restapi/campaigns/get_all')
    promise.then(function(data){
        _.each(data.data.results, function(v){
           $scope.campaigns.push(v.value);
        });
    });
//     promise = $http.get('search/?db_name=chained_requests&query=""&page=-1')
//     promise.then(function(data){
//        $scope.chained_requests = data.data.results;
//     });
// //     console.log("CR: ",$scope.chained_requests);
// //     console.log("CC : ",$scope.chained_campaigns);
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
        if (member_of_campaign == $scope.selectedOption){
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
            scope.toBeUpdated = {block_number: "", staged:"",threshold:""}; //define a variable to localy bind data
            scope.displayBox = false;
          };
          scope.showInput = function(){
            if (scope.displayBox){
              scope.displayBox = false;
            } else{
              scope.displayBox = true;
            };
          };
          
          scope.commit = function(){
//             ctrl.$viewValue.block_number = scope.toBeUpdated.block_number;
//             ctrl.$viewValue.staged = scope.toBeUpdated.staged;
//             ctrl.$viewValue.threshold = scope.toBeUpdated.threshold;
            scope.showInput();
//             restapi/actions/update
            $http({method:'GET', url:'/restapi/actions/update/',data:angular.toJson(scope.result)}).success(function(data,status){
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
//         '    {{toBeUpdated | json}}'+
        '      <input type="checkbox" ng-model="actionInfo.flag"/>'+
        '      <a ng-click="showInput();" ng-hide="displayBox">'+
        '        <i class="icon-wrench"></i>'+
        '      </a>'+
         '    <div ng-show="displayBox">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.threshold"/>'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.staged" ngMaxlength=3/>'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '      <a ng-click="commit();">'+
        '        <i class="icon-envelope"></i>'+
        '      </a>'+
        '    </div>'+
        '    <text>'+
//         '      {{actionInfo}}'+
//         '      {{selectedOption}}'+
        '    </text>'+
        '  </div>'+
        '  <div ng-switch-when="true">'+
        '  </div>'+
        '</div>'
    };
});
