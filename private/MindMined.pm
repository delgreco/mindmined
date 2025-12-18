package MindMined;

=head1 MindMined.pm

Code to be called from command line or web.

=cut

use CGI;
use DBI; 
use HTML::Template;
#use HTML::Entities;
use Dotenv -load;

use FatalsToEmail    
  qw(
      Mailhost localhost
      Address marcusdelgreco@gmail.com
      Error_cache /tmp/library.tmp
      Seconds 60
      Debug 1
    );

=head2 main

Support wide array of characters in templates.  Establish database connection.

=cut

# force templates to be read as UTF-8
HTML::Template->config(utf8 => 1);

our $dbh = DBI->connect(
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

our $doc_root = "/home/mindmine/www";
our $template_path = "$doc_root/cgi-bin/private/templates";

=head2 batchTrackList()

Refresh C</audio/alpha_by_track.html> with the latest data.:w

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


1;

