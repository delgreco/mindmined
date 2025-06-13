#!/usr/bin/perl

# use strict, warnings and modern features
use 5.030;

use lib qw(
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
    ../lib
    .
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
      Error_cache /tmp/songs.tmp
      Seconds 60
      Debug 1
    );

# force templates to be read as UTF-8
HTML::Template->config(utf8 => 1);

my $debug = 0;

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
$action = qq {mainInterface} if ! $action;
&{\&{$action}}();
exit;

=head2 addToSongBook

TODO

=cut

sub addToSongBook {
	my $song_id=$cgiobject->param('song_id');
	my $songbook_id=$cgiobject->param('songbook_id');
	my $message;
	#my $song_id = $_[0];
	#my $songbook_id = $_[1];
	# make sure it's not already there for some strange reason
	my $select = <<"SQL";
    SELECT song_id 
	FROM songs_songbooks
	WHERE song_id = ?
	AND songbook_id = ?
SQL
	my $sth = $dbh->prepare($select);
	$sth->execute($song_id, $songbook_id);
	my ($id) = $sth->fetchrow_array();
	# unless this song/songbook association already exists, add it
	unless ($id) {
		my $insert="INSERT INTO songs_songbooks (song_id, songbook_id) VALUES (?, ?)";
		my $sth = $dbh->prepare($insert);
		$sth->execute($song_id, $songbook_id);
		# give it a starting setlist frequency of '5'
		my $count = 5;
		while ($count > 0) {
			my $insert="INSERT INTO song_frequency (song_id, songbook_id) VALUES (?, ?)";
			my $sth = $dbh->prepare($insert);
			$sth->execute($song_id, $songbook_id);
			$sth->finish();
			$count--;
		}
		$message = qq |Song added to SongBook.|;
	}
	else {
		$message = qq |That song is already in this SongBook.|;
	}
	mainInterface($message, $songbook_id);
}

sub adjustFrequency {
	my $id=$cgiobject->param("id"); 
	my $setlist=$cgiobject->param("setlist"); 
	my $songbook_id=$cgiobject->param("songbook_id"); 
	if ($id =~ /^\+/) {
		$id =~ s/\+//;
		&_upgradeSong($id, $setlist, $songbook_id);
	}
	elsif ($id =~ /^\-/) {
		$id =~ s/\-//;
		&_downgradeSong($id, $setlist, $songbook_id);
	}
	else {
		my $message = qq {Select a radio button in order to adjust the frequency of a setlist song.};
		&setlistInterface($setlist, $message);
	}
}

sub deleteSong {
	my $id=$cgiobject->param('id');
    my $delete="DELETE FROM songs
    WHERE id = ?";
    my $sth = $dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    my $message = qq |Song deleted.|;
    mainInterface($message);
}

