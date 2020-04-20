import asyncio, aioice, socket, json

def sendPT(sock, string):
    data = string.encode('utf-8')
    lendata = len(data).to_bytes(4, 'big')
    sock.sendall(lendata + data)

def receivePT(sock):
    length = int.from_bytes(sock.recv(4), 'big')
    return sock.recv(length).decode('utf-8')

async def connect_ice():
    entrypoint = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    entrypoint.connect(('????',8123))
    data = json.loads(receivePT(entrypoint))

    connection = aioice.Connection(ice_controlling=False)
    await connection.gather_candidates()
    
    connection.remote_candidates = list(map(lambda x: aioice.Candidate.from_sdp(x), data[0]))
    connection.remote_username = data[1]
    connection.remote_password = data[2]
    
    data_out = [list(map(lambda x: x.to_sdp(),connection.local_candidates)),connection.local_username,connection.local_password]
    sendPT(entrypoint,json.dumps(data_out))
    
    print("Connecting...")
    await connection.connect()
    print("Connected. Receiving message...")
    data,component = await connection.recvfrom()
    print(data)
    await connection.sendto(b'not much',1)
    print("Sent not much.")
    
    await connection.close()
    
asyncio.get_event_loop().run_until_complete(connect_ice())