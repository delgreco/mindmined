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
use HTML::Entities;
use HTML::Template;
use Dotenv -load;

use FatalsToEmail qw(
    Mailhost localhost
    Address marcusdelgreco@gmail.com
    Error_cache /tmp/library.tmp
    Seconds 60
    Debug 1
);

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

HTML::Template->config(utf8 => 1);

my $debug = 0;

my $cgiobject = new CGI;
my $action=$cgiobject->param("action");

if ( @ARGV && $ARGV[0] eq "--refresh" ) {
    # when called this way, we need to manually define doc root
    $ENV{DOCUMENT_ROOT} = "$ENV{HOME}/www";
    open(LOG, ">> $ENV{HOME}/cron.log");
    refreshNews('command_line_call');
    exit;
} 

$action = 'mainInterface' if ! $action;
&{\&{$action}}();


=head2 assembleNewsletter()

TODO

=cut

sub assembleNewsletter {
    my $month = $cgiobject->param('month');
    my $year = $cgiobject->param('year');
    my $number = $cgiobject->param('number');
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_URL, newsbit_image_URL, category, `datetime` 
    FROM news 
    WHERE newsletter_status = 'pending'
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my $library; my $gallery; my $audio; my $theatre; my $other;
    while (my ($newsbit, $newsbit_URL, $newsbit_image_URL, $category, $datetime) = $sth->fetchrow_array()) {
        if ($category eq 'library') {$library .= "$newsbit\n$newsbit_URL\n\n"}
        elsif ($category eq 'audiofunhouse')  {$audio .= "$newsbit\n$newsbit_URL\n\n"}
        elsif ($category eq 'gallery')  {$gallery .= "$newsbit\n$newsbit_URL\n\n"}
        elsif ($category eq 'theatre')  {$theatre .= "$newsbit\n$newsbit_URL\n\n"}
        else {$other .= "$newsbit\n$newsbit_URL\n\n"};
    }
    # this is just a plain text newsletter but HTML::Template can still be used
    my $t = HTML::Template->new(filename => 'templates/news/email_newsletter.tmpl');
    $t->param(ISSUE_NUM => $number);
    $t->param(MONTH => $month);
    $t->param(YEAR => $year);
    $t->param(LIBRARY => $library);
    $t->param(AUDIO => $audio);
    $t->param(GALLERY => $gallery);
    $t->param(THEATRE => $theatre);
    $t->param(OTHER => $other);
    my $body = $t->output;
    my $insert="INSERT INTO newsletters (month, year, number, body) VALUES (?, ?, ?, ?)";
    $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
    $sth->execute($month, $year, $number, $body) || die "execute: $insert: $DBI::errstr";
    # rebuild newsletter index
    refreshNewsletterIndex();
    # set all newsbit in database to status 'sent'
    my $update="UPDATE news SET newsletter_status = 'sent'";
    $sth = $dbh->prepare($update);
    $sth->execute() || die "sth->execute($update): $DBI::errstr\n";
    my $message = 'Latest newsletter has been assembled.';
    mainInterface($message);
}

=head2 deleteNewsbit()

Given the id for a newsbit, delete it.

=cut

sub deleteNewsbit {
    my $id=$cgiobject->param('id'); 
    my $select = <<~"SQL";
    SELECT newsbit 
    FROM news 
    WHERE id = ?
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute($id);
    my ($newsbit) = $sth->fetchrow_array();
    # keep it short
    $newsbit = substr($newsbit, 0, 20);
    $newsbit .= '...';
    # delete the entry
    my $sql = <<~"SQL";
    DELETE FROM news WHERE id = ?
    SQL
    my $rows_deleted = $dbh->do(qq{$sql}, undef, $id);
    if ( $rows_deleted != 1 ) {
        print STDERR "ERROR: $rows_deleted rows deleted.";
    }
    my $message = "$newsbit deleted from the database.";
    mainInterface($message);
}

=head2 mainInterface()

The administrative list view of newsbits.

=cut

