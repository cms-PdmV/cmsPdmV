angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {
      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Approval', select: true, db_name: 'approval' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Dataset name', select: true, db_name: 'dataset_name' },
        { text: 'History', select: true, db_name: 'history' },
        { text: 'Tags', select: true, db_name: 'tags' }
      ];

      $scope.dbName = "requests";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.underscore = _;
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
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/reset',
                             data: {'prepid': prepids}})
      }

      $scope.softReset = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to soft reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/soft_reset',
                             data: {'prepid': prepids}})
      }

      $scope.optionReset = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to option reset ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/option_reset',
                             data: {'prepid': prepids}})
      }

      $scope.nextStatus = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to move ' + $scope.promptPrepid(prepids) + ' to next status?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/next_status',
                             data: {'prepid': prepids}})
      };

      $scope.forcecomplete = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to add ' + $scope.promptPrepid(prepids) + ' to force complete list?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/requests/add_forcecomplete',
                             data: {'prepid': prepids}})
      };

      $scope.selected_prepids = [];
      $scope.add_to_selected_list = function (prepid) {
        if (_.contains($scope.selected_prepids, prepid)) {
          $scope.selected_prepids = _.without($scope.selected_prepids, prepid);
        } else {
          $scope.selected_prepids.push(prepid);
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
          return "icon-question-sign";
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
          return "icon-question-sign";
        }
      };

      $scope.toggleAll = function () {
        if ($scope.selected_prepids.length != $scope.result.length) {
          _.each($scope.result, function (v) {
            $scope.selected_prepids.push(v.prepid);
          });
          $scope.selected_prepids = _.uniq($scope.selected_prepids);
        } else {
          $scope.selected_prepids = [];
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
        var notifyModal = $modal.open({
          templateUrl: 'notifyModal.html',
          controller: NotifyModalInstance
        });

        notifyModal.result.then(function (text) {
          $http({ method: 'PUT', url: 'restapi/' + $scope.dbName + '/notify/', data: JSON.stringify({ prepids: prepid, message: text }) }).success(function (data, status) {

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
        const modal = $modal.open({
          templateUrl: 'cloneRequestModal.html',
          controller: function ($http, $scope, $modalInstance, request, pwgs, errorModal, setSuccess) {
            $scope.vars = {
              pwg: '',
              campaign: ''
            };
            $scope.request = request;
            $scope.allPWGs = [];
            $scope.allCampaigns = [];
            $scope.allPWGs = pwgs;
            $scope.vars.pwg = $scope.allPWGs[0];
            $http.get("search?db_name=campaigns&status=started&page=-1").then(function (data) {
              $scope.allCampaigns = data.data.results.map(x => x.prepid);
              $scope.vars.campaign = $scope.allCampaigns[0];
            });
            $scope.clone = function () {
              // Shallow copy!
              let clone = Object.assign({}, request);
              clone["member_of_campaign"] = $scope.vars["campaign"];
              clone["pwg"] = $scope.vars["pwg"];
              $http({ method: 'PUT', url: 'restapi/requests/clone/', data: clone }).success(function (data, status) {
                setSuccess(data["results"]);
                if (data.results) {
                  $window.location.href = 'edit?db_name=requests&query=' + data.prepid;
                } else {
                  errorModal(data.prepid, data['message']);
                  setSuccess(false, status);
                }
              }).error(function (data, status) {
                errorModal(data.prepid, data['message']);
                setSuccess(false, status);
              });
              $modalInstance.close();
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            request: function () { return request; },
            pwgs: function () { return $scope.user.pwgs },
            errorModal: function () { return $scope.openErrorModal; },
            setSuccess: function () { return $scope.setSuccess; },
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

var NotifyModalInstance = function ($scope, $modalInstance) {
  $scope.data = { text: "" };

  $scope.notify = function () {
    $modalInstance.close($scope.data.text);
  };

  $scope.close = function () {
    $modalInstance.dismiss();
  };
};

testApp.directive("generatorParams", function ($http) {
  return {
    require: 'ngModel',
    template:
      '<div>' +
      '  <ul ng-repeat="param in all_data" ng-switch on="$index < all_data.length-1">' +
      '    <li ng-switch-when="true">' +
      '      <a ng-click="viewOldGenParam($index)" ng-hide="display_list.indexOf($index) != -1"><i class="icon-eye-open"></i></a>' +  //elements to be viewed on-click
      '      <a ng-click="viewOldGenParam($index)" ng-show="display_list.indexOf($index) != -1"><i class="icon-eye-close"></i></a>' +  //elements to be viewed on-click
      '      <span ng-show="display_list.indexOf($index) != -1">' + //if index in list of possible views -> then display
      '        <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;">' +
      '          <dt>{{"version"}}</dt>' +
      '          <dd class="clearfix">{{param["version"]}}</dd>' +
      '          <dt>{{"cross section"}}</dt>' +
      '          <dd class="clearfix">{{param["cross_section"]}}' +
      '          <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>' +
      '          </dd>' +
      '          <dt>{{"filter efficiency"}}</dt>' +
      '          <dd class="clearfix">{{param["filter_efficiency"]}}</dd>' +
      '          <dt>{{"filter efficiency error"}}</dt>' +
      '          <dd class="clearfix">{{param["filter_efficiency_error"]}}</dd>' +
      '          <dt>{{"match efficiency"}}</dt>' +
      '          <dd class="clearfix">{{param["match_efficiency"]}}</dd>' +
      '          <dt>{{"match efficiency error"}}</dt>' +
      '          <dd class="clearfix">{{param["match_efficiency_error"]}}</dd>' +
      '          <dt>{{"author username"}}</dt>' +
      '          <dd class="clearfix">{{param["submission_details"]["author_username"]}}</dd>' +
      '        </dl>' +
      '      </span>' +
      '    </li>' +
      '    <li ng-switch-when="false">' + //last parameter to be displayed all the time
      '      <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;">' +
      '        <dt>{{"version"}}</dt>' +
      '        <dd class="clearfix">{{param["version"]}}</dd>' +
      '        <dt>{{"cross section"}}</dt>' +
      '        <dd class="clearfix">{{param["cross_section"]}}' +
      '          <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>' +
      '        </dd>' +
      '        <dt>{{"filter efficiency"}}</dt>' +
      '        <dd class="clearfix">{{param["filter_efficiency"]}}</dd>' +
      '        <dt>{{"filter efficiency error"}}</dt>' +
      '        <dd class="clearfix">{{param["filter_efficiency_error"]}}</dd>' +
      '        <dt>{{"match efficiency"}}</dt>' +
      '        <dd class="clearfix">{{param["match_efficiency"]}}</dd>' +
      '        <dt>{{"match efficiency error"}}</dt>' +
      '        <dd class="clearfix">{{param["match_efficiency_error"]}}</dd>' +
      '        <dt>{{"negative weights fraction"}}</dt>' +
      '        <dd class="clearfix">{{param["negative_weights_fraction"]}}</dd>' +
      '        <dt>{{"author username"}}</dt>' +
      '        <dd class="clearfix">{{param["submission_details"]["author_username"]}}</dd>' +
      '      </dl>' +
      '    </li>' +
      '  </ul>' +
      '</div>',
    link: function (scope, element, attrs, ctrl) {
      ctrl.$render = function () {
        scope.all_data = ctrl.$viewValue;
        scope.display_list = [_.size(scope.all_data) - 1];
        scope.last_param = scope.all_data[_.size(scope.all_data) - 1];
      };
      scope.viewOldGenParam = function (index) {
        if (_.contains(scope.display_list, index)) {
          scope.display_list = _.without(scope.display_list, index)
        } else {
          scope.display_list.push(index);
        }
        scope.display_list = _.uniq(scope.display_list);
      };
    }
  };
});

testApp.directive("loadFields", function ($http, $location) {
  return {
    replace: true,
    restrict: 'E',
    template:
      '<div>' +
      '  <form class="form-inline">' +
      '    <span class="control-group navigation-form" bindonce="searchable" ng-repeat="key in searchable_fields">' +
      '      <label style="width:140px;">{{key}}</label>' +
      '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">' +
      '    </span>' +
      '  </form>' +
      '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>' +
      '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>' +
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

testApp.directive("customActorList", function ($http) {
  return {
    restrict: 'EA',
    template:
      '<span>' +
      '  <a ng-href="#" ng-click="getActors();" tooltip-html-unsafe="{{actors}}" tooltip-trigger="click" tooltip-placement="bottom">' +
      '    <i class="icon-user"></i>' +
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

testApp.directive("fragmentDisplay", function ($http) {
  return {
    require: 'ngModel',
    template:
      '<div ng-show="fragment && fragment.length">' +
      '  <a ng-show="!show_fragment" rel="tooltip" title="Show fragment" ng-click="showFragment();">' +
      '    <i class="icon-eye-open"></i>' +
      '  </a>' +
      '  <a ng-show="show_fragment" rel="tooltip" title="Hide fragment" ng-click="show_fragment = false;">' +
      '    <i class="icon-remove"></i>' +
      '  </a>' +
      '  <a ng-href="public/restapi/requests/get_fragment/{{prepid}}/0" rel="tooltip" title="Open fragment in new tab" target="_blank">' +
      '    <i class="icon-fullscreen"></i>' +
      '  </a>' +
      '  <div ng-show="show_fragment">' +
      '    <textarea ui-codemirror="{ theme:\'eclipse\', readOnly:true}" ui-refresh=true ng-model="fragment"></textarea>' +
      '  </div>' +
      '</div>',
    link: function (scope, element, attrs, ctrl) {
      ctrl.$render = function () {
        scope.show_fragment = false;
        scope.prepid = ctrl.$viewValue;
        scope.fragment = attrs.rawfragment;
        scope.refreshedEditor = false;
      };
      scope.showFragment = function () {
        scope.show_fragment = true;
        if (!scope.refreshedEditor) {
          scope.refreshedEditor = true;
          setTimeout(() => {
            const textarea = angular.element(element)[0].querySelector('textarea');
            const editor = CodeMirror.fromTextArea(textarea);
            editor.setSize(null, 'auto');
            editor.refresh();
          }, 100);
        }
      };
    }
  }
});
