import subprocess

worker_proc = None

def restart_worker():
    global worker_proc
    if worker_proc is not None:
        if not worker_proc.closed:
            os.killpg(os.getpgid(worker_proc.pid), signal.SIGTERM)    
    script = "python worker.py"
    worker_proc = subprocess.Popen(script, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
    time.sleep(5)
    print("Worker init done")
    
    
def test_workload(test_idx):
    global worker_proc
    print "Running workload test {0:d}".format(test_idx)
    time.sleep(3)
    for line in worker_proc.stdout:
        if line is None:
            break
        else:
            print("\t"+line)


for i in range(10):
    test_workload(i)
    