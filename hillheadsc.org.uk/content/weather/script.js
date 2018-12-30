// Load the Visualization API and the piechart package.
google.charts.load('current', {'packages':['corechart']});

//get json data

xhttp = new XMLHttpRequest();

dayUrl = '/weewx/day.json';

xhttp.onreadystatechange = function(){
  if (this.readyState == 4 && this.status == 200) { // Set a callback to run when the Google Visualization API is loaded.
    r=this.responseText;
    //console.log(r);

    latestArchiveData = JSON.parse(r).latestArchiveRecord;
    windJsonData = JSON.parse(r).dayWindData;
    pressureJsonData =JSON.parse(r).dayPressureData;
    outTemp = JSON.parse(r).dayOutTemp;
    inTemp =	JSON.parse(r).dayInTemp;

    updateLatestArchive();


    google.charts.setOnLoadCallback(drawCharts);
  }
}

xhttp.open("GET",dayUrl);
xhttp.send();

function updateLatestArchive() {

  jQuery("#latestArchiveDateTime").text(latestArchiveData.dateTime);
  jQuery("#latestArchiveWindSpeed").text(latestArchiveData.windSpeed);
  jQuery("#latestArchiveWindGust").text(latestArchiveData.windGust);
  jQuery("#latestArchiveWindDirection").text(latestArchiveData.windDirectionOrdinal);
  jQuery("#latestArchivePressure").text(latestArchiveData.pressure);
};

function drawCharts() { //Create table data

    windData = new google.visualization.DataTable();
    windData.addColumn("datetime","Time");
    windData.addColumn("number","Average Speed (knots)");
    windData.addColumn("number","Gust Speed (knots)");

    dirData = new google.visualization.DataTable();
    dirData.addColumn("datetime","Time");
    dirData.addColumn("number","Direction");

    pressureData = new google.visualization.DataTable();
    pressureData.addColumn("datetime","Time");
    pressureData.addColumn("number","Pressure (mbars)");

    windJsonData.forEach(function(x){
      date = new Date(x[0]);
      windData.addRow([date,x[1],x[2]]); dirData.addRow([date,x[3]]);
    })

    pressureJsonData.forEach(function(x){
      date = new Date(x[0]);
      pressureData.addRow([date, x[1]]);
    })

    var windOptions = { title: 'Wind Speed',
    curveType: 'function',
    legend: {
    position: 'bottom' },
    hAxis:{ format:"HH:mm" } };

    dirOptions = {
       title: 'Wind Direction',
       curveType: 'function',
       legend: {
         position: 'bottom'
       },
       hAxis:{
         format:"HH:mm"
       },
       vAxis:{
         viewWindow:{
           min:0,
           max:360
         }
       }
     };

    pressureOptions = {
      title: 'Pressure',
      curveType: 'function',
      legend: {
        position: 'bottom'
      },
      hAxis:{
        format:"HH:mm"
      },
    };

    var windChart = new
      google.visualization.LineChart(document.getElementById('wind_speed_chart'));

    var dirChart = new
      google.visualization.LineChart(document.getElementById('wind_direction_chart'));

    var pressureChart = new
      google.visualization.LineChart(document.getElementById('pressure_chart'));

    windChart.draw(windData, windOptions);

    dirChart.draw(dirData, dirOptions);

    pressureChart.draw(pressureData, pressureOptions);

  }
