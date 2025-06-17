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

my $cgiobject = new CGI;

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

my $action=$cgiobject->param('action');
$action = 'mainInterface' if ! $action;

# run the sub by the same name as $action
my ($template, $message) = &{\&{$action}}();

_processTemplate($template, $message);

exit;

=head2 authorInterface

TODO

=cut

sub authorInterface {
    my $id=$cgiobject->param('id'); 
    my $t = HTML::Template->new(filename => "templates/mmpub/library/authorInterface.tmpl");
    my $add_or_update;
    my $email; my $alt_emails; my $email_display; my $homesite;
    my $bio; my $last_name; my $first_name; my $published;
    if ( $id ) {
        my $select = <<~"SQL";
        SELECT email, alt_emails, email_display, homesite, bio, last_name, first_name, published
        FROM authors 
        WHERE id = ?
        SQL
        my $sth = $dbh->prepare($select);
        $sth->execute($id);
        ($email, $alt_emails, $email_display, $homesite, $bio, $last_name, $first_name, $published) = $sth->fetchrow_array();
        $sth->finish();
    }
    if ( $email_display eq 'mailto' ) {
        $t->param(MAILTO => 1);
    }
    else {
        $t->param(OBFUSCATED => 1);
    }
    $t->param(FIRST_NAME => $first_name);
    $t->param(LAST_NAME => $last_name);
    $t->param(EMAIL => $email);
    $t->param(ALT_EMAILS => $alt_emails);
    $t->param(HOMESITE => $homesite);
    $t->param(BIO => $bio);
    $t->param(ID => $id);
    $t->param(PUBLISHED => $published);
    return ($t, $message);
}

=head2 batchLibrary

TODO

=cut

sub batchLibrary {
    my $title_id = $_[0];
    my $where = "published = 'yes'";
    my @bind_vars;
    if ( $title_id ) {
        $where = 'id = ?';
        push(@bind_vars, $title_id);
    }
    my $select = <<"SQL";
    SELECT pagetitle, genre, body2, image_URL, description, filename, author_id, id, image_alt_text, keywords 
    FROM titles
    WHERE $where
SQL
    # construct the by_title genre indexes
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute(@bind_vars) || die "execute: $select: $DBI::errstr";
    while (my ($pagetitle, $genre, $body, $image_URL, $description, $filename, $author_id, $id, $image_alt_text, $keywords) = $sth->fetchrow_array()) {
        my $t = HTML::Template->new(filename => "templates/library/title.tmpl");
        # grab information about the author
        my $select = <<"SQL";
        SELECT last_name, first_name, email, email_display, homesite, bio 
        FROM authors 
        WHERE id = '$author_id'
SQL
        my $sth = $dbh->prepare($select);
        $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
        my ($last_name, $first_name, $email, $email_display, $homesite, $bio) = $sth->fetchrow_array();
        if ( $email_display eq 'mailto' ) {
            $t->param(MAILTO => 1);
        }
        else {  # obfuscate the email
            $email =~ s/\./ \[dot\] /;
            $email =~ s/\@/ \[at\] /;   
        }
        $t->param(EMAIL => $email);
        # create the library page
        ######
        # substitute variable values
        ######
        $t->param(TITLE => $pagetitle);
        $t->param(PAGETITLE => "$pagetitle by $first_name $last_name");
        my $author_closeup_file = "${first_name}_${last_name}";
        $author_closeup_file =~ s/ /_/g;
        $t->param(AUTHOR_CLOSEUP_FILE => $author_closeup_file);
        $t->param(DESCRIPTION => $description);
        $t->param(KEYWORDS => $keywords);
        $t->param(LAST_NAME => $last_name);
        $t->param(FIRST_NAME => $first_name);
        #$t->param(GENRE => $genre);
        $t->param(BIO => $bio);
        $t->param(HOMESITE => $homesite);
        $t->param(IMAGE_URL => $image_URL);
        $t->param(IMAGE_ALT_TEXT => $image_alt_text);
        $t->param(BODY => $body);
        $t->param(WINDOW_STATUS => "$first_name $last_name on mindmined.com");
        my $output = $t->output;
        open(FINAL, "> $ENV{DOCUMENT_ROOT}/public_library/$genre/$filename") or die "Couldn't open file to write: $!";
        print FINAL "$output";
        close FINAL;
    }
    # make the indexes
    _indexLibrary();
    my $message = qq |The entire library has been refreshed.|;
    mainInterface($message);
}

