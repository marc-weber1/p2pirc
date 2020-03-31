import asyncio, select, socket, sys
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout

def send(sock, string):
    data = string.encode('utf-8')
    lendata = len(data).to_bytes(4, 'big')
    sock.sendall(lendata + data)

def receive(sock):
    length = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(length).decode('utf-8')

class P2PChatConnection:
    def __init__(self, local_port_min, key_file):
        print("Connection object initialized.")
        ''' self.connList is a list of sockets we use to communicate with other
        people in the chat room '''
        self.listenerIP = '127.0.0.1'
        self.listenerPort = local_port_min
        self.connList = []
            
    def connect(self, IP, port):
        '''
        This function should be run to connect to an already existing room.
        It assumes that we are not already connected to a room.
        '''

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((IP, port))
            print('Connected')

            # 'addr' is the ip/port of the socket we need to connect to
            addr = eval(receive(s))

        # 'firstsock' will be the first element of self.connList.
        firstsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        firstsock.connect(addr)

        # The person we connect to will now tell everyone else to create
        # a socket for us to use. Then that person will send us the
        # addresses of the sockets they created.
        addrlist = eval(receive(firstsock))

        self.connList = [firstsock]
        for addr in addrlist:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(addr)
            self.connList.append(sock)
        
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
                result = await session.prompt_async('>>> ')
            if len(result) > 0 and result[0] == '/':
                command = result[1:]
                if command == 'leave':
                    return
                else:
                    print('Unknown command: "%s"' % command)
            print('Me:', result)
            for conn in self.connList:
                # Send the message to everyone else
                send(conn, 'message')
                #send(conn, str(self.listener.getsockname()))
                send(conn, result)

    async def listenForClients(self):
        while True:
            await asyncio.sleep(0.01)
            # The other two values from this function are writable and errored.
            # We might use the third one in the future to detect if someone has
            # disconnected (which would mean that their connection socket has closed)
            readable, _, _ = select.select([self.listener], [], [], 0)
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
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                            tmpsock.bind(('127.0.0.1', 0))
                            tmpsock.listen()
                            send(s, str(tmpsock.getsockname()))                   
                            newsock, addr = tmpsock.accept()
                            # We will eventually add newsock to connList, but not right
                            # away, since we need to use connList first
                        print('===== %s@%s has joined the chat =====' % newsock.getsockname())

                    # Tell everyone else to make a new socket for their communication
                    # with the new client
                    for conn in self.connList:
                        send(conn, 'makenewsock')
                    #print('Told everyone to make a new socket for the client')

                    # Everyone else will send a response back containing the address
                    # of the new socket they made
                    newsocks = []
                    for conn in self.connList:
                        newsocks.append(eval(receive(conn)))
                    #print('Received the new socket addresses')

                    self.connList.append(newsock)
                    send(newsock, str(newsocks))
                    #print('Done!')

    async def listenForMessages(self):
        while True:
            await asyncio.sleep(0.01)
            if not self.connList:
                continue
            readable, _, _ = select.select(self.connList, [], [], 0)

            for sock in readable:
                data = receive(sock)
                if data == 'makenewsock':
                    # Someone else (call this person C) is telling us to
                    # make a new socket for a new client to communicate with us
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tmpsock:
                        tmpsock.bind(('127.0.0.1', 0))
                        tmpsock.listen()
                        #print('New client has joined. Communication port has address',
                        #      tmpsock.getsockname())

                        # Send C the address of the new socket we created.
                        # C will then send this to the new client, who will connect
                        # to our socket.
                        send(sock, str(tmpsock.getsockname()))
                        newsock, addr = tmpsock.accept()
                        self.connList.append(newsock)
                        print('===== %s@%s has joined the chat =====' % newsock.getsockname())
                elif data == 'message':
                    message = receive(sock)
                    print('%s@%s: %s'%(sock.getsockname()[0],
                                       sock.getsockname()[1], message))
