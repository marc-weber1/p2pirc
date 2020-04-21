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

# Test assertions:
# 1 - all members of self.connList should have a pubkey, and have a noise where noise.handshake_finished is true
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
            pubkey_database_b64 = json.loads(f_dat.read())
            self.pubkey_database = {base64.b64decode(k.encode("utf-8")):v for k,v in pubkey_database_b64.items()} #pubkey as bytes: nickname as string
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
                pubkey_database_string = json.dumps( {base64.b64encode(k).decode("utf-8"): v for k,v in self.pubkey_database.items()}, indent=2 )
                f_dat.write( pubkey_database_string )
                f_dat.close()
                print("Pubkeys saved to %s." %self.key_database_filename)
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

        pubkey_added = False
        if firstconn.pubkey in self.pubkey_database.keys():
            print("Confirmed entrypoint identity.")
            firstconn.acceptConnection()
        else:
            #CHECK HERE WITH THE USER IF THE ENDPOINT'S PUBKEY IS OK FIRST, RANDOMART?
            nick = self.getPubkeyNickname(firstconn.pubkey)
            print("WARNING: Entrypoint pubkey was not recognized. Adding it to the database.")
            
            self.pubkey_database[ firstconn.pubkey ] = nick
            pubkey_added = True
            firstconn.acceptConnection()
            
        print("  pubkey: %s" %base64.b64encode(firstconn.pubkey).decode("utf-8"))
        print("  nickname: %s" %self.pubkey_database[firstconn.pubkey])
        
        
        # The person we connect to will now tell everyone else to create
        # a socket for us to use. Then that person will send us the
        # addresses of the sockets they created.
        addrlist = firstconn.receiveAddressList()
        print("Other users in chat:")

        self.connList = [firstconn]
        for addr in addrlist:
            conn = P2PChatConnection("JOININDIRECT",addr=addr)
            conn.waitForAccept() #This blocks, more parallel way?
            if conn.pubkey in self.pubkey_database.keys():
                conn.acceptConnection()
            else:
                self.pubkey_database[ conn.pubkey ] = self.getPubkeyNickname(conn.pubkey)
                pubkey_added = True
                conn.acceptConnection()
            print("  %s" %self.pubkey_database[ conn.pubkey ])
            self.connList.append(conn)
        
        if pubkey_added:
            self.save_pubkey_database()
        
        print("Connection established.")
        try:
            if self.listenerPort >= 0:
                self.createListener()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.mainLoop())
        finally:
            if self.listenerPort >= 0:
                print('Closing our listener')
                self.listener.close()
            print('Closing our connection ports')
            for conn in self.connList:
                conn.close()

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
        if self.listenerPort >= 0:
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
                        if len(self.waitingList.keys()) == 0:
                            print("There are no connections waiting to be accepted.")
                        else:
                            print("Here are the connections waiting to be accepted:")
                            for i in self.waitingList.keys():
                                print("  "+i)
                    else:
                        self.pubkey_database[ self.waitingList[ command[1] ].pubkey ] = command[1]
                        self.save_pubkey_database()
                        self.acceptDirectClient( self.waitingList[ command[1] ] )
                        del self.waitingList[ command[1] ]
                    
                elif command[0] == 'nick': #Rename a known client
                    if len(command) < 3:
                        print("Usage: /nick current_name new_name")
                    elif not command[1] in self.pubkey_database.values():
                        print("Can't find user %s" %command[1])
                    else:
                        for pubkey,nickname in self.pubkey_database.items():
                            if nickname == command[1]:
                                self.pubkey_database[pubkey] = command[2]
                                self.save_pubkey_database()
                                break
                
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
                    
        print('===== %s has joined the chat =====' %self.pubkey_database[newconn.pubkey] )

        # Tell everyone else to make a new socket for their communication
        # with the new client
        for conn in self.connList:
            try:
                conn.sendNewConnection(newconn.addr)
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
                        if newconn.pubkey in self.pubkey_database.keys():
                            self.acceptDirectClient(newconn)
                        else:
                            newnick = self.getPubkeyNickname(newconn.pubkey)
                            #Tell the user there's someone new to accept
                            print('A new user is attempting to join the server. Details:')
                            print('    pubkey: ',base64.b64encode(newconn.pubkey).decode("utf-8"))
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
                    print('===== %s has left the chat =====' %self.pubkey_database[conn.pubkey] )
                    conn.getsockname()
                    conn.close()
                    self.connList.remove(conn)
                elif data == P2P_CHAT_NEWCONNECTION:
                    # Someone else (call this person C) is telling us to
                    # make a new socket for a new client to communicate with us
                    newconn = P2PChatConnection("NEWINDIRECTCLIENT",connection=conn)
                    
                    if newconn.pubkey in self.pubkey_database.items():
                        newconn.acceptConnection
                    else:
                        #OPTIONALLY CHECK HERE IF THE CLIENT'S PUBKEY IS OK FIRST?
                        self.pubkey_database[ newconn.pubkey ] = self.getPubkeyNickname(newconn.pubkey)
                        self.save_pubkey_database()
                        newconn.acceptConnection()
                        
                    
                    newconn.waitForAccept()
                    self.connList.append(newconn)
                    print('===== %s has joined the chat =====' %self.pubkey_database[newconn.pubkey] )
                elif data == P2P_CHAT_NEWMESSAGE:
                    message = conn.receiveMessage()
                    print('%s: %s'%(self.pubkey_database[conn.pubkey], message))

            for conn in errored:
                print('===== %s has left the chat =====' %self.pubkey_database[conn.pubkey] )
                conn.getsockname()
                conn.close()
                self.connList.remove(conn)
    
    
    def getPubkeyNickname(self,pubkey):
        #Generate a nickname
        newnick = gen_unique_nickname(pubkey)
        if newnick in self.waitingList.keys() or newnick in self.pubkey_database.values():
            if pubkey in self.pubkey_database.keys() or pubkey in list(map(lambda x: x.pubkey,self.waitingList.values())):
                #Person is already connected, and is connecting a second time ?
                pass
            else:
                #Hash collision or hash already set as nickname; you got extremely unlucky
                print("ERROR: HASH COLLISION; new joining user has been assigned a nickname that already exists in your database. They have been assigned a nickname that other peers in this group will not recognize.")
                while newnick in self.waitingList.keys() or newnick in self.pubkey_database.values():
                    newnick = gen_random_nickname()
        return newnick