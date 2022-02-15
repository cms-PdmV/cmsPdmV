angular.module('mcmApp').controller('mccmController',
  ['$scope', '$http', '$uibModal',
    function mccmController($scope, $http, $uibModal) {

      $scope.columns = [
        { text: 'Prepid', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Meeting', select: true, db_name: 'meeting' },
        { text: 'Requests', select: true, db_name: 'requests' },
        { text: 'Chains', select: true, db_name: 'chains' },
      ];

      $scope.setDatabaseInfo('mccms', $scope.columns);
      $scope.allRequestsApproved = {};

      $scope.cancelTicket = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/mccms/cancel',
                             data: {'prepid': prepid}});
      };

      $scope.generate = function (prepid) {
        let message = 'Are you sure you want to generate chained requests from ' + prepid + '?';
        $scope.objectAction(message,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/mccms/generate',
                             data: {'prepid': prepid}});
      };

      $scope.recalculate = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/mccms/recalculate',
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
          $http({ method: 'GET', url: 'restapi/mccms/check_all_approved/' + prepid }).then(function (data) {
            $scope.allRequestsApproved[prepid] = data.data.results;
            if (data.message) {
              $scope.openErrorModal(prepid, data.message);
            }
            delete $scope.actionMessage[prepid];
          }, function (data) {
            delete $scope.actionMessage[prepid];
            errorModal(data.data.prepid, data.data.message);
          });
        }
      };

      $scope.openTicketCreator = function () {
        const pwgs = $scope.user.pwgs;
        $uibModal.open({
          templateUrl: 'createTicketModal.html',
          controller: function ($scope, $uibModalInstance, $window, $http, pwgs, errorModal) {
            $scope.vars = {'pwgs': pwgs, 'selectedPwg': pwgs[0]};
            $scope.save = function () {
              const ticketData = {'pwg': $scope.vars.selectedPwg};
              $http({method: 'PUT', url: 'restapi/mccms/save/', data: ticketData}).then(function (data) {
                if (data.data.results) {
                  $window.location.href = "edit?db_name=mccms&prepid=" + data.data.prepid;
                } else {
                  errorModal(data.data.prepid, data.data.message);
                }
              }, function (data,) {
                errorModal(data.data.prepid, data.data.message);
              });
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            pwgs: function () { return pwgs; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };
      $scope.openTicketChainGenerator = function (mccm) {
        $uibModal.open({
          templateUrl: 'generateChainsModal.html',
          controller: function ($scope, $uibModalInstance, $http, mccm, errorModal) {
            $scope.vars = {'prepid': mccm.prepid,
                           'skipExisting': false,
                           'allowDuplicates': false};
            $scope.confirm = function () {
              const ticketData = {'prepid': mccm.prepid,
                                  'skip_existing': $scope.vars.skipExisting,
                                  'allow_duplicates': $scope.vars.allowDuplicates};
              $http({method: 'POST', url: 'restapi/mccms/generate', data: ticketData}).then(function (data) {
                if (data.data.results) {
                  console.log('Get data')
                } else {
                  errorModal(data.data.prepid, data.data.message);
                }
              }, function (data, status) {
                errorModal(data.data.prepid, data.data.message);
              });
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
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
