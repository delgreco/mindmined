#!/usr/bin/perl -w

# use strict, warnings and modern features
use 5.030;

use lib qw (
    ../lib
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
);

use CGI;
use DBI;
use HTML::Template;
use Dotenv -load;

use FatalsToEmail    
  qw(
      Mailhost localhost
      Address marcusdelgreco@gmail.com
      Error_cache /tmp/library.tmp
      Seconds 60
      Debug 1
    );  

my $cgiobject = new CGI;

my $dbh = DBI->connect(
    "DBI:mysql:$ENV{DB_NAME}",
    $ENV{DB_USER},
    $ENV{DB_PASS},
    {
        RaiseError           => 1,
        ShowErrorStatement   => 1,
        AutoCommit           => 1,
        mysql_enable_utf8mb4 => 1,
        mysql_socket         => $ENV{DB_SOCKET},
    }
) || die "Connect failed: $DBI::errstr\n"; 

my $action=$cgiobject->param('action');
$action = 'mainInterface' if ! $action;

my ($template, $message) = &{\&{$action}}() if $action;   # run the sub called $action
_processTemplate($template, $message);

=head2 clientInterface

TODO

=cut

sub clientInterface {
	my $id=$cgiobject->param('id'); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/clients/clientInterface.tmpl');
	my $name; my $website;
	if ($id) {  # get data about this note
		my $select="SELECT name, website 
		FROM clients 
		WHERE id = ?";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($id) || die "execute: $select: $DBI::errstr";
		($name, $website) = $sth->fetchrow_array();
		$sth->finish();
	}
	$template->param(NAME => $name);
	$template->param(WEBSITE => $website);
	$template->param(ID => $id);
	return ($template, $message);
}

=head2 deleteNote

TODO

=cut

sub deleteNote {
	my $id=$cgiobject->param('id');
	my $delete="DELETE FROM client_notes 
	WHERE id = ?";
	my $sth = $dbh->prepare($delete) || die "prepare: $delete: $DBI::errstr";
	$sth->execute($id) || die "execute: $delete: $DBI::errstr";
	$sth->finish();
	my $message = qq |Note id #$id has been deleted.|;
	mainInterface($message);
}

=head2 getHotDate

TODO

=cut

sub getHotDate {  # sets $day (as in 27 or 4), $month (as in January), $year (as in 2004) and $dayname (as in Monday)
	my $timestamp = $_[0];  # assuming a 14 digit timestamp coming in
	# look for a timestamp coming in datetime format (2005-04-11 14:55:58) and convert to timestamp
	if ( $timestamp =~ m/.*:.*/ ) {   # in other words, find a colon, strip all but the digits
		$timestamp =~ s/://g;
		$timestamp =~ s/ //g;
		$timestamp =~ s/-//g;
	}
	# format date
	my $month_digit = substr($timestamp, 4, 2);
	my $month = getMonth($month_digit);
	my $day = substr($timestamp, 6, 2);
	if ( $day =~ /^0/ ) {    # if the day is annything 01-09, strip the 0
		$day =~ s/0//;
	}
	my $year = substr($timestamp, 0, 4);
	my $reformatted_date = "$year-$month_digit-$day";
	my $select_day = <<~ "SQL";
    SELECT DAYNAME(?)
    SQL
	my $sth = $dbh->prepare($select_day);
	$sth->execute($reformatted_date);
	my ($dayname) = $sth->fetchrow_array();
	return ($day, $month, $year, $dayname);
}

=head2 getMonth

TODO

=cut

sub getMonth {  # give it a month name ("January"), get back a digit, or vice versa
	my $month = $_[0];
	# define month hash
	my %month_name = (
		'01' => 'January',
		'02' => 'February',
		'03' => 'March',
		'04' => 'April',
		'05' => 'May',
		'06' => 'June',
		'07' => 'July',
		'08' => 'August',
		'09' => 'September',
		'10' => 'October',
		'11' => 'November',
		'12' => 'December',
	);
	my %month_num = (
		'January' => '01',
		'February' => '02',
		'March' => '03',
		'April' => '04',
		'May' => '05',
		'June' => '06',
		'July' => '07',
		'August' => '08',
		'September' => '09',
		'October' => '10',
		'November' => '11',
		'December' => '12',
	);
	if ($month =~ m/^\D+$/xms) {  # we've been given a month name, give back a digit
		return $month_num{$month};
	}
	elsif ($month =~ m/^\d\d$/xms) {  # we've been given a digit, give back a month name
		return $month_name{$month};
	}
	else {
		$month = "[error in getMonth]";
		return $month;
	}
}

