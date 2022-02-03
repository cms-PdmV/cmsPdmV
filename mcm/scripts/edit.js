angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$modal',
  function ModalDemoCtrl($scope, $modal) {
    $scope.isBoolean = function(value){
      return angular.isBoolean(value);
    };

    // Generator parameters stuff
    $scope.showData = {
        "Cross section": "cross_section",
        "Filter efficiency": "filter_efficiency",
        "Filter efficiency error": "filter_efficiency_error",
        "Match efficiency": "match_efficiency",
        "Match efficiency error": "match_efficiency_error",
        "Negative weights fraction": 'negative_weights_fraction'
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

  // Flows Request params shit
  var EditRequestParametersCtrl = function ( $modalInstance, initRequestParams, parseRequestParams) {
    $scope.req_param_data = [{name: "Time Event", value: initRequestParams.time_event, id: "time_event", type: "int"}, {name: "Size Event", value: initRequestParams.size_event, id: "size_event", type: "int"}, {name: "Process String", value: initRequestParams.process_string, id: "process_string"}, {name: "Sequences", value: initRequestParams.sequences, id: "sequences"}, {name: "More", value: parseRequestParams, id:"more"}];
    $scope.addrem = function (seq, x) {
      for (var i in $scope.req_param_data) {
        if (!seq && $scope.req_param_data[i].name == "More") {
          x < 0 ? $scope.req_param_data[i].value.push({field: '', value: ''}) : $scope.req_param_data[i].value.splice(x, 1);
        } else if (seq && $scope.req_param_data[i].id == "sequences") {
          x < 0 ? $scope.req_param_data[i].value.push({default:{pileup: '', customise: '', conditions: ''}}) : $scope.req_param_data[i].value.splice(x, 1);
        }
      }
    };
      $scope.doneRequestModal = function () {
        var newJSON = {};
        for (var i in $scope.req_param_data) {
          if ($scope.req_param_data[i].value && $scope.req_param_data[i].id != 'more') {
            if ($scope.req_param_data[i].type == 'int') {
              newJSON[$scope.req_param_data[i].id] = parseInt($scope.req_param_data[i].value, 10);
            } else {
              newJSON[$scope.req_param_data[i].id] = $scope.req_param_data[i].value;
            }
          } else if($scope.req_param_data[i].id == 'more') {
              for (var j in $scope.req_param_data[i].value) {
                newJSON[$scope.req_param_data[i].value[j].field] = $scope.req_param_data[i].value[j].value;
              }
          }
        }

        try {
          $scope.whatever_value = JSON.stringify(newJSON, undefined, 4);
          $scope.fieldForm.$setViewValue(newJSON);
          $scope.fieldForm.$setValidity("bad_json", false);
        } catch (err){
          $scope.fieldForm.$setValidity("bad_json", true);
        }

        $modalInstance.dismiss();
      };

      $scope.closeRequestModal = function() {
        $modalInstance.dismiss();
      }
    };

    $scope.openRequestParametersModal = function () {
      $modal.open({
        templateUrl: "HTML/templates/edit.request.parameters.html",
        controller: EditRequestParametersCtrl,
        scope: $scope,
        resolve: {
          initRequestParams: function () {
            return JSON.parse($scope.whatever_value);
          },
          parseRequestParams: function () {
            var copy = JSON.parse($scope.whatever_value);
            var remove_array = ["time_event", "sequences", "size_event", "process_string"];
            for (var i in remove_array) {
              delete copy[remove_array[i]];
            }
            var rt = []
            for (var i in copy) {
              rt.push({field: i, value: copy[i]});
            }
            return rt;
          },
          getFieldValue: function(){
            return $scope.whatever_value;
          }
        }
      });
    };
  }
]);

