from subprocess import Popen, PIPE, CREATE_NEW_CONSOLE
import socket, sys, os
from noise.connection import NoiseConnection, Keypair
sys.path.insert(1,"..")
from p2pirc.P2PChatConnection import P2PChatConnection

    

p1 = Popen(['start','/wait','cmd','/c','python','../p2pirc-linux.py','--new'], stdout=PIPE, stderr=PIPE, stdin=PIPE, creationflags=CREATE_NEW_CONSOLE, shell=True)
#p2 = subprocess.Popen(['python','../p2pirc-linux.py','--local-port','38501'])
#p3 = subprocess.Popen(['python','../p2pirc-linux.py','--local-port','38502'])
    
P2PChatConnection.private_key_file = "test.private_key"
c1 = P2PChatConnection("JOINDIRECT",addr=["127.0.0.1",38500])
print("[-> c1] Handshake started.")
c1.waitForAccept()
print("[<- c1] Pubkey accepted by server.")
print("[<- c1] Pubkey: "+str(c1.pubkey()))
print("[-> c1] Accepting pubkey.")
c1.acceptConnection()

print("[-> c1] Closing connection.")
c1.close()

p1.kill()