sub mainInterface {
    my $message = qq {<font color="red">$_[0]</font>};
    my $t = HTML::Template->new(filename => 'templates/mmpub/news/mainInterface.tmpl');
    my $newsletter_options;
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_title, newsbit_URL, newsbit_image_URL, category,
    `datetime`, newsletter_status, id 
    FROM news 
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my @newsbits; my $i;
    while (my ($newsbit, $title, $newsbit_url, $newsbit_image_url, $category, $datetime, $newsletter_status, $id) = $sth->fetchrow_array()) {
        my %row;
        my $pending;
        $i++;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = '#EEEEEE';
        }
        else { 
            $row{BGCOLOR} = '#FFFFFF';
        }
        my $month = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        # keep it shortish
        $newsbit = substr($newsbit, 0, 90);
        $newsbit .= qq {...};
        if ($newsletter_status eq 'pending') {
            $row{PENDING} = 1;   # true
        }
        else {
            $row{NEWSLETTER_STATUS} = $newsletter_status;
        }
        $row{MONTH} = $month;
        $row{DAY} = $day;
        $row{YEAR} = $year;
        $row{ID} = $id;
        $row{MONTH} = $month;
        $row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
        $row{NEWSBIT} = $newsbit;
        $row{TITLE} = $title;
        $row{CATEGORY} = $category;
        #$row{NEWSBIT_URL} = $newsbit_url;
        push(@newsbits, \%row);
    }
    # get newsletters
    $select = <<~"SQL";
    SELECT number, month, year, body FROM newsletters 
    ORDER BY number DESC
    SQL
    $sth = $dbh->prepare($select);
    $sth->execute();
    my @newsletter_options;
    while (my ($number, $month, $year, $body) = $sth->fetchrow_array()) {
        my %row;
        $row{ISSUE_NUM} = $number;
        $row{MONTH} = $month;
        $row{YEAR} = $year;
        push(@newsletter_options, \%row);
    }
    $t->param(NEWSBITS => \@newsbits);
    $t->param(NEWSLETTER_OPTIONS => \@newsletter_options);
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    $t->param(PAGETITLE => 'Mind Mined News Manager');
    $t->param(MESSAGE => $message);
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;
}

=head2 newsbitInterface()

Add or edit a newsbit.

=cut

sub newsbitInterface {
    my $id=$cgiobject->param('id'); 
    my $t = HTML::Template->new(filename => 'templates/mmpub/news/newsbitInterface.tmpl');
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_title, newsbit_URL, newsbit_image_URL, category, `datetime`, published
    FROM news
    WHERE id = ?
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute($id);
    my ($newsbit, $title, $newsbit_url, $newsbit_image_url, $newsbit_category, $datetime, $published) = $sth->fetchrow_array();
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    $t->param(DATETIME => $datetime);
    $t->param(NEWSBIT => $newsbit);
    $t->param(TITLE => $title);
    $t->param(PUBLISHED => $published);
    $t->param(NEWSBIT_URL => $newsbit_url);
    $t->param(NEWSBIT_IMAGE_URL => $newsbit_image_url);
    $t->param(FILENAME => _getNewsbitFilename($title, $datetime));
    $t->param(ID => $id);
    my @categories;
    $select = <<~"SQL";
    SELECT name 
    FROM news_categories
    ORDER BY id
    SQL
    $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($name) = $sth->fetchrow_array()) {
        my %row;
        if ( $name eq $newsbit_category ) { 
            $row{SELECTED} = 1;
        }
        $row{CATEGORY} = $name;
        push(@categories, \%row);
    }
    $t->param(CATEGORIES => \@categories);
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;
}

=head2 newsletterInterface()

Screen to add or edit a newsletter.

=cut

sub newsletterInterface {
    my $number=$cgiobject->param('number'); 
    my $t = HTML::Template->new(filename => 'templates/mmpub/news/newsletterInterface.tmpl');
    my $select = <<~"SQL";
    SELECT month, year, body 
    FROM newsletters 
    WHERE `number` = ?
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute($number);
    my ($month, $year, $body) = $sth->fetchrow_array();
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    $t->param(BODY => $body);
    $t->param(NUMBER => $number);
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;
}

=head2 publishRSS()

Create an RSS file with XML structured data for the latest newsbits.

=cut

