import asyncio, select, socket, sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from .P2PChatConnection import P2PChatConnection
from .P2PChatSignals import *


class P2PChat:
    key_database = {}
    key_database_file = ""

    def __init__(self, local_port_listener, key_file):
        print("Connection object initialized.")
        ''' self.connList is a list of sockets we use to communicate with other
        people in the chat room '''
        self.listenerIP = '127.0.0.1'
        self.listenerPort = local_port_listener
        self.connList = []
        
        #THEN LOAD THE KEY DATABASE FILE
            
    def connect(self, IP, port):
        '''
        This function should be run to connect to an already existing room.
        It assumes that we are not already connected to a room.
        '''
        
        firstconn = P2PChatConnection("JOINDIRECT",addr=[IP,port])
        firstconn.waitForAccept() # Server accepts first

        #CHECK HERE WITH THE USER IF THE ENDPOINT'S PUBKEY IS OK FIRST, RANDOMART?
        # firstconn.pubkey()
        firstconn.acceptConnection()

        # The person we connect to will now tell everyone else to create
        # a socket for us to use. Then that person will send us the
        # addresses of the sockets they created.
        addrlist = firstconn.receiveAddressList()

        self.connList = [firstconn]
        for addr in addrlist:
            conn = P2PChatConnection("JOININDIRECT",addr=addr)
            conn.waitForAccept() #This blocks, more parallel way?
            conn.acceptConnection()
            self.connList.append(conn)
        
        print("Connection established.")
        try:
            self.createListener()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.mainLoop())
        finally:
            print('Closing our listener')
            self.listener.close()
            print('Closing our connection ports')
            for conn in self.connList:
                conn.close()
            print('Done!')

    def createNewRoom(self):
        self.connList = []

        try:
            self.createListener()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.mainLoop())
        finally:
            print('Closing our listener')
            self.listener.close()
            print('Closing our connection ports')
            for conn in self.connList:
                conn.close()
            print('Done!')

    def createListener(self):
        '''
        Creates a new listener. New clients can connect to this listener to join
        the room that we are currently in.
        '''
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setblocking(0)
        self.listener.bind((self.listenerIP, self.listenerPort))
        self.listener.listen()
        print('Listening on', self.listener.getsockname())

    async def mainLoop(self):
        asyncio.ensure_future(self.listenForMessages())
        asyncio.ensure_future(self.listenForClients())

        session = PromptSession()
        while True:
            with patch_stdout():
                result = await session.prompt_async('>>> ') #Try to un-print the thing typed in after
            if len(result) > 0 and result[0] == '/':
                command = result[1:]
                if command == 'leave':
                    return
                else:
                    print('Unknown command: "%s"' % command)
            print('Me:', result)
            
            # Send the message to everyone else
            for conn in self.connList:
                conn.sendMessage(result)

    async def listenForClients(self):
        while True:
            await asyncio.sleep(0.01)
            # The other two values from this function are writable and errored.
            # We might use the third one in the future to detect if someone has
            # disconnected (which would mean that their connection socket has closed)
            readable,_,_ = select.select([self.listener], [], [], 0)
            #print(readable)

            for sock in readable:
                if sock is self.listener: # should always be True
                    # A new client has tried to connect to our listener
                    s, addr = self.listener.accept()
                    with s:
                        print('Received new client at', addr)
                        # Start listening for new clients right away
                        self.listener.listen()
                        # Create a new socket - this socket will be used for
                        # communication with the new client.
                        
                        newconn = P2PChatConnection("NEWDIRECTCLIENT",listener=s)
                        
                        # CHECK HERE WITH THE USER IF THE CLIENT'S PUBKEY IS OK FIRST !!!
                        # newconn.pubkey()
                        newconn.acceptConnection()
                        
                        newconn.waitForAccept()
                        
                        print('===== %s@%s has joined the chat =====' % newconn.getsockname())

                    # Tell everyone else to make a new socket for their communication
                    # with the new client
                    for conn in self.connList:
                        conn.sendNewConnection(addr)
                    #print('Told everyone to make a new socket for the client')

                    # Everyone else will send a response back containing the address
                    # of the new socket they made
                    newsocks = []
                    for conn in self.connList:
                        newsocks.append(conn.receiveOpenAddress())
                    #print('Received the new socket addresses')

                    self.connList.append(newconn)
                    newconn.sendAddressList(newsocks)
                    #print('Done!')

    async def listenForMessages(self):
        while True:
            await asyncio.sleep(0.01) #Maybe make this not happen if the serverload is high, i.e. if it takes 0.01 seconds to process a request then don't wait
            if not self.connList:
                continue
            readable, _, errored = select.select(self.connList, [], self.connList, 0)
            if errored:
                print('CCC', errored)
            for conn in readable:
                if conn in errored:
                    continue
                data = conn.receiveSignal()
                if not data:
                    # Read zero bytes, that means the other end has disconnected
                    print('===== %s@%s has left the chat =====' % conn.getsockname())
                    conn.getsockname()
                    conn.close()
                    self.connList.remove(conn)
                elif data == P2P_CHAT_NEWCONNECTION:
                    # Someone else (call this person C) is telling us to
                    # make a new socket for a new client to communicate with us
                    newconn = P2PChatConnection("NEWINDIRECTCLIENT",connection=conn)
                    
                    #OPTIONALLY CHECK HERE IF THE CLIENT'S PUBKEY IS OK FIRST?
                    newconn.acceptConnection()
                    
                    newconn.waitForAccept()
                    self.connList.append(newconn)
                    print('===== %s@%s has joined the chat =====' % newconn.getsockname())
                elif data == P2P_CHAT_NEWMESSAGE:
                    message = conn.receiveMessage()
                    print('%s@%s: %s'%(conn.getsockname()[0],
                                       conn.getsockname()[1], message))

            for conn in errored:
                print('===== %s@%s has left the chat =====' % conn.getsockname())
                conn.getsockname()
                conn.close()
                self.connList.remove(conn)
