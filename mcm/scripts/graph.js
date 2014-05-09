/*
 * Author: Ramunas
 *
 */

//requires d3
var Graph =
(function (config) {
    "use strict";

    //default settings
    var settings = {
        width: 1000,
        height: 500,
        charge: -500,
        linkDistance: 100,
        linkWidth: 2,
        nodeRadius: 10,
        gravity: 0.1,
        friction: 0.5,
        marker: {
            viewBox: "0 -5 10 15",
            refX: 15,
            refY: 0,
            width: 30,
            height: 20,
            orient: "auto",
            path: "M0,-5L15,0L0,5"
        },
        containerId: "#graph",
        colors: d3.scale.category20().range(),
        colorsNames: []
    },

        //override provided settings
        initSettings = (function () {
            for (var option in config) {
                if (config.hasOwnProperty(option)) {
                    settings[option] = config[option];
                }
            }

            var len = settings.colors.length;
            for (var i = 0; i < len; i++) {
                settings.colorsNames[i] = settings.colors[i].substring(1);
            }      
        }()),

        nodes = {},
        links = {},
        nodesArray = [], //nodes array for d3
        linksArray = [], //links array for d3

        svg = d3.select(settings.containerId).append("svg")
            .attr("width", settings.width)
            .attr("height", settings.height),

        defs = svg.insert("svg:defs").selectAll("marker").data(settings.colorsNames),
        markerPath = defs.enter().append("svg:marker")
            .attr("id", String)
            .attr("viewBox", settings.marker.viewBox)
            .attr("refX", settings.marker.refX)
            .attr("refY", settings.marker.refY)
            .attr("markerWidth", settings.marker.width)
            .attr("markerHeight", settings.marker.height)
            .attr("orient", settings.marker.orient)
            .attr("markerUnits", "userSpaceOnUse")
            .attr("fill",function (d) {
                return "#" + d;
            })
            .append("svg:path")
            .attr("d", settings.marker.path),

        svgNode = svg.selectAll(".node"),
        svgLink = svg.selectAll(".link"),

        tick = function () {
            svgNode.attr("transform", function (d) {
                return "translate(" + d.x + "," + d.y + ")";
            });

            svgLink
                .attr("x1", function (d) {
                    return d.source.x;
                })
                .attr("y1", function (d) {
                    return d.source.y;
                })
                .attr("x2", function (d) {
                    return d.target.x;
                })
                .attr("y2", function (d) {
                    return d.target.y;
                });
        },

        forceLayout = d3.layout.force()
            .nodes(nodesArray)
            .links(linksArray)
            .gravity(settings.gravity)
            .friction(settings.friction)
            .charge(settings.charge)
            .linkDistance(settings.linkDistance)
            .size([settings.width, settings.height])
            .alpha(0)
            .on("tick", tick),

        toArray = function (obj) {
            var result = [];
            for (var o in obj) {
                if (obj.hasOwnProperty(o)) {
                    result.push(obj[o]);
                }
            }

            return result;
        },

        drawLinks = function () {
            linksArray = toArray(links);
            forceLayout.links(linksArray);

            //svgLink.remove();
            svgLink = svg.selectAll('.link');
            svgLink = svgLink.data(forceLayout.links(), function (d) {
                return d.id;
                //return d.source.id + "-" + d.target.id;
            });

            svgLink.enter().insert("line", ".node")
                //.attr("class", "link")
                .attr("class", function (d) {
                    return d.original ? "link original" : "original";
                })
                .attr("stroke-width", function (d) {
                    return d.size === 1 ? settings.linkWidth : settings.linkWidth * 2;
                })
                .attr("stroke", function (d) {
                    return d.color;
                })
                .attr("marker-end", function (d) {
                    return "url(" + d.color + ")";
                });
            svgLink.exit().remove();
        },

        drawNodes = function () {
            nodesArray = toArray(nodes);
            forceLayout.nodes(nodesArray);

            //svgNode.remove();
            svg.selectAll(".original").remove();
            svgNode = svg.selectAll(".node");
            svgNode = svgNode.data(forceLayout.nodes(), function (d) {
                return d.id;
            });

            var svgNodeEnter = svgNode.enter()
                .append("g")
                .attr("class", function (d) {
                    var classes = "node";
                    if (d.isExpanded) classes += " expanded" ;
                    if (!d.originalId) classes += " original" ;
                    return classes;
                    //return d.isExpanded ? "node expanded" : "node";
                })
                .call(forceLayout.drag);

            svgNodeEnter.append("circle")
                .attr("r", settings.nodeRadius)
                .attr("stroke", function (d) {
                    return d.color;
                })
                .attr("fill", function (d) {
                    return d.color;
                });

            svgNodeEnter.append("text")
                .attr("class", "node-text")
                .attr("y", -settings.nodeRadius * 1.2)
                .text(function (d) {
                    return d.title;
                });
            svgNode.exit().remove();
        },

        draw = function () {              
            drawNodes();
            drawLinks();

            forceLayout.start();
        },

        getLink = function (nodeId1, nodeId2) {
            var linkName = nodeId1 + '-' + nodeId2;

            if(links[linkName]){
                return links[linkName];
            }

            linkName = nodeId2 + '-' + nodeId1;

            if(links[linkName]){
                return links[linkName];
            }

            console.log("Link not found");
            return false;
        },

        addLink = function (nodeId1, nodeId2, count) {
            var linkName = nodeId1 + '-' + nodeId2,
                size = 1;

            if (count) {
                size = count;
            }

            //if link already exists increase its size
            if (links[linkName]) {

                links[linkName].size++;
                return links[linkName];   
            }

            //otherwise create new link and set its neighbours
            var newLink = {
                id: linkName,
                color: nodes[nodeId1].color,
                source: nodes[nodeId1],
                target: nodes[nodeId2],
                size: size
            };

            links[linkName] = newLink;

            nodes[nodeId1].neighbours[nodeId2] = nodes[nodeId2];
            nodes[nodeId2].neighbours[nodeId1] = nodes[nodeId1];

            return newLink;
        },

        removeLink = function (nodeId1, nodeId2) {
            var linkName = nodeId1 + '-' + nodeId2,
                node1 = nodes[nodeId1],
                node2 = nodes[nodeId2];

            //remove neighbour relationship
            if (node1.neighbours[nodeId2] && node2.neighbours[nodeId1]){
                delete node1.neighbours[nodeId2];
                delete node2.neighbours[nodeId1];
            } else {
                console.log("Neighbour not found while removing the link");
            }
            
            if (links[linkName]) {
                delete links[linkName];
                return true;
            } 

            linkName = nodeId2 + '-' + nodeId1;
            if (links[linkName]) {
                delete links[linkName];
                return true;
            }

            console.log("Link not found while trying to remove it");
            return false;
        },

        addLinks = function (linksArray) {
            var len = linksArray.length,
                link;
            for (var i = 0; i < len; i++) {
                link = addLink(linksArray[i].source, linksArray[i].target);
                link.original = true;
            }
        },

        removeLinks = function (linksArray) {
            //not used yet
        },

        expandLinks = function (linkToExpand) {
            expandNodes(linkToExpand.target);
        },

        reduceLinks = function (linkToReduce) {
            reduceNodes(linkToReduce.target);
        },

        getNeighbours = function (nodeId) {
            return nodes[nodeId].neighbours;
        },

        addElement = function (list, element) {
            list = list || [];
            list.push(element);

            return list;
        },

        //group neighbour links by original node id
        getGroupedNeighbourLinks = function (nodeId) {
            var neighbours = getNeighbours(nodeId),
                neighbourLinks = {},
                neighbourLink,
                originalId;

            for (var neighbourId in neighbours) {
                neighbourLink = getLink(nodeId, neighbourId);
                originalId = neighbours[neighbourId].originalId;

                //if original id is undefined, neighbour itself is original
                if (!originalId) {
                    originalId = neighbourId;
                }

                neighbourLinks[originalId] =
                    addElement(neighbourLinks[originalId], neighbourLink);
            }

            return neighbourLinks;
        },          

        getMaxLinkSize = function (groupedLinks) {
            var currentMax = 0,
                currentSize = 0;

            //for each link group find its max size
            for (var i in groupedLinks) {

                //if length is 1, link is not expanded
                if (groupedLinks[i].length === 1) {
                    currentSize = groupedLinks[i][0].size;
                } else {
                    currentSize = groupedLinks[i].length;
                }

                if (currentSize > currentMax) {
                    currentMax = currentSize;
                }
            }

            return currentMax;
        },

        createLinkCopies = function (link, targetNodes, originalNodeId) {
            var linkSize = link.size,
                linkSourceId = link.source.id,
                source = true,
                copies = [],
                newLink,
                mapTo  = linkSourceId,
                i;

            //if source is not original, map to target
            if (linkSourceId !== originalNodeId) {
                mapTo = link.target.id;
                source = false;
            }

            for (i = 0; i < linkSize - 1; i++) {

                if (source) {
                    newLink = addLink(mapTo, targetNodes[i].id);
                } else {                    
                    newLink = addLink(targetNodes[i].id, mapTo);
                }

                //newLink = addLink(targetNodes[i].id, mapTo);
                newLink.originalSize = linkSize;
                copies.push(newLink);
            }

            //handle original link
            link.size = 1;
            link.isExpanded = true;

            return copies;
        },

        mapLinks = function (linksToMap, nodeCopies) {
            var len = linksToMap.length,
                originalNodeId,
                i,
                link,
                map;

            if (nodeCopies.length > 0) {
                originalNodeId = nodeCopies[0].originalId;
            } else {
                console.log("Cannot map links");
                return;
            }

            //remove link between originals
            for (i = 0; i < len; i++) {
                if (!linksToMap[i].source.originalId && !linksToMap[i].target.originalId) {
                    linksToMap.splice(i, 1);
                    len--;
                    i--;
                }
            }

            //map links
            for (i = 0; i < len; i++) {

                // if (linksToMap[i].source.id === originalNodeId) {
                //     map = "target";
                // } else {
                //     map = "source";
                // }

                if (linksToMap[i].source.id === originalNodeId) {
                    map = "target";
                    addLink(nodeCopies[i].id, linksToMap[i][map].id);
                } else {
                    map = "source";
                    addLink(linksToMap[i][map].id, nodeCopies[i].id);
                }

                //link = addLink(linksToMap[i][map].id, nodeCopies[i].id);
                removeLink(linksToMap[i].source.id, linksToMap[i].target.id);
            }

            return linksToMap;
        },

        expandLinkGroup = function (linkGroupName, linkGroup, nodeCopies) {

            //check if group contains expandable or mappable links
            if (linkGroup.length === 1 && linkGroup[0].size > 1) {
                createLinkCopies(linkGroup[0], nodeCopies, linkGroupName);
            } else {
                mapLinks(linkGroup, nodeCopies);
            }
        },

        addNode = function (id, title, color) {
            var node = {};
            node.id = id;
            node.title = title;
            node.neighbours = {};

            if (color) {
                node.color = color;
            }

            nodes[id] = node;

            return node;
        },


        removeNode = function (id) {
            var neighbours = nodes[id].neighbours;

            //remove neighbour links
            if (neighbours) {
                for (var i in neighbours) {
                    removeLink(id, neighbours[i].id);
                }
            }
            
            delete nodes[id];
        },

        addNodes = function (nodesArray) {
            var len = nodesArray.length,
                colors = settings.colors,
                colorId = 0;

            for (var i = 0; i < len; i++) {

                if (colorId >= 20) colorId = 0;

                addNode(nodesArray[i].id, nodesArray[i].id, colors[colorId]);
                colorId++;
            }
        },

        removeNodes = function (nodes) {
            //not used yet
        },

        refactorLink = function (nodeId1, nodeId2) {
            var node1Original = nodes[nodeId1].originalId || nodes[nodeId1].id,
                node2Original = nodes[nodeId2].originalId || nodes[nodeId2].id,
                originalLink = getLink(node1Original, node2Original);

            //if there is no originalId field, node is original
            if (!nodes[nodeId1].originalId) {

                originalLink.size++;
                removeLink(nodeId1, nodeId2);

            } else {
                if (originalLink.source.id === node1Original) {
                    addLink(node1Original, nodeId2);
                } else {
                    addLink(nodeId2, node1Original);
                }
                removeLink(nodeId1, nodeId2);

            }
        },

        refactorNode = function (node) {
            var nodeId = node.id,
                neighbours = node.neighbours;
            
            for (var i in neighbours) {
                refactorLink(nodeId, neighbours[i].id);
            }

            removeNode(nodeId);
        },

        createNodeCopies = function (nodeToCopy, count) {
            var nodeId = nodeToCopy.id,
                nodeTitle = nodeToCopy.title,
                newNodeId,
                nodeCopy,
                copies = [];

            for (var i = 0; i < count; i++) {
                newNodeId = '' + nodeId + i;
                nodeCopy = addNode(newNodeId, nodeTitle, nodeToCopy.color);
                nodeCopy.isExpanded = true;
                nodeCopy.originalId = nodeToCopy.id;
                copies.push(nodeCopy);
            }

            return copies;
        },

        expandNodes = function (nodeToExpand) {
            if (nodeToExpand.isExpanded) {
                return;
            }

            var nodeId = nodeToExpand.id,
                neighbourLinks = getGroupedNeighbourLinks(nodeId),
                maxLinkSize = getMaxLinkSize(neighbourLinks),
                nodeCopies = createNodeCopies(nodeToExpand, maxLinkSize - 1);

            nodeToExpand.copies = nodeCopies;

            for (var i in neighbourLinks) {
                expandLinkGroup(i, neighbourLinks[i], nodeCopies);
            }

            nodeToExpand.isExpanded = true;
        },

        getNodeCopies = function (nodeId) {
            return nodes[nodeId].copies;
        },

        reduceNodes = function (nodeToReduce) {
            var originalId = nodeToReduce.originalId;

            if (!originalId) {
                originalId = nodeToReduce.id;
            }

            var nodeCopies = getNodeCopies(originalId);

            for (var i in nodeCopies) {
                refactorNode(nodeCopies[i]);
            }
            delete nodes[originalId].copies;

            nodes[originalId].isExpanded = false;
        };   

    //expose functions
    return {
        addNodes: addNodes,
        removeNodes: removeNodes,
        expandNodes: expandNodes,
        reduceNodes: reduceNodes,
        addLinks: addLinks,
        removeLinks: removeLinks,            
        expandLinks: expandLinks,
        reduceLinks: reduceLinks,
        draw : draw
    };
});