testApp.directive("editCampaignSequences", function($http){
  return {
    require: 'ngModel',
    template:
    `<div>
      <div ng-repeat="(sequenceName, sequenceList) in sequences">
        <span ng-if="editingSequenceName != sequenceName">
          {{sequenceName}}
          <a style="margin-left: 4px" ng-if="editable" ng-click="startEditingSequenceName(sequenceName)" title="Edit group name">
            <i class="icon-wrench"></i>
          </a>
          <a style="margin-left: 4px" ng-if="editable" ng-click="removeSequenceName(sequenceName)" title="Remove sequence group">
            <i class="icon-minus-sign"></i>
          </a>
        </span>
        <span ng-if="editingSequenceName == sequenceName">
          <input type="text" style="width: auto;" ng-model="newSequenceName">
          <a style="margin-left: 4px" ng-click="stopEditingSequenceName(sequenceName, newSequenceName)" title="Finish editing">
            <i class="icon-ok"></i>
          </a>
        </span>
        <ul>
          <li ng-repeat="sequence in sequenceList track by $index">
            <div style="display: flex">
              <div style="font-size: 0.9em; margin: 2px 0; font-family: monospace; background-color: #f5f5f5; border-radius: 4px; padding: 4px; border: 1px solid rgba(0, 0, 0, 0.15);">
                {{sequenceStrings[sequenceName][$index]}}
              </div>
              <div ng-if="editable" style="display: flex; flex-direction: column; margin: auto 0 auto 4px;">
                <a ng-click="startEditing(sequenceName, $index)" title="Edit" ng-if="editable">
                  <i class="icon-wrench"></i>
                </a>
                <a ng-click="removeSequence(sequenceName, $index)" title="Remove" ng-if="editable">
                  <i class="icon-minus-sign"></i>
                </a>
              </div>
            </div>
            <a ng-click="addSequence(sequenceName)" ng-if="editable && !editingSequenceName && $index == sequenceList.length - 1" title="Add sequence to {{sequenceName}}">
              <i class="icon-plus"></i>
            </a>
          </li>
        </ul>
        <a ng-click="addSequence(sequenceName)" ng-if="editable && !editingSequenceName && !sequenceList.length" title="Add sequence to {{sequenceName}}">
          <i class="icon-plus"></i>
        </a>
      </div>
      <a ng-click="addSequenceName()" title="Add new sequence group" ng-if="editable && !editingSequenceName">
        <i class="icon-plus-sign"></i>
      </a>
    </div>`,
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.sequences = ctrl.$viewValue;
        scope.sequenceStrings = {};
        for (let sequenceName in scope.sequences) {
          scope.buildStrings(sequenceName);
        }
        scope.campaign = scope.$eval(attr.campaign);
        scope.editingSequenceName = undefined;
        scope.newSequenceName = '';
        scope.defaultSequence = undefined;
      };
      scope.startEditing = function(name, index) {
        scope.openSequenceEdit(scope.sequences[name][index], function(newSequence) {
          scope.sequences[name][index] = newSequence;
          scope.buildStrings(name);
        });
      };
      scope.startEditingSequenceName = function(name) {
        scope.editingSequenceName = name;
        scope.newSequenceName = name;
      };
      scope.removeSequenceName = function(name) {
        delete scope.sequences[name];
        delete scope.sequenceStrings[name];
        delete scope.campaign.keep_output[name];
      };
      scope.stopEditingSequenceName = function(name, newName) {
        if (name == newName) {
          scope.editingSequenceName = undefined;
          return
        }
        if (scope.sequences[newName]) {
          return
        }
        scope.editingSequenceName = undefined;
        scope.sequences[newName] = JSON.parse(JSON.stringify(scope.sequences[name]));
        scope.campaign.keep_output[newName] = JSON.parse(JSON.stringify(scope.campaign.keep_output[name]));
        scope.buildStrings(newName);
        scope.removeSequenceName(name);
      };
      scope.buildStrings = function(sequenceName) {
        let sequences = scope.sequences[sequenceName];
        scope.sequenceStrings[sequenceName] = sequences.map(s => scope.buildSequenceString(s));
      }
      scope.removeSequence = function(sequenceName, index){
        scope.sequences[sequenceName].splice(index, 1);
        scope.sequenceStrings[sequenceName].splice(index, 1);
        scope.campaign.keep_output[sequenceName].splice(index, 1);
      };
      scope.addSequence = function(sequenceName) {
        if (scope.defaultSequence) {
          scope.sequences[sequenceName].push(JSON.parse(JSON.stringify(scope.defaultSequence)));
          scope.campaign.keep_output[sequenceName].push(true);
          scope.buildStrings(sequenceName);
        } else {
          const url = 'restapi/campaigns/get_default_sequence';
          $http.get(url).then(function (data) {
            scope.defaultSequence = data.data.results;
            scope.addSequence(sequenceName);
          });
        }
      };
      scope.addSequenceName = function() {
        let name = 'default';
        let number = 0;
        while (scope.sequences[name]) {
          number += 1;
          name = `default-${number}`
        }
        scope.sequences[name] = [];
        scope.sequenceStrings[name] = [];
        scope.campaign.keep_output[name] = [];
      };
      scope.buildSequenceString = function(arguments) {
        let sequence = 'cmsDriver.py';
        for (let attr in arguments) {
          let value = arguments[attr];
          if (value === '' || value === false || value.length === 0) {
            continue
          }
          if (attr == 'nStreams' && value == 0) {
            continue
          }
          if (attr == 'nThreads' && value == 1) {
            continue
          }
          sequence += ` --${attr}`
          if (value !== true) {
            sequence += ` ${value}`;
          }
        }
        return sequence;
      }
    }
  }
});

