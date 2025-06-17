#!/usr/bin/perl

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


#
#
# task: something that needs doing, and its requirements
#
# reminder: a timely email tickler
#
# find local modules

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

# cron this script with the -send_reminders 
# param once per day, preferably in the morning

if ($ARGV[0] && $ARGV[0] eq "-send_reminders") {  # command line for cron
    oneTimeReminders();
    monthlyReminders();
    yearlyReminders();
    weeklyReminders();
    exit;
}
else {  # web
    my $action=$cgiobject->param("action");
    $action = qq |tasksInterface| if ! $action;
    
    my ($template, $message) = &{\&{$action}}() if $action;   # run the sub called $action
    _processTemplate($template, $message);
}
exit;

sub deleteReminder {
    my $id=$cgiobject->param("id");
    my $delete="DELETE FROM reminders WHERE id = '$id'";
    my $sth = $dbh->prepare($delete) || die "prepare: $delete: $DBI::errstr";
    $sth->execute || die "execute: $delete: $DBI::errstr";
    my $message = qq |Reminder deleted.|;
    remindersInterface($message);
}

sub deleteTask {
    my $id=$cgiobject->param("id");
    my $delete="DELETE FROM tasks WHERE id = ?";
    my $sth = $dbh->prepare($delete) || die "prepare: $delete: $DBI::errstr";
    $sth->execute($id) || die "execute: $delete: $DBI::errstr";
    $sth->finish();
    my $message = qq |Task deleted.|;
    tasksInterface($message);
}

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

sub _getStatusesDropdown {
    my %arg = @_;
    my $template = $arg{template};
    my $selected_status = $arg{status};
    my @statuses = (
        'to-do',
        'complete',
    );
    my @statuses_dropdown;
    foreach my $status (@statuses) {
        my %row;
        $row{STATUS} = $status;
        if ($selected_status eq $status) {
            $row{SELECTED} = 1;
        }
        push(@statuses_dropdown, \%row);
    }
    $template->param(STATUSES_DROPDOWN => \@statuses_dropdown);
    return $template;
}

sub _processTemplate {
    my $template = $_[0];
    my $message = $_[1];
    $template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    $template->param(MESSAGE => $message);
    $template->param(PAGETITLE => 'Mind Mined ReMinder');
    #$template->param(SCRIPT_FILENAME => $ENV{SCRIPT_FILENAME});
    my $output = $template->output;
    print "Content-type: text/html\n\n";
    print $output;
}

