angular.module('mcmApp').controller('resultsCtrl',
  ['$scope', '$http', '$location', '$window', '$modal',
    function resultsCtrl($scope, $http, $location, $window, $modal) {

      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.dbName = "batches";
      $scope.actionMessage = {};
      $scope.setDatabaseInfo($scope.dbName, $scope.columns);
      $scope.setLoading = function (prepids, loading) {
        for (let prepid of prepids) {
          $scope.actionMessage[prepid] = loading ? 'loading' : '';
        }
      }

      $scope.announce = function(prepid) {
        let prepids = [prepid];
        let message = 'Are you sure you want to announce ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/batches/announce',
                             data: {'prepid': prepids}})
      }

    }
  ]
);