testApp.directive("editRequestSequences", function($http){
  return {
    require: 'ngModel',
    template:
    `<div>
      <ul>
        <li ng-repeat="sequence in sequences track by $index">
          <div style="display: flex">
            <div style="font-size: 0.9em; margin: 2px 0; font-family: monospace; background-color: #f5f5f5; border-radius: 4px; padding: 4px; border: 1px solid rgba(0, 0, 0, 0.15);">
              {{sequenceStrings[$index]}}
            </div>
            <div ng-if="editable" style="display: flex; flex-direction: column; margin: auto 0 auto 4px;">
              <a ng-click="startEditing($index)" title="Edit" ng-if="editable">
                <i class="icon-wrench"></i>
              </a>
              <a ng-click="removeSequence($index)" title="Remove" ng-if="editable">
                <i class="icon-minus-sign"></i>
              </a>
            </div>
          </div>
          <a ng-click="addSequence()" ng-if="editable && $index == sequences.length - 1" title="Add sequence">
            <i class="icon-plus"></i>
          </a>
        </li>
      </ul>
      <a ng-click="addSequence()" ng-if="editable && !sequences.length" title="Add sequence">
        <i class="icon-plus"></i>
      </a>
    </div>`,
    link: function(scope, element, attr, ctrl){
      ctrl.$render = function(){
        scope.sequences = ctrl.$viewValue;
        scope.sequenceStrings = [];
        scope.buildStrings();
        scope.request = scope.$eval(attr.request);
        scope.defaultSequence = undefined;
      };
      scope.buildStrings = function() {
        scope.sequenceStrings = scope.sequences.map(s => scope.buildSequenceString(s));
      }
      scope.startEditing = function(index) {
        scope.openSequenceEdit(scope.sequences[index], function(newSequence) {
          scope.sequences[index] = newSequence;
          scope.buildStrings();
        });
      };
      scope.removeSequence = function(index){
        scope.sequences.splice(index, 1);
        scope.sequenceStrings.splice(index, 1);
        scope.request.keep_output.splice(index, 1);
        scope.request.time_event.splice(index, 1);
        scope.request.size_event.splice(index, 1);
      };
      scope.addSequence = function() {
        if (scope.defaultSequence) {
          scope.sequences.push(JSON.parse(JSON.stringify(scope.defaultSequence)));
          scope.request.keep_output.push(true);
          scope.request.time_event.push(-1.0);
          scope.request.size_event.push(-1.0);
          scope.buildStrings();
        } else {
          const url = 'restapi/campaigns/get_default_sequence';
          $http.get(url).then(function (data) {
            scope.defaultSequence = data.data.results;
            scope.addSequence();
          });
        }
      };
      scope.buildSequenceString = function(arguments) {
        let sequence = 'cmsDriver.py';
        for (let attr in arguments) {
          let value = arguments[attr];
          if (value === '' || value === false || value.length === 0) {
            continue
          }
          if (attr == 'nStreams' && value == 0) {
            continue
          }
          if (attr == 'nThreads' && value == 1) {
            continue
          }
          sequence += ` --${attr}`
          if (value !== true) {
            sequence += ` ${value}`;
          }
        }
        return sequence;
      }
    }
  }
});

