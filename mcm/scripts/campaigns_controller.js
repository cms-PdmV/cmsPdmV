angular.module('mcmApp').controller('campaignController',
  ['$scope', '$uibModal',
    function campaignController($scope, $uibModal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'CMSSW Release', select: true, db_name: 'cmssw_release' },
        { text: 'Energy', select: true, db_name: 'energy' },
        { text: 'Next', select: true, db_name: 'next' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.setDatabaseInfo('campaigns', $scope.columns);

      $scope.nextStatus = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/' + $scope.database + '/status',
                             data: {'prepid': prepid}});
      };

      $scope.openRequestCreator = function (campaignPrepid) {
        $uibModal.open({
          templateUrl: 'createRequestModal.html',
          controller: function ($scope, $uibModalInstance, $window, $http, pwgs, campaignPrepid, errorModal) {
            $scope.vars = {'pwgs': pwgs, 'selectedPwg': pwgs[0]};
            $scope.save = function () {
              let requestData = {'member_of_campaign': campaignPrepid,
                                 'pwg': $scope.vars.selectedPwg};
              $http({method: 'PUT', url: 'restapi/requests/save/', data: requestData}).then(function (data) {
                if (data.data.results) {
                  $window.location.href = "edit?db_name=requests&prepid=" + data.data.prepid;
                } else {
                  errorModal(data.data.prepid, data.data.message);
                }
              }, function (data) {
                console.log(data)
                errorModal(data.data.prepid, data.data.message);
              });
              $uibModalInstance.close();
            };
            $scope.close = function () {
              $uibModalInstance.dismiss();
            };
          },
          resolve: {
            pwgs: function () { return $scope.user.pwgs; },
            campaignPrepid: function () { return campaignPrepid; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };
    }
  ]
);