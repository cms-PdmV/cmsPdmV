// declare public prepdb variables
$.prep_query_vars = {
	db: "campaigns",
	query: "",
	page: 0,
	last: false
}

function ajax_search(db, query, page, success_handler, error_handler) {
	$.ajax({
                type: 'GET',
                url: '/search/?db_name='+db+'&query="'+query+'"&page='+page,
		async: false,
                success:function(data) {
			success_handler($.parseJSON(data)["results"]);
		},
                error:function(xhr, error, data) {
			 error_handler(data);
		}
        });

}

function search() {
	// retrieve the select values
	$.prep_query_vars.db = $("#entity_menu").find(":selected").text();
	var param_list = $("#forms_search select[id^='params_']").get();
	var ops_list = $("#forms_search select[id^='ops_']").get();
	var input_list = $("#forms_search input[id^='input_']").get();

	// check to see if all lists have the same length
	if (param_list.length != ops_list.length || param_list.length != input_list.length) {
		alert('Error 500: Could not execute query.');
		return;
	}	
	
	$.prep_query_vars.query = "";
	$.each(param_list, function(index, value) {
		$.prep_query_vars.query += $("#params_"+index).find(":selected").text();
		$.prep_query_vars.query += $("#ops_"+index).find(":selected").text();
		$.prep_query_vars.query += $("#input_"+index).val() + ",";
	});
	
	// trim the last ','
	$.prep_query_vars.query = $.prep_query_vars.query.replace(/.$/g, '');

	// redirect to the results page
	redirect("/results/?db_name=\""+$.prep_query_vars.db+"\"&query=\""+$.prep_query_vars.query+"\"&page="+$.prep_query_vars.page);
}

// add a new search form div
function add_search_form(index) {
	if ($("#cont_"+index).size() > 0 || index > 10 )
		return;
	jQuery('<div id="cont_'+index+'"></div>').appendTo("#forms_search_form_container");
	$("#cont_"+index).css("margin-top", "1px");

	// parameter names
	jQuery('<select id="params_'+index+'" class="ui-widget-content"></select>').appendTo("#cont_"+index);

	// operators
	jQuery('<select id="ops_'+index+'" class= "ui-widget-content"></select>').appendTo("#cont_"+index);
	$("#ops_"+index).css("margin-left", "5px");

	// populate dropdowns
	var parameter_names = ["prepid", "type", "member_of_campaign", "priority"];
	var ops = ["<", "<=", "==", "~=", ">=", ">"];

	$.each(parameter_names, function(i,val) {
		jQuery('<option>'+val+'</option>').appendTo("#params_"+index);			
		});
	
	$.each(ops, function(i, val) {
		jQuery('<option>'+val+'</option>').appendTo("#ops_"+index);
		});

	// create objects
	jQuery("<input id='input_"+index+"' type='input' value='' class='ui-widget-content'>").appendTo("#cont_"+index);
	$("#input_"+index).css("margin-left", "5px");

	// update form builder
	$("#add_form_button").attr("href", "javascript:add_search_form("+(index+1)+");");
	$("#remove_form_button").attr("href", "javascript:remove_search_form("+index+");");
	//$("#add_form_button").bind("click", function() {add_search_form(index+1)});
	//$("#remove_form_button").bind("click", function() {remove_search_form(index-1));
}

function search_form() {
	$("#search_placeholder").toggle('slow');
}

function remove_search_form(index) {
	if (index < 1)
		return;
	$("#cont_"+index).empty().remove();
	$("#add_form_button").attr("href", "javascript:add_search_form("+index+");");
	$("#remove_form_button").attr("href", "javascript:remove_search_form("+(index-1)+");");
}

function search_im(db_name, query, page) {
	$(window).attr("location","/results/?db_name="+db_name+"&query=\""+query+"\"&page="+page);
}

