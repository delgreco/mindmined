#!/usr/bin/perl

=head1 Contacts

Just a thing to manage contact data, from before there were many things like that.

2025: updated for newer Perls.

=cut

# use strict, warnings and modern features
use 5.030;

use lib qw (
    ../lib
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
);

use CGI;
use CGI::Carp('fatalsToBrowser');
use DBI; 
use HTML::Template;
use Dotenv -load;

use FatalsToEmail    
  qw(
      Mailhost localhost
      Address marcusdelgreco@gmail.com
      Error_cache /tmp/contacts.tmp
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
# run the sub by the same name as $action
&{\&{$action}}();
exit;

=head2 contactInterface

TODO

=cut

sub contactInterface {
    my $id=$cgiobject->param('id'); 
    my $t = HTML::Template->new(filename => 'templates/mmpub/contacts/contactInterface.tmpl');
    my $existing_contact;
    my ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $notes, $existing_client_id, $producer);
    if ($id) {  # get data about this contact
        my $select = <<~"SQL";
        SELECT last_name, first_name, home_phone, business_phone, cellphone, 
        street, city, state, zip, email, notes, client_id, producer 
        FROM contacts 
        WHERE id = ?
        SQL
        my $sth = $dbh->prepare($select);
        $sth->execute($id);
        ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $notes, $existing_client_id, $producer) = $sth->fetchrow_array();
        $sth->finish();
        my $address;
        if ($city || $state) {
            $address = qq {$city, $state $zip<br>};
        }
        $t->param(ADDRESS => $address);
        $t->param(FIRST_NAME => $first_name);
        $t->param(LAST_NAME => $last_name);
        $t->param(HOME_PHONE => $home_phone);
        $t->param(BUSINESS_PHONE => $business_phone);
        $t->param(CELLPHONE => $cellphone);
        $t->param(STREET => $street);
        $t->param(CITY => $city);
        $t->param(STATE => $state);
        $t->param(ZIP => $zip);
        $t->param(EMAIL => $email);
        $t->param(NOTES => $notes);
        $t->param(ID => $id);
        if ( $producer eq "yes" ) {
            $t->param(PRODUCER => 1);
        }
    }
    my $select = <<~"SQL";
    SELECT id, name FROM clients 
    ORDER BY name
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my @client_options;
    while (my ($client_id, $client_name) = $sth->fetchrow_array()) {
        my %row;
        if ($existing_client_id == $client_id) {
            $row{PRODUCER} = 1;
        }
        $row{CLIENT_NAME} = $client_name;
        $row{CLIENT_ID}= $client_id;
        push(@client_options, \%row);
    }
    $t->param(CLIENT_OPTIONS => \@client_options);
    $t->param(PAGETITLE => 'Contact Manager');
    my $output = $t->output;
    print "Content-type: text/html\n\n";
    print $output;
}


=head2 deleteContact

TODO

=cut
sub deleteContact {
    my $id = $cgiobject->param('id'); 
    my $select = <<~"SQL";
    SELECT first_name, last_name FROM contacts WHERE id = ?
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute($id);
    my ($first_name, $last_name) = $sth->fetchrow_array();
    # delete the entry
    my $sql = <<~"SQL";
    DELETE FROM contacts WHERE id = ?
    SQL
    my $rows_deleted = $dbh->do(qq{$sql}, undef, $id);
    if ( $rows_deleted != 1 ) {
        print STDERR "ERROR: $rows_deleted rows deleted.";
    }
    my $message = qq |$first_name $last_name deleted from the database.|;
    mainInterface($message);
}

=head2 mainInterface

TODO

=cut
sub mainInterface {  # the default interface for managing the Gallery
    my $order_by=$cgiobject->param('order_by'); 
    if (! $order_by) {
        $order_by = 'last_name';
    }
    my $message = $_[0];
    my $t = HTML::Template->new(filename => 'templates/mmpub/contacts/mainInterface.tmpl');
    my $select = <<~"SQL";
    SELECT last_name, first_name, home_phone, business_phone, cellphone, email, id 
    FROM contacts 
    ORDER BY $order_by
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my $i = 0; my @contacts;
    while (my ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $email, $id) = $sth->fetchrow_array()) {
        my %row;
        $i++;
        if ( $i % 2 == 0 ) {
            $row{BGCOLOR} = '#EEEEEE';
        }
        else { 
            $row{BGCOLOR} = '#FFFFFF';
        }
        $row{LAST_NAME} = $last_name;
        $row{FIRST_NAME} = $first_name;
        $row{HOME_PHONE} = $home_phone;
        $row{BUSINESS_PHONE} = $business_phone;
        $row{CELLPHONE} = $cellphone;
        $row{EMAIL} = $email;
        $row{ID} = $id;
        push(@contacts, \%row);
    }
    $t->param(MESSAGE => $message);
    $t->param(CONTACTS => \@contacts);
    $t->param(PAGETITLE => 'Contact Manager');
    my $output = $t->output;
    print "Content-type: text/html\n\n";
    print $output;
}

