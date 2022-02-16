let mcmApp = angular.module('mcmApp', ['ui.bootstrap']).config(function ($locationProvider) { $locationProvider.html5Mode({ enabled: true, requireBase: false }); });

angular.module('mcmApp').controller('mainController',
  ['$scope', '$http', '$location', '$window', '$uibModal',
    function mainController($scope, $http, $location, $window, $uibModal) {
      $scope.database = undefined;
      $scope.columns = undefined;
      $scope.actionMessage = {};
      $scope.user = {};
      $scope.initialGetData = true;

      let urlParams = $location.search();
      let limit = parseInt(urlParams['limit']);
      $scope.limit = limit && limit > 0 ? limit : 20;

      let page = parseInt(urlParams["page"]);
      $scope.page = page && page >= 0 ? page : 0;

      $scope.updatePageLimit = function() {
        setTimeout(() => {
          $scope.updateQuery({'page': $scope.page != 0 ? $scope.page : undefined,
                             'limit': $scope.limit != 20 ? $scope.limit : undefined});
        }, 0);
      };
      $scope.changeLimit = function (limit) {
        $scope.limit = limit;
        $scope.updatePageLimit();
        $scope.getData($scope.database);
      };
      $scope.nextPage = function() {
        $scope.page = $scope.page + 1;
        $scope.updatePageLimit();
        $scope.getData($scope.database);
      };
      $scope.previousPage = function() {
        $scope.page = Math.max(0, $scope.page - 1);
        $scope.updatePageLimit();
        $scope.getData($scope.database);
      }

      // Get user details
      $http.get('restapi/users/get').then(function (data) {
        $scope.user.username = data.data.username;
        $scope.user.fullname = data.data.user_name;
        $scope.user.role = data.data.role;
        $scope.user.pwgs = data.data.pwgs;
        const roles = ['anonymous',
                       'user',
                       'mc_contact',
                       'generator_convener',
                       'production_manager',
                       'production_expert',
                       'administrator'];
        for (let role of roles) {
          $scope.user['is_' + role] = roles.indexOf(role) <= roles.indexOf(data.data.role);
        }
      }, function (data) {
        $scope.openErrorModal(undefined, 'Could not get user details: ' + data.status);
      });

      $scope.isArray = function(x) {
        return Array.isArray(x);
      }

      $scope.setDatabaseInfo = function(database, columns) {
        $scope.database = database;
        $scope.columns = columns;
      }

      $scope.objectAction = function (message, prepids, httpDict) {
        const action = function(prepids, httpDict) {
          $scope.setLoading(prepids, true);
          $http(httpDict).then(function (results) {
            results = results.data;
            let shouldGetData = false;
            if (!Array.isArray(results)) {
              results = [results];
            }
            for (let result of results) {
              $scope.actionMessage[result.prepid] = result.results ? 'OK' : result.message;
              shouldGetData = shouldGetData || !!result.results;
            }
            if (shouldGetData) {
              $scope.getData();
            }
          }, function (data) {
            $scope.openErrorModal(prepids.length == 1 ? prepids[0] : undefined, data['message']);
            $scope.setLoading(prepids, false);
          });
        }
        if (message != undefined) {
          $scope.questionModal(message, function() {
            action(prepids, httpDict);
          });
        } else {
          action(prepids, httpDict);
        }
      };

      $scope.questionModal = function (question, callback) {
        const modal = $uibModal.open({
          templateUrl: 'questionModal.html',
          controller: function ($scope, $uibModalInstance, question) {
            $scope.question = question;
            $scope.yes = function () { $uibModalInstance.close(); };
            $scope.no = function () { $uibModalInstance.dismiss(); };
          },
          resolve: {
            question: function () { return question; }
          }
        });
        modal.result.then(function () { callback(); });
      };

      $scope.deleteObject = function (prepid) {
        let message = 'Are you sure you want to delete ' + prepid + '?';
        $scope.objectAction(message,
                            [prepid],
                            {method: 'DELETE',
                             url: 'restapi/' + $scope.database + '/delete/' + prepid})
      };

      $scope.promptPrepid = function(prepids) {
        let name = $scope.database.replaceAll('_', ' ');
        return prepids.length == 1 ? prepids[0] : (prepids.length + ' ' + name);
      }

      $scope.setLoading = function(prepids, loading) {
        for (let prepid of prepids) {
          $scope.actionMessage[prepid] = loading ? 'loading' : '';
        }
      }

      $scope.isDevMachine = function () {
        const isDev = $location.host().indexOf('dev') != -1;
        if (isDev) {
          const body = document.getElementsByTagName('body');
          for (let elem of body) {
            // elem.style.backgroundImage = 'url(HTML/draft.png)';
            elem.classList.add('dev-ribbon');
          }
        }
        return isDev;
      };

      $scope.dictIsEmptry = function(dict) {
        return !dict || Object.keys(dict).length == 0;
      };

      $scope.numberWithCommas = function (x) {
        if (x) {
          var parts = x.toString().split(".");
          parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
          return parts.join(".");
        } else {
          return x;
        }
      };

      $scope.sequenceName = function(sequences, index) {
        return sequences[index].datatier.length ? sequences[index].datatier.join(',') : ('Sequence ' + (index + 1));
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
      };

      $scope.updateQuery = function(params) {
        let urlParams = Object.fromEntries(new URLSearchParams(window.location.search));
        urlParams = Object.assign({}, urlParams, params);
        Object.keys(urlParams).forEach(key => urlParams[key] === undefined && delete urlParams[key]);
        let urlQuery = new URLSearchParams(urlParams).toString();
        if (urlQuery) {
          urlQuery = '?' + urlQuery;
          urlQuery = decodeURI(urlQuery);
        }
        let newUrl = window.location.protocol + '//' + window.location.host + window.location.pathname + urlQuery;
        window.history.replaceState({path: newUrl}, '', newUrl);
      };

      /* Support modal actions*/

      $scope.openSupportModal = function () {
        $uibModal.open({
          templateUrl: "supportModal.html",
          controller: function ($scope, $uibModalInstance) {
            $scope.close = function () {
              $uibModalInstance.close();
            }
          }
        });
      };

      $scope.openErrorModal = function (prepid, message) {
        const modal = $uibModal.open({
          templateUrl: 'errorModal.html',
          controller: function ($scope, $uibModalInstance, prepid, message) {
            $scope.prepid = prepid;
            $scope.message = message;
            $scope.ok = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            prepid: function () {
              return prepid;
            },
            message: function () {
              return message;
            }
          }
        });
      };

      $scope.upload = function (file) {
        /*Upload a file to server*/
        $scope.got_results = false;
        $scope.resultsFromFile = true;
        $http({ method: 'PUT', url: 'restapi/' + $scope.database + '/listwithfile', data: file }).success(function (data, status) {
          $scope.result = data.results;
          $scope.result_status = data.status;
          $scope.got_results = true;
          $scope.totalRows = data.results.length;
          if ($scope.result.length != 0) {
            columns = Object.keys($scope.result[0]);
            let defaultColumns = new Set($scope.columns.map(x => x.db_name));

            columns.filter(x => x[0] != '_' && !defaultColumns.has(x))
                   .sort()
                   .map(x => Object({'text': x[0].toUpperCase() + x.substring(1).replaceAll('_', ' '),
                                     'select': false,
                                     'db_name': x }))
                   .map(function(c) { $scope.columns.push(c)});
          }

          $scope.selectionReady = true;
        }).error(function (data, status) {
          $scope.setSuccess(false, data.message);
        });
      };

      $scope.getData = function () {
        $scope.initialGetData = false;
        if ($scope.file_was_uploaded) {
          $scope.upload($scope.uploaded_file);
        } else {
          if (!$scope.database) {
            return;
          }
          let query = [`search?db_name=${$scope.database}&page=${$scope.page}&limit=${$scope.limit}`];
          let search = $location.search();
          for (let key in search) {
            if (key != 'shown' && key != 'page' && key != 'limit') {
              query.push(`${key}=${search[key]}`)
            }
          }
          $scope.loading = true;
          $scope.resultsFromFile = false;
          $http.get(query.join('&')).then(function (data) {
            $scope.result = data.data.results;
            if ($scope.result.length != 0) {
              columns = Object.keys($scope.result[0]);
              let defaultColumns = new Set($scope.columns.map(x => x.db_name))
              columns.filter(x => x[0] != '_' && !defaultColumns.has(x))
                     .sort()
                     .map(x => Object({'text': x[0].toUpperCase() + x.substring(1).replaceAll('_', ' '),
                                       'select': false,
                                       'db_name': x }))
                     .map(function(c) { $scope.columns.push(c)});
            }
            $scope.totalRows = data.data.total_rows;
            $scope.pageStart = $scope.totalRows == 0 ? 0 : $scope.page * $scope.limit + 1;
            $scope.pageEnd = Math.min($scope.totalRows, $scope.page * $scope.limit + $scope.limit);
            $scope.loading = false;
          }, function (data) {
            $scope.loading = false;
            $scope.openErrorModal(undefined, data.message);
            $scope.setSuccess(false, data.message ? data.message : 'Error loading results');
          });
        }
      };

      $scope.$watch(function () {
        let query = $location.search();
        let queryString = Object.keys(query).filter(k => !['shown', 'limit', 'page'].includes(k)).sort().map(k => `${k}=${query[k]}`).join('&');
        return queryString;
      },
        function () {
          let query = $location.search();
          let queryString = Object.keys(query).filter(k => !['shown', 'limit', 'page'].includes(k)).sort().map(k => `${k}=${query[k]}`).join('&');
          if (!$scope.initialGetData) {
            $scope.page = 0;
          }
          $scope.updatePageLimit();
          $scope.getData($scope.database);
        }
      );

      $scope.openCloneItemModal = function (database, prepid) {
        const modal = $uibModal.open({
          templateUrl: 'cloneItemModal.html',
          controller: function ($scope, $uibModalInstance, $window, $http, database, prepid, errorModal) {
            $scope.prepid = prepid;
            $scope.vars = {'newPrepid': ''};
            $scope.objectName = database.substr(0, database.length - 1).replaceAll('_', ' ');
            $scope.clone = function () {
              let itemData = {'prepid': prepid, 'new_prepid': $scope.vars.newPrepid};
              $http({ method: 'PUT', url: 'restapi/' + database + '/clone', data: itemData }).then(function (data) {
                if (data.data.results) {
                  $window.location.href = 'edit?db_name=' + database + '&prepid=' + data.data.prepid;
                } else {
                  errorModal(data.data.prepid, data.data.message);
                }
              }).error(function (data, status) {
                errorModal(data.data.prepid, data.data.message);
              });
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            prepid: function () { return prepid; },
            database: function () { return database; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };

      $scope.openCreateItemModal = function (database) {
        $uibModal.open({
          templateUrl: 'createItemModal.html',
          controller: function ($scope, $uibModalInstance, database, errorModal) {
            $scope.vars = {'prepid': ''};
            $scope.objectName = database.substr(0, database.length - 1).replaceAll('_', ' ');
            $scope.save = function () {
              let itemData = {'prepid': $scope.vars.prepid };
              $http({ method: 'PUT', url: 'restapi/' + database + '/save', 'data': itemData }).then(function (data) {
                if (data.data.results) {
                  $window.location.href = 'edit?db_name=' + database + '&prepid=' + data.data.prepid;
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
            database: function () { return database; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };
    }
  ]);


mcmApp.directive('ddlFileReader', function ($http, $rootScope) {
  return {
    require: "ngModel",
    replace: true,
    restrict: 'E',
    link: function (scope, element, attrs, ctrl) {

      element.bind("change", function (ev) {
        var files = ev.target.files;
        var file = files.length ? files[0] : null;

        if (!file) {
          ctrl.$setViewValue(null);
          return;
        }

        // Closure to capture the file information.
        var reader = new FileReader();
        reader.onload = function (e) {
          scope.$apply(function () {
            ctrl.$setViewValue({ f: file, contents: e.target.result });
          });
        };

        reader.readAsText(file);
      });

    },
    template: '<input type="file" class="input" />'
  }
});

/*
Angular-UI panes/tab directive with local customisation
http://angular-ui.github.io/bootstrap/
*/
mcmApp.controller('TabsController', ['$scope', '$element', function ($scope, $element) {
  var panes = $scope.panes = [];

  this.select = $scope.select = function selectPane(pane) {
    if (pane.selected == true) { //if pane is clicked while open -> close pane to save space
      pane.selected = false;
      pane.active = false;
    } else { //else if it was closed-> open clicked pane by closing all and opening the current one
      angular.forEach(panes, function (pane) {
        pane.selected = false;
        pane.active = false;
      });
      pane.selected = true;
      pane.active = true;
    }
    event.preventDefault();
  };

  this.addPane = function addPane(pane) {
    //if (!panes.length) {
    //  $scope.select(pane);
    //}
    panes.push(pane);
  };

  this.removePane = function removePane(pane) {
    var index = panes.indexOf(pane);
    panes.splice(index, 1);
    //Select a new pane if removed pane was selected
    if (pane.selected && panes.length > 0) {
      $scope.select(panes[index < panes.length ? index : index - 1]);
    }
  };
}]);
mcmApp.directive('tabs', function () {
  return {
    restrict: 'EA',
    transclude: true,
    scope: {
    },
    controller: 'TabsController',
    template:
      "<div class=\"tabbable\">\n" +
      "  <ul class=\"nav nav-tabs\">\n" +
      "    <li ng-repeat=\"pane in panes\" ng-class=\"{active:pane.selected}\">\n" +
      "      <a ng-click=\"select(pane)\" ng-href=\"#\">{{pane.heading}}</a>\n" +
      "    </li>\n" +
      "  </ul>{{result}}\n" +
      "  <div class=\"tab-content\" ng-transclude></div>\n" +
      "</div>\n",
    replace: true
  };
});
mcmApp.directive('pane', ['$parse', function ($parse) {
  return {
    require: '^tabs',
    restrict: 'EA',
    transclude: true,
    scope: {
      heading: '@',
      active: '='
    },
    link: function (scope, element, attrs, tabsCtrl) {
      var getSelected, setSelected;
      scope.selected = false;
      if (attrs.active) {
        getSelected = $parse(attrs.active);
        setSelected = getSelected.assign;
        scope.$watch(
          function watchSelected() { return getSelected(scope.$parent); },
          function updateSelected(value) { scope.selected = value; }
        );
        scope.selected = getSelected ? getSelected(scope.$parent) : false;
      }
      //  scope.$watch('selected', function(selected) {
      //if(selected) {
      //tabsCtrl.select(scope); //lame original watch
      //}
      //    if(setSelected) {
      //      setSelected(scope.$parent, selected);
      //    }
      //  });

      tabsCtrl.addPane(scope);
      scope.$on('$destroy', function () {
        tabsCtrl.removePane(scope);
      });
    },
    template: "<div class=\"tab-pane\" ng-class=\"{active: selected}\" ng-show=\"selected\" ng-transclude></div>\n",
    replace: true
  };
}]);

mcmApp.constant('buttonConfig', {
  activeClass: 'active',
  toggleEvent: 'click'
})
  .directive('btnRadio', ['buttonConfig', function (buttonConfig) {
    var activeClass = buttonConfig.activeClass || 'active';
    var toggleEvent = buttonConfig.toggleEvent || 'click';
    return {
      require: 'ngModel',
      link: function (scope, element, attrs, ngModelCtrl) {
        //model -> UI
        ngModelCtrl.$render = function () {
          element.toggleClass(activeClass, angular.equals(ngModelCtrl.$modelValue, scope.$eval(attrs.btnRadio)));
        };
        //ui->model
        element.bind(toggleEvent, function () {
          if (!element.hasClass(activeClass)) {
            scope.$apply(function () {
              ngModelCtrl.$setViewValue(scope.$eval(attrs.btnRadio));
              ngModelCtrl.$render();
            });
          }
        });
      }
    };
  }])
  .directive('btnCheckbox', ['buttonConfig', function (buttonConfig) {
    var activeClass = buttonConfig.activeClass || 'active';
    var toggleEvent = buttonConfig.toggleEvent || 'click';
    return {
      require: 'ngModel',
      link: function (scope, element, attrs, ngModelCtrl) {
        function getTrueValue() {
          var trueValue = scope.$eval(attrs.btnCheckboxTrue);
          return angular.isDefined(trueValue) ? trueValue : true;
        }
        function getFalseValue() {
          var falseValue = scope.$eval(attrs.btnCheckboxFalse);
          return angular.isDefined(falseValue) ? falseValue : false;
        }
        //model -> UI
        ngModelCtrl.$render = function () {
          element.toggleClass(activeClass, angular.equals(ngModelCtrl.$modelValue, getTrueValue()));
        };
        //ui->model
        element.bind(toggleEvent, function () {
          scope.$apply(function () {
            ngModelCtrl.$setViewValue(element.hasClass(activeClass) ? getFalseValue() : getTrueValue());
            ngModelCtrl.$render();
          });
        });
      }
    };
  }]);

mcmApp.directive('dropdownToggle', ['$document', '$location', function ($document, $location) {
  var openElement = null,
    closeMenu = angular.noop;
  return {
    restrict: 'CA',
    link: function (scope, element, attrs) {
      scope.$watch('$location.path', function () { closeMenu(); });
      element.parent().bind('click', function () { closeMenu(); });
      element.bind('click', function (event) {

        var elementWasOpen = (element === openElement);

        event.preventDefault();
        event.stopPropagation();

        if (!!openElement) {
          closeMenu();
        }

        if (!elementWasOpen) {
          element.parent().addClass('open');
          openElement = element;
          closeMenu = function (event) {
            if (event) {
              event.preventDefault();
              event.stopPropagation();
            }
            $document.unbind('click', closeMenu);
            element.parent().removeClass('open');
            closeMenu = angular.noop;
            openElement = null;
          };
          $document.bind('click', closeMenu);
        }
      });
    }
  };
}]);

mcmApp.directive("reqmgrName", function ($http) {
  return {
    require: 'ngModel',
    restrict: 'E',
    // scope: true,
    templateUrl: 'HTML/templates/request.manager.name.html',
    replace: true,
    reqmgr_name: [],
    link: function (scope, element, attrs, ctrl) {
      scope.links = {};
      scope.image_width = 150;
      ctrl.$render = function () {
        scope.reqmgr_name = ctrl.$viewValue;
        scope.prepid = scope.$eval(attrs.prepid);
      };
      scope.getrqmnr_data = function (reqmgr_name) {
        scope.stats_cache[reqmgr_name] = 'Not found'
        for (var index = 0; index < scope.reqmgr_name.length; index++) {
          reqmgr_name_dict = scope.reqmgr_name[index];
          if (reqmgr_name_dict['name'] === reqmgr_name) {
            if (Object.keys(reqmgr_name_dict['content']).length > 0) {
              scope.stats_cache[reqmgr_name] = reqmgr_name_dict['content']
            }
            break;
          }
        }
      };
      scope.$on('loadDataSet', function (events, values) {
        if (scope.prepid !== values[0]) {
          return
        }
        scope.stats_cache[values[1]] = values[2].content
      });
    }
  }
});

mcmApp.directive("customFooter", function ($location, $compile, $http) {
  return {
    restrict: 'C',
    link: function (scope, element) {
      $http.get('HTML/templates/footer.custom.html').then(function (response) {
        element.append($compile(response.data)(scope));
      });


    }
  }
});

mcmApp.directive('columnSelect', function ($location) {
  return {
    restrict: 'E',
    template:
    `<div class="well" style="padding: 8px; text-align: center;">
      <div class="column-select">
        <div ng-repeat="column in columns track by $index">
          <label class="checkbox inline" style="padding-left:20px;">
            <input type="checkbox" ng-model="column.select" style="margin-left: -15px;">{{column.text}}
          </label>
        </div>
      </div>
      <input type="button" class="btn btn-primary btn-xs" value="Select all" ng-click="selectAll()" ng-hide="selectedCount == columns.length">
      <input type="button" class="btn btn-primary btn-xs" value="Deselect" ng-click="selectAll()" ng-show="selectedCount == columns.length">
    </div>`,
    scope: {
      columns: '=',
      updateQuery: '&'
    },
    link: function ($scope) {
      $scope.selectedCount = 0;
      $scope.previous = [];

      let shown = $location.search()["shown"];
      if (shown) {
        $location.search("shown", shown);
        // Make a binary string interpretation of shown number
        let shownBinary = parseInt(shown).toString(2).split('').reverse().join('');
        for (let index =  0; index < $scope.columns.length; index++) {
          let bit = shownBinary.charAt(index);
          $scope.columns[index].select = bit === '1';
          if (bit === '1') {
            $scope.previous.push($scope.columns[index].db_name);
          }
        }
      }

      $scope.$watch('columns', function () { //on chage of column selection -> recalculate the shown number
        var shownBinary = '';
        var count = 0;
        for (let column of $scope.columns) {
          if (column.select) {
            shownBinary = '1' + shownBinary;
            count++;
          } else {
            shownBinary = '0' + shownBinary;
          }
          $scope.selectedCount = count;
        }
        $scope.updateQuery()({'shown': parseInt(shownBinary, 2)});
      }, true);

      $scope.selectAll = function () {
        if ($scope.selectedCount == $scope.columns.length) {
          $scope.columns.map(x => x.select = $scope.previous.includes(x.db_name));
        } else {
          $scope.previous = $scope.columns.filter(x => x.select).map(x => x.db_name);
          $scope.columns.map(x => x.select = true);
        }
      };
    }
  }

});

mcmApp.directive("customHistory", function () {
  return {
    require: 'ngModel',
    template:
      '<div>' +
      '  <div ng-hide="show_history">' +
      '    <input type="button" value="Show" ng-click="show_history=true;" style="margin: 2px;">' +
      '  </div>' +
      '  <div ng-show="show_history">' +
      '    <input type="button" value="Hide" ng-click="show_history=false;" style="margin: 2px;">' +
      '    <table class="table table-bordered">' +
      '      <thead>' +
      '        <tr>' +
      '          <th style="padding: 1px;">Action</th>' +
      '          <th style="padding: 1px;">Date</th>' +
      '          <th style="padding: 1px;">User</th>' +
      '          <th style="padding: 1px;">Step</th>' +
      '        </tr>' +
      '      </thead>' +
      '      <tbody>' +
      '        <tr ng-repeat="elem in show_info">' +
      '          <td style="padding: 1px;">{{elem.action}}</td>' +
      '          <td style="padding: 1px;">{{elem.updater.submission_date}}</td>' +
      '          <td style="padding: 1px;">' +
      '              <div ng-switch="elem.updater.author_name">' +
      '                <div ng-switch-when="">{{elem.updater.author_username}}</div>' +
      '                <div ng-switch-default>{{elem.updater.author_name}}</div>' +
      '              </div>' +
      '          </td>' +
      '          <td style="padding: 1px; min-width: 75px;">' +
      '            <div>{{elem.step}}</div>' +
      '          </td>' +
      '        </tr>' +
      '      </tbody>' +
      '    </table>' +
      '  </div>' +
      '</div>' +
      '',
    link: function (scope, element, attrs, ctrl) {
      ctrl.$render = function () {
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});

mcmApp.directive("sequenceDisplay", function ($http) {
  return {
    restrict: 'EA',
    template:
    `<div>
      <div ng-hide="showSequences">
        <a title="Show" ng-click="toggleShow();">
          <i class="glyphicon glyphicon-eye-open"></i>
        </a>
      </div>
      <div ng-show="showSequences">
        <img ng-show="loading" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>
        <ul ng-if="database == 'campaigns'">
          <li ng-repeat="(sequenceName, sequences) in sequenceStrings">
            <b>{{sequenceName}}</b>
            <ul>
              <li ng-repeat="sequenceString in sequences">
                <div class="sequence-box" style="width:600px;overflow:auto">{{sequenceString}}</div>
              </li>
            </ul>
          </li>
        </ul>
        <ul ng-if="database == 'requests'">
          <li ng-repeat="sequenceString in sequenceStrings">
            <div class="sequence-box" style="width:600px;overflow:auto">{{sequenceString}}</div>
          </li>
        </ul>
        <a title="Hide" ng-click="toggleShow();">
          <i class="glyphicon glyphicon-eye-close"></i>
        </a>
      </div>
    </div>`,
    scope: {
      prepid: '=',
      database: '=',
    },
    link: function (scope) {

      scope.showSequences = false;;
      scope.sequenceStrings = undefined;
      scope.loading = false;

      scope.toggleShow = function () {
        scope.showSequences = !scope.showSequences;
        if (scope.showSequences && !scope.sequenceStrings) {
          scope.loading = true;
          $http.get("restapi/" + scope.database + "/get_cmsDrivers/" + scope.prepid).then(function (data) {
            scope.sequenceStrings = data.data.results;
            scope.loading = false;
          }, function () {
            scope.loading = false;
          });
        }
      }
    }
  }
});
