#!/usr/bin/perl

use strict;
use CGI;
use DBI;
use JSON;

my $dbhost = "";   #Server or Hostname of your MySQL Server
my $database = "led_control";     #Database to use
my $dbuser = "magfest";       		#Username for the MySQL Server
my $dbpass = "";       	#Password for the MySQL Server

my $dbh = DBI->connect("DBI:mysql:database=$database;host=$dbhost","$dbuser", "$dbpass",{'RaiseError' => 1});


my $query = new CGI;
my $action = $query->param("action");

if (defined($action) && $action eq "GETINFO")
{
	print $query->header();
	my $lightid = $query->param("lightid");
	my $version_num = $query->param("version");
	my $No_Update = 0;
	$No_Update = 1 if ($query->param("noupdate") eq "true");

	if (!defined($lightid))
	{
		my %error = ('ERROR' => 'Unknown Light Id');
		my $json = encode_json(\%error);
		print "$json\n";
		exit;
	}
	my $session_ip = $ENV{REMOTE_ADDR};

	my $sql = $dbh->prepare("SELECT id, light, light_ip, switch, switch_ip, snmp, bandwidth FROM led_lights WHERE light = ?");
	$sql->execute($lightid);

	my $row = $sql->fetchrow_hashref();

	if ($row->{'id'} == "")
	{
		my %error = ('ERROR' => 'No Light Id Found');
		my $json = encode_json(\%error);
		print "$json\n";
		exit;

	}
	if ($row->{'light_ip'} eq "" || $row->{'light_ip'} ne $session_ip)
	{
		if ($No_Update == 0)
		{
			#Update light_ip
			$sql = $dbh->prepare("UPDATE led_lights SET light_ip=? WHERE id = ?");
			$sql->execute($session_ip, $row->{'id'});
		}
	}

	$sql = $dbh->prepare("UPDATE led_lights SET version=? WHERE id = ?");
	$sql->execute($version_num, $row->{'id'});


	#Check Database for infomation on lightid.
	#If Found return info as JSON while adding IP address of the light.
	#If not found return JSON stating so.
	my %info = ();
	$info{'light_ip'} = $session_ip;
	$info{'switch_ip'} = $row->{'switch_ip'};
	$info{'snmp'} = $row->{'snmp'};
	$info{'bandwidth'} = $row->{'bandwidth'};
	my $json = encode_json(\%info);
	print "$json\n";

	exit;
}

if (defined($action) && $action eq "SAVELED")
{
	print $query->header();

	my $lightid = $query->param("lightid");
	my $switch_id = $query->param("switch_id");
	my $snmp = $query->param("snmp");
	my $bandwidth = $query->param("bandwidth");
	#my $switch_ip = "10.13.37.

	#Update light_ip
	my $sql = $dbh->prepare("UPDATE led_lights SET switch_ip=?, snmp=?, bandwidth=?  WHERE id = ?");
	$sql->execute($switch_id,$snmp,$bandwidth,$lightid);

	print "LED $lightid SAVED\n";
	exit;
}


print $query->header();
#Number of Columns
#Number of in a column
#Number of Switches in Columns
my $byoc_rows = 11;
my $byoc_tables = 14;
my $byoc_switches = 3;
my $byoc_orientation = 1; #0 = Horizonal 1 = Vertical

my $public_rows = 2;
my $public_tables = 9;
my $public_switches = 1;
my $public_orientation = 0; #0 = Horizonal 1 = Vertical
my $light_count = 1;


print <<EOL;
<html>
<head>
<title>LED Configuration</title>
<link href="css/bootstrap.min.css" rel="stylesheet">
<!-- <link href="css/site.css" rel="stylesheet"> -->
<!-- jQuery (necessary for Bootstrap's JavaScript plugins) -->
<script src="js/jquery-1.11.1.min.js"></script>
<!-- Include all compiled plugins (below), or include individual files as needed -->
<script src="js/bootstrap.min.js"></script>
<script src="js/led.js"></script>

</head>
<style>
	.rtable {
	border: 1px solid #000;
	position: absolute;
	}

	.switch {
	border: 2px solid #F00;
  background-color: #f00;
	position: absolute;
  cursor: pointer;
  z-index: 100;
  font-size: 10px;
	}

 #LightSetupBox {
   position : absolute;
   top: 400px;
   left : 300px;
   width : 300px;
   height : auto;
   border : 1px solid #000;
   display: none;
 }

 #LightControl {
   position : absolute;
   top: 400px;
   left : 300px;
   width : 300px;
   height : auto;
   border : 1px solid #000;
   display: none;
 }

 #ALLLightControl {
   position : absolute;
   top: 50px;
   left : 700px;
   width : 300px;
   height : auto;
   border : 1px solid #000;
 }

</style>
<body style="position: absolute;">

EOL
print "\n";

DrawTables($byoc_rows, $byoc_tables, $byoc_switches, 1, 50, 50, "byoc");
DrawTables($public_rows, $public_tables, $public_switches, 0, 50, 400, "public");

for(my $i=$light_count;$i<31;$i++)
{
	my $switch_width = 15;
	my $switch_height = 10;

	print "<div class=\"switch\" id=\"extra-$i-switch\" style=\"top: ". (($switch_height-250) + ($i * 30)) ."px; left: ". ($switch_width + 45) ."px; \" onclick=\"editLights($light_count)\">$i</div>\n";

}




print "<div id=\"LightSetupBox\">\n";

