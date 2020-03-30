from argparse import ArgumentParser
import socket

from .P2PChatConnection import P2PChatConnection

DEFAULT_PORT_MIN = 38500 #Needs this port for the server, and one more port for each person in the chat


def main():
	print("Parsing arguments...")
	parser = ArgumentParser(description="A peer-to-peer group chat proof of concept.")
	
	parser.add_argument('--ip',metavar='X.X.X.X',default='127.0.0.1',
						help="The IP of one of the people currently in the group chat")
	parser.add_argument('--port',type=int,metavar='N',default=DEFAULT_PORT_MIN,
						help="The port of that person's server you want to connect to")
	parser.add_argument('--local-port',type=int,metavar='N',default=DEFAULT_PORT_MIN,
						help="The port to host your connection server on")
	parser.add_argument('--key-file',metavar='*.json',default='id-rsa.json',
						help="The file containing the key database")
	
	args = parser.parse_args()
	
	
	#VALIDATION - maybe also check if the ports are available?
	
	try:
		socket.inet_aton(args.ip) #Only support ipv4 for now
	except socket.error:
		print("Invalid IP %s." %args.ip)
	
	if args.port<1 or args.port>65535:
		print("Invalid port %d." %args.port)
		return
		
	if args.local_port<1 or args.local_port>65535:
		print("Invalid local port %d." %args.local_port)
		return
		
	try:
		fp = open(args.key_file, "a+")  #Creates file if it doesn't exist
		fp.close()
	except IOError:
		print("Invalid key file %s." %args.key_file)
		return
		
	
	#Everything is good at this point, start the class
	
	con = P2PChatConnection(args.local_port,args.key_file)
	con.connect(args.ip,args.port)