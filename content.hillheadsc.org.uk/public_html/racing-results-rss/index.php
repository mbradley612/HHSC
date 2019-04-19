<?php
/* Class AutoRSS v 1.0
Autor : Roberto Aleman
Email : ventics@gmail.com
General Public Licence , GPL */
// call to auto rss class 
require_once("autorss.php");
//create new object
$newrss = new autorss();
/* example of use and orden of vars : 
$document_type : document type, default : Content-type:text/xml
$path: absolute path of your folder, example path : http://ventics.com/autorss/
$xmlversion : XML file version , default : 1.0
$encoding : encondig : default :utf-8
$rssversion : RSS version, default : 2.0
$atomversion : ATOM version , default : http://www.w3.org/2005/Atom
$title: Title of your RSS autoengine channel : example: CLASS AUTORSS
$homelink: Link os your RSS autoengine channerl: example: http://www.ventics.com/autorss/ 
$description: description about your autoengine channel : example : CLASS AUTORSS TEST by ROBERTO ALEMAN
$language: language of xml file definition , ISO format is require, example: en-us
$lastupdate: Date of last update xml file autoengine, example : Sun, 31 May 2009 09:41:01 GMT
$callfile: file to calle autorss class, example : index.php
$generator: channel generator
$permalink: if permalink? true or false
$category: category of each file

change log : 

22/06/09: Add tags : generator in channel definition and pubDate, isPermalink, category domain in item definition 
and add lstat option to get info about file, where:
$info[7],  size in bytes 
$info[9], 9 mtime last modified (Unix time)

*/
//send parameters and engine rss
$newrss->show("Content-type:text/xml","https://content.hillheadsc.org.uk/racing_results/", "1.0","utf-8","2.0","http://www.w3.org/2005/Atom","CLASS AUTORSS","https://content.hillheadsc.org.uk/racing_results/","HHSC Racing results","en-us","Sun, 31 May 2009 09:41:01 GMT","index.php","CLASS AUTORSS","true","Racing results");
?>
