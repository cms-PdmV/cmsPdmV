angular.module('testApp').controller('mainCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function mainCtrl($scope, $http, $location, $window, $modal) {
      $scope.stats_cache = {};
      $scope.full_details = {};
      $scope.mcm_revision = "";
      $scope.user = { name: "guest", role: "user", roleIndex: 0 };
      $scope.start_time = "";
      $scope.turn_on_button_clicked = false;
      $scope.math = Math;
      $scope.update = {};
      $scope.dbName = undefined;
      $scope.columns = undefined;

      $scope.setDatabaseInfo = function(database, columns) {
        $scope.dbName = database;
        $scope.columns = columns;
      }

      var promise;
      var get_rev = true;
      _.each(["campaigns", "chained_campaigns", "flows", "actions", "requests", "chained_requests", "batch", "invalidations", "mccms", "dashboard", "users", "edit", "news", "settings"], function (elem) {
        if ($location.path().indexOf(elem) != -1) {
          get_rev = false;
        }
      });
      if (get_rev && $window.document.title != "McM maintenance") {
        promise = $http.get("restapi/dashboard/get_revision");
        promise.then(function (data) {
          $scope.mcm_revision = data.data;
        });
      }
      if ($scope.start_time == "" && $window.document.title != "McM maintenance") {
        promise = $http.get("restapi/dashboard/get_start_time");
        promise.then(function (data) {
          $scope.start_time = data.data.results;
        });
      }

      // GET username and role
      promise = $http.get("restapi/users/get_role", { cache: true });
      promise.then(function (data) {
        $scope.user.name = data.data.username;
        $scope.user.role = data.data.role;
        $scope.user.roleIndex = parseInt(data.data.role_index);
      }, function (data) {
        alert("Error getting user information. Error: " + data.status);
      });
      // Endo of user info request

      $scope.turnOnServer = function () {
        if ($window.document.title == "McM maintenance") {
          $scope.turn_on_button_clicked = true;
          var promise = $http.get("restapi/control/turn_on");
          promise.then(function () {
            alert("Server turned on");
            setTimeout(function () { $window.location.reload() }, 5000);
          }, function () {
            alert("Server failed to turn on");
            $scope.turn_on_button_clicked = false;
            setTimeout(function () { $window.location.reload() }, 1000);
          });
        }
      };

      $scope.isDevMachine = function () {
        is_dev = $location.host().indexOf("dev") != -1;
        if (is_dev) {
          body = document.getElementsByTagName("body");
          _.each(body, function (v) {
            // v.style.backgroundImage = "url(HTML/draft.png)"
          });
        }
        return is_dev;
      };

      //return everyting thats after main url
      $scope.getLocation = function () {
        var __location = $location.url();
        return __location.replace(/page=\d+/g, "").substring(1); //remove 1st character which is / to make a relative link
      };
      //return fullUrl
      $scope.getFullLocation = function () {
        var __location = $location.url();
        return __location.substring(1); //remove 1st character which is / to make a relative link
      };

      $scope.role = function (priority) {
        return priority > $scope.user.roleIndex; //if user.priority < button priority then hide=true
      };
      //watch length of pending HTTP requests -> if there are display loading;
      $scope.$watch(function () { return $http.pendingRequests.length; }, function (v) {
        $scope.pendingHTTPLenght = v;
        if (v == 0) {  //if HTTP requests pending == 0
          $scope.pendingHTTP = false;
        } else
          $scope.pendingHTTP = true;
      });
      $scope.numberWithCommas = function (x) {
        if (x) {
          var parts = x.toString().split(".");
          parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
          return parts.join(".");
        } else {
          return x;
        }
      };

      /* Support modal actions*/

      $scope.openSupportModal = function () {
        $modal.open({
          templateUrl: "supportModal.html",
          controller: function ($scope, $modalInstance) {
            $scope.close = function () {
              $modalInstance.close();
            }
          }
        });
      };

      $scope.openIsSureModal = function (database, prepid, action, callback) {
        const modal = $modal.open({
          templateUrl: 'isSureModal.html',
          controller: function ($scope, $modalInstance, database, prepid, action) {
            $scope.database = database;
            $scope.prepid = prepid;
            $scope.action = action;
            var stringToColor = function (str) {
              //converts any string to hexadecimal color format
              let hash = 0;
              for (var i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
              }
              let color = '#';
              for (i = 0; i < 3; i++) {
                let value = (hash >> (i * 8)) & 0xFF;
                color += ('00' + value.toString(16)).substr(-2);
              }
              return color;
            };
            $scope.color = stringToColor(action);
            $scope.yes = function (database, prepid, action) {
              $modalInstance.close(database, prepid, action);
            };
            $scope.no = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            database: function () {
              return database;
            },
            prepid: function () {
              return prepid;
            },
            action: function () {
              return action;
            }
          }
        });
        modal.result.then(function () {
          callback(database, prepid, action)
        });
      };

      $scope.openErrorModal = function (prepid, message) {
        const modal = $modal.open({
          templateUrl: 'errorModal.html',
          controller: function ($scope, $modalInstance, prepid, message) {
            $scope.prepid = prepid;
            $scope.message = message;
            $scope.ok = function () {
              $modalInstance.dismiss();
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

      $scope.deletePrompt = function (prepid) {
        $scope.openIsSureModal($scope.dbName, prepid, 'delete', function (database, prepid, action) {
          $scope.deleteObject(database, prepid);
        });
      };

      $scope.upload = function (file) {
        /*Upload a file to server*/
        $scope.got_results = false;
        $http({ method: 'PUT', url: 'restapi/' + $scope.dbName + '/listwithfile', data: file }).success(function (data, status) {
          $scope.result = data.results;
          $scope.result_status = data.status;
          $scope.got_results = true;
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
        if ($scope.file_was_uploaded) {
          $scope.upload($scope.uploaded_file);
        }
        else if ($location.search()['range'] != undefined) {
          var tmp = $location.search()['range'].split(";");
          var imaginary_file = [];
          _.each(tmp, function (elem) {
            var ranges = elem.split(",");
            if (ranges.length > 1) {
              imaginary_file.push(ranges[0] + " -> " + ranges[1]);
            } else {
              imaginary_file.push(ranges[0]);
            }
          });
          $scope.upload({ contents: imaginary_file.join("\n") });
          $scope.file_was_uploaded = false;
        } else {
          let query = "";
          _.each($location.search(), function (value, key) {
            if ((key != 'shown') && (key != 'fields')) {
              query += "&" + key + "=" + value;
            }
          });
          $scope.got_results = false; //to display/hide the 'found n results' while reloading
          $http.get("search?" + "db_name=" + $scope.dbName + query + "&get_raw").then(function (data) {
            $scope.got_results = true;
            $scope.result = _.pluck(data.data.rows, 'doc');
            if ($scope.result === undefined) {
              alert('The following url-search key(s) is/are not valid : ' + _.keys(data.data));
              return; //stop doing anything if results are undefined
            }
            $scope.total_results = data.data.total_rows;
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
            $scope.selectionReady = true;
          }, function (data, status) {
            $scope.setSuccess(false, data.message);
          });
        }
      };

      $scope.$watch(function () {
        var loc_dict = $location.search();
        return "page" + loc_dict["page"] + "limit" + loc_dict["limit"];
      },
        function () {
          $scope.getData($scope.dbName);
        }
      );

      $scope.setSuccess = function (success, code) {
        $scope.update['success'] = !!success;
        $scope.update['status_code'] = code;
      }

      $scope.deleteObject = function (db, prepid) {
        $http({ method: 'DELETE', url: 'restapi/' + db + '/delete/' + prepid }).success(function (data, status) {
          $scope.setSuccess(data["results"]);
          if (data["results"]) {
            $scope.getData();
          } else {
            $scope.openErrorModal(prepid, data['message']);
          }
        }).error(function (status) {
          $scope.openErrorModal(prepid, data['message']);
          $scope.setSuccess(false, status);
        });
      };

      $scope.openCloneItemModal = function (database, prepid) {
        const modal = $modal.open({
          templateUrl: 'cloneItemModal.html',
          controller: function ($scope, $modalInstance, $window, $http, database, prepid, errorModal, setSuccess) {
            $scope.prepid = prepid;
            $scope.database = database;
            $scope.vars = { 'newPrepid': '' };
            $scope.clone = function () {
              const itemData = { "prepid": $scope.prepid, "new_prepid": $scope.vars.newPrepid };
              $http({ method: 'PUT', url: 'restapi/' + $scope.database + '/clone/', data: itemData }).success(function (data, status) {
                setSuccess(data["results"]);
                if (data.results) {
                  $window.location.href = 'edit?db_name=' + $scope.database + '&query=' + data.prepid;
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
            prepid: function () { return prepid; },
            database: function () { return database; },
            errorModal: function () { return $scope.openErrorModal; },
            setSuccess: function () { return $scope.setSuccess; },
          }
        })
      };

      $scope.openCreateItemModal = function (database) {
        $modal.open({
          templateUrl: 'createItemModal.html',
          controller: function ($scope, $modalInstance, database) {
            $scope.vars = { "prepid": "" };
            $scope.database = database;
            $scope.save = function () {
              const itemData = { "prepid": $scope.vars.prepid };
              $http({ method: 'PUT', url: 'restapi/' + $scope.database + '/save/', "data": itemData }).success(function (data, status) {
                if (data.results) {
                  $window.location.href = 'edit?db_name=' + $scope.database + '&query=' + $scope.vars.prepid;
                } else {
                  $scope.openErrorModal(prepid, data['message']);
                  $scope.setSuccess(false, status);
                }
              }).error(function (data, status) {
                $scope.openErrorModal(prepid, data['message']);
                $scope.setSuccess(false, status);
              });
              $modalInstance.close();
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            database: function () { return database; },
          }
        })
      };
    }
  ]);

testApp.directive('slider', function () {
  return {
    restrict: 'AE',
    scope: {
      value: '=',
      sliding: '='
    },
    link: function (scope, element, attrs, ctrl) {
      var slider_lines = $("input", element).slider();
      slider_lines.data('slider').setValue(scope.value);

      slider_lines.on('slide', function (ev) {
        scope.$parent.$apply(function () {
          scope.sliding = true;
          scope.value = slider_lines.data('slider').getValue();
        });
      });

      slider_lines.on('slideStop', function (ev) {
        scope.$parent.$apply(function () {
          scope.sliding = false;
        });
      });

    },
    template: '<input type="text" class="slider" data-slider-min=5 data-slider-max=101 data-slider-selection="after" data-slider-tooltip="hide" data-slider-handle="round-square">'
  }
});

testApp.directive('tokenfield', function ($parse) {
  return {
    restrict: 'AE',
    scope: {
      onClick: '=onClick', // function which can use the e.token.value and e.token.label elements
      onRemove: '=onRemove', // function which can use the e.token.value and e.token.label elements
      afterCreate: '=afterCreate', // function which can use the e.token.value and e.token.label elements
      beforeCreate: '=beforeCreate', // function which can use the e.token.value and e.token.label elements
      tokens: '&'
    },
    link: function (scope, element, attrs, ctrl) {
      var token_arguments = {};
      if (!(typeof attrs.allowDuplicates === 'undefined'))
        token_arguments.allowDuplicates = scope.$eval(attrs.allowDuplicates);
      if (!(typeof attrs.showAutocompleteOnFocus === 'undefined'))
        token_arguments.showAutocompleteOnFocus = scope.$eval(attrs.showAutocompleteOnFocus);
      if (!(typeof attrs.typeAhead === 'undefined')) {
        token_arguments.typeahead = scope.$eval(attrs.typeAhead);
        if (!(typeof token_arguments.typeahead.prefetch === 'undefined') && !(typeof token_arguments.typeahead.prefetch.filter === 'undefined')) {
          token_arguments.typeahead.prefetch.filter = eval(token_arguments.typeahead.prefetch.filter)
        }
      }
      var tokenfield = $("input", element).tokenfield(token_arguments);

      if (!(typeof scope.tokens === 'undefined'))
        tokenfield.tokenfield("setTokens", scope.$eval(scope.tokens));

      tokenfield.on('clickToken', function (e) {
        if (!(typeof scope.onClick === 'undefined'))
          scope.onClick(e.token)
      });

      tokenfield.on('removeToken', function (e) {
        if (!(typeof scope.onRemove === 'undefined'))
          scope.onRemove(e.token)
      });

      tokenfield.on('afterCreateToken', function (e) {
        if (!(typeof scope.afterCreate === 'undefined'))
          scope.afterCreate(e.token)
      });

      tokenfield.on('beforeCreateToken', function (e) {
        if (!(typeof scope.beforeCreate === 'undefined'))
          scope.beforeCreate(e.token)
      });

      if (!(typeof attrs.ngDisabled === 'undefined')) {
        scope.$parent.$watch(attrs.ngDisabled
          , function (newVal) {
            if (newVal) {
              tokenfield.tokenfield('disable')
            } else {
              tokenfield.tokenfield('enable')
            }
          })
      }

    },

    template: '<input id="tokenfield" type="text" class="form-control" value=""/>'
  }
});

testApp.directive('ddlFileReader', function ($http, $rootScope) {
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
testApp.controller('TabsController', ['$scope', '$element', function ($scope, $element) {
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
testApp.directive('tabs', function () {
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
testApp.directive('pane', ['$parse', function ($parse) {
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

testApp.constant('buttonConfig', {
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

testApp.directive('dropdownToggle', ['$document', '$location', function ($document, $location) {
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

testApp.directive("reqmgrName", function ($http) {
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

testApp.directive("customFooter", function ($location, $compile, $http) {
  return {
    restrict: 'C',
    link: function (scope, element) {

      scope.custom_footer_limit_opts = [20, 50, 100];

      var limit = $location.search()["limit"];
      if (limit === undefined) {
        limit = 20;
      }
      scope.custom_footer_limit = parseInt(limit);
      if (scope.custom_footer_limit_opts.indexOf(scope.custom_footer_limit) == -1) {
        scope.custom_footer_limit_opts.push(scope.custom_footer_limit);
      }

      var page = $location.search()["page"];

      if (page === undefined) {
        page = 0;
        $location.search("page", 0);
      }
      scope.custom_footer_list_page = parseInt(page);

      scope.custom_footer_previous_page = function (current_page) {
        if (current_page > -1) {
          $location.search("page", current_page - 1);
          scope.custom_footer_list_page = current_page - 1;
        }
      };

      scope.custom_footer_new_limit = function () {
        scope.custom_footer_list_page = 0;
        $location.search("limit", scope.custom_footer_limit);
        $location.search("page", 0);
      };

      scope.custom_footer_next_page = function (current_page) {
        if (scope.result.length != 0 && scope.result.length >= scope.custom_footer_limit) {
          $location.search("page", current_page + 1);
          scope.custom_footer_list_page = current_page + 1;
        }
      };

      $http.get('HTML/templates/footer.custom.html').then(function (response) {
        element.append($compile(response.data)(scope));
      });
    }
  }
});

testApp.directive('selectWell', function ($location) {
  return {
    restrict: 'EA',
    template:
      '<input type="button" value="Show selection options" class="btn" ng-click="showWell=!showWell" ng-show="!showWell && !alwaysShow">' +
      '<input type="button" value="Hide selection options" class="btn" ng-click="showWell=!showWell" ng-show="showWell && !alwaysShow">' +
      '<div class="well" ng-show="showWell">' +
      '<div>' +
      '<input type="button" class="btn" value="Select all" ng-click="selectAll()" ng-hide="selectedCount==selection.length">' +
      '<input type="button" class="btn" value="Deselect" ng-click="selectAll()" ng-show="selectedCount==selection.length">' +
      '<input type="button" class="btn" value="Save selection" ng-click="saveCookie()" ng-if="useCookie">' +
      '<a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#View_Characteristics" rel="tooltip" title="Help with view characteristics" target="_blank"><i class="icon-question-sign"></i></a>' +
      '</div>' +
      '<span ng-repeat="value in selection">' +
      '<label class="checkbox inline" style="padding-left:20px;">' +
      '<input type="checkbox" ng-model="value.select" style="margin-left: -15px;">{{value.text}}' +
      '</label>' +
      '</span>' +
      '</div>',
    scope: {
      selection: '=',
      database: '@',
      alwaysShow: "=?",
      useCookie: "=?"
    },
    link: function ($scope) {
      $scope.selectedCount = 0;
      $scope.alwaysShow = $scope.alwaysShow === undefined ? false : $scope.alwaysShow;
      $scope.showWell = $scope.alwaysShow;
      $scope.useCookie = $scope.useCookie === undefined ? true : $scope.useCookie;
      var previousSelection = [];

      if (!$scope.database) {
        $scope.database = $location.search()["db_name"];
      }

      var shown = $location.search()["shown"] || ($scope.useCookie ? $.cookie($scope.database + "shown") : false);
      if ($location.search()["fields"]) //if fields in url don't force to calculate shown from cookie or shown number
      {
        shown = false;
      }
      if (shown) {
        $location.search("shown", shown);
        var binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
        for (var column = 0; column < $scope.selection.length; column++) {
          var binary_bit = binary_shown.charAt(column);
          if (binary_bit != "") { //if not empty -> we have more columns than binary number length
            $scope.selection[column].select = binary_bit == 1;
          } else { //if the binary index isnt available -> this means that column "by default" was not selected
            $scope.selection[column].select = false;
          }
        }
      }
      _.each($scope.selection, function (elem, index) {
        if (elem.select) {
          previousSelection.push(index);
        }
      });

      $scope.$watch('selection', function () { //on chage of column selection -> recalculate the shown number
        var bin_string = ""; //reconstruct from begining
        var count = 0;
        _.each($scope.selection, function (column) { //iterate all columns
          if (column.select) {
            count += 1;
            bin_string = "1" + bin_string; //if selected add 1 to binary interpretation
          } else {
            bin_string = "0" + bin_string;
          }
        });
        $scope.selectedCount = count;
        $location.search("shown", parseInt(bin_string, 2)); //put into url the interger of binary interpretation
      }, true);

      $scope.selectAll = function () {
        var currentSelected = [];
        _.each($scope.selection, function (elem, index) {
          if (elem.select) {
            currentSelected.push(index);
          }
          elem.select = true;
        });
        if ($scope.selectedCount == _.size($scope.selection)) {
          _.each($scope.selection, function (elem) {
            elem.select = false;
          });
          _.each(previousSelection, function (elem) {
            $scope.selection[elem].select = true;
          });
        } else {
          previousSelection = currentSelected;
        }
      };


      $scope.saveCookie = function () {
        var cookie_name = $scope.database + "shown";
        if ($location.search()["shown"]) {
          $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 });
        }
      };
    }
  }

});

testApp.directive("customHistory", function () {
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

testApp.directive("sequenceDisplay", function ($http) {
  return {
    require: 'ngModel',
    template:
      '<div>' +
      '  <div ng-hide="show_sequence">' +
      '    <a rel="tooltip" title="Show" ng-click="getCmsDriver();show_sequence=true;">' +
      '     <i class="icon-eye-open"></i>' +
      '    </a>' +
      '  </div>' +
      '  <div ng-show="show_sequence">' +
      '    <a rel="tooltip" title="Hide" ng-click="show_sequence=false;">' +
      '     <i class="icon-remove"></i>' +
      '    </a>' +
      '    <ul>' +
      '      <li ng-repeat="sequence in driver">' +
      '        <ul ng-repeat="(key,value) in sequence">' +
      '          <li><b>{{key}}</b>: <div style="width:600px;overflow:auto"><pre>{{value}}</pre></div></li>' +
      '        </ul>' +
      '      </li>' +
      '    </ul>' +
      '  </div>' +
      '</div>',
    link: function (scope, element, attrs, ctrl) {
      ctrl.$render = function () {
        scope.show_sequence = false;
        scope.sequencePrepId = ctrl.$viewValue;
      };
      scope.getCmsDriver = function () {
        if (scope.driver === undefined) {
          var promise = $http.get("restapi/" + scope.dbName + "/get_cmsDrivers/" + scope.sequencePrepId);
          promise.then(function (data) {
            scope.driver = data.data.results;
          }, function (data) {
            alert("Error: ", data.status);
          });
        }
      };
    }
  }
});
