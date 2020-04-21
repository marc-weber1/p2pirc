import asyncio
import socket, json
import string

import aioice
from noise.connection import NoiseConnection, Keypair
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
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

def makeIceConnections(amount, conn, controlling, sendFirst):
    c, d = asyncio.get_event_loop().run_until_complete(_makeIceConnections(amount, conn, controlling, sendFirst))
    return c, d
async def _makeIceConnections(amount, conn, controlling, sendFirst):
    connections = []
    datas_out = []

    for i in range(amount):
        connection = aioice.Connection(ice_controlling=controlling)
        connections.append(connection)
        await connection.gather_candidates()
    
    if not sendFirst:
        datas = json.loads(conn.receive())
        for i in range(amount):
            connections[i].remote_candidates = list(map(lambda x: aioice.Candidate.from_sdp(x), datas[i][0]))
            connections[i].remote_username = datas[i][1]
            connections[i].remote_password = datas[i][2]
    for i in range(amount):
        data_out = [list(map(lambda x: x.to_sdp(),connections[i].local_candidates)),connections[i].local_username,connections[i].local_password]
        datas_out.append(data_out)
    conn.send(json.dumps(datas_out))
    if sendFirst:
        datas = json.loads(conn.receive())
        for i in range(amount):
            connections[i].remote_candidates = list(map(lambda x: aioice.Candidate.from_sdp(x), datas[i][0]))
            connections[i].remote_username = datas[i][1]
            connections[i].remote_password = datas[i][2]
    for c in connections:
        await c.connect()
    return connections, datas

class P2PChatConnection:
    '''
    P2PChatConnection represents a single connection between you and another
    person in the group chat, abstracting for who is the "server" and who is
    the "client"
    '''

    #addr is an [IP,port], Listener is a listener socket, connection is a P2PChatConnection
    #After this, self.sock, self.addr are guaranteed to exist
    #def __init__(self,private_key_file,role="JOINCHAT",addr=None,listener=None,connection=None):
    def __init__(self,role,private_key_file,addr=None,listener=None,connection=None):
        self.private_key_file = private_key_file
        
        if role == "JOINDIRECT": #pwnat or open port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(tuple(addr))

                # 'addr' is the ip/port of the socket we need to connect to
                self.addr = json.loads(receivePT(s)) #ENCRYPT THIS?

                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(tuple(self.addr))
        elif role == "JOININDIRECT": #chownat
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(tuple(addr))
            self.addr = addr
        elif role == "NEWINDIRECTCLIENT": #chownat
            '''target_addr = json.loads(connection.receive())
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0)) #Broken on non-local right now
                tmpsock.listen()

                # Send C the address of the new socket we created.
                # C will then send this to the new client, who will connect
                # to our socket.
                connection.send(json.dumps(tmpsock.getsockname()))
                self.sock, self.addr = tmpsock.accept()'''
            newconn_, data_ = P2PChatConnection.makeIceConnections(1, connection, True, False)
            newconn, data = newconn[0], data[0]
        elif role == "NEWDIRECTCLIENT": #pwnat or open port; don't need their IP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0)) #Broken on non-local right now
                tmpsock.listen()
                sendPT(listener, json.dumps(tmpsock.getsockname())) #ENCRYPT THIS??
                self.sock, self.addr = tmpsock.accept()
        
        # Handshake now that the socket is open
        # XX: server - confidentially receive their static pubkey, verify it, then send your static back
        self.noise = NoiseConnection.from_name(b'Noise_XX_25519_AESGCM_SHA256')
        self.noise.set_keypair_from_private_path(Keypair.STATIC, self.private_key_file)
        
        if role == "NEWDIRECTCLIENT" or role == "NEWINDIRECTCLIENT": #"server"
            self.noise.set_as_initiator()
            self.noise.start_handshake()
            eph_loc_pubkey = self.noise.write_message() #any payload?? like random numbers
            self.sock.sendall(eph_loc_pubkey)
            stat_rem_pubkey = self.sock.recv(128)
            payload = self.noise.read_message(stat_rem_pubkey)
            self.handshake_role = "server"
            self.pubkey = self.noise.noise_protocol.handshake_state.rs.public_bytes
            #self.pubkey() is now guaranteed to exist
                
        elif role == "JOINDIRECT" or role == "JOININDIRECT": #"client"
            self.noise.set_as_responder()
            self.noise.start_handshake()
            data = self.sock.recv(128)
            eph_rem_pubkey = self.noise.read_message(data)
            cipher_stat_loc_pubkey = self.noise.write_message() #timestamp would be cool here? or random numbers
            self.sock.sendall(cipher_stat_loc_pubkey)
            self.handshake_role = "client"
        
        #THE HANDSHAKE IS NOT DONE AT THIS POINT; it will be done upon the server accepting, and then the client accepting; sending messages before then will result in an error
    
    
    def acceptConnection(self):
        if self.handshake_role == "server":
            cipher_stat_loc_pubkey = self.noise.write_message()
            self.sock.sendall(cipher_stat_loc_pubkey)
            assert self.noise.handshake_finished
            # Send pubkey
            encrypted_pubkey = self.noise.encrypt( self.getLocalPubkey() )
            lendata = len(encrypted_pubkey).to_bytes(4, 'big')
            self.sock.sendall( lendata + encrypted_pubkey )
        elif self.handshake_role == "client":
            #agreed_key = self.noise.write_message()
            #self.sock.sendall(agreed_key)
        
            self.handshake_role = "finished" #handshake complete
            assert self.noise.handshake_finished
            self.sock.settimeout(5.0) # REMEMBER TO HANDLE THIS with except socket.timeout, this is so clients can't freeze forever
            # HANDSHAKE COMPLETE
            
    
    def rejectConnection(self):
        pass #implementing soon
    
    def waitForAccept(self):
        if self.handshake_role == "server":
            #agreed_key = self.sock.recv(128)
            #self.noise.read_message(agreed_key)
        
            self.handshake_role = "finished"
            assert self.noise.handshake_finished
            self.sock.settimeout(5.0) # REMEMBER TO HANDLE THIS with except socket.timeout, this is so clients can't freeze forever
            # HANDSHAKE COMPLETE
        elif self.handshake_role == "client":
            data = self.sock.recv(128)
            stat_rem_pubkey = self.noise.read_message(data)
            assert self.noise.handshake_finished
            #Receive pubkey
            lendata = int.from_bytes(self.sock.recv(4),'big')
            self.pubkey = self.noise.decrypt(self.sock.recv(lendata))
            
        return True #Will sometimes not return true in the future
    
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
        
    def receiveMessage(self):
        # Hopefully this is good enough for encoding
        st = self.receive().replace('\n',' ') #Newline filtering, or else someone can fake someone else's message
        return "".join(s for s in st if s in string.printable) #Non-printable filtering, so you can't crash anyone
        
    def receiveSignal(self):
        return self.receive()
        
    def getsockname(self): #So you can get the address in a roundabout way
        return self.sock.getsockname()
    
    def fileno(self): #So you can call select() on a list of P2PChatConnections
        return self.sock.fileno()

    def getLocalPubkey(self):
        with open(self.private_key_file,"rb") as f:
            privkey = X25519PrivateKey.from_private_bytes(f.read())
            return privkey.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)