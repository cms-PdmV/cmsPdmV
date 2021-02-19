angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "batches";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.puce = {};
    $scope.r_status = {};
    $scope.update = [];
    $scope.local_requests = {};
    $scope.underscore = _;
    $scope.selected_prepids = [];

    $scope.batches_defaults = [
      {text:'PrepId',select:true, db_name:'prepid'},
      {text:'Actions',select:false, db_name:''},
      {text:'Status',select:true, db_name:'status'},
      {text:'Requests',select:true, db_name:'requests'},
      {text:'Notes',select:true, db_name:'notes'}
    ];

    $scope.sort = {
      column: 'prepid',
      descending: false
    };

    $scope.selectedCls = function(column) {
      return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };

    $scope.changeSorting = function(column) {
      var sort = $scope.sort;
      if (sort.column == column){
        sort.descending = !sort.descending;
      }else{
         sort.column = column;
         sort.descending = false;
       }
    };

    //watch length of pending HTTP requests -> if there are display loading;
    $scope.$watch(function(){ return $http.pendingRequests.length;}, function(v){
      //if HTTP requests pending == 0
       $scope.pendingHTTP = !(v==0);
    });

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
        var query = "";
        _.each($location.search(), function(value,key){
          if (key!= 'shown' && key != 'fields'){
            query += "&"+key+"="+value;
          }
        });
        var promise = $http.get("search?"+ "db_name="+$scope.dbName+query+"&get_raw");
      }
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      promise.then(function(data){
        $scope.result_status = data.status;
        $scope.got_results = true;
        if (data.data.rows === undefined){
            $scope.result = data.data;
        }else{
            $scope.result = _.pluck(data.data.rows, 'doc');
        }
        if ($scope.result.length != 0){
          columns = _.keys($scope.result[0]);
          rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
          _.each(rejected, function(v){
              add = true;
              _.each($scope.batches_defaults, function(column){
              if (column.db_name == v){
                  add = false;
              }
           });
              if (add){
                  $scope.batches_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
              }
          });
          if ( _.keys($location.search()).indexOf('fields') != -1)
          {
            _.each($scope.batches_defaults, function(elem){
              elem.select = false;
            });
            _.each($location.search()['fields'].split(','), function(column){
              _.each($scope.batches_defaults, function(elem){
                if ( elem.db_name == column )
                {
                  elem.select = true;
                }
              });
            });
          }
          }
          $scope.selectionReady = true;
      }, function(){
         alert("Error getting main information");
        });
    };

    $scope.$watch(function() {
       var loc_dict = $location.search();
       return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },function(){
      $scope.getData();
    });

    $scope.announce = function(prepid){
      alert("Batch to be announced:"+prepid);
    };

    $scope.resetBatch = function (batch_id) {
      $http({method: 'GET', url: 'restapi/batches/reset/' + batch_id}).success(function (data, status) {
        $scope.getData();
        alert('Successfully resetted the batch');
      }).error(function (status) {
        console.log(status);
        alert('Failed while updating the batch');
      });
    };

    $scope.loadStats = function(batch_requests){
      _.each( batch_requests, function(elem,index){
        $http({method:'GET', url: 'public/restapi/requests/get_status/'+elem.content.pdmv_prep_id}).success(function(data,status){
          r_prepid=_.keys(data)[0];
          r_status = data[r_prepid];
          $scope.r_status[ r_prepid ] = r_status;
          status_map = { 'done' : 'led-green.gif',
            'submitted' : 'led-blue.gif',
            'approved' : 'led-orange.gif',
            'defined' : 'led-orange.gif',
            'validation' : 'led-red.gif',
            'new' : 'led-red.gif'};

          if (status_map[r_status]){
            $scope.puce[ r_prepid ] = status_map[r_status];
          }else{
            $scope.puce[ r_prepid ] = 'icon-question-sign';
          }
        }).error(function(status){
          alert('cannot get status for '+elem.content.pdmv_prep_id);
        });
      });
    };

    $scope.inspect = function(batchid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/inspect/'+batchid}).success(function(data,status){
        $scope.getData();
      }).error(function(status){
        alert('Cannot inspect '+batchid);
      });
    };

    $scope.hold = function(batchid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/hold/'+batchid}).success(function(data,status){
        $scope.getData();
      }).error(function(status){
        alert('Cannot hold or release '+batchid);
      });
    };

    $scope.preloadRequest = function (batch_prepid, request_prepid, completion) {
      var url = 'restapi/requests/get/' + request_prepid;
      if (!_.has($scope.local_requests, request_prepid)) {
        var promise = $http.get(url);
        promise.then(function(data) {
          $scope.local_requests[request_prepid] = data.data.results.reqmgr_name;
          if (completion !== undefined) {
            completion(request_prepid);
          }
        }, function(data){
          alert("error " + data.results);
        });
      } else {
        if (completion !== undefined) {
          completion(request_prepid);
        }
      }
    };

    $scope.broadcast_inspect = function (batch_prepid, requests_data) {
      $scope.loadStats(requests_data);
      _.each(requests_data, function (element, index){
        $scope.preloadRequest(batch_prepid, element.content.pdmv_prep_id, function(request_prepid) {
          _.each($scope.local_requests[request_prepid], function (element2, index2){
            $scope.$broadcast('loadDataSet', [batch_prepid, element2.name, element2]);
          });
        });
      });
    };

    $scope.generateAllRequests = function (input_data)
    {
      var tmp_url = [];
      if (input_data.length > 0)
      {
        _.each(input_data, function (elem) {
            tmp_url.push(elem.content.pdmv_prep_id);
        });
        tmp_url = _.uniq(tmp_url);
        return tmp_url.join(";");
      }else
      {
        return "";
      }
    };

    $scope.add_to_selected_list = function(prepid){
      if (_.contains($scope.selected_prepids, prepid)){
        $scope.selected_prepids = _.without($scope.selected_prepids,prepid);
      }else{
        $scope.selected_prepids.push(prepid);
      }
    };

    $scope.toggleAll = function(){
      if ($scope.selected_prepids.length != $scope.result.length){
        _.each($scope.result, function(v){
          $scope.selected_prepids.push(v.prepid);
        });
        $scope.selected_prepids = _.uniq($scope.selected_prepids);
      }else{
        $scope.selected_prepids = [];
      }
    };

  }]);

angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$modal',
  function ModalDemoCtrl($scope, $http, $modal) {
    $scope.announceModal = function (id) {
      var announceModal = $modal.open({
        templateUrl: 'announceModal.html',
        controller: ModalAnnounceCtrl,
        resolve: {
          prepid: function() {
            return id;
          },
          type: function() {
            return "Announce";
          }
        }
      });

      announceModal.result.then(function (data) {

        // some hackish checks for multiple announcement
        if (data.prepid == 'all' && $scope.selected_prepids.length == 0)
        {
          alert("No batches were selected for multiple announce");
          return "";
        }
        if (data.prepid == 'all')
        {
          data.prepid = $scope.selected_prepids;
        }

        $http({method: 'PUT', url:'restapi/batches/announce', data:{prepid: data.prepid, notes: data.mail}}).success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["results"] = data.results;
          $scope.update["status_code"] = status;
          $scope.getData();
          //   $window.location.href ="edit?db_name=requests&query="+data.results;
        }).error(function(data,status){
          alert("Error:"+ status);
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });

      })
    };

    $scope.isSureModal = function(action, prepid) {
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

      isSure.result.then(function () {
        switch (action){
          case "delete":
            alert("Not yet in RestAPI!");
            break;
          case "reset":
            $scope.resetBatch(prepid);
            break;
          default:
            alert("Unknown action!");
            break;
        }
      })
    };

    $scope.openNotifyModal = function (id) {
      var notifyModal = $modal.open({
        templateUrl: 'announceModal.html',
        controller: ModalAnnounceCtrl,
        resolve: {
          prepid: function() {
            return id;
          },
          type: function() {
            return "Notify";
          }
        }
      });

      notifyModal.result.then(function (data) {
        $http({method: 'PUT', url:'restapi/batches/notify', data:{prepid: data.prepid, notes: data.mail}}).success(function(data, status){
          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["results"] = data.results;
          $scope.update["status_code"] = status;
        }).error(function(data,status){
          alert("Error:"+ status);
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        });
      })
    };


    var ModalAnnounceCtrl = function($scope, $modalInstance, prepid, type) {
        $scope.prepid = prepid;
        $scope.type = type;
        $scope.mail = {
            mailContent: ""
        };

        $scope.send = function() {
            $modalInstance.close({prepid: $scope.prepid, mail:$scope.mail.mailContent})
        };

        $scope.close = function() {
            $modalInstance.dismiss();
        }
    };
  }]);
