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
        return Array.isArray(obj)
      };

      $scope.requestRange = function (requests) {
        let range = [];
        for (let entry of requests) {
          if ($scope.isArray(entry)) {
            if (entry.length == 1) {
              range.push(entry[0]);
            } else if (entry.length == 2) {
              range.push(entry[0] + "," + entry[1]);
            }
          } else {
            range.push(entry);
          }
        }
        return range.join(";");
      };

      $scope.checkApproved = function (prepid) {
        if ($scope.allRequestsApproved[prepid]) {
          delete $scope.allRequestsApproved[prepid];
        } else {
          $scope.actionMessage[prepid] = 'loading';
          $http({ method: 'GET', url: 'restapi/mccms/check_all_approved/' + prepid }).success(function (data, status) {
            $scope.allRequestsApproved[prepid] = data.results;
            if (data.message) {
              $scope.openErrorModal(prepid, data.message);
            }
            delete $scope.actionMessage[prepid];
          }).error(function (data, status) {
            delete $scope.actionMessage[prepid];
            errorModal(data.prepid, data['message']);
          });
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
      $scope.openTicketChainGenerator = function (mccm) {
        $modal.open({
          templateUrl: 'generateChainsModal.html',
          controller: function ($scope, $modalInstance, $http, mccm, errorModal) {
            $scope.vars = {'prepid': mccm.prepid,
                           'skipExisting': false,
                           'allowDuplicates': false};
            $scope.confirm = function () {
              const ticketData = {'prepid': mccm.prepid,
                                  'skip_existing': $scope.vars.skipExisting,
                                  'allow_duplicates': $scope.vars.allowDuplicates};
              $http({method: 'POST', url: 'restapi/mccms/generate', data: ticketData}).success(function (data) {
                if (data.results) {
                  console.log('Get data')
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
            mccm: function () { return mccm; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        });
      };
    }
  ]);
