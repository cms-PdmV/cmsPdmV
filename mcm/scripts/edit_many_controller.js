angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window',
  function resultsCtrl($scope, $http, $location, $window){
    $scope.defaults = [];
    $scope.edited_fields = {};
    $scope.dbName = $location.search()["db_name"];
    $scope.update = [];
    $scope.underscore = _;

    $scope.minPrepid = function(string_of_prepids)
    {
      $scope.list_of_prepids = string_of_prepids.split(',');
      var min = $scope.list_of_prepids[0];
      _.each($scope.list_of_prepids,function(v){
        if(v<min)
        {
          min = v;
        }
      });
      return min;
    };

    $scope.prepid = $scope.minPrepid($location.search()["prepid"]);
    if($scope.dbName == "requests")
    {
      // get the editable -> set false in list
      $scope.not_editable_list = ["Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version", "History"]; //user non-editable columns
      $scope.non_multiple_editable= ["Prepid", "Member of campaign", "Pwg", "Status", "Approval", "Type", "Priority", "Completion date", "Member of chain", "Config id", "Flown with", "Reqmgr name", "Completed events","Energy", "Version", "History"]; //user non-editable columns
      var promise = $http.get("restapi/requests/editable/"+$scope.prepid)
      promise.then(function(data)
      {
        $scope.parseEditableObject(data.data.results);
      });
    }
    if($location.search()["page"] === undefined)
    {
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else
    {
      page = $location.search()["page"];
      $scope.list_page = parseInt(page);
    }

    $scope.parseEditableObject = function(editable){
      _.each(editable, function(elem,key){
        if (elem == false){
          if (key[0] != "_"){ //if its not mandatory couchDB values eg. _id,_rev
            column_name = key[0].toUpperCase()+key.substring(1).replace(/\_/g,' ')
            if($scope.not_editable_list.indexOf(column_name) ==-1){
              $scope.not_editable_list.push(column_name);
            }
            if($scope.non_multiple_editable.indexOf(column_name) ==-1){
              $scope.non_multiple_editable.push(column_name);
            }
          }
        }
      });
    };

    $scope.booleanize_sequence = function(sequence){
      _.each(sequence, function(value, key){
        if (_.isString(value))
        {
          switch(value.toLowerCase()){
            case "true":
              sequence[key] = true;
              break;
            case "false":
              sequence[key] = false;
              break;
            default:
              break;
          }
        }
      });
    };

    $scope.submit_edit = function(){
      switch($scope.dbName){
        case "requests":
          _.each($scope.result["sequences"], function(sequence){
            $scope.booleanize_sequence(sequence);
            if (_.isString(sequence["step"]))
            {
              sequence["step"] = sequence["step"].split(",");
            }
            if (_.isString(sequence["datatier"]))
            {
              sequence["datatier"] = sequence["datatier"].split(",");
            }
            if (_.isString(sequence["eventcontent"]))
            {
              sequence["eventcontent"] = sequence["eventcontent"].split(",");
            }
          });
          _.each($scope.result["time_event"], function(value, key){
            $scope.result["time_event"][key] = parseFloat(value);
          });
         $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
          break;
        case "campaigns":
          _.each($scope.result["sequences"], function(sequence){
            _.each(sequence, function(subSequence, key){
              if (key != "$$hashKey") //ignore angularhs hashkey
              {
                $scope.booleanize_sequence(subSequence);
                if (_.isString(subSequence["step"]))
                {
                  subSequence["step"] = subSequence["step"].split(",");
                }
                if (_.isString(subSequence["datatier"]))
                {
                  subSequence["datatier"] = subSequence["datatier"].split(",");
                }
                if (_.isString(subSequence["eventcontent"]))
                {
                  subSequence["eventcontent"] = subSequence["eventcontent"].split(",");
                }
              }
            });
          });
          break;
        case "mccms":
          $scope.result['tags'] = _.map($("#tokenfield").tokenfield('getTokens'), function(tok){return tok.value});
          break;
        case "flows":
          _.each($scope.result["request_parameters"]["sequences"], function(sequence){
            _.each(sequence, function(elem){
              if (_.has( elem, "datatier")){
                if(_.isString(elem["datatier"])){
                  elem["datatier"] = elem["datatier"].split(",");
                }
              }
              if (_.has(elem, "eventcontent")){
                if(_.isString(elem["eventcontent"])){
                  elem["eventcontent"] = elem["eventcontent"].split(",");
                }
              }
            });
          });
          break;
        default:
          break;
      }

      var data_to_send = {};
      data_to_send["updated_data"] = {};
      _.each($scope.edited_fields, function(value,key){
        if(value)
        {
          data_to_send["updated_data"][key] = $scope.result[key];
          $scope.edited_fields[key] = false;
        }
      });
      data_to_send["prepids"] = $scope.list_of_prepids;
      $http({method:'PUT', url:'restapi/'+$location.search()["db_name"]+'/update_many',data:angular.toJson(data_to_send)}).success(function(data,status){
        $scope.update["success"] = data["results"][0]["results"];
        $scope.update["fail"] = false;
        $scope.update["message"] = data["results"][0]["message"];
        $scope.update["status_code"] = status;
        if ($scope.update["success"] == false){
          $scope.update["fail"] = true;
        }else{
          if($scope.sequencesOriginal){
            delete($scope.sequencesOriginal);
          }
          $scope.getData();
        }
      }).error(function(data, status){
        $scope.update["message"] = data;
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    $scope.display_approvals = function(data){
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
      if (sort.column == column){
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };

    $scope.getData = function(){
      var promise = $http.get("restapi/"+ $location.search()["db_name"]+"/get/"+$scope.prepid)
      promise.then(function(data){
        $scope.result = data.data.results;
        if ($scope.result.length != 0){
          columns = _.keys($scope.result);
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
            if($scope.not_editable_list.indexOf(v[0].toUpperCase()+v.substring(1).replace(/\_/g,' ')) == -1)
            {
              $scope.not_editable_list.push(v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '));
            }
          });
          setTimeout(function(){ //update fragment field
            codemirror = document.querySelector('.CodeMirror');
            if (codemirror != null){
              _.each(angular.element(codemirror),function(elem){
                elem.CodeMirror.refresh();
              });
            }
          },300);
        }
      }, function(){ alert("Error getting information"); });
    };

    $scope.$watch('list_page', function(){
      $scope.getData();
    });

    $scope.editableFragment = function(){
      return $scope.not_editable_list.indexOf('Fragment')!=-1;
    };

    $scope.hideSequence = function(roleNumber){
      if ($scope.role(roleNumber)){
        return true; //if we hide by role -> hide
      }else{ //else we check if sequence is in editable list
        if ($scope.not_editable_list.indexOf("Sequences")!=-1){
          return true; //if its in list -> hide
        }else{
          return false; //else let be displayed: ng-hide=false
        }
      }
    };

    $scope.removeUserPWG = function(elem){
      //console.log(_.without($scope.result["pwg"], elem));
      $scope.result["pwg"] = _.without($scope.result["pwg"], elem);
    };

    $scope.showAddUserPWG = function(){
      $scope.showSelectPWG = true;
      var promise = $http.get("restapi/users/get_pwg")
      promise.then(function(data){
        //$scope.all_pwgs = ['BPH', 'BTV', 'EGM', 'EWK', 'EXO', 'FWD', 'HIG', 'HIN', 'JME', 'MUO', 'QCD', 'SUS', 'TAU', 'TRK', 'TOP','TSG','SMP'];
        $scope.all_pwgs = data.data.results;
      });
    };

    $scope.addUserPWG = function(elem){
      if($scope.result["pwg"].indexOf(elem) == -1){
        $scope.result["pwg"].push(elem);
      }
    };

    $scope.addToken = function(tok) {
      $http({method:'PUT', url:'restapi/tags/add/', data:JSON.stringify({tag:tok.value})})
    };

    $scope.toggleNotEditable = function(column_name)
    {
      var name_index = $scope.not_editable_list.indexOf(column_name)
      if(name_index != -1)
      {
        $scope.not_editable_list.splice(name_index,1);
      }else
      {
        $scope.not_editable_list.push(column_name);
      }
    };

    $scope.changeData = function(elem){
      var new_list = [elem]
      _.each($scope.list_of_prepids, function(elem){
        if (new_list.indexOf(elem) == -1)
        {
          new_list.push(elem);
        }
      });
      $location.search("prepid", new_list.join(","));
      $scope.prepid = elem;
      $scope.getData();
    }
  }
]);