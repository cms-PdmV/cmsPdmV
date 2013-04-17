function select_chain(action_id, chain_id) {

	$("#action_dialog").dialog({
		closeOnEscape: true, 
		autoOpen: true,
		title: "Define Chain",
		dialogClass: 'dialog-no-close',
		resizable: false,
		show: {
			effect: 'drop',
			direction: 'up'
		},
		hide: {
			effect: 'drop',
			direction: 'down',
		},
		modal: true ,
		open: function() {
		    $.ajax({
		        type: 'GET',
		        // get the action under examination
		        url: '/restapi/actions/get/'+action_id+'/',
		        async: false,
		        success:function(data) {
		            var json = $.parseJSON(data);
		            if (json) {
		                if (!json.results.chains)
		                    alert(json["results"]);
		                
		                // set the correct value for the correct value
		                $("#action_dialog_block_number").val(json["results"]["chains"][chain_id]);
		            }
		        }
            });
            
            //get the threshold from the chained_request or the chained_campaign if the former does not exist
            ajax_search('chained_requests', 'root_request=='+action_id, 0, function(data) { // ajax search
                                var json = data;
                                var flag = false;
                                if (json) { // if json
                                    $.each(json, function() {
                                        if (this.prepid.indexOf(chain_id) > -1) {
                                            flag = true;
                                            if(this.request_parameters.threshold)
                                                $("#action_dialog_threshold").val(this.request_parameters.threshold);
                                            if(this.request_parameters.staged)
                                                $("#action_dialog_staged").val(this.request_parameters.staged);
                                        }         
                                    }); 
                                }
                                else {
                                    alert('Error: Could not contact the database');
                                } 
                                
                                if (flag==false) {
                                    $.ajax({
                                        type: 'GET',
                                        url: '/restapi/chained_campaigns/get/'+chain_id+'/',
                                        async: false,
                                        success: function(data) {
                                            var json = $.parseJSON(data);
                                            if (json) {
                                                if (!json.results._id)
                                                    alert(json.results);
                                                
                                                if (json.results.action_parameters) {
                                                    if (json.results.action_parameters[action_id]) {
                                                        if (json.results.action_parameters[action_id].threshold)
                                                            $("#action_dialog_threshold").val(json.results.action_parameters[action_id].threshold);
                                                        if (json.results.action_parameters[action_id].staged)
                                                            $("#action_dialog_staged").val(json.results.action_parameters[action_id].staged);
                                                    }
                                                }
                                            }
                                        }
                                    });
                                }   
            });
		},
		buttons: [{ 
				text: "close", 
				click: function() {
				    // clear all values in the dialog
				    $("#action_dialog > input").each(function() {
				        $(this).val("");
    				    });				
    				
					$("#action_dialog").dialog('close');
				}
			},{
				text: "save",
				click: function () {
    				    // if block number is null then return
				    if ($("#action_dialog_block_number").val()) {
				
    				    // submit blocknumber through rest
	    			    $.ajax({
                            type: 'GET',
                            url: '/restapi/actions/select/'+action_id+'/'+chain_id+'/'+$("#action_dialog_block_number").val()+'/',
                            async: false,
                            success:function(data){
                                var json = $.parseJSON(data);
                                if(json) {
                                        if (json["results"] != true)
                                            alert(json["results"]);
                                }
                                        /*else
                                            alert('Object was updated successfully.');*/
                                else
                                    alert('Could not update database.');
    
                            },
                            error:function(xhr, error, data){
                                alert(data + '. Could not update object.');
                            }
                        });
                    }
                    
                    // update threshold and staged numbers
                    if ($("#action_dialog_threshold").val() || $("#action_dialog_staged").val()) { // if thres
                            // search for the cross chained_request
                        ajax_search('chained_requests', 'root_request=='+action_id, 0, function(data) { // ajax search
                                var json = data;
                                var flag = false;
                                if (json) { // if json
                                    $.each(json, function() {
                                        if (this.prepid.indexOf(chain_id) > -1) {
                                            flag = true;
                                            // update relevant fields
                                            if ($("#action_dialog_threshold").val())
                                                this.request_parameters["threshold"] = $("#action_dialog_threshold").val();
                                            if($("#action_dialog_staged").val())
                                                this.request_parameters["staged"] = $("#action_dialog_staged").val();
                                            
                                            // avoid useless db transaction
                                            if (!$("#action_dialog_threshold").val() && !$("#action_dialog_staged").val())
                                                redirect(window.location);
                                            
                                            // save to db
                                            $.ajax({
                                                type: 'PUT',
                                                url: '/restapi/chained_requests/update/',
                                                data: $.stringify(this),
            		                            contentType: "application/json; charset=utf-8",
            		                            async: false,
                                                success:function(data){
                                                    var json = $.parseJSON(data);
                                                    if (json["results"]) {
                                                        if (json["results"] != true)
                                                            alert(json["results"]);
                                                    }
                                                    else
                                                        alert('Could not update data to database.');
    
                                                },
                                                error:function(xhr, error, data){
                                                    alert(data + '. Could not update object.');
                                                }        		                            
                                            });
                                       }     
                                    });
                                } // end if json
                                if (!flag) {
                                    ajax_search('chained_campaigns', 'prepid=='+chain_id, 0, function(data) {
                                            
                                        if (data) {
                                            json = data[0];
                                            ap = {};
                                            if ($("#action_dialog_threshold").val())
                                                json.action_parameters[action_id] = {"threshold" : $("#action_dialog_threshold").val()};
                                            else if ($("#action_dialog_staged").val())
                                                json.action_parameters[action_id] = {"staged" : $("#action_dialog_staged").val()};
                                            else
                                                redirect(window.location);
                                            
                                            //save to db
                                            $.ajax({
                                                type: 'PUT',
                                                url: '/restapi/chained_campaigns/update/',
                                                data: $.stringify(json),
                                                contentType: "application/json; charset=utf-8",
                                                async: false,
                                                success:function(data2){
                                                    var json2 = $.parseJSON(data2);

                                                    if (json2) {
                                                        if (json2["results"] != true)
                                                            alert(json2["results"]);
                                                        /*else
                                                            alert('Object was updated successfully.');*/
                                                    }
                                                    else
                                                        alert('Could not update data to database.');
    
                                                },
                                                error:function(xhr, error, data){
                                                    alert(data + '. Could not update object.');
                                                }
                                            });
                                        }
                                        else
                                            alert('Chained Campaign was not found.');
                                    });
                                }
                        }); // end ajax_search
                    } // end if thres
                    redirect(window.location);
            } // function end

            }]
        	});
}

