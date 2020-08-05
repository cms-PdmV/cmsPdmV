angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
  function resultsCtrl($scope, $http, $location, $window, $modal){
    $scope.requests_defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
        {text:'Approval',select:true, db_name:'approval'},
        {text:'Status',select:true, db_name:'status'},
        //{text:'MCDBId',select:true, db_name:'mcdb_id'},
        {text:'Dataset name',select:true, db_name:'dataset_name'},
        //{text:'SW Release',select:false, db_name:'cmssw_release'},
        //{text:'Type',select:false, db_name:'type'},
        {text:'History',select:true, db_name:'history'},
        {text:'Tags',select:true, db_name:'tags'}
    ];
    $scope.requests_renames = {
        'ppd_tags': 'PPD tags',
        'interested_pwg':'Interested PWGs',
    };
    //$scope.searchable_fields= [{"name":"generators", "value":""},{"name":"energy", "value":""},{"name":"notes", "value":""},{"name":"dataset_name", "value":""},{"name":"pwg","value":""},{"name":"status", "value":""},{"name":"approval","value":""}];

    $scope.filt = {}; //define an empty filter
    $scope.update = {};
    $scope.chained_campaigns = [];
    $scope.stats_cache = {};
    $scope.full_details = {};
    $scope.action_report= {};
    $scope.action_status= {};
    $scope.underscore = _;
    $scope.file_was_uploaded = false;
    $scope.image_width = 150;
    $scope.tabsettings = {
      "view":{
        active:false
      },
      "search":{
        active:false
      },
      "file":{
        active:false
      },
      "navigation":{
        active:false
      },
      "output":{
        active:false
      }
    };

    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "requests";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    if($location.search()["query"] === undefined){
	//$location.search("query",'""');
    }

  $scope.setFailure = function(status){
    $scope.update["success"] = false;
    $scope.update["fail"] = true;
    $scope.update["status_code"] = status;
  };

  $scope.setSuccess = function(status){
	  $scope.update["success"] = true;
	  $scope.update["fail"] = false;
	  $scope.update["status_code"] = status;
	  $scope.getData();
  };

  $scope.parse_one = function( report ){
    $scope.action_status[report['prepid']] = report['results'];
    if ( report ['results'] == true)
    {
	    $scope.action_report[report['prepid']] = 'OK';
	    return false;
    }else
    {
	    $scope.action_report[report['prepid']] = report['message'];
	    console.log( report )
	    return true;
    }
  };
  $scope.parse_one_report = function (report,status){
	  if (_.isArray(report)){
	    return $scope.parse_one_only(report[0], status);
	  }else{
	    return $scope.parse_one_only(report, status);
	  }
  };

    $scope.parse_one_only = function (report,status){
      if ($scope.parse_one( report ))
      {
	      $scope.setFailure(status);
      }else
      {
	      $scope.setSuccess(status);
      }
    };
    $scope.delete_object = function(db, value){
        $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
		$scope.parse_one_only(data,status);
        }).error(function(status){
		$scope.setFailure(status);
        });
    };
    $scope.single_step = function(step, prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/'+step+'/'+prepid}).success(function(data,status){
	      $scope.action_status[prepid] = data['results'];
	      if (data['results']){
		      $scope.update["success"] = data["results"];
		      $scope.update["fail"] = false;
		      $scope.update["status_code"] = data["results"];
		      $scope.action_report[prepid] = 'OK';
	        $scope.getData();
	      } else{
	        $scope.update["fail"] = true;
	        $scope.update["status_code"] = data['message'];
	        $scope.action_report[data['prepid']] = data['message'];
        }
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };

    $scope.next_status = function(prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/status/'+prepid}).success(function(data,status){
        $scope.parse_one_only(data,status);
      }).error(function(status){
	      $scope.setFailure(status);
      });
    };

    $scope.register = function(prepid){
	    $http({method:'GET', url:'restapi/'+$scope.dbName+'/register/'+prepid}).success(function(data,status){
        $scope.parse_one_only(data,status);
	    }).error(function(status){
		    $scope.setFailure(status);
		  });
    };

    $scope.inspect = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/inspect/'+prepid}).success(function(data,status){
        $scope.parse_one_report(data,status);
	    }).error(function(status){
		    $scope.setFailure(status);
		  });
    };
    $scope.loadStats = function () {
      for (var a in $scope.result) {
        if (-1 != $scope.selected_prepids.indexOf($scope.result[a].prepid)) {
          for (var b in $scope.result[a].reqmgr_name) {
            this.$broadcast("loadDataSet", [$scope.result[a].prepid, $scope.result[a].reqmgr_name[b].name, $scope.result[a].reqmgr_name[b]]);
          }
        }
      }
    };
    $scope.delete_edit = function(id){
      $scope.delete_object($scope.dbName, id);
    };

    $scope.sort = {
      column: 'prepid',
      descending: false
    };

    $scope.selectedCls = function(column) {
      return column == $scope.sort.column && 'sort-' + $scope.sort.descending;
    };

    $scope.changeSorting = function(column) {
      if (column == "filter_efficiency")
      {
        // when switching to filter_efficienty the actual value is in generator parameters
        column = "generator_parameters.slice(-1)[0]['filter_efficiency']"
      }
      var sort = $scope.sort;
      if (sort.column == column) {
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };

    $scope.parseColumns = function () {
        if ($scope.result.length != 0) {
            columns = _.keys($scope.result[0]);
            columns.push("filter_efficiency");
            columns.sort();
            rejected = _.reject(columns, function (v) {
                return v[0] == "_";
            }); //check if charat[0] is _ which is couchDB value to not be shown

            $scope.columns = _.sortBy(rejected, function (v) {
                return v;
            });  //sort array by ascending order
            _.each(rejected, function (v) {
                add = true;
                _.each($scope.requests_defaults, function (column) {
                    if (column.db_name == v) {
                        add = false;
                    }
                });
                if (add) {
                    if (v in $scope.requests_renames) {
                        $scope.requests_defaults.push({text: $scope.requests_renames[v], select: false, db_name: v});
                    } else {
                        $scope.requests_defaults.push({text: v[0].toUpperCase() + v.substring(1).replace(/\_/g, ' '), select: false, db_name: v});
                    }
                }
            });
            if (_.keys($location.search()).indexOf('fields') != -1) {
                _.each($scope.requests_defaults, function (elem) {
                    elem.select = false;
                });
                _.each($location.search()['fields'].split(','), function (column) {
                  _.each($scope.requests_defaults, function (elem) {
                    if (elem.db_name == column) {
                      elem.select = true;
                    }
                  });
                });
            }
        }
    };

  $scope.getData = function(){
    if ($scope.file_was_uploaded)
    {
      $scope.upload($scope.uploaded_file);
    }
    else if ($location.search()['range']!=undefined)
    {
      var tmp = $location.search()['range'].split(";");
      var imaginary_file = [];
      _.each(tmp, function (elem) {
        var ranges = elem.split(",");
        if (ranges.length > 1 )
        {
          imaginary_file.push(ranges[0] + " -> " + ranges[1]);
        }else
        {
          imaginary_file.push(ranges[0]);
        }
      });
      $scope.upload({contents: imaginary_file.join("\n")});
      $scope.file_was_uploaded = false;
      $scope.selectionReady = true;
    } else {
      $scope.got_results = false; //to display/hide the 'found n results' while reloading
      var get_raw;
      if ($location.search()['allRevisions'])
      {
        $scope.requests_defaults.splice(1, 1, {text:'Revision', select:true, db_name:'_rev'});
        var promise = $http.get("restapi/"+$scope.dbName+"/all_revs/"+$location.search()['prepid']);
      } else if($location.search()["from_notification"]){
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
          var get_raw=true;
          var promise = $http.get("search?"+ "db_name="+$scope.dbName+query+"&get_raw");
      }
      promise.then(function(data){
        if (data.data.rows === undefined){
            $scope.result = data.data;
        }else{
            $scope.result = _.pluck(data.data.rows, 'doc');
        }
        $scope.result_status = data.status;
        $scope.got_results = true;
        if ($scope.result === undefined ){
          alert('The following url-search key(s) is/are not valid : '+_.keys(data.data));
          return; //stop doing anything if results are undefined
        }
        $scope.parseColumns();
        $scope.selectionReady = true;
      },function(){
        alert("Error getting information");
      });
    }
  };

   $scope.$watch(function() {
      var loc_dict = $location.search();
      return "page" + loc_dict["page"] + "limit" +  loc_dict["limit"];
    },
    function(){
        $scope.getData();
        $scope.selected_prepids = [];
    });


  $scope.showapproval = false;
  $scope.showApprovals = function(){
    if ($scope.showapproval){
      $scope.showapproval = false;
    }
    else{
      $scope.showapproval = true;
    }
  };
  $scope.selected_prepids = [];
  $scope.add_to_selected_list = function(prepid){
    if (_.contains($scope.selected_prepids, prepid)){
      $scope.selected_prepids = _.without($scope.selected_prepids,prepid);
    }else{
      $scope.selected_prepids.push(prepid);
    }
  };

  $scope.parse_report = function(data,status){
    to_reload=true;
    for (i=0;i<data.length;i++){
      $scope.action_status[data[i]['prepid']] = data[i]['message'];
      if ($scope.parse_one ( data[i] )){
		    to_reload=false;
      }
    }
    if (to_reload == true){
      $scope.setSuccess(status);
    }else{
      $scope.setFailure(status);
    }
  };

  $scope.next_approval = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+$scope.selected_prepids.join()}).success(function(data,status){
      $scope.parse_report(data,status);
    }).error(function(data,status){
	    $scope.setFailure(status);
    });
  };

  $scope.previous_approval = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/reset/'+$scope.selected_prepids.join()}).success(function(data,status){
	    $scope.parse_report(data,status);
    }).error(function(data,status){
      $scope.setFailure(status);
    });
  };

  $scope.optionreset_several = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/option_reset/'+$scope.selected_prepids.join()}).success(function(data,status){
	    $scope.parse_report(data,status);
    }).error(function(data,status){
      $scope.setFailure(status);
    });
  };

  $scope.status_toggle = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/status/'+$scope.selected_prepids.join()}).success(function(data,status){
	    $scope.parse_report(data,status);
    }).error(function(data,status){
      alert("Error while processing request. Code: "+status);
    });
  };

  $scope.register_several = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/register/'+$scope.selected_prepids.join()}).success(function(data,status){
	    $scope.parse_report(data,status);
	  }).error(function(data,status){
		  alert("Error while processing request. Code: "+status);
	  });
  };

  $scope.inspect_many = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/inspect/'+$scope.selected_prepids.join()}).success(function(data,status){
      $scope.parse_report(data,status);
	  }).error(function(data,status){
      alert("Error while processing request. Code: "+status);
    });
  };

  $scope.softreset_many = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/soft_reset/'+$scope.selected_prepids.join()}).success(function(data,status){
      $scope.parse_report(data,status);
    }).error(function(data,status){
      alert("Error while processing request. Code: "+status);
    });
  };

  $scope.submit_many = function(){
    /* submit many requests. On successfully submited ones open a status watching page*/
    if($scope.selected_prepids.length == 0 ){
      alert("You have selected no requests for multiple actions");
      return;
    }
    $scope.pendingHTTP = true;

    var promise = $http.get("restapi/"+$scope.dbName+"/inject/"+$scope.selected_prepids.join()+"/thread");
      promise.then(function(data){
        $scope.pendingHTTP = false;
        $scope.openSubmissionModal(data.data);
        // return data.data;
      },function(){
        $scope.pendingHTTP = false;
        alert("Error while submiting");
      });
  };

  $scope.approvalIcon = function(value){
    icons = { 'none':'icon-off',
		  'validation' : 'icon-eye-open',
		  'define' : 'icon-check',
		  'approve' : 'icon-share',
		  'submit' : 'icon-ok'
    }
    if (icons[value]){
	    return icons[value];
    }else{
	    return  "icon-question-sign";
    }
  };

  $scope.statusIcon = function(value){
    icons = {'new' :  'icon-edit',
	       'validation' : 'icon-eye-open',
	       'defined' : 'icon-check',
	       'approved' : 'icon-share',
	       'submitted' : 'icon-inbox',
	       'injected' : 'icon-envelope',
	       'done' : 'icon-ok'
    }
    if (icons[value]){
	    return icons[value] ;
    }else{
	    return "icon-question-sign" ;
    }
  };

  $scope.clone = function(prepid){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/clone/'+prepid}).success(function(data,status){
      $scope.update["success"] = data["results"];
      $scope.update["fail"] = false;
      $scope.update["status_code"] = data["results"];
      $window.open("edit?db_name=requests&query="+data["prepid"]);
      $scope.getData();
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
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


  $scope.open_isSureModal = function(action, prepid){
      var isSure = $modal.open( {
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
      isSure.result.then(function() {
          if (prepid == 'selected requests') {
              switch (action) {
                  case 'reset':
                      $scope.previous_approval();
                      break;
                  case 'option reset':
                      $scope.optionreset_several();
                      break;
                  case 'approve':
                      $scope.next_approval();
                      break;
                  case 'soft reset':
                      $scope.softreset_many();
                      break;
                  default:
                      break;
              }
          } else {
              switch (action) {
                  case "toggle":
                      $scope.next_status(prepid);
                      break;
                  case "approve":
                      $scope.single_step('approve', prepid);
                      break;
                  case "reset":
                      $scope.single_step('reset', prepid);
                      break;
                  case "option_reset":
                      $scope.single_step('option_reset', prepid);
                      break;
                  case "soft_reset":
                      $scope.single_step('soft_reset', prepid);
                      break;
                  case "delete":
                      $scope.delete_object('requests', prepid);
                      break;
                  case "clone":
                      $scope.clone(prepid);
                      break;
                  case "forcecomplete":
                      $scope.add_to_focecomplete(prepid);
                      break;
                  default:
                      break;
              }
          }
      });
  };


  /* Multiple selection modal actions*/
  $scope.openSubmissionModal = function (injectModalData){

      var submissionModal = $modal.open({
          templateUrl: 'submissionModal.html',
          controller: SubmissionModalInstance,
          resolve: {
              inject_data : function() {
                return injectModalData;
              }
          }
      });

      submissionModal.result.then(function() {
          $scope.selected_prepids = [];
      });
  };


  /* Notify modal actions */
  $scope.openNotifyModal = function(prepid){

      if (!prepid) {
        prepid = $scope.selected_prepids;
      }
      if (_.isString(prepid)) {
        prepid = [prepid]
      }
      var notifyModal = $modal.open( {
         templateUrl: 'notifyModal.html',
          controller: NotifyModalInstance
      });

      notifyModal.result.then(function(text){
        $http({method:'PUT', url:'restapi/'+$scope.dbName+'/notify/', data:JSON.stringify({prepids: prepid, message: text})}).success(function(data,status){

          $scope.update["success"] = true;
          $scope.update["fail"] = false;
          $scope.update["status_code"] = status;
          $scope.update["message"] = data[0]["message"];
          $scope.selected_prepids = [];

        }).error(function(data,status){
          $scope.setFailure(status);
        });
    })
  };


  $scope.openCloneModal = function(id, pwg, campaign)
  {


    var promise1 = $http.get("restapi/users/get_pwg/"+$scope.user.name);
    promise1.then(function(data){
        var all_pwgs = data.data.results;
        if (all_pwgs.indexOf(pwg)==-1){
            all_pwgs.push(pwg);
        }


         var cloneModal = $modal.open({
              templateUrl: 'cloneModal.html',
              controller: CloneModalInstance,
              resolve: {
                  cloneId : function() {
                    return id;
                  },
                  clonePWG : function() { //modal's selected parameter
                      return pwg;
                  },
                  cloneCampaign : function() {
                      return campaign;
                  },
                  allPWGs: function() {
                      return all_pwgs;
                  }
              }
          });

          cloneModal.result.then(function(input_dict)
          {
            var tmpClone = _.clone(_.find($scope.result, function(element) {
                return element.prepid == id;
            }));
            if(!tmpClone) {
                tmpClone = {};
            }
            tmpClone["member_of_campaign"] = input_dict["campaign"];
            tmpClone["pwg"] = input_dict["pwg"];
            $http({method:'PUT', url:'restapi/'+$scope.dbName+'/clone/', data:tmpClone}).success(function(data,status){

              $scope.update["success"] = data["results"];
              $scope.update["fail"] = !data["results"];
              $scope.update["status_code"] = status;
              if (data["message"])
              {
                $scope.update["status_code"] = data["message"];
              }
              if (data["prepid"])
              {
                $window.open("edit?db_name=requests&query="+data["prepid"]);
              }
              $scope.update["message"] = data;
            }).error(function(data,status){

              $scope.update["success"] = false;
              $scope.update["fail"] = true;
              $scope.update["status_code"] = status;
              $scope.update["message"] = data;
            });
          });
      });

  };

  /* --Modals actions END--*/

  $scope.update_filtered = function(){
    $scope.test_display = _.clone($scope.result);
      _.each($scope.filt, function(filter_column, key){
    });
  };

  $scope.linkify = function(inputText) {
    var replaceText, replacePattern1, replacePattern2, replacePattern3;

    replacedText = inputText;

    //URLs starting with http://, https://, or ftp://
    //    replacePattern1 = /(\b(https?|ftp):\/\/[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/gim;
    //    replacedText = inputText.replace(replacePattern1, '<a href="$1" target="_blank"><i class="icon-shopping-cart"></i></a>');

    //URLs starting with "www." (without // before it, or it'd re-link the ones done above).
    //    replacePattern2 = /(^|[^\/])(www\.[\S]+(\b|$))/gim;
    //    replacedText = replacedText.replace(replacePattern2, '$1<a href="http://$2" target="_blank"><i class="icon-shopping-cart"></i></a>');

    //replace anything that is /.../DQM
    replacePattern3 = /.*,\s+(\/.*DQM)/gim;
    //replacePattern3 = /(\/.*DQM)/gim;
    if ($scope.isDevMachine()){
	replacedText = replacedText.replace(replacePattern3, '<a href="https://cmsweb-testbed.cern.ch/dqm/dev/start?runnr=1;dataset=$1;workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for $1" target="_blank"><i class="icon-th-large"></i></a>');}
    else{
	replacedText = replacedText.replace(replacePattern3, '<a href="https://cmsweb.cern.ch/dqm/relval/start?runnr=1;dataset=$1;workspace=Everything;root=Generator;sampletype=offline_relval" rel="tooltip" title="Go to the DQM gui for $1" target="_blank"><i class="icon-th-large"></i></a>');}

    return replacedText.replace(/\n/g,"<br>")  //return formatted links with new line to <br> as HTML <P> tag skips '\n'
  }

  $scope.togglePane = function(val){
    if (val){
      return true;
    }else{
      return false;
    }
  };

  $scope.upload = function(file){
    $scope.file_was_uploaded = true;
    $scope.uploaded_file = file;
    /*Upload a file to server*/
    $scope.got_results = false;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
      $scope.result = data.results;
      $scope.result_status = data.status;
      $scope.got_results = true;
      $scope.parseColumns();
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };

  $scope.findToken = function(tok){
    $window.location.href = "requests?&tags="+tok.value
  };

  $scope.get_list = function()
  {
    if ($scope.selected_prepids.length > 0)
    {
      var imaginary_file = [];
      _.each($scope.selected_prepids, function(elem)
      {
        imaginary_file.push(elem);
      });
      $scope.upload({"contents": imaginary_file.join("\n")});
      $scope.file_was_uploaded = false;
    }
  };
  $scope.add_to_focecomplete = function(prepid)
  {
    // PUT a request to force complete list
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/add_forcecomplete', data: {'prepid': prepid}}).success(function(data,status){
      $scope.update["success"] = data["results"];
      $scope.update["fail"] = !data["results"];
      $scope.update["status_code"] = status;
      if (data["message"])
      {
        // if we have an actual message returned display it instead of status code
        $scope.update["status_code"] = data["message"];
      }
      if ($scope.update["success"])
      {
        // reload the data to display history changes
        $scope.getData();
      }
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };

  $scope.getLinktoDmytro = function(wf_data,prepid,text){
    // return a link to computings private monitoring of requests url:
    // https://dmytro.web.cern.ch/dmytro/cmsprodmon/workflows.php?prep_id=
    var base_link = "https://dmytro.web.cern.ch/dmytro/cmsprodmon/workflows.php?prep_id="
    if (wf_data[wf_data.length - 1])
    { //we check if wf exists...
      var name = wf_data[wf_data.length - 1]["name"];
      var prepid = name.slice(
          name.indexOf("-")-3,
          name.lastIndexOf("-")+6); //-3 for PWG +6 for '-numerical_id'

      if (name.indexOf("task") != -1) //we check if it was a taskchain
      {
        return base_link + "task_" + prepid;
      }
      else {
        return base_link + prepid;
      }
    }
    else {
      return "";
    }
  };

  $scope.reserveAndApprove = function(chainID){
    console.log("about to reserve and approve chain", chainID);

    $http({method:'GET', url:'restapi/'+$scope.dbName+'/reserveandapprove/'+chainID}).success(function(data, status){
      $scope.update["success"] = data["results"];
      $scope.update["fail"] = !data["results"];
      $scope.update["status_code"] = status;
      if (data["message"])
      {
        // if we have an actual message returned display it instead of status code
        $scope.update["status_code"] = data["message"];
      }
      if ($scope.update["success"])
      {
        // reload the data to display history changes
        $scope.getData();
      }
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };
}]);

var NotifyModalInstance = function($scope, $modalInstance) {
  $scope.data = {text: ""};

  $scope.notify = function() {
    $modalInstance.close($scope.data.text);
  };

  $scope.close = function() {
    $modalInstance.dismiss();
  };
};

var SubmissionModalInstance = function($scope, $modalInstance, $window, inject_data) {
  $scope.data = {
    injectModalData: inject_data,
    anySuccessful: _.some(inject_data, function(elem) {
      return elem["results"];
    })
  };

  $scope.openInjectStatus = function() {
    var prepids = [];
    _.each($scope.data.injectModalData, function(element){
      if(element["results"]) {
        prepids.push(element["prepid"]);
      }
    });
    $window.open("injection_status?prepid="+prepids.join());
    $modalInstance.close();
  };

  $scope.close = function() {
    $modalInstance.dismiss();
  };
};

var CloneModalInstance = function($http, $scope, $modalInstance, cloneId, clonePWG, cloneCampaign, allPWGs) {
  $scope.data = {
    cloneId: cloneId,
    clonePWG: clonePWG,
    cloneCampaign: cloneCampaign
  };
  $scope.allPWGs = allPWGs;
  $scope.allCampaigns = [];

  var promise = $http.get("restapi/campaigns/listall"); //get list of all campaigns for flow editing
  promise.then(function(data){
    $scope.allCampaigns = data.data.results;
  });

  $scope.clone = function() {
    $modalInstance.close({"pwg":$scope.data.clonePWG, "campaign":$scope.data.cloneCampaign});
  };

  $scope.close = function() {
    $modalInstance.dismiss();
  };
};

// NEW for directive
// var testApp = angular.module('testApp', ['ui.bootstrap']).config(function($locationProvider){$locationProvider.html5Mode(true);});
testApp.directive("customApproval", function(){
  return{
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="display_table">'+
    '    <input type="button" value="Show" ng-click="display_approval()">'+
    '    {{whatever.length}} step(-s)'+
    '  </div>'+
    '  <div ng-show="display_table">'+
    '    <input type="button" value="Hide" ng-click="display_approval()">'+
    '    {{whatever.length}} step(-s)'+
    '    <table class="table table-bordered" style="margin-bottom: 0px;">'+
    '      <thead>'+
    '        <tr>'+
    '          <th style="padding: 0px;">Index</th>'+
    '          <th style="padding: 0px;">Approver</th>'+
    '          <th style="padding: 0px;">Step</th>'+
    '        </tr>'+
    '      </thead>'+
    '      <tbody>'+
    '        <tr ng-repeat="elem in approval">'+
    '          <td style="padding: 0px;">{{elem.index}}</td>'+
    '          <td style="padding: 0px;">{{elem.approver}}</td>'+
    '          <td style="padding: 0px;">{{elem.approval_step}}</td>'+
    '        <tr>'+
    '      </tbody>'+
    '    </table>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.whatever = ctrl.$viewValue;
      };
      scope.display_table= false;
      scope.approval = {};
      scope.display_approval = function(){
        if (scope.display_table){
          scope.display_table = false;
        }else{
          scope.display_table = true;
          scope.approval = ctrl.$viewValue;
        }
      };
    }
  }
});

