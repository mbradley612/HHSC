// Load the Visualization API and the piechart package.
google.charts.load('current', {'packages':['corechart']});


//get json data
xhttp = new XMLHttpRequest();
url = '/weewx/day-wind.json';

xhttp.onreadystatechange = function(){
    if (this.readyState == 4 && this.status == 200) {
        // Set a callback to run when the Google Visualization API is loaded.
	r=this.responseText;
	//console.log(r);

	jsonData = JSON.parse(r).dayWindData;
	console.log(jsonData);
	google.charts.setOnLoadCallback(drawChart);        
    }
}

xhttp.open("GET",url);
xhttp.send();

function drawChart() {
    //Create table data

    windData = new google.visualization.DataTable();
    windData.addColumn("datetime","Time");
    windData.addColumn("number","Average Speed");
    windData.addColumn("number","Gust Speed");

    dirData = new google.visualization.DataTable();
    dirData.addColumn("datetime","Time");
    dirData.addColumn("number","Direction");
    
    
    jsonData.forEach(function(x){
	date = new Date(x[0]);
	windData.addRow([date,x[1],x[2]]);
	dirData.addRow([date,x[3]]);
    })
    var windOptions = {
        title: 'Wind Speed',
        legend: { position: 'bottom' },
	hAxis:{
	    format:"hh:mm"
	}
    };

    dirOptions = {
	title: 'Wind Direction',
	legend: {position: 'bottom'},
	hAxis:{
	    format:"hh:mm"
	},
	vAxis:{
	    viewWindow:{
		min:0,
		max:360
	    }
	}
    };

    

    var windChart = new google.visualization.LineChart(document.getElementById('wind_chart'));

    var dirChart = new google.visualization.LineChart(document.getElementById('dir_chart'));

    
    windChart.draw(windData, windOptions);

    dirChart.draw(dirData, dirOptions);
}
