function resultsCtrl($scope, $http){
	// GET all news
    var promise = $http.get("restapi/news/getall/5");
    promise.then(function(data){
      $scope.news = data.data;
      var new_marquee = document.createElement('marquee');
      var news_banner = document.getElementById("news_banner");
      new_marquee.setAttribute('direction','left');
      new_marquee.setAttribute('behavior','scroll');
      //var marquee = body = document.getElementById("news_spammer");

      // for(i=1;i<=10;i++){ //test samples
      // var test1 ={};
      // test1.author = "anorkus";
      // test1.subject = "spammer news";
      // test1.text = "a spammer new to be displayed in custom fasion";
      // test1.date = "2013-0"+i+"-16-10-3"+i+"";
      // $scope.news.push(test1);
      // }
      var sorted_news = _.sortBy($scope.news, function(elem){ //sort news array by date
        return elem.date;
      });
      //changed in the rest api directly
      sorted_news.reverse(); //lets reverse it so newest new is in beggining of array
      sorted_news = sorted_news.splice(0,5); //take only 5 newest and best news
      _.each(sorted_news, function(v){
        new_new = "<span> <i class='icon-globe'></i><b>"+v.subject+"</b>  <i>"+v.date+" </i></span>";
        new_marquee.innerHTML += new_new;
      });
      news_banner.appendChild(new_marquee);
      news_banner.appendChild(new_marquee);
      console.log($scope.news);
    },function(data){
      alert("Error getting news. Error: "+data.status);
    });
// Endo of news!
};