testApp.directive("selectCampaign", function(){
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
    '<div ng-controller="ModalDemoCtrl">'+
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
    }
  }
});

testApp.directive("inlineEditable", function ($modal) {
    return {
        require: 'ngModel',
        templateUrl: "HTML/templates/edit.request.parameters.textarea.html",
        link: function (scope, element, attr, ctrl) {
            ctrl.$render = function () {
                scope.whatever_value = JSON.stringify(ctrl.$viewValue, null, 4);
                scope.formColumn = scope.$eval(attr.column);
            };
            scope.update = function () {
                var object = null;
                try {
                    object = JSON.parse(scope.whatever_value);
                    ctrl.$setViewValue(object);
                    ctrl.$setValidity("bad_json", true);
                } catch (err) {
                    ctrl.$setValidity("bad_json", false);
                }
            };

        }
    };
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
    '        Add VALIDATION step and upload output to DQM GUI:'+
    '        <input type="checkbox"  ng-model="validation_data.valid" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.valid">' +
    '        Validation Content:'+       
    '        <select  ng-model="validation_data.content" ng-options="dqmcontent for dqmcontent in [\'all\',\'DY\',\'Top\',\'W\',\'Higgs\',\'QCD\']"></select>'+ 
    //'        nEvents:'+
    //'        <input type="number"  ng-model="validation_data.nEvents" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
    '      </div>'+
    '      <div class="control-group" ng-show="validation_data.dqm">'+
    '        DQM:'+
    '        <a ng-show="isDevMachine()" href="https://cmsweb-testbed.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '        <a ng-show="!isDevMachine()" href="https://cmsweb.cern.ch/dqm/dev/start?runnr=1;dataset={{data[value.db_name].dqm}};sampletype=offline_relval;filter=all;referencepos=overlay;referenceshow=all;referencenorm=True;referenceobj1=other%3A1%3A{{data[value.db_name].ref_dqm}}%3AReference%3A;referenceobj2=none;referenceobj3=none;referenceobj4=none;search=;striptype=object;stripruns=;stripaxis=run;stripomit=none;workspace=Everything;size=M;root=Generator;focus=;zoom=no;" rel="tooltip" title="Go to the DQM gui for {{data[value.db_name].dqm}}" target="_blank">'+
    '          <i class="icon-th-large"></i>'+
    '        </a>'+
    '      </div>'+
    '      <div class="control-group">'+
    '        Validation length (use only when validation produce <10 events in 8h): '+
    '        <span ng-hide="!role(3)">' +
    '          <select style="width:50px; margin-bottom:0" ng-disabled="not_editable_list.indexOf(\'Validation\') != -1" ng-model="validation_data.time_multiplier" ng-options="key as key for key in [1,2]">' +
    '            <option hidden disabled selected value>{{ validation_data.time_multiplier ? validation_data.time_multiplier : 1 }}</option>' +
    '          </select> x 8h = {{(validation_data.time_multiplier ? validation_data.time_multiplier : 1)* 8}}h' +
    '        </span>' +
    '        <span ng-hide="role(3)">' +
    '          <select style="width:50px; margin-bottom:0" ng-disabled="not_editable_list.indexOf(\'Validation\') != -1" ng-model="validation_data.time_multiplier" ng-options="key as key for key in [1,2,3,4,5,6]">' +
    '            <option hidden disabled selected value>{{ validation_data.time_multiplier ? validation_data.time_multiplier : 1 }}</option>' +
    '          </select> x 8h = {{(validation_data.time_multiplier ? validation_data.time_multiplier : 1) * 8}}h' +
    '        </span>' +
    '      </div>'+
    '    </fieldset>'+
    '  </form>'+
    '  <input type="text" ng-switch-default ng-model="validation_data" style="width: 390px; height: 20px; margin-bottom: 0px;" ng-disabled="not_editable_list.indexOf(\'Validation\')!=-1">'+
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
      scope.$watch("validation_data.time_multiplier", function(elem){ //watch time_multiplier -> is user leaves empty remove time_multiplier, as not to save null
        if (!elem){
          delete(scope.validation_data.time_multiplier);
        }
      });
    }
  }
});


