angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.chainedCampaigns_defaults = [
      {text:'PrepId',select:true, db_name:'prepid'},
      {text:'Actions',select:true, db_name:''},
      {text:'Alias',select:true, db_name:'alias'},
      {text:'Campaigns',select:true, db_name:'campaigns'}
    ];
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "chained_campaigns";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }

    $scope.update = [];
    $scope.chained_campaigns = [];
    $scope._ = _; //enable underscorejs to be accessed from HTML template

    $scope.delete_object = function(db, value){
      $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
        if (data["results"]){
          $scope.update["success"] = data.results;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData();
        }else{
          $scope.update["success"] = false;
          $scope.update["fail"] = true;
          $scope.update["status_code"] = status;
        }
        }).error(function(status){
          alert('Error no.' + status + '. Could not delete object.');
      });
    };

    $scope.inspect = function(value){
      $http({method:'GET', url:'restapi/chained_campaigns/inspect/'+value}).success(function(data,status){
        if (data["results"]){
          $scope.update["success"] = data.results;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.getData();
        }else{
          if ( _.isArray(data) )
          {
            $scope.update["success"] = true;
            $scope.update["fail"] = false;
          }
          else
          {
            $scope.update["success"] = false;
            $scope.update["fail"] = true;
          }
          $scope.update["status_code"] = status;
        }
        }).error(function(status){
          alert('Error no.' + status + '. Could not delete object.');
      });
    };

    $scope.sort = {
      column: 'prepid',
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

  $scope.filterResults = function(){
    var data =_.filter($scope.result, function(element){
      return element["valid"];
    });
    if ($scope.role(3)){
      return data;
    }else{
      return $scope.result;
    }
  };

  $scope.getData = function () {
      var query = "";

      _.each($location.search(), function (value, key) {
          if (key != 'shown' && key != 'fields') {
              query += "&" + key + "=" + value;
          }
      });
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var promise, get_raw;
      get_raw = true;
      promise = $http.get("search?" + "db_name=" + $scope.dbName + query + "&get_raw");
      //var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
      promise.then(function (data) {
          $scope.result_status = data.status;
          $scope.got_results = true;
          $scope.result = get_raw ? _.pluck(data.data.rows, 'doc') : data.data.results;
          if ($scope.result === undefined) {
              alert('The following url-search key(s) is/are not valid : ' + _.keys(data.data));
              return; //stop doing anything if results are undefined
          }
          $scope.total_results = data.data.total_rows;
          if ($scope.result.length > 0) {
              columns = _.keys($scope.result[0]);
              rejected = _.reject(columns, function (v) {
                  return v[0] == "_";
              }); //check if charat[0] is _ which is couchDB value to not be shown
              $scope.columns = _.sortBy(rejected, function (v) {
                  return v;
              });  //sort array by ascending order
              _.each(rejected, function (v) {
                  add = true;
                  _.each($scope.chainedCampaigns_defaults, function (column) {
                      if (column.db_name == v) {
                          add = false;
                      }
                  });
                  if (add) {
                      $scope.chainedCampaigns_defaults.push({text: v[0].toUpperCase() + v.substring(1).replace(/\_/g, ' '), select: false, db_name: v});
                  }
              });
              if (_.keys($location.search()).indexOf('fields') != -1) {
                  _.each($scope.chainedCampaigns_defaults, function (elem) {
                      elem.select = false;
                  });
                  _.each($location.search()['fields'].split(','), function (column) {
                      _.each($scope.chainedCampaigns_defaults, function (elem) {
                          if (elem.db_name == column) {
                              elem.select = true;
                          }
                      });
                  });
              }
          }else{
            alert("Error: " + data.data.message)
          }
          $scope.selectionReady = true;
      }, function () {
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
    }
  );

  $scope.create = function( cc_name ){
    for (var i = 0; i< $scope.result.length; i++) {
      if($scope.result[i].prepid == cc_name) {
        var campaigns = $scope.result[i].campaigns;
        break
      }
    }
    $http({method: 'PUT', url:'restapi/chained_campaigns/save/', data:{prepid: cc_name, campaigns:campaigns}}).success(function(data, status){
      if (data.results){
        $window.location.href ="edit?db_name=chained_campaigns&prepid="+data.prepid;
      } else {
        alert("Error:" + data.message + status);
      }
	  }).error(function(data, status){
        alert("Error:"+ status);
        console.log(data, status);
	   });
  };
}
]);