testApp.directive("sequenceDisplay", function($http){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="show_sequence">'+
    '    <a rel="tooltip" title="Show" ng-click="getCmsDriver();show_sequence=true;">'+
    '     <i class="icon-eye-open"></i>'+
    '    </a>'+
    '  </div>'+
    '  <div ng-show="show_sequence">'+
    '    <a rel="tooltip" title="Hide" ng-click="show_sequence=false;">'+
    '     <i class="icon-remove"></i>'+
    '    </a>'+
    '    <ul>'+
    '      <li ng-repeat="sequence in driver"><div style="width:600px;overflow:auto"><pre>{{sequence}}</pre></div></li>'+
    '    </ul>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_sequence = false;
        scope.sequencePrepId = ctrl.$viewValue;
      };

      scope.getCmsDriver = function(){
        if (scope.driver ===undefined){
          var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.sequencePrepId);
          promise.then(function(data){
            scope.driver = data.data.results;
          }, function(data){
            alert("Error: ", data.status);
          });
        }
      };
   }
  }
});

testApp.directive("generatorParams", function($http){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <ul ng-repeat="param in all_data" ng-switch on="$index < all_data.length-1">'+
    '    <li ng-switch-when="true">'+
    '      <a ng-click="viewOldGenParam($index)" ng-hide="display_list.indexOf($index) != -1"><i class="icon-eye-open"></i></a>'+  //elements to be viewed on-click
    '      <a ng-click="viewOldGenParam($index)" ng-show="display_list.indexOf($index) != -1"><i class="icon-eye-close"></i></a>'+  //elements to be viewed on-click
    '      <span ng-show="display_list.indexOf($index) != -1">'+ //if index in list of possible views -> then display
    '        <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;">'+
    '          <dt>{{"version"}}</dt>'+
    '          <dd class="clearfix">{{param["version"]}}</dd>'+
    '          <dt>{{"cross section"}}</dt>'+
    '          <dd class="clearfix">{{param["cross_section"]}}'+
    '          <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '          </dd>'+
    '          <dt>{{"filter efficiency"}}</dt>'+
    '          <dd class="clearfix">{{param["filter_efficiency"]}}</dd>'+
    '          <dt>{{"filter efficiency error"}}</dt>'+
    '          <dd class="clearfix">{{param["filter_efficiency_error"]}}</dd>'+
    '          <dt>{{"match efficiency"}}</dt>'+
    '          <dd class="clearfix">{{param["match_efficiency"]}}</dd>'+
    '          <dt>{{"match efficiency error"}}</dt>'+
    '          <dd class="clearfix">{{param["match_efficiency_error"]}}</dd>'+
    '          <dt>{{"author username"}}</dt>'+
    '          <dd class="clearfix">{{param["submission_details"]["author_username"]}}</dd>'+
    '        </dl>'+
    '      </span>'+
    '    </li>'+
    '    <li ng-switch-when="false">'+ //last parameter to be displayed all the time
    '      <dl class="dl-horizontal" style="margin-bottom: 0px; margin-top: 0px;">'+
    '        <dt>{{"version"}}</dt>'+
    '        <dd class="clearfix">{{param["version"]}}</dd>'+
    '        <dt>{{"cross section"}}</dt>'+
    '        <dd class="clearfix">{{param["cross_section"]}}'+
    '          <a class="label label-info" rel="tooltip" title="pico barn" ng-href="#">pb</a>'+
    '        </dd>'+
    '        <dt>{{"filter efficiency"}}</dt>'+
    '        <dd class="clearfix">{{param["filter_efficiency"]}}</dd>'+
    '        <dt>{{"filter efficiency error"}}</dt>'+
    '        <dd class="clearfix">{{param["filter_efficiency_error"]}}</dd>'+
    '        <dt>{{"match efficiency"}}</dt>'+
    '        <dd class="clearfix">{{param["match_efficiency"]}}</dd>'+
    '        <dt>{{"match efficiency error"}}</dt>'+
    '        <dd class="clearfix">{{param["match_efficiency_error"]}}</dd>'+
    '        <dt>{{"negative weights fraction"}}</dt>'+
    '        <dd class="clearfix">{{param["negative_weights_fraction"]}}</dd>'+
    '        <dt>{{"author username"}}</dt>'+
    '        <dd class="clearfix">{{param["submission_details"]["author_username"]}}</dd>'+
    '      </dl>'+
    '    </li>'+
    '  </ul>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.all_data = ctrl.$viewValue;
        scope.display_list = [_.size(scope.all_data)-1];
        scope.last_param = scope.all_data[_.size(scope.all_data)-1];
      };
      scope.viewOldGenParam = function(index){
        if (_.contains(scope.display_list,index)){
          scope.display_list = _.without(scope.display_list,index)
        }else{
          scope.display_list.push(index);
        }
        scope.display_list = _.uniq(scope.display_list);
      };
    }
  };
});

