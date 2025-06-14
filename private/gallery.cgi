#!/usr/bin/perl -w

# use strict, warnings and modern features
use 5.030;

use lib qw (
    ../lib
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
);

use CGI;
use HTML::Template;
use DBI;
use Dotenv -load;

use FatalsToEmail    
  qw(
      Mailhost localhost
      Address marcusdelgreco@gmail.com
      Error_cache /tmp/gallery.tmp
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
my ($template, $message) = &{\&{$action}}();

_processTemplate($template, $message);

exit;

=head2 artistInterface()

TODO

=cut

sub artistInterface {
    my $id=$cgiobject->param('id');
    my $template = HTML::Template->new(filename => "templates/mmpub/gallery/artistInterface.tmpl");
    my $first_name; my $last_name; my $email;
    my $homesite; my $dir; my $bio;
    my $add_or_update;
    if ( $id ) {
        my $select = <<~"SQL";
        SELECT first_name, last_name, email, homesite, dir, bio 
        FROM artists 
        WHERE id = ?
        SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute($id) || die "execute: $select: $DBI::errstr";
        ($first_name, $last_name, $email, $homesite, $dir, $bio) = $sth->fetchrow_array();
        $add_or_update = 'Update';
    }
    else {
        $add_or_update = 'Add';
    }
    $template->param(ADD_OR_UPDATE => $add_or_update);
    $template->param(FIRST_NAME => $first_name);
    $template->param(LAST_NAME => $last_name);
    $template->param(EMAIL => $email);
    $template->param(HOMESITE => $homesite);
    $template->param(DIR => $dir);
    $template->param(BIO => $bio);
    $template->param(ID => $id);
    return ($template, $message);
}

=head2 batchPublish()

TODO

=cut

sub batchPublish {
    my $artist_index_template = HTML::Template->new(filename => "templates/gallery/artist_index.tmpl");
    my $artist_template = HTML::Template->new(filename => "templates/gallery/artist.tmpl");
    my $image_template = HTML::Template->new(filename => "templates/gallery/image.tmpl");
    my $select = <<~"SQL";
    SELECT first_name, last_name, email, homesite, dir, bio, id 
    FROM artists 
    ORDER BY last_name, first_name
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my @artist_list;
    while (my ($first_name, $last_name, $email, $homesite, $dir, $bio, $artist_id) = $sth->fetchrow_array()) {
        my %artist;
        $artist{FIRST_NAME} = $first_name;
        $artist{LAST_NAME} = $last_name;
        $artist{DIR} = $dir;
        push(@artist_list, \%artist);
        ### get a list of the artist's images
        my $select = <<~"SQL";
        SELECT COUNT(*) FROM gallery 
        WHERE artist_id = $artist_id
        SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        my ($total_images_from_artist) = $sth->fetchrow_array();
        ### get a list of the artist's images
        my $select = <<~"SQL";
        SELECT title, url, description, year, id 
        FROM gallery 
        WHERE artist_id = $artist_id
        SQL
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        # reset filename counter
        my $counter = 0;
        my @image_list;
        while (my ($title, $url, $description, $year, $image_id) = $sth->fetchrow_array()) {
            $counter++;
            my %image_link;
            $image_link{FILENAME} = "${counter}.html";
            $image_link{TITLE} = $title;
            $image_link{YEAR} = $year;
            $image_template = compile_images($artist_id, $image_template, $counter);
            $image_template->param(TITLE => $title);
            $image_template->param(URL => $url);
            # populate arrow links for previous and next image pages
            my $next_page = $counter + 1;
            my $previous_page = $counter - 1;
            # override these values if we are on the 1st or last image page
            if ($counter == 1) {
                $previous_page = $total_images_from_artist;
            }
            else {
                if ($counter == $total_images_from_artist) {
                    $next_page = 1;
                }
            }
            $image_template->param(NEXT_PAGE => "${next_page}.html");
            $image_template->param(PREVIOUS_PAGE => "${previous_page}.html");
            $description =~ s/\"//g;
            $description =~ s/<br>//g;
            $description =~ s/\n//g;
            if ( ! $description ) {
                $description = $year;
            }
            $image_template->param(DESCRIPTION => $description);
            $image_template->param(BIO => $bio);
            $image_template->param(DIR => $dir);
            $image_template->param(FIRST_NAME => $first_name);
            $image_template->param(LAST_NAME => $last_name);
            #$image_template->param(YEAR => $year);
            $image_template->param(EMAIL => $email);
            $image_template->param(HOMESITE => $homesite);
            $image_template->param(KEYWORDS => "$first_name $last_name,$title,art from $year,online art gallery,fine art,digital art,independent artists");
            $image_template->param(PAGETITLE => "$title - $first_name $last_name - $year");
            push(@image_list, \%image_link);
            my $image_output = $image_template->output;
            open(IMAGE, "> $ENV{DOCUMENT_ROOT}/gallery/$dir/${counter}.html");
            print IMAGE "$image_output";
            close(IMAGE);
        }
        $artist_template->param(BIO => $bio);
        $artist_template->param(FIRST_NAME => $first_name);
        $artist_template->param(LAST_NAME => $last_name);
        $artist_template->param(EMAIL => $email);
        $artist_template->param(HOMESITE => $homesite);
        $artist_template->param(IMAGES => \@image_list);
        my $artist_output = $artist_template->output;
        open(ARTIST, "> $ENV{DOCUMENT_ROOT}/gallery/$dir/index.html");
        print ARTIST "$artist_output";
        close(ARTIST);
    }
    $artist_index_template->param(ARTISTS => \@artist_list);
    my $artist_index_output = $artist_index_template->output;
    open(ARTIST_INDEX, "> $ENV{DOCUMENT_ROOT}/gallery/artists.html");
    print ARTIST_INDEX "$artist_index_output";
    close(ARTIST_INDEX);
    my $message = qq |The Gallery has been published in batch.  The online pages have all been refreshed from the database.|;
    mainInterface($message);
}

=head2 compileImage()

TODO

=cut

sub compile_images {
    my $artist_id = $_[0]; 
    my $t = $_[1];
    my $image_num = $_[2];
    my $select = <<~"SQL";
    SELECT year FROM gallery 
    WHERE artist_id = ?
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute($artist_id) || die "execute: $select: $DBI::errstr";
    my @entry_loop;
    my $counter = 0;
    while (my ($year) = $sth->fetchrow_array()) {
         $counter++;
         my %entry;
         $entry{COUNTER} = $counter;
         $entry{FILENAME} = "${counter}.html";
         unless ( $counter == $image_num ) {
            $entry{LINKED} = 1;
         }
         push(@entry_loop, \%entry);
    }
    $t->param(ENTRIES => \@entry_loop);
    return $t;
}

=head2 deleteArtist()

TODO

=cut

sub deleteArtist {
    my $id=$cgiobject->param('id'); 
    my $select = <<~"SQL";
    SELECT first_name, last_name 
    FROM artists WHERE id = ?
    SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute($id) || die "execute: $select: $DBI::errstr";
    my ($first_name, $last_name) = $sth->fetchrow_array();
    #
    my $delete="DELETE FROM artists WHERE id = ?";
    $sth = $dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    my $message = qq {$first_name $last_name deleted from the database.};
    mainInterface($message);
}

=head2 deleteImage()

TODO

=cut

sub deleteImage {
    my $id=$cgiobject->param("id"); 
    my $select="SELECT title FROM gallery WHERE id = '$id'";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($title) = $sth->fetchrow_array();
    #
    my $delete="DELETE FROM gallery WHERE id ='$id'";
    $sth = $dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    $sth->finish();
    my $message = qq {$title deleted from the database.};
    mainInterface($message);
}

=head2 imageInterface()

TODO

=cut

sub imageInterface {
    my $t = HTML::Template->new(filename => "templates/mmpub/gallery/imageInterface.tmpl");
    my $id=$cgiobject->param("id"); 
    my $title; my $url; my $description; my $year;
    my $image_id; my $artist_id;
    if ($id) {
        my $select="SELECT title, url, description, year, id, artist_id FROM gallery WHERE id = '$id'";
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        ($title, $url, $description, $year, $image_id, $artist_id) = $sth->fetchrow_array();
        $t->param(TITLE => $title);
        $t->param(URL => $url);
        $t->param(DESCRIPTION => $description);
        $t->param(YEAR => $year);
        $t->param(ID => $id);
    }
    # get artist info
    my $select = <<"SQL";
    SELECT first_name, last_name, id 
    FROM artists ORDER BY last_name, first_name
SQL
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my @artist_loop;
    while (my ($first_name, $last_name, $id_option) = $sth->fetchrow_array()) {
        my %row;
        if ($artist_id == $id_option) {$row{SELECTED} = 'SELECTED';}
        $row{ARTIST_ID} = $id_option;
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        push(@artist_loop, \%row);
    }
    $t->param(PAGETITLE => 'Save Image');
    $t->param(ARTIST_OPTIONS => \@artist_loop);
    return ($t, $message);
}

=head2 mainInterface()

TODO

=cut

sub mainInterface {  # the default interface for managing the Gallery
    my $t = HTML::Template->new(filename => "templates/mmpub/gallery/mainInterface.tmpl");
    my $message = $_[0];
    my $select="SELECT last_name, first_name, email, id FROM artists ORDER BY last_name"; 
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my $last_name; my $first_name; my $email; my $artist_id;
    my @artists_loop; my $i;
    while (my ($last_name, $first_name, $email, $artist_id) = $sth->fetchrow_array()) {
        my %row;
        $i++;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = qq {#CCCCCC};
        }
        else { 
            $row{BGCOLOR} = qq {#FFFFFF};
        }
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        $row{EMAIL} = $email;
        $row{ID} = $artist_id;
        push(@artists_loop, \%row);
    }
    $t->param(ARTISTS => \@artists_loop);
    $select="SELECT title, url, description, id, artist_id FROM gallery ORDER BY title"; 
    $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my @images_loop;
    while (my ($title, $url, $description, $image_id, $artist_id) = $sth->fetchrow_array()) {
        my %row;
        if (length($description) > 70) {
            $description = substr($description, 0, 69);
            $description .= qq {...};
        }
        my $select="SELECT last_name, first_name FROM artists WHERE id = '$artist_id'"; 
        my $sth = $dbh->prepare($select);
        $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
        my ($last_name, $first_name) = $sth->fetchrow_array();
        $i++;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = qq {#CCCCCC};
        }
        else { 
            $row{BGCOLOR} = qq {#FFFFFF};
        }
        $row{TITLE} = $title;
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        $row{DESCRIPTION} = $description;
        $row{URL} = $url;
        $row{ID} = $image_id;
        $row{URL} = $url;
        push(@images_loop, \%row);
    }
    my $artist_count = @artists_loop;
    my $image_count = @images_loop;
    $t->param(ARTIST_COUNT => $artist_count);
    $t->param(IMAGE_COUNT => $image_count);
    $t->param(PAGETITLE => 'Gallery Publisher');
    $t->param(ARTISTS => \@artists_loop);
    $t->param(IMAGES => \@images_loop);
    return ($t, $message);
}

=head2 _processTemplate()

TODO

=cut

sub _processTemplate {
    my $t = $_[0];
    my $message = $_[1];
    $t->param(SCRIPT_NAME => $ENV{SCRIPT_NAME});
    #$t->param(MESSAGE => $message);
    my $output = $t->output;
    print "Content-type: text/html\n\n";
    print $output;
}

=head2 saveArtist()

TODO

=cut

sub saveArtist {
    my $first_name=$cgiobject->param("first_name"); 
    my $last_name=$cgiobject->param("last_name"); 
    my $email=$cgiobject->param("email"); 
    my $homesite=$cgiobject->param("homesite"); 
    my $dir=$cgiobject->param("dir"); 
    my $bio=$cgiobject->param("bio"); 
    my $id=$cgiobject->param("id"); 
    if ($id) {
        # when editing or viewing, query the database about the product
        my $update="UPDATE artists SET first_name = ? ,last_name = ?, email = ?, homesite = ?, bio = ? WHERE id = '$id'";
        my $sth = $dbh->prepare($update);
        $sth->execute($first_name, $last_name, $email, $homesite, $bio) || die "sth->execute($update): $DBI::errstr\n";
        $sth->finish();
        $message = qq {$first_name $last_name updated.};
    }
    else {
        my $insert="INSERT INTO artists (first_name, last_name, email, homesite, dir, bio) VALUES (?, ?, ?, ?, ?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($first_name, $last_name, $email, $homesite, $dir, $bio) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        my $id = $sth->{mysql_insertid} || $sth->{insertid}; 
        $message = qq {$first_name $last_name added.};
        # construct the rec_artist directory and index page
        system("mkdir $ENV{DOCUMENT_ROOT}/gallery/$dir");
    }
    mainInterface($message);
}

=head2 saveImage()

TODO

=cut

sub saveImage {
    my $title=$cgiobject->param('title'); 
    my $url=$cgiobject->param('url'); 
    my $description=$cgiobject->param('description'); 
    my $year=$cgiobject->param('year'); 
    my $artist_id=$cgiobject->param('artist_id'); 
    my $id=$cgiobject->param('id'); 
    my $message;
    if ($id) {
        my $update="UPDATE gallery 
        SET title = ?, url = ?, description = ?, year = ? 
        WHERE id = ?";
        my $sth = $dbh->prepare($update);
        $sth->execute($title, $url, $description, $year, $id) || die "sth->execute($update): $DBI::errstr\n";
        $sth->finish();
        $message = qq |$title updated.|;
    }
    else {
        my $insert="INSERT INTO gallery 
        (title, url, description, year, artist_id) 
        VALUES 
        (?, ?, ?, ?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($title, $url, $description, $year, $artist_id) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        my $id = $sth->{mysql_insertid} || $sth->{insertid}; 
        $sth->finish();
        # get artist name
        my $select="SELECT first_name, last_name 
        FROM artists 
        WHERE id = ?";
        $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute($artist_id) || die "execute: $select: $DBI::errstr";
        my ($first_name, $last_name) = $sth->fetchrow_array();
        $message = qq |$title added.|;
    }
    mainInterface($message);
}



=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut

