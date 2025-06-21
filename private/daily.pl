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

use open qw( :std :encoding(UTF-8) );

# force templates to be read as UTF-8
HTML::Template->config(utf8 => 1);

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

my $debug = 0;

my $doc_root = "/home/mindmine/www";
my $template_path = "$doc_root/cgi-bin/private/templates";

if ( @ARGV ) { 
    $ARGV[0] =~ s/-//;  # remove dash from option
    my $action = $ARGV[0];
    open(LOG, ">> $doc_root/cron.log");
    &{\&{$action}}();  # call the proper sub and exit when done
} 
else {
    print STDOUT "usage: daily.pl -dailyBatch\n";
}

=head2 artistOfTheDay()

TODO

=cut

sub artistOfTheDay {
    my $index_template = $_[0];
    my $select = <<~"SQL";
    SELECT id, title, url, artist_id 
    FROM gallery 
    ORDER BY RAND()
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute;
    my ($id, $image_title, $image_URL, $artist_id) = $sth->fetchrow_array();
    $select = <<~"SQL";
    SELECT first_name, last_name, dir 
    FROM artists 
    WHERE id = ?
    SQL
    $sth = $dbh->prepare($select);
    $sth->execute($artist_id);
    my ($first_name, $last_name, $dir) = $sth->fetchrow_array();
    $index_template->param(ARTIST => "$first_name $last_name");
    $index_template->param(ARTIST_URL => "/gallery/$dir");
    $index_template->param(GALLERY_IMAGE_URL => $image_URL);

    # artist of the day standalone file 
    my $template = HTML::Template->new(filename => "$template_path/daily_features/daily_artist.tmpl") || die "oops $!";
    $template->param(ARTIST_URL => "/gallery/$dir");
    $template->param(ARTIST => "$first_name $last_name");
    $template->param(GALLERY_IMAGE_URL => "$image_URL");
    my $file = "$template_path/daily_features/today_artist.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    # for index page
    $template->param(HOMEPAGE => 1); # show links to sub-sections
    $file = "$template_path/daily_features/today_artist_index.html";
    open(TODAY, "> $file") || die "$file, $!";
    $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    return $index_template;
}

=head2 batchTrackList()

TODO

=cut

sub batchTrackList {
    my $t = HTML::Template->new(filename => 'templates/audio/tracks.tmpl');
    my $count = 0;
    my $select = <<~"SQL";
    SELECT tracks.title, tracks.url, tracks.length, tracks.mediatype, tracks.bitrate, 
    releases.`release`, releases.filename, ra.name, ra.dir
    FROM tracks
    LEFT JOIN releases
    ON tracks.release_id = releases.id
    LEFT JOIN rec_artists AS ra
    ON releases.rec_artist = ra.id
    WHERE ra.published = 1
    ORDER BY title
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute;
    my @tracks;
    while (my ($title, $url, $length, $mediatype, $bitrate, $release, $filename, $rec_artist, $dir) = $sth->fetchrow_array()) {
        my %row;
        $row{URL} = $url;
        $row{TITLE} = $title;
        $row{LENGTH} = $length;
        $row{DIR} = $dir;
        $row{FILENAME} = $filename;
        #$row{MEDIATYPE} = $mediatype;
        #$row{BITRATE} = $bitrate;
        $row{RELEASE} = $release;
        $row{REC_ARTIST} = $rec_artist;
        push(@tracks, \%row);
        $count++;
    }
    $t->param(TRACKS => \@tracks);
    $t->param(TOTAL => $count);
    $t->param(PAGETITLE => 'Complete audio tracks available on mindmined.com');
    $t->param(DESCRIPTION => "$count tracks, most in mp3 format, downloadable for free on mindmined.com.");
    $t->param(KEYWORDS => 'recording artists,podsafe music,free mp3s,download mp3s,bands');
    $t->param(WINDOW_STATUS => 'Obtain permission before using tracks for any purpose other than your listening pleasure.');
    my $output = $t->output;
    open(INDEX_PAGE, "> $doc_root/audio/alpha_by_track.html");
    print INDEX_PAGE "$output";
    close INDEX_PAGE;
}

