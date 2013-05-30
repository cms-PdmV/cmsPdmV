function resultsCtrl($scope, $http, $location, $window){
    $scope.filt = {}; //define an empty filter
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "actions";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
       
    $scope.actions_defaults = [
    //  {text:'Actions',select:true, db_name:'prepid'}
//         {text:'Actions',select:true, db_name:''},
    ];
    $scope.campaigns = ["------"];
    $scope.selectedOption = {};
    $scope.selectedOption['contains'] = "------";
    $scope.selectedOption['starts'] = "------";
    //not used ? JR    $scope.selected_campaign = "";

    $scope.generatingAllIcon = false;
    $scope.selected_prepids = [];
    $scope.multipleSelection = {};
    $scope.update = [];

    //watch selectedOption -> to change it corespondigly in URL
    $scope.$watch("selectedOption", function(){
      if ($scope.selectedOption['contains'] != "------"){
          $location.search("select",$scope.selectedOption['contains']);
      }
      if ($scope.selectedOption['starts'] != "------"){
          $location.search("starts",$scope.selectedOption['starts']);
      }
    },true);

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
        if (($scope.selectedOption['contains'] == "------") && ($scope.selectedOption['starts'] == "------")){ //if to show all chained campains -> push all to well values
          //console.log("selected to show all");
          var tmp = [];
          $scope.actions_defaults = tmp;
        }
        else{
        var query = ""
        if (($scope.selectedOption['contains'] != "------")){
          query+="&contains="+$scope.selectedOption['contains'];
        };
        if (($scope.selectedOption['starts'] != "------")){
          query+="&root="+$scope.selectedOption['starts'];
        };
        var promise = $http.get('search/?db_name=chained_campaigns'+query);
          promise.then(function(data){
           $scope.chained_campaigns = data.data.results;
    
          //console.log("if selected not ------");
            $scope.actions_defaults = [{text:'Actions',select:true, db_name:'prepid'}];
            var to_remove_list = [];
            var to_add_list = [];
             _.each($scope.chained_campaigns, function(chain_campaign){
               var remove = true;
               name = $scope.getChainCampainTEXT(chain_campaign.alias, chain_campaign._id);
               for (i=0; i< chain_campaign.campaigns.length; i++){
                // if (_.indexOf(chain_campaign.campaigns[i],$scope.selectedOption['contains']) != -1){ //if chained campaing includes selected campaign
                   to_add_list.push({id:chain_campaign._id, alias:chain_campaign.alias, valid: chain_campaign.valid});
                   i = chain_campaign.campaigns.length+1;
                   $scope.rootCampaign.push(chain_campaign.campaigns[0][0]); //push a root campaigs name
                   remove = false; //if we add a campaign that means we dont want it to be removed.
                // }
               }
               if (remove){
                 to_remove_list.push(name);
               }
             });
          $scope.rootCampaign = _.uniq($scope.rootCampaign);
          console.log($scope.rootCampaign)
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


    promise = $http.get('restapi/campaigns/get_all')
    promise.then(function(data){
      _.each(data.data.results, function(v){
        $scope.campaigns.push(v.key);
      });

	if (($location.search()["select"] === undefined) && ($location.search()["starts"] === undefined)){
	    $location.search("select", $scope.selectedOption['contains']);
      $location.search("starts", $scope.selectedOption['starts']);
	}else{
      if ($location.search()["select"] !== undefined){
	      $scope.selectedOption['contains'] = $location.search()["select"];
      }
      if ($location.search()["starts"] !== undefined){
        $scope.selectedOption['starts'] = $location.search()["starts"];
      }
	    $scope.select_campaign();
	}
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
      //console.log("modified");
      //      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+"&page="+$scope.list_page)
      var query = ""
      _.each($location.search(), function(value,key){
	      if (key == 'select'){
          if(value !='------'){
		        query += "&member_of_campaign="+value;
          }
	      }
        else if(key != 'starts'){
          query += "&"+key+"="+value;
        };
	  });
      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query)
          promise.then(function(data){
            $scope.result = data.data.results;
            if ($scope.result.length != 0){
            columns = _.keys($scope.result[0]);
            rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
            $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
//             _.each(rejected, function(v){
//                 add = true;
//                 _.each($scope.actions_defaults, function(column){
//                 if (column.db_name == v){
//                     add = false;
//                   }
//                 });
// //                if (add){
// //                     $scope.actions_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
// //                }
//               });
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
    if (($scope.selectedOption['contains'] == "------")&&($scope.selectedOption['starts'] == "------")){
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
  
  $scope.generateRequests = function(id){
    //console.log(id);
    var generateUrl = "";
    if ( id.indexOf("chain_") !=-1){
        generateUrl = "restapi/chained_campaigns/generate_chained_requests/"+id;
    }else {
        generateUrl = "restapi/actions/generate_chained_requests/"+id;
    };
//      $http.get("search/?"+ "db_name="+$location.search()["db_name"]+"&query="+$location.search()["query"]+"&page="+$scope.list_page)
    promise = $http.get(generateUrl);
    promise.then(function(data){
      //console.log(data);
      
      $scope.update['status_code'] = data.status;
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = id+" generated Successfully";
      $window.location.reload();
    }, function(data){
        $scope.update['status_code'] = data.status;
        $scope.update['fail'] = true;
        $scope.update['success'] = false;
        $scope.update['result'] = id+" generation Failed";
        alert("Error: ", data.status);
    });
  };
  $scope.generateAllRequests = function(){
    //console.log("Generate all!");
    $scope.generatingAllIcon = true;
    
    generateUrl = "restapi/actions/generate_all_chained_requests";
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.generatingAllIcon = false;
      //console.log(data);
      
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = "All requests generated Successfully";
      $scope.update['status_code'] = data.status;
      $window.location.reload();
    }, function(data){
        $scope.update['fail'] = true;
        $scope.update['success'] = false;
        $scope.update['result'] = "All requests generation Failed";
        $scope.update['status_code'] = data.status;
        alert("Error: ", data.status);
    });
  };
  $scope.refreshSingleAction = function(id){
    generateUrl = "restapi/actions/detect_chains/"+id;
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.refreshingAllIcon = false;
      //console.log(data);
      
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = id+" chain detected Successfully";
      $scope.update['status_code'] = data.status;
      $window.location.reload();
    }, function(data){
        $scope.refreshingAllIcon = false;
        
        $scope.update['fail'] = true;
        $scope.update['success'] = false;
        $scope.update['result'] = id+ " chain detection Failed";
        $scope.update['status_code'] = data.status;
        alert("Error: ", data.status);
    });
  };
  $scope.refreshActions = function(){
    //console.log("Detect all!");
    $scope.refreshingAllIcon = true;
    
    generateUrl = "restapi/actions/detect_chains";
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.refreshingAllIcon = false;
      //console.log(data);
      
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = "All chains detected Successfully";
      $scope.update['status_code'] = data.status;
      $window.location.reload();
    }, function(data){
        $scope.refreshingAllIcon = false;
        
        $scope.update['fail'] = true;
        $scope.update['success'] = false;
        $scope.update['result'] = "All chains detection Failed";
        $scope.update['status_code'] = data.status;
        alert("Error: ", data.status);
    });
  };

  $scope.toggleMultipleInput = function(){
    if ($scope.showMultipleInput){
      $scope.showMultipleInput = false;
    }else{
      $scope.multipleSelection["block_number"] = 0;
      $scope.showMultipleInput = true;
    }
  };
  $scope.$watch('multipleSelection', function(){
    if ($scope.multipleSelection['block_number'] !== undefined){
      $scope.multipleChanged = true;
    }
  }, true);
  $scope.commitMultipleSelection = function(){
    $scope.updatingMultipleActions = true;
    $scope.multipleSelection["block_number"] = parseInt($scope.multipleSelection["block_number"]);
    var dataToSend = {"actions": $scope.selected_prepids, "values":$scope.multipleSelection}
    if ($scope.selected_prepids.length == 0){
      alert("You have selected 0 actions from table");
      $scope.updatingMultipleActions = false;
    }else{
      //console.log($scope.multipleSelection);
      //lets send the data to server WOOOO
      $http({method:'PUT', url:'restapi/'+$scope.dbName+'/update_multiple',data:JSON.stringify(dataToSend)}).success(function(data,status){
        $scope.updatingMultipleActions = false;
        $scope.update['success'] = true;
        $scope.update['fail'] = false;
        $scope.update['result'] = data;
        $scope.update['status_code'] = status;
        // $window.location.reload();
      }).error(function(data,status){
        $scope.updatingMultipleActions = false;
        $scope.update['fail'] = true;
        $scope.update['success'] = false;
        $scope.update['result'] = data;
        $scope.update['status_code'] = status;
      });
      $scope.multipleChanged = false;
      $scope.toggleMultipleInput();
    }
  };
}
// var testApp = angular.module('testApp',[]).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customPrepId", function ($rootScope, $http) {
    return {
        restrict: 'E',
        replace: true,
        require: "ngModel",
        link: function (scope, element, attr, ctrl) {
          ctrl.$render = function(){
//             scope.chainCampaignValues = scope.chained_campaigns.member_of_campaign;
//             scope.chainReqValues = scope.chained_campaigns.member_of_campaign;
            scope.column = scope.$eval(attr.chain);
//             console.log(ctrl.$viewValue);
            scope.actionInfo = ctrl.$viewValue['chains'][scope.column];
            scope.prepid = ctrl.$viewValue['prepid'];
//             console.log(ctrl.$viewValue);
            scope.originalInfo = _.clone(scope.actionInfo);
//             scope.toBeUpdated = {block_number: "", staged:"",threshold:""}; //define a variable to localy bind data
            scope.displayBox = false;
//             console.log(scope.$eval(attr.chain));
            scope.anychanges = false;
          };
          scope.showInput = function(){
	          if (scope.actionInfo.flag){
		          scope.displayBox = true;
	          }
	           else{
		          scope.displayBox = false;
	          }
          };
          scope.open = function(){ scope.displayBox = true;};
          scope.close = function(){ scope.displayBox = false; };
	        scope.change = function() { 
	          scope.anychanges;
	        };

	        scope.$watch("actionInfo",function(){
            if (! _.isEqual(scope.actionInfo,scope.originalInfo)){
              scope.anychanges = true;
            }else{
              scope.anychanges = false;
            }
          }, true);

          scope.commit = function(){
             ctrl.$viewValue['chains'][scope.column].block_number = parseInt(ctrl.$viewValue['chains'][scope.column].block_number);
//             ctrl.$viewValue.staged = scope.toBeUpdated.staged;
//             ctrl.$viewValue.threshold = scope.toBeUpdated.threshold;
//            scope.showInput();
            //console.log(ctrl.$viewValue);
            //console.log(scope.actionInfo);
             $http({method:'PUT', url:'restapi/actions/update/',data:angular.toJson(ctrl.$viewValue)}).success(function(data,status){
               //console.log(data,status);
	             scope.displayBox = false;
               scope.anychanges = false;
             }).error(function(data,status){
                     alert("Error: ", status);
             });
          };
          scope.add_to_selected_list = function(prepid){
            var selected = {};
            selected['prepid'] = prepid;
            selected['column'] = scope.column;
            //console.log(selected);
            //console.log(scope.selected_prepids.indexOf(selected));
            //console.log(_.contains(scope.selected_prepids, selected));
            var exists = false;
            _.each(scope.selected_prepids, function(v){
              if (v['prepid'] == prepid && v['column'] == scope.column){ //if exists in array then lets remove
                scope.selected_prepids.splice(scope.selected_prepids.indexOf(v),1);
                exists = true;
              }
            });
            if (!exists){
              scope.selected_prepids.push(selected);
            }
          };
        },
        template:
        '<div ng-switch="actionInfo === "undefined"">'+
        '  <div ng-switch-when="false">'+
        '    <input type="checkbox" ng-model="actionInfo.flag" ng-click="showInput()" ng-disabled="role(3);" rel="tooltip" title="Set the action for {{column}} on {{prepid}}"/>'+
        '    <a ng-click="open();" ng-hide="displayBox || role(3);" title="Edit action parameters">'+
        '      <i class="icon-wrench"></i>'+
        '    </a>'+
        '    <a ng-show="anychanges" ng-click="commit();" rel="tooltip" title="Save updated values for {{prepid}}">'+
        '      <i class="icon-warning-sign"></i>'+
        '    </a>'+
        '<div ng-show="role(3);">'+
        '  <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number" ng-disabled="true">'+
        '    <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.block_number == key">{{key}}</option>'+
        '  </select>'+
        '  <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.staged" ng-disabled="true"/>'+
        '  <span class="input-append">'+
        '    <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.threshold" ng-disabled="true"/>'+
        '    <span class="add-on">%</span>'+
        '  </span>'+
        '</div>'+
        '      <input type="checkbox" ng-click="add_to_selected_list(prepid)" ng-checked="selected_prepids.indexOf(prepid) != -1 && 1<2" rel="tooltip" title="Add to multiple list" ng-hide="role(3);"/>'+
        '    <div ng-show="displayBox">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.block_number == key">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.staged"/>'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.threshold"/>'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '      <a ng-click="close();">'+
        '        <i class="icon-remove"></i>'+
        '      </a>'+
        '    </div>'+
        '    <a ng-repeat="cr in actionInfo.chains" rel="tooltip" title="Show chained request {{cr}}" ng-href="chained_requests?query=prepid%3D%3D{{cr}}" target="_blank">'+
        '      <i class="icon-check"></i>'+
        '    </a >'+
        '  </div>'+
        '  <div ng-switch-when="true">'+
        '  </div>'+
        '</div>'
    };
});
