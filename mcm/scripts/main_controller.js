testApp.config(['$compileProvider', function ($compileProvider) {
  $compileProvider.debugInfoEnabled(false);
}]);

angular.module('testApp').controller('mainCtrl',
  ['$scope','$http', '$location', '$window', '$modal',
  function mainCtrl($scope, $http, $location, $window, $modal){
  $scope.stats_cache = {};
  $scope.full_details = {};
  $scope.mcm_revision = "";
  $scope.user = {name: "guest", role:"user",roleIndex:0};
  $scope.start_time = "";
  $scope.turn_on_button_clicked = false;

  var browserName=navigator.appName;
  if (browserName == 'Microsoft Internet Explorer'){
    if ($window.location.href.indexOf('#') == -1){
      var newLocation = $window.location.href.replace(/\#/g,''); //for safety remove all # to not add ##?
      newLocation = newLocation.replace('?','#?');
     // $location.hash(newLocation.split('?')[1]);
     $window.location.href = newLocation;
    }
  }
  var promise;
  var get_rev = true;
  _.each(["campaigns","chained_campaigns","flows","actions","requests","chained_requests","batch","invalidations","mccms","dashboard","users","edit","news","settings"], function (elem){
    if ($location.path().indexOf(elem) != -1)
    {
      get_rev = false;
    }
  });
  if (get_rev && $window.document.title != "McM maintenance")
  {
    promise = $http.get("restapi/dashboard/get_revision");
    promise.then(function (data) {
      $scope.mcm_revision = data.data;
    });
  }
  if ($scope.start_time == "" && $window.document.title !="McM maintenance")
  {
    promise = $http.get("restapi/dashboard/get_start_time");
    promise.then(function (data) {
      $scope.start_time = data.data.results;
    });
  }

// GET username and role
  promise = $http.get("restapi/users/get_role",{ cache: true});
  promise.then(function(data){
    $scope.user.name = data.data.username;
    $scope.user.role = data.data.role;
    $scope.user.roleIndex = parseInt(data.data.role_index);
    $scope.xMasSpecial();
  },function(data){
    alert("Error getting user information. Error: "+data.status);
  });
// Endo of user info request

  $scope.turnOnServer = function() {
    if ($window.document.title == "McM maintenance") {
      $scope.turn_on_button_clicked = true;
      var promise = $http.get("restapi/control/turn_on");
      promise.then(function(){
          alert("Server turned on");
          setTimeout(function(){$window.location.reload()}, 5000);
      }, function(){
          alert("Server failed to turn on");
          $scope.turn_on_button_clicked = false;
          setTimeout(function(){$window.location.reload()}, 1000);
      });
    }
  };

  $scope.isDevMachine = function(){
    is_dev = $location.host().indexOf("dev") != -1;
    if (is_dev){
      body = document.getElementsByTagName("body");
     _.each(body, function(v){
      v.style.backgroundImage = "url(HTML/draft.png)"
      });
    }
    return is_dev;
  };

  //return everyting thats after main url
  $scope.getLocation = function(){
    var __location = $location.url();
    return __location.replace(/page=\d+/g,"").substring(1); //remove 1st character which is / to make a relative link
  };
  //return fullUrl
  $scope.getFullLocation = function(){
    var __location = $location.url();
    return __location.substring(1); //remove 1st character which is / to make a relative link
  };

  $scope.role = function(priority){
    return priority > $scope.user.roleIndex; //if user.priority < button priority then hide=true
  };
  //watch length of pending HTTP requests -> if there are display loading;
  $scope.$watch(function(){ return $http.pendingRequests.length;}, function(v){
    $scope.pendingHTTPLenght = v;
    if (v == 0){  //if HTTP requests pending == 0
      $scope.pendingHTTP = false;
    }else
      $scope.pendingHTTP = true;
  });
  $scope.numberWithCommas =  function(x) {
   if (x){
     var parts = x.toString().split(".");
     parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
     return parts.join(".");
   }else{
     return x;
   }
  };

  /* Support modal actions*/

  $scope.openSupportModal = function (){
    $modal.open({
        templateUrl:"supportModal.html",
        controller: function($scope, $modalInstance) {
            $scope.close = function() {
                $modalInstance.close();
            }
        }
    });
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

testApp.directive('tokenfield', function($parse) {
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
           if(!(typeof attrs.allowDuplicates === 'undefined'))
                token_arguments.allowDuplicates = scope.$eval(attrs.allowDuplicates);
           if(!(typeof attrs.showAutocompleteOnFocus === 'undefined'))
                token_arguments.showAutocompleteOnFocus = scope.$eval(attrs.showAutocompleteOnFocus);
           if(!(typeof attrs.typeAhead === 'undefined')) {
                token_arguments.typeahead = scope.$eval(attrs.typeAhead);
                if(!(typeof token_arguments.typeahead.prefetch === 'undefined') && !(typeof token_arguments.typeahead.prefetch.filter === 'undefined')){
                    token_arguments.typeahead.prefetch.filter = eval(token_arguments.typeahead.prefetch.filter)
                }
           }
            var tokenfield = $("input", element).tokenfield(token_arguments);

           if(!(typeof scope.tokens === 'undefined'))
                tokenfield.tokenfield("setTokens", scope.$eval(scope.tokens));

            tokenfield.on('clickToken', function(e) {
                if(!(typeof scope.onClick === 'undefined'))
                    scope.onClick(e.token)
            });

            tokenfield.on('removeToken', function(e) {
                if(!(typeof scope.onRemove === 'undefined'))
                    scope.onRemove(e.token)
            });

           tokenfield.on('afterCreateToken', function(e) {
                if(!(typeof scope.afterCreate === 'undefined'))
                    scope.afterCreate(e.token)
            });

           tokenfield.on('beforeCreateToken', function(e) {
                if(!(typeof scope.beforeCreate === 'undefined'))
                    scope.beforeCreate(e.token)
            });

           if(!(typeof attrs.ngDisabled === 'undefined')) {
            scope.$parent.$watch(attrs.ngDisabled
            , function(newVal){
                    if(newVal) {
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

testApp.directive('ddlFileReader', function($http,$rootScope) {
    return {
        require: "ngModel",
        replace: true,
        restrict: 'E',
        link: function(scope, element, attrs, ctrl) {

            element.bind("change", function (ev) {
                var files = ev.target.files;
                var file = files.length?files[0]:null;

                if (! file) {
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
testApp.controller('TabsController', ['$scope', '$element', function($scope, $element) {
  var panes = $scope.panes = [];

  this.select = $scope.select = function selectPane(pane) {
    if (pane.selected == true){ //if pane is clicked while open -> close pane to save space
      pane.selected = false;
      pane.active = false;
    }else{ //else if it was closed-> open clicked pane by closing all and opening the current one
      angular.forEach(panes, function(pane) {
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
      $scope.select(panes[index < panes.length ? index : index-1]);
    }
  };
}]);
testApp.directive('tabs', function() {
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
testApp.directive('pane', ['$parse', function($parse) {
  return {
    require: '^tabs',
    restrict: 'EA',
    transclude: true,
    scope:{
      heading:'@',
      active:'='
    },
    link: function(scope, element, attrs, tabsCtrl) {
      var getSelected, setSelected;
      scope.selected = false;
      if (attrs.active) {
        getSelected = $parse(attrs.active);
        setSelected = getSelected.assign;
        scope.$watch(
          function watchSelected() {return getSelected(scope.$parent);},
          function updateSelected(value) {scope.selected = value;}
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
      scope.$on('$destroy', function() {
        tabsCtrl.removePane(scope);
      });
    },
    template: "<div class=\"tab-pane\" ng-class=\"{active: selected}\" ng-show=\"selected\" ng-transclude></div>\n",
    replace: true
  };
}]);

testApp.constant('buttonConfig', {
    activeClass:'active',
    toggleEvent:'click'
  })
  .directive('btnRadio', ['buttonConfig', function (buttonConfig) {
  var activeClass = buttonConfig.activeClass || 'active';
  var toggleEvent = buttonConfig.toggleEvent || 'click';
  return {
    require:'ngModel',
    link:function (scope, element, attrs, ngModelCtrl) {
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
    require:'ngModel',
    link:function (scope, element, attrs, ngModelCtrl) {
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
      closeMenu   = angular.noop;
  return {
    restrict: 'CA',
    link: function(scope, element, attrs) {
      scope.$watch('$location.path', function() { closeMenu(); });
      element.parent().bind('click', function() { closeMenu(); });
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

testApp.directive("reqmgrName", function($http){
  return {
    require: 'ngModel',
    restrict: 'E',
    scope: true,
    templateUrl: 'HTML/templates/request.manager.name.html',
    replace: true,
    link: function(scope, element, attrs, ctrl)
    {
      scope.links = {};
      scope.image_width = 150;
      ctrl.$render = function(){
        scope.rqmngr_data = ctrl.$viewValue;
        scope.r_prepid = scope.$eval(attrs.prepid);
      };
      scope.load_dataset_list = function (req_name, index){
        scope.getrqmnr_data(req_name, index);
      };
      scope.getrqmnr_data = function(req_name, index){
        var __tmp = _.without(req_name.split("_"),"");
        var __filename = _.rest(__tmp, __tmp.length-1)[0];
        var __dirname = _.without(__tmp, __filename)
        __url = __dirname.join("/") + "/" + __filename
        scope.links[req_name] = "https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/"+__url+".gif";
        getfrom='/stats/restapi/get_one/'+req_name;
        $http({method:'GET', url: getfrom}).success(function(data,status){
          scope.stats_cache[req_name] = data;
        }).error(function(status){
          scope.stats_cache[req_name] = "Not found";
        });
      };
      scope.$on('loadDataSet', function (events, values) {
        if (scope.dbName == "requests") {
          if (scope.data._id == values[2]) {
            scope.load_dataset_list(values[0], values[1]);
          }
        } else {
          if (scope.r_prepid == values[2]) {
            scope.load_dataset_list(values[0], values[1]);
          }
        }
      });
    }
  }
});

testApp.directive("customFooter", function($location, $compile, $http) {
   return {
       restrict: 'C',
       link: function(scope, element) {

            scope.custom_footer_limit_opts = [20,50,100];

            var limit = $location.search()["limit"];
            if(limit === undefined){
                limit=20;
            }
            scope.custom_footer_limit=parseInt(limit);
            if (scope.custom_footer_limit_opts.indexOf(scope.custom_footer_limit)==-1){
                scope.custom_footer_limit_opts.push(scope.custom_footer_limit);
            }

            var page = $location.search()["page"];

            if(page === undefined){
                page = 0;
                $location.search("page", 0);
            }
            scope.custom_footer_list_page = parseInt(page);

            scope.custom_footer_previous_page = function(current_page){
                if (current_page >-1){
                    $location.search("page", current_page-1);
                    scope.custom_footer_list_page = current_page-1;
                }
            };

            scope.custom_footer_new_limit = function(){
                scope.custom_footer_list_page = 0;
                $location.search("limit",scope.custom_footer_limit);
                $location.search("page", 0);
            };

            scope.custom_footer_next_page = function(current_page){
                if (scope.result.length !=0 && scope.result.length >= scope.custom_footer_limit){
                    $location.search("page", current_page+1);
                    scope.custom_footer_list_page = current_page+1;
                }
            };

            $http.get('HTML/templates/footer.custom.html').then(function(response){
                    element.append($compile(response.data)(scope));
                });
       }
   }
});

testApp.directive('selectWell', function($location) {
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
        link: function($scope) {
            $scope.selectedCount = 0;
            $scope.alwaysShow = $scope.alwaysShow===undefined ? false : $scope.alwaysShow;
            $scope.showWell = $scope.alwaysShow;
            $scope.useCookie = $scope.useCookie===undefined ? true : $scope.useCookie;
            var previousSelection = [];

            if (!$scope.database) {
                $scope.database = $location.search()["db_name"];
            }

            var shown = $location.search()["shown"] || ($scope.useCookie ? $.cookie($scope.database + "shown") : false);
            if ($location.search()["fields"]) //if fields in url don't force to calculate shown from cookie or shown number
            {
              shown=false;
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

var ModalIsSureCtrl = function($scope, $modalInstance, action, prepid) {
    $scope.modal_action = action;
    $scope.toggle_prepid = prepid;

    var stringToColour = function(str) {
        //converts any string to hexadecimal color format
        var hash = 0;
        for (var i = 0; i < str.length; i++) {
            hash = str.charCodeAt(i) + ((hash << 5) - hash);
        }
        var colour = '#';
        for (i = 0; i < 3; i++) {
            var value = (hash >> (i * 8)) & 0xFF;
            colour += ('00' + value.toString(16)).substr(-2);
        }
        return colour;
    };

    $scope.modal_color = stringToColour(action);

    $scope.yes = function() {
        $modalInstance.close();
    };

    $scope.no = function() {
        $modalInstance.dismiss();
    };
};