angular.module('mcmApp').controller('requestController',
['$scope', '$http', '$window', '$uibModal',
function requestController($scope, $http, $window, $uibModal) {
      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Approval', select: true, db_name: 'approval' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Dataset name', select: true, db_name: 'dataset_name' },
        { text: 'History', select: true, db_name: 'history' },
        { text: 'Tags', select: true, db_name: 'tags' }
      ];

      $scope.setDatabaseInfo('requests', $scope.columns);
      $scope.selectedItems = [];
      $scope.file_was_uploaded = false;
      $scope.tabsettings = {
        "view": {
          active: false
        },
        "search": {
          active: false
        },
        "file": {
          active: false
        },
        "navigation": {
          active: false
        },
        "output": {
          active: false
        }
      };

      $scope.reset = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/reset',
                             data: {'prepid': prepids}})
      }

      $scope.softReset = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to soft reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/soft_reset',
                             data: {'prepid': prepids}})
      }

      $scope.optionReset = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to option reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/option_reset',
                             data: {'prepid': prepids}})
      }

      $scope.nextStatus = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to move ' + $scope.promptPrepid(prepids) + ' to next status?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/next_status',
                             data: {'prepid': prepids}})
      };

      $scope.forcecomplete = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        let message = 'Are you sure you want to add ' + $scope.promptPrepid(prepids) + ' to force complete list?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/add_forcecomplete',
                             data: {'prepid': prepids}})
      };

      $scope.updateStats = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selectedItems : [prepid];
        $scope.objectAction(undefined,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/update_stats',
                             data: {'prepid': prepids}})
      }

      $scope.toggleSelection = function (prepid) {
        if ($scope.selectedItems.includes(prepid)) {
          $scope.selectedItems = $scope.selectedItems.filter(x => x != prepid);
        } else {
          $scope.selectedItems.push(prepid);
        }
      };

      $scope.toggleAll = function () {
        if ($scope.selectedItems.length != $scope.result.length) {
          $scope.selectedItems = $scope.result.map(x => x.prepid);
        } else {
          $scope.selectedItems = [];
        }
      };

      $scope.approvalIcon = function (value) {
        icons = {
          'none': 'icon-off',
          'validation': 'icon-eye-open',
          'define': 'icon-check',
          'approve': 'icon-share',
          'submit': 'icon-ok'
        }
        if (icons[value]) {
          return icons[value];
        } else {
          return "glyphicon glyphicon-question-sign";
        }
      };

      $scope.statusIcon = function (value) {
        icons = {
          'new': 'icon-edit',
          'validation': 'icon-eye-open',
          'defined': 'icon-check',
          'approved': 'icon-share',
          'submitted': 'icon-inbox',
          'injected': 'icon-envelope',
          'done': 'icon-ok'
        }
        if (icons[value]) {
          return icons[value];
        } else {
          return "glyphicon glyphicon-question-sign";
        }
      };

      /* Notify modal actions */
      $scope.openNotifyModal = function (prepid) {

        if (!prepid) {
          prepid = $scope.selected_prepids;
        }
        if (_.isString(prepid)) {
          prepid = [prepid]
        }
        var notifyModal = $uibModal.open({
          templateUrl: 'notifyModal.html',
          controller: NotifyModalInstance
        });

        notifyModal.result.then(function (text) {
          $http({ method: 'PUT', url: 'restapi/' + $scope.database + '/notify/', data: JSON.stringify({ prepids: prepid, message: text }) }).success(function (data, status) {

            $scope.update["success"] = true;
            $scope.update["fail"] = false;
            $scope.update["status_code"] = status;
            $scope.update["message"] = data[0]["message"];
            $scope.selected_prepids = [];

          }).error(function (data, status) {
            $scope.setFailure(status);
          });
        })
      };


      $scope.openCloneRequestModal = function (request) {
        const modal = $uibModal.open({
          templateUrl: 'cloneRequestModal.html',
          controller: function ($http, $scope, $uibModalInstance, request, pwgs, errorModal) {
            $scope.vars = {
              pwg: '',
              campaign: ''
            };
            $scope.request = request;
            $scope.allPWGs = [];
            $scope.allCampaigns = [];
            $scope.allPWGs = pwgs;
            $scope.vars.pwg = $scope.allPWGs[0];
            $http.get("search?db_name=campaigns&status=started&page=-1&include_fields=prepid&root=0,-1").then(function (data) {
              $scope.allCampaigns = data.data.results.map(x => x.prepid);
              $scope.vars.campaign = $scope.allCampaigns[0];
            });
            $scope.clone = function () {
              // Shallow copy!
              let clone = Object.assign({}, request);
              clone["member_of_campaign"] = $scope.vars["campaign"];
              clone["pwg"] = $scope.vars["pwg"];
              $http({ method: 'PUT', url: 'restapi/requests/clone/', data: clone }).then(function (data) {
                if (data.data.results) {
                  $window.location.href = 'edit?db_name=requests&prepid=' + data.data.prepid;
                } else {
                  errorModal(data.data.prepid, data.data.message);
                }
              }, function (data) {
                errorModal(data.data.prepid, data.data.message);
              });
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            request: function () { return request; },
            pwgs: function () { return $scope.user.pwgs },
            errorModal: function () { return $scope.openErrorModal; },
          }
        });
      };

      /* --Modals actions END--*/

      $scope.findToken = function (tok) {
        $window.location.href = "requests?&tags=" + tok.value
      };

      $scope.openOnlySelected = function () {
        if ($scope.selected_prepids.length > 0) {
          $scope.upload({ "contents": $scope.selected_prepids.join("\n") });
          $scope.file_was_uploaded = false;
        }
      };

      $scope.getLinktoDmytro = function (wf_data, prepid, text) {
        // return a link to computings private monitoring of requests url:
        // https://dmytro.web.cern.ch/dmytro/cmsprodmon/workflows.php?prep_id=
        var base_link = "https://dmytro.web.cern.ch/dmytro/cmsprodmon/workflows.php?prep_id="
        if (wf_data[wf_data.length - 1]) { //we check if wf exists...
          var name = wf_data[wf_data.length - 1]["name"];
          var prepid = name.slice(
            name.indexOf("-") - 3,
            name.lastIndexOf("-") + 6); //-3 for PWG +6 for '-numerical_id'

          if (name.indexOf("task") != -1) //we check if it was a taskchain
          {
            return base_link + "task_" + prepid;
          }
          else {
            return base_link + prepid;
          }
        }
        else {
          return "";
        }
      };
    }]);

