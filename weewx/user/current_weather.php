<?php
$mem = new Memcached();
$mem->addServer("127.0.0.1", 11211);

$result = $mem->get("current_weather");

header('Content-Type: application/json');

echo $result
?>