sub reminderInterface {
    my $message = $_[0];
    my $id=$cgiobject->param("id");  # we will get this
    my $account_number = $cgiobject->param("account_number");  # or this
    my $template = HTML::Template->new(filename => 'templates/mmpub/reminder/reminderInterface.tmpl');
    my $remindee_email; my $reminder_type;
    if ($id) {
        my $select="SELECT email, account_number, reminder_type FROM reminders WHERE id = '$id'";
        my $sth = $dbh->prepare($select);
        $sth->execute();
        ($remindee_email, $account_number, $reminder_type) = $sth->fetchrow_array();
        $sth->finish();
    }
    # recipients
    my @emails = (
        "marcus\@mindmined.com", 
        "delgreco\@unh.edu", 
        "jessica\@mindmined.com", 
        "connie\@mindmined.com", 
        "info\@lastingwordz.com", 
        "lockeamb\@worldpath.net"
    );
    my @reminder_types = (
        "one-time",
        "yearly",
        "monthly",
        "weekly"
    );
    my @email_options;
    foreach my $email (@emails) {
        my %row;
        if ($email eq $remindee_email) {
            $row{SELECTED} = 1;
        }
        $row{EMAIL} = $email;
        push(@email_options, \%row);
    }
    my @type_options;
    foreach my $type (@reminder_types) {
        my %row;
        if ($type eq $reminder_type) {
            $row{CHECKED} = 1;
        }
        $row{TYPE} = $type;
        push(@type_options, \%row);
    }
    # grab client list
    my $select="SELECT id, name FROM clients ORDER BY name";
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my @client_options;
    while (my ($client_id, $client_name) = $sth->fetchrow_array()) {
        my %row;
        if ($account_number eq $client_id) {
            $row{SELECTED} = 1;
        }
        $row{ID} = $client_id;
        $row{CLIENT} = $client_name;
        push(@client_options, \%row);
    }
    $sth->finish();
    my $reminder; my $trigger_month; my $trigger_day; my $trigger_year; my $trigger_weekday;
    if ($id) {
        my $select="SELECT reminder, trigger_month, trigger_day, trigger_year, trigger_weekday FROM reminders WHERE id = '$id'";
        my $sth = $dbh->prepare($select);
        $sth->execute();
        ($reminder, $trigger_month, $trigger_day, $trigger_year, $trigger_weekday) = $sth->fetchrow_array();
        $sth->finish();
    }
    $select="SELECT YEAR(NOW())";
    $sth = $dbh->prepare($select);
    $sth->execute();
    my ($year) = $sth->fetchrow_array();
    $sth->finish();
    my $month_options;
    my @months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December"
    );
    my @month_options;
    foreach my $month (@months) {
        my %row;
        if ($month eq $trigger_month) {
            $row{SELECTED} = 1;
        }
        $row{MONTH} = $month;
        push(@month_options, \%row);
    }
    my @dayofmonth_options;
    foreach my $day (1 .. 31) {
        my %row;
        $row{DAY} = $day;
        if ($day eq $trigger_day) {
            $row{SELECTED} = 1;
        }
        push(@dayofmonth_options, \%row);
    }
    my @dayofweek_options;
    my %daysofweek = (
        "1" => "Sunday",
        "2" => "Monday",
        "3" => "Tuesday",
        "4" => "Wednesday",
        "5" => "Thursday",
        "6" => "Friday",
        "7" => "Saturday"
    );
    my @dofofweek_options;
    for my $key (sort (keys %daysofweek)) {
        my %row;
        if ($key eq $trigger_weekday) {
            $row{DAYOFWEEK_SELECTED} = 1;
        }
        $row{DAYOFWEEK_NUM} = $key;
        $row{DAYOFWEEK} = $daysofweek{$key};
        push(@dayofweek_options, \%row);
    }
    $template->param(EMAIL_OPTIONS => \@email_options);
    $template->param(DAYOFMONTH_OPTIONS => \@dayofmonth_options);
    $template->param(DAYOFWEEK_OPTIONS => \@dayofweek_options);
    $template->param(MONTH_OPTIONS => \@month_options);
    $template->param(YEAR => $year);
    $template->param(ID => $id);
    $template->param(REMINDER => $reminder);
    $template->param(EMAIL_OPTIONS => \@email_options);
    $template->param(REMINDER_TYPES => \@type_options);
    $template->param(CLIENT_OPTIONS => \@client_options);
    return($template, $message);
}

