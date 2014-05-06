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
    if (['anorkus', 'ijurkows'].indexOf($scope.user.name) == -1 ) //if user is the one to get news
    {
      $scope.setNews();
    }
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

  }};

  $scope.setNews = function ()
  {
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
    var __location = $location.url();
    return __location.replace(/page=\d+/g,"");
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
    '<a ng-href="http://cms-pdmv.cern.ch/stats/?PI={{r_prepid}}" title="All stats for the request" rel="tooltip" target="_self" ng-hide="r_prepid.indexOf(\'-chain_\')>-1">All stats</a>'+
    '  <ul style="margin-bottom: 0px;">'+
    '    <li ng-repeat="rqmngr in rqmngr_data">'+
    '      <a ng-href="batches?contains={{rqmngr.name}}" rel="tooltip" title="View batches containing {{rqmngr.name}}" target="_self"><i class="icon-tags"></i></a>'+
    '      <a ng-show="isDevMachine();" ng-href="https://cmsweb-testbed.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>'+
    '      <a ng-show="!isDevMachine();" ng-href="https://cmsweb.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>,'+
    '      <a ng-hide="stats_cache[rqmngr[\'name\']]" ng-href="http://cms-pdmv.cern.ch/stats/?RN={{rqmngr[\'name\']}}" rel="tooltip" title="Stats" target="_self"> stats</a>,'+
    '      <a ng-show="r_prepid.split(\'-\').length < 3" ng-href="requests?prepid={{rqmngr.content.pdmv_prep_id}}" rel="tooltip" title="view request {{rqmngr.content.pdmv_prep_id}}" target="_self"> {{rqmngr.content.pdmv_prep_id}}</a>'+
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
    '        <a ng-href="{{links[rqmngr.name]}}"><img width={{image_width}} ng-src="{{links[rqmngr.name]}}" ng-mouseover="image_width = 700" ng-mouseleave="image_width = 150"/></a>'+
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
      scope.links = {};
      scope.image_width =150;
      ctrl.$render = function(){
        scope.rqmngr_data = ctrl.$viewValue;
        scope.r_prepid = scope.$eval(attrs.prepid);
      };

      scope.load_dataset_list = function (req_name, index){
        scope.getrqmnr_data(req_name, index);
      };
      scope.getrqmnr_data = function(req_name, index){
        scope.links[req_name] = "https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/"+req_name+".gif";
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

testApp.directive("customFooter", function($location, $compile) {
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
           var innerHtml = '<div class="span2" style="margin-top:20px;">';
           innerHtml += '<span ng-show="got_results"> Found {{ result.length}} results </span>';
           innerHtml += '<img ng-show="pendingHTTP" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>';
           innerHtml += '<div ng-show="update[\'success\']"> Success. Status code:<font color="green">{{update[\'status_code\']}}</font> </div>';
           innerHtml += '<div ng-show="update[\'fail\']"> Fail. Status code:<font color="red">{{update[\'status_code\']}}</font> </div>';
           innerHtml += '</div>';
           innerHtml += '<div class="span5 pagination pagination-right" > <ul>';
           innerHtml += '<li ng-class="{ disabled: custom_footer_list_page <= -1 }"> <a ng-click="custom_footer_previous_page(custom_footer_list_page)" ng-href="#" ng-show="custom_footer_list_page>0">Prev</a> <a ng-click="custom_footer_previous_page(custom_footer_list_page)" ng-href="#" ng-hide="custom_footer_list_page>0">All</a> </li>';
           innerHtml += '<li> <a ng-href="#" ng-show="custom_footer_list_page>=0" target="_blank">#{{custom_footer_list_page}}</a> <a ng-href="#" ng-show="custom_footer_list_page==-1" target="_blank">#All</a> </li>';
           innerHtml += '<li ng-class="{ disabled: result.length < custom_footer_limit }"> <a ng-click="custom_footer_next_page(custom_footer_list_page)" ng-href="#" ng-show="custom_footer_list_page>=0">Next</a> <a ng-click="custom_footer_next_page(custom_footer_list_page)" ng-href="#" ng-show="custom_footer_list_page==-1">Paginated</a> </li>';
           innerHtml += '<li> <select ng-model="custom_footer_limit" ng-options="elem for elem in custom_footer_limit_opts;" style="width: 60px;" ng-change="custom_footer_new_limit();" ng-show="custom_footer_list_page>=0"></select> </li>';
           innerHtml += '</ul> </div>'
           element.append($compile(innerHtml)(scope))
       }
   }
});

