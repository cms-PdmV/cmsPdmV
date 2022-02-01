angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'Prepid', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Meeting', select: true, db_name: 'meeting' },
        { text: 'Requests', select: true, db_name: 'requests' },
        { text: 'Chains', select: true, db_name: 'chains' },
      ];

      $scope.dbName = "mccms";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.allRequestsApproved = {};

      $scope.cancelTicket = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/' + $scope.dbName + '/cancel',
                             data: {'prepid': prepid}});
      };

      $scope.generate = function (prepid) {
        let message = 'Are you sure you want to generate chained requests from ' + prepid + '?';
        $scope.objectAction(message,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/' + $scope.dbName + '/generate',
                             data: {'prepid': prepid}});
      };

      $scope.recalculate = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/' + $scope.dbName + '/recalculate',
                             data: {'prepid': prepid}});
      };

      $scope.isArray = function (obj) {
        return angular.isArray(obj)
      };

      $scope.findToken = function (tok) {
        $window.location.href = "requests?&tags=" + tok.value
      };

      $scope.generateAllRequests = function (input_data) {
        var tmp_url = [];
        if (input_data.length > 0) {
          _.each(input_data, function (elem) {
            if (_.isArray(elem)) {
              tmp_url.push(elem[0] + "," + elem[1]);
            } else {
              tmp_url.push(elem);
            }
          });
          return tmp_url.join(";");
        } else {
          return "";
        }
      };

      $scope.checkIfAllApproved = function (prepid) {
        for (i = 0; i < $scope.result.length; i++) {
          if ($scope.result[i].prepid == prepid) {
            // if already present. remove it to redisplay properly
            if (_.keys($scope.allRequestsApproved).indexOf(prepid) == -1 || $scope.allRequestsApproved[prepid] == undefined) {
              $http({ method: 'GET', url: 'restapi/mccms/check_all_approved/' + prepid }).success(function (data, status) {
                $scope.allRequestsApproved[prepid] = data.results;
                if (data.message) {
                  alert(data.message);
                }
              }).error(function (status) {
                alert('Cannot get information for ' + prepid);
              });
            }
          }
        }
      };

      $scope.openTicketCreator = function () {
        const pwgs = $scope.user.pwgs;
        $modal.open({
          templateUrl: 'createTicketModal.html',
          controller: function ($scope, $modalInstance, $window, $http, pwgs, errorModal) {
            $scope.vars = {'pwgs': pwgs, 'selectedPwg': pwgs[0]};
            $scope.save = function () {
              const ticketData = {'pwg': $scope.vars.selectedPwg};
              $http({method: 'PUT', url: 'restapi/mccms/save/', data: ticketData}).success(function (data) {
                if (data.results) {
                  $window.location.href = "edit?db_name=mccms&query=" + data.prepid;
                } else {
                  errorModal(data.prepid, data['message']);
                }
              }).error(function (data, status) {
                errorModal(data.prepid, data['message']);
              });
              $modalInstance.close();
            };
            $scope.close = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            pwgs: function () { return pwgs; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };
    }
  ]);
