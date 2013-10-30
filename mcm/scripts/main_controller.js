function mainCtrl($scope, $http, $location, $window){
  $scope.stats_cache = {};
  $scope.full_details = {};

  var browserName=navigator.appName;
  if (browserName == 'Microsoft Internet Explorer'){
    // console.log('fOUND ie');
    if ($window.location.href.indexOf('#') == -1){
      var newLocation = $window.location.href.replace(/\#/g,''); //for safety remove all # to not add ##?
      newLocation = newLocation.replace('?','#?');
     // $location.hash(newLocation.split('?')[1]);
     $window.location.href = newLocation;
    }
  }
  // console.log(browserName);
  $scope.user = {name: "guest", role:"user",roleIndex:0};

// GET username and role
  var promise = $http.get("restapi/users/get_role",{ cache: true});
  promise.then(function(data){
    $scope.user.name = data.data.username;
    $scope.user.role = data.data.role;
    $scope.user.roleIndex = parseInt(data.data.role_index);
  },function(data){
    alert("Error getting user information. Error: "+data.status);
  });
// Endo of user info request

// GET all news
  $scope.getNews = function(){ //we check for wich page to get news -> home page gets news all the time
    var pages_not_to_get_news = ["chained_campaigns","flows","actions","chained_requests","batch","dashboard","users","edit"];
    var return_info = true;
    _.each(pages_not_to_get_news, function(elem){
      if($location.path().indexOf(elem) != -1)
      {
        return_info = false;
      }
    });
      return return_info;
  };
  if ($scope.getNews()){
    var promise = $http.get("restapi/news/getall/5");
    promise.then(function(data){
      $scope.news = data.data;
      var new_marquee = document.createElement('marquee');
      var news_banner = document.getElementById("news_banner");
      if(news_banner){
        new_marquee.setAttribute('direction','left');
        new_marquee.setAttribute('behavior','scroll');
        var sorted_news = _.sortBy($scope.news, function(elem){ //sort news array by date
          return elem.date;
        });
        //changed in the rest api directly
        sorted_news.reverse(); //lets reverse it so newest new is in beggining of array
    //    sorted_news = sorted_news.splice(0,5); //take only 5 newest and best news
        _.each(sorted_news, function(v){
          new_new = "<span> <i class='icon-globe'></i><b>"+v.subject+"</b>  <i>"+v.date+" </i></span>";
            new_marquee.innerHTML += new_new;
        });
        news_banner.appendChild(new_marquee);
        news_banner.appendChild(new_marquee);
      }
    },function(data){
      alert("Error getting news. Error: "+data.status);
    });
  }
// Endo of news!



  $scope.isDevMachine = function(){
    is_dev = $location.absUrl().indexOf("dev") != -1;
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
    return $location.url();
  };

  $scope.role = function(priority){
    if(priority > $scope.user.roleIndex){ //if user.priority < button priority then hide=true
      return true;
    }else{
      return false;
    }
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
}
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
    replace: true,
    require: 'ngModel',
    restrict: 'E',
    scope: true,
    template:
    '<span>'+
    '  <ul style="margin-bottom: 0px;">'+
    '    <li ng-repeat="rqmngr in rqmngr_data">'+
    '      <a ng-href="batches?contains={{rqmngr.name}}" rel="tooltip" title="View batches containing {{rqmngr.name}}" target="_self"><i class="icon-tags"></i></a>'+
    '      <a ng-show="isDevMachine();" ng-href="https://cmsweb-testbed.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>'+
    '      <a ng-show="!isDevMachine();" ng-href="https://cmsweb.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>,'+
    '      <a ng-hide="stats_cache[rqmngr[\'name\']]" ng-href="http://cms-pdmv.cern.ch/stats/?RN={{rqmngr[\'name\']}}" rel="tooltip" title="Stats" target="_self"> stats</a>'+
    '      <a ng-click="load_dataset_list(rqmngr.name, $index);" ng-hide="stats_cache[rqmngr[\'name\']]" rel="tooltip" title="Load statistics" ng-href="#"> <i class="icon-eye-open"></i></a>'+
    '      <b><font color="red" ng-show="stats_cache[rqmngr[\'name\']] && !underscore.isObject(stats_cache[rqmngr[\'name\']])"> Stats Not Found</font></b>'+
    '      <span ng-show="underscore.isObject(stats_cache[rqmngr[\'name\']])">'+
    '        <a ng-href="http://cms-pdmv.cern.ch/stats/?RN={{rqmngr[\'name\']}}" target="_self"> {{numberWithCommas(stats_cache[rqmngr[\'name\']].pdmv_evts_in_DAS)}} events</a>,'+
    '        <a ng-hide="role(3);" ng-href="https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/{{rqmngr[\'name\']}}" rel="tooltip" title="Perf" target="_self">perf</a>,'+
    '        <a ng-hide="role(3);" ng-href="https://cmsweb.cern.ch/reqmgr/reqMgr/outputDatasetsByRequestName/{{rqmngr[\'name\']}}" rel="tooltip" title="DS" target="_self">output</a>,'+
    '        {{stats_cache[rqmngr[\'name\']].pdmv_status_from_reqmngr}}, {{stats_cache[rqmngr[\'name\']].pdmv_status_in_DAS}},'+
    '        <span ng-repeat="c_site in stats_cache[rqmngr_data[\'name\']].pdmv_custodial_sites">'+
    '          @{{c_site}},'+
    '        </span>'+
    '        <span ng-show="stats_cache[rqmngr[\'name\']].pdmv_running_sites.length">'+
    '          Running at : {{stats_cache[rqmngr[\'name\']].pdmv_running_sites.join()}},'+
    '        </span>'+
    '        Last update on {{stats_cache[rqmngr[\'name\']].pdmv_monitor_time}}'+
    '        </br>'+
    '        <a ng-href="{{links[$index]}}"><img width={{image_width}} ng-src="{{links[$index]}}" ng-mouseover="image_width = 700" ng-mouseleave="image_width = 150"/></a>'+
    '        <ul style="margin-bottom: 0px;" ng-show="true;">'+
    '          <li ng-repeat="DS in stats_cache[rqmngr[\'name\']].pdmv_dataset_list">'+
    '            <span ng-switch on="stats_cache[rqmngr[\'name\']].pdmv_status_in_DAS == \'VALID\'">'+
    '              <a ng-switch-when="true" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{DS}}" rel="tooltip" title="Link to {{DS}} in DAS" target="_self">{{DS}}</a>'+
    '              <a ng-switch-when="false" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{DS}}" rel="tooltip" title="Link to {{DS}} in DAS" target="_self"><del>{{DS}}</del></a>'+
    '            </span>'+
    '          </li>'+
    '          <li ng-show="data[\'status\']==\'done\' && rqmngr_data.content.pdmv_dataset_name && !underscore.isObject(stats_cache[rqmngr[\'name\']])">'+
    '            <span ng-switch on="stats_cache[rqmngr[\'name\']].pdmv_status_in_DAS == \'VALID\'">'+
    '              <a ng-switch-when="true" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{rqmngr_data.content.pdmv_dataset_name }}" rel="tooltip" title="Link to {{rqmngr_data.content.pdmv_dataset_name}} in DAS" target="_self">{{ rqmngr_data.content.pdmv_dataset_name}}</a>'+
    '              <a ng-switch-when="false" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{rqmngr_data.content.pdmv_dataset_name }}" rel="tooltip" title="Link to {{rqmngr_data.content.pdmv_dataset_name}} in DAS" target="_self"><del>{{ rqmngr_data.content.pdmv_dataset_name}}</del></a>'+
    '            </span>'+
    '          </li>'+
    '        </ul>'+
    '        <a ng-click="full_details[rqmngr[\'name\']]=true;" ng-hide="role(3) || full_details[rqmngr[\'name\']]" rel="tooltip" title="Load Full details" ng-href="#"> <i class="icon-barcode"></i></a>'+
    '      </span>'+
    '      <div ng-show="underscore.isObject(stats_cache[rqmngr[\'name\']]) && full_details[rqmngr[\'name\']]">'+
    '        <a ng-click="full_details[rqmngr[\'name\']]=false;" rel="tooltip" title="Close details" ng-href="#"><i class="icon-barcode"></i></a>'+
    '        <pre>{{stats_cache[rqmngr[\'name\']]|json}}</pre>'+
    '      </div>'+
    '    </li>'+
    '  </ul>'+
    '</span>',
    link: function(scope, element, attrs, ctrl)
    {

      ctrl.$render = function(){
        scope.links = {};
        //scope.remngr_name = ctrl.$viewValue.name;
        scope.rqmngr_data = ctrl.$viewValue;
        scope.r_prepid = scope.$eval(attrs.prepid);
      };

      scope.load_dataset_list = function (req_name, index){
        scope.getrqmnr_data(req_name, index);
      };
      scope.getrqmnr_data = function(req_name, index){
        scope.links[index] = "https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/"+req_name+".gif";
        getfrom='/stats/restapi/get_one/'+req_name;
        $http({method:'GET', url: getfrom}).success(function(data,status){
          scope.stats_cache[req_name] = data;
        }).error(function(status){
          scope.stats_cache[req_name] = "Not found";
        });
      };

      scope.$on('loadDataSet', function(event, values){
        if(scope.dbName == "requests")
        {
          if (values[2]== scope.r_prepid)
          {
            scope.load_dataset_list(values[0], values[1]);
          }
        }else
        {
          if (values[2] == scope.r_prepid)
          {
            scope.load_dataset_list(values[0], values[1]);
          }
        }
      });
    }
  }
});
