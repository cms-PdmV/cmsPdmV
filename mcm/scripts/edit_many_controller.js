function resultsCtrl($scope, $http, $location, $window){
  $scope.defaults = [];
  $scope.edited_fields = {};
  $scope.dbName = $location.search()["db_name"];
  $scope.update = [];
  $scope.underscore = _;

  $scope.minPrepid = function(string_of_prepids)
  {
  	$scope.list_of_prepids = string_of_prepids.split(',');
  	var min = $scope.list_of_prepids[0];
  	_.each($scope.list_of_prepids,function(v){
  	  if(v<min)
  	  {
  	    min = v;
  	  }
  	});
  	return min;
  }
  $scope.prepid = $scope.minPrepid($location.search()["prepid"]);
  if($scope.dbName == "requests")
  {
    // get the editable -> set false in list
    $scope.not_editable_list = ["Cmssw release", "Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version", "History"]; //user non-editable columns
    $scope.non_multiple_editable= ["Cmssw release", "Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version", "History"]; //user non-editable columns
    var promise = $http.get("restapi/requests/editable/"+$scope.prepid)
    promise.then(function(data)
    {
      $scope.parseEditableObject(data.data.results);
    });
  }
  if($location.search()["page"] === undefined)
  {
    page = 0;
    $location.search("page", 0);
    $scope.list_page = 0;
  }else
  {
    page = $location.search()["page"];
    $scope.list_page = parseInt(page);
  }
    
    $scope.parseEditableObject = function(editable){
      _.each(editable, function(elem,key){
        if (elem == false){
          if (key[0] != "_"){ //if its not mandatory couchDB values eg. _id,_rev
            column_name = key[0].toUpperCase()+key.substring(1).replace(/\_/g,' ')
            if($scope.not_editable_list.indexOf(column_name) ==-1){
              $scope.not_editable_list.push(column_name);
            }
            if($scope.non_multiple_editable.indexOf(column_name) ==-1){
              $scope.non_multiple_editable.push(column_name);
            }
          }
        }
      });
    };

    $scope.booleanize_sequence = function(sequence){
      _.each(sequence, function(value, key){
        if (_.isString(value))
        {
          switch(value.toLowerCase()){
            case "true":
              sequence[key] = true;
              break;
            case "false":
              sequence[key] = false;
              break;
            default:
              break;
          }
        }
      });
    };

    $scope.submit_edit = function(){
      switch($scope.dbName){
        case "requests":
          _.each($scope.result["sequences"], function(sequence){
            $scope.booleanize_sequence(sequence);
            if (_.isString(sequence["step"]))
            {
              sequence["step"] = sequence["step"].split(",");
            }
            if (_.isString(sequence["datatier"]))
            {
              sequence["datatier"] = sequence["datatier"].split(",");
            }
            if (_.isString(sequence["eventcontent"]))
            {
              sequence["eventcontent"] = sequence["eventcontent"].split(",");
            }
          });
         $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
          break;
        case "campaigns":
          _.each($scope.result["sequences"], function(sequence){
            _.each(sequence, function(subSequence, key){
              if (key != "$$hashKey") //ignore angularhs hashkey 
              {
                $scope.booleanize_sequence(subSequence);
                if (_.isString(subSequence["step"]))
                {
                  subSequence["step"] = subSequence["step"].split(",");
                }
                if (_.isString(subSequence["datatier"]))
                {
                  subSequence["datatier"] = subSequence["datatier"].split(",");
                }
                if (_.isString(subSequence["eventcontent"]))
                {
                  subSequence["eventcontent"] = subSequence["eventcontent"].split(",");
                }
              }
            });  
          });
          break;
        default:
          break;
      }
      var data_to_send = {};
      data_to_send["updated_data"] = {};
      _.each($scope.edited_fields, function(value,key){
        if(value)
        {
          data_to_send["updated_data"][key] = $scope.result[key]
        }
      });
      data_to_send["prepids"] = $scope.list_of_prepids;
      $http({method:'PUT', url:'restapi/'+$location.search()["db_name"]+'/update_many',data:angular.toJson(data_to_send)}).success(function(data,status){
        $scope.update["success"] = data["results"];
        $scope.update["fail"] = false;
        $scope.update["message"] = data["message"];
        $scope.update["status_code"] = status;
        if ($scope.update["success"] == false){
          $scope.update["fail"] = true;
        }else{
          if($scope.sequencesOriginal){
            delete($scope.sequencesOriginal);
          }
          $scope.getData();
        }
      }).error(function(data,status){
        $scope.update["message"] = data;
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    $scope.display_approvals = function(data){
    };
    $scope.sort = {
      column: 'prepid',
      descending: false
    };
    $scope.role = function(priority){
	    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
	      return true;
	    }else{
	      return false;
	    }
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
  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }else{
      $scope.show_well = true;
    }  
  };
  $scope.getData = function(){
    var promise = $http.get("restapi/"+ $location.search()["db_name"]+"/get/"+$scope.prepid)
    promise.then(function(data){
      $scope.result = data.data.results;
      if ($scope.result.length != 0){
        columns = _.keys($scope.result);
        rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
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
          if($scope.not_editable_list.indexOf(v[0].toUpperCase()+v.substring(1).replace(/\_/g,' ')) == -1)
          {
            $scope.not_editable_list.push(v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '));
          }
        });
        setTimeout(function(){ //update fragment field
          codemirror = document.querySelector('.CodeMirror');
          if (codemirror != null){
            _.each(angular.element(codemirror),function(elem){
              elem.CodeMirror.refresh();
            });          
          }
        },300);
        //});
      }
    }, function(){ alert("Error getting information"); });
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
  $scope.editableFragment = function(){
    return $scope.not_editable_list.indexOf('Fragment')!=-1;
  };
  $scope.hideSequence = function(roleNumber){
    if ($scope.role(roleNumber)){
      return true; //if we hide by role -> hide
    }else{ //else we check if sequence is in editable list
      if ($scope.not_editable_list.indexOf("Sequences")!=-1){
        return true; //if its in list -> hide
      }else{
        return false; //else let be displayed: ng-hide=false
      }
    }
  };
  $scope.removeUserPWG = function(elem){
    //console.log(_.without($scope.result["pwg"], elem));
    $scope.result["pwg"] = _.without($scope.result["pwg"], elem);
  };
  $scope.showAddUserPWG = function(){
    $scope.showSelectPWG = true;
    var promise = $http.get("restapi/users/get_pwg")
    promise.then(function(data){
	    //$scope.all_pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP','TSG','SMP'];
	    $scope.all_pwgs = data.data.results;
	});
    
  };
  $scope.addUserPWG = function(elem){
    if($scope.result["pwg"].indexOf(elem) == -1){
      $scope.result["pwg"].push(elem);
    }
  };
    $scope.addToken = function(tok) {
        $http({method:'PUT', url:'restapi/tags/add/', data:JSON.stringify({tag:tok.value})})
    };

  $scope.removeToken = function(tok) {
      // for now let's store all tags, can be changed in future for some checks
//      $http({method:'PUT', url:'restapi/tags/remove/', data:JSON.stringify({tag:tok.value})})
  }

  $scope.toggleNotEditable = function(column_name)
  {
    var name_index = $scope.not_editable_list.indexOf(column_name)
    if(name_index != -1)
    {
      $scope.not_editable_list.splice(name_index,1);
    }else
    {
      $scope.not_editable_list.push(column_name);
    }
  }
  $scope.changeData = function(elem){
    var new_list = [elem]
    _.each($scope.list_of_prepids, function(elem){
      if (new_list.indexOf(elem) == -1)
      {
        new_list.push(elem);
      }
    });
    $location.search("prepid", new_list.join(","));
    $scope.prepid = elem;
    $scope.getData();
  }
}
var ModalDemoCtrl = function ($scope) {
  $scope.open = function (number) {
  	console.log(number);
    $scope.shouldBeOpen = true;
    $scope.sequenceNum = number;
    $scope.seqModalInfo = _.clone($scope.sequenceInfo[number]);
  };

  $scope.close = function (number) {
    $scope.shouldBeOpen = false;
    $scope.seqModalInfo = _.clone($scope.sequenceInfo[number]);
  };
    $scope.save = function () {
    $scope.result.sequences = $scope.sequenceInfo;
    $scope.shouldBeOpen = false;
  };
  $scope.openNewSubSequence = function(){
    $scope.shouldBeOpen = true;
    $scope.newSequenceName = "";
    $scope.newSequence = _.clone($scope.default_sequences);
  };
  $scope.saveNewSubform = function(index){
    if ($scope.dbName !="requests"){
      $scope.result.sequences[index][$scope.newSequenceName] = $scope.newSequence;
      $scope.driver[index][$scope.newSequenceName] = $scope.newSequence;
    }else{
      $scope.result.sequences[index].push($scope.newSequence);
    };
    $scope.shouldBeOpen = false;
  };
  $scope.saveNewSequence = function(){
    var shift = 0;
    if ($scope.dbName != "requests"){
    //  if (_.size($scope.result.sequences) != 0){
    //    shift =1; //in case we are ading a new sequence not from 0 we must increase array index of sequences
    //  }
      $scope.driver[_.size($scope.result.sequences)+shift] = {default: $scope.newSequence};
      $scope.result.sequences[_.size($scope.result.sequences)+shift] = {default: $scope.newSequence};
    }else{
      $scope.driver.push($scope.newSequence); //add a string to display in table
      $scope.result.sequences.push($scope.newSequence); //add to original data -> to be commited
    }
  };
}
var genParamModalCtrl = function($scope, $http) {
  $scope.openGenParam = function(index) {
    $scope.modalOpen = true;
    $scope.modal_data = _.clone($scope.genParam_data[index]);
  };

  $scope.closeGenParam = function(index) {
    $scope.modalOpen = false;
  };
    $scope.saveGenParam = function(index) {
    $scope.modalOpen = false;
    _.each($scope.modal_data, function(key,elem){
      if (_.isString(key) && elem !="$$hashKey"){ //ignore: submission details object, angularjs $$hashKey
        $scope.genParam_data[index][elem] = parseFloat(key);
      }
    });
  };

  //methods for adding a new Gen Param.
  $scope.openAddParam = function(){
    $scope.addParamLoad = true;
    var promise = $http.get("restapi/"+ $scope.dbName+"/default_generator_params/"+$scope.result["prepid"]);
    promise.then(function(data){
      $scope.new_gen_params = data.data.results;
      $scope.addParamLoad = false;
      $scope.addParamModal = true;
    }, function(){ alert("Error getting new generator parameters"); });
  };
  $scope.saveAddParam = function(){
    $scope.addParamModal = false;
    _.each($scope.new_gen_params, function(key,elem){
      if (elem != "submission_details"){ //ignore: submission details object, angularjs $$hashKey
        $scope.new_gen_params[elem] = parseFloat(key);
      }
    });
    $scope.genParam_data.push($scope.new_gen_params);
  };
  $scope.closeAddParam = function(){
    $scope.addParamModal = false;
  };
};
// NEW for directive
//var testApp = angular.module('testApp', ['ui','ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("inlineEditable", function(){
  return{
      require: 'ngModel',
      template: 
      '<textarea ng-model="whatever_value" ng-change="update()" style="width: 390px; height: 152px;" ng-disabled="not_editable_list.indexOf(formColumn)!=-1">'+
      '</textarea>',
      link: function(scope, element, attr, ctrl){
       
       ctrl.$render = function () {
         scope.whatever_value = JSON.stringify(ctrl.$viewValue, null, 4);
         scope.formColumn = scope.$eval(attr.column);
       }
//        scope.not_editable_list = ["Cmssw release", "Prepid", "Member of campaign", "Reqmgr name", "Pileup dataset name", "Pwg", "Completed events", "Status", "Type", "Priority", "Completion date"]; //user non-editable columns
       scope.update = function () {
         var object = null;
         try{
           object = JSON.parse(scope.whatever_value);
           ctrl.$setViewValue(object);
           ctrl.$setValidity("bad_json", true);
         }catch (err){
           ctrl.$setValidity("bad_json", false);
         }
       }
     }
  }
});
testApp.directive("sequenceEdit", function($http){
  return {
    require: 'ngModel',
    template:
    '<div >'+
    '  <ul ng-switch="dbName">'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-hide="showSequences">'+
    '     <i class="icon-eye-open"></i>'+
    '   </a>'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-show="showSequences">'+
    '     <i class="icon-eye-close"></i>'+
    '   </a>'+
    '  <div ng-switch-when="requests">'+
    '   <div ng-show="showSequences">'+
    '    <li ng-repeat="(sequence_id, sequence) in driver">{{sequence}}'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <a rel="tooltip" title="Edit sequence" ng-click="open(sequence_id);" ng-hide="hideSequence(1)">'+
    '          <i class="icon-wrench"></i>'+
    '        </a>'+
    '        <div modal="shouldBeOpen" close="close()">'+
    '          <div class="modal-header">'+
    '            <h4>Sequence edit modal</h4>'+
    '          </div>'+
    '          <div class="modal-body">'+
    '            <form class="form-horizontal" name="sequenceForm">'+
    '              <div class="control-group" ng-repeat="key in underscore.keys(result.sequences[sequence_id])">'+
    '                <label class="control-label">{{key}}</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="result.sequences[sequence_id][key]">'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="save()">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '          </div>'+
    '       </div>'+
    '      <a rel="tooltip" title="Remove sequence" ng-click="removeSequence($index);" ng-hide="hideSequence(1)">'+
    '        <i class="icon-remove-sign"></i>'+
    '      </a>'+
    '    </li>'+
    '   </div>'+
    '  </div>'+
    '  <div ng-switch-default ng-show="showSequences">'+
    '    <li ng-repeat="(key,value) in driver">'+
    '      <ul>'+
    '        {{key}}'+
    '      </ul>'+
    '      <ul ng-repeat="(name,elem) in value">'+
    ///MODAL
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <li>{{CMSdriver[key][name]}}'+
    '          <a rel="tooltip" title="Edit sequence" ng-click="open($index);" ng-hide="hideSequence(1)">'+
    '            <i class="icon-wrench"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Remove sequence" ng-click="removeSubSequence(key, name);" ng-hide="hideSequence(1)">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '          <div modal="shouldBeOpen" close="close()">'+ //hidden modal template
    '            <div class="modal-header">'+
    '              <h4>Sequence edit modal</h4>'+
    '            </div>'+ //end oFda.f modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal" name="sequenceForm">'+
    '              <div class="control-group" ng-repeat="key in underscore.keys(elem) ">'+
    '                <div ng-switch on="key">'+
    '                  <div ng-switch-when="$$hashKey"></div>'+
    '                  <div ng-switch-default>'+
    '                    <label class="control-label">{{key}}</label>'+
    '                    <div class="controls">'+
    '                      <input type="text" ng-model="elem[key]">'+
    '                    </div>'+
    '                  </div>'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+ //end of modal body
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="save()">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '          </div>'+ //end of modal footer
    '        </li>'+
    '      </div>'+ //end of modalControler DIV
    ///END OF MODAL
    '      </ul>'+
    '        <div ng-controller="ModalDemoCtrl">'+ //add new sub-sequence
    '          <span ng-hide="showAddNewModal">'+
    '          <a rel="tooltip" title="Add new sequence" ng-click="showAddSequencePlus();" ng-hide="hideSequence(1)">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-zoom-in"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Remove sequence" ng-click="removeSequence(key);" ng-hide="hideSequence(1)">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '          </span>'+
    '          <span ng-show="showAddNewModal">'+
    '            <a rel="tooltip" title="Add new sequence" ng-click="openNewSubSequence();" ng-hide="hideSequence(1)">'+ //add sequence
    '              <i class="icon-plus"></i>'+
    '            </a>'+
    '          </span>'+
    '          <div modal="shouldBeOpen" close="close()">'+ //hidden modal template
    '            <div class="modal-header">'+
    '              <h4>Sequence add modal</h4>'+
    '            </div>'+ //end oF  modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal" name="sequenceForm">'+
    '              <div class="control-group">'+
    '                <label class="control-label">Name</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="newSequenceName" name="Name" required>'+
    '                  <span class="error" ng-show="sequenceForm.Name.$error.required">'+
    '                     Required!</span>'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group" ng-repeat="key in underscore.keys(default_sequences)">'+
    '                <div ng-switch on="key">'+
    '                  <div ng-switch-when="$$hashKey"></div>'+
    '                  <div ng-switch-default>'+
    '                    <label class="control-label">{{key}}</label>'+
    '                    <div class="controls">'+
    '                      <input type="text" ng-model="newSequence[key]">'+
    '                    </div>'+
    '                  </div>'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+ //end of modal body
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="saveNewSubform(key)" ng-disabled="sequenceForm.Name.$error.required">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '          </div>'+ //end of modal footer
    '        </div>'+
    '    </li>'+
    '  </div>'+
    '  </ul>'+
    //ADD NEW SEQUENCE MODAL
    '  <div ng-controller="ModalDemoCtrl" ng-show="showSequences">'+ //add new sequence to sequence list
    '  <span ng-hide="showAddNewModal">'+
    '    <a rel="tooltip" title="Add new sequence" ng-click="showAddSequencePlus();" ng-hide="hideSequence(1)">'+ //button to get default sequences, and make plus-sign available
    '      <i class="icon-zoom-in"></i>'+
    '    </a>'+
    '  </span>'+
    '  <span ng-show="showAddNewModal">'+
    '    <a rel="tooltip" title="Add new sequence" ng-click="openNewSubSequence();" ng-hide="hideSequence(1)">'+ //add sequence
    '      <i class="icon-plus"></i>'+
    '    </a>'+
    '  </span>'+
    '  <div modal="shouldBeOpen" close="close()">'+ //hidden modal template
    '    <div class="modal-header">'+
    '      <h4>Sequence add modal</h4>'+
    '    </div>'+ //end oF  modal header
    '    <div class="modal-body">'+
    '      <form class="form-horizontal" name="sequenceForm">'+
    '        <div class="control-group" ng-repeat="key in underscore.keys(default_sequences)">'+
    '          <div ng-switch on="key">'+
    '            <div ng-switch-when="$$hashKey"></div>'+
    '            <div ng-switch-default>'+
    '              <label class="control-label">{{key}}</label>'+
    '              <div class="controls">'+
    '                <input type="text" ng-model="newSequence[key]">'+
    '              </div>'+
    '            </div>'+
    '          </div>'+
    '        </div>'+
    '      </form>'+
    '    </div>'+ //end of modal body
    '    <div class="modal-footer">'+
    '      <button class="btn btn-success" ng-click="saveNewSequence();shouldBeOpen = false;">Save</button>'+
    '      <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '    </div>'+ //end of modal footer
    '  </div>'+
    //end OF MODAL
    '</div>',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){ 
        scope.showSequences = false;
        scope.showAddNewModal = false;
        scope.default_sequences = {};
      };
      scope.removeSequence = function(elem){
        scope.driver.splice(elem,1); //remove sequence from display
        scope.result.sequences.splice(elem,1); //remove the value from original sequences
      };
      scope.removeSubSequence = function(key, name){
        delete scope.driver[key][name];
        if (scope.result.sequences[key] != null){
          delete scope.result.sequences[key][name];
        }
        if (_.keys(scope.driver[key]).length == 1){ //$$hashkey dosent count
          scope.driver.splice(key,1);
          scope.result.sequences.splice(key,1);
        };
      };
      scope.displaySequences = function(){
        if (scope.showSequences){ //if shown then -> HIDE;
          scope.showSequences = false;
        }else{
          scope.showSequences = true; //if hidden -> then display sequences, get the cmsDrivers;
        if(scope.dbName == "requests"){
          if (true || !scope.sequencesOriginal){ //if requests and sequences haven't been requested already
            var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.result.prepid);
            promise.then(function(data){
              scope.driver = data.data.results;
	      // try to evolve the schema at this point ! yes or no ? helps with campaigns editing
	      /*
	      console.log('sequences', scope.result.sequences );
	      var promise2 = $http.get("getDefaultSequences");
	      promise2.then(function(data){
		      console.log('data retreived', data );
		      //and put any new entries of data in the sequence
		      _.each( data.data, function(elem,key){
			      console.log(key, scope.result.sequences[key]);
			      if (scope.result.sequences[key] === undefined ){
				  console.log(key,'adding',elem);
				  scope.result.sequences[key] = elem;
			      }
			      else{
				  console.log(key,'is there already',elem);
			      }
			  });

		      console.log( scope.sequencesOriginal );
		  });
	      */
	      //copy in case one cancels
              scope.sequencesOriginal = _.clone(scope.result.sequences);
              console.log(scope.sequencesOriginal);
            }, function(data){ alert("Error: ", data.status); });
          }
        }else{  //just clone the original sequences -> in case user edited and didnt saved.
          if (true || !scope.sequencesOriginal){ //if requests and sequences haven't been requested already
            var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.result.prepid);
            promise.then(function(data){
              scope.CMSdriver = data.data.results;
              scope.sequencesOriginal = _.clone(scope.result.sequences);
            }, function(data){ alert("Error: ", data.status); });
          }
          scope.sequencesOriginal = _.clone(scope.result.sequences);
          scope.driver = scope.sequencesOriginal;
        }
        scope.sequenceInfo = ctrl.$viewValue;
        scope.sequencesOriginal = _.clone(scope.result.sequences);
        }
      };
      scope.showAddSequencePlus = function(){
        if (scope.showAddNewModal){
          scope.showAddNewModal = false;
        }else{
          scope.showAddNewModal = true;
          if (_.keys(scope.default_sequences).length == 0){ //get default sequences list if it hasn't been already done
            scope.gettingDefaultSequences = true;
            var promise = $http.get("getDefaultSequences");
            promise.then(function(data){
              scope.default_sequences = data.data;
              scope.gettingDefaultSequences = true;
            }, function(){ alert("Error"); });
          }
        }
      };
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
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});
testApp.directive("selectCampaign", function($http){
  return{
      require: 'ngModel',
      template:
      '<div>'+
      '  <a ng-repeat="elem in allowedCampaigns" ng-click="removeAllowedCampaign(elem)">{{elem}}<i class="icon-minus"></i></a>'+ //display allowed campaign list with possibility to remove it
      '</div>'+
      '<a ng-click="displaySelect();" ng-hide="selectACampaign && all_campaigns.length ==1"><i class="icon-plus"></i></a>'+ //options to add a new campaign from available list
      '<select ng-change="allowCampaign();" ng-model="toAllow" ng-options="value for value in all_campaigns" ng-show="selectACampaign && all_campaigns.length !=1"></select>'
      ,
      link: function(scope, element, attr, ctrl){
        ctrl.$render = function () {
          scope.selected_column = attr.value;
          scope.allowedCampaigns = ctrl.$viewValue;
          scope.all_campaigns = _.difference(scope.allCampaigns, scope.allCampaigns);
          scope.all_campaigns.push("------");

        }
        scope.displaySelect = function(){
          var notAllowedlist = _.clone(scope.allowedCampaigns); //get a deepcopy of allowed campaigns
          notAllowedlist.push(scope.result['next_campaign']); // push next campaign so exlude list
          scope.all_campaigns = _.difference(scope.allCampaigns, notAllowedlist); //get only those that are not in allowed campaigns & next_campaign
          scope.all_campaigns.push("------");
          scope.toAllow = "------"; //by default preselected value 
          scope.selectACampaign = true;
        };
        scope.allowCampaign = function(){
          scope.allowedCampaigns.push(scope.toAllow); //push a selected value
          scope.selectACampaign = false;
        }
        scope.removeAllowedCampaign = function(campaign_name){
          scope.allowedCampaigns = _.without(scope.allowedCampaigns, campaign_name);
          scope.result["allowed_campaigns"] = _.without(scope.allowedCampaigns, campaign_name);
          scope.all_campaigns.push(campaign_name);
          // scope.allowedCampaigns.push(campaign_name); //push a selected value
        }
      }
  }
});

