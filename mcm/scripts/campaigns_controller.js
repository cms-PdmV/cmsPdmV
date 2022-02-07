angular.module('testApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'CMSSW Release', select: true, db_name: 'cmssw_release' },
        { text: 'Energy', select: true, db_name: 'energy' },
        { text: 'Next', select: true, db_name: 'next' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.dbName = "campaigns";
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);

      $scope.nextStatus = function (prepid) {
        $scope.objectAction(undefined,
                            [prepid],
                            {method: 'POST',
                             url: 'restapi/' + $scope.dbName + '/status',
                             data: {'prepid': prepid}});
      };

      $scope.openRequestCreator = function (campaignPrepid) {
        const pwgs = $scope.user.pwgs;
        $modal.open({
          templateUrl: 'createRequestModal.html',
          controller: function ($scope, $modalInstance, $window, $http, pwgs, prepid, errorModal) {
            $scope.vars = {'prepid': prepid, 'pwgs': pwgs, 'selectedPwg': pwgs[0]};
            $scope.save = function () {
              const requestData = {member_of_campaign: $scope.vars.prepid, pwg: $scope.vars.selectedPwg};
              $http({method: 'PUT', url: 'restapi/requests/save/', data: requestData}).success(function (data) {
                if (data.results) {
                  $window.location.href = "edit?db_name=requests&prepid=" + data.prepid;
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
            prepid: function () { return campaignPrepid; },
            errorModal: function () { return $scope.openErrorModal; },
          }
        })
      };
    }
  ]
);