sub mainInterface { 
	my $message = $_[0];
	my $songbook_id = $_[1];
	$songbook_id=$cgiobject->param('songbook_id') if ! $songbook_id;
	my $t = HTML::Template->new(filename => 'templates/songs/songsMainInterface.tmpl');
	my $where; my @bind_variables;
	if ($songbook_id) {
		$where = "WHERE songs_songbooks.songbook_id = ?";
		push(@bind_variables, $songbook_id);
	}
	else {
		$t->param(VIEWING_ALL_SONGS => 1);
	}
	my $select = <<~"SQL";
    SELECT title, credits, more_info_url, audio_url, chordsheet, songs.id
	FROM songs
    LEFT JOIN songs_songbooks 
	ON songs.id = songs_songbooks.song_id
    LEFT JOIN songbooks
	ON songbooks.id = songs_songbooks.songbook_id
	$where
	GROUP BY title, credits, more_info_url, audio_url, chordsheet, songs.id

	ORDER BY title
    SQL
	my $sth = $dbh->prepare($select);
	$sth->execute(@bind_variables);
	my $i;
	my @songs;
	while (my ($title, $credits, $more_info_url, $audio_url, $chordsheet, $id) = $sth->fetchrow_array()) {
	    $i++;
	    my $bgcolor;
		my %row;
		$row{TITLE} = $title;
		$row{CREDITS} = $credits;
		$row{ID} = $id;
		$row{MORE_INFO_URL} = $more_info_url;
		$row{AUDIO_URL} = $audio_url;
		$row{CHORDSHEET} = $chordsheet;
		# $row{SONGBOOK_ID} = $songbook_id;
		# $row{SONGBOOK} = $songbook;
		if ($i % 2 == 0) {
			$bgcolor = qq {#CCCCCC};
		}
		else { 
			$bgcolor = qq {#FFFFFF};
		}
		$row{BGCOLOR} = $bgcolor;
		push(@songs, \%row);
	}
	$sth->finish();
	$t = _getSongsTopTemplate(
		template    => $t,
		songbook_id => $songbook_id,
	);
	# populate songs dropdown
	$t = _getAddSongsDropdown($template, $songbook_id);	
	# get the SongBook name
	my $songbook = _getSongBookName($songbook_id);
	$t->param(SONGBOOK => $songbook);
	$t->param(SONGS => \@songs);
	$t->param(SONGBOOK_ID => $songbook_id);	
	$t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$t->param(MESSAGE => $message);
	my $output = $t->output;
	print "Content-type:text/html\n\n";
	print $output;
}

sub removeFromSongBook {
	my $song_id=$cgiobject->param('song_id'); 
	my $songbook_id=$cgiobject->param('songbook_id'); 
	my $message;
	#my $song_id = $_[0];
	#my $songbook_id = $_[1];
	# disassociate song from songbook
    my $delete="DELETE FROM songs_songbooks 
    WHERE song_id ='$song_id'
    AND songbook_id = '$songbook_id'";
    my $sth = $dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    # remove all rows of this song/songbook in the frequency table
    $delete="DELETE FROM song_frequency 
    WHERE song_id ='$song_id'
    AND songbook_id = '$songbook_id'";
    $sth = $dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
	$message = qq |Song removed from SongBook.|;
	&mainInterface($message, $songbook_id);
}

sub setlistInterface {
	my $setlist = $_[0];
	my $message = $_[1];
	my $limit=$cgiobject->param('number_of_songs'); 
	my $songbook_id=$cgiobject->param('songbook_id'); 
	my $number_of_songs=$cgiobject->param('number_of_songs'); 
	my $include_exercises=$cgiobject->param('include_exercises'); 
	my $t = HTML::Template->new(filename => 'templates/songs/songsSetlistInterface.tmpl');
	my @songs_loop;
	if ( $setlist ) {  # if only adjusting frequency, reprint remembered setlist
		my @song_ids = split(/,/, $setlist);
		foreach my $id (@song_ids) {
			my %row;
			# determine current frequency rate for this song
			my $select = <<"SQL";
            SELECT COUNT(*) 
			FROM song_frequency 
			WHERE song_id = ?
			AND songbook_id = ?
SQL
			my $sth = $dbh->prepare($select);
			$sth->execute($id, $songbook_id) || die "sth->execute($select): $DBI::errstr\n";
			my ($freq) = $sth->fetchrow_array();
			if ($freq == 1) {
				$row{DELETE} = 1;
			}
			$select = <<"SQL";
            SELECT title, credits, audio_url 
			FROM songs 
			WHERE id = ?
SQL
			$sth = $dbh->prepare($select);
			$sth->execute($id) || die "sth->execute($select): $DBI::errstr\n";
			my ($title, $credits, $audio_url) = $sth->fetchrow_array();
			$sth->finish();
			$row{TITLE} = $title;
			$row{CREDITS} = $credits;
			$row{ID} = $id;
			$row{FREQUENCY_RATE} = $freq;
			push(@songs_loop, \%row);
		}
	}
	else {  # generate fresh setlist
		my $select = <<"SQL";
        SELECT song_frequency.song_id, songs.title, songs.credits, songs.audio_url 
		FROM song_frequency 
		JOIN songs 
		ON song_frequency.song_id = songs.id 
		WHERE song_frequency.songbook_id = '$songbook_id'
		ORDER BY RAND()
SQL
		my $sth = $dbh->prepare($select);
		$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
		my $i = 0;
		my @song_ids;
		while (my ($id, $title, $credits, $audio_url) = $sth->fetchrow_array()) {
			if ( $i == $limit ) {  # generate only the desired number of songs
				last;
			}
			if ( grep(/$id/, @song_ids) ) {  # no dupes
				next;
			}
			# decide whether or not to include DRILLS
			if (! $include_exercises && $credits =~ m/.*DRILL.*/) {next;}
			# otherwise, we have a fresh song id
			$i++;
			push(@song_ids, $id);
			$setlist .= qq {$id,};
			my %row;
			# determine current frequency rate for this song
			my $select = <<"SQL";
            SELECT COUNT(*) 
			FROM song_frequency 
			WHERE song_id = ?
			AND songbook_id = ?
SQL
			my $sth = $dbh->prepare($select);
			$sth->execute($id, $songbook_id) || die "sth->execute($select): $DBI::errstr\n";
			my ($freq) = $sth->fetchrow_array();
			# there will either be one occurrence of this song in the table, in which case we present an upgrade-or-delete option
			if ($freq == 1) {
				$row{DELETE} = 1;
			}
			$row{TITLE} = $title;
			$row{CREDITS} = $credits;
			$row{ID} = $id;
			$row{FREQUENCY_RATE} = $freq;
			push(@songs_loop, \%row);
		}
	}
	my $songbook = _getSongBookName($songbook_id);
	my ($day_of_month, $month, $year) = _getToday();
	$t = _getSongsTopTemplate(
		template    => $t,
		songbook_id => $songbook_id,
	);
	$t->param(DATE => "$month $day_of_month, $year");
	$t->param(SETLIST => $setlist);
	$t->param(SONGBOOK_ID => $songbook_id);
	$t->param(SONGBOOK => $songbook);
	$t->param(SONGS => \@songs_loop);
	$t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$t->param(NUM_SONGS => $number_of_songs);
	$t->param(INCLUDE_EXERCISES => $include_exercises);
	$t->param(MESSAGE => $message);
	my $output = $t->output;
	print "Content-type:text/html\n\n";
	print $output;
}

sub saveSong {
	# grab the values submitted
	my $title=$cgiobject->param("title"); 
	my $credits=$cgiobject->param("credits"); 
	my $more_info_url=$cgiobject->param("more_info_url"); 
	my $audio_url=$cgiobject->param("audio_url"); 
	my $chordsheet=$cgiobject->param("chordsheet"); 
	my $id=$cgiobject->param("id"); 
	# return to a specific songbook if we started there
	my $songbook_id=$cgiobject->param("songbook_id"); 
	my $message;
	if ($id) {  # update existing song
		my $update="UPDATE songs 
		SET title = ?, credits = ?, more_info_url = ?, audio_url = ?, chordsheet = ?
		WHERE id = '$id'";
		my $sth = $dbh->prepare($update);
		$sth->execute($title, $credits, $more_info_url, $audio_url, $chordsheet) || die "sth->execute($update): $DBI::errstr\n";
		$message = qq {$title has been updated.};
	}
	else {  # add new song
		my $insert="INSERT INTO songs (title, credits, more_info_url, audio_url, chordsheet) VALUES (?, ?, ?, ?, ?)";
		my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($title, $credits, $more_info_url, $audio_url, $chordsheet) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid};
		$sth->finish();
		$message = qq {$title has been added.};
	}
	&mainInterface($message, $songbook_id);
}

sub saveSongbook {
	# grab the values submitted
	my $name=$cgiobject->param('name'); 
	my $id=$cgiobject->param('id'); 
	my $message;
	if ($id) {  # update existing song
		my $update="UPDATE songbooks 
		SET name = ?
		WHERE id = ?";
		my $sth = $dbh->prepare($update);
		$sth->execute($name, $id) || die "sth->execute($update): $DBI::errstr\n";
		$message = qq |The songbook called $name has been updated.|;
	}
	else {  # add new songbook
		my $insert="INSERT INTO songbooks (name) VALUES (?)";
		my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
		$sth->execute($name) || die "execute: $insert: $DBI::errstr";
		# grab the automatically incremented id that was generated
		$id = $sth->{mysql_insertid} || $sth->{insertid};
		$sth->finish();
		$message = qq |A songbook called $name has been added.|;
	}
	mainInterface($message, $id);
}

sub songInterface { 
	my $message = $_[0];
	my $id=$cgiobject->param("id"); 
	# so we can return to the songbook we were looking at
	my $songbook_id=$cgiobject->param("songbook_id");
	my $template = HTML::Template->new(filename => 'templates/songs/songInterface.tmpl');
	my $select = <<"SQL";
    SELECT title, credits, more_info_url, audio_url, chordsheet
	FROM songs 
	WHERE id = ?
SQL
	my $sth = $dbh->prepare($select);
	$sth->execute($id) || die "sth->execute($select): $DBI::errstr\n";
	my ($title, $credits, $more_info_url, $audio_url, $chordsheet) = $sth->fetchrow_array();
	$template = _getSongsTopTemplate(
		template    => $template,
		songbook_id => $id,
	);
	$template->param(SONG_INTERFACE => 1);
	$template->param(TITLE => $title);
	$template->param(CREDITS => $credits);
	$template->param(MORE_INFO_URL => $more_info_url);
	$template->param(AUDIO_URL => $audio_url);
	$template->param(CHORDSHEET => $chordsheet);
	$template->param(ID => $id);
	$template->param(SONGBOOK_ID => $songbook_id);
	$template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	my $output = $template->output;
	print "Content-type:text/html\n\n";
	print $output;
}

sub songbookInterface { 
	my $message = $_[0];
	my $id=$cgiobject->param('id'); 
	my $template = HTML::Template->new(filename => 'templates/songs/songbookInterface.tmpl');
	my $select="SELECT name 
	FROM songbooks 
	WHERE id = ?";
	my $sth = $dbh->prepare($select);
	$sth->execute($id) || die "sth->execute($select): $DBI::errstr\n";
	my ($name) = $sth->fetchrow_array();
	$sth->finish();
	$template->param(NAME => $name);
	$template->param(ID => $id);
	$template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	$template = _getSongsTopTemplate(
		template    => $template,
		songbook_id => $id,
	);
	my $output = $template->output;
	print "Content-type:text/html\n\n";
	print $output;
}

sub viewSong {
	my $id=$cgiobject->param('id'); 
	# so we can return to the songbook we were looking at
	my $songbook_id=$cgiobject->param('songbook_id');
	my $template = HTML::Template->new(filename => 'templates/songs/viewSong.tmpl');
	my $select="SELECT title, credits, more_info_url, audio_url, chordsheet
	FROM songs 
	WHERE id = ?";
	my $sth = $dbh->prepare($select);
	$sth->execute($id) || die "sth->execute($select): $DBI::errstr\n";
	my ($title, $credits, $more_info_url, $audio_url, $chordsheet) = $sth->fetchrow_array();
	$template->param(TITLE => $title);
	$template->param(PAGETITLE => "$title ($credits)");
	$template->param(CREDITS => $credits);
	$template->param(MORE_INFO_URL => $more_info_url);
	$template->param(AUDIO_URL => $audio_url);
	# replace line breaks with <br>
	#$chordsheet =~ s/\n/<br>/g;
	$template->param(CHORDSHEET => $chordsheet);
	$template->param(ID => $id);
	$template->param(SONGBOOK_ID => $songbook_id);
	#$template->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
	my $output = $template->output;
	print "Content-type:text/html\n\n";
	print $output;	
}

###############
# internal subs
###############

sub _downgradeSong {
	my $song_id = $_[0]; 
	my $setlist = $_[1]; 
	my $songbook_id = $_[2];
	my $delete="DELETE FROM song_frequency 
	WHERE song_id = '$song_id' 
	AND songbook_id = '$songbook_id'
	LIMIT 1";
	my $sth = $dbh->prepare($delete);
	$sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
	$sth->finish();
	my $message = qq {Song has been downgraded.};
	&setlistInterface($setlist, $message);
}

sub _getAddSongsDropdown {
	my $template = $_[0];
	my $songbook_id = $_[1];  # when passing a songbook id,
	# we are telling this sub that we want the songs that DON'T
	# appear in this songbook yet, so they can be added via this dropdown
	my @songbook_song_ids = _getSongBookSongIDs($songbook_id); 
	my $select="SELECT title, id
	FROM songs
	ORDER BY title";
	my $sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my @songs;
	while (my ($title, $id) = $sth->fetchrow_array()) {
		if (grep(/^$id$/, @songbook_song_ids)) {
			next;
		}
		my %row;
		$row{TITLE} = $title;
		$row{ID} = $id;
		push(@songs, \%row);
	}
	$sth->finish();
	$template->param(SONGS_OPTIONS => \@songs);
	return $template;
}

sub _getSongBookDropdown {
	my $template = $_[0];
	my $songbook_id = $_[1];
	my $select="SELECT name, id 
	FROM songbooks 
	ORDER BY name";
	my $sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my @songbooks;
	while (my ($name, $id) = $sth->fetchrow_array()) {
		my %row;
		if ($id == $songbook_id) {
			$row{SELECTED} = 1;
		}
		$row{NAME} = $name;
		$row{ID} = $id;
		push(@songbooks, \%row);
	}
	$sth->finish();
	$template->param(SONGBOOKS => \@songbooks);
	return $template;
}

sub _getSongBookName {
	my $songbook_id = $_[0];
	my $select="SELECT name
	FROM songbooks
	WHERE id = '$songbook_id'";
	my $sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my @songs;
	my ($name) = $sth->fetchrow_array();
	$sth->finish();
	return $name;
}

sub _getSongBookSongIDs {
	my $songbook_id = $_[0];
	my $select="SELECT id 
	FROM songs
	JOIN songs_songbooks
	ON songs_songbooks.song_id = songs.id
	WHERE songs_songbooks.songbook_id = ?
	ORDER BY songs.title";
	my $sth = $dbh->prepare($select);
	$sth->execute($songbook_id) || die "sth->execute($select): $DBI::errstr\n";
	my @song_ids;
	while (my ($id) = $sth->fetchrow_array()) {
		push(@song_ids, $id);
	}
	$sth->finish();
	return @song_ids;
}

sub _getSongsTopTemplate {
	my %arg = @_;
	my $template = $arg{template};
	my $songbook_id = $arg{songbook_id};
	# populate songbook dropdowns
	$template = _getSongBookDropdown($template, $songbook_id);	
	return $template;
}

sub _getToday {
	my $select="SELECT DAYOFMONTH(NOW()), MONTHNAME(NOW()), YEAR(NOW())";
	my $sth = $dbh->prepare($select);
	$sth->execute() || die "sth->execute($select): $DBI::errstr\n";
	my ($day_of_month, $month, $year) = $sth->fetchrow_array();
	$sth->finish();
	return($day_of_month, $month, $year);
}

sub _upgradeSong {
	my $song_id = $_[0];
	my $setlist = $_[1];
	my $songbook_id = $_[2];
	my $insert="INSERT INTO song_frequency (song_id, songbook_id) VALUES (?, ?)";
	my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
	$sth->execute($song_id, $songbook_id) || die "execute: $insert: $DBI::errstr";
	$sth->finish();
	my $message = qq {Song has been upgraded.};
	&setlistInterface($setlist, $message);
}

=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


