
angular.module('testApp').controller('notificator',
  ['$scope', '$http', '$location', '$window',
  function notificator($scope, $http, $location, $window){
    $scope.show_notifications = false;
    $scope.unseen = -1;
    $scope.notification_numbers = {};
    $scope.notifications = {};
    $scope.sorted_groups = [];
    $scope.display_notifications = false;
    $scope.overlay_height = "0%";
    $scope.overlay_title = "";
    $scope.overlay_message = "";

    $scope.checkNotifications = function(){
      var promise = $http.get("restapi/notifications/check");
      promise.then(function(data) {
            $scope.notification_numbers = data.data;
            if ($scope.unseen !== -1 && $scope.unseen < $scope.notification_numbers.unseen){
              $scope.playAudio();
            }
            $scope.unseen = $scope.notification_numbers.unseen;
            delete $scope.notification_numbers.unseen;
            $scope.sorted_groups = Object.keys($scope.notification_numbers).sort();
        }, function() {
            alert("Error checking notifications");
        });
    }

    $scope.playAudio = function() {
        var audio = new Audio('scripts/notif.mp3');
        audio.play();
    };

    $scope.showActions = function(object_type, notification_id){
      window.location = object_type + "?from_notification=" + notification_id;
    }

    $scope.showGroup = function(group){
      if($scope.notifications.hasOwnProperty(group)){
        $scope.notifications[group]['is_selected'] = !$scope.notifications[group]['is_selected'];
      } else{
        $scope.fetchNotifications(group);
      }
    }

    $scope.fetchNotifications = function(group){
      var page = $scope.notifications.hasOwnProperty(group) ? $scope.notifications[group].page : 0;
      var groupAux = group == 'All' ? '*' : group
      var promise = $http.get("restapi/notifications/fetch?page=" + page + "&group=" + groupAux);
      promise.then(function(data) {
            if(!$scope.notifications.hasOwnProperty(group)){
              $scope.notifications[group] = {};
              $scope.notifications[group]['page'] = 0;
              $scope.notifications[group]['is_selected'] = true;
              $scope.notifications[group]['more_to_fetch'] = true;
              $scope.notifications[group]["notifications"] = [];
            }
            $scope.notifications[group]["notifications"] = $scope.notifications[group]["notifications"].concat(data.data.notifications);
            $scope.notifications[group]['page'] += 1;
            if (data.data.notifications.length < 10) {
              $scope.notifications[group]['more_to_fetch'] = false;
            }
        }, function() {
            alert("Error fetching notifications");
        });
    }

    $scope.saveSeenNotification = function(notification_id){
      $http({method:'POST', url:"restapi/notifications/seen", data: {"notification_id": notification_id}}).success(function(data,status){
      }).error(function(status){
      });
    }

    $scope.showNotification = function(notification, group){
      if(!notification.seen){
        notification.seen = true;
        $scope.saveSeenNotification(notification._id);
        if($scope.notifications.hasOwnProperty('All')){
          for(var index in $scope.notifications.All.notifications){
            if($scope.notifications.All.notifications[index]._id == notification._id){
              $scope.notifications.All.notifications[index].seen = true;
            }
          }
        }
        $scope.unseen -= 1;
      }
      $scope.overlay_height = '100%';
      $scope.overlay_message = notification.message;
      $scope.overlay_title = notification.title;
    }

    $scope.displayNotifications = function(){
      $scope.display_notifications = !$scope.display_notifications;
      if(!$scope.display_notifications){
        $scope.notifications = {};
        $scope.check_timer = setInterval($scope.checkNotifications, 60000);
      } else{
        clearInterval($scope.check_timer);
      }
    }
    $scope.checkNotifications();
    $scope.check_timer = setInterval($scope.checkNotifications, 60000);
  }
]);