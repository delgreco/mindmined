#!/usr/bin/perl -w

# use strict, warnings and modern features
use 5.030;

use lib qw (
    ../lib
    .
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

use MindMined;

my $debug = 0;

if ( @ARGV ) { 
    $ARGV[0] =~ s/-//;  # remove dash from option
    my $action = $ARGV[0];
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
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my ($id, $image_title, $image_URL, $artist_id) = $sth->fetchrow_array();
    $select = <<~"SQL";
    SELECT first_name, last_name, dir 
    FROM artists 
    WHERE id = ?
    SQL
    $sth = $MindMined::dbh->prepare($select);
    $sth->execute($artist_id);
    my ($first_name, $last_name, $dir) = $sth->fetchrow_array();
    $index_template->param(ARTIST => "$first_name $last_name");
    $index_template->param(ARTIST_URL => "/gallery/$dir");
    $index_template->param(GALLERY_IMAGE_URL => $image_URL);

    # artist of the day standalone file 
    my $template = HTML::Template->new(
        filename => "$MindMined::template_path/daily_features/daily_artist.tmpl",
    ) || die "oops $!";
    $template->param(ARTIST_URL => "/gallery/$dir");
    $template->param(ARTIST => "$first_name $last_name");
    $template->param(GALLERY_IMAGE_URL => "$image_URL");
    my $file = "$MindMined::template_path/daily_features/today_artist.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    return $index_template;
}

=head2 dailyBatch()

Refresh daily features.

=cut

sub dailyBatch {
    makeDailyFeaturesTemplate();
    recArtistOfTheDay();
    releaseOfTheDay();
    MindMined::batchTrackList();  # has a track-of-the-day panel
    makeOtherPages();
    my $datetime = `date`;
    chomp($datetime);
    unless ( $ENV{CRON} ) {
        print "$datetime, daily.pl: Daily features template refreshed.\n";
        print "Others refreshed too.\n";
        print "Run news.cgi --refresh to update these to the homepage.\n";
    }
}

=head2 makeDailyFeaturesTemplate()

TODO

=cut

# this is a page of raw html to incorporate into index.html, which will refresh more frequently
sub makeDailyFeaturesTemplate {
    my $t = HTML::Template->new(filename => "$MindMined::template_path/daily_features/daily.tmpl") || die "oops $!";
    $t = trackOfTheDay($t);  
    $t = titleOfTheDay($t);   
    $t = artistOfTheDay($t);     
    $t = productOfTheDay($t); 
    open(TODAY, "> $MindMined::template_path/daily_features/today.html") || die "$MindMined::template_path/daily_features/today.html, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 makeOtherPages()

TODO

=cut

sub makeOtherPages {
    # subscribe page
    # my $subscribe_template = HTML::Template->new(filename => "$MindMined::template_path/subscribe.tmpl");
    # $subscribe_template->param(PAGETITLE => "Subscribe to the Mind Mined Newsletter");
    # $subscribe_template->param(DESCRIPTION => "Our email newsletter is sent every now and again.  We prefer you to subscribe to our RSS feed for free syndicated content.");
    # $subscribe_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    # open(SUB_PAGE, "> $MindMined::doc_root/subscribe.html");
    # my $output = $subscribe_template->output;
    # print SUB_PAGE "$output";
    # close(SUB_PAGE);
    
    # unsubscribe page
    # my $unsubscribe_template = HTML::Template->new(filename => "$MindMined::template_path/unsubscribe.tmpl");
    # $unsubscribe_template->param(PAGETITLE => 'Unsubscribe to the Mind Mined Newsletter');
    # $unsubscribe_template->param(DESCRIPTION => "We'll be glad to stop emailing you-- just say so.");
    # $unsubscribe_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    # open(UNSUB_PAGE, "> $MindMined::doc_root/unsubscribe.html");
    # $output = $unsubscribe_template->output;
    # print UNSUB_PAGE "$output";
    # close(UNSUB_PAGE);
    
    # "Contact Us" page
    my $contact_template = HTML::Template->new(filename => "$MindMined::template_path/contact/index.tmpl");
    $contact_template->param(PAGETITLE => 'Contact Mind Mined Productions');
    $contact_template->param(DESCRIPTION => 'Welcome to Mind Mined, a multimedia production and publishing company where creative content is king.');
    $contact_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    open(CONTACT_PAGE, "> $MindMined::doc_root/contact/index.html");
    my $output = $contact_template->output;
    print CONTACT_PAGE "$output";
    close(CONTACT_PAGE);

    # "Preferences" page
    my $prefs_template = HTML::Template->new(filename => "$MindMined::template_path/preferences.tmpl");
    $prefs_template->param(PAGETITLE => 'Mind Mined Productions: User Preferences');
    $prefs_template->param(DESCRIPTION => 'Select personal preferences such as Dark Mode.');
    $prefs_template->param(KEYWORDS => 'audio downloads, multimedia production, original fiction, nonfiction, plays, poetry, CDs, mp3 downloads, web development services, New Hampshire music studios, online gallery');
    $prefs_template->param(SHOW_EDITOR_LINK => 1);
    open(CONTACT_PAGE, "> $MindMined::doc_root/preferences.html");
    $output = $prefs_template->output;
    print CONTACT_PAGE "$output";
    close(CONTACT_PAGE);
}


=head2 productOfTheDay()

Given a template object, return that object populated with data for a 
Product of the Day.

=cut

sub productOfTheDay {
    my $index_template = $_[0];
    my $select = <<~"SQL";
    SELECT product, product_id, description, price, product_image_URL, 
    product_URL, product_type, id 
    FROM products 
    ORDER BY RAND()
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my ($product, $product_id, $description, $price, $product_image_URL, 
        $product_URL, $product_type, $id) = $sth->fetchrow_array();
    $index_template->param(PRODUCT_URL => $product_URL);
    $index_template->param(PRODUCT => $product);
    $index_template->param(PRODUCT_DESCRIPTION => $description);
    $index_template->param(PRODUCT_URL => $product_URL);
    $index_template->param(PRODUCT_IMAGE_URL => $product_image_URL);    
    return $index_template;
}

=head2 recArtistOfTheDay()

Prepare a fresh "Recording Artist of the Day" html file for inclusion in the 
Recording Artists index.

=cut

sub recArtistOfTheDay { 
    my $select = <<~"SQL";
    SELECT name, dir, image_url
    FROM rec_artists
    ORDER BY RAND()
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my ($rec_artist, $rec_artist_dir, $image_url) = $sth->fetchrow_array();
    # standalone file 
    my $t = HTML::Template->new(
        filename => "$MindMined::template_path/daily_features/daily_rec_artist.tmpl"
    ) || die "oops $!";
    $t->param(REC_ARTIST => $rec_artist);
    $t->param(REC_ARTIST_URL => "/audiofun/${rec_artist_dir}/");
    $t->param(REC_ARTIST_IMAGE_URL => $image_url);
    my $path = "$MindMined::template_path/daily_features/today_rec_artist.html";
    open(TODAY, "> $path") || die "$path, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 releaseOfTheDay()

Prepare a fresh "Release of the Day" html file for inclusion in the Releases 
index.

=cut

sub releaseOfTheDay {   
    my $select = <<~"SQL";
    SELECT `release`, rec_artist, rel.image_url, filename, year, ra.name, ra.dir
    FROM releases AS rel
    LEFT JOIN rec_artists AS ra
    ON rel.rec_artist = ra.id
    ORDER BY RAND()
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my ($release, $rec_artist_id, $image_url, $filename, $year, $rec_artist, 
        $rec_artist_dir) = $sth->fetchrow_array();
    # standalone file 
    my $t = HTML::Template->new(
        filename => "$MindMined::template_path/daily_features/daily_release.tmpl"
    ) || die "oops $!";
    $t->param(RELEASE => "$release");
    $t->param(RELEASE_URL => "/audiofun/${rec_artist_dir}/${filename}");
    $t->param(RELEASE_IMAGE_URL => $image_url);
    $t->param(REC_ARTIST => $rec_artist);
    $t->param(REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    my $path = "$MindMined::template_path/daily_features/today_release.html";
    open(TODAY, "> $path") || die "$path, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
}

=head2 trackOfTheDay()

Prepare a fresh "Track of the Day" html file for inclusion in the Tracks
index.

=cut

sub trackOfTheDay { 
    my $index_template = $_[0];
    my @random = ('1', '2');
    my $select = <<~"SQL";
    SELECT title, url, length, mediatype, bitrate, release_id
    FROM tracks 
    WHERE published = 1
    ORDER BY RAND()
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my $title; my $url; my $length;
    my $mediatype; my $bitrate; my $release; my $release_id;
    my $rec_artist_id; my $image_url; my $filename; my $year;
    my $rec_artist; my $rec_artist_dir;
    while (($title, $url, $length, $mediatype, $bitrate, $release_id) = $sth->fetchrow_array()) {
        my $rand = rand @random;
        my $select = <<~"SQL";
        SELECT `release`, rec_artist, image_url, filename, year 
        FROM releases 
        WHERE id = '$release_id'
        SQL
        my $sth = $MindMined::dbh->prepare($select);
        $sth->execute;
        ($release, $rec_artist_id, $image_url, $filename, $year) = $sth->fetchrow_array();
        # select a Cozmik track of the day a little less often
        if ( ($random[$rand] eq "1") && ($rec_artist_id == 1) ) {  
            next;
        }
        my $success = 1;
        $select = <<~"SQL";
        SELECT name, dir 
        FROM rec_artists 
        WHERE id = ?
        SQL
        $sth = $MindMined::dbh->prepare($select);
        $sth->execute($rec_artist_id);
        ($rec_artist, $rec_artist_dir) = $sth->fetchrow_array();
        if ( $success eq "1" ) {
            last;
        }
    }
    $index_template->param(RELEASE_IMAGE_URL => $image_url);
    $index_template->param(TRACK_TITLE => $title);
    $index_template->param(TRACK_URL => $url);
    $index_template->param(TRACK_REC_ARTIST => $rec_artist);
    $index_template->param(TRACK_REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    # track of the day standalone file 
    my $t = HTML::Template->new(filename => "$MindMined::template_path/daily_features/daily_track.tmpl") || die "oops $!";
    $t->param(RELEASE_URL => "/audiofun/${rec_artist_dir}/${filename}");
    $t->param(RELEASE_IMAGE_URL => $image_url);
    $t->param(TRACK_TITLE => $title);
    $t->param(TRACK_URL => $url);
    $t->param(TRACK_REC_ARTIST => $rec_artist);
    $t->param(TRACK_REC_ARTIST_URL => "/audiofun/$rec_artist_dir");
    my $file = "$MindMined::template_path/daily_features/today_track.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $t->output;
    print TODAY "$output";
    close(TODAY);
    return $index_template;
}

=head2 titleOfTheDay()

Prepare a fresh "Title of the Day" html file for inclusion in other pages.

=cut

sub titleOfTheDay {
    my $index_template = $_[0];
    my $select = <<~"SQL";
    SELECT pagetitle, genre, image_URL, description, filename, author_id, id, 
    image_alt_text, keywords 
    FROM titles 
    WHERE genre <> 'erotic_fiction' 
    AND published = 'yes'
    ORDER BY RAND()
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute();
    my ($pagetitle, $genre, $image_URL, $description, $filename, $author_id, $id, $image_alt_text, $keywords) = $sth->fetchrow_array();

    # grab information about the author
    $select = <<~"SQL";
    SELECT last_name, first_name 
    FROM authors 
    WHERE id = ?
    SQL
    $sth = $MindMined::dbh->prepare($select);
    $sth->execute($author_id);
    my ($last_name, $first_name) = $sth->fetchrow_array();
    $index_template->param(TITLE_URL => "/public_library/$genre/$filename");
    $index_template->param(TITLE => $pagetitle);    
    $index_template->param(AUTHOR => "$first_name $last_name");
    $index_template->param(TITLE_DESCRIPTION => $description);
    $index_template->param(TITLE_ALT => $image_alt_text);
    $index_template->param(TITLE_IMAGE_URL => $image_URL);

    # title of the day standalone file 
    my $template = HTML::Template->new(filename => "$MindMined::template_path/daily_features/daily_title.tmpl") || die "oops $!";
    $template->param(TITLE => $pagetitle);
    $template->param(TITLE_URL => "/public_library/$genre/$filename");
    $template->param(AUTHOR => "$first_name $last_name");
    $template->param(TITLE_DESCRIPTION => $description);
    $template->param(TITLE_ALT => $image_alt_text);
    $template->param(TITLE_IMAGE_URL => $image_URL);
    my $file = "$MindMined::template_path/daily_features/today_title.html";
    open(TODAY, "> $file") || die "$file, $!";
    my $output = $template->output;
    print TODAY "$output";
    close(TODAY);
    return $index_template;
}