testApp.directive("editAttributeWithSuggestions", function($http){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    `<input type="text"
            ng-model="value"
            ng-disabled="!editable"
            typeahead="suggestion for suggestion in loadSuggestions($viewValue)">`,
    link: function(scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.value = ctrl.$viewValue;
        scope.editable = scope.$eval(attr.editable);
        scope.limit = attr.limit ? attr.limit : 20;
        scope.attribute = attr.attribute;
        scope.cache = {};
      };

      scope.startEditing = function(index) {
        scope.editingIndex = index;
      }

      scope.stopEditing = function(index) {
        if (!scope.listItems[index].length) {
          scope.remove(index);
        }
        scope.editingIndex = undefined;
      }

      scope.addNew = function() {
        scope.listItems.push('');
        scope.editingIndex = scope.listItems.length - 1;
      }

      scope.loadSuggestions = function (value) {
        if (value == '') {
          return [];
        }
        if (scope.cache[value]) {
          return scope.cache[value];
        }
        const url = `restapi/${scope.dbName}/unique_values/?attribute=${scope.attribute}&value=${value}&limit=${scope.limit}`;
        return $http.get(url).then(function (data) {
          scope.cache[value] = data.data.results;
          return data.data.results;
        }, function (data) {
          return [];
        });
      };
    }
  }
});


testApp.directive("editListWithSuggestions", function($http){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    `<div>
      <ul ng-if="!editable">
        <li ng-repeat="item in listItems track by $index">
          {{item}}
        </li>
      </ul>
      <ul ng-if="editable">
        <li ng-repeat="item in listItems track by $index">
          <span ng-if="editingIndex !== $index">
            {{item}}
            <a style="margin-left: 4px" ng-click="startEditing($index)" title="Edit">
              <i class="icon-wrench"></i>
            </a>
            <a style="margin-left: 4px" ng-click="listItems.splice($index, 1)" title="Remove">
              <i class="icon-minus-sign"></i>
            </a>
          </span>
          <span ng-if="editingIndex === $index">
            <input type="text"
                    style="width: auto;"
                    ng-model="listItems[$index]"
                    typeahead="suggestion for suggestion in loadSuggestions($viewValue)">
            <a style="margin-left: 4px" ng-click="stopEditing($index)" title="Finish editing">
              <i class="icon-ok"></i>
            </a>
          </span>
        </li>
      </ul>
      <a ng-click="addNew()" ng-if="!editingIndex" title="Add new">
        <i class="icon-plus"></i>
      </a>
    </div>`,
    link: function(scope, element, attr, ctrl) {
      ctrl.$render = function(){
        scope.listItems = ctrl.$viewValue;
        scope.editable = scope.$eval(attr.editable);
        scope.limit = attr.limit ? attr.limit : 20;
        scope.attribute = attr.attribute;
        scope.editingIndex = undefined;
        scope.cache = {};
      };

      scope.startEditing = function(index) {
        scope.editingIndex = index;
      }

      scope.stopEditing = function(index) {
        if (!scope.listItems[index].length) {
          scope.listItems.splice(index, 1);
        }
        scope.editingIndex = undefined;
      }

      scope.addNew = function() {
        scope.listItems.push('');
        scope.editingIndex = scope.listItems.length - 1;
      }

      scope.loadSuggestions = function (value) {
        if (value == '') {
          return [];
        }
        if (scope.cache[value]) {
          return scope.cache[value];
        }
        const url = `restapi/${scope.dbName}/unique_values/?attribute=${scope.attribute}&value=${value}&limit=${scope.limit}`;
        return $http.get(url).then(function (data) {
          scope.cache[value] = data.data.results;
          return data.data.results;
        }, function (data) {
          return [];
        });
      };
    }
  }
});

