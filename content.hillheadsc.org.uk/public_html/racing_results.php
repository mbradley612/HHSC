<?php
$directoryToScan = "racing_results";

define('WEBSITE', "https://content.hillheadsc.org.uk/racing_results");

$json_array = array();

// Open a known directory, and proceed to read its contents
foreach(glob($directoryToScan, GLOB_ONLYDIR) as $folders) 
{
    //get total number of jpg files in each folder
    $num_files = count(glob("$folders/*.jpg"));
    $totalFiles = (string)$num_files;

    //find a php file in each folder and get its realpath
    foreach (glob("$folders/*.json") as $filename) {

        $turl = WEBSITE.$filename;
        $url = str_replace("\/", "\\", $turl);
        //echo($url);
    }

    //get date on which each folder was created.
    $fileDate = date("mdY", filectime($folders));   

    $json_Array[] = array('name'=>$folders,'images'=>$num_files,'url'=>$url,'uploaddate'=>$fileDate);

}

echo(json_encode($json_Array));

?>