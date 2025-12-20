#!/usr/bin/perl

# use strict, warnings and modern features
use 5.030;

use lib qw (
    ../lib
    .
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
);

use MindMined;

my $cgi = new CGI;

my $action=$cgi->param('action');
$action = 'mainInterface' if ! $action;

my %dispatch = (
    batchFunhouse       => \&batchFunhouse,
    batchRecArtistPages => \&batchRecArtistPages,
    batchReleasePages   => \&batchReleasePages,
    deleteRecArtist     => \&deleteRecArtist,
    deleteRelease       => \&deleteRelease,
    deleteTrack         => \&deleteTrack,
    mainInterface       => \&mainInterface,
    recordingArtist     => \&recordingArtist,
    release             => \&release,
    saveRecArtist       => \&saveRecArtist,
    saveRelease         => \&saveRelease,
    saveImage           => \&saveImage,
    track               => \&track,
);

my ($template, $message);
if ( my $code = $dispatch{$action} ) {
    $code->();
    # run the sub by the same name as $action
    ($template, $message) = &{\&{$action}}();
    _processTemplate($template, $message);
}
else {
    die "Unknown action: $action\n";
}

exit;

=head2 batchFunhouse()

TODO

=cut

sub batchFunhouse {
	MindMined::batchTrackList();
	batchRecArtistPages();
	batchReleasePages();
	my $message = 'The Funhouse has been batched.';
	mainInterface($message);
}

=head2 batchRecArtistPages()

TODO

=cut

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
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
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
        my $sth = $MindMined::dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
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

=head2 batchReleasePages()

TODO

