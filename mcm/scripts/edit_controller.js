function resultCtrl($scope, $http, $location, $window){

    $scope.defaults = [];
    $scope.underscore = _;
    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];

    $scope.dbName = $location.search()["db_name"];
    $scope.prepid = $location.search()["prepid"];
    if ($scope.prepid === undefined){
      $scope.prepid = $location.search()["query"];
    }

    switch($scope.dbName)
    {
      case "campaigns":
        $scope.not_editable_list = ["Prepid", "Member of campaign","Completed events", "Status","Approval","Next", "Total events"];
        $scope.type_list = ["MCReproc","Prod","LHE"];
        break;
      case "requests":
        $scope.not_editable_list = ["Cmssw release", "Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version"]; //user non-editable columns
        var promise = $http.get("restapi/requests/editable/"+$scope.prepid)
        promise.then(function(data){
          $scope.parseEditableObject(data.data.results);
        });
        break;
      case "chained_requests":
        $scope.not_editable_list = ["Prepid", "Chain","Approval","Member of campaign","Pwg"];
        break;
      case "chained_campaigns":
        $scope.not_editable_list = ["Prepid", "Campaigns"];
        break;
      case "flows":
        $scope.not_editable_list = ["Prepid", "Approval"];
        var promise = $http.get("restapi/campaigns/listall"); //get list of all campaigns for flow editing
          promise.then(function(data){
          $scope.allCampaigns = data.data.results;
        },function(){
          alert("Error getting all campaign list for flows");
        });
        break;
      case "news":
        $scope.not_editable_list = ["Author", "Date"];
        break;
      case "settings":
        $scope.not_editable_list = ["Prepid"];
        break;
      case "users":
        $scope.not_editable_list = ["Username", "Role"];
        break;
      case "mccms":
	      $scope.not_editable_list = ["Prepid", "Pwg"];
        var promise = $http.get("restapi/mccms/editable/"+$scope.prepid)
        promise.then(function(data){
          $scope.parseEditableObject(data.data.results);
        });
        break;
      default:
        $scope.not_editable_list = [];
        break;
    }

    if($location.search()["page"] === undefined){
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else{
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
          }
        }
      });
    };
    
    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          alert('Object was deleted successfully.');
        }else{
          alert('Could not save data to database.');
        }
      }).error(function(status){
        alert('Error no.' + status + '. Could not delete object.');
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

    function isInt(n) {
       return typeof n === 'number' && n % 1 == 0;
    }

    function parseSettingValue (string_value) {
        if(!isNaN(string_value)) {
            return +string_value
        } else {
            switch(string_value.toLowerCase()){
            case "true":
              return true;
            case "false":
              return false;
            default:
              break;
          }
        }
        return string_value
    }

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
         $scope.result["time_event"] = parseFloat($scope.result["time_event"]);
         $scope.result["size_event"] = parseFloat($scope.result["size_event"]);
         $scope.result["memory"] = parseFloat($scope.result["memory"]);
         $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
  //$scope.listify_blocks();
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
      $http({method:'PUT', url:'restapi/'+$location.search()["db_name"]+'/update',data:angular.toJson($scope.result)}).success(function(data,status){
        $scope.update["success"] = data["results"];
        $scope.update["fail"] = false;
        $scope.update["message"] = data["message"];
        $scope.update["status_code"] = status;
        if ($scope.update["success"] == false){
          $scope.update["fail"] = true;
        }else{
          $scope.getData();
        }
      }).error(function(data,status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    $scope.delete_edit = function(id){
      $scope.delete_object($location.search()["db_name"], id);
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
}
var ModalDemoCtrl = function ($scope, $modal) {
  $scope.openSequenceEdit = function (seq1, seq2, number) {
    $scope.sequenceToShow = [];
    $scope.sequenceHidden = [];
    var sequences = {};
    _.each($scope.dbName == "requests" ? $scope.result.sequences[number] : $scope.result.sequences[seq1][seq2], function(value,key){
        if (! _.isEmpty(value) || _.isBoolean(value) || _.isNumber(value)) {
          $scope.sequenceToShow.push(key);
        } else {
          $scope.sequenceHidden.push(key);
        }
        sequences[key]=value;
    });
    //sort both lists ???
    $scope.sequenceHidden.sort();
      var sequenceEditModal = $modal.open({
          templateUrl: 'sequenceEditModal.html',
          controller: SequenceEditModalInstanceCtrl,
          resolve: {
              sequenceHidden: function() {
                  return $scope.sequenceHidden;
              },
              sequenceToShow: function() {
                  return $scope.sequenceToShow;
              },
              selectedHidden: function() {
                  return $scope.sequenceHidden[0];
              },
              sequences: function() {
                  return sequences;
              }
          }
      });
      sequenceEditModal.result.then(function(newSequence) {
         if( $scope.dbName == "requests") {
            $scope.result.sequences[number] = newSequence; // we should somehow change driver shown as well
         } else {
            $scope.result.sequences[seq1][seq2] = newSequence;
         }
      });
  };

  $scope.openNewSequence = function(define_name, index) {
      var sequenceAddModal = $modal.open({
          templateUrl: 'sequenceAddModal.html',
          controller: SequenceAddModalInstanceCtrl,
          resolve: {
              define_name: function() {
                  return define_name;
              },
              defaultSequence: function() {
                  return _.clone($scope.default_sequences);
              }
          }
        });
      sequenceAddModal.result.then(function(data) {
          if($scope.dbName == "requests") {
              $scope.drivers.push(data.sequence);
              $scope.result.sequences.push(data.sequence);
          } else {
              if(!define_name) {
                $scope.drivers[_.size($scope.result.sequences)] = {default: data.sequence};
                $scope.result.sequences[_.size($scope.result.sequences)] = {default: data.sequence};
              } else {
                $scope.drivers[index][data.name] = data.sequence;
                $scope.result.sequences[index][data.name] = data.sequence;
              }
          }
      })
  };

  $scope.isBoolean = function(value){
    return angular.isBoolean(value);
  };


};

var SequenceAddModalInstanceCtrl = function($scope, $modalInstance, define_name, defaultSequence) {
    $scope.define_name = define_name;
    $scope.sequences = {
        newSequenceName: "",
        newSequence: defaultSequence
    };

    $scope.save = function() {
        $modalInstance.close({name: $scope.sequences.newSequenceName, sequence: $scope.sequences.newSequence});
    };

    $scope.close = function() {
        $modalInstance.dismiss();
    }
};

var SequenceEditModalInstanceCtrl = function($scope, $modalInstance, sequences, selectedHidden, sequenceToShow, sequenceHidden) {
    $scope.sequence = {
        toShow: sequenceToShow,
        hidden: sequenceHidden,
        selectedHidden: selectedHidden,
        sequences: sequences
    };

    $scope.showHiddenSequence = function() {
        $scope.sequence.toShow.push($scope.sequence.selectedHidden);
        $scope.sequence.hidden.splice($scope.sequence.hidden.indexOf($scope.sequence.selectedHidden), 1);
        $scope.sequence.selectedHidden = $scope.sequence.hidden[0];
    };
    $scope.close = function() {
        $modalInstance.dismiss();
    };
    $scope.save = function() {
        $modalInstance.close($scope.sequence.sequences);
    }
};

var genParamModalCtrl = function($scope, $http, $modal) {

  $scope.showData = {
      "Cross section": "cross_section",
      "Filter efficiency": "filter_efficiency",
      "Filter efficiency error": "filter_efficiency_error",
      "Match efficiency": "match_efficiency",
      "Match efficiency error": "match_efficiency_error"
  };

  $scope.openGenParam = function(action, index) {
      var data = [];
      if(action == "Edit") {
          data = $scope.genParam_data[index];
      } else {
          data = $scope.defaultGenParams;
      }
    var genParamModal = $modal.open({
      templateUrl: 'generatorParamsModal.html',
      controller: GeneratorParamsInstandeModal,
      resolve: {
          data: function() {
              return _.clone(data);
          },
          action: function() {
              return action;
          },
          showData: function() {
              return $scope.showData;
          }
      }
    });
    genParamModal.result.then(function(new_gen_params) {
        _.each(new_gen_params, function(elem,key){
          if (_.isString(elem) && key !="$$hashKey"){
            new_gen_params[key] = parseFloat(elem);
          }
        });
        if(action == "Edit") {
            _.each(new_gen_params, function(elem,key){
              if (!isNaN(elem)){
                $scope.genParam_data[index][key] = elem;
              }
            });
        } else { // Add
            $scope.genParam_data.push(new_gen_params);
        }
    });

  };

};

var GeneratorParamsInstandeModal = function($scope, $modalInstance, data, action, showData) {
    $scope.action = action;
    $scope.gen_params = {
        data: data,
        show: showData
    };
    $scope.closeGenParam = function() {
        $modalInstance.dismiss();
    };

    $scope.saveGenParam = function() {
        $modalInstance.close($scope.gen_params.data);
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
       };
       scope.update = function () {
         var object = null;
         try{
           object = JSON.parse(JSON.stringify(scope.whatever_value));
           ctrl.$setViewValue(angular.fromJson(object));
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
    '  <script type="text/ng-template" id="sequenceEditModal.html">'+ // Edit sequence modal template
    '     <div class="modal-header">'+
    '       <h4>Edit sequence</h4>'+
    '     </div>'+
    '     <div class="modal-body">'+
    '       <form class="form-horizontal" name="sequenceForm">'+
    '         <div class="control-group" ng-repeat="key in sequence.toShow">'+
    '          <div ng-if="key!=$$hashkey">'+
    '           <label class="control-label">{{key}}</label>'+
    '             <input type="text" ng-model="sequence.sequences[key]">'+
    '          </div>' +
    '         </div>'+
    '       </form>'+
    '     </div>'+
    '     <div class="modal-footer">'+
    '       <div class="span3 input-append" style="text-align:left;">'+
    '         <select ng-model="sequence.selectedHidden" ng-show="sequence.hidden.length > 0">'+
    '           <option ng-repeat="elem in sequence.hidden">{{elem}}</option>'+
    '         </select>'+
    '         <a class="btn" ng-click="showHiddenSequence();" ng-href="#" ng-show="sequence.hidden.length > 0"><i class="icon-plus-sign"></i></a>'+
    '       </div>'+
    '       <div class="span2">'+
    '         <button class="btn btn-success" ng-click="save()">Save</button>'+
    '         <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '       </div>'+
    '     </div>'+
    '  </script>'+
    '  <script type="text/ng-template" id="sequenceAddModal.html">'+ //Add sequence modal template
    '    <div class="modal-header">'+
    '      <h4>Add sequence</h4>'+
    '    </div>'+ //end oF  modal header
    '    <div class="modal-body">'+
    '      <form class="form-horizontal" name="sequenceForm">'+
    '        <div class="control-group" ng-if="define_name">'+
    '          <label class="control-label">Name</label>'+
    '          <div class="controls">'+
    '            <input type="text" ng-model="sequences.newSequenceName" name="Name" required>'+
    '            <span class="error" ng-show="sequenceForm.Name.$error.required">'+
    '               Required!</span>'+
    '          </div>'+
    '        </div>'+
    '        <div class="control-group" ng-repeat="(key, value) in sequences.newSequence">'+
    '          <div ng-if="key!=$$hashKey">'+
    '            <label class="control-label">{{key}}</label>'+
    '            <div class="controls">'+
    '              <input type="text" ng-model="sequences.newSequence[key]">'+
    '            </div>'+
    '          </div>'+
    '      </form>'+
    '    </div>'+ //end of modal body
    '    <div class="modal-footer">'+
    '      <button class="btn btn-success" ng-click="save()" ng-disabled="sequenceForm.Name.$error.required">Save</button>'+
    '      <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '    </div>'+ //end of modal footer
    '  </script>'+
    '  <ul ng-switch="dbName">'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-hide="showSequences" ng-href="#">'+
    '     <i class="icon-eye-open"></i>'+
    '   </a>'+
    '   <a rel="tooltip" title="Display sequences" ng-click="displaySequences();" ng-show="showSequences" ng-href="#">'+
    '     <i class="icon-eye-close"></i>'+
    '   </a>'+
    '  <div ng-switch-when="requests" ng-show="showSequences">'+
    '    <li ng-repeat="(sequence_id, sequence) in drivers">{{sequence}}'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <a rel="tooltip" title="Edit sequence" ng-click="openSequenceEdit(\'\',\'\',sequence_id);" ng-hide="hideSequence(1);" ng-href="#">'+
    '          <i class="icon-wrench"></i>'+
    '        </a>'+
    '        <a rel="tooltip" title="Remove sequence" ng-click="removeSequence($index);" ng-hide="hideSequence(1);" ng-href="#">'+
    '          <i class="icon-remove-sign"></i>'+
    '        </a>'+
    '    </li>'+
    '  </div>'+
    '  <div ng-switch-default ng-show="showSequences">'+
    '    <li ng-repeat="(key,value) in result.sequences">'+
    '      <ul>'+
    '        {{key}}'+
    '      </ul>'+
    '      <ul ng-repeat="(name,elem) in value">'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <li>{{drivers[key][name]}}'+
    '          <a rel="tooltip" title="Edit sequence" ng-click="openSequenceEdit(key,name,$index);" ng-hide="hideSequence(1);" ng-href="#">'+
    '            <i class="icon-wrench"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Remove subsequence" ng-click="removeSubSequence(key, name);" ng-hide="hideSequence(1);" ng-href="#">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '        </li>'+
    '      </div>'+ //end of modalControler DIV
    '      </ul>'+
    '        <div ng-controller="ModalDemoCtrl">'+
    '          <a rel="tooltip" title="Remove sequence" ng-click="removeSequence(key);" ng-hide="hideSequence(1);" ng-href="#">'+ //button to get default sequences, and make plus-sign available
    '            <i class="icon-remove-sign"></i>'+
    '          </a>'+
    '          <a rel="tooltip" title="Add new subsequence" ng-click="openNewSequence(true, $index);" ng-hide="hideSequence(1);" ng-href="#">'+ //add sequence
    '            <i class="icon-plus"></i>'+
    '          </a>'+
    '        </div>'+
    '    </li>'+
    '  </div>'+
    '  </ul>'+
    '  <div ng-controller="ModalDemoCtrl" ng-show="showSequences">'+ //add new sequence to sequence list
    '    <a rel="tooltip" title="Add new sequence" ng-click="openNewSequence(false);" ng-hide="hideSequence(1);" ng-href="#">'+ //add sequence
    '      <i class="icon-plus"></i>'+
    '    </a>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.showSequences = false;
        scope.showAddNewModal = false;
        scope.default_sequences = {};
        scope.sequenceToShow = [];
        scope.sequenceHidden = [];
        scope.alreadyShown = false;
      };
      scope.removeSequence = function(elem){
        scope.result.sequences.splice(elem, 1); //remove the value from original sequences
        scope.drivers.splice(elem, 1);
      };
      scope.removeSubSequence = function(key, name){
        if (scope.result.sequences[key] != null){
          delete scope.result.sequences[key][name];
          delete scope.drivers[key][name];
        }
        if (_.keys(scope.result.sequences[key]).length == 1){ //$$hashkey dosent count
          scope.result.sequences.splice(key,1);
          scope.drivers.splice(key, 1);
        }
      };
      scope.displaySequences = function(){
        if (scope.showSequences){ //if shown then -> HIDE;
          scope.showSequences = false;
        } else {
          scope.showSequences = true; //if hidden -> then display sequences, get the cmsDrivers;
          if(!scope.alreadyShown) {
               var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.result.prepid);
                promise.then(function(data){
                    scope.drivers = data.data.results;

                }, function(data){
                    alert("Error: " + data.status);
                });
               var promise2 = $http.get("getDefaultSequences");
              promise2.then(function(data) {
                  scope.default_sequences = data.data;
              }, function() {
                  alert("Error getting default sequences");
              });
              scope.alreadyShown = true;
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
        ///MODAL
    '  <script  type="text/ng-template" id="generatorParamsModal.html">'+ //hidden modal template
    '    <div class="modal-header">'+
    '      <h4>{{action}} generator parameters</h4>'+
    '    </div>'+ //end of modal header
    '    <div class="modal-body">'+
    '      <form class="form-horizontal">'+
    '        <div ng-repeat="(key, value) in gen_params.show" class="control-group">'+
    '          <label class="control-label">{{key}}</label>'+
    '          <div class="controls">'+
    '            <input type="text" ng-model="gen_params.data[value]">'+
    '            <a ng-if="key==\'Cross section\'" class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '          </div>'+
    '        </div>'+
    '      </form>'+
    '    </div>'+ //end of modal body
    '    <div class="modal-footer">'+
    '      <button class="btn btn-success" ng-click="saveGenParam()">Save</button>'+
    '      <button class="btn btn-warning cancel" ng-click="closeGenParam()">Cancel</button>'+
    '    </div>'+ //end of modal footer
    '  </script>'+///END OF MODAL
    '  <ul ng-repeat="elem in genParam_data">'+
    '    <li>'+ //when not the last element display only wrench
    '      <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;" ng-if="$index==genParam_data.length-1">'+
    '        <dt ng-repeat-start="(key, value) in showData">{{key.toLowerCase()}}</dt>'+
    '        <dd ng-repeat-end class="clearfix">{{elem[value]}}'+
    '          <a ng-if="key==\'Cross section\'" class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '        </dd>'+
    '        <dt>author username</dt>'+
    '        <dd class="clearfix">{{elem["submission_details"]["author_username"]}}</dd>'+
    '      </dl>'+
    '      <a ng-click="openGenParam(\'Edit\', $index)" ng-hide="not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-wrench"></i></a>'+
    '    </li>'+
    '  </ul>'+
    '      <a ng-click="openGenParam(\'Add\')" ng-hide="addParamLoad || not_editable_list.indexOf(\'Generator parameters\')!=-1"><i class="icon-plus"></i></a>'+
    '      <img ng-show="addParamLoad" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.genParam_data = ctrl.$viewValue;
        scope.defaultGenParams = [];
      };

        scope.addParamLoad = true;
        var promise = $http.get("restapi/"+ scope.dbName+"/default_generator_params/"+scope.result["prepid"]);
        promise.then(function(data){
          scope.defaultGenParams = data.data.results;
            scope.addParamLoad = false;
        }, function(){
          alert("Error getting default generator parameters");
        });
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
    '        <input ng-disabled="disabled" type="checkbox" ng-model="validation_data.valid">'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.valid">'+
    '        nEvents:'+
    '        <input ng-disabled="disabled"  type="number" ng-model="validation_data.nEvents">'+
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
    '  <input type="text" ng-switch-default ng-model="validation_data" style="width: 390px; height: 20px; margin-bottom: 0px;">'+
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
    '       <input type="text" ng-model="new_id" class="input-xxlarge">'+
    '       <a ng-click="save($index, new_id)">'+
    '         <i class="icon-plus-sign"></i>'+
    '       </a>'+
    '       <a ng-click="edit($index)">'+
    '         <i class="icon-minus"></i>'+
    '       </a>'+
    '     </span>'+
    '     <span ng-hide="editable[$index]">'+
    '       <a ng-click="edit($index)" ng-hide="not_editable_list.indexOf(formColumn)!=-1">'+
    '         <i class="icon-wrench"></i>'+
    '       </a>'+
    '       <a ng-click="remove($index)" ng-hide="not_editable_list.indexOf(formColumn)!=-1">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(formColumn)!=-1">'+
    '      <a ng-click="toggleAddNewAnalysisID()">'+
    '        <i class="icon-plus" ng-hide="add_analysis_id"></i>'+
    '        <i class="icon-minus" ng-show="add_analysis_id"></i>'+
    '      </a>'+
    '      <input type="text" ng-model="new_analysis_id" ng-show="add_analysis_id" class="input-xxlarge"></i>'+
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
        scope.formColumn = scope.$eval(attr.column);
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
testApp.directive("customRequestsEdit", function($http, $rootScope){
  return {
    require: 'ngModel',
    replace: true,
    restrict: 'E',
    template: 
    '<div>'+
    '  <ul>'+
    '    <li ng-repeat="elem in requests_data">'+
    '      <span ng-switch on="underscore.isArray(elem)">'+
    '        <span ng-switch-when="true">'+
    '        {{elem[0]}} <i class="icon-arrow-right"></i> {{elem[1]}}'+
    '          <a ng-href="#" ng-click="removeOldRequest($index)" rel="tooltip" title="Remove last from list"><i class="icon-minus"></i></a>'+
    '        </span>'+
    '        <span ng-switch-when="false">'+
    '          {{elem}}'+
    '          <a ng-href="#" ng-click="removeOldRequest($index)" ng-hide="show_new[$index] || not_editable_list.indexOf(\'Requests\')!=-1" rel="tooltip" title="Remove itself" ><i class="icon-minus"></i></a>'+
    '          <a ng-href="#" ng-click="addNewRequest($index)" ng-hide="show_new[$index] || not_editable_list.indexOf(\'Requests\')!=-1" rel="tooltip" title="Add new"><i class="icon-plus"></i></a>'+
    '          <a ng-href="#" ng-click="toggleNewRequest($index)" ng-show="show_new[$index]" rel="tooltip" title="Close input"><i class="icon-minus-sign"></i></a>'+
    '          <input type="text" ng-model="tmpRequest[$index]" ng-show="show_new[$index]" typeahead="id for id in possible_sub_requests[$index] | filter: $viewValue | limitTo: 10">'+
    '          <a ng-href="#" ng-click="saveNewRequest($index)" ng-show="show_new[$index]"><i class="icon-plus-sign" rel="tooltip" title="Add id to list"></i></a>'+
    '          <font color="red" ng-show="bad_sub_request">Wrong request</font>'+
    '        </span>'+
    '      </span>'+
    '    </li>'+
    '  </ul>'+
    '  <a ng-href="#" ng-click ="toggleNewRequest(\'new\')" ng-hide="show_new[\'new\'] || not_editable_list.indexOf(\'Requests\')!=-1"><i class="icon-plus"></i></a>'+
    '  <a ng-href="#" ng-click="toggleNewRequest(\'new\')" ng-show="show_new[\'new\']"><i class="icon-minus-sign"></i></a>'+
    '  <input type="text" ng-model="tmpRequest[\'new\']" ng-show="show_new[\'new\']" typeahead="id for id in possible_requests | filter: $viewValue | limitTo: 10">'+
    '  <a ng-href="#" ng-click="pushNewRequest()" ng-show="show_new[\'new\']"><i class="icon-plus-sign"></i></a>'+
    '  <font color="red" ng-show="bad_request">Wrong request</font>'+
    '</div>'+
    '',
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.requests_data = ctrl.$viewValue;
        scope.show_new = {};
        scope.tmpRequest = {};
        scope.possible_requests = [];
        scope.campaign_name = "";
        scope.bad_request = false;
        scope.bad_sub_request = false;
        scope.possible_sub_requests = {};
        if (scope.requests_data.length != 0)
        {
          switch(_.isArray(scope.requests_data[0])){
            case true:
              scope.campaign_name = scope.requests_data[0][0].split("-")[1];
              break;
            default:
              scope.campaign_name = scope.requests_data[0].split("-")[1];
              break;
          };
        scope.preloadRequests(scope.campaign_name);
        $rootScope.$broadcast('loadChains', scope.campaign_name);
        }else{
          scope.preloadAllRequests();
        };
      };
      scope.toggleNewRequest = function (elem)
      {
        if(scope.show_new[elem] == true)
        {
          scope.show_new[elem] = false;
        }else
        {
          scope.show_new[elem] = true;
        }
      };
      scope.addNewRequest = function (elem)
      {
        scope.toggleNewRequest(elem);
        scope.possible_sub_requests[elem] = [];
        var __pwg = scope.requests_data[elem].split("-")[0];
        _.each(scope.possible_requests, function (el)
        {
          if (el.split('-')[0] == __pwg)
          {
            scope.possible_sub_requests[elem].push(el);
          }
        });
      };
      scope.saveNewRequest = function (index)
      {
        if (scope.possible_sub_requests[index].indexOf(scope.tmpRequest[index]) == -1)
        {
          scope.bad_sub_request = true;
        }else{
          scope.bad_sub_request = false;
          var __request = scope.requests_data[index];
          scope.requests_data[index] = [];
          scope.requests_data[index].push(__request); 
          scope.requests_data[index].push(scope.tmpRequest[index]);
          scope.show_new[__request] = false;
        }
      };
      scope.pushNewRequest = function()
      {
        var preload = false;
        if (scope.possible_requests.indexOf(scope.tmpRequest["new"]) == -1)
        {
          scope.bad_request = true;
        }else{
          if (scope.requests_data.length == 0)
          {
            preload = true;
          }
          scope.bad_request = false;
          scope.requests_data.push(scope.tmpRequest["new"]);
          scope.toggleNewRequest('new');
          scope.campaign_name = scope.tmpRequest["new"].split("-")[1];
          scope.tmpRequest["new"] = "";
          $rootScope.$broadcast('refreshChains', scope.campaign_name);
        }
        if (preload)
        {
          var parsed_campaign = scope.requests_data[0].split("-")[1];
          scope.preloadRequests(parsed_campaign);
        };
      };
      scope.removeOldRequest = function (index)
      {
        if (_.isArray(scope.requests_data[index]))
        {
          scope.requests_data[index] = scope.requests_data[index][0]
        }else
        {
          scope.requests_data.splice(index,1);
        }
        scope.show_new[index] = false;
        if (scope.requests_data.length == 0)
        {
          if (scope.result['chains'].length == 0)
          {
            scope.preloadAllRequests();
            $rootScope.$broadcast('refreshChains', "_");
          }else
          {
            var parsed_campaign = scope.result['chains'][0].split("_")[1];
            scope.preloadRequests(parsed_campaign);
          };
        };
      };
      scope.preloadRequests = function (id)
      {
        if (scope.requests_data.length != 0)
        {
          id = scope.campaign_name;
        };
        var promise = $http.get("restapi/requests/search_view/member_of_campaign/" + id);
        promise.then(function(data){
          scope.possible_requests = data.data.results;
        }, function(data){
          alert("Error getting list of possible requests: " + data.data);
        });
      };
      scope.preloadAllRequests = function ()
      {
        var promise = $http.get("restapi/requests/search_view/all");
        promise.then(function(data){
          scope.possible_requests = data.data.results;
        }, function(data){
          alert("Error getting list of possible requests: " + data.data);
        });
      };

      scope.$on('loadRequests', function(event, chain){
        scope.preloadRequests(chain);
      });
    }
  }
});
testApp.directive("customMccmChains", function($http, $rootScope){
  return {
    replace: false,
    restrict: 'E',   
    require: 'ngModel',
    template: 
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in chain_data">'+
    '     <span>'+
    '       {{elem}}'+
    '       <a ng-href="#" ng-click="remove($index)" ng-hide="not_editable_list.indexOf(\'Chains\')!=-1">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(\'Chains\')!=-1">'+
    '      <a ng-href="#" ng-click="toggleAddNewChain();">'+
    '        <i class="icon-plus" ng-hide="add_chain"></i>'+
    '        <i class="icon-minus" ng-show="add_chain"></i>'+
    '      </a>'+
    '      <select ng-model="new_chain" ng-show="add_chain" class="input-xxlarge" ng-options="elem as alias_map[elem] for elem in list_of_chained_campaigns"></select>'+
    '      <a ng-href="#">'+
    '        <i class="icon-plus-sign" ng-click="pushNewMcMChain()" ng-show="add_chain"></i>'+
    '      </a>'+
    '    </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.chain_data = ctrl.$viewValue;
        if (scope.chain_data.length != 0)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
          if (scope.result['requests'].length == 0)
          {
            $rootScope.$broadcast('loadRequests', scope.root_campaign);
          }
        }else{
          scope.root_campaign = "_";
        }
        scope.new_chain = "";
        scope.list_of_chained_campaigns = [];
        scope.alias_map = {};
        scope.original_chain_list = [];
        scope.getChains(scope.root_campaign);
      };
      scope.toggleAddNewChain = function(){
        if(scope.add_chain)
        {
          scope.add_chain = false;
        }else{
          scope.add_chain = true;
        }
      };
      scope.getChains = function(root_campaign)
      {
        if (scope.list_of_chained_campaigns.length == 0)
        {
		      var promise = $http.get("search/?db_name=chained_campaigns&valid=true&page=-1");
          promise.then(function (data) {
            _.each(data.data.results, function (elem) {
              if (elem.alias != "") //lets construct alais map
              {
                scope.alias_map[elem.prepid] = elem.alias;
                scope.alias_map[elem.alias] = elem.prepid;
              }else{
                scope.alias_map[elem.prepid] = elem.prepid;
              }
              scope.original_chain_list.push(elem.prepid);
              if (elem.prepid.split("_")[1] == root_campaign)
              {
                if (scope.chain_data.indexOf(elem.prepid) == -1) //add only if its not already in chains -> in chain we display normal prepid no fcking ALIAS
                {
                  scope.list_of_chained_campaigns.push(elem.prepid);
                }
              }else if (root_campaign == "_")
              {
                scope.list_of_chained_campaigns.push(elem.prepid);
              }
            }, function(data){
              alert("Error getting chained campaigns: " + data);
            });
            scope.list_of_chained_campaigns = _.uniq(scope.list_of_chained_campaigns);
            scope.original_chain_list = _.uniq(scope.original_chain_list);
            scope.list_of_chained_campaigns.sort(); //sort list to be in ascending order
            scope.new_chain = scope.list_of_chained_campaigns[0];
          });
        }
      };
      scope.remove = function(index){
        //scope.list_of_chained_campaigns.push(scope.chain_data[index]);
        scope.chain_data.splice(index,1);
        if (scope.chain_data.length != 0)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
        }else{
          scope.root_campaign = "_";
          $rootScope.$broadcast('loadRequests', "");
        }
        scope.list_of_chained_campaigns = scope.original_chain_list;
        scope.parseRootChains();
      }
      scope.pushNewMcMChain = function()
      {
        scope.chain_data.push(scope.alias_map[scope.new_chain]);
        if (scope.chain_data[0].indexOf('_') != -1)
        {
          scope.root_campaign = scope.chain_data[0].split('_')[1];
        }else
        {
          scope.root_campaign = scope.alias_map[scope.chain_data[0]].split('_')[1];
        }
        $rootScope.$broadcast('loadRequests', scope.root_campaign);
        scope.list_of_chained_campaigns.splice(scope.list_of_chained_campaigns.indexOf(scope.new_chain), 1); //lets remove not to duplicate
        //scope.add_chain = false; //uncomment if we cant to close select field after each new chain_campaign addition
        scope.parseRootChains();
        scope.new_chain = scope.list_of_chained_campaigns[0];
      };
      scope.parseRootChains = function ()
      {
        var to_remove = [];
        _.each(scope.list_of_chained_campaigns, function (elem, index)
        {
          if (elem.split("_")[1] != scope.root_campaign)
          {
            to_remove.push(elem);
          }
        });
        if (scope.root_campaign != "_"){
          scope.list_of_chained_campaigns = _.difference(scope.list_of_chained_campaigns, to_remove);
        }else{
          scope.list_of_chained_campaigns = scope.original_chain_list;
        }
        scope.list_of_chained_campaigns.sort(); //re-sort the list in select fields
        scope.new_chain = scope.list_of_chained_campaigns[0];
      };

      scope.$on('loadChains', function(event, chain){
        scope.getChains(chain);
        scope.parseRootChains();
      });
      scope.$on('refreshChains', function(event, chain){
        //scope.getChains(chain);
        scope.root_campaign = chain;
        scope.parseRootChains();
      });
    }
  }
});
