//requires LineChart, underscore
testApp.directive("lineChart", function($http, $location) {

    function link(scope, element, attrs) {
        scope.dbName = $location.search()["db_name"];
        scope.ids = $location.search()["prepid"];
        scope.chartData = {};
        scope.chart = LineChart;
        scope.possibleStatuses = ['new', 'validation', 'defined', 'approved', 'submitted', 'done'];
        scope.chartConfig = {
            statuses: scope.possibleStatuses,
            //width: 1000,
            height: 550,
            margin: {
                top: 40,
                right: 20,
                bottom: 60,
                left: 79
            },
            infobox: function(data) {
                var htmlData = "";
                htmlData += '<div><a target="_self" href="/mcm/chained_requests?prepid=' + data.prepid + '">' + data.prepid + '</a></div>';
                htmlData += '<div>Request <a target="_self" href="/mcm/requests?prepid=' + data.requestId + '">' + data.requestId + '</a></div>';
                htmlData += '<div>' + data.status + ' at ' + data.date.toLocaleDateString() + ' ' + data.date.toLocaleTimeString() + '</div>';
                htmlData += '<div>By <a target="_self" href="/mcm/users?prepid=' + data.author + '">' + data.author + '</a></div>';
                return htmlData;
            }
        }

        scope.parseData = function(rawData) {
            var entry;
            var parseDate = function(date) {
                var replaceAt = function(i, char, str) {
                    return str.substr(0, i) + char + str.substr(i + char.length);
                };

                date = replaceAt(10, "T", date);
                date = replaceAt(13, ":", date);
                return new Date(date);
            }

            //for each chained request
            _.each(rawData, function(chainedRequest, chainedRequestName) {
                scope.chartData[chainedRequestName] = [];

                //for each chained request state
                _.each(chainedRequest, function(state) {

                    //if current status is in possible statuses then add it
                    if (scope.possibleStatuses.indexOf(state.step) > -1) {
                        entry = {
                            'date': parseDate(state.updater.submission_date),
                            'status': state.step,
                            'prepid': chainedRequestName,
                            'author': state.updater.author_username,
                            'requestId': state.request_id
                        };
                        scope.chartData[chainedRequestName].push(entry);
                    }
                });

                //sort requests by date 
                scope.chartData[chainedRequestName] =
                    _.sortBy(scope.chartData[chainedRequestName], function(num) {
                        return num.date;
                    });
            });
        };

        scope.getData = function() {
            if (!scope.ids) {
                return false;
            }

            var promise = $http.get("restapi/" + scope.dbName + "/fullhistory/" + scope.ids);

            promise.then(function(data) {
                scope.parseData(data.data.results);
                scope.chart(scope.chartData, scope.chartConfig);
            });
        }();
    }

    return {
        replace: true,
        restrict: 'E',
        template: '<div id="line-chart"></div>',
        link: link
    };
});