testApp.directive("listPredefined", function($http){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in analysis_data track by $index">'+
    '     <span ng-hide="editable[$index]">'+
    '       {{elem}}'+
    '     </span>'+
    '     <span ng-hide="editable[$index] || not_editable_list.indexOf(columnName)!=-1">'+
    '       <a ng-click="remove($index)">'+
    '         <i class="icon-remove-sign"></i>'+
    '       </a>'+
    '     <span>'+
    '   </li>'+
    '  </ul>'+
    '    <form class="form-inline" ng-hide="not_editable_list.indexOf(columnName)!=-1">'+
    '      <a ng-click="add_analysis_id=!add_analysis_id;">'+
    '        <i class="icon-plus" ng-hide="add_analysis_id"></i>'+
    '        <i class="icon-minus" ng-show="add_analysis_id"></i>'+
    '      </a>'+
    '      <input type="text" ng-model="new_analysis_id" ng-show="add_analysis_id" class="input-xxlarge" typeahead="suggestion for suggestion in getSuggestions($viewValue)">'+
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
        scope.columnName = scope.$eval(attr.column);
        scope.fieldName = attr.suggestionsFieldname;
        if (scope.suggestions === undefined) {
          scope.suggestions = [];
        }
        if (scope.suggestions.length === 0) {
          scope.loadSuggestions()
        }
      };

      scope.remove = function(index){
        scope.analysis_data.splice(index, 1);
        scope.loadSuggestions()
      };

      scope.pushNewAnalysisID = function(){
        if (!(scope.suggestions.includes(scope.new_analysis_id))) {
          alert(scope.new_analysis_id + ' is not a valid value')
          return;
        }
        scope.analysis_data.push(scope.new_analysis_id);
        scope.add_analysis_id = false;
        scope.new_analysis_id = "";
        scope.loadSuggestions()
      };

      scope.getSuggestions = function(value) {
        if (scope.suggestions.length === 0) {
          scope.loadSuggestions();
        }
        var filteredResults = scope.suggestions.filter(function(el) {
          return el.indexOf(value) >= 0;
        });
        return filteredResults;
      }

      scope.loadSuggestions = function () {
        if (attr.suggestions !== undefined && scope[attr.suggestions] !== undefined) {
          scope.suggestions = scope[attr.suggestions];
        } else {
          scope.suggestions = []
        }
        if (scope.fieldName == undefined) {
          return {};
        }
        let searchURL = "restapi/requests/unique_values/" + scope.fieldName + "?key=" + fieldValue;
        if (scope.fieldName === 'ppd_tags') {
          searchURL = "restapi/requests/ppd_tags/" + scope.result.prepid ;
        }
        return $http.get(searchURL).then(function (data) {
          return data.data.results;
        }, function (data) {
          alert("Error getting suggestions for " + scope.fieldName + "=" + fieldValue + ": " + data.status);
        });
      };
    }
  }
});

