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
    var promise = $http.get("restapi/users/get_role");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.role;
      $scope.user.roleIndex = parseInt(data.data.role_index);
    },function(data){
      alert("Error getting user information. Error: "+data.status);
    });
// Endo of user info request

  $scope.isDevMachine = function(){
    is_dev = $location.absUrl().indexOf("dev") != -1;
    //    if (is_dev){
    //        nav_bar = document.getElementsByClassName("navbar-inner");
    //        _.each(nav_bar, function(v){
    //		v.style.backgroundImage = "linear-gradient(to bottom, #E89619, #F2F2F2)"    
    //		    });
    //    }
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
   if (x !== undefined){
     var parts = x.toString().split(".");
     parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
     return parts.join(".");
   }else{
     return x;
   }
  };
};
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
    }else{ //else if it was closed-> open clicked pane by closing all and opening the current one
      angular.forEach(panes, function(pane) {
        pane.selected = false;
      });
      pane.selected = true;
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
}])
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
    "      <a ng-click=\"select(pane)\">{{pane.heading}}</a>\n" +
    "    </li>\n" +
    "  </ul>{{result}}\n" +
    "  <div class=\"tab-content\" ng-transclude></div>\n" +
    "</div>\n",
    replace: true
  };
})
testApp.directive('pane', ['$parse', function($parse) {
  return {
    require: '^tabs',
    restrict: 'EA',
    transclude: true,
    scope:{
      heading:'@',
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