sub publishRSS {
    # get current datetime
    my $select_now = <<~"SQL";
    SELECT YEAR(NOW()), DAYOFMONTH(NOW()), DAYNAME(NOW()), MONTHNAME(NOW()), 
    DATE_FORMAT(NOW(), '%H:%i:%s')
    SQL
    my $sth = $dbh->prepare($select_now);
    $sth->execute();
    my ($year, $dayofmonth, $dayname, $monthname, $time) = $sth->fetchrow_array();
    # parse out needed date bits
    $dayname = substr($dayname, 0, 3);
    $dayofmonth = "0$dayofmonth" if (length $dayofmonth == 1);
    $monthname = substr($monthname, 0, 3);
    # contruct channel section
    my $xml = <<~"XML";
    <?xml version="1.0" encoding="UTF-8"?> 
    <rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
    <channel>
    <title>Mind Mined Productions</title>
    <link>https://www.mindmined.com</link>
    <description>News about additions to our independent arts archive.</description>
    <pubDate>$dayname, $dayofmonth $monthname $year $time GMT</pubDate>
    <generator>The Mind Mined Publisher</generator>
    <language>en</language>
    <atom:link href="https://www.mindmined.com/news.xml" rel="self" type="application/rss+xml" />
    XML
    # loop through and replace custom tags with values fetched from database
    my $select_newsbit = <<~"SQL";
    SELECT newsbit, newsbit_title, newsbit_URL, newsbit_image_URL, category, `datetime`, 
    YEAR(`datetime`), DAYOFMONTH(`datetime`), DAYNAME(`datetime`), MONTHNAME(`datetime`), 
    DATE_FORMAT(`datetime`, '%H:%i:%s') 
    FROM news 
    WHERE published = 1
    ORDER BY `datetime` DESC
    SQL
    $sth = $dbh->prepare($select_newsbit);
    $sth->execute();
    my $counter = 0;
    while (my ($newsbit, $title, $newsbit_URL, $newsbit_image_URL, $category, $datetime, $year, $dayofmonth, $dayname, $monthname, $time) = $sth->fetchrow_array()) {
        $counter++;
        # allow the showing of previous feeds on a new subscription
        if ($counter > 6) {last;}
        $dayname = substr($dayname, 0, 3);
        $dayofmonth = "0$dayofmonth" if (length $dayofmonth == 1);
        $monthname = substr($monthname, 0, 3);
        # get a title by trucating the longish newsbit...
        # I guess this is the best we can do unless we start using titles or headlines in the news table
        #my $title = substr($newsbit, 0, 75);
        #$title .= '...';
        # get groovey 12.25.2005 format
        my $month = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        my $groovy_date = qq {$month\.$day\.$year};
        my $filename = _getNewsbitFilename($title, $datetime);
        $title = encode_entities($title);
        # $newsbit = encode_entities($newsbit);
        my $local_url = "https://www.mindmined.com/news/archive/$filename";
        # $newsbit_URL = $local_url unless $newsbit_URL;
        $xml .= <<~"XML";
        <item>
        <title>$title</title>
        <link>https://www.mindmined.com/news/archive/$filename</link>
        <description><![CDATA[<a href="$local_url">$groovy_date</a> - $newsbit ]]></description>
        <pubDate>$dayname, $dayofmonth $monthname $year $time EST</pubDate>
        <category>$category</category>
        <guid>$local_url</guid>
        </item>
        XML
    }
    $xml .= <<~"XML";
    </channel>
    </rss>
    XML
    my $file = "$ENV{DOCUMENT_ROOT}/news.xml";
    open my $feedpage, '>:encoding(utf8)', $file;
    print $feedpage "$xml";
    close $feedpage;
}

=head2 refreshAudioIndex

Refresh the Audio Funhouse homepage with the latest audio newsbits.

=cut

sub refreshAudioIndex {
    my $t = HTML::Template->new(filename => 'templates/audio/index.tmpl');
    my $counter = 0;
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_URL, newsbit_image_URL, category, `datetime`, newsletter_status 
    FROM news 
    WHERE category = 'audiofunhouse' 
    AND published = 1
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my @newsbits;
    while (my ($newsbit, $newsbit_url, $newsbit_image_url, $category, $datetime, $newsletter_status) = $sth->fetchrow_array()) {
        $counter++;
        if ($counter > 3) {last;}
        my %row;
        $row{NEWSBIT} = $newsbit;
        $row{NEWSBIT_IMAGE_URL} = $newsbit_image_url;
        $row{NEWSBIT_URL} = $newsbit_url;
        my $month = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        $row{NEWSBIT_DATETIME} = "${month}.${day}.${year}";
        push(@newsbits, \%row);
    }
    $t->param(NEWSBITS => \@newsbits);
    $t->param(SHOW_EDITOR_LINK => 1);
    my $output = $t->output;
    open(AUDIO_INDEX, ">:encoding(utf8)", "$ENV{DOCUMENT_ROOT}/audio/index.html") or die $!;
    print AUDIO_INDEX "$output";
    close AUDIO_INDEX;
}

=head2 refreshGalleryIndex

