angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
  function resultsCtrl($scope, $http, $location, $window, $modal){
    $scope.defaults = [
      {text:'Prepid', select:true, db_name:'prepid'},
      {text:'Actions', select:true, db_name:''},
      {text:'Meeting', select:true, db_name:'meeting'},
      {text:'Approval', select:false, db_name:'approval'},
      {text:'Status', select:false, db_name:'status'},
      {text:'Deadline', select:true, db_name:'deadline'},
      {text:'Block', select:true, db_name:'block'},
      {text:'Message ID', select:false, db_name:'message_id'},
      {text:'Notes', select:false, db_name:'notes'},
      {text:'Pwg', select:false, db_name:'pwg'},
      {text:'Requests', select:true, db_name:'requests'},
      {text:'Size', select:false, db_name:'size'},
      {text:'Chains', select:true, db_name:'chains'},
      {text:'History', select:false, db_name:'history'}
    ];

    $scope.update = [];
    $scope.dbName = "mccms";
    $scope.sort = {
      column: 'value.name',
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
      }else{
        var query = "";
        _.each($location.search(), function(value,key){
          if (key!= 'shown' && key != 'fields'){
            query += "&"+key+"="+value;
          }
        });
        var promise = $http.get("search?db_name="+$scope.dbName+query+"&get_raw");
      }
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      promise.then(function(data){
        $scope.processFetchedData(data);
      },function(){
         alert("Error getting information");
      });
    };

    $scope.processFetchedData = function (data){
        if (data.data.rows === undefined){
            $scope.result = data.data;
        }else{
            $scope.result = _.pluck(data.data.rows, 'doc');
        }
        $scope.result_status = data.status;
        $scope.got_results = true;
        if ($scope.result.length != 0){
          var columns = _.keys($scope.result[0]);
          var rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
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
    }

    $scope.$watch(function() {
       var loc_dict = $location.search();
       return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
     },
     function(){
         $scope.getData();
         $scope.selected_prepids = [];
     });

    $scope.cancel = function(mccm_id){
      $http({method:'GET', url:'restapi/mccms/cancel/'+ mccm_id}).success(function(data,status){
        if (data.results){
          alert("Ticket canceled");
          $scope.getData();
        }else{
          alert(data.message);
        }
      }).error(function(status){
        alert("Could not cancel the ticket");
      });
    };

    $scope.remove = function(mccm_id){
      $http({method:'DELETE', url:'restapi/mccms/delete/'+ mccm_id}).success(function(data,status){
        if (data.results){
          alert("Ticket deleted");
          $scope.getData();
        }else{
          alert(data.message);
        }
      }).error(function(status){
        alert("Could not delete the ticket");
      });
    };

    $scope.generate = function(mccm_id, opt){
      var promise= $http.get("restapi/mccms/generate/"+mccm_id+opt);
      promise.then(function(data){
        if (data.data.results){
          alert("Everything went fine");
        }
        else{
          alert(data.data.message);
        }
      },function(){
        alert("Something went wrong");
      });
    };

    $scope.approve_all_requests = function(mccm_prepid){
      var requests = '';
      for (index in $scope.result){
        if ($scope.result[index].prepid == mccm_prepid){
          var generated_chains = $scope.result[index].generated_chains
          for (var chain in generated_chains){
            for (index_requests in generated_chains[chain]){
              requests +=  generated_chains[chain][index_requests] + ",";
            }
          }
          break;
        }
      }
      if (requests != ''){
        requests = requests.slice(0, -1);
        $scope.approve_gen_request(requests);
      }
    };

    $scope.get_requests_size = function(dict){
      var size = 0;
      for (var chain in dict){
        size += dict[chain].length;
      }
      return size;
    };

    $scope.is_generated_chains_empty = function(dict){
      for (var chain in dict){
        return true;
      }
      return false;
    };

    $scope.redirect_chained_request = function(ticket_prepid){
      window.location = "chained_requests?from_ticket=" + ticket_prepid;
    }

    $scope.approve_gen_request = function(prepids){
      $http({method:'POST', url:'restapi/requests/approve', data: prepids}).success(function(data,status){
        if (!$scope.isArray(data)){
          data = [data];
        }
        alert_text = "";
        for (index in data){
          alert_text += data[index].prepid + ":\n";
          if (data[index].results){
            alert_text += "Everything went fine\n";
          }
          else{
            alert_text += data[index].message + "\n";
          }
        }
        alert(alert_text);
      }).error(function(data,status){
        alert("Something went wrong");
      });
    };

    $scope.isArray = function(obj){
      return angular.isArray(obj)
    };

    $scope.findToken = function(tok){
      $window.location.href = "requests?&tags="+tok.value
    };

    $scope.generateAllRequests = function (input_data)
    {
      var tmp_url = [];
      if (input_data.length > 0)
      {
        _.each(input_data, function (elem) {
          if (_.isArray(elem))
          {
            tmp_url.push(elem[0]+","+elem[1]);
          }else
          {
            tmp_url.push(elem);
          }
        });
        return tmp_url.join(";");
      }else
      {
        return "";
      }
    };

    $scope.recalculate_evts = function(prepid){
      var promise= $http.get("restapi/mccms/update_total_events/"+prepid);
      promise.then(function(data){
        if (data.data.results){
          $scope.getData();
        }
        else{
          alert(data.data.message);
        }
      },function(){
        alert("Something went wrong");
      });
    };

    $scope.open_isSureModal = function(action, prepid){
      var isSure = $modal.open({
         templateUrl: 'isSureModal.html',
          controller: ModalIsSureCtrl,
          resolve: {
              prepid: function() {
                  return prepid;
              },
              action: function() {
                  return action;
              }
          }
      });

      isSure.result.then(function(){
        switch (action){
            case "cancel":
                $scope.cancel(prepid);
                break;
            case "delete":
                $scope.remove(prepid);
                break;
            default:
                break;
        }
      });
    };

    $scope.openCreateModal = function () {
      var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name);
      promise.then(function(data){
        var pwgs = data.data.results;
          $modal.open({
            templateUrl: "createMccmModal.html",
            controller: CreateMccmModalInstance,
            resolve: {
              pwgs: function() {
                return pwgs;
              }
            }
          });
      }, function() {
        alert("Error while getting PWGs for user")
      });
    };

    $scope.dropdownModal = function(prepid, chain_prepids) {
      var isConfirmed = $modal.open({
        templateUrl: 'dropdownModal.html',
        controller: ReserveMccmModalInstance,
        resolve: {
          prepid: function() {
            return prepid;
          },
          chain_prepids: function() {
            return chain_prepids;
          }
        }
      });

      isConfirmed.result.then(function (campaigns) {
        console.log(campaigns);
        console.log(chain_prepids);
        var reserveLimits = '';
        for (var i = 0; i < chain_prepids.length; i++) {
          if (campaigns[chain_prepids[i]] == undefined || campaigns[chain_prepids[i]] == "--------") {
            reserveLimits += '';
          } else {
            reserveLimits += campaigns[chain_prepids[i]];
          }
          if (i != chain_prepids.length - 1) {
            reserveLimits += ',';
          }
        }
        $scope.generate(prepid, '/reserve/' + reserveLimits);
      });
    };

    var ReserveMccmModalInstance = function($scope, $modalInstance, $window, $http, prepid, chain_prepids) {
      $scope.loadingData = true;
      $scope.campaignListDropdown = Object();
      $scope.campaignListDropdownSelector = Object();
      for (var i = 0; i < chain_prepids.length; i++) {
        $scope.campaignListDropdown[chain_prepids[i]] = ["--------"];
        $scope.campaignListDropdownSelector[chain_prepids[i]] = $scope.campaignListDropdown[chain_prepids[i]][0];
        var url = undefined;
        if (chain_prepids[i].indexOf('chain_') == -1) {
          url = "search?db_name=chained_campaigns&get_raw&alias=" + chain_prepids[i];
        } else {
          url = "search?db_name=chained_campaigns&get_raw&prepid=" + chain_prepids[i];
        }
        var promiseDeep = $http.get(url);
        promiseDeep.then(function(d){
          d.data.rows[0].doc.campaigns.forEach(function(c) {
            var prepid = d.data.rows[0].doc.prepid;
            var alias = d.data.rows[0].doc.alias;
            if (prepid in $scope.campaignListDropdown) {
              $scope.campaignListDropdown[prepid].push(c[0]);
            } else {
              $scope.campaignListDropdown[alias].push(c[0]);
            }
          });
        });
      }
      $scope.loadingData = false;

      $scope.toggle_prepid = prepid;
      $scope.confirm = function(id) {
        console.log('confirm ' + prepid);
        $modalInstance.close(id);
      };
      $scope.cancel = function() {
        console.log('cancel ' + prepid);
        $modalInstance.dismiss();
      };
    };

    var CreateMccmModalInstance = function($scope, $modalInstance, $window, $http, pwgs) {
      $scope.mccms = {
        pwgs: pwgs,
        selectedPwg: pwgs[0]
      };

      $scope.close = function() {
        $modalInstance.dismiss();
      };

      $scope.save = function () {
        if ($scope.mccms.selectedPwg){
          $http({method: 'PUT', url:'restapi/mccms/save/', data:{prepid: $scope.mccms.selectedPwg, pwg: $scope.mccms.selectedPwg}})
          .success(function(data, stauts){
            if (data.results){
              $window.location.href ="edit?db_name=mccms&prepid="+data.prepid;
            }else{
              alert("Error:"+ data.message);
            }
          }).error(function(data,status){
            alert("Error:"+ status);
          });
        }else{
          alert("Error: no pwg defined!");
        }
        $modalInstance.close();
      };
    };
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