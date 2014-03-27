function resultsCtrl($scope, $http, $location, $window){
    $scope.filt = {}; //define an empty filter a stupid update test for github
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "actions";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
       
    $scope.actions_defaults = [
    //  {text:'Actions',select:true, db_name:'prepid'}
    //  {text:'Actions',select:true, db_name:''},
    ];
    $scope.campaigns = ["------"];
    $scope.selectedOption = {};
    $scope.selectedOption['contains'] = "------";
    $scope.selectedOption['starts'] = "------";
    //not used ? JR    $scope.selected_campaign = "";

    $scope.generatingAllIcon = false;
    //$scope.selected_prepids = [];
    $scope.multipleSelection = {};
    $scope.update = [];
    $scope.result = [];
    $scope.changed_prepids = [];
    $scope.multiple_selection = {};
    $scope.tabsettings = {
      "view":{
        active:false
      },
      "file":{
        active:false
      }
    };
    
    //watch selectedOption -> to change it corespondigly in URL
    $scope.$watch("selectedOption", function(){
      $scope.update = [];
      if ($scope.selectedOption['contains'] != "------"){
        $location.search("select",$scope.selectedOption['contains']);
        //$scope.getData("");
        //do_get_data = true;
      }else
      {
        //$location.search("select",null);
      }
      if ($scope.selectedOption['starts'] != "------"){
        $location.search("starts",$scope.selectedOption['starts']);
        //$scope.getData("");
        //do_get_data = true;
      }else
      {
        //$location.search("starts",null);
      }
    },true);

    $scope.getChainCampainTEXT = function(alias, id){
      if (alias != ""){
        return alias;
      }else{
        return id;
      }
    }
    $scope.get_chained_campaigns_info = function(do_get_data, query){
      $scope.rootCampaign = [];
      var promise = $http.get('search?db_name=chained_campaigns'+query+"&get_raw");
      promise.then(function(data){
        $scope.update['success'] = true;
        $scope.update['fail'] = false;
        $scope.update['status_code'] = "Ok";
        $scope.chained_campaigns = _.pluck(data.data.rows, 'doc');
        //console.log("if selected not ------");
        $scope.actions_defaults = [{text:'Actions',select:true, db_name:'prepid'},
            {text:'History',select:true, db_name:'history'}];
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
          if (element.text != 'Actions' && element.text !='History'){    //leave actions column
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
        //then get data
        if (do_get_data == true){
          $scope.getData("");
        }
        // 
      }, function(status) {
        $scope.update['success'] = false;
        $scope.update['fail'] = true;
        $scope.update['status_code'] = status;

      });
    };

    $scope.select_campaign = function(do_get_data){
      $scope.got_results = false;
      //$scope.result = []; //clear results on selection
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
        $scope.get_chained_campaigns_info(do_get_data,query);
      }
    };

    $scope.show_well = false;


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
    }else{
      $scope.show_well = true;
    }
  };

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.actions_defaults, function(column){ //iterate all columns
      if(column.select){
        bin_string ="1"+bin_string; //if selected add 1 to binary interpretation
      }else{
        bin_string ="0"+bin_string;
      }
    });
    $location.search("shown",parseInt(bin_string,2)); //put into url the interger of binary interpretation
  };

  $scope.parseShown = function(){
    var shown = "";
    //if ($.cookie($scope.dbName+"shown") !== undefined){
    //  shown = $.cookie($scope.dbName+"shown");
   // }
    if ($location.search()["shown"] !== undefined){
      shown = $location.search()["shown"];
    }
    if (shown != ""){
      $location.search("shown", shown);
      binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
      _.each($scope.actions_defaults, function(column){
        column_index = $scope.actions_defaults.indexOf(column);
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
  $scope.getData = function(prepid){
  $scope.multiple_selection = {};
   if($scope.file_was_uploaded)
   {
     $scope.upload($scope.uploaded_file);
   }
   else
   {
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
        if (key != 'select' && key  != 'starts' && key != 'shown' ){
          query += "&"+key+"="+value;
        };
      });
            $scope.got_results = false;
	    var promise = $http.get("search?"+ "db_name="+$scope.dbName+query+"&get_raw");
	    promise.then(function(data){
		    _.each(_.pluck(data.data.rows, 'doc') , function( item ){
			    $scope.result.push( item );
			  });
            $scope.got_results = true;
        $scope.parseShown();
            $scope.update['success'] = false;
            $scope.update['fail'] = false;
      //set selected columns?
		  },function(){
		    alert("Error getting data.");
		  });
	  });
    }
  };

  $scope.getDataFromButton = function(){
    $scope.file_was_uploaded = false;
    $scope.getData("");
  };

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData("");
        $scope.multiple_selection = {};
    });

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
      }else{
        return false;
      }
    }
  };
  
  $scope.generateRequests = function(id){
    var generateUrl = "";
    if ( id.indexOf("chain_") !=-1){
	    var ids_on_the_page=[];
	    _.each($scope.result, function(item){
		    ids_on_the_page.push(item.prepid);
	    });
	    generateUrl = "restapi/actions/generate_chained_requests/"+ids_on_the_page.join();
    } else{
      generateUrl = "restapi/actions/generate_chained_requests/"+id;
    };
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.update['status_code'] = data.status;
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = id+" generated Successfully";
      $scope.getData("");
    }, function(data){
      $scope.update['status_code'] = data.status;
      $scope.update['fail'] = true;
      $scope.update['success'] = false;
      $scope.update['result'] = id+" generation Failed";
      alert("Error: ", data.status);
    });
  };

  $scope.generateAllRequests = function(){
    $scope.generatingAllIcon = true;
    var ids_on_the_page=[];
    _.each($scope.result, function(item){      
	    ids_on_the_page.push(item.prepid);          
	  });  
    generateUrl = "restapi/actions/generate_chained_requests/"+ids_on_the_page.join();
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.generatingAllIcon = false;
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = "All requests generated Successfully";
      $scope.update['status_code'] = data.status;
      $scope.getData("");
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
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = id+" chain detected Successfully";
      $scope.update['status_code'] = data.status;
      $scope.getData("");
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
    $scope.refreshingAllIcon = true;
    var ids_on_the_page=[];
    _.each($scope.result, function(item){
      ids_on_the_page.push(item.prepid);
    });
    generateUrl = "restapi/actions/detect_chains/"+ids_on_the_page.join();
    promise = $http.get(generateUrl);
    promise.then(function(data){
      $scope.refreshingAllIcon = false;
      $scope.update['success'] = true;
      $scope.update['fail'] = false;
      $scope.update['result'] = "All chains detected Successfully";
      $scope.update['status_code'] = data.status;
      $scope.getData("");
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
          remove = false;
        }
      });
      if (remove){
        delete($scope.multiple_selection[key]);
      }
    });
    //var dataToSend = {"actions": $scope.selected_prepids, "values":$scope.multipleSelection}
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
      $scope.update['result'] = data.results;
      $scope.update['status_code'] = status;
      $scope.getData("");
    }).error(function(data,status){
      $scope.updatingMultipleActions = false;
      $scope.update['fail'] = true;
      $scope.update['success'] = false;
      $scope.update['result'] = data;
      $scope.update['status_code'] = status;
    });
    $scope.updatingMultipleActions = false;
    $scope.multipleChanged = false;
  };

  $scope.formatDocument = function(doc){
    _.each(doc.chains, function(chain){
      if (chain.staged !== undefined){
        if (chain.staged == null){
          delete(chain.staged);
        }
      }
      if (chain.threshold !== undefined){
        if (chain.threshold == null){
          delete(chain.threshold);
        }
      }
      if (chain.block_number !== undefined){
        chain.block_number = parseInt(chain.block_number);
      }
      _.each(chain.chains, function(super_chain){ //crosscheck all sub-chains
      if (super_chain.staged !== undefined){
        if (super_chain.staged == null){
          delete(super_chain.staged);
        }
      }
      if (super_chain.threshold !== undefined){
        if (super_chain.threshold == null){
          delete(super_chain.threshold);
        }
      }
      if (super_chain.block_number !== undefined){
        super_chain.block_number = parseInt(super_chain.block_number);
      } 
      });
    });
    return doc;
  };

  $scope.commitAllChanges = function(){
    var documents_to_update = [];
    _.each($scope.changed_prepids, function(doc_id_to_update){
      _.each($scope.result, function(doc){
        if (doc.prepid == doc_id_to_update){
          documents_to_update.push($scope.formatDocument(doc));
        }
      });
    });
    $scope.sendUpdatedDocuents(documents_to_update);
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
          if ($scope.multiple_selection[id][columnId.db_name] === undefined)
          {
            $scope.multiple_selection[id][columnId.db_name] = {};
          }
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
    $scope.file_was_uploaded = true;
    $scope.uploaded_file = file;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
      $scope.result = data.results;
      //var chained_campaign = $scope.result[0]["member_of_campaign"];
      //query = "&contains="+ chained_campaign;
      //$scope.get_chained_campaigns_info(false,query);
      $scope.got_results = true;
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };
  $scope.commit = function(prepid){
    var place = 0;
    _.each($scope.result, function(element, index){
      if(element.prepid == prepid){
        place = index;
      }
    }); //get index of prepid
    _.each($scope.result[place]['chains'], function(chain){
      if (chain['block_number']){
        chain['block_number'] = parseInt(chain['block_number']);
      }
      _.each(chain['chains'], function(value,key){
        if (value['block_number']){
          value['block_number'] = parseInt(value['block_number']);
        }
      });
    });    
    $http({method:'PUT', url:'restapi/actions/update/',data:angular.toJson($scope.result[place])}).success(function(data,status){
      $scope.changed_prepids = $scope.changed_prepids.splice($scope.changed_prepids.indexOf(prepid),0);
      $scope.getData($scope.result[place]['prepid']);
    }).error(function(data,status){
      alert("Error: "+ status);
    });
  };
  $scope.toggleMultipleTransfer = function(){
    $scope.allChainedCampaings = _.rest($scope.actions_defaults);
    if ($scope.showMultipleTransfer){
      $scope.showMultipleTransfer = false;
    } else {
      $scope.showMultipleTransfer = true;
    }
  };
  $scope.transferMultiple = function(){
    var documents_to_update = [];
    _.each($scope.multiple_selection, function(doc, id){
      var selected_chain="";
      _.each(doc, function(chain, name){
        if (chain.selected){
          selected_chain = name;
        }
      });
      if (selected_chain != ""){
        _.each($scope.result, function(elem, key){
          if(elem.prepid == id){
            elem.chains[$scope.selected_transfer_target] = elem.chains[selected_chain];
            documents_to_update.push(elem);
          }
        });
      }
    });
    if(documents_to_update.length != 0){
      $scope.sendUpdatedDocuents(documents_to_update);
    }else{
      $scope.update['success'] = false;
      $scope.update['fail'] = true;
      $scope.update['result'] = "No actions were selected for transfer";      
    };
  };
};

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
        '    <input type="checkbox" ng-click="add_to_selected_list(prepid)" ng-checked="multiple_selection[prepid][column].selected" rel="tooltip" title="Add to multiple list" ng-hide="role(3);"/>'+
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
        '    <ul ng-repeat="(cr,value) in actionInfo.chains">'+
        '      <li>'+
        '        <input type="checkbox" ng-model="actionInfo.chains[cr].flag" ng-disabled="role(3);" rel="tooltip" title="Set the action for {{column}} on {{prepid}}"/>'+
        '        <a ng-click="openSubForm(cr);" ng-hide="role(3);" title="Edit action parameters">'+
        '          <i class="icon-wrench"></i>'+
        '        </a>'+
        '        <input type="checkbox" ng-click="add_chain_to_selected_list(prepid,cr)" ng-checked="multiple_selection[prepid][column].chains[cr]" rel="tooltip" title="Add to multiple list" ng-hide="role(3);"/>'+
        '        <a rel="tooltip" title="Show chained request {{cr}}" ng-href="chained_requests?prepid={{cr}}" target="_blank">'+
        '          <i class="icon-indent-left"></i>'+
        '        </a>'+
        '        <form class="form-inline" ng-show="showSubForm[cr]">'+
        '          <select class="input-mini" style="margin-bottom: 0px; margin-left: 2px;" ng-model="actionInfo.chains[cr].block_number" ng-disabled="role(3);">'+
        '            <option ng-repeat="key in [0,1,2,3,4,5,6]" ng-selected="actionInfo.chains[cr].block_number == key">{{key}}</option>'+
        '          </select>'+
        '          <input type="number" style="margin-bottom: 0px; width: 80px;" ng-model="actionInfo.chains[cr].staged" ng-disabled="role(3);"/>'+
        '          <span class="input-append">'+
        '            <input type="number" style="margin-bottom: 0px; width: 25px;" ng-model="actionInfo.chains[cr].threshold" ng-disabled="role(3);"/>'+
        '            <span class="add-on">%</span>'+
        '          </span>'+
        '        </form>'+
        '      </li>'+
        '    </ul>'+
        '  </div>'+
        '  <div ng-switch-when="true"></div>'+
        '</div>'
    };
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
//     '          <th style="padding: 0px;">Message</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+ //is it needed?
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
    '          <td style="padding: 0px;">{{elem.step}}</td>'+ //is it needed?
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
