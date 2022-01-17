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
      $scope.actionMessage = {};
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.setLoading = function(prepids, loading) {
        for (let prepid of prepids) {
          $scope.actionMessage[prepid] = loading ? 'loading' : '';
        }
      }

      $scope.nextStatus = function (prepid) {
        $scope.setLoading([prepid], true);
        $http({ method: 'POST', url: 'restapi/' + $scope.dbName + '/status/' + prepid }).success(function (data, status) {
          $scope.actionMessage[prepid] = data.results ? 'OK' : data.message;
          if (data.results) {
            $scope.getData();
          }
        }).error(function (data, status) {
          $scope.openErrorModal(prepid, data['message']);
          $scope.setLoading([prepid], false);
        });
      };

      $scope.openRequestCreator = function (campaignPrepid) {
        const pwgs = $scope.user.pwgs;
        $modal.open({
          templateUrl: 'createRequestModal.html',
          controller: function ($scope, $modalInstance, $window, $http, pwgs, selectedPwg, prepid, errorModal, setSuccess) {
            $scope.vars = {'prepid': prepid, 'pwgs': pwgs, 'selectedPwg': selectedPwg};
            $scope.save = function () {
              const requestData = {member_of_campaign: $scope.vars.prepid, pwg: $scope.vars.selectedPwg};
              $http({method: 'PUT', url: 'restapi/requests/save/', data: requestData}).success(function (data) {
                if (data.results) {
                  $window.location.href = "edit?db_name=requests&query=" + data.prepid;
                } else {
                  errorModal(data.prepid, data['message']);
                  setSuccess(false, status);
                }
              }).error(function (data, status) {
                errorModal(data.prepid, data['message']);
                setSuccess(false, status);
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
            errorModal: function () { return $scope.openErrorModal; },
            setSuccess: function () { return $scope.setSuccess; },
          }
        })

      };
    }
  ]
);