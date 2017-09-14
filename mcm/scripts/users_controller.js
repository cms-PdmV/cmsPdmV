angular.module('testApp').controller('resultsCtrl',
  ['$scope','$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [
      {text:'UserName', select:true, db_name:'username'},
      {text:'Full name', select:true, db_name:'fullname'},
      {text:'Actions', select:false, db_name:''},
      {text:'Email', select:false, db_name:'email'},
      {text:'Role', select:true, db_name:'role'},
      {text:'Pwg', select:true, db_name:'pwg'}
    ];

    $scope.update = [];
    $scope.all_pwgs = [];

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "users";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.sort = {
      column: 'value.username',
      descending: false
    };

    $scope.selectedCls = function(column) {
      return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };

    $scope.changeSorting = function(column) {
      var sort = $scope.sort;
      if (sort.column == column) {
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };

    $scope.getData = function(){
      if($location.search()["from_notification"]){
        notification = $location.search()["from_notification"];
          page = $location.search()["page"]
          limit = $location.search()["limit"]
          if(page === undefined){
            page = 0
          }
          if(limit === undefined){
            limit = 20
          }
          var promise = $http.get("restapi/notifications/fetch_actions?notification_id=" + notification + "&page=" + page + "&limit=" + limit);
      }else if($location.search()["from_notification_group"]){
          group = $location.search()["from_notification_group"];
          page = $location.search()["page"]
          limit = $location.search()["limit"]
          if(page === undefined){
            page = 0
          }
          if(limit === undefined){
            limit = 20
          }
          var promise = $http.get("restapi/notifications/fetch_group_actions?group=" + group + "&page=" + page + "&limit=" + limit);
      }else{
        var query = ""
        _.each($location.search(), function(value,key){
          if (key!= 'shown' && key != 'fields'){
            query += "&"+key+"="+value;
          }
        });

        var promise = $http.get("search?db_name="+$scope.dbName+query+"&get_raw");
      }
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      promise.then(function(data){
        if (data.data.rows === undefined){
            $scope.result = data.data;
        }else{
            $scope.result = _.pluck(data.data.rows, 'doc');
        }
        $scope.result_status = data.status;
        $scope.got_results = true;
        if ($scope.result.length != 0){
          columns = _.keys($scope.result[0]);
          rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
          _.each(rejected, function(v){
            add = true;
            _.each($scope.defaults, function(column){
              if (column.db_name == v){
                add = false;
              }
            });
            if (add){
              $scope.defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
            }
          });
          if ( _.keys($location.search()).indexOf('fields') != -1)
          {
            _.each($scope.defaults, function(elem){
              elem.select = false;
            });
            _.each($location.search()['fields'].split(','), function(column){
              _.each($scope.defaults, function(elem){
                if ( elem.db_name == column )
                {
                  elem.select = true;
                }
              });
            });
          }
        }
          $scope.selectionReady = true;
      },function(){
         alert("Error getting information");
      });
    };

    $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
      $scope.getData();
      $scope.selected_prepids = [];
    });

    $scope.askrole = function(pwg){
      var promise = $http.get("restapi/users/ask_role/"+pwg);
      promise.then(function(data, status){
        $scope.update["success"] = true;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data.status;
        $scope.update["results"] = data.data.results;
        $scope.getData();
      },function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });
    };

    $scope.changeRole = function(username,step){
      var promise = $http.get("restapi/users/change_role/"+username+"/"+step);
      promise.then(function(data, status){
        $scope.update["success"] = true;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data.status;
        $scope.update["results"] = data.data.results;
        $scope.getData();
      },function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });
    };

    $scope.addMe = function(){
      var promise = $http.get("restapi/users/add_role");
      promise.then(function(data, status){
        $scope.update["success"] = true;
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data.status;
        $scope.getData();
      },function(data, status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = data.status;
      });
    };
  }
  ]);
angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$modal', '$http',
  function ModalDemoCtrl($scope, $modal, $http) {
    $scope.openPwgNotify = function (pwg) {
      $modal.open( {
        templateUrl: 'pwgNotifyModal.html',
          controller: ModalPwgNotifyInstanceCtrl,
          resolve: {
            pwg: function() {
              return pwg;
            }
          }
        }
      );
    };

    function createPwgModal() {
      var pwgModalInst = $modal.open({
        templateUrl: 'pwgModalSelect.html',
        controller: ModalPwgSelectInstanceCtrl,
        resolve: {
          all_pwgs: function(){
            return $scope.all_pwgs;
          },
          newPWG: function(){
            return $scope.newPWG;
          }
        }
      });
      pwgModalInst.result.then(function (newPWG) {
        if(newPWG != "------") {
          $scope.askrole(newPWG);
        }
      });
    }

    $scope.openPwgModal = function(curr_pwgs)
    {
      $scope.newPWG = "------";
      if ($scope.all_pwgs.length == 0)
      {
        var promise = $http.get("restapi/users/get_pwg")
        promise.then(function(data){
          $scope.all_pwgs = _.difference(data.data.results, curr_pwgs);
          $scope.all_pwgs.splice(0,0,"------");
          $scope.newPWG = $scope.all_pwgs[0];
            createPwgModal()
        });
      }
      else
      {
        $scope.newPWG = $scope.all_pwgs[0];
          createPwgModal();
      }
    };

    var ModalPwgNotifyInstanceCtrl = function($scope, $modalInstance, $http, pwg) {
      $scope.pwg = pwg;
      $scope.mail = {
              mailContent: "",
              mailSubject: ""
          };
      $scope.notify = function () {
          if(!$scope.mail.mailContent.length && !$scope.mail.mailSubject.length) {
              alert("Cannot send empty message with empty subject");
              return;
          }
          $http({method: 'PUT', url:'restapi/users/notify_pwg', data:{pwg: $scope.pwg, subject:$scope.mailSubject, content: $scope.mailContent}})
              .success(function(data, status){
                  alert("Notification sent");
              }).error(function(data,status){
                  alert("Error:"+ status);
              });
          $modalInstance.close();
    };

      $scope.close = function() {
          $modalInstance.dismiss();
      }
    };

    var ModalPwgSelectInstanceCtrl = function($scope, $modalInstance, $http, all_pwgs, newPWG) {
      $scope.all_pwgs = all_pwgs;
      $scope.selected = {newPWG: newPWG};

      $scope.select = function () {
        $modalInstance.close($scope.selected.newPWG);
      };

      $scope.close = function() {
        $modalInstance.dismiss();
      };
    }
}
]);

testApp.directive("customHistory", function(){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="show_history">'+
    '    <input type="button" value="Show" ng-click="show_history=true;">'+
    '  </div>'+
    '  <div ng-show="show_history">'+
    '    <input type="button" value="Hide" ng-click="show_history=false;">'+
    '    <table class="table table-bordered" style="margin-bottom: 0px;">'+
    '      <thead>'+
    '        <tr>'+
    '          <th style="padding: 0px;">Action</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in show_info">'+
    '          <td style="padding: 0px;">{{elem.action}}</td>'+
//     '          <td style="padding: 0px;"><a rel="tooltip" title={{elem.message}}><i class="icon-info-sign"></i></a></td>'+
    '          <td style="padding: 0px;">{{elem.updater.submission_date}}</td>'+
    '          <td style="padding: 0px;">'+
    '              <div ng-switch="elem.updater.author_name">'+
    '                <div ng-switch-when="">{{elem.updater.author_username}}</div>'+
    '                <div ng-switch-default>{{elem.updater.author_name}}</div>'+
    '              </div>'+
    '          </td>'+
    '          <td style="padding: 0px;">{{elem.step}}</td>'+
    '        </tr>'+
    '      </tbody>'+
    '    </table>'+
    '  </div>'+
    '</div>'+
    '',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_history = false;
        scope.show_info = ctrl.$viewValue;
      };
    }
  }
});
