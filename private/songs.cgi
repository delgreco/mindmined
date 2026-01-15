#!/usr/bin/perl

# use strict, warnings and modern features
use 5.030;

use lib qw(
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
    ../lib
    .
);

use MindMined;

my $cgi = new CGI;

my $action=$cgi->param('action');
$action = 'mainInterface' if ! $action;

my %dispatch = (
    addToSongBook      => \&addToSongBook,
    adjustFrequency    => \&adjustFrequency,
    deleteSong         => \&deleteSong,
    mainInterface      => \&mainInterface,
    removeFromSongBook => \&removeFromSongBook,
    saveSong           => \&saveSong,
    saveSongBook       => \&saveSongBook,
    setlist            => \&setlist,
    song               => \&song,
    songBookInterface  => \&songBookInterface,
    viewSong           => \&viewSong,
);

if ( my $code = $dispatch{$action} ) {
    $code->();
}
else {
    die "Unknown action: $action\n";
}
exit;

=head2 addToSongBook

TODO

=cut

sub addToSongBook {
    my $song_id=$cgi->param('song_id');
    my $songbook_id=$cgi->param('songbook_id');
    my $message;
    #my $song_id = $_[0];
    #my $songbook_id = $_[1];
    # make sure it's not already there for some strange reason
    my $select = <<~"SQL";
    SELECT song_id 
    FROM songs_songbooks
    WHERE song_id = ?
    AND songbook_id = ?
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($song_id, $songbook_id);
    my ($id) = $sth->fetchrow_array();
    # unless this song/songbook association already exists, add it
    unless ($id) {
        my $insert="INSERT INTO songs_songbooks (song_id, songbook_id) VALUES (?, ?)";
        my $sth = $MindMined::dbh->prepare($insert);
        $sth->execute($song_id, $songbook_id);
        # give it a starting setlist frequency of '5'
        my $count = 5;
        while ($count > 0) {
            my $insert="INSERT INTO song_frequency (song_id, songbook_id) VALUES (?, ?)";
            my $sth = $MindMined::dbh->prepare($insert);
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

=head2 adjustFrequency

TODO

=cut

sub adjustFrequency {
    my $id=$cgi->param("id"); 
    my $setlist=$cgi->param("setlist"); 
    my $songbook_id=$cgi->param("songbook_id"); 
    if ($id =~ /^\+/) {
        $id =~ s/\+//;
        _upgradeSong($id, $setlist, $songbook_id);
    }
    elsif ($id =~ /^\-/) {
        $id =~ s/\-//;
        _downgradeSong($id, $setlist, $songbook_id);
    }
    else {
        my $message = qq {Select a radio button in order to adjust the frequency of a setlist song.};
        setlist($setlist, $message);
    }
}

=head2 deleteSong

Given the id for a song, delete that song and return to the main screen.

=cut

sub deleteSong {
    my $id=$cgi->param('id');
    my $delete="DELETE FROM songs
    WHERE id = ?";
    my $sth = $MindMined::dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    my $message = qq |Song deleted.|;
    mainInterface($message);
}

=head2 mainInterface

The main Songbook screen.

=cut

sub mainInterface { 
    my $message = $_[0];
    my $songbook_id = $_[1];
    $songbook_id=$cgi->param('songbook_id') if ! $songbook_id;
    my $t = HTML::Template->new(filename => 'templates/songs/songsMainInterface.tmpl');
    my $where; my @bind_variables;
    if ( $songbook_id ) {
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
    my $sth = $MindMined::dbh->prepare($select);
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
        $row{SONGBOOK_ID} = $songbook_id;
        $row{MORE_INFO_URL} = $more_info_url;
        $row{AUDIO_URL} = $audio_url;
        $row{CHORDSHEET} = $chordsheet;
        # $row{SONGBOOK_ID} = $songbook_id;
        # $row{SONGBOOK} = $songbook;
        if ( $i % 2 == 0 ) {
            $bgcolor = qq {#CCCCCC};
        }
        else { 
            $bgcolor = qq {#FFFFFF};
        }
        $row{BGCOLOR} = $bgcolor;
        push(@songs, \%row);
    }
    $t = _getSongsTopTemplate(
        template    => $t,
        songbook_id => $songbook_id,
    );
    # populate songs dropdown
    $t = _getAddSongsDropdown($t, $songbook_id); 
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

=head2 removeFromSongbook

Remove a song from a songbook.

=cut

sub removeFromSongBook {
    my $song_id=$cgi->param('song_id'); 
    my $songbook_id=$cgi->param('songbook_id'); 
    my $message;
    # disassociate song from songbook
    my $delete="DELETE FROM songs_songbooks 
    WHERE song_id ='$song_id'
    AND songbook_id = '$songbook_id'";
    my $sth = $MindMined::dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    # remove all rows of this song/songbook in the frequency table
    $delete="DELETE FROM song_frequency 
    WHERE song_id ='$song_id'
    AND songbook_id = '$songbook_id'";
    $sth = $MindMined::dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    $message = qq |Song removed from SongBook.|;
    mainInterface($message, $songbook_id);
}

=head2 saveSong

Add or edit a song.

=cut

sub saveSong {
    my $title=$cgi->param("title"); 
    my $credits=$cgi->param("credits"); 
    my $more_info_url=$cgi->param("more_info_url"); 
    my $audio_url=$cgi->param("audio_url"); 
    my $chordsheet=$cgi->param("chordsheet"); 
    my $id=$cgi->param("id"); 
    # return to a specific songbook if we started there
    my $songbook_id=$cgi->param("songbook_id"); 
    my $message;
    if ($id) {  # update existing song
        my $update="UPDATE songs 
        SET title = ?, credits = ?, more_info_url = ?, audio_url = ?, chordsheet = ?
        WHERE id = '$id'";
        my $sth = $MindMined::dbh->prepare($update);
        $sth->execute($title, $credits, $more_info_url, $audio_url, $chordsheet);
        $message = "'$title' has been updated.";
    }
    else {  # add new song
        my $insert="INSERT INTO songs (title, credits, more_info_url, audio_url, chordsheet) VALUES (?, ?, ?, ?, ?)";
        my $sth = $MindMined::dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($title, $credits, $more_info_url, $audio_url, $chordsheet) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        $id = $sth->{mysql_insertid} || $sth->{insertid};
        $sth->finish();
        $message = qq {$title has been added.};
    }
    viewSong($id);
}

=head2 saveSongBook

Add or update a songbook.

=cut

sub saveSongBook {
    my $name=$cgi->param('name'); 
    my $id=$cgi->param('id'); 
    my $message;
    if ($id) {  # update existing song
        my $update="UPDATE songbooks 
        SET name = ?
        WHERE id = ?";
        my $sth = $MindMined::dbh->prepare($update);
        $sth->execute($name, $id) || die "sth->execute($update): $DBI::errstr\n";
        $message = qq |The songbook called $name has been updated.|;
    }
    else {  # add new songbook
        my $insert="INSERT INTO songbooks (name) VALUES (?)";
        my $sth = $MindMined::dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($name) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        $id = $sth->{mysql_insertid} || $sth->{insertid};
        $sth->finish();
        $message = qq |A songbook called $name has been added.|;
    }
    mainInterface($message, $id);
}

=head2 setList

Screen to manage a setlist: a weighted selection of N songs from a songbook.

=cut

sub setlist {
    my $setlist = $_[0];
    my $message = $_[1];
    my $limit=$cgi->param('number_of_songs'); 
    my $songbook_id=$cgi->param('songbook_id'); 
    my $number_of_songs=$cgi->param('number_of_songs'); 
    my $include_exercises=$cgi->param('include_exercises'); 
    my $t = HTML::Template->new(filename => 'templates/songs/setlist.tmpl');
    my @songs_loop;
    if ( $setlist ) {  # if only adjusting frequency, reprint remembered setlist
        my @song_ids = split(/,/, $setlist);
        foreach my $id (@song_ids) {
            my %row;
            # determine current frequency rate for this song
            my $select = <<~"SQL";
            SELECT COUNT(*) 
            FROM song_frequency 
            WHERE song_id = ?
            AND songbook_id = ?
            SQL
            my $sth = $MindMined::dbh->prepare($select);
            $sth->execute($id, $songbook_id);
            my ($freq) = $sth->fetchrow_array();
            if ( $freq == 1 ) {
                $row{DELETE} = 1;
            }
            $select = <<~"SQL";
            SELECT title, credits, audio_url 
            FROM songs 
            WHERE id = ?
            SQL
            $sth = $MindMined::dbh->prepare($select);
            $sth->execute($id);
            my ($title, $credits, $audio_url) = $sth->fetchrow_array();
            $row{TITLE} = $title;
            $row{CREDITS} = $credits;
            $row{ID} = $id;
            $row{FREQUENCY_RATE} = $freq;
            push(@songs_loop, \%row);
        }
    }
    else {  # generate fresh setlist
        my $select = <<~"SQL";
        SELECT song_frequency.song_id, songs.title, songs.credits, songs.audio_url 
        FROM song_frequency 
        JOIN songs 
        ON song_frequency.song_id = songs.id 
        WHERE song_frequency.songbook_id = ?
        ORDER BY RAND()
        SQL
        my $sth = $MindMined::dbh->prepare($select);
        $sth->execute($songbook_id);
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
            my $select = <<~"SQL";
            SELECT COUNT(*) 
            FROM song_frequency 
            WHERE song_id = ?
            AND songbook_id = ?
            SQL
            my $sth = $MindMined::dbh->prepare($select);
            $sth->execute($id, $songbook_id);
            my ($freq) = $sth->fetchrow_array();
            # there will either be zero or one occurrence of this song 
            # in the table, so then we present an upgrade-or-delete option
            if ( $freq == 1 ) {
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

=head2 song

Screen to edit a song.

=cut

sub song { 
    my $message = $_[0];
    my $id=$cgi->param("id"); 
    # so we can return to the songbook we were looking at
    my $songbook_id=$cgi->param("songbook_id");
    my $t = HTML::Template->new(
        filename => 'templates/songs/song.tmpl'
    );
    my $select = <<~"SQL";
    SELECT title, credits, more_info_url, audio_url, chordsheet
    FROM songs 
    WHERE id = ?
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($id);
    my ($title, $credits, $more_info_url, $audio_url, $chordsheet) = $sth->fetchrow_array();
    $t = _getSongsTopTemplate(
        template    => $t,
        songbook_id => $id,
    );
    $t->param(SONG_INTERFACE => 1);
    $t->param(TITLE => $title);
    $t->param(CREDITS => $credits);
    $t->param(MORE_INFO_URL => $more_info_url);
    $t->param(AUDIO_URL => $audio_url);
    $t->param(CHORDSHEET => $chordsheet);
    $t->param(ID => $id);
    $t->param(SONGBOOK_ID => $songbook_id);
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;
}

=head2 songbook

Screen to view and manage a songbook.

=cut

sub songbook { 
    my $message = $_[0];
    my $id=$cgi->param('id'); 
    my $t = HTML::Template->new(
        filename => 'templates/songs/songbook.tmpl'
    );
    my $select = <<~"SQL";
    SELECT name 
    FROM songbooks 
    WHERE id = ?
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($id);
    my ($name) = $sth->fetchrow_array();
    $t->param(NAME => $name);
    $t->param(ID => $id);
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    $t = _getSongsTopTemplate(
        template    => $t,
        songbook_id => $id,
    );
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;
}

=head2 viewSong

Screen to view a song.

=cut

sub viewSong {
    my $id = $_[0] || $cgi->param('id'); 
    # so we can return to the songbook we were looking at
    my $songbook_id=$cgi->param('songbook_id');
    my $t = HTML::Template->new(filename => 'templates/songs/viewSong.tmpl');
    my $select = <<~"SQL";
    SELECT title, credits, more_info_url, audio_url, chordsheet
    FROM songs 
    WHERE id = ?
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($id);
    my ($title, $credits, $more_info_url, $audio_url, $chordsheet) = $sth->fetchrow_array();
    $t->param(TITLE => $title);
    $t->param(PAGETITLE => "$title ($credits)");
    $t->param(CREDITS => $credits);
    $t->param(MORE_INFO_URL => $more_info_url);
    $t->param(AUDIO_URL => $audio_url);
    # replace line breaks with <br>
    #$chordsheet =~ s/\n/<br>/g;
    $t->param(CHORDSHEET => $chordsheet);
    $t->param(ID => $id);
    $t->param(SONGBOOK_ID => $songbook_id);
    #$t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    my $output = $t->output;
    print "Content-type:text/html\n\n";
    print $output;  
}

=head1 INTERNAL SUBS

=head2 _downgradeSong

TODO

=cut

sub _downgradeSong {
    my $song_id = $_[0]; 
    my $setlist = $_[1]; 
    my $songbook_id = $_[2];
    my $delete="DELETE FROM song_frequency 
    WHERE song_id = '$song_id' 
    AND songbook_id = '$songbook_id'
    LIMIT 1";
    my $sth = $MindMined::dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    my $message = qq {Song has been downgraded.};
    setlistInterface($setlist, $message);
}

=head2 _getAddSongsDropdown

TODO

=cut

sub _getAddSongsDropdown {
    my $template = $_[0];
    my $songbook_id = $_[1];  # when passing a songbook id,
    # we are telling this sub that we want the songs that DON'T
    # appear in this songbook yet, so they can be added via this dropdown
    my @songbook_song_ids = _getSongBookSongIDs($songbook_id); 
    my $select = <<~"SQL";
    SELECT title, id
    FROM songs
    ORDER BY title
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute();
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
    $template->param(SONGS_OPTIONS => \@songs);
    return $template;
}

=head2 _getSongBookDropdown

TODO

=cut

sub _getSongBookDropdown {
    my $template = $_[0];
    my $songbook_id = $_[1];
    my $select = <<~"SQL";
    SELECT name, id 
    FROM songbooks 
    ORDER BY name
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute();
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
    $template->param(SONGBOOKS => \@songbooks);
    return $template;
}

=head2 _getSongBookName

TODO

=cut

sub _getSongBookName {
    my $songbook_id = $_[0];
    my $select = <<~"SQL";
    SELECT name
    FROM songbooks
    WHERE id = ?
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($songbook_id);
    my @songs;
    my ($name) = $sth->fetchrow_array();
    return $name;
}

=head2 _getSongBookSongIDs

TODO

=cut

sub _getSongBookSongIDs {
    my $songbook_id = $_[0];
    my $select = <<~"SQL";
    SELECT id 
    FROM songs
    JOIN songs_songbooks
    ON songs_songbooks.song_id = songs.id
    WHERE songs_songbooks.songbook_id = ?
    ORDER BY songs.title
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute($songbook_id);
    my @song_ids;
    while (my ($id) = $sth->fetchrow_array()) {
        push(@song_ids, $id);
    }
    return @song_ids;
}

=head2 _getSongsTopTemplate

TODO

=cut

sub _getSongsTopTemplate {
    my %arg = @_;
    my $template = $arg{template};
    my $songbook_id = $arg{songbook_id};
    $template = _getSongBookDropdown($template, $songbook_id);  
    return $template;
}

=head2 _getToday

TODO

=cut

sub _getToday {
    my $select = <<~"SQL";
    SELECT DAYOFMONTH(NOW()), MONTHNAME(NOW()), YEAR(NOW())
    SQL
    my $sth = $MindMined::dbh->prepare($select);
    $sth->execute();
    my ($day_of_month, $month, $year) = $sth->fetchrow_array();
    return($day_of_month, $month, $year);
}

=head2 _upgradeSong

TODO

=cut

sub _upgradeSong {
    my $song_id = $_[0];
    my $setlist = $_[1];
    my $songbook_id = $_[2];
    my $insert="INSERT INTO song_frequency (song_id, songbook_id) VALUES (?, ?)";
    my $sth = $MindMined::dbh->prepare($insert);
    $sth->execute($song_id, $songbook_id);
    $sth->finish();
    my $message = qq {Song has been upgraded.};
    setlistInterface($setlist, $message);
}

=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


