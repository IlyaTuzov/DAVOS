import sys
import datetime
import time

cnt = 0
while True:
    x = datetime.datetime.now()
    print("Message {0:d}: {1:s}\n".format(cnt, x.strftime("%H:%M:%S")))
    time.sleep(1)
    cnt+=1
    