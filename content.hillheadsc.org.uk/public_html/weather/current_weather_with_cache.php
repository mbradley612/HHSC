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
# set the http headers
header("Cache-Control: no-cache, must-revalidate");

header('Content-Type: application/json');

header('Access-Control-Allow-Origin: *');



# First try to get the data from the memcache cache

# NB this is using Memcache which is deprecated and not
# supported on PHP 7. Default ubuntu install is for PHP 7. 
#
# Probably time to upgrade to memcached,
# but need to check support on TSO.

$mem = new Memcache();
$mem->connect("10.168.1.55", 11211);

$result = $mem->get("current_weather");

if ($result) {
	# if we get a result back from the cache write it to the client
	echo $result;

} else {
	# otherwise, retrieve from one of our two sources


	# Try and get the data from the URL. If not, default to a local file.
	#
	$result = get_data("http://hillheadsc.dyndns.biz:14580/current_weather.php",
		__DIR__ . "/wp-content/plugins/byteweewx/data/current_weather.json");




	# and write it to the memcache with an expiry of 10 seconds
	$mem->set("current_weather",$result,0,10);

	# finally write it to the client

	echo $result;
}
?>
