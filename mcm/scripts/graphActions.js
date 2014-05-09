(function () {
    var url = "/mcm/search?db_name=chained_campaigns&valid=true&page=-1",
        graph,

    parseResult = function (result) {
        result = jQuery.parseJSON(result);
        
        var tempNodeArray = [],
            nodes = [],
            links = [],
            entries = result.results,
            entriesLen = entries.length,
            campaignLen;

        for (var i = 0; i < entriesLen; i++) {

            campaignLen = entries[i].campaigns.length;
            for (var j = 0; j < campaignLen; j++) {

                //add node if it doesn't already exist
                if ($.inArray(entries[i].campaigns[j][0], tempNodeArray) === -1) {
                    tempNodeArray.push(entries[i].campaigns[j][0]);
                    nodes.push({
                        "id": entries[i].campaigns[j][0]
                    });
                }

                if (j !== 0) {  
                    links.push({
                        "source": entries[i].campaigns[j - 1][0],
                        "target": entries[i].campaigns[j][0],
                        "name": entries[i].campaigns[j][1]
                    });
                }

            }

        }

        return {
            nodes: nodes,
            links: links
        };
    },

    draw = function (nodes, links) {
        graph = new Graph({
            width: window.innerWidth - 4,
            height: window.innerHeight - 4,
            linkDistance: 80,
            nodeRadius: 8,
            charge: -600
        });

        graph.addNodes(nodes);
        graph.addLinks(links);
        graph.draw();
    },

    setListeners = function () {
        var $svg = $('svg');

        $svg.on('dblclick', '.node', function () {
            var thisData = this.__data__;

            if (thisData.isExpanded) {
                graph.reduceNodes(thisData);
            } else {
                graph.expandNodes(thisData);
            }

            graph.draw();
        })
        .on('mouseover', '.node',function () {
            $(this).find('.node-text').show();
        })
        .on('mouseleave', '.node',function () {
            $(this).find('.node-text').hide();
        });
    };

    $.ajax({
        type: "GET",
        url: url,
        success: function (result) {
            var parsedResult = parseResult(result);

            draw(parsedResult.nodes, parsedResult.links);
            setListeners();
        }
    });

}());