// put a loading gif at the center of a div
function loading_gif(parid) {
	// load the image
	$('#'+parid).html('<div class="loading"><img id="loader_gif" src="/icons/loading.gif" alt="Loading..." /></div>');
	$('#'+parid).css( 'text-align', 'center'); // align horizontally

	// calculate parent height and align vertically 
	var parent_height = $('#'+parid).height();
	var image_height = $('#loader_gif').height();
	var top_margin = (parent_height - image_height)/2;
	$('#loader_gif').css( 'margin-top' , top_margin);
}
function get_results(id) {
	$.prep_query_vars.db = $("#db_input").val();
	$.prep_query_vars.query = $("#query_input").val();
	$.ajax({
		type: 'GET',
		url: '/search/?db_name='+$.prep_query_vars.db+'&query="'+$.prep_query_vars.query+'"&page='+$.prep_query_vars.page,
		//data: { postVar1: 'theValue1', postVar2: 'theValue2' },
		beforeSend:function(){
			// this is where we append a loading image
			if ($.prep_query_vars.last)
				return;
			$('#'+id).empty();
			loading_gif(id);
			},
		success:function(data){
		    // successful request; do something with the data
			var json = $.parseJSON(data);
			$('#'+id).empty();
			if (json["results"] == "") {
				$.prep_query_vars.last = true;
				$.prep_query_vars.page = $.prep_query_vars.page - 1;
				return;
			}
			show_results(id, json["results"]);
			$.prep_query_vars.last = false;
			},
		error:function(data){
		    // failed request; give feedback to user
		    $('#'+id).html('<p class="error"><strong>Oops!</strong> Try that again in a few moments.</p>');
			}
		});
}

function show_results(id, data) {
	if (!data || data.length == 0) 
		return;

	build_table(id);
	build_header(id);
	$.each(data, function(index, value) {
		build_rows(id, index, value);
	});	
	addHover("a");
}

function build_table(id) {
	$('<table id="object_list_table" class="ui-widget"><thead id="object_list_thead" class="ui-widget-header"></thead><tbody id="object_list_tbody" class="ui-widget-content"></tbody></table>').appendTo("#"+id);
}

function build_header(id) {
	if ($.prep_query_vars.db == "campaigns") 
		$("<tr><th>Prepid</th><th>Actions</th><th>Completed Events / Total Events</th><th>Energy</th><th>Type</th></tr>").appendTo("#"+id+"_thead");
	else if ($.prep_query_vars.db == "requests") 
		$("<tr><th>Prepid</th><th>Actions</th><th>Completed Events / Total Events</th><th>Priority</th><th>Type</th></tr>").appendTo("#"+id+"_thead");
	else if ($.prep_query_vars.db == "chained_requests")
		$("<tr><th>Prepid</th><th>Actions</th><th>Chain</th></tr>").appendTo("#"+id+"_thead");
	else if ($.prep_query_vars.db == "chained_campaigns")
		$("<tr><th>Prepid</th><th>Actions</th><th>Chain</th><th>Energy</th></tr>").appendTo("#"+id+"_thead");
	else if ($.prep_query_vars.db == "flows")
		$("<tr><th>Prepid</th><th>Actions</th><th>Allowed Campaigns</th><th>Next Campaign</th></tr>").appendTo("#"+id+"_thead");	    
	else
		$("#"+id).empty();
}

// build the rows of the table that shows the results of the search
function build_rows(id, index, data) {
	if ($.prep_query_vars.db == "campaigns") {
		$("<tr><td>"+data["_id"]+"</td><td>"+build_actions(data["_id"])+"</td><td><div class='prog_container'><div class='progressbar' id='progbar_"+index+"'><div class='prog_text'>"+data["completed_events"]+"/"+data["total_events"]+"</div></div></td><td>"+data["energy"]+"</td><td>"+data["type"]+"</td></tr>").appendTo("#"+id+"_tbody");
		build_progress("progbar_"+index, data["completed_events"], data["total_events"]);
	}	
	else if ($.prep_query_vars.db == "requests") {
		$("<tr><td>"+data["_id"]+"</td><td>"+build_actions(data["_id"])+"</td><td><div class='prog_container'><div class='progressbar' id='progbar_"+index+"'><div class='prog_text'>"+data["completed_events"]+"/"+data["total_events"]+"</div></div></div></td><td>"+data["priority"]+"</td><td>"+data["type"]+"</td></tr>").appendTo("#"+id+"_tbody");
		build_progress("progbar_"+index, data["completed_events"], data["total_events"]);
	}	
	else if ($.prep_query_vars.db == "chained_requests")
		$("<tr><td>"+data["_id"]+"</td><td>"+build_actions(data["_id"])+"</td><td>"+build_chain_links(data["chain"])+"</td></tr>").appendTo("#"+id+"_tbody");
	else if ($.prep_query_vars.db == "chained_campaigns")
		$("<tr><td>"+data["_id"]+"</td><td>"+build_actions(data["_id"])+"</td><td>"+build_chain_links(data["campaigns"])+"</td><td>"+data["energy"]+"</td></tr>").appendTo("#"+id+"_tbody");
	else if ($.prep_query_vars.db == "flows")
	    $("<tr><td>"+data["_id"]+"</td><td>"+build_actions(data["_id"])+"</td><td>"+build_allowed_campaigns(data["allowed_campaigns"])+"</td><td>"+data["next_campaign"]+"</td></tr>").appendTo("#"+id+"_tbody");
	else 
		$("#"+id).empty();
}