=cut

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
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute;
    my @releases;
    while (my ($release, $rec_artist_id, $year, $image_url, $filename, $description, $store_id, $release_id, $rec_artist, $dir) = $sth->fetchrow_array()) {
        my %row;
        $count++;
        my $product_url; my $price;
        unless ( ! $store_id || $store_id eq '0' ) { 
            my $select="SELECT price, product_URL FROM products WHERE id = ?";
            my $sth = $MindMined::dbh->prepare($select);
            $sth->execute($store_id);
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
        my $sth = $MindMined::dbh->prepare($select);
        $sth->execute($release_id);
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

=head2 deleteRecArtist

Given a recording artist id, delete that recording artist.

TODO: put some failsafes in places.

=cut

sub deleteRecArtist {
	my $id=$cgi->param("id"); 
	my $select = <<~"SQL";
    SELECT name FROM rec_artists WHERE id = ?
    SQL
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute($id);
	my ($rec_artist) = $sth->fetchrow_array();
    my $delete = <<~"SQL";
    DELETE FROM rec_artists WHERE id = ?
    SQL
    $sth = $MindMined::dbh->prepare($delete);
    $sth->execute($id);
    my $message = "'$rec_artist' deleted from the database.";
    mainInterface($message);
}

=head2 deleteRelease()

Given a release id, delete that release.

=cut

sub deleteRelease {
	my $id=$cgi->param('id'); 
	my $select="SELECT 'release' FROM releases WHERE id = ?";
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute($id);
	my ($release) = $sth->fetchrow_array();
    my $delete="DELETE FROM releases WHERE id = ?";
    $sth = $MindMined::dbh->prepare($delete);
    $sth->execute($id);
    my $message = qq {$release deleted from the database.};
    mainInterface($message);
}

=head2 deleteTrack()

Given a track id, delete that track.

=cut

sub deleteTrack {
	my $id=$cgi->param("id"); 
	my $select="SELECT title FROM tracks WHERE id = '$id'";
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute;
	my ($track_name) = $sth->fetchrow_array();
    my $delete="DELETE FROM tracks WHERE id = ?";
    $sth = $MindMined::dbh->prepare($delete);
    $sth->execute($id);
    my $message = "'$track_name' deleted from the database.";
    mainInterface($message);
}

=head2 mainInterface()

The main Audio Funhouse management view.

=cut

sub mainInterface {
	my $message = $_[0];
	my $template = HTML::Template->new(
        filename => 'templates/mmpub/audio/mainInterface.tmpl'
    );
	my $select = <<~"SQL";
    SELECT name, email, homesite, dir, id 
    FROM rec_artists 
    ORDER BY name
    SQL
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute();
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
	$select = <<~"SQL";
    SELECT `release`, year, filename, id 
    FROM releases 
    ORDER BY `release`
    SQL
	$sth = $MindMined::dbh->prepare($select);
	$sth->execute();
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
	$select = <<~"SQL";
    SELECT title, length, bitrate, mediatype, release_id, id
    FROM tracks 
    ORDER BY title
    SQL
	$sth = $MindMined::dbh->prepare($select);
	$sth->execute();
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
		my $sth = $MindMined::dbh->prepare($select);
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

=head2 recordingArtist()

Screen for managing a recording artist's data.

=cut

sub recordingArtist {
	my $id=$cgi->param("id"); 
	my $template = HTML::Template->new(filename => 'templates/mmpub/audio/recordingArtistInterface.tmpl');
	my $rec_artist; my $email; my $email_display; my $homesite; my $profile;
	my $image_url; my $dir; my $published;
	if ( $id ) {
		my $select = <<~"SQL";
        SELECT name, email, email_display, homesite, profile, image_url, dir, published 
        FROM rec_artists 
        WHERE id = ?
        SQL
		my $sth = $MindMined::dbh->prepare($select);
		$sth->execute($id);
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

=head2 release()

Screen for managing data for a release.

=cut

sub release {
	my $id=$cgi->param('id'); 
	my $template = HTML::Template->new(
        filename => 'templates/mmpub/audio/releaseInterface.tmpl'
    );
	my $release; my $rec_artist_id; my $year; my $image_url;
	my $filename; my $description; my $store_id;
	if ( $id ) { 
		my $select = <<~"SQL";
        SELECT `release`, rec_artist, id, year, image_url, filename, description, store_id 
        FROM releases WHERE id = ?
        SQL
		my $sth = $MindMined::dbh->prepare($select);
		$sth->execute($id);
		($release, $rec_artist_id, $id, $year, $image_url, $filename, $description, $store_id) = $sth->fetchrow_array();
	}
	else {
		my $select = <<~"SQL";
        SELECT YEAR(NOW())
        SQL
		my $sth = $MindMined::dbh->prepare($select);
		$sth->execute;
		my ($this_year) = $sth->fetchrow_array();
		$year = qq {$this_year};
		$image_url = qq {https://www.mindmined.com/audiofun-images/};
	}
	# create recording aritst dropdown
	my $select = <<~"SQL";
    SELECT id, name 
    FROM rec_artists ORDER BY name
    SQL
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute;
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
	$select = <<~"SQL";
    SELECT id, product FROM products ORDER BY product
    SQL
	$sth = $MindMined::dbh->prepare($select);
	$sth->execute;
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

=head2 saveRecArtist()

Insert or update a recording artist.

=cut

sub saveRecArtist {
	my $rec_artist=$cgi->param("rec_artist"); 
	my $published=$cgi->param("published"); 
	my $dir=$cgi->param("dir"); 
	my $email=$cgi->param("email"); 
	my $email_display=$cgi->param("email_display"); 
	my $homesite=$cgi->param("homesite"); 
	my $profile=$cgi->param("profile"); 
	my $image_url=$cgi->param("image_url"); 
	my $id=$cgi->param("id"); 
    $published = $published ? 1 : 0;
    my $message;
	if ( $id ) {
		$profile =~ s/\n/<br>/g;
		my $update="UPDATE rec_artists 
        SET name = ?, dir = ?, email = ?, email_display = ?, homesite = ?, profile = ?, image_url = ?, published= ?
        WHERE id = ?";
		my $sth = $MindMined::dbh->prepare($update);
		$sth->execute($rec_artist, $dir, $email, $email_display, $homesite, $profile, $image_url, $published, $id) || die "sth->execute($update): $DBI::errstr\n";
		$message = "'$rec_artist' has been updated.";
	}
	else {
		my $insert="INSERT INTO rec_artists 
        (name, dir, email, email_display, homesite, profile, image_url, published) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
		my $sth = $MindMined::dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($rec_artist, $dir, $email, $email_display, $homesite, $profile, $image_url, $published) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
        my $rec_artist_dir = "$ENV{DOCUMENT_ROOT}/audio/$dir";
        unless ( -d $rec_artist_dir ) {
            # establish directory for this recording artist
            system("mkdir $rec_artist_dir");
		    $message = "'$rec_artist' has been added.";
        }
	}
	mainInterface($message);
}

=head2 saveRelease()

TODO

=cut

sub saveRelease {
	my $release=$cgi->param('release'); 
	my $filename=$cgi->param('filename'); 
	my $rec_artist_id=$cgi->param('rec_artist_id'); 
	my $year=$cgi->param('year'); 
	my $store_id=$cgi->param('store_id') || 0; 
	my $description=$cgi->param('description'); 
	my $image_url=$cgi->param('image_url'); 
	my $id=$cgi->param('id');
	if ( $id ) {
		my $update="UPDATE releases SET `release` = ?, filename = ?, year = ?, description = ?, image_url = ?, store_id = ?, rec_artist = ? 
		WHERE id = ?";
		my $sth = $MindMined::dbh->prepare($update);
		$sth->execute($release, $filename, $year, $description, $image_url, $store_id, $rec_artist_id, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq |$release has been updated.|;
		mainInterface($message);
	}
	else {
		my $insert="INSERT INTO releases (`release`, filename, rec_artist, year, store_id, description, image_url) VALUES (?, ?, ?, ?, ?, ?, ?)";
		my $sth = $MindMined::dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($release, $filename, $rec_artist_id, $year, $store_id, $description, $image_url) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |$release has been added.|;
		mainInterface($message);
	}
}

=head2 saveTrack()

Insert or update a Track.

=cut

sub saveTrack {
	my $url=$cgi->param('url'); 
	my $title=$cgi->param('title'); 
	my $published=$cgi->param('published'); 
	my $release_id=$cgi->param('release_id'); 
	my $length=$cgi->param('length'); 
	my $mediatype=$cgi->param('mediatype'); 
	my $bitrate=$cgi->param('bitrate'); 
	my $id=$cgi->param('id'); 
    $published = $published ? 1 : 0;
	if ( $id ) {
		my $update="UPDATE tracks 
		SET title = ?, url = ?, length = ?, mediatype = ?, bitrate = ?, release_id = ?, published = ?
		WHERE id = ?";
		my $sth = $MindMined::dbh->prepare($update);
		$sth->execute($title, $url, $length, $mediatype, $bitrate, $release_id, $published, $id) || die "sth->execute($update): $DBI::errstr\n";
		my $message = qq |$title has been updated.|;
		mainInterface($message);
	}
	else {
		my $insert="INSERT INTO tracks 
		(url, title, release_id, length, mediatype, bitrate, published) 
		VALUES 
		(?, ?, ?, ?, ?, ?, ?)";
		my $sth = $MindMined::dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($url, $title, $release_id, $length, $mediatype, $bitrate, $published) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid}; 
		my $message = qq |$title has been added.|;
		mainInterface($message);
	}
}

=head2 track()

Screen for managing data for a Track.

=cut

sub track {
	my $id=$cgi->param('id'); 
	my $t = HTML::Template->new(
        filename => 'templates/mmpub/audio/trackInterface.tmpl'
    );
	my $url; my $title; my $published; my $release_id; my $length;
	my $mediatype; my $bitrate;
	my $add_or_update;
	if ( $id ) {
		$add_or_update = 'Update';
		my $select = <<~"SQL";
        SELECT url, title, release_id, length, mediatype, bitrate, published
        FROM tracks WHERE id = ?
        SQL
		my $sth = $MindMined::dbh->prepare($select);
		$sth->execute($id);
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
	my $select = <<~"SQL";
    SELECT `release`, id 
    FROM releases ORDER BY `release`
    SQL
	my $sth = $MindMined::dbh->prepare($select);
	$sth->execute;
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
	$t->param(RELEASE_OPTIONS => \@release_options);
	$t->param(URL => $url);
	$t->param(TITLE => $title);
	$t->param(PUBLISHED => $published);
	$t->param(LENGTH => $length);
	$t->param(MEDIATYPE => $mediatype);
	$t->param(BITRATE => $bitrate);
	$t->param(ID => $id);
	return ($t, $message);
}

=head1 INTERNAL SUBROUTINES

=head2 _processTemplate()

TODO

=cut

sub _processTemplate {
	my $template = $_[0];
	my $message = $_[1];
	$template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$template->param(MESSAGE => $message);
	my $output = $template->output;
	print "Content-type: text/html\n\n";
	print $output;
}

