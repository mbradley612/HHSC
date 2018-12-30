<?php

/* Get data from a URL */
function get_data($url, $alternate_filename) {
	$ch = curl_init();
	$timeout = 5;
	curl_setopt($ch, CURLOPT_URL, $url);
	curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
	curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, $timeout);
	$data = curl_exec($ch);
	# if we couldn't get hold of the resource from the URL use the file
	if(curl_errno($ch) ){
		$data = file_get_contents($alternate_filename);
	}
	curl_close($ch);
	return $data;
}

# Try and get the data from the URL. If not, default to a local file.
#
$result = get_data("http://hillheadsc.dyndns.biz:14580/current_weather.php",
	__DIR__ . "/wp-content/plugins/byteweewx/data/current_weather.json");
header("Cache-Control: no-cache, must-revalidate");

header('Content-Type: application/json');

echo $result
?>