Refresh the gallery index page to assure inclusion of latest gallery news items.

=cut

sub refreshGalleryIndex {
    my $t = HTML::Template->new(filename => 'templates/gallery/index.tmpl');
    # reset counter
    my $counter = 0; my @newsbits;
    # loop through and replace custom tags with values fetched from database
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_URL, newsbit_image_URL, datetime 
    FROM news 
    WHERE category = 'gallery' 
    AND published = 1
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    while (my ($newsbit, $newsbit_url, $newsbit_image_url, $datetime) = $sth->fetchrow_array()) {
        my %row;
        $counter++;
        if ($counter > 3) {last;}
        my $month = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        $row{NEWSBIT_URL} = $newsbit_url;
        $row{NEWSBIT_IMAGE_URL} = "$newsbit_image_url";
        $row{NEWSBIT_DATETIME} = "${month}.${day}.${year}";
        $row{NEWSBIT} = $newsbit;
        push(@newsbits, \%row);
    }
    $t->param(NEWSBITS => \@newsbits);
    my $output = $t->output;
    open(GALLERY_INDEX, ">:encoding(utf8)", "$ENV{DOCUMENT_ROOT}/gallery/index.html") or die $!;
    print GALLERY_INDEX "$output";
    close GALLERY_INDEX;
}

=head2 refreshIndex

Keep home page piping hot with news.

=cut

sub refreshIndex {
    my $t = HTML::Template->new(filename => 'templates/index.tmpl');
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_title, newsbit_URL, newsbit_image_URL, category, news_categories.url, news_categories.icon_image_url, datetime, MONTHNAME(datetime)
    FROM news
    JOIN news_categories
    ON news_categories.name = news.category
    WHERE published = 1
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my $counter = 0; my @newsbits;
    while (my ($newsbit, $title, $newsbit_url, $newsbit_image_url, $category, $category_url, $category_icon_url, $datetime, $month) = $sth->fetchrow_array()) {
        my %row;
        $counter++;
        if ($counter > 8) {last;}
        my $monthnum = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        if ( ! $title ) {
            $title = substr($newsbit, 0, 45) . '...';
        }

        my $datetime = "${month} ${day}, ${year}";
        $row{NEWSBIT_URL} = $newsbit_url;
        $row{FILENAME} = _getNewsbitFilename($title, $datetime);
        $row{NEWSBIT_IMAGE_URL} = $newsbit_image_url;
        $row{NEWSBIT_DATETIME} = $datetime;
        # give me a break
        $newsbit =~ s/\n/<br>/g;
        $row{NEWSBIT} = $newsbit;
        push(@newsbits, \%row);
    }
    $t->param(NEWSBITS => \@newsbits);
    $t->param(PAGETITLE => 'Mind Mined Productions');
    $t->param(SHOW_EDITOR_LINK => 1);
    $t->param(DESCRIPTION => "Welcome to Mind Mined, a multimedia production and publishing company where creative content is king.");
    $t->param(KEYWORDS => "audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery");
    my $output = $t->output;
    my $file = "$ENV{DOCUMENT_ROOT}/index.html";
    open my $page, '>:encoding(utf8)', $file;
    print $page "$output";
    close $page;
}

=head2 refreshLibraryIndex

Refresh the Public Library homepage with the latest library news items.

=cut

sub refreshLibraryIndex {
    my $t = HTML::Template->new(filename => 'templates/library/index.tmpl');
    my $counter = 0; my @newsbits;
    # loop through and replace custom tags with values fetched from database
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_URL, newsbit_image_URL, datetime 
    FROM news 
    WHERE category = 'library' 
    AND published = 1
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    while (my ($newsbit, $newsbit_url, $newsbit_image_url, $datetime) = $sth->fetchrow_array()) {
        my %row;
        $counter++;
        if ($counter > 3) {last;}
        my $month = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        my $year = substr($datetime, 0, 4);
        $row{NEWSBIT_URL} =  $newsbit_url;
        $row{NEWSBIT_IMAGE_URL} = $newsbit_image_url;
        $row{NEWSBIT_DATETIME} = "${month}.${day}.${year}";
        $newsbit =~ s/\n/<br>/g;
        $row{NEWSBIT} = $newsbit;
        push(@newsbits, \%row)
    }
    $t->param(NEWSBITS => \@newsbits);
    $t->param(SHOW_EDITOR_LINK => 1);
    my $output = $t->output;
    my $library_index = "$ENV{DOCUMENT_ROOT}/public_library/index.html";
    open(LIBRARY_INDEX, ">:encoding(utf8)", "$library_index") || die("Unable to open file '$library_index': $!");
    print LIBRARY_INDEX "$output";
    close LIBRARY_INDEX;
}