=head2 bodyInterface

TODO

=cut

sub bodyInterface {
    my $id=$cgiobject->param('id');
    my $template = HTML::Template->new(filename => "templates/mmpub/library/bodyInterface.tmpl");
    # get pagetitle
    my $select = <<~"SQL";
    SELECT pagetitle FROM titles 
    WHERE id = ?
    SQL
    my $sth = $dbh->prepare($select);
    $sth->execute($id);
    my ($pagetitle) = $sth->fetchrow_array();
    $template->param(PAGETITLE => $pagetitle);
    $template->param(ID => $id);
    return ($template, $message);
}

=head2 deleteAuthor

TODO

=cut

sub deleteAuthor {
    my $id=$cgiobject->param('id'); 
    my $select="SELECT first_name, last_name 
    FROM authors 
    WHERE id = ?";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute($id) || die "execute: $select: $DBI::errstr";
    my ($first_name, $last_name) = $sth->fetchrow_array();
    $sth->finish();
    my $delete="DELETE FROM authors WHERE id ='$id'";
    $sth = $dbh->prepare($delete);
    $sth->execute() || die "sth->execute($delete): $DBI::errstr\n";
    my $message = qq |$first_name $last_name deleted from the database.|;
    mainInterface($message);
}

=head2 deleteTitle

TODO

=cut

sub deleteTitle {
    my $id=$cgiobject->param('id'); 
    my $select="SELECT pagetitle 
    FROM titles 
    WHERE id = ?";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute($id) || die "execute: $select: $DBI::errstr";
    my ($pagetitle) = $sth->fetchrow_array();
    my $delete="DELETE FROM titles WHERE id = ?";
    $sth = $dbh->prepare($delete);
    $sth->execute($id) || die "sth->execute($delete): $DBI::errstr\n";
    my $message = qq {$pagetitle deleted from the database.};
    mainInterface($message);
}

=head2 _indexLibrary

TODO

=cut

sub _indexLibrary {
    _makeGenreIndexes();
    _makeAuthorIndexes();
}

=head2 mainInterface

TODO

=cut

sub mainInterface {  # the default interface for managing the Library
    my $message = $_[0];
    my $template = HTML::Template->new(filename => "templates/mmpub/library/mainInterface.tmpl");
    my $order_by=$cgiobject->param("order_by"); 
    if ($order_by eq "author") {
        $order_by = "last_name, first_name";
    }
    else {
        $order_by = "pagetitle";
    }
    # list authors
    my $select="SELECT last_name, first_name, email, homesite, bio, id FROM authors ORDER BY last_name, first_name";
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my $i; my @authors;
    while (my ($last_name, $first_name, $email, $homesite, $bio, $id) = $sth->fetchrow_array()) {
        my %row;
        $i++;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = '#CCCCCC';
        }
        else { 
            $row{BGCOLOR} = '#FFFFFF';
        }
        $bio = substr($bio, 0, 60);
        $bio .= qq {...};
        $row{LAST_NAME} = $last_name;
        $row{FIRST_NAME} = $first_name;
        $row{EMAIL} = $email;
        $row{HOMESITE} = $homesite;
        $row{BIO} = $bio;
        $row{ID} = $id;
        push(@authors, \%row);
    }
    # list titles
    $select="SELECT titles.pagetitle, titles.genre, titles.filename, authors.first_name, authors.last_name, titles.id 
    FROM titles
    JOIN authors
    ON titles.author_id = authors.id 
    ORDER BY $order_by";
    $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my @titles;
    while (my ($title, $genre, $filename, $first_name, $last_name, $id) = $sth->fetchrow_array()) {
        my %row;
        $i++;
        if ($i % 2 == 0) {
            $row{BGCOLOR} = '#CCCCCC';
        }
        else { 
            $row{BGCOLOR} = '#FFFFFF';
        }
        $row{TITLE} = $title;
        $row{GENRE} = $genre;
        $row{FILENAME} = $filename;
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        $row{ID} = $id;
        push(@titles, \%row);
    }
    $template->param(AUTHORS => \@authors);
    $template->param(TITLES => \@titles);
    return ($template, $message);
}

=head2 _makeAuthorIndexes

