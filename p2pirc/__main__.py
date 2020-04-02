from argparse import ArgumentParser
import socket, json
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

from .P2PChat import P2PChat
from .P2PChatConnection import P2PChatConnection

DEFAULT_LISTENING_PORT = 38500 #Needs this port for the server, and one more port for each person in the chat, 0 means the OS chooses a free port

def main():
    print("Parsing arguments...")
    parser = ArgumentParser(description="A peer-to-peer group chat proof of concept.")
    
    parser.add_argument('--ip',metavar='X.X.X.X',default='127.0.0.1',
                        help="The IP of one of the people currently in the group chat")
    parser.add_argument('--port',type=int,metavar='N',default=DEFAULT_LISTENING_PORT,
                        help="The port of that person's server you want to connect to")
    parser.add_argument('--local-port',type=int,metavar='N',default=DEFAULT_LISTENING_PORT,
                        help="The port to host your connection server on")
    parser.add_argument('--key-database',metavar='*.json',default='id-25519.json',
                        help="The file containing the key database - if nonexistent, a new one will be made")
    parser.add_argument('--key-file',metavar='*.private_key',default='id-25519.private_key',
                        help="The file containing your private key - if nonexistent, a new one will be made")
    parser.add_argument('--new',action='store_true',
                        help="Creates a new room")
    
    args = parser.parse_args()
    
    
    #VALIDATION - maybe also check if the ports are available?
    
    try:
        socket.inet_aton(args.ip) #Only support ipv4 for now
    except socket.error:
        print("Invalid IP %s." %args.ip)
    
    if args.port<0 or args.port>65535:
        print("Invalid port %d." %args.port)
        return
            
    if args.local_port<0 or args.local_port>65535:
        print("Invalid local port %d." %args.local_port)
        return
            
    try:
        fp = open(args.key_database, "a+")  #Creates file if it doesn't exist
        fp.close()
        P2PChat.key_database_file = args.key_database
    except IOError:
        print("Invalid key database %s." %args.key_database)
        return
                
    try:
        fp = open(args.key_file, "ab+") #Creates file if it doesnt exist
        if(fp.tell() == 0):
            fp.write( X25519PrivateKey.generate().private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()) )
        fp.close()
        P2PChatConnection.private_key_file = args.key_file
    except IOError:
        print("Invalid key file %s." %args.key_file)
        return
    
        
    #Everything is good at this point, start the class
    
    con = P2PChat(args.local_port,args.key_file)
    if args.new:
        con.createNewRoom()
    else:
        con.connect(args.ip,args.port)
