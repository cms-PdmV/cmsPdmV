function resultsCtrl($scope, $http, $location, $window, chttp){
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
    $scope.result = [];
    $scope.changed_prepids = [];
    $scope.multiple_selection = {};
    
    //watch selectedOption -> to change it corespondigly in URL
    $scope.$watch("selectedOption", function(){
      $scope.update = [];
      if ($location.search()["select"] == null){
        if ($scope.selectedOption['contains'] != "------"){
            $location.search("select",$scope.selectedOption['contains']);
            //$scope.getData();
            //do_get_data = true;
        }else{
          $location.search("select",null);
        }
      }
      if ($location.search()["starts"] == null){
        if ($scope.selectedOption['starts'] != "------"){
            $location.search("starts",$scope.selectedOption['starts']);
            //$scope.getData();
            //do_get_data = true;
        }else{
          $location.search("starts",null);
        }
      }
    },true);

    $scope.getChainCampainTEXT = function(alias, id){
        if (alias != ""){
          return alias;
        }else{
          return id;
        }
    }
    
    $scope.select_campaign = function(do_get_data){
        $scope.result = []; //clear results on selection
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

        var promise = chttp.get('search/?db_name=chained_campaigns'+query);

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

          // console.log($scope.rootCampaign)
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

	   // then get data
     if (do_get_data == true){
	     $scope.getData();
     }
	   // 

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


    promise = $http.get('restapi/campaigns/listall')
    promise.then(function(data){
      _.each(data.data.results, function(v){
	      //$scope.campaigns.push(v.key);
	      $scope.campaigns.push(v);
      });

	if (($location.search()["select"] === undefined) && ($location.search()["starts"] === undefined)){
    if (($scope.selectedOption['contains'] != "------") && ($scope.selectedOption['starts'] != "------")){
	      $location.search("select", $scope.selectedOption['contains']);
        $location.search("starts", $scope.selectedOption['starts']);
      }
	}else{
      var do_get_data = false;
      if ($location.search()["select"] !== undefined){
	      $scope.selectedOption['contains'] = $location.search()["select"];
        do_get_data = true;
      }
      if ($location.search()["starts"] !== undefined){
        $scope.selectedOption['starts'] = $location.search()["starts"];
        do_get_data = true;
      }
      $scope.select_campaign(do_get_data);
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
    
  $scope.getData = function(){
      $scope.result = [];
      var query = ""
      if ($scope.rootCampaign){ //if defined
        if ($scope.rootCampaign.length == 0){
          $scope.update['status_code'] = "None";
          $scope.update['success'] = false;
          $scope.update['fail'] = true;
          $scope.update['result'] = "No root campaign to get data";
        }
      }
      _.each($scope.rootCampaign, function(element){
        query = "&member_of_campaign="+element;
        _.each($location.search(), function(value,key){
          if (key == 'select'){
            //do nothing
          } else if (key == 'starts'){
            //do nothing
          }
          else{
            query += "&"+key+"="+value;
          };
        });
	      var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
	      promise.then(function(data){
		      _.each( data.data.results , function( item ){
			      $scope.result.push( item );
			  });
		  },function(){
		      alert("Error getting data.");
		  });
	  });
      //then put everything in result
      //      $scope.result = [];
      //      console.log( results );
      //      _.each(results, function(item_list){
      //	      _.each(item_list, function(item){
      //		      $scope.result.push(item);
      //		  });
      //	  });
  

      /*
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
      }
    },function(){
        alert("Error getting data.");
    });
      */
  };


  $scope.$watch('list_page', function(){
    $scope.getData();
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
      $scope.getData();
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
      $scope.getData();
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
      $scope.getData();
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
      $scope.getData();
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
    _.each($scope.multiple_selection, function(element,key){ //lets remove if we have no chains selected and floating selection is false
      var remove = true;
      _.each(element, function(columnId){
        if (columnId.selected == true){
          remove = false;
        }
        if (columnId.chains !== undefined){
          remove = false
        }
      });
      if (remove){
        delete($scope.multiple_selection[key]);
      }
    });
    var dataToSend = {"actions": $scope.selected_prepids, "values":$scope.multipleSelection}
    if (_.keys($scope.multiple_selection).length == 0){
      alert("You have selected 0 actions from table");
      $scope.updatingMultipleActions = false;
    }else{
      var list_of_docs = [];
      _.each($scope.multiple_selection, function(elem, name){
        var column = name;
        _.each($scope.result, function(doc){ //lets find a document to update
          if (doc.prepid == name){
            list_of_docs.push(doc);
          };
        });
        var doc_to_update = list_of_docs[list_of_docs.length-1];
        _.each(elem, function(chain, chain_name){
          if (chain.selected == true){ //if we want to update floating values ->
            doc_to_update['chains'][chain_name]['threshold']= $scope.multipleSelection['threshold'];  
            doc_to_update['chains'][chain_name]['block_number']= $scope.multipleSelection['block_number'];
            doc_to_update['chains'][chain_name]['staged']= $scope.multipleSelection['staged'];
            if ($scope.multipleSelection['flag'] !== undefined){
              doc_to_update['chains'][chain_name]['flag'] = $scope.multipleSelection['flag'];
            }else{
              doc_to_update['chains'][chain_name]['flag'] = false;
            }
          }
          chains_to_update = chain['chains'];
          _.each(chains_to_update, function(chain_of_chains, super_chain_name){
            doc_to_update['chains'][chain_name]['chains'][super_chain_name]['threshold']= $scope.multipleSelection['threshold'];  
            doc_to_update['chains'][chain_name]['chains'][super_chain_name]['block_number']= $scope.multipleSelection['block_number'];
            doc_to_update['chains'][chain_name]['chains'][super_chain_name]['staged']= $scope.multipleSelection['staged'];
            if ($scope.multipleSelection['flag'] !== undefined){
              doc_to_update['chains'][chain_name]['chains'][super_chain_name]['flag'] = $scope.multipleSelection['flag'];
            }else{
              doc_to_update['chains'][chain_name]['chains'][super_chain_name]['flag'] = false;
            } 
          });
        });
      });
      $scope.sendUpdatedDocuents(list_of_docs);
    }
  };

  $scope.sendUpdatedDocuents = function(documents){
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/update_multiple',data:angular.toJson(documents)}).success(function(data,status){
      $scope.updatingMultipleActions = false;
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = data;
      $scope.update['status_code'] = status;
      $scope.getData();
    }).error(function(data,status){
      $scope.updatingMultipleActions = false;
      $scope.update['fail'] = true;
      $scope.update['success'] = false;
      $scope.update['result'] = data;
      $scope.update['status_code'] = status;
    });
    $scope.updatingMultipleActions = false;
    $scope.multipleChanged = false;
    $scope.toggleMultipleInput();
  };

  $scope.wholeColumnSelection = function(columnId){
    _.each($scope.result, function(v){
      if(v['chains'][columnId.db_name] !== undefined){
        var exists = false;
        var id = v['prepid'];
        if ($scope.multiple_selection[id] === undefined){
          $scope.multiple_selection[id] = {};
          $scope.multiple_selection[id][columnId.db_name] = {};
          if ($scope.multiple_selection[id][columnId.db_name]['selected'] === undefined){
            $scope.multiple_selection[id][columnId.db_name]['selected'] = true;
          }
        }else{
          if ($scope.multiple_selection[id][columnId.db_name]['selected'] === undefined){
            $scope.multiple_selection[id][columnId.db_name]['selected'] = false;
          }
          if ($scope.multiple_selection[id][columnId.db_name]['selected'] === false){
            $scope.multiple_selection[id][columnId.db_name]['selected'] = true;
          }else{
            $scope.multiple_selection[id][columnId.db_name]['selected'] = false;
          }

        }
      }
    });
  };

  $scope.upload = function(file){
      /*Upload a file to server*/
    $scope.got_results = false;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
      $scope.result = data.results;
      $scope.got_results = true;
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };
  $scope.commit = function(prepid){
    _.each($scope.result[prepid]['chains'], function(chain){
      if (chain['block_number']){
        chain['block_number'] = parseInt(chain['block_number']);
      }
      _.each(chain['chains'], function(value,key){
        console.log(key,value);
        if (value['block_number']){
          value['block_number'] = parseInt(value['block_number']);
        }
      });
    });    
    $http({method:'PUT', url:'restapi/actions/update/',data:angular.toJson($scope.result[prepid])}).success(function(data,status){
      scope.displayBox = false;
      scope.anychanges = false;
    }).error(function(data,status){
      alert("Error: ", status);
    });
  };
};

testApp.service("chttp", function ($http, $window, $q) {
  var obj = {};

  obj.get = function (query) {
    var code = $window.btoa(query);
    var ret = $window.localStorage[code];

    var deferred = $q.defer();
    
    // if (ret) { //uncoment to improce local load -> takes data from local storage
    //  deferred.resolve(JSON.parse(ret));
    // } else {
      var http_promise = $http.get(query);
      http_promise.then(function (body) {
        deferred.resolve(body);
        $window.localStorage.setItem(code, JSON.stringify(body));
      });
    // }
    
    return deferred.promise;
  };

  return obj;
});

// var testApp = angular.module('testApp',[]).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customPrepId", function ($rootScope, $http) {
    return {
        restrict: 'E',
        replace: true,
        require: "ngModel",
        link: function (scope, element, attr, ctrl) {
          ctrl.$render = function(){
            scope.column = scope.$eval(attr.chain);
            scope.actionInfo = ctrl.$viewValue['chains'][scope.column];
            scope.prepid = ctrl.$viewValue['prepid'];
            scope.originalInfo = angular.toJson(scope.actionInfo);
            scope.displayBox = false;
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
          scope.open = function(){ 
            if (scope.displayBox == true){
              scope.displayBox = false;
            }else {
              scope.displayBox = true;
            };
          }
          //scope.close = function(){ scope.displayBox = false; };
          scope.openSubForm = function(value){
            if (scope.showSubForm === undefined){
              scope.showSubForm = {};
            }
            if (scope.showSubForm[value] == true){
              scope.showSubForm[value] = false;
            }else{
              scope.showSubForm[value] = true;
            }
          };

	        scope.change = function() { 
	          scope.anychanges;
	        };

	        scope.$watch("actionInfo",function(){
            if (! _.isEqual(scope.actionInfo,angular.fromJson(scope.originalInfo))){
              scope.anychanges = true;
              if (scope.changed_prepids.indexOf(scope.prepid) == -1){ 
                scope.changed_prepids.push(scope.prepid);
              }
            }else{
              scope.anychanges = false;
            };
          }, true);

          scope.add_to_selected_list = function(prepid){
            if (scope.multiple_selection[prepid] === undefined){
              scope.multiple_selection[prepid] = {};
              scope.multiple_selection[prepid][scope.column] = {};
              scope.multiple_selection[prepid][scope.column]['selected'] = true;
              scope.multiple_selection[prepid][scope.column]['chains']= {};
            }else{
              if (scope.multiple_selection[prepid][scope.column] === undefined){
                scope.multiple_selection[prepid][scope.column] = {};
                scope.multiple_selection[prepid][scope.column]['selected'] = true;
                scope.multiple_selection[prepid][scope.column]['chains'] = {};
              }else{
                if (scope.multiple_selection[prepid][scope.column]['selected'] == true){
                  scope.multiple_selection[prepid][scope.column]['selected'] = false;
                  if((scope.multiple_selection[prepid][scope.column]['chains'])){
                    if (_.keys(scope.multiple_selection[prepid][scope.column]['chains']).length == 0){
                      delete(scope.multiple_selection[prepid][scope.column]['chains']);
                    }
                  }
                }else{
                  scope.multiple_selection[prepid][scope.column]['selected'] = true;
                }
              }
            }
          };
          scope.add_chain_to_selected_list = function(prepid,chain){
            if (scope.multiple_selection[prepid] === undefined){
              scope.multiple_selection[prepid] = {};
              scope.multiple_selection[prepid][scope.column] = {};
              if (scope.multiple_selection[prepid][scope.column]['selected'] === undefined){
                scope.multiple_selection[prepid][scope.column]['selected'] = false;
              }
              scope.multiple_selection[prepid][scope.column]['chains'] = {};
              scope.multiple_selection[prepid][scope.column]['chains'][chain] = true;
            }else{
              if (scope.multiple_selection[prepid][scope.column] === undefined){
                scope.multiple_selection[prepid][scope.column] = {};
                scope.multiple_selection[prepid][scope.column]['chains'] = {};
              }
              if (scope.multiple_selection[prepid][scope.column]['chains'] === undefined){
                scope.multiple_selection[prepid][scope.column]['chains'] = {};
              }
              if (scope.multiple_selection[prepid][scope.column]['chains'][chain] == true){
                scope.multiple_selection[prepid][scope.column]['chains'][chain] = false;
                delete(scope.multiple_selection[prepid][scope.column]['chains'][chain]);
                if (_.keys(scope.multiple_selection[prepid][scope.column]['chains']).length == 0){
                  delete(scope.multiple_selection[prepid][scope.column]['chains']);
                }
              }else{
                scope.multiple_selection[prepid][scope.column]['chains'][chain] = true;
              }
            }
          }
        },
        template:
        '<div ng-switch="actionInfo === "undefined"">'+
        '  <div ng-switch-when="false">'+
        '    <input type="checkbox" ng-model="actionInfo.flag" ng-click="showInput()" ng-disabled="role(3);" rel="tooltip" title="Set the action for {{column}} on {{prepid}}"/>'+
        '    <a ng-click="open();" ng-hide="role(3);" title="Edit action parameters">'+
        '      <i class="icon-wrench"></i>'+
        '    </a>'+

        '    <div ng-show="role(3);">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number" ng-disabled="true">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.block_number == key">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.staged" ng-disabled="true"/>'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.threshold" ng-disabled="true"/>'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '    </div>'+
        '      <input type="checkbox" ng-click="add_to_selected_list(prepid)" ng-checked="multiple_selection[prepid][column].selected" rel="tooltip" title="Add to multiple list" ng-hide="role(3);"/>'+
        '    <div ng-show="displayBox">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.block_number">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.block_number == key">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.staged"/>'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.threshold"/>'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '    </div>'+
        '    <div ng-repeat="(cr,value) in actionInfo.chains">'+
        '      <input type="checkbox" ng-model="actionInfo.chains[cr].flag" ng-disabled="role(3);" rel="tooltip" title="Set the action for {{column}} on {{prepid}}"/>'+
        '      <a ng-click="openSubForm(cr);" ng-hide="role(3);" title="Edit action parameters">'+
        '        <i class="icon-wrench"></i>'+
        '      </a>'+
        '      <input type="checkbox" ng-click="add_chain_to_selected_list(prepid,cr)" ng-checked="multiple_selection[prepid][column].chains[cr]" rel="tooltip" title="Add to multiple list" ng-hide="role(3);"/>'+
        '      <a rel="tooltip" title="Show chained request {{cr}}" ng-href="chained_requests?query=prepid%3D%3D{{cr}}" target="_blank">'+
        '        <i class="icon-indent-left"></i>'+
        '      </a>'+
        '    <form class="form-inline" ng-show="showSubForm[cr]">'+
        '      <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.chains[cr].block_number" ng-disabled="role(3);">'+
        '        <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.chains[cr].block_number == key">{{key}}</option>'+
        '      </select>'+
        '      <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.chains[cr].staged" ng-disabled="role(3);"/>'+
        '      <span class="input-append">'+
        '        <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.chains[cr].threshold" ng-disabled="role(3);"/>'+
        '        <span class="add-on">%</span>'+
        '      </span>'+
        '    </form>'+
        '    </div>'+
        '  </div>'+
        '  <div ng-switch-when="true">'+
        '  </div>'+
        '</div>'
    };
});