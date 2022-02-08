angular.module('mcmApp').controller('editController',
  ['$scope', '$http', '$location', '$window', '$uibModal',
    function editController($scope, $http, $location, $window, $uibModal) {

      $scope.update = [];
      $scope.editingInfo = {};
      $scope.editableObject = {};

      const urlParams = $location.search()
      $scope.dbName = urlParams['db_name'];
      $scope.prepid = urlParams['prepid'];

      $scope.getObject = function () {
        let url = 'restapi/' + $scope.dbName + '/get_editable/' + $scope.prepid;
        $http.get(url).then(function (data) {
          if (data.results) {
            $scope.parseEditableObject(data.results);
          } else {
            $scope.openErrorModal(data.prepid, data['message']);
          }
        }, function (data) {
          $scope.openErrorModal(data.prepid, data['message']);
        });
      };
      setTimeout(() => {
        $scope.getObject();
      }, 1000);

      $scope.parseEditableObject = function (editableDict) {
        $scope.editingInfo = editableDict.editing_info;
        const hide = ['history', '_id', '_rev', 'next', 'reqmgr_name', 'config_id',
          'output_dataset', 'member_of_chain', 'member_of_campaign',
          'campaigns', 'generated_chains', 'meeting', 'completed_events', 'version'];
        for (let attr of hide) {
          delete $scope.editingInfo[attr];
        }
        // If use is not production manager, show only those fields that can be edited
        if (!$scope.user.is_mc_contact) {
          for (let attr in $scope.editingInfo) {
            if (!$scope.editingInfo[attr]) {
              delete $scope.editingInfo[attr];
            }
          }
        }
        $scope.editableObject = editableDict.object;
        // Fragment field
        setTimeout(function () {
          const fragmentTextArea = document.querySelector('textarea.fragment');
          if (fragmentTextArea) {
            const editor = CodeMirror.fromTextArea(fragmentTextArea,
              {
                'readOnly': !$scope.editingInfo['fragment'],
                'lineNumbers': true,
                'indentWithTabs': true,
                'height': 'auto',
                'viewportMargin': Infinity,
                'theme': 'eclipse'
              });
          }
        }, 300);
      };

      $scope.$watch(function () { return $http.pendingRequests.length; }, function (len) {
        $scope.pendingHTTPLength = len;
        $scope.pendingHTTP = len != 0;
      });

      $scope.openSequenceEdit = function (sequence, onSave) {
        $uibModal.open({
          templateUrl: 'editSequenceModal.html',
          controller: function ($scope, $uibModalInstance, $window, $http, sequence, onSave, attributeType) {
            $scope.sequence = JSON.parse(JSON.stringify(sequence));
            $scope.attributeType = attributeType;
            $scope.save = function () {
              onSave($scope.sequence);
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            sequence: function () { return sequence; },
            onSave: function () { return onSave; },
            attributeType: function () { return $scope.attributeType; },
          }
        })
      };

      $scope.attributeType = function (attribute) {
        let type = typeof (attribute)
        if (type != 'object') {
          return type;
        }
        if (Array.isArray(attribute)) {
          return 'array';
        }
        return type;
      }

      $scope.deleteEditableObject = function () {
        let prepid = $scope.prepid;
        const action = function () {
          $http({ method: 'DELETE', url: 'restapi/' + $scope.dbName + '/delete/' + prepid }).success(function (result, status) {
            if (result.results) {
              $window.location.href = $scope.database;
            } else {
              $scope.openErrorModal(prepid, result['message']);
            }
          }).error(function (data, status) {
            $scope.openErrorModal(prepid, data['message']);
          });
        }
        $scope.questionModal('Are you sure you want to delete ' + prepid, function () {
          action();
        });
      };

      $scope.booleanize_sequence = function (sequence) {
        _.each(sequence, function (value, key) {
          if (_.isString(value)) {
            switch (value.toLowerCase()) {
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

      $scope.commitEdit = function () {
        console.log('Saving...');
        console.log($scope.editableObject);
        switch ($scope.dbName) {
          case "requests":
            _.each($scope.result["sequences"], function (sequence) {
              $scope.booleanize_sequence(sequence);
              if (_.isString(sequence["step"])) {
                sequence["step"] = sequence["step"].split(",");
              }
              if (_.isString(sequence["datatier"])) {
                sequence["datatier"] = sequence["datatier"].split(",");
              }
              if (_.isString(sequence["eventcontent"])) {
                sequence["eventcontent"] = sequence["eventcontent"].split(",");
              }
            });
            _.each($scope.result["time_event"], function (value, key) {
              $scope.result["time_event"][key] = parseFloat(value);
            });
            _.each($scope.result["size_event"], function (value, key) {
              $scope.result["size_event"][key] = parseFloat(value);
            });
            $scope.result["memory"] = parseFloat($scope.result["memory"]);
            $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function (tok) { return tok.value });
            break;
          case "campaigns":
            _.each($scope.result["sequences"], function (sequence) {
              _.each(sequence, function (subSequence, key) {
                if (key != "$$hashKey") //ignore angularhs hashkey
                {
                  $scope.booleanize_sequence(subSequence);
                  if (_.isString(subSequence["step"])) {
                    subSequence["step"] = subSequence["step"].split(",");
                  }
                  if (_.isString(subSequence["datatier"])) {
                    subSequence["datatier"] = subSequence["datatier"].split(",");
                  }
                  if (_.isString(subSequence["eventcontent"])) {
                    subSequence["eventcontent"] = subSequence["eventcontent"].split(",");
                  }
                }
              });
            });
            break;
          case "mccms":
            $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function (tok) { return tok.value });
            break;
          case "flows":
            _.each($scope.result["request_parameters"]["sequences"], function (sequence) {
              _.each(sequence, function (elem) {
                if (_.has(elem, "datatier")) {
                  if (_.isString(elem["datatier"])) {
                    elem["datatier"] = elem["datatier"].split(",");
                  }
                }
                if (_.has(elem, "eventcontent")) {
                  if (_.isString(elem["eventcontent"])) {
                    elem["eventcontent"] = elem["eventcontent"].split(",");
                  }
                }
              });
            });
            break;
          default:
            break;
        }
        let method = $scope.prepid && $scope.prepid.length ? 'POST' : 'PUT';
        $http({ 'method': method, url: 'restapi/' + $location.search()["db_name"] + '/update', data: angular.toJson($scope.result) }).success(function (data, status) {
          $scope.update["success"] = data["results"];
          $scope.update["fail"] = false;
          $scope.update["message"] = data["message"];
          $scope.update["status_code"] = status;
          if ($scope.update["success"] == false) {
            $scope.update["fail"] = true;
          } else {
            $scope.getData();
          }
        }).error(function (data, status) {
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });
      };

      $scope.editableFragment = function () {
        return $scope.not_editable_list.indexOf('Fragment') != -1;
      };

      $scope.hideSequence = function (roleNumber) {
        return false;
      };

      $scope.removeUserPWG = function (elem) {
        $scope.result["pwg"] = _.without($scope.result["pwg"], elem);
      };

      $scope.showAddUserPWG = function () {
        $scope.showSelectPWG = true;
        var promise = $http.get("restapi/users/get_pwg")
        promise.then(function (data) {
          $scope.all_pwgs = data.data.results;
        });
      };

      $scope.addUserPWG = function (elem) {
        if ($scope.result["pwg"].indexOf(elem) == -1) {
          $scope.result["pwg"].push(elem);
        }
      };

      $scope.addToken = function (tok) {
        $http({ method: 'PUT', url: 'restapi/tags/add/', data: JSON.stringify({ tag: tok.value }) })
      };
    }
  ]);

  mcmApp.directive("editCampaignSequences", function($http){
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
            if (value === '' || attr == 'extra' || value === false || value.length === 0) {
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
          if (arguments.extra) {
            sequence += ` ${arguments.extra}`
          }
          return sequence;
        }
      }
    }
  });
  
  mcmApp.directive("editRequestSequences", function($http){
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
            if (value === '' || attr == 'extra' || value === false || value.length === 0) {
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
          if (arguments.extra) {
            sequence += ` ${arguments.extra}`
          }
          return sequence;
        }
      }
    }
  });
  
  
  mcmApp.directive("editRequestParameters", function () {
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div style="display: normal">
        <small ng-if="!errorMessage" style="color: #27ae60">Valid JSON</small>
        <small ng-if="errorMessage" style="color: red">Invalid JSON: {{errorMessage}}</small>
        <br>
        <div style="display: flex; width: 100%;">
          <textarea style="font-family: monospace; width: 100%; min-height: 400px; font-size: 0.9em; line-height: 1.1em;"
                    ng-model="value"
                    ng-blur="reformat()"
                    ng-disabled="!editable"></textarea>
        </div>
      </div>`,
      link: function(scope, element, attr, ctrl) {
        ctrl.$render = function(){
          scope.value = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
          scope.errorMessage = undefined;
          scope.value = JSON.stringify(scope.value, null, 2);
        };
        scope.reformat = function() {
          if (!scope.errorMessage) {
            scope.value = JSON.stringify(JSON.parse(scope.value), null, 2);
          }
        };
        scope.$watch("value", function(elem) {
          try {
            ctrl.$setViewValue(JSON.parse(scope.value));
            scope.errorMessage = undefined;
          } catch(err) {
            scope.errorMessage = err.toString();
          }
        });
      }
    }
  });
  
  
  mcmApp.directive("editGeneratorParameters", function(){
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div>
        <table ng-if="!editable" class="generator-parameters">
          <tr ng-repeat="attribute in attributes track by $index">
            <td style="text-align: right">
              {{attribute.replaceAll('_', ' ')}}
              <span ng-if="attribute != 'negative_weights_fraction' && attribute != 'cross_section'">(0.0 - 1.0)</span>
            </td>
            <td>{{generatorParameters[attribute]}}</td>
          </tr>
        </table>
        <table ng-if="editable" class="generator-parameters">
          <tr ng-repeat="attribute in attributes track by $index">
            <td style="text-align: right">
              {{attribute.replaceAll('_', ' ')}}
              <span ng-if="attribute != 'negative_weights_fraction' && attribute != 'cross_section'">(0.0 - 1.0)</span>
            </td>
            <td ng-if="editingAttribute !== attribute">
              {{generatorParameters[attribute]}}
              <span title="Pico barn" ng-if="attribute == 'cross_section'">pb</span>
              <a style="margin-left: 4px" ng-click="startEditing(attribute)" title="Edit">
                <i class="icon-wrench"></i>
              </a>
            </td>
            <td ng-if="editingAttribute == attribute">
              <input type="number"
                     style="width: auto;"
                     ng-model="generatorParameters[attribute]">
              <span title="Pico barn" ng-if="attribute == 'cross_section'">pb</span>
              <a style="margin-left: 4px" ng-click="stopEditing()" title="Finish editing">
                <i class="icon-ok"></i>
              </a>
            </td>
          </tr>
        </table>
        <a ng-click="addParameters()" ng-if="editable && attributes.length == 0" title="Add parameters">
          <i class="icon-plus"></i>
        </a>
        <a ng-click="removeParameters()" ng-if="editable && attributes.length != 0" title="Delete parameters">
          <i class="icon-minus-sign"></i>
        </a>
      </div>`,
      link: function(scope, element, attr, ctrl) {
        ctrl.$render = function(){
          scope.generatorParameters = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
          scope.editingAttribute = undefined;
          scope.setAttributes();
        };
        scope.setAttributes = function() {
          if (Object.keys(scope.generatorParameters).length == 0) {
            scope.attributes = [];
          } else {
            scope.attributes = ['cross_section', 'filter_efficiency',
                                'filter_efficiency_error', 'match_efficiency',
                                'match_efficiency_error', 'negative_weights_fraction'];
          }
        };
        scope.defaultParameters = function() {
          scope.generatorParameters = {'cross_section': 0,
                                       'filter_efficiency': 1,
                                       'filter_efficiency_error': 0,
                                       'match_efficiency': 1,
                                       'match_efficiency_error': 0,
                                       'negative_weights_fraction': 0};
        };
        scope.addParameters = function() {
          scope.defaultParameters();
          scope.setAttributes();
          ctrl.$setViewValue(scope.generatorParameters);
        };
        scope.removeParameters = function() {
          scope.generatorParameters = {};
          scope.setAttributes();
          ctrl.$setViewValue(scope.generatorParameters);
        };
        scope.startEditing = function(attribute) {
          scope.editingAttribute = attribute;
        };
        scope.stopEditing = function() {
          scope.editingAttribute = undefined;
        };
      }
    }
  });
  
  
  mcmApp.directive('editRequestValidation', function(){
    return {
      require: 'ngModel',
      replace: true,
      restrict: 'E',
      template:
      `<div ng-if="show">
        Length: <select style="width:50px; margin-bottom:0" ng-disabled="!editable" ng-model="data.time_multiplier" ng-options="key for key in multiplierOptions">
        </select> x 8h = {{(data.time_multiplier ? data.time_multiplier : 1)* 8}}h
        <br>
        <input type="checkbox" ng-disabled="!editable || !user.is_production_expert" ng-model="data.bypass"> Bypass
      </div>`,
      link: function(scope, element, attr, ctrl){
        ctrl.$render = function(){
          scope.data = ctrl.$viewValue;
          scope.show = Object.keys(scope.data).length > 0;
          scope.editable = scope.$eval(attr.editable);
          scope.multiplierOptions = [1, 2];
          if (scope.user.is_production_manager) {
            scope.multiplierOptions = [1, 2, 3, 4, 5, 6];
          }
        };
      }
    }
  });
  
  
  mcmApp.directive('editTags', function(){
    return {
      require: 'ngModel',
      replace: false,
      restrict: 'E',
      template: `<div style="display: flex; width: 100%; flex-direction: column">
        <input id="tokenfield" ng-disabled="!editable" type="text" class="form-control" value=""/>
        <small ng-if="editable"><i>Type a tag and press ENTER to add it or select one from a list</i></small>
      </div>`,
      link: function(scope, element, attr, ctrl){
        let typeahead = {'typeahead': {'remote': {'url': `restapi/${scope.dbName}/unique_values/?attribute=tags&value=%QUERY&limit=10`,
                                                  'filter': x=> x.results},
                                       'limit': 10}};
        let tokenfield = $("input", element).tokenfield(typeahead);
        ctrl.$render = function(){
          scope.tokens = ctrl.$viewValue;
          tokenfield.tokenfield("setTokens", scope.tokens);
          scope.editable = scope.$eval(attr.editable);
          tokenfield.tokenfield("setTokens", ctrl.$viewValue);
          if (scope.editable) {
            tokenfield.on('removeToken', function (e) {
              let token = e.token.value;
              scope.tokens = scope.tokens.filter(x => x != token);
              ctrl.$setViewValue(scope.tokens);
            });
            tokenfield.on('afterCreateToken', function (e) {
              let token = e.token.value;
              scope.tokens.push(token);
              ctrl.$setViewValue(scope.tokens);
            });
          } else {
            tokenfield.tokenfield('disable');
          }
        };
      }
    }
  });
  
  
  mcmApp.directive("editAttributeWithSuggestions", function($http){
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
          scope.database = attr.suggestDatabase ? attr.suggestDatabase : scope.dbName;
          scope.suggestAttribute = attr.suggestAttribute;
          scope.cache = {};
        };
        scope.$watch("value", function(elem) {
          ctrl.$setViewValue(scope.value);
        });
        scope.loadSuggestions = function (value) {
          if (value == '') {
            return [];
          }
          if (scope.cache[value]) {
            return scope.cache[value].filter(x => x != scope.value);
          }
          const url = `restapi/${scope.database}/unique_values/?attribute=${scope.suggestAttribute}&value=${value}&limit=${scope.limit}`;
          return $http.get(url).then(function (data) {
            let values = data.data.results;
            scope.cache[value] = values;
            return data.data.results.filter(x => x != scope.value);
          }, function (data) {
            return [];
          });
        };
      }
    }
  });
  
  
  mcmApp.directive("editListWithSuggestions", function($http){
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
        <a ng-click="addNew()" ng-if="editable && !editingIndex" title="Add new">
          <i class="icon-plus"></i>
        </a>
      </div>`,
      link: function(scope, element, attr, ctrl) {
        ctrl.$render = function(){
          scope.listItems = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
          scope.limit = attr.limit ? attr.limit : 20;
          scope.database = attr.suggestDatabase ? attr.suggestDatabase : scope.dbName;
          scope.suggestAttribute = attr.suggestAttribute;
          scope.editingIndex = undefined;
          scope.cache = {};
        };
        scope.startEditing = function(index) {
          scope.editingIndex = index;
        };
        scope.stopEditing = function(index) {
          if (!scope.listItems[index].length) {
            scope.listItems.splice(index, 1);
          }
          scope.editingIndex = undefined;
        };
        scope.addNew = function() {
          scope.listItems.push('');
          scope.editingIndex = scope.listItems.length - 1;
        };
        scope.loadSuggestions = function (value) {
          if (value == '') {
            return [];
          }
          if (scope.cache[value]) {
            return scope.cache[value].filter(x => !scope.listItems.includes(x));
          }
          const url = `restapi/${scope.database}/unique_values/?attribute=${scope.suggestAttribute}&value=${value}&limit=${scope.limit}`;
          return $http.get(url).then(function (data) {
            let values = data.data.results;
            scope.cache[value] = values;
            return data.data.results.filter(x => !scope.listItems.includes(x));
          }, function (data) {
            return [];
          });
        };
      }
    }
  });
  
  
  mcmApp.directive("editEventsPerLumi", function(){
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div style="width: 100%">
        <input type="checkbox" ng-disabled="!editable" ng-model="campaignValue">Use campaign value<br>
        <input style="margin-top: 4px" ng-disabled="!editable" type="number" ng-model="eventsPerLumi" class="input-xxsmall" ng-show="!campaignValue"></input>
        <span ng-show="eventsPerLumi != 0 && (eventsPerLumi < 100 || eventsPerLumi > 1000)" style="color:red">
          <br>
          Value must be between 100 and 1000 or 0
        </span>
      </div>`,
      link: function(scope, element, attr, ctrl)
      {
        ctrl.$render = function(){
          scope.eventsPerLumi = ctrl.$viewValue;
          scope.campaignValue = scope.eventsPerLumi == 0;
          scope.editable = scope.$eval(attr.editable);
        };
        scope.$watch("campaignValue", function(elem) {
          if (scope.campaignValue) {
            ctrl.$setViewValue(0);
          } else {
            ctrl.$setViewValue(100);
          }
        });
        scope.$watch("eventsPerLumi", function(elem) {
          if (scope.eventsPerLumi == 0 || (scope.eventsPerLumi >= 100 && scope.eventsPerLumi <= 1000)) {
            ctrl.$setViewValue(scope.eventsPerLumi);
          }
        });
      }
    }
  });
  
  
  mcmApp.directive("editTimeEvent", function(){
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div style="width: 100%">
        <ul ng-if="!editable">
          <li ng-repeat="value in timePerEvent track by $index">
            Sequence {{$index + 1}}: {{value}} s
          </li>
        </ul>
        <ul ng-if="editable">
          <li ng-repeat="value in timePerEvent track by $index" style="margin: 4px 0">
            Sequence {{$index + 1}}: <input type="number" style="width: auto;" ng-model="timePerEvent[$index]"> s
          </li>
        </ul>
      </div>`,
      link: function(scope, element, attr, ctrl)
      {
        ctrl.$render = function(){
          scope.timePerEvent = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
        };
        scope.$watch("timePerEvent", function(elem) {
          if (scope.timePerEvent) {
            ctrl.$setViewValue(scope.timePerEvent);
          }
        });
      }
    }
  });
  
  
  mcmApp.directive('convertToNumber', function() {
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
  
  
  mcmApp.directive("editSizeEvent", function(){
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div style="width: 100%">
        <ul ng-if="!editable">
          <li ng-repeat="value in sizePerEvent track by $index">
            Sequence {{$index + 1}}: {{value}} kB
          </li>
        </ul>
        <ul ng-if="editable">
          <li ng-repeat="value in sizePerEvent track by $index" style="margin: 4px 0">
            Sequence {{$index + 1}}: <input type="number" style="width: auto;" ng-model="sizePerEvent[$index]"> kB
          </li>
        </ul>
      </div>`,
      link: function(scope, element, attr, ctrl)
      {
        ctrl.$render = function(){
          scope.sizePerEvent = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
        };
        scope.$watch("sizePerEvent", function(elem) {
          if (scope.sizePerEvent) {
            ctrl.$setViewValue(scope.sizePerEvent);
          }
        });
      }
    }
  });
  
  
  mcmApp.directive("editMccmRequests", function ($http, $rootScope) {
    return {
      require: 'ngModel',
      replace: true,
      restrict: 'E',
      template:
      `<div style="width: 100%;">
        <ul ng-if="!editable">
          <li ng-repeat="elem in requests track by $index">
            <span ng-if="isArray(elem)">
              {{elem[0]}} <i class="icon-arrow-right"></i> {{elem[1]}}
            </span>
            <span ng-if="!isArray(elem)">
              {{elem}}
            </span>
          </li>
        </ul>
        <ul ng-if="editable">
          <li ng-repeat="elem in requests track by $index">
            <span ng-if="isArray(elem)">
              {{elem[0]}} <a ng-href="#" ng-click="removeFirstRequest($index)" ng-if="editingIndex === undefined" title="Remove {{elem[0]}}"><i class="icon-minus"></i></a>
              <i class="icon-arrow-right"></i>
              <span ng-if="editingIndex !== $index">{{elem[1]}}</span> <a ng-href="#" ng-click="removeSecondRequest($index)" ng-if="editingIndex === undefined" title="Remove {{elem[1]}}"><i class="icon-minus"></i></a>
              <input type="text"
                     style="width: auto"
                     ng-blur="cancelRange($index)"
                     ng-model="requests[$index][1]"
                     ng-if="editingIndex === $index"
                     typeahead="suggestion for suggestion in loadSuggestions(elem[0], $viewValue)"
                     typeahead-on-select=selected()>
            </span>
            <span ng-if="!isArray(elem)">
              <span ng-if="editingIndex !== $index">{{elem}}</span>
              <a ng-href="#" ng-click="removeRequest($index)" ng-if="editingIndex === undefined" title="Remove {{elem}}"><i class="icon-minus"></i></a>
              <a ng-href="#" ng-click="makeRange($index)" ng-if="editingIndex === undefined" title="Make range"><i class="icon-plus"></i></a>
              <input type="text"
                     style="width: auto"
                     ng-blur="cancel($index)"
                     ng-model="requests[$index]"
                     ng-if="editingIndex === $index"
                     typeahead="suggestion for suggestion in loadSuggestions(undefined, $viewValue)"
                     typeahead-on-select=selected()>
            </span>
          </li>
        </ul>
  
        <a ng-href="#" ng-click="addNew()" title="Add new request or range" ng-show="editable && editingIndex === undefined">
          <i class="icon-plus"></i>
        </a>
      </div>`,
      link: function (scope, element, attr, ctrl) {
        ctrl.$render = function () {
          scope.requests = ctrl.$viewValue;
          scope.editingIndex = undefined;
          scope.editable = scope.$eval(attr.editable);
          scope.cache = {};
        };
        scope.isArray = function(x) {
          return Array.isArray(x);
        }
        scope.addNew = function() {
          scope.requests.push('');
          scope.editingIndex = scope.requests.length - 1;
        }
        scope.cancel = function(index) {
          if (!scope.requests[index].length) {
            scope.requests.splice(index, 1);
            scope.editingIndex = undefined;
          }
        }
        scope.makeRange = function(index) {
          scope.requests[index] = [scope.requests[index], '']
          scope.editingIndex = index;
        }
        scope.cancelRange = function(index) {
          if (!scope.requests[index][1].length) {
            scope.requests[index] = scope.requests[index][0];
            scope.editingIndex = undefined;
          }
        }
        scope.selected = function () {
          scope.editingIndex = undefined;
        };
        scope.removeRequest = function (index) {
          scope.requests.splice(index, 1);
        }
        scope.removeFirstRequest = function (index) {
          scope.requests[index] = scope.requests[index][1];
        }
        scope.removeSecondRequest = function (index) {
          scope.requests[index] = scope.requests[index][0];
        }
        scope.loadSuggestions = function (firstPrepid, value) {
          if (!value.length) {
            return [];
          }
          let url = 'search/?db_name=requests&include_fields=prepid&prepid=' + value + '*';
          if (firstPrepid) {
            let firstParts = firstPrepid.split('-');
            let secondParts = value.split('-');
            if (firstParts[0].indexOf(secondParts[0]) != 0) {
              return [];
            }
            if (secondParts.length > 1 && firstParts[1].indexOf(secondParts[1]) != 0) {
              return [];
            }
            url += '&member_of_campaign=' + firstParts[1];
          }
          if (scope.cache[url]) {
            return scope.cache[url].filter(x => !scope.requests.includes(x))
          }
          return $http.get(url).then(function (data) {
            scope.cache[url] = data.data.results.map(x => x.prepid);
            return scope.cache[url].filter(x => !scope.requests.includes(x))
          }, function (data) {
            return [];
          });
        };
      }
    }
  });
  
  mcmApp.directive("editMccmChains", function ($http, $rootScope) {
    return {
      replace: false,
      restrict: 'E',
      require: 'ngModel',
      template:
      `<div style="width: 100%; display: flex; flex-direction: column;">
        <ul ng-if="!editable">
          <li ng-repeat="chain in chains track by $index">
            {{chain}}
          </li>
        </ul>
        <ul ng-if="editable">
          <li ng-repeat="chain in chains track by $index">
            <div ng-if="!addingNew || $index < chains.length - 1">
              {{chain}}
              <a style="margin-left: 4px" ng-click="removeChain($index)" title="Remove">
                <i class="icon-minus-sign"></i>
              </a>
            </div>
            <div ng-if="addingNew && $index == chains.length - 1">
              <input type="text"
                     placeholder="chain_..."
                     ng-model="chains[$index]"
                     ng-blur="cancel()"
                     typeahead="suggestion for suggestion in loadSuggestions($viewValue)"
                     typeahead-on-select="addChain($item)">
            </div>
          </li>
        </ul>
        <a ng-href="#" ng-if="editable && !addingNew" ng-click="addNew()">
          <i class="icon-plus"></i>
        </a>
      </div>`,
      link: function (scope, element, attr, ctrl) {
        ctrl.$render = function () {
          scope.chains = ctrl.$viewValue;
          scope.editable = scope.$eval(attr.editable);
          scope.addingNew = false;
          scope.cache = {};
        };
        scope.removeChain = function (index) {
          scope.chains.splice(index, 1);
        };
        scope.addNew = function() {
          scope.chains.push('');
          scope.addingNew = true;
        };
        scope.cancel = function() {
          if (!scope.chains[scope.chains.length - 1].length) {
            scope.chains.splice(scope.chains.length - 1, 1);
            scope.addingNew = false;
          }
        };
        scope.addChain = function (item) {
          if (!item || !item.trim().length) {
            return
          }
          scope.addingNew = false;
        };
        scope.loadSuggestions = function (value) {
          if (!value.length) {
            return [];
          }
          let url = "search/?db_name=chained_campaigns&include_fields=prepid&enabled=true&prepid=" + value + "*";
          if (scope.cache[url]) {
            return scope.cache[url].filter(x => !scope.chains.includes(x));
          }
          return $http.get(url).then(function (data) {
            scope.cache[url] = data.data.results.map(x => x.prepid);
            return scope.cache[url].filter(x => !scope.chains.includes(x));
          }, function (data) {
            return [];
          });
        };
      }
    }
  });
  