function generate_requests(id) {
    var urlStrl
    if (id.indexOf("chain_") != -1) {
        urlStr = '/restapi/chained_campaigns/generate_chained_requests/'+id;
    }
    else
        urlStr = '/restapi/actions/generate_chained_requests/'+id;
        
        
    // submit it to the db through rest
    $.ajax({
        type: 'GET',
        url: urlStr,
        success:function(data){
        var json = $.parseJSON(data);
        if (json) {
            if (json["results"] != true)
                alert(json["results"]);
        }
        else
            alert('Could not update data to database.');

        //refresh
        redirect(window.location);
        },
        error:function(xhr, error, data){
            alert(data + '. Could not update object.');
        }
    });
}

// generate all possible chained_requests
function generate_all_requests() {
    // submit it to the db through rest
    $.ajax({
        type: 'GET',
        url: "/restapi/actions/generate_all_chained_requests/",
        success:function(data){
        var json = $.parseJSON(data);
        if (json) {
            if (json["results"] != true)
                alert(json["results"]);
        }
        else
            alert('Could not update data to database.');

        //refresh
        redirect(window.location);
        },
        error:function(xhr, error, data){
            alert(data + '. Could not update object.');
        }
    });    
}

// requests that all actions will calculate their actions
function refresh_all_chains() {
        // contact REST
        $.ajax({
                type: 'GET',
                url: '/restapi/actions/detect_chains/',
                success:function(data){
                        var json = $.parseJSON(data);
                        if (json) {
                                if (json["results"] != true)
                                    alert(json["results"]);
                        }
                        else
                                alert('Could not update data to database.');

                        //refresh
                        redirect(window.location);
                },
                error:function(xhr, error, data){
                        alert(data + '. Could not update object.');
                }
        });
}