testApp.directive("growthGraph", function($http, $location){
  return {
    replace: true,
    // require: 'ngModel',
    restrict: 'E',
    template:
    '<div style="position: relative;">'+
    '  <div id="chart">'+
    '    <svg ></svg>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attrs)
    {
      var level_order = ["new", "validation", "defined", "approved", "submitted", "done"];
      var possible_dates = [];
      
      scope.dbName = $location.search()["db_name"];
      scope.chart_data = [];

      // ctrl.$render = function(){
        //scope.input_id = ctrl.$viewValue;
        // scope.chart_data = [];
      // };

      var parseDate = function (date) {
        var replaceAt = function (i, char, str) {
          return str.substr(0, i) + char + str.substr(i + char.length);
        };

        date = replaceAt(10, " ", date);
        date = replaceAt(13, ":", date);
        return date;
      }

      scope.parseHistory = function(input)
      {
        var previus_info = {};
        var tmp_data = _.filter(input, function(elem){
          if ( level_order.indexOf(elem.step) != -1 )
          {
            //var tmp_info = {"step": elem.step, "date":elem.updater.submission_date};
            var tmp_info = {"step": elem.step, "date":elem.updater.submission_date};
            if ( !_.isEqual(previus_info, tmp_info) ) //we ignore dublicated statuses and same days -> so we wont get undefined error in nvd3 script
            {
              previus_info = _.clone(tmp_info);
              return elem;
            }
          }
        });
        return tmp_data;
      };
      
      scope.getMinInterval = function(data){
        var time_diff = [],
            previous;
        _.each(data, function(elem, key){
          _.each(elem, function(el){
            el.updater.submission_date = parseDate(el.updater.submission_date);
              if(previous){
                time_diff.push(el.updater.submission_date - previous.updater.submission_date);
              }
              previous = el;
          });
        });
        return _.min(time_diff);
      }

      scope.getHistoryData = function(ids){
        var promise = $http.get("restapi/"+scope.dbName+"/fullhistory/"+ids);
        promise.then( function( data ) {
          //for each request
          _.each(data.data.results, function(elem, key)
          {
            //for each request status
            _.each(elem, function(el){
              //el.updater.submission_date = parseDate(el.updater.submission_date);
              if (possible_dates.indexOf(el.updater.submission_date) )
              {
                possible_dates.push(el.updater.submission_date);
              }
            });
            scope.chart_data.push({"values" : scope.parseHistory(elem), "key" : key, "color" : "#"+((1<<24)*Math.random()|0).toString(16)})
          });
          //console.log(scope.chart_data);
          scope.displayChart();
        });
      };
      scope.getIDsFromURL = function()
      {
        if ( $location.search()["prepid"] )
        {
          scope.getHistoryData($location.search()["prepid"]);
          console.log($location.search()["prepid"]);
        }
      }
      scope.getIDsFromURL();
      // EXO-chain_Summer12PLHE_flowLHE2FS53-00002

      scope.displayChart = function()
      {
        // Wrapping in nv.addGraph allows for '0 timeout render', stores rendered charts in nv.graphs, and may do more in the future... it's NOT required
          var chart;
      
          //possible_dates = ['2001-03-03 10:12', '2002-03-03 10:12']
          possible_dates = _.uniq(possible_dates);
          possible_dates.sort();
          var levels = {};
          _.each(level_order, function (key, i) {
            levels[key] = i;
          });
      
          nv.addGraph(function() {
            chart = nv.models.lineChart()
            .options({
              margin: {left: 100, bottom: 120, right:100},
              padding: {bottom: 3, top: 3},
              x: function (obj) { return possible_dates.indexOf(obj.updater.submission_date); },
              y: function (obj) { return levels[obj.step]; },
              showXAxis: true,
              showYAxis: true,
              transitionDuration: 250
            })
            // .width(600).height(400)
            .tooltipContent(function(key, x, y, entry, graph) {
              var e = entry.point;
              return '<a href=""><h5>' + key + '</h5></a>' +
                     '<p>' + e.step + ' at ' + e.updater.submission_date + '</p>' +
                     '<p>' + 'by ' + '<a href=""><b>' + e.updater.author_username + '</b></a>' + '</p>';
            });
      
          // chart sub-models (ie. xAxis, yAxis, etc) when accessed directly, return themselves, not the parent chart, so need to chain separately
            chart.xAxis
              .axisLabel("Date")
              .rotateLabels(-45)
              .tickValues(_.keys(possible_dates))
              .tickFormat(function(d) {
                var dx = possible_dates[d]  || "";
                if ( possible_dates[d] )
                {
                  return dx;
                }
              });
      
            chart.yAxis
              .axisLabel('Step')
              .tickValues(_.keys(level_order))
              .tickFormat(function(d) {
                if ( level_order[d] )
                {
                  return level_order[d];
                }
              });
      
            d3.select('#chart svg')
                .datum(scope.chart_data)
                .call(chart);
      
          nv.utils.windowResize(chart.update);
          return chart;
        });
      }
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