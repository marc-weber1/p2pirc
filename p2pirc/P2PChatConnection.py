import socket, json
from noise.connection import NoiseConnection

from .P2PChatSignals import *

def send(sock, string):
    data = string.encode('utf-8')
    lendata = len(data).to_bytes(4, 'big')
    sock.sendall(lendata + data)

def receive(sock):
    length = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(length).decode('utf-8')


#P2PChatConnection represents a single connection between you and another person in the group chat, abstracting for who is the "server" and who is the "client"

class P2PChatConnection:
    #addr is an [IP,port], Listener is a listener socket, connection is a P2PChatConnection
    def __init__(self,role="JOINCHAT",addr=None,listener=None,connection=None):
        if role == "JOINDIRECT": #pwnat or open port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(tuple(addr))
                print('Connected')

                # 'addr' is the ip/port of the socket we need to connect to
                self.addr = json.loads(receive(s))

                # 'firstsock' will be the first element of self.connList.
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(tuple(self.addr))
        elif role == "JOININDIRECT": #chownat
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect(tuple(addr))
                self.addr = addr
        elif role == "NEWINDIRECTCLIENT": #chownat
            target_addr = json.loads(receive(connection.sock))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0))
                tmpsock.listen()

                # Send C the address of the new socket we created.
                # C will then send this to the new client, who will connect
                # to our socket.
                send(connection.sock, json.dumps(tmpsock.getsockname()))
                self.sock, self.addr = tmpsock.accept()
        elif role == "NEWDIRECTCLIENT": #pwnat or open port; don't need their IP
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                tmpsock.bind(('127.0.0.1', 0))
                tmpsock.listen()
                send(listener, json.dumps(tmpsock.getsockname()))
                self.sock, self.addr = tmpsock.accept()
    
    def close(self):
        self.sock.close()
    
    def sendAddressList(self,addrs):
        send(self.sock, json.dumps(addrs))
    
    def sendNewConnection(self,addr):
        send(self.sock, P2P_CHAT_NEWCONNECTION)
        send(self.sock, json.dumps(addr))
    
    def sendMessage(self,m):
        send(self.sock, P2P_CHAT_NEWMESSAGE)
        send(self.sock,m)
    
    def receiveAddressList(self):
        return json.loads(receive(self.sock))
        
    def receiveOpenAddress(self):
        return json.loads(receive(self.sock))
        
    def receiveMessage(self): #THIS NEEDS ENCODING
        return receive(self.sock)
        
    def receiveSignal(self):
        return receive(self.sock)
        
    def getsockname(self,):
        return self.sock.getsockname()
    
    def fileno(self): #So you can call select() on a list of P2PChatConnections
        return self.sock.fileno()