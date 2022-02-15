angular.module('mcmApp').controller('batchController',
  ['$scope',
    function batchController($scope) {
      $scope.columns = [
        { text: 'PrepId', select: true, db_name: 'prepid' },
        { text: 'Actions', select: true, db_name: '' },
        { text: 'Status', select: true, db_name: 'status' },
        { text: 'Requests', select: true, db_name: 'requests' },
        { text: 'Notes', select: true, db_name: 'notes' },
      ];
      $scope.setDatabaseInfo('batches', $scope.columns);

      $scope.announce = function(prepid) {
        let prepids = prepid == 'selected' ? $scope.selected_prepids : prepid;
        let message = 'Are you sure you want to announce ' + $scope.promptPrepid(prepids) + '?';
        $scope.objectAction(message,
                            prepids,
                            {method: 'POST',
                             url: 'restapi/batches/announce',
                             data: {'prepid': prepids}})
      }

      $scope.generateAllRequests = function(requests) {
        return requests.map(x => x[0]).join(',')
      }

    }
  ]
);
