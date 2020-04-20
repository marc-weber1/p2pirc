import asyncio, aioice, socket, json, select

def sendPT(sock, string):
    data = string.encode('utf-8')
    lendata = len(data).to_bytes(4, 'big')
    sock.sendall(lendata + data)

def receivePT(sock):
    length = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(length).decode('utf-8')

async def connect_ice():
    listener = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    listener.setblocking(1)
    listener.bind(('',8123))
    listener.listen()
    
    server_continue=True
    while server_continue:
        readable,_,_ = select.select([listener],[],[],0)
        
        for sock in readable:
            if sock is listener:
                s,addr = listener.accept()
                with s:
                    connection = aioice.Connection(ice_controlling=True)
                    
                    await connection.gather_candidates()
                    
                    data_out = [list(map(lambda x: x.to_sdp(),connection.local_candidates)),connection.local_username,connection.local_password]
                    print(data_out)
                    sendPT(s,json.dumps(data_out))
                    
                    data = json.loads(receivePT(s))
                    connection.remote_candidates = list(map(lambda x: aioice.Candidate.from_sdp(x), data[0]))
                    connection.remote_username = data[1]
                    connection.remote_password = data[2]
                    
                    await connection.connect()
                    
                    await connection.sendto(b'sup',1)
                    print("Sent sup to %s:%s." %s.getsockname())
                    response, component = await connection.recvfrom()
                    print(response)
                    
                    await connection.close()
                    
                
asyncio.run(connect_ice())