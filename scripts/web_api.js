// open url in a new tab (or popup )
function new_tab_redirect(url) {
    window.open(url);
}

// open url in the same window
function redirect(url) {
    window.location = url;
}

// redirect to the web app that creates and saves 
// objects in the database
function create_object(db, parid) {
	redirect('/create/'+db+'/'+parid);
}

// redirect to the web app that updates objects
// in the database
function edit_object(db, id) {
	new_tab_redirect('/edit/'+db+'/'+id);
}

// creates a new object in db using the info
// from the /create web application
function save_object(db) {
	// gather all data from the page
	$("#editor tbody").children("tr").each(function() {
		var key = $(this).children("td:first-child").html();
		
		if ($(this).children("td:nth-child(2)").children(":first-child").is("textarea"))
			var val = $(this).children("td:nth-child(2)").children("textarea:first-child").val();
		else if($(this).children("td:nth-child(2)").children(":first-child").is("select"))
			var val = $(this).children("td:nth-child(2)").find(":selected").html();
		if(val)
			jsondata[key] = val;
	});
	
	// submit it to the db through rest
	$.ajax({
		type: 'PUT',
		url: '/restapi/'+db+'/save/',
		data: $.stringify(jsondata),
		contentType: "application/json; charset=utf-8",
                success:function(data){
                        var json = $.parseJSON(data);
                        if (json["results"])
                                alert('Object was saved successfully.');
                        else
                                alert('Could not save data to database.');

                        //refresh
			if (db.indexOf("request") != -1)
				search_im(db, 'member_of_campaign=='+jsondata["member_of_campaign"], 0);
			else
				redirect("/"+db);
                },
                error:function(xhr, error, data){
                        alert( data + '. Could not save object.');
                }
	});		
}

