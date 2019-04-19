<?php /* CLASS AUTORSS V 1.0 Autor : Roberto Aleman Email : ventics@gmail.com
This class is to automatic read and show  the files in a directory as rss 2.0 version,
only configure the config.php file with de globals vars and xml and rss versions,
the directory path and put config, callfile and autorss in directory to show at rss channel.
i apply to read a folder of images and show images gallery to rss channel with feedreader. Enjoy!!
GENERAL PUBLIC LICENCE , GPL */
class autorss
{
	public function show($document_type,$path,$xmlversion,$encoding,$rssversion,$atomversion,$title,$homelink,$description,$language,$lastupdate,$callfile,$generator,$permalink,$category)
	{
		header($document_type); // define document type header
		$dir=getcwd(); // get directory where is script
		$dr=@opendir($dir); //asign path to $dr var
		if(!$dr){
			echo "<error/>"; //if error, stop! and exit!
			exit;
		return;
		}
		else
		{ //begin write xml file whith vars
echo "<?xml version='".$xmlversion."' encoding='".$encoding."'?>
<rss version='".$rssversion."' xmlns:atom='".$atomversion."'>
<channel>
<atom:link href='".$path."' rel='self' type='application/rss+xml'/>
<title>".$title."</title>
<link>".$homelink."</link>
<description>".$description."</description>
<language>".$language."</language>
<lastBuildDate>".$lastupdate."</lastBuildDate>
<generator>".$generator."</generator>";
			while (($archivo = readdir($dr)) !== false)
		{
				if($archivo!="autorss.php" AND $archivo!="." AND $archivo!=".." AND $archivo!="error_log" AND $archivo!=$callfile )
				{
				clearstatcache() ;
						$info = lstat($archivo);

echo "
<item>
<title>".$path.$archivo."</title>
<link>".$path.$archivo."</link>
<pubDate>".date('r' ,$info[9])."</pubDate>
<description><![CDATA[<img src=".$path.$archivo."></img><br/>File Size :".$info[7]." Bytes, Modified:".date('r',$info[9])."]]></description>
<guid isPermaLink='".$permalink."'>".$path.$archivo."</guid>
<category domain='".$path."'>".$category."</category>
</item>";
				}
		}
echo "</channel></rss>";
			closedir($dr);
			return;
		}
	}
}
?>