sub remindersInterface {
    my $message = $_[0];
    my $email=$cgiobject->param('email'); 
    my $where;
    my $show_all;
    my $template = HTML::Template->new(filename => 'templates/mmpub/reminder/remindersInterface.tmpl');
    # get today
    my $select="SELECT DAYOFMONTH(NOW()), MONTH(NOW()), YEAR(NOW())";
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my ($day_of_month, $month, $year) = $sth->fetchrow_array();
    $sth->finish();
    if ($email) {
        $where = qq |WHERE email = '$email'|;
        $template->param(SHOW_ALL_LINK => 1);
    }
    $select="SELECT email, reminder, trigger_day, trigger_month, trigger_year, trigger_weekday, reminder_type, account_number, id 
    FROM reminders $where 
    ORDER BY added_stamp DESC";
    $sth = $dbh->prepare($select);
    $sth->execute();
    my @reminders;
    my $i;
    while (my ($email, $reminder, $trigger_day, $trigger_month, $trigger_year, $trigger_weekday, $reminder_type, $account_number, $reminder_id) = $sth->fetchrow_array()) {   
        my %row;
        $row{MOUSEOVER_BGCOLOR} = '#FFFF99';
        $row{EMAIL} = $email;
        $row{REMINDER} = $reminder;
        #$row{REMINDER_TYPE} = $reminder_type;
        #$row{ACCOUNT_NUMBER} = $account_number;
        $row{ID} = $reminder_id;
        $i++;
        my $trigger_month_digit;
        if ($reminder_type eq "one-time") {
            $trigger_month_digit = getMonth($trigger_month);
            if ($year > $trigger_year) {
                $row{BGCOLOR} = '#6600FF';
            }
            elsif (($day_of_month < $trigger_day) && ($month > $trigger_month_digit) && ($year == $trigger_year)) {
                $row{BGCOLOR} = '#6600FF';
            }
            elsif (($day_of_month > $trigger_day) && ($month >= $trigger_month_digit) && ($year >= $trigger_year)) {
                $row{BGCOLOR} = '#6600FF';
            }
            else {          
                if ($i % 2 == 0) {
                    $row{BGCOLOR} = '#DDDDDD';
                }
                else { 
                    $row{BGCOLOR} = '#EEEEEE';
                }       
            }
        }
        else {
            if ($i % 2 == 0) {
                $row{BGCOLOR} = '#DDDDDD';
            }
            else { 
                $row{BGCOLOR} = '#EEEEEE';
            }
        }
        if ($reminder_type eq 'one-time') {
            $row{SCHEDULE} = qq |$trigger_month $trigger_day, $trigger_year ($reminder_type)|;
        }
        elsif ($reminder_type eq 'monthly') {
            $row{SCHEDULE} = qq |day $trigger_day of each month|;
        }
        elsif ($reminder_type eq 'yearly') {
            $row{SCHEDULE} = qq |yearly on $trigger_month $trigger_day|;
        }
        elsif ($reminder_type eq 'weekly') {
            my %daysofweek = (
                '1' => 'Sunday',
                '2' => 'Monday',
                '3' => 'Tuesday',
                '4' => 'Wednesday',
                '5' => 'Thursday',
                '6' => 'Friday',
                '7' => 'Saturday',
            );
            $row{SCHEDULE} = qq |weekly on $daysofweek{"$trigger_weekday"}|;
        }
        else {
            $row{SCHEDULE} = qq |ERROR: no valid reminder_type.|;
        }
        push(@reminders, \%row);
    }
    $sth->finish();
    #$template->param(YEAR => $year) if $year;
    $template->param(REMINDERS => \@reminders);
    return($template, $message);
}