TODO

=cut

sub _makeAuthorIndexes {
    my $authors_index_template = HTML::Template->new(filename => "templates/library/authors.tmpl");
    my @author_loop;
    # get total authors in library
    my $select = "SELECT COUNT(*) FROM authors";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($total_authors) = $sth->fetchrow_array();
    $select = "SELECT first_name, last_name, homesite, email, email_display, bio, id 
    FROM authors 
    WHERE published = 1
    ORDER BY last_name, first_name";
    $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    while (my ($first_name, $last_name, $homesite, $email, $email_display, $bio, $id) = $sth->fetchrow_array()) {
        my $author_page_template = HTML::Template->new(filename => "templates/library/author.tmpl");
        # assemble title list
        my $select = "SELECT pagetitle, genre, filename, image_url
        FROM titles 
        WHERE author_id = '$id'
        AND published = 'yes'
        ORDER BY pagetitle";
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        my @title_loop;
        while (my ($pagetitle, $genre, $filename, $image_url) = $sth->fetchrow_array()) {
            my $title_url = "https://www.mindmined.com/public_library/$genre/$filename";
            my %title;
            $title{PAGETITLE} = $pagetitle;
            $title{IMAGE_URL} = $image_url;
            $title{GENRE} = $genre;
            $title{TITLE_URL} = $title_url;
            push(@title_loop, \%title);
        }
        my $closeup_file = "${first_name}_${last_name}.html";
        $closeup_file =~ s/ /_/g;
        my $closeup_path = "$ENV{DOCUMENT_ROOT}/public_library/authors/$closeup_file";
        my $closeup_url = "/public_library/authors/$closeup_file";
        # populate author index
        my $short_bio = substr($bio, 0, 90);
        $short_bio .= qq {...} if length($bio) > 90;
        # remove bolding
        $short_bio =~ s/<b>//g;
        $short_bio =~ s/<\/b>//g;
        my %author;
        $author{FIRST} = $first_name;
        $author{LAST} = $last_name;
        $author{CLOSEUP_URL} = $closeup_url;
        $author{BIO} = $short_bio;
        push(@author_loop, \%author);
        # populate individual author page
        # replace loops
        $author_page_template->param(TITLES => \@title_loop);
        # replace single vars
        if ( $email ) {  
            # call with a true value (1) to include the conditional content
            if ( $email_display eq 'mailto' ) {
                $author_page_template->param(MAILTO => 1);
            }
            else {  # obfuscate the email
                $email =~ s/\./ \[dot\] /g;
                $email =~ s/\@/ \[at\] /g;
            }
            $author_page_template->param(EMAIL => $email);
        }
        $author_page_template->param(HOMESITE => $homesite);
        $author_page_template->param(FIRST => $first_name);
        $author_page_template->param(LAST => $last_name);
        $author_page_template->param(BIO => $bio);
        $author_page_template->param(PAGETITLE => "$first_name $last_name on mindmined.com");
        # strip quotes from bio for use in meta tage
        $bio =~ s/"//g;
        $author_page_template->param(DESCRIPTION => "$bio");
        $author_page_template->param(KEYWORDS => "$first_name $last_name,full text,");
        $author_page_template->param(WINDOW_STATUS => "$first_name $last_name on mindmined.com");
        my $output = $author_page_template->output;
        open(AUTHOR_PAGE, "> $closeup_path");
        print AUTHOR_PAGE "$output";
        close(AUTHOR_PAGE);
    }
    # replace loops
    $authors_index_template->param(AUTHORS => \@author_loop);
    my $output = $authors_index_template->output;
    open(AUTHORS_INDEX, "> $ENV{DOCUMENT_ROOT}/public_library/authors/index.html");
    print AUTHORS_INDEX "$output";
    close(AUTHORS_INDEX);
}

=head2 _makeGenreIndexes

TODO

=cut