angular.module('testApp').controller('ModalDemoCtrl',
  ['$scope', '$http', '$window', '$modal',
  function ModalDemoCtrl($scope, $http, $window, $modal) {
    $scope.pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP'];
    $scope.selectedPwg= 'BPH';
    $scope.createChainedRequest = function (id) {
      var promise = $http.get("restapi/users/get_pwg/"+$scope.user.name);
      promise.then(function(data){
	      var pwgs = data.data.results;
        $modal.open({
          templateUrl: 'createChainedRequestModal.html',
          controller: ChainedRequestCreationModal,
          resolve: {
              pwgs: function(){
                  return pwgs;
              },
              selectedPwg: function(){
                return pwgs[0];
              },
              prepid: function() {
                  return id;
              }
          }
        })
	    });
    };

    var ChainedRequestCreationModal = function($scope, $modalInstance, $window, $http, pwgs, selectedPwg, prepid) {
      $scope.pwgs = pwgs;
      $scope.prepid = prepid;
      $scope.pwg = {
        selected: selectedPwg
      };
      $scope.save = function(){
        if ($scope.pwg.selected){
          $http({method: 'PUT', url: 'restapi/chained_requests/save/', data: {member_of_campaign: $scope.prepid, pwg: $scope.pwg.selected}}).success(function (data, status) {
            if (data.results) {
              $window.location.href = "edit?db_name=chained_requests&prepid=" + data.prepid;
            } else {
              alert("Error:" + data.message + status);
          }
          }).error(function (data, status){
              alert("Error:" + status);
            });
        } else {
          alert("Error: No PWG defined!");
        }
      };
      $scope.close = function() {
        $modalInstance.dismiss();
      }
    };
  }
]);

angular.module('testApp').controller('ModalCreateChainedCampaign',
  ['$scope', '$http', '$window', '$modal',
  function ModalCreateChainedCampaign($scope, $http, $window, $modal) {
    $scope.open = function () {
      var flowCreationModal = $modal.open({
          templateUrl: "chainedCampaignCreateModal.html",
          controller: CreateChainedCampaignInstance
      });
    };

    var CreateChainedCampaignInstance = function($scope, $modalInstance, $window, $http) {
      $scope.pairs = [{campaigns:[], flows:[], selectedCampaign:'', selectedFlow:{prepid:undefined}}]
      var promise = $http.get("search?db_name=campaigns&page=-1");
      promise.then(function(data){
        $scope.pairs[0].campaigns = data.data.results.filter(campaign => campaign.root != 1).map(campaign => campaign.prepid);
      });
      $scope.updateFlow = function(index) {
        while ($scope.pairs.length > index + 1) {
          $scope.pairs.pop();
        }
        if ($scope.pairs[index].selectedFlow.prepid !== '') {
          $scope.pairs[index].campaigns = [$scope.pairs[index].selectedFlow.next];
          $scope.pairs[index].selectedCampaign = $scope.pairs[index].selectedFlow.next;
          $scope.updateCampaign(index);
        } else {
          $scope.pairs[index].selectedCampaign = '';
        }
      }
      $scope.updateCampaign = function(index) {
        while ($scope.pairs.length > index + 1) {
          $scope.pairs.pop()
        }
        var promise = $http.get("search?db_name=flows&page=-1&allowed_campaigns=" + $scope.pairs[index].selectedCampaign);
        promise.then(function(data){
          var nextFlows = data.data.results.map(flow => {const x = {'prepid':flow.prepid, 'next':flow.next_campaign}; return x});
          if (nextFlows.length > 0) {
            nextFlows.unshift({'prepid': '', 'next': ''})
            $scope.pairs.push({campaigns:[], flows:[], selectedCampaign:'', selectedFlow:nextFlows[0]})
            $scope.pairs[index + 1].flows = nextFlows;
          }
        });
      }
      $scope.save = function(){
        $scope.pairs = $scope.pairs.filter(pair => pair.selectedCampaign && pair.selectedCampaign !== '')
        var campaigns = $scope.pairs.map(pair => {const x = [pair.selectedCampaign, pair.selectedFlow.prepid]; return x;})
        $http({method: 'PUT', url: 'restapi/chained_campaigns/save/', data: {'campaigns': campaigns}}).success(function (data, status) {
            if (data.results) {
              $window.location.href = "edit?db_name=chained_campaigns&prepid=" + data.prepid;
            } else {
              alert("Error: " + data.message);
            }
          }).error(function (data, status){
            alert("Error: " + status);
          });
      };
      $scope.close = function() {
        $modalInstance.dismiss();
      }
    };
  }
]);