=head2 manageClientInterface

TODO

=cut

sub manageClientInterface {
	my $id=$cgiobject->param("id"); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/clients/manageClientInterface.tmpl');
	my $select="SELECT name, website FROM clients WHERE id = '$id'";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my ($name, $website) = $sth->fetchrow_array();
	$sth->finish();
	# get all associated contacts
	$select="SELECT last_name, first_name, home_phone, business_phone, cellphone, street, city, state, zip, email, id FROM contacts WHERE client_id = '$id'";
	$sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my $counter = 0;
	my @contacts;
	while (my ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $contact_id) = $sth->fetchrow_array()) { 
		my %row;
		$row{LAST_NAME} = $last_name;
		$row{FIRST_NAME} = $first_name;		
		$row{HOME_PHONE} = $home_phone;		
		$row{BUSINESS_PHONE} = $business_phone;
		$row{CELLPHONE} = $cellphone;
		$row{CITY} = $city;
		$row{STREET} = $street;
		$row{STATE} = $state;
		$row{CONTACT_ID} = $contact_id;
		$row{EMAIL} = $email;
		$row{ZIP} = $zip;
		push(@contacts, \%row);
	}
	$sth->finish();
	# get reminder info, be it one or many reminders for this account
	$select="SELECT email, reminder_type, reminder, id FROM reminders WHERE account_number = '$id'";
	$sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my @reminders;
	while (my ($email, $reminder_type, $reminder, $id) = $sth->fetchrow_array()) {
		my %row;
		$row{REMINDER} = $reminder;
		$row{EMAIL} = $email;
		$row{REMINDER_TYPE} = $reminder_type;
		$row{ID} = $id;
		push(@reminders, \%row);
	}
	# get associated notes
	$select="SELECT note, date_added, id FROM client_notes WHERE client_id = '$id' ORDER BY date_added DESC";
	$sth = $dbh->prepare($select);
	$sth->execute();
	my $i; my @notes;
	while (my ($note, $date_added, $note_id) = $sth->fetchrow_array()) { 
		my %row;
		$i++;
		#if ($i % 2 == 0) {
	   	#	$row{BGCOLOR} = '';
		#}
		#else {
		#	$row{BGCOLOR} = '#DDDDDD';
		#}
		my ($day, $month, $year, $dayname) = getHotDate($date_added);
		my $date_added = qq {$month $day, $year};
		$row{NOTE} = $note;
		$row{NOTE_ID} = $note_id;
		$row{DATE_ADDED} = $date_added;
		push(@notes, \%row);
	}
	$sth->finish();	
	$template->param(CONTACTS => \@contacts);
	$template->param(NOTES => \@notes);
	$template->param(REMINDERS => \@reminders);
	$template->param(NAME => $name);
	$template->param(WEBSITE => $website);
	$template->param(CLIENT_ID => $id);
	return ($template, $message);
}

=head2 mainInterface

TODO

=cut

sub mainInterface {  # the default interface for managing the Gallery
	my $message = $_[0];
	my $template = HTML::Template->new(filename => 'templates/mmpub/clients/mainInterface.tmpl');
	# for sorting the clients table
	my $sort_by=$cgiobject->param("sort_by"); 
	unless ($sort_by) {
		$sort_by = "name";
	}
	my $select="
	SELECT client_notes.client_id, clients.name, client_notes.note, client_notes.date_added AS date_added, client_notes.id 
	FROM client_notes
	JOIN clients ON client_notes.client_id = clients.id
	ORDER BY date_added DESC 
	LIMIT 15";
	my $sth = $dbh->prepare($select);
	$sth->execute();
	my $i; my @notes;
	while (my ($client_id, $client_name, $note, $date_added, $id) = $sth->fetchrow_array()) { 
		my %row;
		$i++;
		if ($i % 2 == 0) {
			$row{BGCOLOR} = '';
		}
		else {
			$row{BGCOLOR} = '#DDDDDD';
		}
		my ($day, $month, $year, $dayname) = getHotDate($date_added);
		$date_added = qq {$month $day, $year};
		$row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
		$row{NOTE} = $note;
		$row{ID} = $id;
		$row{CLIENT_NAME} = $client_name;
		$row{CLIENT_ID} = $client_id;
		$row{DATE_ADDED} = $date_added;
		push(@notes, \%row);
	}
	$sth->finish();
	$select="SELECT name, website, id FROM clients ORDER BY $sort_by";
	$sth = $dbh->prepare($select);
	$sth->execute();
	my @clients;
	while (my ($name, $website, $id) = $sth->fetchrow_array()) {
		my %row;
		my $select="SELECT note, date_added, id FROM client_notes WHERE client_id = '$id' ORDER BY date_added DESC";
		my $sth = $dbh->prepare($select);
		$sth->execute();
		my ($note, $date_added, $note_id) = $sth->fetchrow_array();
		$sth->finish();
		my ($day, $month, $year, $dayname) = getHotDate($date_added);
		$date_added = qq |$month $day, $year|;
		$i++;
		if ($i % 2 == 0) {
			$row{BGCOLOR} = '';
		}
		else { 
			$row{BGCOLOR} = '#DDDDDD';
		}
		$row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
		$row{NAME} = $name;
		$row{WEBSITE} = $website;
		$row{NOTE} = $note;
		$row{DATE_ADDED} = $date_added;
		$row{ID} = $id;
		push(@clients, \%row);
	}
	$sth->finish();
	$template->param(MESSAGE => $message);
	$template->param(NOTES => \@notes);
	$template->param(CLIENTS => \@clients);
	return ($template, $message);
}