sub _makeGenreIndexes {
    # get total titles in library
    my $select = "SELECT COUNT(*) 
    FROM titles 
    WHERE published = 'yes'";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my ($total_titles) = $sth->fetchrow_array();
    # establish the genres and the ways to sort them
    my @genres = (
        'fiction',
        'nonfiction',
        'poetry',
        'plays',
        'erotic_fiction',
    );
    my @index_types = (
        'by length',
        'by title',
        'by author',
        'by year',
    );
    foreach my $genre (@genres) {
        # get total titles for this genre
        my $select = "SELECT COUNT(*) 
        FROM titles 
        WHERE genre = '$genre'
        AND published  = 'yes'";
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute || die "execute: $select: $DBI::errstr";
        my ($genre_total) = $sth->fetchrow_array();
        my $genre_printable = ucfirst($genre);
        if ( $genre_printable eq 'erotic_fiction' ) {
            $genre_printable =~ s/_/ /;
        }
        # get title list
        foreach my $type ( @index_types ) {
            my $genre_index_template = HTML::Template->new(filename => "templates/library/genre_index.tmpl");
            my $order_by;
            my $index_type_filename;
            if ( $type eq 'by length' ) {
                $order_by = "LENGTH(body) DESC, pagetitle";
                $index_type_filename = "by_length";
                # call with a true value (1) to include the conditional content
                $genre_index_template->param(BY_FILELENGTH => 1);
            }
            elsif ( $type eq 'by title' ) {
                $order_by = "pagetitle";
                $index_type_filename = "index";
                $genre_index_template->param(BY_PAGETITLE => 1);
            }
            elsif ( $type eq 'by year' ) {
                $order_by = "year DESC, pagetitle";
                $index_type_filename = "by_year";
                # call with a true value (1) to include the conditional content
                $genre_index_template->param(BY_YEAR => 1);
            }
            elsif ( $type eq 'by author' ) {
                $order_by = "last_name, first_name, pagetitle";
                $index_type_filename = "by_author";
                # call with a true value (1) to include the conditional content
                $genre_index_template->param(BY_AUTHOR => 1);
            }
            else {$order_by = ""; $index_type_filename = "";}
            my $title_list;
            my $select = "SELECT t.pagetitle, t.filename, t.description, 
            length(t.body), t.year, a.first_name, a.last_name 
            FROM titles AS t
            LEFT JOIN authors AS a
            ON t.author_id = a.id
            WHERE genre = '$genre' 
            AND t.published = 'yes'
            ORDER BY $order_by";
            my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
            $sth->execute || die "execute: $select: $DBI::errstr";
            my @titles_loop;
            while (my ($pagetitle, $filename, $description, $length, $year, $first_name, $last_name) = $sth->fetchrow_array()) {
                my %title;
                $title{PAGETITLE} = $pagetitle;
                $title{FILENAME} = $filename;
                $title{DESCRIPTION} = $description;
                my $length_in_kilobytes = sprintf("%.0f", ($length / 1000));
                $title{LENGTH} = $length_in_kilobytes;
                $title{YEAR} = $year;
                $title{FIRST_NAME} = $first_name;
                $title{LAST_NAME} = $last_name;
                my $author_file = "${first_name}_${last_name}.html";
                $author_file =~ s/ /_/g;
                $title{AUTHOR_FILENAME} = $author_file;
                push(@titles_loop, \%title);
            }
            # replace loops
            $genre_index_template->param(TITLES => \@titles_loop);
            # replace single vars
            my $title = "$genre index $type on mindmined.com";
            my $description = qq |Original $genre_printable on mindmined.com sorted $type|;
            $genre_index_template->param(GENRE_TOTAL => $genre_total);
            $genre_index_template->param(GENRE => $genre);
            $genre_index_template->param(GENRE_PRINTABLE => $genre_printable);
            #$genre_index_template->param(TITLE => $title);
            $genre_index_template->param(DESCRIPTION => $description);
            $genre_index_template->param(TOTAL => $total_titles);
            $genre_index_template->param(PAGETITLE => "$genre on mindmined.com");
            $genre_index_template->param(DESCRIPTION => "Full text $genre on mindmined.com.");
            $genre_index_template->param(KEYWORDS => "$genre,public library,full text,");
            $genre_index_template->param(WINDOW_STATUS => "$genre on mindmined.com");
            my $output = $genre_index_template->output;
            open(GENRE_INDEX, "> $ENV{DOCUMENT_ROOT}/public_library/$genre/${index_type_filename}.html") or die("Trouble writing file: $!");
            print GENRE_INDEX "$output";
            close(GENRE_INDEX);
        }
    }
}


=head2 _processTemplate

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

=head2 _saveAuthor

TODO

=cut