// updates a document in db using the data
// from /edit web application
function update_object(db) {
        // gather all data from the page
        $("#editor tbody").children("tr").each(function() {
                var key = $(this).children("td:first-child").html();
                var val = $(this).children("td:nth-child(2)").children("textarea:first-child").val();
                if(val)
                        jsondata[key] = val;
        });
        
	// submit it to the db through rest
        $.ajax({
                type: 'PUT',
                url: '/restapi/'+db+'/update/',
                data: $.stringify(jsondata),
		contentType: "application/json; charset=utf-8",
                success:function(data){
                        var json = $.parseJSON(data);
                        if (json["results"])
                                alert('Object was updated successfully.');
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

function json_escape(str) {
  return str
    //.replace(/[\\]/g, '\\\\')
    //.replace(/[\"]/g, '\\\"')
    //.replace(/[\/]/g, '\\/')
    //.replace(/[\b]/g, '\\b')
    //.replace(/[\f]/g, '\\f')
    .replace(/[\n]/g, "<br>")
    //.replace(/[\r]/g, "\\r")
    //.replace(/[\t]/g, "\\t");
}


//function commit_changes(db, data);
//function save_object(db, data); 

function delete_object(db, id) {
	$.ajax({
		type: 'DELETE',
		url: '/restapi/'+db+'/delete/'+id,
		success:function(data){
			var json = $.parseJSON(data);
			if (json["results"]) 
	                        alert('Object was deleted successfully.');
	                else 
                	        alert('Could not save data to database.');

			//refresh
			redirect(window.location);
		},
		error:function(xhr, error, msg){
			alert('Error no.' + msg + '. Could not delete object.');
		}
 	});
}

function inject_object(db, id) {
	redirect("/inject/"+db+"/"+id);
} 

function get_composite_id(id) {
	var substr = id.split("_");
        var key = '';
        var index = -1;

        // if there are more than one  '_' in the key
        if (substr.length > 2) {
                $.each(substr, function(i, v) {
                        if(i < substr.length-1)
                                key += v ;
                                if (i < substr.length-2)
                                        key += "_";
                });

                // calculate index
                index = substr[substr.length-1];
        }
        else {
                key = substr[0];
                index = substr[1];
	}
	return [key, index];
}

function edit_composite_object(id) {
	c = get_composite_id(id);	

	// call dialog to edit the object
	edit_box(c[0], c[1]);
}

function create_composite_object(key) {
	create_box(key);
}

function delete_composite_object(key, index) {
	// remove element from list
	jsondata[key].splice(index, 1);

	// refresh
	update_object(db_name);
}

function add_to_chain(chainid, campaignid) {
	if (campaignid.indexOf("-") != -1)
		new_tab_redirect("/edit/requests/"+campaignid);
	else	
		new_tab_redirect("/create/requests/"+campaignid+"/?chainid="+chainid);
}

function create_box(key) {
	$("#"+key+"_dialog").dialog({
                closeOnEscape: true,
                autoOpen: true,
                title: "edit "+key,
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
                buttons: [{
                                text: "close",
                                click: function() {
                                        $("#"+key+"_dialog").dialog('close');
                                }
                        },{
                                text: "save",
                                click: function() {
                                        if (key == "generators" || key=="process_string" || key=="type" || key=="cmssw_release" || key=="allowed_campaigns")       
                                                update_json_object(key, $("#"+key+"_"+key).val());
                                        else 
                                                update_json_object(key, get_dialog_data(key));
                               }
                        }],
        });
}

function edit_box(key, index) {
	$("#"+key+"_dialog").dialog({
		closeOnEscape: true, 
		autoOpen: true,
		title: "edit "+key,
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
			ob = jsondata[key][index];
			build_edit_dialog(ob, key);	
		},
		buttons: [{ 
				text: "close", 
				click: function() {
					$("#"+key+"_dialog").dialog('close');
				}
			},{
				text: "update",
				click: function() {
					if (key == "generators" || key=="process_string" || key=="type" || key=="cmssw_release")  
						update_json_object(key, $("#"+key+"_"+key).val(), index);
					else {
						update_json_object(key, get_dialog_data(key), index);
					}
				}
			},{
				text: "delete",
				click: function() {
					delete_composite_object(key, index);
				}
			}],
	});
}

function build_edit_dialog(ob, key) {
	if (typeof ob === "string")
		$("#"+key+"_"+key).val(ob);
	$.each(ob, function(k, v) {
		$.each(this, function(k2,v2) {
			$("#"+key+"_"+k2).val(v2);
		});
		$("#"+key+"_"+k).val(v);
	});
}

function zfill(n){ 
	n=n+'';
	while(n.length < 2)
		n="0"+n;
	return n;
}

function get_date() {
	d = new Date();
	return d.getFullYear() + "-" + zfill(d.getMonth()) + "-" + zfill(d.getDay()) + "-" + zfill(d.getHours()) + "-" + zfill(d.getMinutes());
}

function get_dialog_data(key) {
	var json_var = $(window).attr(key+"_json");
        $.each(json_var, function(k, v) {
                $.each(this, function(k2,v2) {
                        if ($("#"+key+"_"+k2).length)
                                json_var[k][k2] = $("#"+key+"_"+k2).val();
                        if (k2 == 'submission_date')
                                json_var[k][k2] = get_date();
                });
                if ($("#"+key+"_"+k).length)
                        json_var[k] = $("#"+key+"_"+k).val();
        });
	return json_var;
}

function update_json_object(key, value, index) {
	// push object to db 
	if (typeof index != undefined)
		jsondata[key][index] = value;
	else
		jsondata[key].push(value);
	
	//alert($.stringify(json_var));
	update_object(db_name); // push to the database and reload page
} 

// extend jquery to add stringify implementation for json
$.extend({
	stringify  : function stringify(obj) {         
		//if ("JSON" in window) {
	        //    return JSON.stringify(obj);
        	//}
		
		var t = typeof (obj);
		if (t != "object" || obj === null) {
			// simple data type
			if (t == "string") obj = '"' + obj + '"';
				return String(obj);
		} else {
        	    	// recurse array or object
			var n, v, json = [], arr = (obj && obj.constructor == Array);

			for(n in obj) {
				v = obj[n];
	        	        t = typeof(v);
        	        	if (obj.hasOwnProperty(n)) {
					if (t == "string") {
						if (!$.isNumeric(v))
							v = '"' + v + '"';
					} else if (t == "object" && v !== null){
						v = jQuery.stringify(v);
	                    		}
					if ($.isNumeric(v))
						json.push((arr ? "" : '"' + n + '":') + Number(v));
					else
						json.push((arr ? "" : '"' + n + '":') + String(v));
                		}
            		}

			return json_escape((arr ? "[" : "{") + String(json) + (arr ? "]" : "}"));
		}
	}
});
