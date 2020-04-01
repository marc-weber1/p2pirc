#!/usr/bin/perl
#
# Copyright (c) 2004 Samy Kamkar
#
# chownat, pronounced "chone nat", v0.07-beta
# developed 08/16/04
#
# chownat allows two peers behind two seperate NATs
# with NO port forwarding and NO DMZ to communicate
# with each other. more importantly, it opens up a
# tunnel between the two machines so one peer can
# access a service, such as a web server, on the other
# machine which is also behind a NAT. there is NO
# middle man, NO proxy, NO 3rd party, and the
# application runs as an unprivileged user on both
# ends.
#
# example usage:
# nat1 w/ssh server$	./chownat.pl -d -s 22 nat2.com
# nat2$			./chownat.pl -d -c 1234 nat1.com
#
# nat2 runs `ssh -p 1234 username@localhost` to ssh as 'username' to
# machine nat1 and gets right through any NATs on either or both sides
#
# 
#######################################################################

# check for correct usage
my ($DEBUG, $mode, $localport, $remoteaddr, $remoteport) = &usage();

my $localhost = "localhost";
my $size = 4096;

use strict;
use Socket;
use IO::Select;

&debug("Opening socket on port $remoteport");
socket(CHOWNAT, PF_INET, SOCK_DGRAM, getprotobyname("udp")) or die "socket: $!";
bind(CHOWNAT, sockaddr_in($remoteport, INADDR_ANY)) || die "bind: $!";

$remoteaddr = inet_aton($remoteaddr);
$remoteport = sockaddr_in($remoteport, $remoteaddr);


# client mode
if ($mode eq "-c")
{
	# open a port on the machine to allow connections
	&client_bind($localport);

	# we received a connection to the local port
	while (my $ipaddr = accept(SOCK, WAITCLI))
	{
		&debug("Received a connection to the local port");

		# establish a "connection" with the remote chownat

		&client_chownat_connect();

		my %connections;
		my $id = 0;
		my $expected = 0;
		my $select = IO::Select->new(\*SOCK, \*CHOWNAT);
		my $command;
		my $inputlen;
		my @ready;
		my $closed = 0;
		my @buffer;

		while (!$closed)
		{
				while (@ready = $select->can_read(5))
				{
					foreach my $fh (@ready) 
					{
						if (fileno($fh) == fileno(SOCK))
						{
							# Read a buffer full of data
							unless (sysread($fh, $_, $size))
							{
								$id = 0;
								$expected = 0;
								@buffer = ();

								&debug("REMOTE: 1Attempting to disconnect");
								&chownat_disconnect($remoteport);
 
								$select->remove(\*SOCK);
								close SOCK;

								$closed = 1;
							}

							else
							{
								$buffer[$id] = $_;
								send(CHOWNAT, "09" . chr($id++) . $_, 0, $remoteport);
							}
						}
						else
						{
							# We got a packet from the remote CHOWNAT
							unless (recv($fh, $command, $size, 0))
							{
								$id = 0;
								$expected = 0;
								@buffer = ();

								&debug("REMOTE: 2Attempting to disconnect");
								&chownat_disconnect($remoteport);
			
								$select->remove(\*SOCK);
								close SOCK;

								$closed = 1;
							}

							next unless length($command)>=3; # ignore keep-alives
							my $data = substr($command, 3, length($command)-3, "");

							# remote NAT wants to close the connection
							if ($command eq "02\n")
							{
								$id = 0;
								$expected = 0;
								@buffer = ();

								&debug("REMOTE: 3Attempting to disconnect");
								&chownat_disconnect($remoteport);

								$select->remove(\*SOCK);
								close SOCK;

								$closed = 1;
							}

							# connection opened
							elsif ($command eq "03\n")
							{
								next;
							}

							# remote chownat is missing some packets
							elsif ($command =~ /^08(.)/s)
							{
								my $got = ord($1);

								&debug("Remote host needs packet $got, we're on $id");

								foreach ($got .. $id - 1)
								{
									send(CHOWNAT, "09" . chr($_) . $buffer[$_], 0, $remoteport);
								}
							}

							# Got data from remote CHOWNAT for our local socket
							elsif ($command =~ /^09(.)/s)
							{
								my $got = ord($1);

								&debug("Got packet $got, expected packet $expected", ($got == $expected ? 4 : 1));

								# make sure this is the expected packet
								if ($got != $expected)
								{
									&debug("Asking for packet $expected");

									# we got the wrong packet, ask for the right one
									send(CHOWNAT, "08" . chr($expected), 0, $remoteport);
								}

								else
								{
									# send data from remote chownat to our client
									send(SOCK, $data, 0);
									$expected = 0 if $expected++ == 255;
								}
							}

						} # else
					} # foreach fh
				} # while select

			# Send keep-alive
			send(CHOWNAT, "", 0, $remoteport);

		} # while not closed

	} # while accept
	exit;
}