testApp.directive("loadFields", function($http, $location){
  return {
    replace: true,
    restrict: 'E',
    template:
    '<div>'+
    '  <form class="form-inline">'+
    '    <span class="control-group navigation-form" bindonce="searchable" ng-repeat="key in searchable_fields">'+
    '      <label style="width:140px;">{{key}}</label>'+
    '      <input class="input-medium" type="text" ng-model="listfields[key]" typeahead="suggestion for suggestion in loadSuggestions($viewValue, key)">'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '</div>'
    ,
    link: function(scope, element, attr)
    {
      scope.listfields = {};
      scope.showUrl = false;
      scope.is_prepid_in_url = $location.search()["prepid"];
      scope.test_values = [];
      scope.test_data = "";

      scope.searchable_fields = [
        'status',
        'member_of_chain',
        'prepid',
        'extension',
        'tags',
        'energy',
        'mcdb_id',
        'flown_with',
        'pwg',
        'process_string',
        'generators',
        'member_of_campaign',
        'approval',
        'dataset_name'
      ];

      scope.zeroPad = function(num, places){
        var zero = places - num.toString().length + 1;
        return Array(+(zero > 0 && zero)).join("0") + num;
      };

      scope.goToNextPrepid = function(increment){
        if($location.search()["prepid"]){
          var prepid = $location.search()["prepid"];
          lastnumber = parseInt(prepid.substring(prepid.length-5))+increment;
          var new_prepid = prepid.substring(0,prepid.length-5)+scope.zeroPad(lastnumber, 5);
          $location.search("prepid", new_prepid);
          scope.getData();
        }
      };

      scope.cleanSearchUrl = function(){
        _.each($location.search(),function(elem,key){
          $location.search(key,null);
        });
        $location.search("page",0);
      };

      scope.getUrl = function(){
        scope.cleanSearchUrl();
         //var url = "?";
        _.each(scope.listfields, function(value, key){
          if (value != ""){
            //url += key +"=" +value+"&";
            $location.search(key,String(value));
          }else{
            $location.search(key,null);//.remove(key);
          }
        });
        scope.getData();
      };

      scope.loadSuggestions = function (fieldValue, fieldName) {
        if (fieldValue == '') {
          return {};
        }

        var searchURL = "restapi/requests/unique_values/" + fieldName;
        searchURL += "?limit=10&group=true";
        searchURL += '&startkey=' + fieldValue + '&endkey=' + fieldValue + '\ufff0';

        var promise = $http.get(searchURL);
        return promise.then(function(data){
          return data.data.results;
        }, function(data){
          alert("Error getting suggestions for " + fieldName + " field (value=" + fieldValue + "): " + data.status);
        });
      };
    }
  }
});

