import subprocess
from threading import Thread 
import time
 
linebuffer=[]
x=subprocess.Popen(['/bin/bash','-c',"while true; do sleep 5; echo yes; done"],stdout=subprocess.PIPE)

def reader(f,buffer):
   while True:
     line=f.readline()
     if line:
        buffer.append(line)
     else:
        break

t=Thread(target=reader,args=(x.stdout,linebuffer))
t.daemon=True
t.start()

while True:
  if linebuffer:
     print linebuffer.pop(0)
  else:
     print "nothing here"
     time.sleep(1)
     