=head2 dailyBatch()

TODO

=cut

sub dailyBatch {
    makeDailyFeaturesTemplate();
    recArtistOfTheDay();
    releaseOfTheDay();
    batchTrackList();  # has a track-of-the-day panel
    makeOtherPages();
    
    my $datetime = `date`;
    chomp($datetime);
    print LOG qq |$datetime, daily.cgi: Daily features template refreshed, others refreshed too.  Run news.cgi --refresh to update these to the homepage.
| if $debug;
}


=head2 dailyBatch()

TODO

=cut

# this is a page of raw html to incorporate into index.html, which will refresh more frequently
sub makeDailyFeaturesTemplate {
    my $t = HTML::Template->new(filename => "$template_path/daily_features/daily.tmpl") || die "oops $!";
    $t = trackOfTheDay($t);  
    $t = titleOfTheDay($t);   
    $t = artistOfTheDay($t);     
    $t = productOfTheDay($t); 
    open(TODAY, "> $template_path/daily_features/today.html") || die "$template_path/daily_features/today.html, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 makeOtherPages()

TODO

=cut

sub makeOtherPages {
    # subscribe page
    # my $subscribe_template = HTML::Template->new(filename => "$template_path/subscribe.tmpl");
    # $subscribe_template->param(PAGETITLE => "Subscribe to the Mind Mined Newsletter");
    # $subscribe_template->param(DESCRIPTION => "Our email newsletter is sent every now and again.  We prefer you to subscribe to our RSS feed for free syndicated content.");
    # $subscribe_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    # open(SUB_PAGE, "> $doc_root/subscribe.html");
    # my $output = $subscribe_template->output;
    # print SUB_PAGE "$output";
    # close(SUB_PAGE);
    
    # unsubscribe page
    # my $unsubscribe_template = HTML::Template->new(filename => "$template_path/unsubscribe.tmpl");
    # $unsubscribe_template->param(PAGETITLE => 'Unsubscribe to the Mind Mined Newsletter');
    # $unsubscribe_template->param(DESCRIPTION => "We'll be glad to stop emailing you-- just say so.");
    # $unsubscribe_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    # open(UNSUB_PAGE, "> $doc_root/unsubscribe.html");
    # $output = $unsubscribe_template->output;
    # print UNSUB_PAGE "$output";
    # close(UNSUB_PAGE);
    
    # "Contact Us" page
    my $contact_template = HTML::Template->new(filename => "$template_path/contact/index.tmpl");
    $contact_template->param(PAGETITLE => 'Contact Mind Mined Productions');
    $contact_template->param(DESCRIPTION => 'Welcome to Mind Mined, a multimedia production and publishing company where creative content is king.');
    $contact_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    open(CONTACT_PAGE, "> $doc_root/contact/index.html");
    my $output = $contact_template->output;
    print CONTACT_PAGE "$output";
    close(CONTACT_PAGE);

    # "Preferences" page
    my $prefs_template = HTML::Template->new(filename => "$template_path/preferences.tmpl");
    $prefs_template->param(PAGETITLE => 'Mind Mined Productions: User Preferences');
    $prefs_template->param(DESCRIPTION => 'Select personal preferences such as Dark Mode.');
    $prefs_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    $prefs_template->param(SHOW_EDITOR_LINK => 1);
    open(CONTACT_PAGE, "> $doc_root/preferences.html");
    $output = $prefs_template->output;
    print CONTACT_PAGE "$output";
    close(CONTACT_PAGE);
}


=head2 productOfTheDay()

TODO

=cut

sub productOfTheDay {
    my $index_template = $_[0];
    my $select = <<"SQL";
    SELECT product, product_id, description, price, product_image_URL, product_URL, product_type, id 
    FROM products 
    ORDER BY RAND()
SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($product, $product_id, $description, $price, $product_image_URL, $product_URL, $product_type, $id) = $sth->fetchrow_array();
    $index_template->param(PRODUCT_URL => $product_URL);
    $index_template->param(PRODUCT => $product);
    $index_template->param(PRODUCT_DESCRIPTION => $description);
    $index_template->param(PRODUCT_URL => $product_URL);
    $index_template->param(PRODUCT_IMAGE_URL => $product_image_URL);    
    return  $index_template;
}

=head2 recArtistOfTheDay()

TODO

=cut

sub recArtistOfTheDay { 
    my $select = <<"SQL";
    SELECT name, dir, image_url
    FROM rec_artists
    ORDER BY RAND()
SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($rec_artist, $rec_artist_dir, $image_url) = $sth->fetchrow_array();
    #if ( ( $random[$rand] eq '1' ) && ( $rec_artist_id == 1 ) ) { 
        # selecting a Cozmik track of the day a little less often
    #    next;
    #}
    # standalone file 
    my $t = HTML::Template->new(filename => "$template_path/daily_features/daily_rec_artist.tmpl") || die "oops $!";
    $t->param(REC_ARTIST => $rec_artist);
    $t->param(REC_ARTIST_URL => "/audiofun/${rec_artist_dir}/");
    $t->param(REC_ARTIST_IMAGE_URL => $image_url);
    my $path = "$template_path/daily_features/today_rec_artist.html";
    open(TODAY, "> $path") || die "$path, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 releaseOfTheDay()

TODO

=cut

sub releaseOfTheDay {   
    my $select = <<"SQL";
    SELECT `release`, rec_artist, rel.image_url, filename, year, ra.name, ra.dir
    FROM releases AS rel
    LEFT JOIN rec_artists AS ra
    ON rel.rec_artist = ra.id
    ORDER BY RAND()
SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($release, $rec_artist_id, $image_url, $filename, $year, $rec_artist, $rec_artist_dir) = $sth->fetchrow_array();
    #if ( ( $random[$rand] eq '1' ) && ( $rec_artist_id == 1 ) ) { 
        # selecting a Cozmik track of the day a little less often
    #    next;
    #}
    # standalone file 
    my $t = HTML::Template->new(filename => "$template_path/daily_features/daily_release.tmpl") || die "oops $!";
    $t->param(RELEASE => "$release");
    $t->param(RELEASE_URL => "/audiofun/${rec_artist_dir}/${filename}");
    $t->param(RELEASE_IMAGE_URL => $image_url);
    $t->param(REC_ARTIST => $rec_artist);
    $t->param(REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    my $path = "$template_path/daily_features/today_release.html";
    open(TODAY, "> $path") || die "$path, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 trackOfTheDay()

TODO

=cut

sub trackOfTheDay { 
    my $index_template = $_[0];
    my @random = ('1', '2');
    my $select = <<"SQL";
    SELECT title, url, length, mediatype, bitrate, release_id
    FROM tracks 
    WHERE published = 1
    ORDER BY RAND()
SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my $title; my $url; my $length;
    my $mediatype; my $bitrate; my $release; my $release_id;
    my $rec_artist_id; my $image_url; my $filename; my $year;
    my $rec_artist; my $rec_artist_dir;
    while (($title, $url, $length, $mediatype, $bitrate, $release_id) = $sth->fetchrow_array()) {
        my $rand = rand @random;
        my $select = <<"SQL";
        SELECT `release`, rec_artist, image_url, filename, year 
        FROM releases 
        WHERE id = '$release_id'
SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        ($release, $rec_artist_id, $image_url, $filename, $year) = $sth->fetchrow_array();
        if (($random[$rand] eq "1") && ($rec_artist_id == 1)) {  # selecting a Cozmik track of the day a little less often
            next;
        }
        my $success = 1;
        $select = <<"SQL";
        SELECT name, dir 
        FROM rec_artists 
        WHERE id = '$rec_artist_id'
SQL
        $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        ($rec_artist, $rec_artist_dir) = $sth->fetchrow_array();
        if ( $success eq "1" ) {
            last;
        }
    }
    $index_template->param(RELEASE_IMAGE_URL => $image_url);
    $index_template->param(TRACK_TITLE => $title);
    $index_template->param(TRACK_URL => $url);
    $index_template->param(TRACK_MEDIATYPE => $mediatype);
    $index_template->param(TRACK_BITRATE => $bitrate);
    $index_template->param(TRACK_LENGTH => $length);
    $index_template->param(TRACK_REC_ARTIST => $rec_artist);
    $index_template->param(TRACK_REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    #$index_template->param(HOMEPAGE => 1); # show links to sub-sections
    # track of the day standalone file 
    my $t = HTML::Template->new(filename => "$template_path/daily_features/daily_track.tmpl") || die "oops $!";
    $t->param(RELEASE_URL => "/audiofun/${rec_artist_dir}/${filename}");
    $t->param(RELEASE_IMAGE_URL => $image_url);
    $t->param(TRACK_TITLE => $title);
    $t->param(TRACK_URL => $url);
    $t->param(TRACK_MEDIATYPE => $mediatype);
    $t->param(TRACK_BITRATE => $bitrate);
    #$t->param(TRACK_LENGTH => $length);
    $t->param(TRACK_REC_ARTIST => $rec_artist);
    $t->param(TRACK_REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    my $file = "$template_path/daily_features/today_track.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
    # for index page
    $t->param(HOMEPAGE => 1); # show links to sub-sections
    $file = "$template_path/daily_features/today_track_index.html";
    open(TODAY, "> $file") || die "$file, $!";
    $output = $t->output;
    print TODAY "$output";
    close(TODAY);

    return $index_template;
}

=head2 titleOfTheDay()

TODO

=cut

sub titleOfTheDay {
    my $index_template = $_[0];
    my $select = <<"SQL";
    SELECT pagetitle, genre, image_URL, description, filename, author_id, id, image_alt_text, keywords 
    FROM titles 
    WHERE genre <> 'erotic_fiction' 
    AND published = 'yes'
    ORDER BY RAND()
SQL
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my ($pagetitle, $genre, $image_URL, $description, $filename, $author_id, $id, $image_alt_text, $keywords) = $sth->fetchrow_array();
    # grab information about the author
    $select = <<"SQL";
    SELECT last_name, first_name 
    FROM authors 
    WHERE id = '$author_id'
SQL
    $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my ($last_name, $first_name) = $sth->fetchrow_array();
    $index_template->param(TITLE_URL => "/public_library/$genre/$filename");
    $index_template->param(TITLE => $pagetitle);    
    $index_template->param(AUTHOR => "$first_name $last_name");
    $index_template->param(TITLE_DESCRIPTION => $description);
    $index_template->param(TITLE_ALT => $image_alt_text);
    $index_template->param(TITLE_IMAGE_URL => $image_URL);

    # title of the day standalone file 
    my $template = HTML::Template->new(filename => "$template_path/daily_features/daily_title.tmpl") || die "oops $!";
    $template->param(TITLE => $pagetitle);
    $template->param(TITLE_URL => "/public_library/$genre/$filename");
    $template->param(AUTHOR => "$first_name $last_name");
    $template->param(TITLE_DESCRIPTION => $description);
    $template->param(TITLE_ALT => $image_alt_text);
    $template->param(TITLE_IMAGE_URL => $image_URL);
    my $file = "$template_path/daily_features/today_title.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    # for index page
    $template->param(HOMEPAGE => 1); # show links to sub-sections
    $file = "$template_path/daily_features/today_title_index.html";
    open(TODAY, "> $file") || die "$file, $!";
    $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    return $index_template;
}



