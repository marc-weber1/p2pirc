from subprocess import Popen, PIPE, CREATE_NEW_CONSOLE
import socket, sys, os, time
from noise.connection import NoiseConnection, Keypair
sys.path.insert(1,"..")

try:
    os.remove('id-25519.json')
except IOError:
    pass

p1 = Popen(['start','/wait','cmd','/c','python','../p2pirc-linux.py','--new','--entrypoint','8123'], stdout=PIPE, stderr=PIPE, stdin=PIPE, creationflags=CREATE_NEW_CONSOLE, shell=True)
p2 = Popen(['start','/wait','cmd','/c','python','../p2pirc-linux.py'], stdout=PIPE, stderr=PIPE, stdin=PIPE, creationflags=CREATE_NEW_CONSOLE, shell=True)
p3 = Popen(['start','/wait','cmd','/c','python','../p2pirc-linux.py'], stdout=PIPE, stderr=PIPE, stdin=PIPE, creationflags=CREATE_NEW_CONSOLE, shell=True)

time.sleep(5)

p1.stdin.write(b"/accept g5ZU1KCL\r\n")
p1.stdin.write(b"hi\n")
p2.stdin.write(b"sup\n")
p3.stdin.write(b"not much\n")

p1.stdin.write(b"/leave\n")
p2.stdin.write(b"/leave\n")
p3.stdin.write(b"/leave\n")

print("------ P1 ------")
print( p1.communicate() )
print("------ P2 ------")
print( p2.communicate() )
print("------ P3 ------")
print( p3.communicate() )

#p1.kill()
#p2.kill()
#p3.kill()