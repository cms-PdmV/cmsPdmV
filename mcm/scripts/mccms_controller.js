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

      $scope.actionPrompt = function(action, prepid) {
        $scope.openIsSureModal($scope.dbName, prepid, action, function (database, prepid, action) {
          $scope.objectAction(action, prepid);
        });
      }

      $scope.objectAction = function (action, prepid) {
        $http({ method: 'GET', url: 'restapi/mccms/' + action + '/' + prepid }).success(function (data, status) {
          if (data.results) {
            $scope.getData();
          } else {
            $scope.openErrorModal(prepid.split('?')[0], data['message'])
          }
        }).error(function (data, status) {
          $scope.openErrorModal(prepid.split('?')[0], data['message'])
        });
      };

      $scope.approve_all_requests = function (mccm_prepid) {
        var requests = '';
        for (index in $scope.result) {
          if ($scope.result[index].prepid == mccm_prepid) {
            var generated_chains = $scope.result[index].generated_chains
            for (var chain in generated_chains) {
              for (index_requests in generated_chains[chain]) {
                requests += generated_chains[chain][index_requests] + ",";
              }
            }
            break;
          }
        }
        if (requests != '') {
          requests = requests.slice(0, -1);
          $scope.approve_gen_request(requests);
        }
      };

      $scope.get_requests_size = function (dict) {
        var size = 0;
        for (var chain in dict) {
          size += dict[chain].length;
        }
        return size;
      };

      $scope.is_generated_chains_empty = function (dict) {
        for (var chain in dict) {
          return true;
        }
        return false;
      };

      $scope.redirect_chained_request = function (ticket_prepid) {
        window.location = "chained_requests?from_ticket=" + ticket_prepid;
      }

      $scope.approve_gen_request = function (prepids) {
        $http({ method: 'POST', url: 'restapi/requests/approve', data: prepids }).success(function (data, status) {
          if (!$scope.isArray(data)) {
            data = [data];
          }
          alert_text = "";
          for (index in data) {
            alert_text += data[index].prepid + ":\n";
            if (data[index].results) {
              alert_text += "Everything went fine\n";
            }
            else {
              alert_text += data[index].message + "\n";
            }
          }
          alert(alert_text);
        }).error(function (data, status) {
          alert("Something went wrong");
        });
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
        $http.get("restapi/users/get_pwg/" + $scope.user.name).then(function (data) {
          const pwgs = data.data.results;
          $modal.open({
            templateUrl: 'createTicketModal.html',
            controller: function ($scope, $modalInstance, $window, $http, pwgs, selectedPwg, errorModal, setSuccess) {
              $scope.vars = {'pwgs': pwgs, 'selectedPwg': selectedPwg};
              $scope.save = function () {
                const ticketData = {'pwg': $scope.vars.selectedPwg};
                $http({method: 'PUT', url: 'restapi/mccms/save/', data: ticketData}).success(function (data) {
                  if (data.results) {
                    $window.location.href = "edit?db_name=mccms&query=" + data.prepid;
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
              errorModal: function () { return $scope.openErrorModal; },
              setSuccess: function () { return $scope.setSuccess; },
            }
          })
        });
      };

      $scope.openGenerateReserveModal = function (mccm) {
        $modal.open({
          templateUrl: 'reserveGenerateReserveModal.html',
          controller: function ($scope, $modalInstance, $http, mccm, objectAction) {
            $scope.chains = mccm.chains.map(x => Object({'prepid': x, 'campaigns': [[undefined, '<No limit>']], 'campaign': undefined}))
            $scope.vars = {'skipExisting': false, 'allowDuplicates': false};
            let chainedCampaigns = [...$scope.chains.map(x => x.prepid)]
            for (let chainedCampaignPrepid of chainedCampaigns) {
              $http.get("restapi/chained_campaigns/get/" + chainedCampaignPrepid).then(function (data) {
                let chainedCampaign = data.data.results;
                for (let chain of $scope.chains) {
                  if (chainedCampaign && chain.prepid == chainedCampaign.prepid) {
                    chain.campaigns = [[undefined, '<No limit>']].concat(chainedCampaign.campaigns.map(x => [x[0], x[0]]));
                    chain.campaign = chain.campaigns[0][0];
                  }
                }
              });
            }
            $scope.confirm = function () {
              let query = '?reserve=true';
              let limits = $scope.chains.map(x => x.campaign);
              if (limits.filter(x => x != undefined).length) {
                query += '&limit=' + limits.map(x => x ? x : '').join(',');
              }
              if ($scope.vars.skipExisting) {
                query += '&skip_existing=true';
              }
              if ($scope.vars.allowDuplicates) {
                query += '&allow_duplicates=true';
              }
              objectAction('generate', mccm.prepid + query);
              $modalInstance.close();
            };
            $scope.cancel = function () {
              $modalInstance.dismiss();
            };
          },
          resolve: {
            mccm: function () { return mccm; },
            objectAction: function() { return $scope.objectAction; },
          }
        });
      };
    }
  ]);