testApp.directive("singlePredefined", function($http){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <span ng-show="analysis_data !== undefined && analysis_data !== \'\'">'+
    '    {{analysis_data}}'+
    '    <span ng-hide="editable[$index] || not_editable_list.indexOf(columnName)!=-1">'+
    '      <a ng-click="remove()">'+
    '        <i class="icon-remove-sign"></i>'+
    '      </a>'+
    '    </span>'+
    '  </span>'+
    '  <form ng-hide="analysis_data !== undefined && analysis_data !== \'\'" class="form-inline" ng-hide="not_editable_list.indexOf(columnName)!=-1">'+
    '    <input type="text" ng-model="new_analysis_id" class="input-xxlarge" typeahead="suggestion for suggestion in getSuggestions($viewValue)">'+
    '    <i class="icon-plus-sign" ng-click="pushNewAnalysisID()"></i>'+
    '  </form>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.analysis_data = ctrl.$viewValue;
        scope.new_analysis_id = "";
        scope.editable = {};
        scope.new_id = "";
        scope.columnName = scope.$eval(attr.column);
        scope.fieldName = attr.suggestionsFieldname;
        if (scope.suggestions === undefined) {
          scope.suggestions = [];
        }
        if (scope.suggestions.length === 0) {
          scope.loadSuggestions()
        }
      };

      scope.remove = function(){
        scope.analysis_data = ''
        scope.loadSuggestions()
      };

      scope.pushNewAnalysisID = function(){
        if (!(scope.suggestions.includes(scope.new_analysis_id))) {
          alert(scope.new_analysis_id + ' is not a valid value')
          return;
        }
        scope.analysis_data = scope.new_analysis_id;
        scope.add_analysis_id = false;
        scope.new_analysis_id = "";
        ctrl.$setViewValue(scope.analysis_data);
        scope.loadSuggestions()
      };

      scope.getSuggestions = function(value) {
        if (scope.suggestions.length === 0) {
          scope.loadSuggestions();
        }
        var filteredResults = scope.suggestions.filter(function(el) {
          return el.indexOf(value) >= 0;
        });
        return filteredResults;
      }

      scope.loadSuggestions = function () {
        if (attr.suggestions !== undefined && scope[attr.suggestions] !== undefined) {
          scope.suggestions = scope[attr.suggestions];
        } else {
          scope.suggestions = []
        }
        if (scope.fieldName == undefined) {
          return {};
        }
        const searchURL = "restapi/requests/unique_values/" + scope.fieldName + "?key=" + fieldValue;
        return $http.get(searchURL).then(function (data) {
          return data.data.results;
        }, function (data) {
          alert("Error getting suggestions for " + scope.fieldName + "=" + fieldValue + ": " + data.status);
        });
      };
    }
  }
});

testApp.directive("timeEventEdit", function(){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in time_event track by $index">'+
    '     <input type="number" ng-model="time_event[$index]" class="input-xxsmall" style="width: 90px;" ng-disabled="not_editable_list.indexOf(\'Time event\')!=-1"></input>'+
    '     <a class="label label-info" rel="tooltip" title="seconds">s</a>'+
    '     <a ng-click="remove($index)" ng-href="#" ng-hide="not_editable_list.indexOf(\'Time event\')!=-1">'+
    '       <i class="icon-remove-sign"></i>'+
    '     </a>'+
    '   </li>'+
    '  </ul>'+
    '  <div style="margin-left: 7px;" ng-hide="not_editable_list.indexOf(\'Time event\')!=-1">'+
    '    <a ng-click="add_time_event =! add_time_event;" ng-href="#">'+
    '      <i class="icon-plus" ng-hide="add_time_event"></i>'+
    '      <i class="icon-minus" ng-show="add_time_event"></i>'+
    '    </a>'+
    '    <input type="number" ng-model="new_time_event" ng-show="add_time_event" class="input-xxsmall" style="width: 90px;"></inputs>'+
    '    <a ng-click="pushNewTimeEvent()" ng-show="add_time_event" ng-href="#">'+
    '      <i class="icon-plus-sign"></i>'+
    '    </a>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.time_event = ctrl.$viewValue;
        scope.new_time_event = -1;
        scope.columnName = scope.$eval(attr.column);
      };

      scope.remove = function(index){
        scope.time_event.splice(index, 1);
      };

      scope.pushNewTimeEvent = function(){
        if (scope.new_time_event > 0) {
          scope.time_event.push(parseFloat(scope.new_time_event));
        }
        scope.add_time_event = false;
        scope.new_time_event = -1;
      };
    }
  }
});

