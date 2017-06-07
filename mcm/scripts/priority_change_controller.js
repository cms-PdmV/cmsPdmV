angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window','$modal',
  function resultsCtrl($scope, $http, $location, $window, $modal){
    $scope.selected_pane = 'Requests'
    $scope.objects_in_page = [];
    $scope.form_fields = {};
    $scope.page = 0;
    $scope.limit = 20;
    $scope.do_next_page = false;
    $scope.select_btn = 'Select all';
    $scope.global_action_parameters = {
      'block_number': 0,
      'threshold': 0,
      'staged': 0,
      'flag': false
    }
    $scope.priority_blocks = {
      110000: 1,
      90000: 2,
      85000: 3,
      80000: 4,
      70000: 5,
      63000: 6
    };

    $scope.search = function(){
      if (!$scope.get_selected_pane()){
        return;
      }
      $scope.global_action_parameters = {
        'block_number': 0,
        'threshold': 0,
        'staged': 0,
        'flag': false
      }
      $scope.select_btn = "Select all";
      if ($scope.selected_pane == "Requests"){
        $scope.search_requests();
      } else if ($scope.selected_pane == "Chained requests"){
        $scope.search_chains('chained_requests');
      }else{
        $scope.search_chains('chained_campaigns');
      }
    };

    $scope.search_requests = function(){
      var prepid = "*";
      var tag = "";
      if ($scope.form_fields.request_prepid && $scope.form_fields.request_prepid.trim() != ""){
        prepid = "*" + $scope.form_fields.request_prepid + "*";
      }
      if ($scope.form_fields.request_tag && $scope.form_fields.request_tag.trim() != ""){
        tag = "&tags=*" + $scope.form_fields.request_tag + "*";
      }
      var promise = $http.get("search/?db_name=requests&page=" + $scope.page + "&limit=" + $scope.limit + "&include_fields=prepid,priority&prepid=" + prepid + tag);
        return promise.then(function(data){
          $scope.objects_in_page = data.data.results;
          $scope.do_next_page = $scope.objects_in_page.length < $scope.limit ? false: true;
          for (var index in $scope.objects_in_page){
            var request = $scope.objects_in_page[index];
            request.priority = $scope.priority_blocks[request.priority];
            request['selected'] = false;
          };
        }, function(data){
          alert("Error getting requests: " + data.status);
        });
    };

    $scope.search_chains = function(database){
      var prepid = "*";
      if ($scope.form_fields.chained_request_prepid && $scope.form_fields.chained_request_prepid.trim() != "" && $scope.selected_pane == "Chained requests"){
        prepid = "*" + $scope.form_fields.chained_request_prepid + "*";
      } else if ($scope.form_fields.chained_campaign_prepid && $scope.form_fields.chained_campaign_prepid.trim() != ""){
        prepid = "*" + $scope.form_fields.chained_campaign_prepid + "*";
      }
      var promise = $http.get("search/?db_name=" + database + "&page=" + $scope.page + "&limit=" + $scope.limit + "&prepid=" + prepid);
        return promise.then(function(data){
          parsed_data = [];
          var results = data.data.results;
          for (var index in results){
            var dict = {};
            dict['prepid'] = results[index].prepid;
            dict['action_parameters'] = results[index].action_parameters;
            dict['selected'] = false;
            parsed_data.push(dict);
          };
          $scope.do_next_page = parsed_data.length < $scope.limit ? false : true;
          $scope.objects_in_page = parsed_data;
        }, function(data){
          alert("Error getting chains: " + data.status);
        });
    };

    $scope.redirect = function(prepid){
        var path = $scope.selected_pane.replace(" ", "_").toLowerCase() + "?prepid=" + prepid;
        $window.location.href = path;
    }

    $scope.global_change = function(parameter){
      for(var index in $scope.objects_in_page){
        var object = $scope.objects_in_page[index];
        if($scope.selected_pane == "Requests"){
          object['priority'] = $scope.global_action_parameters[parameter];
        }else{
          object.action_parameters[parameter] = $scope.global_action_parameters[parameter];
        }
      }
    }

    $scope.get_selected_pane = function(){
      for (var i in $scope.$$childHead.panes){
        var pane = $scope.$$childHead.panes[i];
        if(typeof(pane.selected) != "undefined" && pane.selected){
          $scope.selected_pane = pane.heading;
          return true;
        }
      };
      return false;
    };

    $scope.preload_tags = function(viewValue)
    {
      var promise = $http.get("restapi/requests/unique_values/tags?limit=10&startkey=" + viewValue);
      return promise.then(function(data){
        return data.data.results;
      }, function(data){
        alert("Error getting searchable fields: " + data.status);
      });
    };

    $scope.submit = function(){
      var objects_to_submit = [];
      for(var index in $scope.objects_in_page){
        var object = $scope.objects_in_page[index];
        if(object.selected){
          objects_to_submit.push(object)
        }
      }
      if(objects_to_submit.length == 0){
        return;
      }
      var object_type = $scope.selected_pane.replace(" ", "_").toLowerCase();
      $http({method:'POST', url:"restapi/" + object_type +"/priority_change", data: objects_to_submit}).success(function(data,status){
        if (data.results){
          alert("Everything went fine!");
          $scope.search();
          return;
        }
        errors = "";
        for(var index in data.message){
          errors += data.message[index] + '\n';
        }
        alert('There were some errors:\n' + errors);
        $scope.search();
      }).error(function(status){
        alert("Something went wrong: " + status);
        $scope.search();
      });
    }

    $scope.update_selected_objects = function(index){
      $scope.objects_in_page[index].selected = !$scope.objects_in_page[index].selected;
    }

    $scope.next_page = function(){
      $scope.page += 1;
      $scope.search();
    }

    $scope.previous_page = function(){
      $scope.page -= 1;
      $scope.search();
    }

    $scope.search_start = function(){
      $scope.page = 0;
      $scope.search();
    }

    $scope.select_all = function(){
      var is_selection = true;
      if($scope.select_btn == "Select all"){
        $scope.select_btn = "Deselect all";
      } else{
        is_selection = false;
        $scope.select_btn = "Select all";
      }
      for (var index in $scope.objects_in_page){
        $scope.objects_in_page[index].selected = is_selection;
      }
    }
}]);