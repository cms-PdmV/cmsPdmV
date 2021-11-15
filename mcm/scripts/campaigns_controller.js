angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'CMSSW Release', select: true, db_name: 'cmssw_release' },
        { text: 'Energy', select: true, db_name: 'energy' },
        { text: 'Next', select: true, db_name: 'next' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.dbName = "campaigns";

      $scope.nextStatus = function (prepid) {
        $http({ method: 'GET', url: 'restapi/' + $scope.dbName + '/status/' + prepid }).success(function (data, status) {
          $scope.setSuccess(data.results);
          if (data.results) {
            $scope.getData();
          } else {
            $scope.openErrorModal(value, data['message']);
          }
        }).error(function (status) {
          $scope.openErrorModal(value, data['message']);
          $scope.setSuccess(false, status);
        });
      };

      $scope.getData = function () {
        var query = ""
        _.each($location.search(), function (value, key) {
          if ((key != 'shown') && (key != 'fields')) {
            query += "&" + key + "=" + value;
          }
        });
        $scope.got_results = false; //to display/hide the 'found n results' while reloading
        var promise = $http.get("search?" + "db_name=" + $scope.dbName + query + "&get_raw")
        promise.then(function (data) {
          $scope.result_status = data.status;
          $scope.got_results = true;
          $scope.result = _.pluck(data.data.rows, 'doc');
          if ($scope.result === undefined) {
            alert('The following url-search key(s) is/are not valid : ' + _.keys(data.data));
            return; //stop doing anything if results are undefined
          }
          $scope.total_results = data.data.total_rows;
          if ($scope.result.length != 0) {
            columns = _.keys($scope.result[0]);
            rejected = _.reject(columns, function (v) { return v[0] == "_"; }); //check if charat[0] is _ which is couchDB value to not be shown
            //           $scope.columns = _.sortBy(rejected, function(v){return v;});  //sort array by ascending order
            _.each(rejected, function (v) {
              add = true;
              _.each($scope.columns, function (column) {
                if (column.db_name == v) {
                  add = false;
                }
              });
              if (add) {
                $scope.columns.push({ text: v[0].toUpperCase() + v.substring(1).replace(/\_/g, ' '), select: false, db_name: v });
              }
            });
            if (_.keys($location.search()).indexOf('fields') != -1) {
              _.each($scope.columns, function (elem) {
                elem.select = false;
              });
              _.each($location.search()['fields'].split(','), function (column) {
                _.each($scope.columns, function (elem) {
                  if (elem.db_name == column) {
                    elem.select = true;
                  }
                });
              });
            }
          }
          $scope.selectionReady = true;
        }, function () {
          alert("Error getting information");
        });
      };

      $scope.deletePrompt = function(prepid) {
        $scope.openIsSureModal('campaigns', prepid, 'delete', function(database, prepid, action) {
          $scope.deleteObject(database, prepid);
        });
      };

      $scope.$watch(function () {
        var loc_dict = $location.search();
        return "page" + loc_dict["page"] + "limit" + loc_dict["limit"];
      },
        function () {
          $scope.getData();
        });
    }
  ]
);

angular.module('testApp').controller('CreateRequestModal',
  ['$scope', '$http', '$modal',
    function CreateRequestModal($scope, $http, $modal) {
      $scope.openRequestCreator = function (campaignPrepid) {
        $http.get("restapi/users/get_pwg/" + $scope.user.name).then(function (data) {
          const pwgs = data.data.results;
          $modal.open({
            templateUrl: 'createRequestModal.html',
            controller: function ($scope, $modalInstance, $window, $http, pwgs, selectedPwg, prepid) {
              $scope.vars = {'prepid': prepid, 'pwgs': pwgs, 'selectedPwg': selectedPwg};
              $scope.save = function () {
                const requestData = {member_of_campaign: $scope.vars.prepid, pwg: $scope.vars.selectedPwg};
                $http({method: 'PUT', url: 'restapi/requests/save/', data: requestData}).success(function (data) {
                  if (data.results) {
                    $window.location.href = "edit?db_name=requests&query=" + data.prepid;
                  } else {
                    $scope.openErrorModal("New request", data['message']);
                    $scope.setSuccess(false, status);
                  }
                }).error(function (data, status) {
                  $scope.openErrorModal("New request", data['message']);
                  $scope.setSuccess(false, status);
                });
                $modalInstance.close();
              };
              $scope.close = function () {
                $modalInstance.dismiss();
              };
            },
            resolve: {
              pwgs: function () { return pwgs; },
              selectedPwg: function () { return pwgs[0]; },
              prepid: function () { return campaignPrepid; },
            }
          })
        });
      };
    }
  ]
);

angular.module('testApp').controller('CreateCampaignModal',
  ['$scope', '$http', '$modal', '$window',
    function CreateCampaignModal($scope, $http, $modal, $window) {
      $scope.openCampaignCreator = function () {
        $modal.open({
          templateUrl: 'createCampaignModal.html',
          controller: function ($scope, $modalInstance) {
            $scope.vars = {"newPrepid": ""};
            $scope.save = function () {
              $modalInstance.close($scope.vars.newPrepid);
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            };
          }
        }).result.then(function (campaignPrepid) {
          const campaignData = {prepid: campaignPrepid};
          $http({method: 'PUT', url: 'restapi/campaigns/save/', data: campaignData}).success(function (data, status) {
            if (data.results) {
              $window.location.href = "edit?db_name=campaigns&query=" + campaignPrepid;
            } else {
              $scope.openErrorModal(campaignPrepid, data['message']);
              $scope.setSuccess(false, status);
            }
          }).error(function (data, status) {
            $scope.openErrorModal(campaignPrepid, data['message']);
            $scope.setSuccess(false, status);
          });
        })
      };
    }
  ]
);