print "<form id=\"lightsetup\">\n";
print "Light ID : <input type=\"text\" name=\"lightid\"><br>\n";
print "Light IP : <input type=\"text\" name=\"light_ip\" disabled=\"disabled\" ><br>\n";
print "Switch IP : <input type=\"text\" name=\"switch_id\"><br>\n";
print "SNMP : <input type=\"text\" name=\"snmp\" value=\".1.3.6.1.2.1.2.2.1.10.4\"><br>\n";
print "Bandwidth : <input type=\"text\" name=\"bandwidth\" value=\"10000000\"><br>\n";
print "<button type=\"button\" class=\"btn btn-primary\" onclick=\"SaveLED();\">Save Light</button>\n";
print "<button type=\"button\" class=\"btn btn-primary\" onclick=\"Close('LightSetupBox');\" style=\"float: right\">Close</button><br>\n";
print "</form>\n";
print "</div>\n";

print "<div id=\"LightControl\">\n";
print "Light Id = <span id=\"lightidtext\">NaN</span><br>\n";
print '<button id="light_off" type="button" class="btn btn-primary btn-block">OFF</button><br>';
print '<button id="light_BW" type="button" class="btn btn-primary btn-block">BANDWIDTH</button><br>';
print '<button id="light_white" type="button" class="btn btn-primary btn-block">WHITE</button><br>';
print '<button id="light_Rainbox" type="button" class="btn btn-primary btn-block">RAINBOW</button><br>';
print "<button type=\"button\" class=\"btn btn-primary btn-block\" onclick=\"Close('LightControl');\">Close</button><br>";
print "</div>\n";

print "<div id=\"ALLLightControl\">\n";
print "Light Id = <span id=\"lightidtext\">ALL LIGHTS!</span><br>\n";
print "<button id=\"light_off\" type=\"button\" class=\"btn btn-primary btn-block\" onclick=\"LightControl(9999, 'STOP');\">OFF</button><br>";
print "<button id=\"light_BW\" type=\"button\" class=\"btn btn-primary btn-block\" onclick=\"LightControl(9999, 'BANDWIDTH');\">BANDWIDTH</button><br>";
print "<button id=\"light_white\" type=\"button\" class=\"btn btn-primary btn-block\" onclick=\"LightControl(9999, 'FILL 60 FFFFFF');\">WHITE</button><br>";
print "<button id=\"light_Rainbox\" type=\"button\" class=\"btn btn-primary btn-block\" onclick=\"LightControl(9999, 'RAINBOW');\">RAINBOW</button><br>";
print "</div>\n";



sub DrawTables()
{
	my ($rows, $tables, $switches, $orientation, $left, $top, $pre)= @_;
	my $table;
	my $wait = $tables / $switches;
	$wait = sprintf("%.0f", $wait);
	my $place = $wait/2;
	$place = sprintf("%.0f", $place);
	my $next = $wait - $place;
	#print "$next<hr>\n";

	if ($orientation == 1)
	{
		my $table_width = 20;
		my $table_height = 20;
		my $switch_width = 15;
		my $switch_height = 10;

		for(my $i=0;$i<$rows;$i++)
		{
			$table = 1;
			$next = $wait - $place;
			for(my $j=0;$j<$tables;$j++)
			{
				print "<div class=\"rtable\" id=\"$pre-$i-$table\" style=\"top: ". ($j * ($table_height+3) + $top) ."px;left: ". ($i * ($table_width + 40) + $left) ."px;width: ". $table_width ."px;height: ". $table_height ."px;\"></div>\n";

				if ($next == $table && $light_count <= 30)
				{
					print "<div class=\"switch\" id=\"$pre-$i-switch\" style=\"top: ". (($j+1) * ($switch_height+13) + $top) ."px; left: ". ($i * ($switch_width + 45) + $left - (($switch_width - $table_width) / 2 +1)) ."px; \" onclick=\"editLights($light_count)\">$light_count</div>\n";
					$light_count++;
					#print "<div class=\"switch\" style=\"top: ". (($j+1) * 23+ 5) ."px;left: ". ($i * 50 + 47) ."px\"></div>\n";
					$next = $next + $wait;
				}
				$table++;
			}
		}
	}

	if ($orientation == 0)
	{
		my $table_width = 20;
		my $table_height = 20;
		my $switch_width = 10;
		my $switch_height = 15;

		for(my $i=0;$i<$rows;$i++)
		{
			$table = 1;
			$next = $wait - $place;
			for(my $j=0;$j<$tables;$j++)
			{
				print "<div class=\"rtable\" id=\"$pre-$i-$table\" style=\"top: ". ($i * ($table_height+40) + $top) ."px;left: ". ($j * ($table_width + 3) + $left) ."px;width: ". $table_width ."px;height: ". $table_height ."px;\"></div>\n";
				if ($next == $table && $light_count <= 30)
				{
					print "<div class=\"switch\" id=\"$pre-$i-switch\" style=\"top: ". (($i) * ($switch_height+45) + $top - (($switch_height - $table_height) / 2 +1)) ."px; left: ". (($j+1) * ($switch_width + 13) + $left) ."px; \">$light_count</div>\n";
					$light_count++;
					#print "<div class=\"switch\" style=\"top: ". (($j+1) * 23+ 5) ."px;left: ". ($i * 50 + 47) ."px\"></div>\n";
					$next = $next + $wait;
				}
				$table++;
			}
		}

	}
}
