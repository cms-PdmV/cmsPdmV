function resultsCtrl($scope, $http, $location){
    $scope.user = {name: "", role:""}
// GET username and role
    var promise = $http.get("restapi/users/get_roles");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.roles[0];
    },function(data){
      alert("Error getting user information. Error: "+data.status);
    });
// Endo of user info request
    $scope.defaults = [];
    $scope.underscore = _;
    $scope.update = [];
    $scope.show_well = false;
    $scope.chained_campaigns = [];
    $scope.not_editable_list = ["Cmssw release", "Prepid", "Member of campaign", "Reqmgr name", 
                                "Pileup dataset name", "Pwg", "Completed events", "Status", 
                                "Type", "Priority", "Completion date"]; //user non-editable columns
    $scope.dbName = $location.search()["db_name"];
    if($location.search()["page"] === undefined){
        page = 0;
        $location.search("page", 0);
        $scope.list_page = 0;
    }else{
        page = $location.search()["page"];
        $scope.list_page = parseInt(page);
    }
//          var promise = $http.get("restapi/"+ $location.search()["db_name"]+"/get/"+$location.search()["query"])
    var promise = $http.get("getDefaultSequences");
    promise.then(function(data){
        console.log(data.data);
        $scope.default_sequences = data.data;
//         $scope.default_sequences = $scope.default_sequences.split(",");
    }, function(){ alert("Error"); });
       console.log($scope.default_sequences);
    
    $scope.default_sequences = 
    
    $scope.delete_object = function(db, value){
//         $http({method: 'GET', url: '/someUrl'}).
        $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
            console.log(data,status);
            if (data["results"]){
                alert('Object was deleted successfully.');
            }else{
                alert('Could not save data to database.');
            }
        }).error(function(status){
            alert('Error no.' + status + '. Could not delete object.');
        });
    };
    
    $scope.submit_edit = function(){
        console.log("submit function");
        console.log($scope.result);
        $http({method:'PUT', url:'restapi/'+$location.search()["db_name"]+'/update',data:angular.toJson($scope.result)}).success(function(data,status){
            console.log(data,status);
            $scope.update["success"] = data["results"];
            $scope.update["fail"] = false;
            $scope.update["status_code"] = status;
        }).error(function(data,status){
            $scope.update["success"] = false;
            $scope.update["fail"] = true;
            $scope.update["status_code"] = status;
        });
    };
    $scope.delete_edit = function(id){
        console.log("delete some from edit");
        $scope.delete_object($location.search()["db_name"], id);
    };
    $scope.display_approvals = function(data){
        console.log(data);
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
        if (sort.column == column) {
            sort.descending = !sort.descending;
        } else {
            sort.column = column;
            sort.descending = false;
        }
    };
  $scope.showing_well = function(){
        if ($scope.show_well){
          $scope.show_well = false;
        }
        else{
            console.log("true");
            $scope.show_well = true;
        }
    };    

   $scope.$watch('list_page', function(){
     console.log("modified");
     var promise = $http.get("restapi/"+ $location.search()["db_name"]+"/get/"+$location.search()["query"])
     promise.then(function(data){
       console.log(data);
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
       }
       console.log($scope.requests_defaults);
     }, function(){ alert("Error"); });
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
  
}
var ModalDemoCtrl = function ($scope) {
  $scope.open = function (number) {
    $scope.shouldBeOpen = true;
    $scope.sequenceNum = number;
    $scope.seqModalInfo = _.clone($scope.sequenceInfo[number]);
  };

  $scope.close = function (number) {
    $scope.shouldBeOpen = false;
    $scope.seqModalInfo = _.clone($scope.sequenceInfo[number]);
  };
    $scope.save = function () {
    console.log("saving modal info");
    console.log($scope.sequenceInfo);
    console.log($scope.sequencesOriginal);
    console.log($scope.seqModalInfo);
//     $scope.sequenceInfo[$scope.sequenceNum] = $scope.seqModalInfo;
    $scope.result.sequences = $scope.sequenceInfo;
    $scope.shouldBeOpen = false;
  };
  $scope.openNewSubSequence = function(){
    $scope.shouldBeOpen = true;
    $scope.newSequenceName = "";
    $scope.newSequence = $scope.default_sequences;
  };
  $scope.saveNewSubform = function(index){
    console.log($scope.newSequenceName, $scope.newSequence, index);
    if ($scope.dbName !="requests"){
      $scope.result.sequences[index][$scope.newSequenceName] = $scope.newSequence;
    }else{
      $scope.result.sequences[index].push($scope.newSequence);
    };
    $scope.shouldBeOpen = false;
  };
  $scope.saveNewSequence = function(){
    var shift = 0;
    if ($scope.dbName != "requests"){
      if (_.size($scope.result.sequences) != 0){
        shift =1; //in case we are ading a new sequence not from 0 we must increase array index of sequences
      }
      $scope.driver[_.size($scope.result.sequences)+shift] = {default: $scope.newSequence};
      $scope.result.sequences[_.size($scope.result.sequences)+shift] = {default: $scope.newSequence};
      console.log($scope.result.sequences, _.size($scope.result.sequences));
    }else{
      $scope.driver.push($scope.newSequence); //add a string to display in table
       $scope.result.sequences.push($scope.newSequence); //add to original data -> to be commited
    }
  };
};
// NEW for directive
var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("inlineEditable", function(){
  return{
      require: 'ngModel',
      template: 
      '<textarea ng-model="whatever_value" ng-change="update()" style="width: 390px; height: 152px;">'+
      '</textarea>',
      link: function(scope, element, attrs, ctrl){
       
       ctrl.$render = function () {
            scope.whatever_value = JSON.stringify(ctrl.$viewValue, null, 4);
       }
       
       scope.update = function () {
           var object = null;
           try {
               object = JSON.parse(scope.whatever_value);
               ctrl.$setViewValue(scope.whatever_value);
               ctrl.$setValidity("bad_json", true);
           } catch (err) {
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
    '  <div ng-switch-when="requests">'+
    '    <li ng-repeat="(sequence_id, sequence) in driver">{{sequence}}'+
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <a rel="tooltip" title="Edit sequence" ng-click="open(sequence_id);">'+
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
    '      <a rel="tooltip" title="Remove sequence" ng-click="removeSequence($index);">'+
    '        <i class="icon-remove-sign"></i>'+
    '      </a>'+
    '    </li>'+
    '  </div>'+
    '  <div ng-switch-default>'+
    '    <li ng-repeat="(key,value) in driver">'+
    '      <ul>'+
    '        {{key}}'+
    '      </ul>'+
    '      <ul ng-repeat="(name,elem) in value">'+
    ///MODAL
    '      <div ng-controller="ModalDemoCtrl">'+
    '        <li>{{name}}'+
    '          <a rel="tooltip" title="Edit sequence" ng-click="open($index);">'+
    '            <i class="icon-wrench"></i>'+
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
    '        <div ng-controller="ModalDemoCtrl">'+
    '          <a rel="tooltip" title="Add new sequence" ng-click="openNewSubSequence();">'+ //add sequence for Campaign
    '            <i class="icon-plus"></i>'+
    '          </a>'+
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
    '      </ul>'+
    '    </li>'+
    '  </div>'+
    '  </ul>'+
    //ADD NEW SEQUENCE MODAL
    '        <div ng-controller="ModalDemoCtrl">'+
    '          <a rel="tooltip" title="Add new sequence" ng-click="openNewSubSequence();">'+ //add sequence
    '            <i class="icon-plus"></i>'+
    '          </a>'+
    '          <div modal="shouldBeOpen" close="close()">'+ //hidden modal template
    '            <div class="modal-header">'+
    '              <h4>Sequence add modal</h4>'+
    '            </div>'+ //end oF  modal header
    '          <div class="modal-body">'+
    '            <form class="form-horizontal" name="sequenceForm">'+
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
    '            <button class="btn btn-success" ng-click="saveNewSequence();shouldBeOpen = false;">Save</button>'+
    '            <button class="btn btn-warning cancel" ng-click="close()">Cancel</button>'+
    '          </div>'+ //end of modal footer
    '        </div>'+
    //end OF MODAL
//     '  <a rel="tooltip" title="Add new sequence" ng-click="addSequence();">'+
//     '    <i class="icon-plus"></i>'+
//     '  </a>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        
        scope.show_sequence = false;
        if(scope.dbName == "requests"){
          if (!scope.sequencesOriginal){
            var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.result.prepid);
            promise.then(function(data){
              scope.driver = data.data.results;
              scope.sequencesOriginal = _.clone(scope.result.sequences);
            }, function(data){ alert("Error: ", data.status); });
          }
        }else{
            scope.sequencesOriginal = _.clone(scope.result.sequences);
            scope.driver = scope.sequencesOriginal;
        }
        console.log(scope.driver);
          scope.sequenceInfo = ctrl.$viewValue;
          scope.sequencesOriginal = _.clone(scope.result.sequences);
      };
      scope.editSequence = function(elem){
        alert("Not yet implemented "+elem);
      };
      scope.removeSequence = function(elem){
//         console.log(scope.result[0].sequence);
        scope.driver.splice(elem,1); //remove sequence from display
        scope.result.sequences.splice(elem,1); //remove the value from original sequences
        alert("Not yet implemented "+elem);
      };
      scope.addSequence = function(){
        alert("Not yet implemented");
      };
      
      scope.$watch('sequenceInfo', function(){
        console.log("pasikeite");
        console.log(scope.sequenceInfo);
      });
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
//     '          <th style="padding: 0px;">Message</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
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