sub saveAuthor {   # grab the values submitted
    my $email=$cgiobject->param('email'); 
    my $alt_emails=$cgiobject->param('alt_emails'); 
    my $email_display=$cgiobject->param('email_display'); 
    my $homesite=$cgiobject->param('homesite'); 
    my $bio=$cgiobject->param('bio'); 
    my $first_name=$cgiobject->param('first_name'); 
    my $last_name=$cgiobject->param('last_name'); 
    my $published=$cgiobject->param('published'); 
    my $id=$cgiobject->param('id'); 
    $published = $published ? 1 : 0;
    if ( $id ) {   # update existing author
        $bio =~ s/\n/<br>/g;
        # when editing or viewing, query the database about the product
        my $update="UPDATE authors 
        SET email = ?, alt_emails = ?, email_display = ?, homesite = ?, bio = ?, first_name = ?, last_name = ?, published = ?
        WHERE id = ?";
        my $sth = $dbh->prepare($update);
        $sth->execute($email, $alt_emails, $email_display, $homesite, $bio, $first_name, $last_name, $published, $id) || die "sth->execute($update): $DBI::errstr\n";
        my $message = qq {$first_name $last_name has been updated.};
        mainInterface($message);
    }
    else {  # add new author
        my $insert="INSERT INTO authors (email, alt_emails, email_display, homesite, bio, first_name, last_name, published) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($email, $alt_emails, $email_display, $homesite, $bio, $first_name, $last_name, $published) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        $id = $sth->{mysql_insertid} || $sth->{insertid}; 
        my $message = qq {$first_name $last_name has been added.};
        mainInterface($message);
    }
    batchLibrary();
}


=head2 saveBody

TODO

=cut

sub saveBody {
    my $body=$cgiobject->param('body'); 
    my $id=$cgiobject->param('id');
    my $select="SELECT pagetitle 
    FROM titles 
    WHERE id = '$id'";
    my $sth = $dbh->prepare($select);
    $sth->execute() || die "sth->execute($select): $DBI::errstr\n";
    my ($pagetitle) = $sth->fetchrow_array();
    ##
    my $update="UPDATE titles SET body = ? WHERE id = '$id'";
    $sth = $dbh->prepare($update);
    $sth->execute($body) || die "sth->execute($update): $DBI::errstr\n";
    my $message = qq {$pagetitle has been updated.};
}

=head2 saveTitle

TODO

=cut

sub saveTitle {
    # grab the values submitted
    my $published=$cgiobject->param('published'); 
    my $pagetitle=$cgiobject->param('pagetitle'); 
    my $genre=$cgiobject->param('genre'); 
    my $image_URL=$cgiobject->param('image_URL'); 
    my $description=$cgiobject->param('description'); 
    my $filename=$cgiobject->param('filename'); 
    my $year=$cgiobject->param('year'); 
    my $author_id=$cgiobject->param('author_id'); 
    my $image_alt_text=$cgiobject->param('image_alt_text'); 
    my $keywords=$cgiobject->param('keywords'); 
    my $body=$cgiobject->param('body'); 
    my $id=$cgiobject->param('id');
    if ( ! $genre ) {
        my $message = qq |Please select a genre.|;
        titleInterface($message);
        exit;
    }
    if ( ! $author_id ) {
        my $message = qq |Please select an author.|;
        titleInterface($message);
        exit;
    }
    if ( $published =~ m/^on$/i ) {
        $published = 'yes';
    }
    else {
        $published = 'no';
    }
    my $message;
    if ( $id ) {  # update existing title
        my $update="UPDATE titles 
        SET published = ?, pagetitle = ?, genre = ?, image_URL = ?, description = ?, filename = ?, year = ?, author_id = ?, image_alt_text = ?, keywords = ? 
        WHERE id = ?";
        my $sth = $dbh->prepare($update);
        $sth->execute($published, $pagetitle, $genre, $image_URL, $description, $filename, $year, $author_id, $image_alt_text, $keywords, $id) || die "sth->execute($update): $DBI::errstr\n";
        $message = qq {$pagetitle has been updated.};
    }
    else {  # add new title
        my $content_body;
        $body =~ m/^.*(\\|\/)(.*)/; # strip the remote path and keep the filename
        while(<$body>) {
           $content_body .= $_;
        }
        my $insert="INSERT INTO titles (pagetitle, genre, image_URL, description, filename, year, author_id, image_alt_text, keywords, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        my $sth = $dbh->prepare($insert) || die "prepare: $insert: $DBI::errstr";
        $sth->execute($pagetitle, $genre, $image_URL, $description, $filename, $year, $author_id, $image_alt_text, $keywords, $content_body) || die "execute: $insert: $DBI::errstr";
        # grab the automatically incremented id that was generated
        $id = $sth->{mysql_insertid} || $sth->{insertid}; 
        $message = qq {$pagetitle has been added.};
    }
    batchLibrary($id);
    mainInterface($message);
}


