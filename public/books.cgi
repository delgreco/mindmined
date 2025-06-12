#!/usr/bin/perl

# use strict, warnings and modern features
use 5.030;

use lib qw(
    local/lib/perl5
    local/lib/perl5/x86_64-linux-thread-multi
    ../lib
    ../private
);

use CGI;
use CGI::Carp('fatalsToBrowser');
use DBI; 
use HTML::Template;
use Dotenv -load;

use FatalsToEmail   # only use this when called from the web
  qw(
	  Mailhost localhost
	  Address marcus@mindmined.com
	  Error_cache /tmp/books.tmp
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

mainInterface();
exit;

sub mainInterface {
	my $t = HTML::Template->new(filename => 'templates/books/mainInterface.tmpl');
	my $select = <<~"SQL";
    SELECT author, title, year, notes, genre, id FROM books ORDER BY author, year
    SQL
	my $sth = $dbh->prepare($select);
	$sth->execute;
	my $count = 0;
	my @books;
	while (my ($author, $title, $year, $notes, $genre, $id) = $sth->fetchrow_array()) {
		my %row;
		$count++;
		if ($count % 2 == 0) {
			$row{BGCOLOR} = '#DDDDDD';
		}
		else { 
			$row{BGCOLOR} = '';
		}
		$row{AUTHOR} = $author;
		$row{TITLE} = $title;
		$row{YEAR} = $year;
		$row{NOTES} = $notes;
		$row{GENRE} = $genre;
		$row{ID} = $id;
		push(@books, \%row);
	}
	$t->param(BOOKS => \@books);
	my $output = $t->output;
	print "Content-type: text/html\n\n";
	print $output;
}

=head1 AUTHORS

Written by Marcus Del Greco (marcus@mindmined.com).  L<Marcus Del Greco|https://mindmined.com/marcus>.

=cut


