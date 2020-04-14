import asyncio, select, socket, sys, os, base64, json
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

from .P2PChatConnection import P2PChatConnection
from .P2PChatSignals import *


def gen_unique_nickname(pubkey): #Accessibility problem: l and I might look similar, and nicknames need to be typed
    digest = hashes.Hash(hashes.SHA256(),default_backend())
    digest.update(pubkey)
    return base64.b64encode(digest.finalize()[:6]).decode("utf-8")

def gen_random_nickname(): #Untested
    return base64.b64encode( os.urandom(6) ).decode("utf-8")


class P2PChat:

    def __init__(self, local_port_listener, key_database, key_file):
        ''' self.connList is a list of sockets we use to communicate with other
        people in the chat room '''
        self.listenerIP = '' #Binds to all IPs? Might be a security flaw, should only be 129.168.x.x for the intended router or 127.0.x.x for testing
        self.listenerPort = local_port_listener
        self.connList = []
        self.waitingList = {} # nickname : P2PChatConnection
        
        #Print out the pubkey?
        #print("Our pubkey: " + str(?.public_bytes(Encoding.Raw,PublicFormat.Raw)))
        
        #Then load the key database file
        try:
            f_dat = open(key_database, "r")
            self.pubkey_database = json.loads( f_dat.read() ) # pubkey : nickname
            f_dat.close()
            self.key_database_filename = key_database
        except IOError:
            print("ERROR: Failed to load the pubkey database %s. A temporary database will be used, and every possibly familiar peer will be marked as unfamiliar." %key_database)
            self.pubkey_database = {}
            self.key_database_filename = ''
        
    def save_pubkey_database(self): #Soon
        if self.key_database_filename != '':
            try:
                f_dat = open(self.key_database_filename, "w")
                f_dat.write( json.dumps( self.pubkey_database, indent=2 ) )
                f_dat.close()
                print("Pubkey saved to %s." %self.key_database_filename)
            except IOError:
                print("ERROR: Failed to save the pubkey database %s. Any peers accepted during this group chat will not be saved as trusted.")
        
    def connect(self, IP, port):
        '''
        This function should be run to connect to an already existing room.
        It assumes that we are not already connected to a room.
        '''
        print("Connecting to %s:%d ..." %(IP,port) )
        firstconn = P2PChatConnection("JOINDIRECT",addr=[IP,port])
        print("Sent public key to entrypoint. Waiting for them to accept ...")
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
                command = result[1:].split(' ')
                if len(command) == 0:
                    break
                
                
                # COMMANDS
                
                if command[0] == 'leave':
                    return
                    
                elif command[0] == 'accept':  #Accept a new client
                    if len(command) < 2 or not command[1] in self.waitingList.keys():
                        print("Here are the connections waiting to be accepted:")
                        # ...
                    else:
                        self.pubkey_database[ str(self.waitingList[ command[1] ].pubkey) ] = command[1]
                        self.save_pubkey_database()
                        self.acceptDirectClient( self.waitingList[ command[1] ] )
                        del self.waitingList[ command[1] ]
                    
                elif command[0] == 'nick': #Rename a known client
                    pass #Will implement once clientside pubkey works
                    
                else:
                    print('Unknown command: "%s"' % command)
            
            else: #Chat message
                print('Me:', result)
            
                # Send the message to everyone else
                for conn in self.connList:
                    conn.sendMessage(result)

    def acceptDirectClient(self,newconn): #newconn should be a P2PChatConnection
    
        newconn.acceptConnection()
        newconn.waitForAccept() #This blocks, maybe do this entire function on a new thread
                    
        print('===== %s@%s has joined the chat =====' % newconn.getsockname())

        # Tell everyone else to make a new socket for their communication
        # with the new client
        for conn in self.connList:
            try:
                conn.sendNewConnection(addr)
            except socket.error:
                pass
        #print('Told everyone to make a new socket for the client')

        # Everyone else will send a response back containing the address
        # of the new socket they made
        newsocks = []
        for conn in self.connList:
            try:
                newsocks.append(conn.receiveOpenAddress()) #This blocks too oops
            except socket.error:
                pass
        #print('Received the new socket addresses')

        self.connList.append(newconn)
        newconn.sendAddressList(newsocks)
        #print('Done!')


    async def listenForClients(self):
        while True:
            await asyncio.sleep(0.01)
            # The other two values from this function are writable and errored.
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
                        # newconn.pubkey
                        if str(newconn.pubkey) in self.pubkey_database.keys():
                            self.acceptDirectClient(newconn)
                        else:
                            #Generate a nickname
                            newnick = gen_unique_nickname(newconn.pubkey)
                            if newnick in self.waitingList.keys() or newnick in self.pubkey_database.values(): #Hash collision or hash already set as nickname; you got extremely unlucky
                                print("ERROR: HASH COLLISION; new joining user has been assigned a nickname that already exists in your database. They have been assigned a nickname that other peers in this group will not share with you.")
                                while newnick in self.waitingList.keys() or newnick in self.pubkey_database.values():
                                    newnick = gen_random_nickname()
                                
                            #Tell the user there's someone new to accept
                            print('A new user is attempting to join the server. Details:')
                            print('    pubkey: ',newconn.pubkey)
                            print('    address: %s:%s' %addr)
                            print('    fingerprint: %s' %newnick)
                            print('  To accept, type /accept %s' %newnick)
                            #Maybe randomart too?
                            
                            self.waitingList[ newnick ] = newconn
                            

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
                    print('%s@%s: %s'%( conn.getsockname()[0], conn.getsockname()[1], message))

            for conn in errored:
                print('===== %s@%s has left the chat =====' % conn.getsockname())
                conn.getsockname()
                conn.close()
                self.connList.remove(conn)