testApp.directive('convertToNumber', function() {
  return {
    require: 'ngModel',
    link: function(scope, element, attrs, ngModel) {
      ngModel.$parsers.push(function(val) {
        return parseInt(val, 10);
      });
      ngModel.$formatters.push(function(val) {
        return '' + val;
      });
    }
  };
});

testApp.directive("sizeEventEdit", function(){
  return {
    replace: false,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul>'+
    '   <li ng-repeat="elem in size_event track by $index">'+
    '     <input type="number" ng-model="size_event[$index]" class="input-xxsmall" style="width: 90px;" ng-disabled="not_editable_list.indexOf(\'Size event\')!=-1"></input>'+
    '     <a class="label label-info" rel="tooltip" title="kiloBytes">kB</a>'+
    '     <a ng-click="remove($index)" ng-href="#" ng-hide="not_editable_list.indexOf(\'Size event\')!=-1">'+
    '       <i class="icon-remove-sign"></i>'+
    '     </a>'+
    '   </li>'+
    '  </ul>'+
    '  <div style="margin-left: 7px;" ng-hide="not_editable_list.indexOf(\'Size event\')!=-1">'+
    '    <a ng-click="add_size_event =! add_size_event;" ng-href="#">'+
    '      <i class="icon-plus" ng-hide="add_size_event"></i>'+
    '      <i class="icon-minus" ng-show="add_size_event"></i>'+
    '    </a>'+
    '    <input type="number" ng-model="new_size_event" ng-show="add_size_event" class="input-xxsmall" style="width: 90px;"></inputs>'+
    '    <a ng-click="pushNewSizeEvent()" ng-show="add_size_event" ng-href="#">'+
    '      <i class="icon-plus-sign"></i>'+
    '    </a>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.size_event = ctrl.$viewValue;
        scope.new_size_event = -1;
        scope.columnName = scope.$eval(attr.column);
      };

      scope.remove = function(index){
        scope.size_event.splice(index, 1);
      };

      scope.pushNewSizeEvent = function(){
        if (scope.new_size_event > 0) {
          scope.size_event.push(parseFloat(scope.new_size_event));
        }
        scope.add_size_event = false;
        scope.new_size_event = -1;
      };
    }
  }
});

testApp.directive("eventsLumiEdit", function(){
  return {
    replace: true,
    restrict: 'E',
    require: 'ngModel',
    template:
    '<div>'+
    '  <input type="checkbox" ng-model="useCampaignsValue" style="margin-top: 0">Use campaign\'s value<br>'+
    '  <input type="number" ng-model="eventsPerLumi" class="input-xxsmall" style="width: 120px; margin-top:4px;" ng-show="!useCampaignsValue"></input>'+
    '  <span ng-show="!useCampaignsValue && (eventsPerLumi < 100 || eventsPerLumi > 1000)" style="color:red"><br>Values must be within 100 and 1000 or 0 to use value from campaign</span>'+
    '</div>'+
    '',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.eventsPerLumi = ctrl.$viewValue;
        scope.oldEventsPerLumi = scope.eventsPerLumi;
        if (scope.eventsPerLumi == 0) {
          scope.eventsPerLumi = 100;
        }
        scope.useCampaignsValue = ctrl.$viewValue == 0;
      };
      scope.$watch("useCampaignsValue", function(elem){ //watch nEvents -> is user leaves empty remove nEvents, as not to save null
        if (elem){
          scope.oldEventsPerLumi = scope.eventsPerLumi;
          scope.eventsPerLumi = 0;
        } else {
          scope.eventsPerLumi = scope.oldEventsPerLumi;
        }
      });
      scope.$watch("eventsPerLumi", function(elem){ //watch nEvents -> is user leaves empty remove nEvents, as not to save null
        ctrl.$setViewValue(scope.eventsPerLumi);
      });
    }
  }
});
