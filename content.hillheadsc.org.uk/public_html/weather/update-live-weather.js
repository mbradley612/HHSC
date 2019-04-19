/*
* Look at http://simple2kx.com/use-jquery-ajax-and-json-format-to-update-multiple-fields-on-webpage/
*/






jQuery(document).ready(function () {
	// check if we have an element with id of liveweather
	// the liveweather HTML elements should be wrapper in a div
	// of id "liveweather"
	if($('#liveweather').length){

		
		updateWeather()
		
		setInterval(function(){
		 updateWeather() // this will run after every 5 seconds
		}, 5000);
	}
});

function updateWeather() {
	jQuery.getJSON("https://content.hillheadsc.org.uk/weather/current_weather.php", { } )
	  .done(function( json ) {

	    jQuery("#windSpeed").text(json.windSpeed.value);
  	    jQuery("#mobWindSpeed").text(json.windSpeed.value);

	    jQuery("#windGust").text(json.windGust.value);
	    jQuery("#mobWindGust").text(json.windGust.value);

		 jQuery("#windDir").text(json.windDir.value);
		 jQuery("#mobWindDir").text(json.windDir.value);


		 jQuery("#outTemp").text(json.outTemp.value);
		 jQuery("#mobOutTemp").text(json.outTemp.value);


		 observationMoment = moment(json.timestamp)
		 jQuery("#timestamp").text(observationMoment.format('DD/MM/YY HH:mm:ss'));


		 jQuery("#pressure").text(json.pressure.value);
		 jQuery("#mobPressure").text(json.pressure.value);



	  })
	  .fail(function( jqxhr, textStatus, error ) {
	    var err = textStatus + ", " + error;
	    console.log( "Request Failed: " + err );
	});


}