=head2 noteInterface

TODO

=cut

sub noteInterface {
	my $client_id=$cgiobject->param('client_id'); 
	my $id=$cgiobject->param('id'); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/clients/noteInterface.tmpl');
	my $note; my $date_added;
	if ($id) {  # get data about this note
		my $select="SELECT note, client_id, date_added 
		FROM client_notes 
		WHERE id = ?";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($id) || die "execute: $select: $DBI::errstr";
		($note, $client_id, $date_added) = $sth->fetchrow_array();
		$sth->finish();
	}
	# create client dropdown
	my $select="SELECT id, name FROM clients ORDER BY name";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my @client_options;
	while (my ($id, $name) = $sth->fetchrow_array()) {
		my %row;
		$row{NAME} = $name;
		$row{ID} = $id;
		if ($client_id eq $id) {
			$row{SELECTED}= 1;
		}
		push(@client_options, \%row);
	}
	$sth->finish();
	$template->param(NOTE => $note);
	$template->param(CLIENT_OPTIONS => \@client_options);
	return ($template, $message);	
}

=head2 _processTemplate

TODO

=cut

sub _processTemplate {
	my $t = $_[0];
	my $message = $_[1];
	$t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$t->param(MESSAGE => $message);
	$t->param(PAGETITLE => 'Mind Mined Business Manager');
	#$t->param(SCRIPT_FILENAME => $ENV{SCRIPT_FILENAME});
	my $output = $t->output;
	print "Content-type: text/html\n\n";
	print $output;
}

=head2 saveClient

TODO

=cut

sub saveClient {   # grab the values submitted
	my $name = $cgiobject->param('name'); 
	my $website = $cgiobject->param('website'); 
	my $id = $cgiobject->param('id'); 
	if ($id) {  # update the client data
		my $update="UPDATE clients SET name = ?, website = ? 
		WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($name, $website, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq {$name has been updated.};
		mainInterface($message);
	}
	else {  # insert the new client data
		my $select="INSERT INTO clients (name, website) VALUES (?, ?)";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($name, $website) || die "execute: $select: $DBI::errstr";
		# grab the automatically incremented id that was generated
		my $id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |$name has been added.|;
		mainInterface($message);
	}
}

=head2 saveNote

TODO

=cut

sub saveNote {
	my $note=$cgiobject->param('note'); 
	my $id=$cgiobject->param('id');
	my $client_id=$cgiobject->param('client_id');
	# get the client name
	my $select="SELECT name FROM clients 
	WHERE id = ?";
	my $sth = $dbh->prepare($select);
	$sth->execute($client_id) || die "sth->execute($select): $DBI::errstr\n";
	my ($client_name) = $sth->fetchrow_array();
	$sth->finish();
	if ($id) {  # update existing note
		my $update="UPDATE client_notes 
		SET note = ?, client_id = ? 
		WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($note, $client_id, $id) || die "sth->execute($update): $DBI::errstr\n";
		$sth->finish();
		my $message = qq |Note updated for $client_name.|;
		mainInterface($message);
	}
	else {  # insert new note
		# get the current datetime
		my $select="SELECT NOW()";
		my $sth = $dbh->prepare($select);
		$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
		my ($datetime) = $sth->fetchrow_array();
		$sth->finish();
		my $insert="INSERT INTO client_notes 
		(note, date_added, client_id) 
		VALUES 
		(?, ?, ?)";
		$sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($note, $datetime, $client_id) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |Note added for $client_name.|;
		mainInterface($message);
	}
}

=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