testApp.directive("generatorParams", function($http){
  return {
    require: 'ngModel',
    template: 
    '<div ng-controller="genParamModalCtrl">'+
    '  <ul ng-repeat="elem in genParam_data" ng-switch on="$index < genParam_data.length-1">'+
    '    <li ng-switch-when="true">'+ //when not the last element display only wrentch
    '      <a ng-click="openGenParam($index)" ng-hide="not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-wrench"></i></a>'+
        ///MODAL
    '          <div modal="modalOpen" close="closeGenParam($index)">'+ //hidden modal template
    '            <div class="modal-header">'+
    '              <h4>Generator parameters editer</h4>'+
    '            </div>'+ //end of modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal">'+
    '              <div class="control-group">'+
    '                <label class="control-label">Cross section</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.cross_section">'+
    '                  <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.filter_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.filter_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.match_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.match_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+ //end of modal body
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="saveGenParam($index)">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="closeGenParam($index)">Cancel</button>'+
    '          </div>'+ //end of modal footer
    ///END OF MODAL
    '    </li>'+
    '    <li ng-switch-when="false">'+ //when last gen param to be shown
    '      <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;">'+
    '        <dt>{{"cross section"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["cross_section"]}}'+
    '          <a class="label label-info" rel="tooltip" title="pico barn" ng-hre="#">pb</a>'+
    '        </dd>'+
    '        <dt>{{"filter efficiency"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["filter_efficiency"]}}</dd>'+
    '        <dt>{{"filter efficiency error"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["filter_efficiency_error"]}}</dd>'+
    '        <dt>{{"match efficiency"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["match_efficiency"]}}</dd>'+
    '        <dt>{{"match efficiency error"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["match_efficiency_error"]}}</dd>'+
    '        <dt>{{"author username"}}</dt>'+
    '        <dd class="clearfix">{{genParam_data[$index]["submission_details"]["author_username"]}}</dd>'+
    '      </dl>'+
    '      <a ng-click="openGenParam($index)" ng-hide="not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-wrench"></i></a>'+
    '          <div modal="modalOpen" close="closeGenParam($index)">'+ //hidden modal template
    '            <div class="modal-header">'+
    '              <h4>Generator parameters editer</h4>'+
    '            </div>'+ //end of modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal">'+
    '              <div class="control-group">'+
    '                <label class="control-label">Cross section</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.cross_section">'+
    '                  <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.filter_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.filter_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.match_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="modal_data.match_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+ //end of modal body
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="saveGenParam($index)">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="closeGenParam($index)">Cancel</button>'+
    '          </div>'+ //end of modal footer
    '    </li>'+
    '  </ul>'+
    '      <a ng-click="openAddParam()" ng-hide="addParamLoad || not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-plus"></i></a>'+
    '      <img ng-show="addParamLoad" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '      <div modal="addParamModal" close = "closeAddParam()">'+
    '            <div class="modal-header">'+
    '              <h4>Add Generator parameters</h4>'+
    '            </div>'+ //end of modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal">'+
    '              <div class="control-group">'+
    '                <label class="control-label">Cross section</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="new_gen_params.cross_section">'+
    '                  <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="new_gen_params.filter_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Filter efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="new_gen_params.filter_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="new_gen_params.match_efficiency">'+
    '                </div>'+
    '              </div>'+
    '              <div class="control-group">'+
    '                <label class="control-label">Match efficiency error</label>'+
    '                <div class="controls">'+
    '                  <input type="text" ng-model="new_gen_params.match_efficiency_error">'+
    '                </div>'+
    '              </div>'+
    '            </form>'+
    '          </div>'+ //end of modal body
    '          <div class="modal-footer">'+
    '            <button class="btn btn-success" ng-click="saveAddParam()">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="closeAddParam()">Cancel</button>'+
    '          </div>'+ //end of modal footer
    ///END OF MODAL
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.genParam_data = ctrl.$viewValue;
      };
    }
  }
});
testApp.directive("customValidationEdit", function(){
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template: 
    '<div ng-switch on="dbName">'+
    '  <form ng-switch-when="requests">'+
    '    <fieldset>'+
    '      <div class="control-group">'+
    '        Valid:'+
    '        <input type="checkbox" ng-disabled="disabled"  ng-model="validation_data.valid" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1"></input>'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.valid">'+
    '        nEvents:'+
    '        <input type="number" ng-disabled="disabled"  ng-model="validation_data.nEvents" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1"></input>'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.dqm">'+
    '        DQM:'+
    '        <a ng-show="isDevMachine()" href="https://cmsweb-testbed.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '        <a ng-show="!isDevMachine()" href="https://cmsweb.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '      </div>'+
    '    </fieldset>'+
    '  </form>'+
    '  <input type="text" ng-switch-default ng-model="validation_data" style="width: 390px; height: 20px; margin-bottom: 0px;" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1"></input>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.validation_data = ctrl.$viewValue;
      };
      scope.$watch("validation_data.nEvents", function(elem){ //watch nEvents -> is user leaves empty remove nEvents, as not to save null
        if (!elem){
          delete(scope.validation_data.nEvents);
        }
      });

      scope.$watch(function(){
            return scope.$eval(attr.ngDisabled);
        }, function(newVal){
            scope.disabled = newVal
      })
    }
  }
});
testApp.directive("customAnalysisId", function(){
  return {
    replace: false,
    restrict: 'E',   
    require: 'ngModel',
    template: 
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in analysis_data">'+
    '     <span ng-hide="editable[$index]">'+
    '       {{elem}}'+
    '     </span>'+
    '     <span ng-show="editable[$index]">'+
    '       <input ng-model="new_id" ng-disabled="not_editable_list.indexOf(\'Analysis id\')!=-1"></input>'+
    '       <a ng-click="save($index, new_id)">'+
    '         <i class="icon-plus-sign"></i>'+
    '       </a>'+
    '       <a ng-click="edit($index)">'+
    '         <i class="icon-minus"></i>'+
    '       </a>'+
    '     </span>'+
    '     <span ng-hide="editable[$index]">'+
    '       <a ng-click="edit($index)" ng-hide="not_editable_list.indexOf(\'Analysis id\')!=-1">'+
    '         <i class="icon-wrench"></i>'+
    '       </a>'+
    '       <a ng-click="remove($index)" ng-hide="not_editable_list.indexOf(\'Analysis id\')!=-1">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(\'Analysis id\')!=-1">'+
    '      <a ng-click="toggleAddNewAnalysisID()">'+
    '        <i class="icon-plus" ng-hide="add_analysis_id"></i>'+
    '        <i class="icon-minus" ng-show="add_analysis_id"></i>'+
    '      </a>'+
    '      <input type="text" ng-model="new_analysis_id" ng-show="add_analysis_id"></i>'+
    '      <i class="icon-plus-sign" ng-click="pushNewAnalysisID()" ng-show="add_analysis_id"></i>'+
    '    </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.analysis_data = ctrl.$viewValue;
        scope.new_analysis_id = "";
        scope.editable = {};
        scope.new_id = "";
      };
      scope.toggleAddNewAnalysisID = function(){
        if(scope.add_analysis_id)
        {
          scope.add_analysis_id = false;
        } else
        {
           scope.add_analysis_id = true;
        }
      };
      scope.edit = function(elem){
        if(scope.editable[elem])
        {
          scope.editable[elem] = false;
        }else
        {
          scope.editable[elem] = true;
        }
        scope.new_id = scope.analysis_data[elem];
      };
      scope.save = function(index, new_id){
        scope.analysis_data[index] = new_id;
        scope.editable[index] = false;
      }
      scope.remove = function(index){
        scope.analysis_data.splice(index,1);
      }
      scope.pushNewAnalysisID = function(){
        scope.analysis_data.push(scope.new_analysis_id);
        scope.add_analysis_id = false;
        scope.new_analysis_id = "";
      };
    }
  }
});