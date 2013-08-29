function mainCtrl($scope, $http, $location, $window){
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
    var pages_not_to_get_news = ["chained_campaigns","flows","actions","requests","chained_requests","batch","dashboard","users","edit"];
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