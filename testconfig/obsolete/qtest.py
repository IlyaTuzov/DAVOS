import threading
import Queue
import time

class ExecControl:
    def __init__(self):
        self.quitflag = False
        

class InterruptableQueue():
    def __init__(self, maxsize, excntr):
        self.q = Queue.Queue(maxsize)
        self.excntr = excntr
        
    def interruptable_get(self):
        while not self.excntr.quitflag:
            try:
                return self.q.get(timeout=1)
            except Queue.Empty:
                pass
            
    def interruptable_put(self, item):
        while not self.excntr.quitflag:
            try:
                self.q.put(item, timeout=1)
                return True
            except Queue.Full:
                pass


class Item:
    def __init__(self, id):
        self.label = str(id)

        
class Generator:
    def __init__(self, excntr):
        self.excntr = excntr
        self.workthread = None
        
    def do_work(self):
        for i in range(15):
            if not self.excntr.quitflag:
                L = Item(i)
                MQ.interruptable_put(L)
                print("Put to queue: " + str(L.label))
            else:
                print('generator stop requested')
                return

    def run(self):
        self.workthread = threading.Thread(target=self.do_work)
        self.workthread.start()


        
try:  
    excntr = ExecControl()
    MQ = InterruptableQueue(5, excntr)    
    generator = Generator(excntr)
    generator.run()


    while generator.workthread.isAlive() or MQ.q.qsize() > 0:
        #print('runniojkng hbyo;8iusdyhfk,myu.hdxzg v,mx')
    
        item = MQ.interruptable_get()
        time.sleep(2)
        print('processed item : ' + str(item.label))   

    print('Completed')
    
    
    
    
    
except:
    excntr.quitflag = True
    
    
    
    
    
 