// make the body of a list of allowed campaigns (flowdb)
function build_allowed_campaigns(lst) {
	res = "<ul class='chain_links'>";
    $.each(lst, function(i, v) {
        res += "<li><a ui='ui-widget-content' href='javascript:redirect(\"/edit/campaigns/";
        res += this+"/\");'>"+this+"</a></li>";
		if (i < lst.lenght - 1)
			res += ", ";
	});
	res += "</ul>";        
	return res;
}

// make the body of the chain a link
function build_chain_links(lst) {
    if (!lst)
        return "";
	res = "<ul class='chain_links'>";
	$.each(lst, function(i, v) {
		res += "<li><a ui='ui-widget-content' href='javascript:redirect(\"/edit/";
		if ($.prep_query_vars.db == "chained_requests")
			res += "requests/"+this+"/\");'>"+this+"</a></li>";
		else if ($.prep_query_vars.db == "chained_campaigns")
			res += "campaigns/"+this+"/\");'>"+this+"</a></li>";
		if (i < lst.lenght - 1)
			res += ", ";
	});
	res += "</ul>";
	return res;
}

function build_actions(id) {
	if ($.prep_query_vars.db == "campaigns") {
		return "<a title='Edit details' href='javascript:edit_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-wrench'></span></a><a title='Delete campaign' href='javascript:delete_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-close'></span></a><a title='Show requests' href='javascript:search_im(\"requests\", \"member_of_campaign=="+id+"\", 0);' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-folder-open'></span></a><a title='Create new request' href='javascript:create_object(\"requests\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-plus'></span></a>"
	}
	else if ($.prep_query_vars.db == "requests") {
		return "<a title='Edit details' href='javascript:edit_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-wrench'></span></a><a title='Delete request' href='javascript:delete_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-close'></span></a>"
	}
	else if ($.prep_query_vars.db == "chained_requests") {
		return "<a title='Edit details' href='javascript:edit_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-wrench'></span></a><a title='Delete request' href='javascript:delete_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-close'></span></a>"
	}
	else if ($.prep_query_vars.db == "chained_campaigns") {
		return "<a title='Edit details' href='javascript:edit_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-wrench'></span></a><a title='Delete campaign' href='javascript:delete_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-close'></span></a><a title='Show requests' href='javascript:search_im(\"chained_requests\", \"member_of_campaign=="+id+"\", 0);' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-folder-open'></span> </a><a title='Create new request' href='javascript:create_object(\"chained_requests\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-plus'></span></a>"
	}
	else if ($.prep_query_vars.db == "flows") {
        return "<a title='Edit details' href='javascript:edit_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-wrench'></span></a><a title='Delete flow' href='javascript:delete_object(\""+$.prep_query_vars.db+"\",\""+id+"\");' class='iconholder ui-corner-all ui-state-default'><span class='ui-icon ui-icon-close'></span></a>"
	}
}

function build_progress(id, comp, total) {
    c = parseInt(comp);
    t = parseInt(total);
    prog = 0;
    if (t < 0 || c < 0)
        prog = 0;
    else
        prog = Math.floor((c / t)*100);
    if(prog > 100)
        prog = 100;

	// build progressbar widget	
	$("#"+id).progressbar({value: prog});
}

function show_next_page(id) {
	if ($.prep_query_vars.last)
		return;
	$.prep_query_vars.page = $.prep_query_vars.page + 1;
	get_results(id);
}

function show_previous_page(id) {
	if ($.prep_query_vars.page > 0) {
		$.prep_query_vars.page = $.prep_query_vars.page - 1;
		get_results(id);
	}
	return;
}	

function addHover(selector){
	$(selector).hover(
		function() { $(this).addClass('ui-state-hover');},
		function() { $(this).removeClass('ui-state-hover'); }
		);
}