# server mode
elsif ($mode eq "-s")
{
		my $select = IO::Select->new(\*CHOWNAT);
		my $command;
		my @ready;
		my @buffer;
		my $id = 0;
		my $expected = 0;

		while (1)
		{
			while(@ready = $select->can_read(5))
			{
				foreach my $fh (@ready)
				{
					if (fileno(SOCK) && fileno $fh == fileno SOCK)
					{
						# send to chownat
						unless (sysread($fh, $_, $size))
						{
							$id = 0;
							$expected = 0;
							@buffer = ();

							&debug("REMOTE: 4Attempting to disconnect");
							&chownat_disconnect($remoteport);

							$select->remove(\*SOCK);
							close SOCK;
						}

						else
						{
							$buffer[$id] = $_;
							send(CHOWNAT, "09". chr($id++) . $_, 0, $remoteport);
						}
				   }

				   # send to client
				   else
				   {
						unless (recv($fh, $command, $size, 0))
						{
							$id = 0;
							$expected = 0;
							@buffer = ();

							&debug("REMOTE: 5Attempting to disconnect");
							&chownat_disconnect($remoteport);
											
							$select->remove(\*SOCK);
							close SOCK;
						}

						next unless length($command)>=3; # ignore keep-alives
						my $data = substr($command, 3, length($command)-3, "");

						# user is trying to connect to me -- new connection
						if ($command eq "01\n")
						{
							# send back "you're connected!"
							&debug("REMOTE: 6Attempted to connect to us, initializing connection");
							&server_chownat_connect($remoteport);

							# open a real connection to the local port we are tunneling
							my $paddr = sockaddr_in($localport, inet_aton($localhost));

							# close any SOCK that might already be open
							close(SOCK);
							socket(SOCK, PF_INET, SOCK_STREAM, getprotobyname('tcp')) || die "socket: $!";

							connect(SOCK, $paddr) || die "Can't open socket to $localhost:$localport: $!";

							&debug("Connection to local daemon (port $localport) opened");

							$select->add(\*SOCK);

						}

						# user is disconnecting
						elsif ($command eq "02\n")
						{
							$id = 0;
							$expected = 0;
							@buffer = ();

							&debug("REMOTE: 7Attempting to disconnect");
#							&chownat_disconnect($remoteport);
#							send(CHOWNAT,"02\n",0,$remoteport);
							
							$select->remove(\*SOCK);
							close SOCK;
						}
						
						# user is handshaking
						elsif ($command eq "03\n")
						{
							&debug("REMOTE: handshake", 5);
							
							send(CHOWNAT, "03\n", 0, $remoteport);
							next;
						}

						# remote chownat is missing some packets
						elsif ($command =~ /^08(.)/s)
						{
							my $got = ord($1);
							&debug("Remote host needs packet $got, we're on $id");

							foreach ($got .. $id - 1)
							{
								send(CHOWNAT, "09" . chr($_) . $buffer[$_], 0, $remoteport);
							}
						}
						

						# Got data from remote CHOWNAT for our local socket
						elsif ($command =~ /^09(.)/s)
						{
							my $got = ord($1);

							&debug("Got packet $got, expected packet $expected", ($got == $expected ? 4 : 1));

							# make sure this is the expected packet
							if ($got != $expected)
							{
								# we got the wrong packet, ask for the right one
								send(CHOWNAT, "08" . chr($expected), 0, $remoteport);
							}

							else
							{
								# send data from remote chownat to our client
								send(SOCK, $data, 0);
								$expected = 0 if $expected++ == 255;
							}
						}

					} #else
					
				} #foreach fh
				
			} #while select
			
			#Send keep-alive
			send(CHOWNAT, "", 0, $remoteport);
			
		} #while not closed
}


else
{
		die "Invalid mode.\n";
}



sub usage
{
		my $debug = 0;
		if ($ARGV[0] eq "-d")
		{
				$debug++;
				shift(@ARGV);
		}

		if ($ARGV[0] eq "-d")
		{
				$debug++;
				shift(@ARGV);
		}

		if ($ARGV[0] eq "-dd")
		{
				$debug = 2;
				shift(@ARGV);
		}

		$ARGV[3] ||= 2222;

		die << "EOF"
chownat 0.07-beta
usage: $0 [-d] <-c|-s> <local port> <dest host> [communication port]

		-d debug mode, two -d's for verbose debug mode
		-c client mode, you connect other applications to
		   localhost:local_port and it tunnels to the dest host
		-s server mode, anyone who connects to you gets tunneled
		   to whatever is already running on localhost:local_port

		<local port>	local port to listen on or connect to
						depending on if -c or -s is used
		<dest host>	 destination host to connect to or
						allow connections from
		[comm port]	 port to communicate on, default of 2222


example:
  on machine \"nat1\" running an ssh server behind a nat:
		nat1\$ ./chownat.pl -d -s 22 nat2.com

  on machine \"nat2\" behind another nat:
		nat2\$ ./chownat.pl -d -c 1234 nat1.com

  nat2 can now run `ssh -p 1234 username\@localhost` to ssh as 'username'
  to nat1 and break straight through both NATs / firewalls

EOF
		if	  @ARGV != 4 ||
				$ARGV[0] !~ /^-[cs]$/ ||
				$ARGV[1] !~ /^\d+$/ ||
				$ARGV[2] =~ /[^a-zA-Z\d.-]/ ||
				$ARGV[3] !~ /^\d+$/;

		return ($debug, @ARGV);
}


sub debug
{
		my $msg = shift;
		$msg =~ s/\r?\n//g;

		print "DEBUG: $msg\n" if (shift > 1 ? $DEBUG > 1 : $DEBUG >= 1);
}


# server side -- accepts and establishes a connection with the remote chownat
sub server_chownat_connect
{
		my $data;

		while (1)
		{
				&debug("Connecting..");
				send(CHOWNAT, "03\n", 0, $_[0]);
				eval
				{
					$SIG{ALRM}=sub{die};
					alarm(1);
					recv(CHOWNAT,$data,3,0);
					alarm(0);
				};

				# we're connected
				if ($data eq "03\n")
				{
						&debug("REMOTE: Connection opened to remote end");
						last;
				}
		}

		return 1;
}

# client side -- establishes a connection with the remote chownat
sub client_chownat_connect
{
		my $data;

		# open up a connection to the remote side
		&debug("Opening a connection to the remote end");
		while (1)
		{
				&debug("8Attempting to connect..");


				# open the connection
				send(CHOWNAT, "01\n", 0, $remoteport);
				eval
				{
					$SIG{ALRM}=sub{die};
					alarm(1);
					recv(CHOWNAT,$data,$size,0);
					alarm(0);
				};

				# we're connected
				if ($data eq "03\n")
				{
						send(CHOWNAT, "03\n", 0, $remoteport);
						&debug("REMOTE: Connection opened to remote end");
						last;
				}

				select(undef, undef, undef, 0.25);
		}

		return 1;
}

# client side -- binds a socket to allow local connections
sub client_bind
{
		my $localport = shift;

		&debug("Binding a new socket to $localport");

		socket(WAITCLI, PF_INET, SOCK_STREAM, getprotobyname('tcp'));
		setsockopt(WAITCLI, SOL_SOCKET, SO_REUSEADDR, pack("l", 1));

		bind(WAITCLI, sockaddr_in($localport, INADDR_ANY)) || die "Cannot bind to $localport: $!\n"; 
		listen(WAITCLI, 1);
}


# disconnect from remote chownat
sub chownat_disconnect
{
		my $data;

		&debug("9Attempting to disconnect");

		# let the remote NAT know we're disconnecting
		&debug("Trying to disconnect..");
		send(CHOWNAT, "02\n", 0, $_[0]);
		eval
		{
				$SIG{ALRM} = sub { die };
				alarm(1);
				recv(CHOWNAT,$data,3,0);
				alarm(0);
		};
		if ($data eq "02\n")
		{
				send(CHOWNAT, "02\n", 0, $_[0]);
		}

		&debug("REMOTE: Disconnected");
}