=head2 titleInterface

TODO

=cut

sub titleInterface {
    my $id=$cgiobject->param('id'); 
    my $template = HTML::Template->new(filename => "templates/mmpub/library/titleInterface.tmpl");
    my $file_upload;
    my $file_upload_form;
    my $add_or_update;
    my $published; my $pagetitle; my $this_genre; my $image_URL; my $description;
    my $filename; my $year; my $this_author_id; my $image_alt_text; my $keywords;
    if ($id) {
        $add_or_update = qq {Update};
        my $select="SELECT published, pagetitle, genre, image_URL, description, filename, year, author_id, image_alt_text, keywords 
        FROM titles 
        WHERE id = ?";
        my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
        $sth->execute($id) || die "execute: $select: $DBI::errstr";
        ($published, $pagetitle, $this_genre, $image_URL, $description, $filename, $year, $this_author_id, $image_alt_text, $keywords) = $sth->fetchrow_array();
    }
    else {
        $add_or_update = 'Add';
    }
    my @genres = ('erotic_fiction','fiction','nonfiction','plays','poetry');
    my @genre_options;
    foreach my $genre (@genres) {
        my %row;
        if ($this_genre eq $genre) {$row{SELECTED} = 'SELECTED';}
        $row{GENRE} = $genre;
        push(@genre_options, \%row);
    }
    # get list of authors
    my $select="SELECT first_name, last_name, id 
    FROM authors 
    ORDER BY last_name, first_name";
    my $sth = $dbh->prepare($select) || die "prepare: $select: $DBI::errstr";
    $sth->execute || die "execute: $select: $DBI::errstr";
    my @author_options;
    while (my ($first_name, $last_name, $author_id) = $sth->fetchrow_array()) {
        my %row;
        if ($this_author_id eq $author_id) {$row{SELECTED} = 'SELECTED';} 
        $row{AUTHOR_ID} = $author_id;
        $row{FIRST_NAME} = $first_name;
        $row{LAST_NAME} = $last_name;
        push(@author_options, \%row);
    }
    if (! $image_alt_text) {
        $image_alt_text = qq |image for $pagetitle|;
    }
    if ($published eq 'yes') {
        $template->param(PUBLISHED => 1);
    }
    $template->param(ADD_OR_UPDATE => $add_or_update);
    $template->param(AUTHOR_OPTIONS => \@author_options);
    $template->param(GENRE_OPTIONS => \@genre_options);
    $template->param(PAGETITLE => $pagetitle);
    #$template->param(GENRE => $this_genre);
    $template->param(IMAGE_URL => $image_URL);
    $template->param(DESCRIPTION => $description);
    $template->param(FILENAME => $filename);
    $template->param(YEAR => $year);
    $template->param(IMAGE_ALT_TEXT => $image_alt_text);
    $template->param(KEYWORDS => $keywords);
    $template->param(ID => $id);
    return ($template, $message);
}

=head2 updateBody

TODO

=cut

sub updateBody {
    my $body=$cgiobject->param('body'); 
    my $id=$cgiobject->param('id');
    my $content_body;
    die("You must choose a local file to upload...") if ! $body;
    $body =~ m/^.*(\\|\/)(.*)/; # strip the remote path and keep the filename
    while(<$body>) {
       $content_body .= $_;
    }
    # prevents a crash
    utf8::upgrade($content_body);
    my $update="UPDATE titles 
    SET body = ?, body2 = ? 
    WHERE id = ?";
    my $sth = $dbh->prepare($update);
    $sth->execute($content_body, $content_body, $id) || die "sth->execute($update): $DBI::errstr\n";
    my $message = qq |Body of piece has been updated.|;
    batchLibrary($id);
    mainInterface($message);
}

=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