testApp.directive("customActorList", function($http){
  return {
    restrict: 'EA',
    template:
    '<span>'+
    '  <a ng-href="#" ng-click="getActors();" tooltip-html-unsafe="{{actors}}" tooltip-trigger="click" tooltip-placement="bottom">'+
    '    <i class="icon-user"></i>'+
    '  </a>'+
    '</span>',
    link: function(scope, element, attrs){
      scope.actors = "<ul> </ul>";
      scope.prepid = scope.$eval(attrs.prepid);
      scope.getActors = function () {
        if ( scope.actors == "<ul> </ul>")
        {
          var promise = $http.get("public/restapi/requests/get_actors/"+scope.prepid);
          promise.then(function (data) {
            scope.actors = "<ul>";
            _.each(data.data, function (user) {
              tmp = "<li>" + "<a href='users?page=0&username=" + user + "' target='_blank'>"+user+"</a>" + "</li>";
              scope.actors += tmp;
            });
            scope.actors += "</ul>"
          }, function (data){
            alert("Error getting actor list: ", data.data.results);
          });
        }
      }
   }
  }
});

testApp.directive("fragmentDisplay", function($http){
  return {
    require: 'ngModel',
    template:
    '<div ng-show="fragment && fragment.length">'+
    '  <a ng-show="!show_fragment" rel="tooltip" title="Show fragment" ng-click="showFragment();">'+
    '    <i class="icon-eye-open"></i>'+
    '  </a>'+
    '  <a ng-show="show_fragment" rel="tooltip" title="Hide fragment" ng-click="show_fragment = false;">'+
    '    <i class="icon-remove"></i>'+
    '  </a>'+
    '  <a ng-href="public/restapi/requests/get_fragment/{{prepid}}/0" rel="tooltip" title="Open fragment in new tab" target="_blank">'+
    '    <i class="icon-fullscreen"></i>'+
    '  </a>'+
    '  <div ng-show="show_fragment">'+
    '    <textarea ui-codemirror="{ theme:\'eclipse\', readOnly:true}" ui-refresh=true ng-model="fragment"></textarea>'+
    '  </div>'+
    '</div>',
    link: function(scope, element, attrs, ctrl){
      ctrl.$render = function(){
        scope.show_fragment = false;
        scope.prepid = ctrl.$viewValue;
        scope.fragment = attrs.rawfragment;
        scope.refreshedEditor = false;
      };
      scope.showFragment = function() {
        scope.show_fragment = true;
        if (!scope.refreshedEditor) {
          scope.refreshedEditor = true;
          setTimeout(() => {
            const textarea = angular.element(element)[0].querySelector('textarea');
            const editor = CodeMirror.fromTextArea(textarea);
            editor.setSize(null, 'auto');
            editor.refresh();
          }, 100);
        }
      };
   }
  }
});