=head2 refreshNews

Main routine that calls all the others to refresh news content across the site.

=cut

sub refreshNews {
    my $command_line_call = $_[0];
    refreshIndex();
    refreshNewsIndex();
    refreshGalleryIndex();
    refreshLibraryIndex();
    refreshAudioIndex();
    publishRSS();
    my $datetime = `date`;
    chomp($datetime);
    if ($command_line_call) {
        print LOG "$datetime, news.cgi: mindmined.com index page, news page, archive indexes and RSS feed have been refreshed.\n" if $debug;
    }
    else {
        my $message = qq |News has been refreshed at news/, library/, audio/, and gallery/.  RSS Feed also refreshed.|;
        mainInterface($message);
    }
}

=head2 refreshNewsIndex

Refresh the list of news items at C<news/index.html>.  

=cut

sub refreshNewsIndex {
    my $template = HTML::Template->new(filename => 'templates/news/index.tmpl');
    my $select = <<~"SQL";
    SELECT newsbit, newsbit_title, newsbit_URL, newsbit_image_URL, category, news_categories.url, 
    news_categories.icon_image_url, datetime, MONTHNAME(`datetime`), published
    FROM news
    LEFT JOIN news_categories
    ON news_categories.name = news.category
    ORDER BY datetime DESC
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute();
    my $counter = 0; my @newsbits;
    while (my ($newsbit, $title, $newsbit_url, $newsbit_image_url, $category, $category_url,  $category_icon_url, $datetime, $month, $published) = $sth->fetchrow_array()) {
        my %row;
        $counter++;
        my $monthnum = substr($datetime, 5, 2);
        my $day = substr($datetime, 8, 2);
        if ( $day =~ m/^0/ ) { # strip leading 0 on day number
            $day =~ s/0//;
        }
        my $year = substr($datetime, 0, 4);
        my $filename = _getNewsbitFilename($title, "${monthnum}.${day}.${year}");
        if ( ! $title ) {
            $title = substr($newsbit, 0, 55) . '...';
        }
        $row{NEWSBIT_TITLE} = $title;
        # give me a break
        $newsbit =~ s/\n/<br>/g;
        my $datetime = "${month} ${day}, ${year}";
        $row{NEWSBIT_DATETIME} = $datetime;
        $row{FILENAME} = $filename;
        push(@newsbits, \%row) if $published;
        # make news archive page, regardless of 'published'
        my $t = HTML::Template->new(filename => 'templates/news/article.tmpl');
        $t->param(NEWSBIT => $newsbit);
        $t->param(NEWSBIT_DATETIME => $datetime);
        $t->param(NEWSBIT_URL => $newsbit_url);
        $t->param(NEWSBIT_IMAGE_URL => $newsbit_image_url);
        $t->param(SHOW_EDITOR_LINK => 1);
        my $output = $t->output;
        open(FINAL, ">:encoding(utf8)", "$ENV{DOCUMENT_ROOT}/news/archive/${filename}") or die $!;
        print FINAL "$output";
        close FINAL;
    }
    $template->param(NEWSBITS => \@newsbits);
    $template->param(SHOW_EDITOR_LINK => 1);
    my $output = $template->output;
    open(FINAL, ">:encoding(utf8)", "$ENV{DOCUMENT_ROOT}/news/index.html") or die $!;
    print FINAL "$output";
    close FINAL;
}

=head2 saveNewsbit()

Add or update a newsbit.

Optionally, upload an image file.  This image will be saved in C<news_images/> directory and the URL will be noted in the newsbit record.  Alternately, the Newsbit Image URL field can be used for an already hosted image.

=cut

