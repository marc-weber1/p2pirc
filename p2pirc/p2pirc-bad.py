import select, socket, time

'''with socket.socket() as s:
    s.bind(('localhost', 0))
    port = s.getsockname()[1]
    with socket.socket() as c:
        print(port)
        c.connect(('localhost', port))
        c.sendall(b'123123123123123123123123123')
        print(s.recv(1024))
        c.sendall(b'123123123123123123123123123123')
        print(c.recv(1024))'''

'''
Create A on port 100
A listens for newcomers on port 100 (this will never change!)
B sends message to port 100
    A tells B to connect to a specific port (101)
    B connects to 101, now they have a connection
    B creates a port for listening for newcomers (102)

When a client X receives a packet from Y (through X's receiving port):
    1. X creates a (server) socket on a new port, sends that to Y
    2. Y connects to that port, that's their communication port
    3. X continues to listen for connections on its receiving port
    4. Y then tells X the list of everyone else's receiving port
    5. X connects to everyone else's port, does steps 1-2 for each of them

When X says a message:






Client C connects to other client D.
D has a listening port.
C opens a temporary socket to connect to D's listening port.
D sees that C has connected and creates a new address to be used for C/D.
D sends C that address
C makes a socket corresponding to C/D, adds it to a list, and 
IF NOT THE FIRST PERSON IN LINE, STOP RIGHT HERE!!!
C makes the first socket in a list, connects to it and sends D something
D receives that something and sends C a list of addresses 
'''

def send(sock, string):
    b = string.encode('utf-8')
    l = len(b).to_bytes(4, 'big')
    sock.sendall(l + string.encode('utf-8'))

def myrecv(sock):
    l = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(l).decode('utf-8')

def main(target=None):
    # target == None iff we are creating a new room
    # else, target = network addr of anyone in the room
    if target:
        # CLIENT SIDE
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(target)
            print('Connected')
            addr = eval(myrecv(s))
            firstsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            firstsock.connect(addr)
            addrlist = eval(myrecv(firstsock))
            print('Received stuff', addrlist)
            connlist = []
            for addr in addrlist:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(addr)
                connlist.append(sock)
            connlist.append(firstsock)
            #print('Received new address from group:', connaddr)

    else:
        connlist = []
    
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        print('Listening on', listener.getsockname())

        # "SERVER" SIDE
        while True:
            time.sleep(0.005)
            readable, _, _ = select.select(connlist+[listener], [], [])
            # read from "connlist" to get messages from other clients
            # read from "listener" to accept new clients
            for thing in readable:
                if thing is listener:
                    s, addr = listener.accept()
                    print('Received new client at', addr)
                    listener.listen()
                    tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    tmpsock.bind(('127.0.0.1', 0))
                    tmpsock.listen()
                    send(s, str(tmpsock.getsockname()))                   
                    newsock, addr = tmpsock.accept()
                    s.close()

                    for conn in connlist:
                        # Tell everyone else to make a new socket for E
                        send(conn, 'makenewsock')
                        print('Told person')
                    print('Told everyone')

                    newsocks = []
                    for conn in connlist:
                        # Get the socket everyone made
                        newsocks.append(eval(myrecv(conn)))
                        print('Received person')
                    print('Received everyone')

                    connlist.append(newsock)
                    send(newsock, str(newsocks))
                    tmpsock.close()
                    print('Done!')
                else:
                    # THE FOLLOWING LINE IS WHERE IT CRASHED WHEN DISCONNECT!!
                    data = myrecv(thing)
                    if data == 'makenewsock':
                        #print('Request for makenewsock from', thing.getsockname())
                        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        tmpsock.bind(('127.0.0.1', 0))
                        tmpsock.listen()
                        print('New client has joined. Communication port has address',
                              tmpsock.getsockname())
                        send(thing, str(tmpsock.getsockname()))
                        newsock, addr = tmpsock.accept()
                        connlist.append(newsock)
                        tmpsock.close()
                        #print('Success!')
    finally:
        listener.close()
        for c in connlist:
            c.close()
                    
if __name__ == '__main__':
    port = input('Target: ')
    if not port:
        main()
    else:
        main(('127.0.0.1', int(port)))