=head2 saveContact

TODO

=cut

sub saveContact {  
    my $last_name=$cgiobject->param('last_name'); 
    my $first_name=$cgiobject->param('first_name'); 
    my $home_phone=$cgiobject->param('home_phone'); 
    my $business_phone=$cgiobject->param('business_phone'); 
    my $cellphone=$cgiobject->param('cellphone'); 
    my $street=$cgiobject->param('street');
    my $city=$cgiobject->param('city'); 
    my $state=$cgiobject->param('state'); 
    my $zip=$cgiobject->param('zip'); 
    my $email=$cgiobject->param('email'); 
    my $notes=$cgiobject->param('notes'); 
    my $client_id=$cgiobject->param('client_id'); 
    my $producer=$cgiobject->param('producer'); 
    my $id=$cgiobject->param('id'); 
    if ($producer eq 'on') {
        $producer = 'yes';
    }
    else {
        $producer = 'no';
    }
    $client_id = 0 unless $client_id;
    if ( $id ) {
        my $sql = <<~"SQL";
        UPDATE contacts SET last_name = ?, first_name = ?, home_phone = ?, business_phone = ?, 
        cellphone = ?, street = ?, city = ?, state = ?, zip = ?, email = ?, notes = ?, client_id = ?, producer = ? 
        WHERE id = ?
        SQL
        my $rows_updated = $dbh->do(qq{$sql}, undef, $last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $notes, $client_id, $producer, $id);
        if ( $rows_updated != 1 ) {
            print STDERR "ERROR: $rows_updated rows updated.";
        }
        my $message = qq {$first_name $last_name has been updated.};
        mainInterface($message);
    }
    else {
        my $sql = <<~"SQL";
        INSERT INTO contacts (last_name, first_name, home_phone, business_phone, cellphone, street, city, state, zip, email, notes, client_id, producer) 
        VALUES 
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        SQL
        my $rows_inserted = $dbh->do(qq{$sql}, undef, $last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $notes, $client_id, $producer);
        if ( $rows_inserted != 1 ) {
            print STDERR "ERROR: $rows_inserted rows inserted.";
        }
        # grab the automatically incremented id that was generated
        $id = $dbh->{mysql_insertid} || $dbh->{insertid};
        my $message = qq |$first_name $last_name has been added.|;
        mainInterface($message);
    }

}

=head2 showCompleteList

TODO

=cut

sub showCompleteList {
    my $t = HTML::Template->new(filename => 'templates/mmpub/contacts/completeList.tmpl');
    my $select = <<~"SQL";
    SELECT last_name, first_name, home_phone, business_phone, cellphone, email, 
    street, city, state, zip, notes, id 
    FROM contacts 
    ORDER BY last_name, first_name
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my @contacts;
    while (my ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $email, $street, $city, $state, $zip, $notes, $id) = $sth->fetchrow_array()) {
        my %row;
        my $address;
        if ($city || $state) {
            $address = qq |$city, $state $zip|;
        }
        $row{ADDRESS} = $address;
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        $row{HOME_PHONE} = $home_phone;
        $row{BUSINESS_PHONE} = $business_phone;
        $row{CELLPHONE} = $cellphone;
        $row{STREET} = $street;
        #$row{CITY} = $city;
        #$row{STATE} = $state;
        #$row{ZIP} = $zip;
        $row{EMAIL} = $email;
        $row{NOTES} = $notes;
        #$row{ID} = $id;
        push(@contacts, \%row);
    }
    $t->param(CONTACTS => \@contacts);
    $t->param(PAGETITLE => 'Contact Manager');
    my $output = $t->output;
    print "Content-type: text/html\n\n";
    print $output;
}