sub saveNewsbit {
    my $title=$cgiobject->param('title');
    my $published=$cgiobject->param('published');
    my $newsbit=$cgiobject->param('newsbit');
    my $newsbit_URL=$cgiobject->param('newsbit_URL');
    my $image=$cgiobject->param('image');
    my $newsbit_image_URL=$cgiobject->param('newsbit_image_URL');
    my $category=$cgiobject->param('category'); 
    my $id=$cgiobject->param('id'); 
    $published = $published ? 1 : 0;
    my $message;
    if ( $image ) {
        my $image_dir = "$ENV{DOCUMENT_ROOT}/news_images";
        my $final_filename = ''; my $contents = '';
        my $filename = $image;
        print STDERR "Filename: '$filename'\n";
        $filename =~ s/\s+/_/g;  # substitute whitespaces with underscores
        $filename =~ s/        # substitute...
                    [^\w\.]    # characters which are NOT: "word" characters or periods
                    /_/xg;     # ...with an underscore
        if ( $filename =~ /(.*)/ ) {  # for taint.
            $filename = $1;
        }
        # # prevent duplicate filenames/overwrites
        for ( my $count = 1; -e "$image_dir/$final_filename"; $count++ ) {
            $final_filename = $count . '_' . $filename;
        }
        open (UPLOADFILE, "> $image_dir/$final_filename") or die "$image_dir/$final_filename $!";
        binmode UPLOADFILE;
        if ( $contents ) {
            print UPLOADFILE $contents;
        }
        else {
            my $fh = $cgiobject->param('image');
            while( <$fh> ) {
                print UPLOADFILE;
                $contents .= $_;
            }
        }
        close UPLOADFILE;
        # a new upload overwrites any existing newsbit image URL
        $newsbit_image_URL = "https://mindmined.com/news_images/$final_filename";
    }
    if ( $id ) {  # update existing item
        my $sql = <<~"SQL";
        UPDATE news 
        SET newsbit_title = ?, newsbit = ?, newsbit_URL = ?, newsbit_image_URL = ?, category = ?, published = ?
        WHERE id = ?
        SQL
        my $rows_updated = $dbh->do(qq{$sql}, undef, $title, $newsbit, $newsbit_URL, $newsbit_image_URL, $category, $published, $id);
        if ( $rows_updated != 1 ) {
            print STDERR "ERROR: $rows_updated rows updated.\n";
        }
        $message = qq |Newsbit has been updated.  News pages have been refreshed.|;
    }
    else {   # new item
        my $select = <<~"SQL";
        SELECT NOW()
        SQL
        my $sth = $dbh->prepare($select);
        $sth->execute();
        my ($datetime) = $sth->fetchrow_array();
        # set newsletter status to 'pending'
        my $newsletter_status = 'pending';
        my $sql = <<~"SQL";
        INSERT INTO news 
        (newsbit_title, newsbit, newsbit_URL, newsbit_image_URL, category, datetime, newsletter_status, published) 
        VALUES 
        (?, ?, ?, ?, ?, ?, ?, ?)
        SQL
        my $rows_inserted = $dbh->do(qq{$sql}, undef, $title, $newsbit, $newsbit_URL, $newsbit_image_URL, $category, $datetime, $newsletter_status, $published);
        if ( $rows_inserted != 1 ) {
            print STDERR "ERROR: $rows_inserted rows inserted.\n";
        }
        # grab the automatically incremented id that was generated
        $id = $dbh->{mysql_insertid} || $dbh->{insertid};
        $message = qq |Newsbit has been added linking to <a href="$newsbit_URL">$newsbit_URL</a>.  News pages have been refreshed.|;
    }
    refreshNews();
    mainInterface($message);
}

=head2 saveNewsletter()

TODO

=cut

sub saveNewsletter {  
    my $number=$cgiobject->param('number'); 
    my $month=$cgiobject->param('month'); 
    my $year=$cgiobject->param('year'); 
    my $body=$cgiobject->param('body'); 
    my $message;
    my $sql = <<~"SQL";
    UPDATE newsletters SET body = ? 
    WHERE `number` = ?
    SQL
    my $rows_updated = $dbh->do(qq{$sql}, undef, $body, $number);
    if ( $rows_updated != 1 ) {
        print STDERR "ERROR: $rows_updated rows updated.\n";
    }
    $message = 'Newsletter updated.';
    refreshNews();
    mainInterface($message);
}

=head2 _getNewsbitFilename()

Given the title of the newsbit, return a string suitable for an HTML filename.

    - characters are lowercased
    - spaces are converted to dashes
    - non-ASCII characters are removed

=cut

sub _getNewsbitFilename {
    my $title = $_[0];
    my $datetime = $_[1];
    my $filename = '';
    if ( $title ) {
        $filename = lc($title);
        $filename =~ s/\s+/-/g;
        $filename =~ s/[^[a-zA-Z0-9_-]]*//g;
    }
    # else {  # not sure we ever need this
    #     $filename  = $datetime;
    # }
    return "${filename}.html";
}