sub saveReminder {
    my $id = $cgiobject->param('id');
    my $reminder = $cgiobject->param('reminder');
    my $trigger_day = $cgiobject->param('trigger_day');
    my $trigger_month = $cgiobject->param('trigger_month');
    my $trigger_year = $cgiobject->param('trigger_year');
    my $trigger_weekday = $cgiobject->param('trigger_weekday');
    my $account_number = $cgiobject->param('account_number');
    my $email = $cgiobject->param('email');
    my $reminder_type = $cgiobject->param('reminder_type');
    my $message;
    if (! $id) {  # brand new reminder
        my $insert="INSERT INTO reminders (reminder, trigger_day, trigger_month, trigger_year, trigger_weekday, account_number, email, reminder_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($reminder, $trigger_day, $trigger_month, $trigger_year, $trigger_weekday, $account_number, $email, $reminder_type) || die "execute: $insert: $DBI::errstr";
        $message = qq {A $reminder_type reminder has been added.};
    }
    else {
        my $update="UPDATE reminders SET reminder = ?, trigger_day = ?, trigger_month = ?, trigger_year = ?, trigger_weekday = ?, account_number = ?, email = ?, reminder_type = ? WHERE id = '$id'";
        my $sth = $dbh->prepare($update);
        $sth->execute($reminder, $trigger_day, $trigger_month, $trigger_year, $trigger_weekday, $account_number, $email, $reminder_type) || die "sth->execute($update): $DBI::errstr\n";
        $sth->finish();
        $message = qq {Reminder id #$id has been updated.};

    }
    remindersInterface($message);
}

sub saveTask {
    my $id = $cgiobject->param('id');
    my $task = $cgiobject->param('task');
    my $status = $cgiobject->param('status');
    my $message;
    if ($id) { 
        my $update="UPDATE tasks 
        SET task = ?, status = ? 
        WHERE id = ?";
        my $sth = $dbh->prepare($update);
        $sth->execute($task, $status, $id) || die "sth->execute($update): $DBI::errstr\n";
        $sth->finish();
        $message = qq |Task updated.|;
    }
    else {
        my $insert="INSERT INTO tasks 
        (task, status) 
        VALUES 
        (?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($task, $status) || die "execute: $insert: $DBI::errstr";
        $message = qq |Task added.|;
    }
    tasksInterface($message);
}

sub taskInterface {
    my $message = $_[0];
    my $id=$cgiobject->param("id");
    my $template = HTML::Template->new(filename => 'templates/mmpub/reminder/taskInterface.tmpl');
    my $task; my $status;
    if ($id) {
        my $select="SELECT task, status 
        FROM tasks 
        WHERE id = ?";
        my $sth = $dbh->prepare($select);
        $sth->execute($id);
        ($task, $status) = $sth->fetchrow_array();
        $sth->finish();
    }
    $template = &_getStatusesDropdown(
        status   => $status,
        template => $template,
    );
    $template->param(TASK => $task);
    $template->param(ID => $id);
    return($template, $message);
}

sub tasksInterface {
    my $message = $_[0];
    my $template = HTML::Template->new(filename => 'templates/mmpub/reminder/tasksInterface.tmpl');
    my $select="SELECT task, id
    FROM tasks
    ORDER BY task";
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my @tasks; my $i;
    while (my ($task, $id) = $sth->fetchrow_array()) {   
        $i++;
        my %row;
        $row{MOUSEOVER_BGCOLOR} = '#FFFF99';
        $row{TASK} = $task;
        $row{ID} = $id;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = '#DDDDDD';
        }
        else { 
            $row{BGCOLOR} = '#EEEEEE';
        }
        push(@tasks, \%row);
    }
    $sth->finish();
    $template->param(TASKS => \@tasks);
    return($template, $message);
}

# everything from this point down deals with the
# sending of email reminders.
# above is the web interface

######
# monthly reminders
######
sub monthlyReminders {
    my $day_of_month = $_[0];
    my $select="SELECT email, reminder, account_number, reminder_type, id 
    FROM reminders 
    WHERE reminder_type = 'monthly' 
    AND trigger_day = DAYOFMONTH(NOW())";
    my $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($recipient, $reminder, $account_number, $reminder_type, $id) = $sth->fetchrow_array()) {
        &sendReminder($recipient, $reminder, $reminder_type, $account_number);
    }
    $sth->finish();
}

######
# one-time reminders
######
sub oneTimeReminders {
    my $select="SELECT email, reminder, account_number, reminder_type, id 
    FROM reminders 
    WHERE reminder_type = 'one-time' 
    AND trigger_day = DAYOFMONTH(NOW()) 
    AND trigger_month = MONTHNAME(NOW()) 
    AND trigger_year = YEAR(now())";
    my $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($recipient, $reminder, $account_number, $reminder_type, $id) = $sth->fetchrow_array()) {
        sendReminder($recipient, $reminder, $reminder_type, $account_number);
    }
}


######
# send mail
######

