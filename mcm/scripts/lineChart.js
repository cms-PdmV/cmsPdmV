//requires jQuery, d3

//expecting sorted data
function LineChart(chartData, config) {

    //default values
    var statuses = ['new', 'validation', 'defined', 'approved', 'submitted', 'done'],
        margin = {
            top: 60,
            right: 60,
            bottom: 60,
            left: 60
        },
        width,
        height = 500,
        infoboxView = function(data) {
            return '<div><a>' + data.prepid + '</a></div>';
        },
        shapePoints = [{
            'name': 'triangle',
            'points': '0,-6 -6,6 6,6'
        }, {
            'name': 'heart',
            'points': '0,6 8,-2 4,-6 0,-2 -4,-6 -8,-2'
        }, {
            'name': 'rectangle',
            'points': '6,-6 6,6 -6,6 -6,-6'
        }, {
            'name': 'house',
            'points': '6,0 6,6 -6,6 -6,0 0,-6'
        }, {
            'name': 'trianglev2',
            'points': '0,-6 -6,6 0,3 6,6'
        }, {
            'name': 'diamond',
            'points': '0,-6 6,0 0,6 -6,0'
        }];

    //set configurations
    if (config) {
        if (config.statuses) {
            statuses = config.statuses;
        }
        if (config.margin) {
            margin = config.margin;
        }
        if (config.width) {
            width = config.width;
        }
        if (config.height) {
            height = config.height;
        }
        if (config.infobox) {
            infoboxView = config.infobox;
        }
        if (config.shapeInterval) {
            shapeInterval = config.shapeInterval
        }
    }

    var initSize = function() {
        var $windowWidth = $(window).width();
        if (!width) {
            width = $windowWidth - margin.left - margin.right;
        }
    }();

    var data = chartData,
        dateFrom,
        dateTo;

    //min and max values for x axis, assuming data is sorted chronologically
    var calculateMinAndMaxDates = function() {
        $.each(data, function(key, value) {
            if (!dateFrom || value[0].date < dateFrom) {
                dateFrom = value[0].date;
            }

            if (!dateTo || value[value.length - 1].date > dateTo) {
                dateTo = value[value.length - 1].date;
            }
        });
    }();

    //scale functions
    var xScale = d3.time.scale()
        .domain([dateFrom, dateTo])
        .range([0, width - margin.left - margin.right]);

    var yScale = d3.scale.linear()
        .domain([0, statuses.length - 1])
        .range([height - margin.top - margin.bottom, 0]);

    var lineFunction = d3.svg.line()
        .x(function(d, i) {
            return xScale(d.date);
        })
        .y(function(d, i) {
            return yScale(statuses.indexOf(d.status));
        })
        .interpolate('linear');

    var xAxis = d3.svg.axis()
        .scale(xScale)
        .orient('bottom')
        .tickFormat(d3.time.format('%Y-%m-%d'))
        .tickSize(-height + margin.top + margin.bottom, 0, 0)
        .tickPadding(10)
        .ticks(10);

    var yAxis = d3.svg.axis()
        .scale(yScale)
        .orient('left')
        .tickFormat(function(d) {
            if (statuses[d]) {
                return statuses[d];
            }
        })
        .tickSize(-width + margin.left + margin.right, 0, 0)
        .tickPadding(10)
        .ticks(statuses.length);


    //add svg container
    var container = d3.select('#line-chart')
        .attr('class', 'line-chart')
        .append('svg:svg')
        .attr('width', width)
        .attr('height', height)
        .append('svg:g')
        .attr('transform', 'translate(' + margin.left + ', ' + margin.top + ')');

    //add x axis
    container.append('svg:g')
        .attr('class', 'x axis')
        .attr('transform', 'translate(0, ' + (height - margin.top - margin.bottom) + ')')
        .call(xAxis)
        .selectAll('text')
        .style('text-anchor', 'end')
        .attr('dx', '-12px')
        .attr('dy', '2px')
        .attr("transform", function(d) {
            return "rotate(-45)"
        });

    //add y axis
    container.append('svg:g')
        .attr('class', 'y axis')
        .call(yAxis);

    var nextShapeId = 0;
    var getNextShape = function() {
        nextShapeId++;

        if (nextShapeId >= shapePoints.length) {
            nextShapeId = 0;
        }
        return shapePoints[nextShapeId];
    }

    var existingRequests = {};
    var tempRequestShapes = [];
    var isShapeAssigned = function(requestId) {
        var len = tempRequestShapes.length;
        for (var i = 0; i < len; i++) {
            if (tempRequestShapes[i].requestId === requestId) {
                return true;
            }
        }
        return false;
    };
    var getShapeForRequest = function(requestId, color, elementId) {
        var resultShape = {};
        var currentShape;

        if (requestId in existingRequests) {
            currentShape = existingRequests[requestId];
        } else {
            currentShape = getNextShape();
            existingRequests[requestId] = currentShape;

        }
        resultShape.color = color;
        resultShape.name = currentShape.name;
        resultShape.points = currentShape.points;
        resultShape.elementId = elementId;
        resultShape.requestId = requestId;
        if (!isShapeAssigned(requestId)) {
            tempRequestShapes.push(resultShape);
        }

        return resultShape;
    };

    var getCloseElements = function($element, $elements) {
        var result = [],
            cx = parseFloat($element.attr('data-x')),
            cy = parseFloat($element.attr('data-y')),
            cxCompare,
            cyComapre,
            visible,
            err = 10; //how close can elements be

        $.each($elements, function(key, value) {
            cxCompare = parseFloat(value.getAttribute('data-x'));
            cyCompare = parseFloat(value.getAttribute('data-y'));
            visible = $(value).css('display') != 'none';

            if (visible && cxCompare <= (cx + err) && cxCompare >= (cx - err) && cyCompare <= (cy + err) && cyCompare >= (cy - err)) {
                result.push(value);
            }
        });
        return result;
    };

    //set up tooltips
    var showInfobox = true;
    var showTooltip = function(element, data, offset) {
        var height = 90;
        var htmlData = infoboxView(data);
        var $infobox = $('<div class="infobox"></div>').appendTo('#line-chart');
        var coord = $(element).position();

        $infobox.css({
            'height': height - 15 + 'px',
            'left': (coord.left - 190) + 'px',
            'top': (coord.top + (height * offset) + 20) + 'px'
        });

        $infobox.append(htmlData);
        $infobox.on('click', function() {
            $(this).remove();
            showInfobox = true;
        });
    };
    var removeTooltips = function() {
        $('.infobox').remove();
    };
    (function() {
        $('body').on('click', function(e) {
            if (!showInfobox) {
                removeTooltips();
            }
            showInfobox = false;
        });
    })();

    //draw functions
    var drawLine = function(data, color, elementId, container) {
        return container.append('svg:path')
            .attr('class', 'data element-' + elementId)
            .attr('d', lineFunction(data))
            .attr('style', 'stroke:' + color);
    };

    var drawShape = function(x, y, shape, container) {
        return container
            .append('svg:polygon')
            .attr('class', 'polygon')
            .attr('transform', 'translate(' + x + ',' + y + ')')
            .attr('points', shape.points)
            .attr('style', 'stroke:' + shape.color)
            .attr('data-element-id', shape.elementId);
    };

    var drawShapes = function(data, color, elementId) {
        container
            .append('svg:g')
            .selectAll('polygon')
            .data(data)
            .enter()
            .append('svg:polygon')
            .attr('style', 'stroke:' + color)
            .attr('class', 'polygon data element-' + elementId)
            .attr('transform', function(d) {
                var x = xScale(d.date);
                var y = yScale(statuses.indexOf(d.status));
                return 'translate(' + x + ',' + y + ')';
            })
            .attr('points', function(d) {
                return getShapeForRequest(d.requestId, color, elementId).points;
            })
            .attr('data-x', function(d) {
                return xScale(d.date);
            })
            .attr('data-y', function(d) {
                return yScale(statuses.indexOf(d.status));
            })
            .on('mouseover', function(element) {
                $(this).css('fill', color);
            })
            .on('mouseout', function(element) {
                $(this).css('fill', '#fff');
            })
            .on('click', function(d) {
                var $this = $(this);
                var closePolygons = getCloseElements($this, $polygons);

                //show all nearby elements tooltips
                $.each(closePolygons, function(key, value) {
                    showTooltip(value, value.__data__, key);
                });
                showInfobox = true;
            });

        console.log(tempRequestShapes);
    };

    //draw a legend
    var legend = {};
    var legendTextIndent = 10;
    var shapeCenterOffset = 4;
    var lineHeight = 20;
    var drawLegendBlock = function(title, content, x, y, legendContainer) {
        legendContainer
            .append('svg:text')
            .attr('x', x + legendTextIndent + 'px')
            .attr('y', y + 'px')
            .html(title);
        legendContainer.append('svg:circle')
            .attr('data-show', 'true')
            .attr('class', 'legend-circle')
            .attr('cx', x)
            .attr('cy', y - shapeCenterOffset)
            .attr('r', '6')
            .attr('fill', content.color)
            .attr('stroke', content.color)
            .attr('stroke-width', '1.5')
            .on('mouseover', function() {
                $(this).css('stroke-width', '3');
            })
            .on('mouseout', function() {
                $(this).css('stroke-width', '1.5');
            })
            .on('click', function() {
                $this = $(this);
                var elementId = '.element-' + content.elementId;

                if ($this.attr('data-show') == 'false') {
                    $this.css('fill', content.color);
                    $this.attr('data-show', 'true');
                    $(elementId).fadeIn();
                } else {
                    $this.css('fill', '#fff');
                    $this.attr('data-show', 'false');
                    $(elementId).fadeOut();
                }
            });

        var shapey = y + lineHeight;
        $.each(content, function(key, value) {
            legendContainer.append('svg:text')
                .attr('x', (x + 3 * legendTextIndent) + 'px')
                .attr('y', shapey + 'px')
                .html(value.requestId);

            drawShape(x + 2 * legendTextIndent, shapey - shapeCenterOffset, value, legendContainer)
                .attr('data-show', 'false');
            shapey += lineHeight;
        });
    };
    var drawLegendToggle = function(legendContainer) {
        var toggleColor = '#000';
        legendContainer
            .append('svg:text')
            .attr('x', legendTextIndent + 'px')
            .attr('y', height + 'px')
            .html('Toggle all');

        legendContainer.append('svg:circle')
            .attr('class', 'toggle-all')
            .attr('data-show', 'true')
            .attr('cx', 0)
            .attr('cy', height - shapeCenterOffset)
            .attr('r', '6')
            .attr('fill', toggleColor)
            .attr('stroke', toggleColor)
            .attr('stroke-width', '1.5')
            .on('mouseover', function() {
                $(this).css('stroke-width', '3');
            })
            .on('mouseout', function() {
                $(this).css('stroke-width', '1.5');
            })
            .on('click', function() {
                $this = $(this);
                $circles = $('.legend-circle');
                $lines = $('.data');

                if ($this.attr('data-show') == 'true') {
                    $this.css('fill', '#fff');
                    $this.attr('data-show', 'false');
                    $lines.fadeOut();
                    $lines.attr('data-show', 'false');
                    $circles.attr('data-show', 'false');
                    $circles.css('fill', '#fff');
                } else {
                    $this.css('fill', toggleColor);
                    $this.attr('data-show', 'true');
                    $lines.attr('data-show', 'true');
                    $circles.attr('data-show', 'true');

                    $.each($circles, function(key, value) {
                        $value = $(value);
                        $value.css('fill', $value.attr('stroke'));
                    });

                    $lines.fadeIn(1000);
                }
            });
    };
    var drawLegend = function() {
        var legendContainer = container.append('svg:g')
            .attr('class', 'legend')
            .attr('transform', 'translate(' + (-margin.left + 40) + ', 0)');
        drawLegendToggle(legendContainer);

        var getMaxItemWidth = function() {
            var currentWidth = 0;
            $.each(legend, function(key, value) {
                if (currentWidth < key.length) {
                    currentWidth = key.length;
                }
            });

            return currentWidth;
        };
        var averageCharWidth = 6.5;
        var maxItemWidth = getMaxItemWidth() * averageCharWidth;

        var x = 0;
        var y = height + 2 * lineHeight - shapeCenterOffset;
        var subelementsCount = 0;
        $.each(legend, function(key, value) {
            if (x + maxItemWidth >= width) {
                x = 0;
                y += subelementsCount * lineHeight + lineHeight;
                subelementsCount = 0;
            }

            if (value.length > subelementsCount) {
                subelementsCount = value.length;
            }
            drawLegendBlock(key, value, x, y, legendContainer);
            x += maxItemWidth;
        });
        $('#line-chart svg').attr('height', y + 150);
    };

    var render = function() {
        var color = d3.scale.category20().range();
        var colorId = 0;
        var elementId = 0;

        //draw lines and shapes
        $.each(data, function(key, element) {
            tempRequestShapes = [];
            if (colorId >= 20) {
                colorId = 0;
            }
            drawLine(element, color[colorId], elementId, container);
            drawShapes(element, color[colorId], elementId);

            legend[key] = tempRequestShapes;
            legend[key].color = color[colorId];
            legend[key].elementId = elementId;
            colorId++;
            elementId++;
        });

        drawLegend();
    }();

    var $polygons = $('#line-chart polygon');
};