var NotifyModalInstance = function ($scope, $uibModalInstance) {
  $scope.data = { text: "" };

  $scope.notify = function () {
    $uibModalInstance.close($scope.data.text);
  };

  $scope.close = function () {
    $uibModalInstance.dismiss();
  };
};

mcmApp.directive("loadFields", function ($http, $location) {
  return {
    replace: true,
    restrict: 'E',
    template:
      '<div>' +
      '  <form class="form-inline">' +
      '    <span class="control-group navigation-form" ng-repeat="key in searchable_fields">' +
      '      <label style="width:140px;">{{key}}</label>' +
      '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">' +
      '    </span>' +
      '  </form>' +
      '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>' +
      '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="glyphicon glyphicon-question-sign"></i></a>' +
      '</div>'
    ,
    link: function (scope, element, attr) {
      scope.listfields = {};
      scope.showUrl = false;
      scope.is_prepid_in_url = $location.search()["prepid"];
      scope.test_values = [];
      scope.test_data = "";

      scope.searchable_fields = [
        'status',
        'member_of_chain',
        'prepid',
        'extension',
        'tags',
        'energy',
        'mcdb_id',
        'flown_with',
        'pwg',
        'process_string',
        'generators',
        'member_of_campaign',
        'approval',
        'dataset_name'
      ];

      scope.cleanSearchUrl = function () {
        _.each($location.search(), function (elem, key) {
          $location.search(key, null);
        });
        $location.search("page", 0);
      };

      scope.getUrl = function () {
        scope.cleanSearchUrl();
        //var url = "?";
        _.each(scope.listfields, function (value, key) {
          if (value != "") {
            //url += key +"=" +value+"&";
            $location.search(key, String(value));
          } else {
            $location.search(key, null);//.remove(key);
          }
        });
        scope.getData();
      };

      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        var searchURL = "restapi/requests/unique_values/" + fieldName + "?key=" + fieldValue;
        var promise = $http.get(searchURL);
        return promise.then(function (data) {
          return data.data.results;
        }, function (data) {
          alert("Error getting suggestions for " + fieldName + "=" + fieldValue + ": " + data.status);
        });
      };
    }
  }
});