# expects:  $recipient, $reminder, $reminder_type 
# and optional $account_number
sub sendReminder {
    my $recipient = $_[0];
    my $reminder = $_[1];
    my $reminder_type = $_[2];
    my $account_number = $_[3];
    if ($reminder eq "EXECUTE_AUTHOR_NOTICES") {
        system("~/www/cgi-bin/mmpublisher/private/author_notices.pl");
    }
    if ($reminder eq "EXECUTE_REC_ARTIST_NOTICES") {
        system("~/www/cgi-bin/mmpublisher/private/rec_artist_notices.pl");
    }
    # shorten reminder to fit in subject line - 40 characters
    my $short_reminder = substr($reminder, 0, 40);
    # strip any line breaks (replace with spaces) as they falsely signal the end of the subject line
    $short_reminder =~ s/\n/ /g;
    # add elipses
    $short_reminder .= "...";           # see if this is a business reminder by the presence of an account number
    # bring in client data if appropriate
    my $contacts;
    my $client_name;
    my $client_address;
    my $client_email;
    unless (($account_number eq "0") || ($account_number eq "")) {
        # this is a business reminder, so grab info from the 
        # client table based on the account number  
        my $select="SELECT name FROM clients WHERE id = '$account_number'";
        my $sth = $dbh->prepare($select);
        $sth->execute();
        ($client_name) = $sth->fetchrow_array();
        $sth->finish();
        # get any related individual contacts
        $select="SELECT last_name, first_name, home_phone, business_phone, cellphone, street, city, state, zip, email, id FROM contacts WHERE client_id = '$account_number'";
        $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        my $counter = 0;
        while (my ($last_name, $first_name, $home_phone, $business_phone, $cellphone, $street, $city, $state, $zip, $email, $contact_id) = $sth->fetchrow_array()) {
            $contacts .= qq {<br>$first_name $last_name<br>};
            if ($email) {$contacts .= qq {<a href="mailto:$email">$email</a>};}
            if ($home_phone) {$contacts .= qq {<br>home phone: $home_phone</a>};}
            if ($business_phone) {$contacts .= qq {<br>business phone: $business_phone</a>};}
            if ($cellphone) {$contacts .= qq {<br>cellphone: $cellphone</a>};}
            if ($street) {$contacts .= qq {<br>$street};}
            if (($city) && ($state)) {$contacts .= qq {<br>$city, $state};}
            if ($zip) {$contacts .= qq {<br>$zip};}
        }
    }
    ######
    # mail confirmation
    ######
    # point to mail program
    my $mailprog = '/usr/sbin/sendmail';
    # this opens an output stream and pipes it directly to the 
    # sendmail program.  If sendmail can't be found, abort 
    # by calling the dienice subroutine
    open (MAIL, "|$mailprog -t") or dienice("Can't access $mailprog!\n");
    # print recipient to mail header
    print MAIL "From: reminders\@mindmined.com\n";
    print MAIL "To: $recipient\n";
    print MAIL "Cc: marcus\@mindmined.com\n";
    # print out a subject line.
    # The two \n\n's end the header section of the message.  
    # anything you print after this point will be part of the 
    # body of the mail.
    print MAIL "Subject: $short_reminder\n";
    print MAIL "Content-type: text/html\n\n";
    my $account_num_html = '';
    if ($account_number) {
        $account_num_html = qq {
Account Number: <b>$account_number</b><br>
Client: <b>$client_name</b><br>
<hr>
Contacts:<br><br>
$contacts
        };
    }
    # print body of mail message
    print MAIL qq {
$reminder_type reminder<br><br>
<font color="red">$reminder</font><br><br>
$account_num_html
    };
    # close the input stream so it actually gets mailed.
    close(MAIL);
}


######
# weekly reminders
######
sub weeklyReminders {
    my $select="SELECT email, reminder, reminder_type, account_number, id 
    FROM reminders 
    WHERE reminder_type = 'weekly' 
    AND trigger_weekday = DAYOFWEEK(NOW())";
    my $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($recipient, $reminder, $reminder_type, $account_number, $id) = $sth->fetchrow_array()) {
        sendReminder($recipient, $reminder, $reminder_type, $account_number);
    }
}

=head2 yearly reminders

TODO

=cut

sub yearlyReminders {
    my $select = <<~"SQL";
    SELECT email, reminder, account_number, reminder_type, id 
    FROM reminders 
    WHERE reminder_type = 'yearly' 
    AND trigger_day = DAYOFMONTH(NOW()) 
    AND trigger_month = MONTHNAME(NOW())
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($recipient, $reminder, $account_number, $reminder_type, $id) = $sth->fetchrow_array()) {
        sendReminder($recipient, $reminder, $reminder_type, $account_number);
    }
}


=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


