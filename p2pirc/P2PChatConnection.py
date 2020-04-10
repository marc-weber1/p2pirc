import socket, json
from noise.connection import NoiseConnection, Keypair

from cryptography.hazmat.primitives.serialization import PublicFormat
from cryptography.hazmat.primitives.serialization import Encoding

from .P2PChatSignals import *


# These are plaintext send/receive functions. If you want encrypted versions,
# use P2PChatConnection.send() or .receive().
def sendPT(sock, string):
    data = string.encode('utf-8')
    lendata = len(data).to_bytes(4, 'big')
    sock.sendall(lendata + data)

def receivePT(sock):
    length = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(length).decode('utf-8')


class P2PChatConnection:
    '''
    P2PChatConnection represents a single connection between you and another
    person in the group chat, abstracting for who is the "server" and who is
    the "client"
    '''
    private_key_file = ""

    #addr is an [IP,port], Listener is a listener socket, connection is a P2PChatConnection
    #After this, self.sock, self.addr are guaranteed to exist
    def __init__(self,role="JOINCHAT",addr=None,listener=None,connection=None):
        
        if role == "JOINDIRECT": #pwnat or open port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(tuple(addr))
                print('Connected')

                # 'addr' is the ip/port of the socket we need to connect to
                self.addr = json.loads(receivePT(s))

                # 'firstsock' will be the first element of self.connList.
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(tuple(self.addr))
        elif role == "JOININDIRECT": #chownat
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(tuple(addr))
            self.addr = addr
        elif role == "NEWINDIRECTCLIENT": #chownat
            target_addr = json.loads(connection.receive())
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0))
                tmpsock.listen()

                # Send C the address of the new socket we created.
                # C will then send this to the new client, who will connect
                # to our socket.
                connection.send(json.dumps(tmpsock.getsockname()))
                self.sock, self.addr = tmpsock.accept()
        elif role == "NEWDIRECTCLIENT": #pwnat or open port; don't need their IP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0))
                tmpsock.listen()
                sendPT(listener, json.dumps(tmpsock.getsockname()))
                self.sock, self.addr = tmpsock.accept()
        
        
        # Handshake now that the socket is open
        # XX: server - confidentially receive their static pubkey, verify it, then send your static back
        self.noise = NoiseConnection.from_name(b'Noise_XX_25519_AESGCM_SHA256')
        self.noise.set_keypair_from_private_path(Keypair.STATIC, P2PChatConnection.private_key_file)
        
        if role == "NEWDIRECTCLIENT" or role == "NEWINDIRECTCLIENT": #"server"
            self.noise.set_as_initiator()
            self.noise.start_handshake()
            eph_loc_pubkey = self.noise.write_message() #any payload?? like random numbers
            self.sock.sendall(eph_loc_pubkey)
            stat_rem_pubkey = self.sock.recv(96)
            payload = self.noise.read_message(stat_rem_pubkey)
            self.handshake_role = "server"
            #self.pubkey() is now guaranteed to exist
                
        elif role == "JOINDIRECT" or role == "JOININDIRECT": #"client"
            self.noise.set_as_responder()
            self.noise.start_handshake()
            data = self.sock.recv(32)
            eph_rem_pubkey = self.noise.read_message(data)
            cipher_stat_loc_pubkey = self.noise.write_message() #timestamp would be cool here? or random numbers
            print("Our pubkey: " + str(self.noise.noise_protocol.keypairs['s'].public.public_bytes(Encoding.Raw,PublicFormat.Raw)))
            self.sock.sendall(cipher_stat_loc_pubkey)
            self.handshake_role = "client"
        
        #THE HANDSHAKE IS NOT DONE AT THIS POINT; it will be done upon the server accepting, and then the client accepting; sending messages before then will result in an error
    
    
    def acceptConnection(self):
        if self.handshake_role == "server":
            cipher_stat_loc_pubkey = self.noise.write_message()
            print("Our pubkey: " + str(self.noise.noise_protocol.keypairs['s'].public.public_bytes(Encoding.Raw,PublicFormat.Raw)))
            self.sock.sendall(cipher_stat_loc_pubkey)
        elif self.handshake_role == "client":
            self.handshake_role = "finished" #handshake complete
            assert self.noise.handshake_finished
            # Send confirmation packet
    
    def rejectConnection(self):
        pass #implementing soon
    
    def waitForAccept(self):
        if self.handshake_role == "server":
            self.handshake_role = "finished"
            assert self.noise.handshake_finished
            # Receive confirmation packet
        elif self.handshake_role == "client":
            data = self.sock.recv(64)
            stat_rem_pubkey = self.noise.read_message(data)
            self.handshake_role = "finished"
            assert self.noise.handshake_finished
            
        return True #Will sometimes not return true in the future
    
    def pubkey(self): #returns a x25519PublicKey object
        print(vars(self.noise.noise_protocol))
        return self.noise.noise_protocol.keypairs['rs']
    
    
    def send(self,string):
        encrypted_data = self.noise.encrypt(string.encode('utf-8'))
        lendata = len(encrypted_data).to_bytes(4, 'big')
        self.sock.sendall(lendata + encrypted_data)

    def receive(self):
        len_data = self.sock.recv(4)
        if not len_data:
            return ''
        length = int.from_bytes(len_data, 'big')
        plaintext_message = self.noise.decrypt(self.sock.recv(length))
        return plaintext_message.decode('utf-8')
    
    
    
    def close(self):
        self.sock.close()
    
    def sendAddressList(self,addrs):
        self.send(json.dumps(addrs))
    
    def sendNewConnection(self,addr):
        self.send(P2P_CHAT_NEWCONNECTION)
        self.send(json.dumps(addr))
    
    def sendMessage(self,m):
        self.send(P2P_CHAT_NEWMESSAGE)
        self.send(m)
    
    def receiveAddressList(self):
        return json.loads(self.receive())
        
    def receiveOpenAddress(self):
        return json.loads(self.receive())
        
    def receiveMessage(self): #THIS NEEDS ENCODING
        return self.receive()
        
    def receiveSignal(self):
        return self.receive()
        
    def getsockname(self): #So you can get the address in a roundabout way
        return self.sock.getsockname()
    
    def fileno(self): #So you can call select() on a list of P2PChatConnections
        return self.sock.fileno()