mcmApp.directive("customActorList", function ($http) {
  return {
    restrict: 'EA',
    template:
      '<span>' +
      '  <a ng-href="#" ng-click="getActors();" tooltip-html-unsafe="{{actors}}" tooltip-trigger="click" tooltip-placement="bottom">' +
      '    <i class="glyphicon glyphicon-user"></i>' +
      '  </a>' +
      '</span>',
    link: function (scope, element, attrs) {
      scope.actors = "<ul> </ul>";
      scope.prepid = scope.$eval(attrs.prepid);
      scope.getActors = function () {
        if (scope.actors == "<ul> </ul>") {
          var promise = $http.get("public/restapi/requests/get_actors/" + scope.prepid);
          promise.then(function (data) {
            scope.actors = "<ul>";
            _.each(data.data, function (user) {
              tmp = "<li>" + "<a href='users?page=0&username=" + user + "' target='_blank'>" + user + "</a>" + "</li>";
              scope.actors += tmp;
            });
            scope.actors += "</ul>"
          }, function (data) {
            alert("Error getting actor list: ", data.data.results);
          });
        }
      }
    }
  }
});

mcmApp.directive("fragmentDisplay", function ($http) {
  return {
    require: 'ngModel',
    template:
    `<div ng-show="fragment && fragment.length">
      <a ng-show="!showFragment" title="Show fragment" ng-click="toggleShow();">
        <i class="glyphicon glyphicon-eye-open"></i>
      </a>
      <a ng-show="showFragment" title="Hide fragment" ng-click="toggleShow();">
        <i class="glyphicon glyphicon-eye-close"></i>
      </a>
      <a ng-href="public/restapi/requests/get_fragment/{{prepid}}" title="Open fragment in new tab" target="_blank">
        <i class="glyphicon glyphicon-fullscreen"></i>
      </a>
      <div ng-show="showFragment">
        <textarea class="fragment" style="width: 100%; min-height: 50px;" ng-model="fragment"></textarea>
      </div>
    </div>`,
    link: function (scope, element, attr, ctrl) {
      ctrl.$render = function () {
        scope.fragment = ctrl.$viewValue;
        scope.prepid = scope.$eval(attr.prepid);
        scope.showFragment = false;
        scope.textarea = element[0].querySelector('textarea.fragment');
        scope.editor = undefined;
      };
      scope.toggleShow = function () {
        if (!scope.editor) {
          scope.editor = CodeMirror.fromTextArea(scope.textarea,
            {
              'readOnly': true,
              'lineNumbers': false,
              'indentWithTabs': true,
              'height': 'fit-content',
              'viewportMargin': Infinity,
              'theme': 'eclipse',
              'value': scope.fragment,
            });
          scope.editor.setValue(scope.fragment);
        }
        scope.showFragment = !scope.showFragment;
        if (scope.showFragment) {
          setTimeout(() => {
            scope.editor.setSize(null, 'fit-content');
            scope.editor.refresh();
          }, 10);
        }
      };
    }
  }
});
