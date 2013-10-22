function resultsCtrl($scope, $http, $location, $window){
    $scope.requests_defaults = [
        {text:'PrepId',select:true, db_name:'prepid'},
        {text:'Actions',select:true, db_name:''},
        {text:'Approval',select:true, db_name:'approval'},
        {text:'Status',select:true, db_name:'status'},
        //{text:'MCDBId',select:true, db_name:'mcdb_id'},
        {text:'Dataset name',select:true, db_name:'dataset_name'},
        //{text:'SW Release',select:false, db_name:'cmssw_release'},
        //{text:'Type',select:false, db_name:'type'},
        {text:'History',select:true, db_name:'history'}
    ];
    //$scope.searchable_fields= [{"name":"generators", "value":""},{"name":"energy", "value":""},{"name":"notes", "value":""},{"name":"dataset_name", "value":""},{"name":"pwg","value":""},{"name":"status", "value":""},{"name":"approval","value":""}];
    $search_data = {};

    $scope.filt = {}; //define an empty filter
    $scope.notify_text = "";
    $scope.update = {};
    $scope.show_well = false;
    $scope.notify_Modal = false;
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

    if($location.search()["page"] === undefined){
      page = 0;
      $location.search("page", 0);
      $scope.list_page = 0;
    }else{
      page = $location.search()["page"];
      $scope.list_page = parseInt(page);
    }
    if ($location.search()["db_name"] === undefined){
      $scope.dbName = "requests";
    }else{
      $scope.dbName = $location.search()["db_name"];
    }
    if($location.search()["query"] === undefined){
	//$location.search("query",'""');
    }
    
  $scope.set_fail = function(status){
    $scope.update["success"] = false;
    $scope.update["fail"] = true; 
    $scope.update["status_code"] = status; 
  };

  $scope.set_success = function(status){
	  $scope.update["success"] = true;
	  $scope.update["fail"] = false; 
	  $scope.update["status_code"] = status; 
	  $scope.getData();
  };
    
    $scope.parse_one = function( report ){
	$scope.action_status[report['prepid']] = report['results'];
	if ( report ['results'] == true){
	    $scope.action_report[report['prepid']] = 'OK';
	    return false;
	}else{
	    $scope.action_report[report['prepid']] = report['message'];
	    console.log( report )
	    return true;
	}
    };
    $scope.parse_one_only = function (report,status){
	if ($scope.parse_one( report )){
	    $scope.set_fail(status);}
	else{
	    $scope.set_success(status);}
    };
    $scope.delete_object = function(db, value){
        $http({method:'DELETE', url:'restapi/'+db+'/delete/'+value}).success(function(data,status){
		$scope.parse_one_only(data,status);
        }).error(function(status){
		$scope.set_fail(status);
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
		  if (step=='clone'){
		      // not used anymore
		      $scope.action_report[prepid]= 'OK';
		      $scope.action_status[prepid]
		      $scope.update["status_code"] = 'edit?db_name=requests&query='+data["prepid"];
		  }else{
		      //$window.location.reload();
		      console.log('I want to reload');
		      $scope.getData();
		  }
	      }
	      else{
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
	      $scope.set_fail(status);
      });
    };
    /*
    $scope.submit = function (prepid){
      $http({method:'GET', url: 'restapi/'+$scope.dbName+'/inject/'+prepid}).success(function(data,status){
	      
        $scope.update["success"] = data["results"];
        $scope.update["fail"] = false;
        $scope.update["status_code"] = data["results"];
	 //        $window.location.reload();
      }).error(function(status){
        $scope.update["success"] = false;
        $scope.update["fail"] = true;
        $scope.update["status_code"] = status;
      });
    };
    */
    $scope.load_dataset_list = function (req_name){
	getfrom='/stats/restapi/get_one/'+req_name;
	$http({method:'GET', url: getfrom}).success(function(data,status){
		$scope.stats_cache [req_name] = data;
	    }).error(function(status){
		    $scope.stats_cache [req_name] = "Not found";
		    console.log(getfrom,' --> error');
		});
    };

    $scope.register = function(prepid){
	    $http({method:'GET', url:'restapi/'+$scope.dbName+'/register/'+prepid}).success(function(data,status){
        $scope.parse_one_only(data,status);
	    }).error(function(status){
		    $scope.set_fail(status);
		  });
    };

    $scope.inspect = function(prepid){
      $http({method:'GET', url:'restapi/'+$scope.dbName+'/inspect/'+prepid}).success(function(data,status){
        $scope.parse_one_only(data,status);
	    }).error(function(status){
		    $scope.set_fail(status);
		  });
    };

    $scope.loadStats = function(){	
      for (i=0;i<$scope.result.length;i++){
        if ($scope.selected_prepids.indexOf( $scope.result[i].prepid) != -1){
          for (i_r=0;i_r!=$scope.result[i].reqmgr_name.length;i_r++){
            $scope.load_dataset_list($scope.result[i].reqmgr_name[i_r].name);
          }
        }
      }
    };

    $scope.select_all_well = function(){
      $scope.selectedCount = true;
      var selectedCount = 0
      _.each($scope.requests_defaults, function(elem){
        if (elem.select){
          selectedCount +=1;
        }
        elem.select = true;
      });
      if (selectedCount == _.size($scope.requests_defaults)){
      _.each($scope.requests_defaults, function(elem){
        elem.select = false;
      });
      $scope.requests_defaults[0].select = true; //set prepid to be enabled by default
      $scope.requests_defaults[1].select = true; // set actions to be enabled
      $scope.requests_defaults[2].select = true; // set actions to be enabled
      $scope.requests_defaults[3].select = true; // set actions to be enabled
      $scope.requests_defaults[4].select = true; // set actions to be enabled
      $scope.requests_defaults[5].select = true; // set actions to be enabled
      $scope.requests_defaults[6].select = true; // set actions to be enabled
      $scope.requests_defaults[7].select = true; // set actions to be enabled
      $scope.selectedCount = false;
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
      var sort = $scope.sort;
      if (sort.column == column) {
        sort.descending = !sort.descending;
      }else{
        sort.column = column;
        sort.descending = false;
      }
    };

  $scope.showing_well = function(){
    if ($scope.show_well){
      $scope.show_well = false;
    }
    else{
      $scope.show_well = true;
    }
   };

  $scope.parseColumns = function(){
    if ($scope.result.length != 0){
    columns = _.keys($scope.result[0]);
    rejected = _.reject(columns, function(v){return v[0] == "_";}); //check if charat[0] is _ which is couchDB value to not be shown
    $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
    _.each(rejected, function(v){
      add = true;
      _.each($scope.requests_defaults, function(column){
        if (column.db_name == v){
          add = false;
        }
      });
      if (add){
        $scope.requests_defaults.push({text:v[0].toUpperCase()+v.substring(1).replace(/\_/g,' '), select:false, db_name:v});
      }
    });
    var shown = "";
    if ($.cookie($scope.dbName+"shown") !== undefined){
      shown = $.cookie($scope.dbName+"shown");
    }
    if ($location.search()["shown"] !== undefined){
      shown = $location.search()["shown"];
    }
    if (shown != ""){
      $location.search("shown", shown);
      binary_shown = parseInt(shown).toString(2).split('').reverse().join(''); //make a binary string interpretation of shown number
      _.each($scope.requests_defaults, function(column){
        column_index = $scope.requests_defaults.indexOf(column);
        binary_bit = binary_shown.charAt(column_index);
        if (binary_bit!= ""){ //if not empty -> we have more columns than binary number length
          if (binary_bit == 1){
            column.select = true;
          }else{
            column.select = false;
          }
        }else{ //if the binary index isnt available -> this means that column "by default" was not selected
          column.select = false;
        }
      });
    }
  }
  }
  $scope.getData = function(){
    if($scope.file_was_uploaded)
   {
     $scope.upload($scope.uploaded_file);
   }
    else if($location.search()['range']!=undefined)
    {
        var ranges = $location.search()['range'].split(",");
        $scope.upload({contents: ranges[0] + " -> " + ranges[1]});
        $scope.file_was_uploaded = false
    }
    else if($location.url().indexOf("*")!=-1)
    {
      $scope.superSearch();
    }
   else
   {
    var query = ""
    _.each($location.search(), function(value,key){
      if (key!= 'shown'){
        query += "&"+key+"="+value;
      }
    });
    $scope.got_results = false; //to display/hide the 'found n results' while reloading
    var promise = $http.get("search/?"+ "db_name="+$scope.dbName+query);
    promise.then(function(data){
      $scope.result = data.data.results;
      $scope.got_results = true;
      if ($scope.result === undefined ){
        alert('The following url-search key(s) is/are not valid : '+_.keys(data.data));
        return; //stop doing anything if results are undefined
      }
      $scope.parseColumns();
    },function(){
      alert("Error getting information");
    });
   }
  };

  $scope.$watch('list_page', function(){
    $scope.getData();
    $scope.selected_prepids = [];
  });

  $scope.calculate_shown = function(){ //on chage of column selection -> recalculate the shown number
    var bin_string = ""; //reconstruct from begining
    _.each($scope.requests_defaults, function(column){ //iterate all columns
      if(column.select){
        bin_string ="1"+bin_string; //if selected add 1 to binary interpretation
      }else{
        bin_string ="0"+bin_string;
      }
    });
    $location.search("shown",parseInt(bin_string,2)); //put into url the interger of binary interpretation
  };

  $scope.previous_page = function(current_page){
    if (current_page >-1){
      $location.search("page", current_page-1);
      $scope.list_page = current_page-1;
    }
  };

  $scope.next_page = function(current_page){
    if ($scope.result.length !=0){
      $location.search("page", current_page+1);
      $scope.list_page = current_page+1;
    }
  };
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
      $scope.action_status[data[i]['prepid']] = data[i]['results'];
      if ($scope.parse_one ( data[i] )){
		    to_reload=false;
      }
    }
    if (to_reload == true){
      $scope.set_success(status);
    }else{
      $scope.set_fail(status);
    }
  };

  $scope.next_approval = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/approve/'+$scope.selected_prepids.join()}).success(function(data,status){
      $scope.parse_report(data,status);
    }).error(function(data,status){
	    $scope.set_fail(status);
    });
  };

  $scope.previous_approval = function(){
    $http({method:'GET', url:'restapi/'+$scope.dbName+'/reset/'+$scope.selected_prepids.join()}).success(function(data,status){
	    $scope.parse_report(data,status);
    }).error(function(data,status){
      $scope.set_fail(status);
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
        $scope.injectModalData = data.data;
        $scope.successfullSubmits = _.filter($scope.injectModalData, function(element){
          return element["results"] == true;
        });
        $scope.openModal();
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

  /*Is Sure modal actions*/
  $scope.open_isSureModal = function(action, prepid){
    $scope.isSure_Modal = true;
    $scope.toggle_prepid = prepid;
    $scope.modal_action = action;
  };

  $scope.closeisSureModal = function(){
    $scope.isSure_Modal = false;
  };

  $scope.sureTotoggle = function(){
    $scope.isSure_Modal = false;
    switch ($scope.modal_action){
      case "toggle":
        $scope.next_status($scope.toggle_prepid);
        break;
      case "approve":
        $scope.single_step('approve',$scope.toggle_prepid);
        break;
      case "reset":
        $scope.single_step('reset',$scope.toggle_prepid);
        break;
      case "delete":
        $scope.delete_object('requests', $scope.toggle_prepid);
        break;
      case "clone":
        $scope.clone($scope.toggle_prepid);
        break;
      default:
        // alert to announce that uknown action is asked???
        break;
    }
  };

  /* Multiple selection modal actions*/
    $scope.submissionModal = false;
  $scope.openModal = function (){
    $scope.submissionModal = true;
  };

  $scope.closeModal = function () {
    $scope.submissionModal = false;
  };

  $scope.openInjectStatus = function(){
    var prepids = [];
    _.each($scope.successfullSubmits, function(element){
      prepids.push(element["prepid"]);
    });
    $window.open("injection_status?prepid="+prepids.join());
    $scope.submissionModal = false;
  };

  /* Notify modal actions */
  $scope.notifyUsers = function(prepid){
    $scope.notify_Modal = true;
    $scope.notify_prepid = prepid;
  };

  $scope.closeNotifyModal = function(){
    $scope.notify_Modal = false;
  };

  $scope.Notify = function(){
    if ($scope.selected_prepids.length != 0){
      $scope.notify_prepid = $scope.selected_prepids;
    }else{
      $scope.notify_prepid = [$scope.notify_prepid];
    }
    $scope.loadNotify = true;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/notify/', data:JSON.stringify({prepids: $scope.notify_prepid, message: $scope.notify_text})}).success(function(data,status){
      $scope.loadNotify = false;

      $scope.update["success"] = true;
      $scope.update["fail"] = false;
      $scope.update["status_code"] = status;
      $scope.update["message"] = data[0]["message"];

      $scope.notify_prepid = "";
      $scope.notify_Modal = false;
      $scope.notify_text = "";
      $scope.notify_prepid = [];
    }).error(function(data,status){
      $scope.loadNotify = false;
      $scope.set_fail(status);
    });
  };

  $scope.cloneModal = false;
  $scope.closeCloneModal = function()
  {
    $scope.clonableID = "";
    $scope.clonePWG = "";
    $scope.cloneCampaign = "";
    $scope.cloneModal = false;
  }
  $scope.openCloneModal = function(id, pwg, campaign)
  {
    if(!$scope.all_pwgs){
      var promise = $http.get("restapi/users/get_pwg")
      promise.then(function(data){
        $scope.all_pwgs = data.data.results;
      });
    }
    if(!$scope.allCampaigns)
    {
      var promise = $http.get("restapi/campaigns/listall"); //get list of all campaigns for flow editing
      promise.then(function(data){
        $scope.allCampaigns = data.data.results;
      });
    }
    $scope.clonePWG = pwg;
    $scope.cloneCampaign = campaign;
    $scope.clonableID = id;
    $scope.cloneModal = true;
  }
  $scope.clonePrepid = function()
  {
    var tmpClone = {};
    _.each($scope.result, function(elem)
    {
      if(elem.prepid == $scope.clonableID)
      {
        tmpClone = _.clone(elem);
      }
    });
    tmpClone["member_of_campaign"] = $scope.cloneCampaign;
    tmpClone["pwg"] = $scope.clonePWG;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/clone/', data:tmpClone}).success(function(data,status){
      $scope.cloneModal = false;

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
      $scope.cloneModal = false;

      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
      $scope.update["message"] = data;
    });
  }
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

  $scope.superSearch = function(){
    var search_data={};
    _.each($location.search(),function(elem,key){
      if (key != "page" && key != "shown" )
      {
        search_data[key] = elem;
      }
    });
      /*submit method*/
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/search', data: search_data}).success(function(data,status){
      $scope.result = data.results;
      $scope.got_results = true;
      $scope.parseColumns();
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    }); 
   };

  $scope.upload = function(file){
    $scope.file_was_uploaded = true;
    $scope.uploaded_file = file;
    /*Upload a file to server*/
    $scope.got_results = false;
    $http({method:'PUT', url:'restapi/'+$scope.dbName+'/listwithfile', data: file}).success(function(data,status){
      $scope.result = data.results;
      $scope.got_results = true;
      $scope.parseColumns();
    }).error(function(status){
      $scope.update["success"] = false;
      $scope.update["fail"] = true;
      $scope.update["status_code"] = status;
    });
  };

  $scope.saveCookie = function(){
    var cookie_name = $scope.dbName+"shown";
    if($location.search()["shown"]){
      $.cookie(cookie_name, $location.search()["shown"], { expires: 7000 })
    }
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
                  console.log(ctrl.$viewValue);
                  scope.approval = ctrl.$viewValue;
                }
            console.log(scope.display_table);
            };
        }
    }
});
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
//     '          <th style="padding: 0px;">Message</th>'+
    '          <th style="padding: 0px;">Date</th>'+
    '          <th style="padding: 0px;">User</th>'+
    '          <th style="padding: 0px;">Step</th>'+ //is it needed?
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
    '          <td style="padding: 0px;">{{elem.step}}</td>'+ //is it needed?
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
testApp.directive("sequenceDisplay", function($http){
  return {
    require: 'ngModel',
    template:
    '<div>'+
    '  <div ng-hide="show_sequence">'+
    '    <a rel="tooltip" title="Show" ng-click="getCmsDriver();show_sequence=true;">'+
    '     <i class="icon-eye-open"></i>'+
    '    </a>'+
	//    '    <input type="button" value="Show" ng-click="getCmsDriver();show_sequence=true;">'+
    '  </div>'+
    '  <div ng-show="show_sequence">'+
	//    '    <input type="button" value="Hide" ng-click="show_sequence=false;">'+
    '    <a rel="tooltip" title="Hide" ng-click="show_sequence=false;">'+
    '     <i class="icon-remove"></i>'+
    '    </a>'+
    '    <a rel="tooltip" title="Reset" ng-click="resetCmsDriver();"ng-hide="role(1);">'+
    '     <i class="icon-repeat"></i>'+
    '    </a>'+
    '    <a rel="tooltip" title="Cast" ng-click="castCmsDriver()" ng-hide="role(1);">'+
    '     <i class="icon-share"></i>'+
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
//         scope.sequencePrepId = scope.dbName;
      };
      scope.genericCmsDriver = function(extra){
        if (scope.driver ===undefined || extra!=""){
          var promise = $http.get("restapi/"+scope.dbName+"/get_cmsDrivers/"+scope.sequencePrepId+extra);
          promise.then(function(data){
            scope.driver = data.data.results;
          }, function(data){
             alert("Error: ", data.status);
        });
	}
      };
      scope.getCmsDriver = function(){	  scope.genericCmsDriver("");      };
      scope.resetCmsDriver = function(){	  scope.genericCmsDriver("/-1");      };
      scope.castCmsDriver = function(){	  scope.genericCmsDriver("/1");      };
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
    // '          <dd>{{$index}}</dd>'+
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
    // '          <dd>{{$index}}</dd>'+
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
    '    <span class="control-group" ng-repeat="(key,value) in searchable">'+
    '      <label style="width:140px;">{{key}}</label>'+
    '      <select ng-model="listfields[key]" ng-show="showOption[key]" style="width: 164px;">'+
    '        <option ng-repeat="elem in value">{{elem}}</option>'+
    '      </select>'+
    '      <input class="input-medium" type="text" ng-hide="showOption[key]" ng-model="listfields[key]" typeahead="state for state in searchable[key] | filter: $viewValue | limitTo: 10">'+
    '      <a class="btn btn-mini" ng-href="#" ng-click="toggleSelectOption(key)"><i class="icon-arrow-down"></i></a>'+
    '    </span>'+
    '  </form>'+
    '  <button type="button" class="btn btn-small" ng-click="getUrl();">Search</button>'+
    '  <button type="button" class="btn btn-small" ng-click="getSearch();">Reload menus</button>'+
    '  <img ng-show="loadingData" ng-src="https://twiki.cern.ch/twiki/pub/TWiki/TWikiDocGraphics/processing-bg.gif"/>'+
    '   <a ng-href="https://twiki.cern.ch/twiki/bin/view/CMS/PdmVMcM#Browsing" rel="tooltip" title="Help on navigation"><i class="icon-question-sign"></i></a>'+
    '  <button type="button" class="btn btn-small" ng-click="goToNextPrepid(-1);" ng-disabled="is_prepid_in_url == undefined">Previous</button>,'+
    '  <button type="button" class="btn btn-small" ng-click="goToNextPrepid(1);" ng-disabled="is_prepid_in_url == undefined">Next</button> request'+
    '</div>'
    ,
    link: function(scope, element, attr)
    {
      scope.listfields = {};
      scope.showUrl = false;
      scope.showOption = {};
      scope.is_prepid_in_url = $location.search()["prepid"];
      scope.getSearch = function(){
        scope.listfields = {};
        scope.showUrl = false;
        var promise = $http.get("restapi/"+scope.dbName+"/searchable/do");
        scope.loadingData = true;
        promise.then(function(data){
          scope.loadingData = false;
          scope.searchable = data.data;
        }, function(data){
          scope.loadingData = false;
          alert("Error getting searchable fields: "+data.status);
        });
      };
      scope.zeroPad = function(num, places){
        var zero = places - num.toString().length + 1;
        return Array(+(zero > 0 && zero)).join("0") + num;
      }
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
      scope.toggleSelectOption = function(option){
        if (scope.showOption[option])
        {
          scope.showOption[option] = false;
        }else
        {
          scope.showOption[option] = true;
        }
      };
      scope.$watch('tabsettings.navigation.active', function(){
        if (scope.tabsettings.navigation.active)
        {
          if (!scope.searchable) //get searchable fields only if undefined -> save time for 2nd time open of pane
          {
            var promise = $http.get("restapi/"+scope.dbName+"/searchable");
            scope.loadingData = true;
            promise.then(function(data){
              scope.loadingData = false;
              scope.searchable = data.data;
            }, function(data){
              scope.loadingData = false;
              alert("Error getting searchable fields: "+data.status);
            });
          }
        }
      },true);
    }
  }
});
testApp.directive("reqmgrName", function($http){
  return {
    replace: true,
    require: 'ngModel',
    restrict: 'E',
    template:
    '<div>'+
    '  <ul style="margin-bottom: 0px;">'+
    '    <li ng-repeat="rqmngr in data[value.db_name]">'+
    '      <a ng-href="batches?contains={{rqmngr.name}}" rel="tooltip" title="View batches containing {{rqmngr.name}}" target="_self"><i class="icon-tags"></i></a>'+
    '      <a ng-show="isDevMachine();" ng-href="https://cmsweb-testbed.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>'+
    '      <a ng-show="!isDevMachine();" ng-href="https://cmsweb.cern.ch/reqmgr/view/details/{{rqmngr[\'name\']}}" rel="tooltip" title="Details" target="_self">details</a>,'+
    '      <a ng-hide="stats_cache[rqmngr[\'name\']]" ng-href="http://cms-pdmv.cern.ch/stats/?RN={{rqmngr[\'name\']}}" rel="tooltip" title="Stats" target="_self"> stats</a>'+
    '      <a ng-click="load_dataset_list(rqmngr[\'name\']);" ng-hide="stats_cache[rqmngr[\'name\']]" rel="tooltip" title="Load statistics"> <i class="icon-eye-open"></i></a>'+
    '      <b><font color="red" ng-show="stats_cache[rqmngr[\'name\']] && !underscore.isObject(stats_cache[rqmngr[\'name\']])"> Stats Not Found</font></b>'+
    '      <span ng-show="underscore.isObject(stats_cache[rqmngr[\'name\']])">'+
    '        <a ng-href="http://cms-pdmv.cern.ch/stats/?RN={{rqmngr[\'name\']}}" target="_self"> {{numberWithCommas(stats_cache[rqmngr["name"]].pdmv_evts_in_DAS)}} events</a>,'+
    '        <a ng-hide="role(3);" ng-href="https://cmsweb.cern.ch/couchdb/workloadsummary/_design/WorkloadSummary/_show/histogramByWorkflow/{{rqmngr[\'name\']}}" rel="tooltip" title="Perf" target="_self">perf</a>,'+
    '        <a ng-hide="role(3);" ng-href="https://cmsweb.cern.ch/reqmgr/reqMgr/outputDatasetsByRequestName/{{rqmngr[\'name\']}}" rel="tooltip" title="DS" target="_self">output</a>,'+
    '        {{stats_cache[rqmngr["name"]].pdmv_status_from_reqmngr}}, {{stats_cache[rqmngr["name"]].pdmv_status_in_DAS}},'+
    '        <span ng-repeat="c_site in stats_cache[rqmngr[\'name\']].pdmv_custodial_sites">'+
    '          @{{c_site}},'+
    '        </span>'+
    '        <span ng-show="stats_cache[rqmngr[\'name\']].pdmv_running_sites.length">'+
    '          Running at : {{stats_cache[rqmngr["name"]].pdmv_running_sites.join()}},'+
    '        </span>'+
    '        Last update on {{stats_cache[rqmngr["name"]].pdmv_monitor_time}}'+
    '        </br>'+
    '        <a ng-href="https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/{{rqmngr[\'name\']}}.gif"><img width={{image_width}} ng-src="https://cms-pdmv.web.cern.ch/cms-pdmv/stats/growth/{{rqmngr[\'name\']}}.gif" ng-mouseover="image_width = 700" ng-mouseleave="image_width = 150"/></a>'+
    '        <ul style="margin-bottom: 0px;" ng-show="true;">'+
    '          <li ng-repeat="DS in stats_cache[rqmngr[\'name\']].pdmv_dataset_list">'+
    '            <span ng-switch on="stats_cache[rqmngr[\'name\']].pdmv_status_in_DAS == \'VALID\'">'+
    '              <a ng-switch-when="true" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{DS}}" rel="tooltip" title="Link to {{DS}} in DAS" target="_self">{{DS}}</a>'+
    '              <a ng-switch-when="false" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{DS}}" rel="tooltip" title="Link to {{DS}} in DAS" target="_self"><del>{{DS}}</del></a>'+
    '            </span>'+
    '          </li>'+
    '          <li ng-show="data[\'status\']==\'done\' && rqmngr.content.pdmv_dataset_name && !underscore.isObject(stats_cache[rqmngr[\'name\']])">'+
    '            <span ng-switch on="stats_cache[rqmngr[\'name\']].pdmv_status_in_DAS == \'VALID\'">'+
    '              <a ng-switch-when="true" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{rqmngr.content.pdmv_dataset_name }}" rel="tooltip" title="Link to {{rqmngr.content.pdmv_dataset_name}} in DAS" target="_self">{{ rqmngr.content.pdmv_dataset_name}}</a>'+
    '              <a ng-switch-when="false" ng-href="https://cmsweb.cern.ch/das/request?instance=cms_dbs_prod_global&input={{rqmngr.content.pdmv_dataset_name }}" rel="tooltip" title="Link to {{rqmngr.content.pdmv_dataset_name}} in DAS" target="_self"><del>{{ rqmngr.content.pdmv_dataset_name}}</del></a>'+
    '            </span>'+
    '          </li>'+
    '        </ul>'+
    '        <a ng-click="full_details[rqmngr[\'name\']]=true;" ng-hide="role(3) || full_details[rqmngr[\'name\']]" rel="tooltip" title="Load Full details"> <i class="icon-eye-open"></i></a>'+
    '      </span>'+
    '      <div ng-show="underscore.isObject(stats_cache[rqmngr[\'name\']]) && full_details[rqmngr[\'name\']]">'+
    '        <a ng-click="full_details[rqmngr[\'name\']]=false;" rel="tooltip" title="Close details"><i class="icon-eye-close"></i></a>'+
    '        <pre>{{stats_cache[rqmngr["name"]]|json}}</pre>'+
    '      </div>'+
    '    </li>'+
    '  </ul>'+
    '</div>',
    link: function(scope, element, attr, ctrl)
    {
      ctrl.$render = function(){
        scope.rqmngr_data = ctrl.$viewValue;
      };
    }
  }
});
