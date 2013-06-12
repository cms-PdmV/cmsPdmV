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
    var promise = $http.get("restapi/users/get_roles");
    promise.then(function(data){
      $scope.user.name = data.data.username;
      $scope.user.role = data.data.roles[0];
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
};
