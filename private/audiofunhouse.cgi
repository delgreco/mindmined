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
use HTML::Entities;
use Dotenv -load;

use FatalsToEmail    
  qw(
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

my $cgiobject = new CGI;
# force templates to be read as UTF-8
HTML::Template->config(utf8 => 1);

my $action=$cgiobject->param('action');
$action = 'mainInterface' if ! $action;

my ($template, $message) = &{\&{$action}}();

_processTemplate($template, $message);


sub batchFunhouse {
	#batchTrackList(); # now done in daily.pl
	batchRecArtistPages();
	batchReleasePages();
	my $message = 'The Funhouse has been batched.';
	mainInterface($message);
}

sub batchRecArtistPages {
    my $rec_artists_template = HTML::Template->new(filename => 'templates/audio/rec_artists.tmpl');
    my $new_dirs;
    my $count = 0;
    my $select = <<~"SQL";
    SELECT id, email, email_display, homesite, profile, image_url, dir, name 
    FROM rec_artists
    WHERE published = 1
    ORDER BY name
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my @rec_artists;
    while (my ($rec_artist_id, $email, $email_display, $homesite, $profile, $image_url, $dir, $rec_artist) = $sth->fetchrow_array()) {
        my $rec_artist_template = HTML::Template->new(filename => 'templates/audio/rec_artist.tmpl');
        my %row;
        $count++;
        if ( mkdir ("$ENV{DOCUMENT_ROOT}/audiofun/$dir", 0755) ) {
            $new_dirs .= "mkdir $ENV{DOCUMENT_ROOT}/audiofun/$dir: successful\n";
        }
        ### get more info
        my $select = <<~"SQL";
        SELECT `release`, filename, year, image_url
        FROM releases 
        WHERE rec_artist = '$rec_artist_id'
        ORDER BY year DESC
        SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        my @releases;
        while (my ($release, $filename, $year, $release_image_url) = $sth->fetchrow_array()) {
            my %release_row;
            $release_row{FILENAME} = $filename;
            $release_row{RELEASE} = $release;
            $release_row{RELEASE_IMAGE_URL} = $release_image_url;
            $release_row{YEAR} = $year;
            push(@releases, \%release_row);
        }
        $rec_artist_template->param(REC_ARTIST_IMAGE_URL => $image_url);
        $rec_artist_template->param(PROFILE => $profile);
        $rec_artist_template->param(REC_ARTIST => $rec_artist);
        if ( $email ) {  
            # call with a true value (1) to include the conditional content
            if ($email_display eq "mailto") {
                $rec_artist_template->param(MAILTO => 1);
            }
            else {  # obfuscate the email
                $email =~ s/\./ \[dot\] /g;
                $email =~ s/\@/ \[at\] /g;
            }
            $rec_artist_template->param(EMAIL => $email);
        }
        $rec_artist_template->param(HOMESITE => $homesite);
        $rec_artist_template->param(RELEASES => \@releases);
        $rec_artist_template->param(PAGETITLE => "$rec_artist on mindmined.com");
        # strip double quotes from profile for meta description
        $profile =~ s/"/'/g;
        $profile = substr($profile, 0, 150);
        if (length($profile) == 150) {
            $profile .= qq {...};
        }
        $rec_artist_template->param(DESCRIPTION => $profile);
        $rec_artist_template->param(KEYWORDS => 'recording artists,podsafe music,free mp3s,download mp3s,bands');
        $rec_artist_template->param(WINDOW_STATUS => "Meet $rec_artist.");
        my $output = $rec_artist_template->output;
        open(REC_ARTIST, "> $ENV{DOCUMENT_ROOT}/audiofun/$dir/index.html");
        print REC_ARTIST "$output";
        close(REC_ARTIST);
        # compile list of recording artists as we go
        $row{DIR} = $dir;
        $row{REC_ARTIST}= $rec_artist;
        push(@rec_artists, \%row);
    }
    $rec_artists_template->param(PAGETITLE => 'Recording Artists on mindmined.com');
    $rec_artists_template->param(DESCRIPTION => 'Featuring independent recording artists from the northeastern U.S. and around the world, contact information, mp3s and a lot more!');
    $rec_artists_template->param(KEYWORDS => 'recording artists,podsafe music,free mp3s,download mp3s,bands');
    $rec_artists_template->param(WINDOW_STATUS => 'All music belongs to the recording artists.');
    $rec_artists_template->param(TOTAL => $count);
    $rec_artists_template->param(REC_ARTISTS => \@rec_artists);
    my $output = $rec_artists_template->output;
    open(REC_ARTIST_LIST, "> $ENV{DOCUMENT_ROOT}/audio/rec_artists.html");
    print REC_ARTIST_LIST "$output";
    close(REC_ARTIST_LIST);
}

sub batchReleasePages {
    my $release_template = HTML::Template->new(filename => 'templates/audio/release.tmpl');
    my $releases_template = HTML::Template->new(filename => 'templates/audio/releases.tmpl');
    my $count = 0;
    my $select = <<~"SQL";
    SELECT releases.`release`, releases.rec_artist, releases.year, releases.image_url, releases.filename, releases.description, releases.store_id, releases.id, rec_artists.name, rec_artists.dir 
    FROM releases 
    LEFT JOIN rec_artists 
    ON releases.rec_artist = rec_artists.id 
    WHERE rec_artists.published = 1
    ORDER BY year DESC
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my @releases;
    while (my ($release, $rec_artist_id, $year, $image_url, $filename, $description, $store_id, $release_id, $rec_artist, $dir) = $sth->fetchrow_array()) {
        my %row;
        $count++;
        my $product_url; my $price;
        unless (! $store_id || $store_id eq '0') { 
            my $select="SELECT price, product_URL FROM products WHERE id = '$store_id'";
            my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
            $sth->execute || die "execute: $select: $DBI::errstr";
            ($price, $product_url) = $sth->fetchrow_array();
        }
        $release_template->param(PRICE => $price);
        $release_template->param(PRODUCT_URL => $product_url);
        # TODO: add explicit track ordering
        my $select = <<~"SQL";
        SELECT title, url, `length`, mediatype, bitrate 
        FROM tracks 
        WHERE release_id = ?
        AND published = 1
        SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute($release_id) || die "execute: $select: $DBI::errstr";
        my @tracks; my $tracks_for_keywords; my $tracknum = 0;
        while (my ($title, $url, $length, $mediatype, $bitrate) = $sth->fetchrow_array()) {
            $tracknum++;
            my %row;
            $row{TRACKNUM} = $tracknum if $tracknum > 1;
            $row{URL} = $url;
            $row{TITLE} = $title;
            $row{LENGTH} = $length;
            $row{MEDIATYPE} = $mediatype;
            if ( $mediatype eq 'mpg' ) {  # look for video
                $row{VIDEO} = 1;
                $row{AUDIO} = 0;
            }
            else {  # assume audio
                $row{VIDEO} = 0;
                $row{AUDIO} = 1;
            }
            $row{BITRATE} = $bitrate;
            push(@tracks, \%row);
            $tracks_for_keywords .= qq {$title,};
        }
        $row{YEAR} = $year;
        $row{DIR} = $dir;
        $row{FILENAME} = $filename;
        $row{RELEASE} = $release;
        $row{REC_ARTIST} = $rec_artist;
        $release_template->param(RELEASE => $release);
        $release_template->param(DIR => $dir);
        $release_template->param(REC_ARTIST => $rec_artist);
        $release_template->param(YEAR => $year);
        $release_template->param(IMAGE_URL => $image_url);
        $description =~ s/"/'/g;
        $release_template->param(DESCRIPTION => $description);
        $release_template->param(TRACKS => \@tracks);
        $release_template->param(PAGETITLE => "$release from $rec_artist on mindmined.com");
        $release_template->param(DESCRIPTION => "$description");
        $release_template->param(KEYWORDS => "${tracks_for_keywords}recording artists,podsafe music,free mp3s,download mp3s,bands,$rec_artist,$release");
        $release_template->param(WINDOW_STATUS => "$rec_artist on mindmined.com");
        my $output = $release_template->output;
        open(RELEASE_PAGE, "> $ENV{DOCUMENT_ROOT}/audiofun/$dir/$filename");
        print RELEASE_PAGE "$output";
        close(RELEASE_PAGE);
        push(@releases, \%row);
    }
    $releases_template->param(RELEASES => \@releases);
    $releases_template->param(TOTAL => $count);
    $releases_template->param(PAGETITLE => 'Audio releases on mindmined.com');
    $releases_template->param(DESCRIPTION => 'Independent audio releases by recording artists from the northeastern U.S. and around the world.');
    $releases_template->param(KEYWORDS => 'recording artists,podsafe music,free mp3s,download mp3s,bands');
    $releases_template->param(WINDOW_STATUS => 'Special thanks to all our contributors.');
    my $output = $releases_template->output;
    open(RELEASE_LIST, "> $ENV{DOCUMENT_ROOT}/audio/releases.html");
    print RELEASE_LIST "$output";
    close(RELEASE_LIST);
}

=head2 batchTrackList()

TODO

=cut

sub batchTrackList {
    my $template = HTML::Template->new(filename => 'templates/audio/tracks.tmpl');
    my $count = 0;
    my $select = <<~"SQL";
    SELECT tracks.title, tracks.url, tracks.length, tracks.mediatype, tracks.bitrate, releases.`release`, releases.filename, ra.name, ra.dir 
    FROM tracks 
    LEFT JOIN releases 
    ON tracks.release_id = releases.id 
    LEFT JOIN rec_artists AS ra
    ON releases.rec_artist = ra.id 
    WHERE ra.published = 1
    ORDER BY title
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
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
    $template->param(TRACKS => \@tracks);
    $template->param(TOTAL => $count);
    $template->param(PAGETITLE => 'Complete audio tracks available on mindmined.com');
    $template->param(DESCRIPTION => "$count tracks, most in mp3 format, downloadable for free on mindmined.com.");
    $template->param(KEYWORDS => 'recording artists,podsafe music,free mp3s,download mp3s,bands');
    $template->param(WINDOW_STATUS => 'Obtain permission before using tracks for any purpose other than your listening pleasure.');
    my $output = $template->output;
    open(INDEX_PAGE, "> $ENV{DOCUMENT_ROOT}/audio/alpha_by_track.html");
    print INDEX_PAGE "$output";
    close INDEX_PAGE;
    my $message = 'Tracks page refreshed.';
    mainInterface($message) unless $ENV{CRON};
}

=head2 deleteRecordingArtist

Deletes a recording artist.

TODO: put some failsafes in places.

=cut

sub deleteRecordingArtist {
	my $id=$cgiobject->param("id"); 
	my $select = <<~"SQL";
    SELECT name FROM rec_artists WHERE id = ?
    SQL
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute($id) || die "execute: $select: $DBI::errstr";
	my ($rec_artist) = $sth->fetchrow_array();
    my $delete = <<~"SQL";
    DELETE FROM rec_artists WHERE id = ?
    SQL
    $sth = $dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    my $message = qq {$rec_artist deleted from the database.};
    mainInterface($message);
}

sub deleteRelease {
	my $id=$cgiobject->param('id'); 
	my $select="SELECT 'release' FROM releases WHERE id = '$id'";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my ($release) = $sth->fetchrow_array();
    my $delete="DELETE FROM releases WHERE id = ?";
    $sth = $dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    my $message = qq {$release deleted from the database.};
    mainInterface($message);
}

sub deleteTrack {
	my $id=$cgiobject->param("id"); 
	my $select="SELECT title FROM tracks WHERE id = '$id'";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my ($track_name) = $sth->fetchrow_array();
    my $delete="DELETE FROM tracks WHERE id ='$id'";
    $sth = $dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    my $message = qq {$track_name deleted from the database.};
    mainInterface($message);
}

sub mainInterface {
	my $message = $_[0];
	my $template = HTML::Template->new(filename => 'templates/mmpub/audio/mainInterface.tmpl');
	my $select="SELECT name, email, homesite, dir, id 
    FROM rec_artists 
    ORDER BY name";
	my $sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my $i; my @rec_artists;
	while (my ($rec_artist, $email, $homesite, $dir, $id) = $sth->fetchrow_array()) {
		my %row;
		$i++;
		if ($i % 2 == 0) {
			$row{BGCOLOR} = '#CCCCCC';
		}
		else { 
			$row{BGCOLOR} = '#FFFFFF';
		}
		$row{REC_ARTIST} = $rec_artist;
		$row{EMAIL} = $email;
		$row{HOMESITE} = $homesite;
		$row{DIR} = $dir;
		$row{ID} = $id;
		$row{REC_ARTIST} = $rec_artist;
		$row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
		push(@rec_artists, \%row);
	}
	$select="SELECT `release`, year, filename, id 
    FROM releases 
    ORDER BY `release`";
	$sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my @releases;
	while (my ($release, $year, $filename, $id) = $sth->fetchrow_array()) {
		my %row;
		$i++;
		if ($i % 2 == 0) {
			$row{BGCOLOR} = '#CCCCCC';
		}
		else { 
			$row{BGCOLOR} = '#FFFFFF';
		}
		$row{RELEASE} = $release;
		$row{YEAR} = $year;
		$row{FILENAME} = $filename;
		$row{ID} = $id;
		$row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
		push(@releases, \%row);
	}
	$select="SELECT title, length, bitrate, mediatype, release_id, id
    FROM tracks 
    ORDER BY title";
	$sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my @tracks;
	while (my ($title, $length, $bitrate, $mediatype, $release_id, $id) = $sth->fetchrow_array()) {
		my %row;
		$i++;
		if ($i % 2 == 0) {
			$row{BGCOLOR} = '#CCCCCC';
		}
		else { 
			$row{BGCOLOR} = '#FFFFFF';
		}
		my $select="SELECT `release` FROM releases WHERE id = ?";
		my $sth = $dbh->prepare($select);
		$sth->execute($release_id) || die "sth->execute($select): $DBI::errstr\n";
		my ($release) = $sth->fetchrow_array();
		$row{RELEASE} = $release;
		$row{TITLE} = $title;
		$row{LENGTH} = $length;
		$row{BITRATE} = $bitrate;
		$row{MEDIATYPE} = $mediatype;
		$row{LENGTH} = $length;
		$row{ID} = $id;
		$row{SCRIPT_NAME} = $ENV{SCRIPT_NAME};
		push(@tracks, \%row);
	}
	$template->param(REC_ARTISTS => \@rec_artists);
	$template->param(RELEASES => \@releases);
	$template->param(TRACKS => \@tracks);
	return ($template, $message);
}

sub _processTemplate {
	my $template = $_[0];
	my $message = $_[1];
	$template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$template->param(MESSAGE => $message);
	my $output = $template->output;
	print "Content-type: text/html\n\n";
	print $output;
}

sub recordingArtistInterface {
	my $id=$cgiobject->param("id"); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/audio/recordingArtistInterface.tmpl');
	my $rec_artist; my $email; my $email_display; my $homesite; my $profile;
	my $image_url; my $dir; my $published;
	if ( $id ) {
		my $select="SELECT name, email, email_display, homesite, profile, image_url, dir, published 
        FROM rec_artists 
        WHERE id = ?";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($id) || die "execute: $select: $DBI::errstr";
		($rec_artist, $email, $email_display, $homesite, $profile, $image_url, $dir, $published) = $sth->fetchrow_array();
		$profile =~ s/<br>/\n/g;
	}
	if ( $email_display eq "mailto" ) {
		$template->param(MAILTO => 1);
	}
	else {
		$template->param(OBFUSCATED => 1);
	}
	$template->param(ID => $id);
	$template->param(REC_ARTIST => $rec_artist);
	$template->param(PUBLISHED => $published);
	$template->param(EMAIL => $email);
	$template->param(HOMESITE => $homesite);
	$template->param(PROFILE => $profile);
	$template->param(IMAGE_URL => $image_url);
	$template->param(DIR => $dir);
	return ($template, $message);
}

sub releaseInterface {
	my $id=$cgiobject->param('id'); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/audio/releaseInterface.tmpl');
	my $release; my $rec_artist_id; my $year; my $image_url;
	my $filename; my $description; my $store_id;
	if ($id) { 
		my $select="SELECT `release`, rec_artist, id, year, image_url, filename, description, store_id 
        FROM releases WHERE id = ?";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($id) || die "execute: $select: $DBI::errstr";
		($release, $rec_artist_id, $id, $year, $image_url, $filename, $description, $store_id) = $sth->fetchrow_array();
	}
	else {
		my $select="SELECT YEAR(NOW())";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute || die "execute: $select: $DBI::errstr";
		my ($this_year) = $sth->fetchrow_array();
		$year = qq {$this_year};
		$image_url = qq {https://www.mindmined.com/audiofun-images/};
		$filename = qq {filename.html};
	}
	# create recording aritst dropdown
	my $select="SELECT id, name 
    FROM rec_artists ORDER BY name";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my @rec_artist_options;
	while (my ($id, $rec_artist) = $sth->fetchrow_array()) {
		my %row;
		if ($id eq $rec_artist_id) {
			$row{SELECTED} = "SELECTED";
		}
		$row{ID} = $id;
		$row{REC_ARTIST} = $rec_artist;
		push(@rec_artist_options, \%row);
	}
	# create product dropdown
	$select="SELECT id, product FROM products ORDER BY product";
	$sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my @product_options;
	while (my ($id, $product) = $sth->fetchrow_array()) {
		my %row;
		if ($id eq $store_id) {
			$row{SELECTED} = "SELECTED";
		}
		$row{ID} = $id;
		$row{PRODUCT} = $product;
		push(@product_options, \%row);
	} 
	$template->param(RELEASE => $release);	
	$template->param(ID => $id);	
	$template->param(YEAR => $year);	
	$template->param(IMAGE_URL => $image_url);	
	$template->param(FILENAME => $filename);	
	$template->param(DESCRIPTION => $description);
	$template->param(PRODUCT_OPTIONS => \@product_options);
	$template->param(REC_ARTIST_OPTIONS => \@rec_artist_options);
	return ($template, $message);
}

sub saveRecordingArtist {
	my $rec_artist=$cgiobject->param("rec_artist"); 
	my $published=$cgiobject->param("published"); 
	my $dir=$cgiobject->param("dir"); 
	my $email=$cgiobject->param("email"); 
	my $email_display=$cgiobject->param("email_display"); 
	my $homesite=$cgiobject->param("homesite"); 
	my $profile=$cgiobject->param("profile"); 
	my $image_url=$cgiobject->param("image_url"); 
	my $id=$cgiobject->param("id"); 
    $published = $published ? 1 : 0;
	if ( $id ) {
		$profile =~ s/\n/<br>/g;
		my $update="UPDATE rec_artists 
        SET name = ?, dir = ?, email = ?, email_display = ?, homesite = ?, profile = ?, image_url = ?, published= ?
        WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($rec_artist, $dir, $email, $email_display, $homesite, $profile, $image_url, $published, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq {$rec_artist has been updated.};
		mainInterface($message);
	}
	else {
		my $insert="INSERT INTO rec_artists 
        (name, dir, email, email_display, homesite, profile, image_url, published) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
		my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($rec_artist, $dir, $email, $email_display, $homesite, $profile, $image_url, $published) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		# establish directory for this recording artist
		system("mkdir $ENV{DOCUMENT_ROOT}/audio/$dir");
		my $message = qq |$rec_artist has been added.|;
		mainInterface($message);
	}
}

sub saveRelease {
	my $release=$cgiobject->param('release'); 
	my $filename=$cgiobject->param('filename'); 
	my $rec_artist_id=$cgiobject->param('rec_artist_id'); 
	my $year=$cgiobject->param('year'); 
	my $store_id=$cgiobject->param('store_id') || 0; 
	my $description=$cgiobject->param('description'); 
	my $image_url=$cgiobject->param('image_url'); 
	my $id=$cgiobject->param('id');
	if ( $id ) {
		my $update="UPDATE releases SET `release` = ?, filename = ?, year = ?, description = ?, image_url = ?, store_id = ?, rec_artist = ? 
		WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($release, $filename, $year, $description, $image_url, $store_id, $rec_artist_id, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq |$release has been updated.|;
		mainInterface($message);
	}
	else {
		my $insert="INSERT INTO releases (`release`, filename, rec_artist, year, store_id, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)";
		my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($release, $filename, $rec_artist_id, $year, $store_id, $description, $image_url) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |$release has been added.|;
		mainInterface($message);
	}
}

sub saveTrack {
	my $url=$cgiobject->param('url'); 
	my $title=$cgiobject->param('title'); 
	my $published=$cgiobject->param('published'); 
	my $release_id=$cgiobject->param('release_id'); 
	my $length=$cgiobject->param('length'); 
	my $mediatype=$cgiobject->param('mediatype'); 
	my $bitrate=$cgiobject->param('bitrate'); 
	my $id=$cgiobject->param('id'); 
    $published = $published ? 1 : 0;
	if ( $id ) {
		my $update="UPDATE tracks 
		SET title = ?, url = ?, length = ?, mediatype = ?, bitrate = ?, release_id = ?, published = ?
		WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($title, $url, $length, $mediatype, $bitrate, $release_id, $published, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq |$title has been updated.|;
		mainInterface($message);
	}
	else {
		my $insert="INSERT INTO tracks 
		(url, title, release_id, length, mediatype, bitrate, published) 
		VALUES 
		(?, ?, ?, ?, ?, ?, ?)";
		my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($url, $title, $release_id, $length, $mediatype, $bitrate, $published) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |$title has been added.|;
		mainInterface($message);
	}
}

sub trackInterface {
	my $id=$cgiobject->param('id'); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/audio/trackInterface.tmpl');
	my $url; my $title; my $published; my $release_id; my $length;
	my $mediatype; my $bitrate;
	my $add_or_update;
	if ( $id ) {
		$add_or_update = 'Update';
		my $select="SELECT url, title, release_id, length, mediatype, bitrate, published
        FROM tracks WHERE id = ?";
		my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
		$sth->execute($id) || die "execute: $select: $DBI::errstr";
		($url, $title, $release_id, $length, $mediatype, $bitrate, $published) = $sth->fetchrow_array();
	}
	else {
		$add_or_update = 'Add';
		$url = 'https://www.mindmined.com/audio/';
		$length = '0:00';
		$mediatype = 'mp3';
		$bitrate = '128 kbps';
	}
	###
	my $select="SELECT `release`, id 
    FROM releases ORDER BY `release`";
	my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
	$sth->execute || die "execute: $select: $DBI::errstr";
	my @release_options;
	while (my ($release, $id) = $sth->fetchrow_array()) {
		my %row;
		if ($release_id eq $id) {
			$row{SELECTED} = "SELECTED";
		}
		$row{RELEASE} = $release;
		$row{ID} = $id;
		push(@release_options, \%row);
	}
	$template->param(RELEASE_OPTIONS => \@release_options);
	$template->param(URL => $url);
	$template->param(TITLE => $title);
	$template->param(PUBLISHED => $published);
	$template->param(LENGTH => $length);
	$template->param(MEDIATYPE => $mediatype);
	$template->param(BITRATE => $bitrate);
	$template->param(ID => $id);
	return ($template, $message);
}

