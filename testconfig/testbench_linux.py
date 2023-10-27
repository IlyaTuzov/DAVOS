import os
import pexpect
import sys
import time
import shutil
from pexpect import pxssh
import getpass
import subprocess
import re
import hashlib
import socket
import time

ETH_INITIALIZED = False
grmon_proc, linux_proc = None, None
grmon_message_buf = ['']
MAX_RETRIES = 1
    
def eth_config(selene_dir):  
    global ETH_INITIALIZED
    if not ETH_INITIALIZED:
        with open(os.path.join(selene_dir, "grmon_davos.do"), "w") as f:
            f.write(
                """
                edcl 192.168.0.53
                after 1000
                source {0:s}/eth_config.tcl
                after 5000
                exit
                """.format(selene_dir)
            )
        script = "grmon -u -uart /dev/ttyUSB2 -c {0:s}/grmon_davos.do".format(selene_dir)
        grmon_proc = pexpect.spawn(script, timeout=30)
        grmon_proc.expect('link has been established', timeout=30)
        print("Configure ETH: SUCCESS")     
        ETH_INITIALIZED = True            
        grmon_proc.close()        
        time.sleep(5)


def boot_linux(selene_dir):   
    global grmon_proc
    with open(os.path.join(selene_dir, "grmon_davos.do"), "w") as f:
        f.write(
            """
            forward enable uart2
            load /home2/tuil/UC7/fw_payload.elf
            dtb /home2/tuil/UC7/bsc/selene.dtb
            run
            """.format()
        )
    script = "grmon -eth 192.168.0.53 -c {0:s}/grmon_davos.do".format(selene_dir)
    if grmon_proc is not None:
        if not grmon_proc.closed:
            #grmon_proc.close(force=True) 
            os.killpg(os.getpgid(grmon_proc.pid), signal.SIGTERM)
    for i in range(MAX_RETRIES):
        try:
            print("BOOT LINUX: START")
            grmon_proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        except Exception as e:
            print(str(e))
            print("BOOT LINUX: FAILURE")   
            if i==MAX_RETRIES-1:
                return False            
            continue 
    time.sleep(120)
    print('BOOT LINUX: DONE')
    return True
    
    
def capture_grmon_out(f, buffer):
    print("capture_grmon_out started")
    while True:
        line=f.readline()
        if line:
            grmon_message_buf[-1] += line    



def get_linux_terminal():
    global linux_proc
    try:
        if linux_proc is not None:
            linux_proc.close()
    except Exception as e:
        print(str(e))
    time.sleep(3)        
    linux_proc = pxssh.pxssh()
    for i in range(MAX_RETRIES):
        try:
            linux_proc.login("192.168.0.153", "riscv", "riscv", login_timeout=120, sync_multiplier=60)
            break
        except Exception as e:
            print(str(e))
            if i==MAX_RETRIES-1:
                return False             
            continue
    print("Linux Login: SUCCESS")
    time.sleep(5)    
    return True
    
    
def log(msg):
    with open("/home2/tuil/selene_axi4/selene-hardware/selene-soc/selene-xilinx-vcu118/DAVOS_log.txt", 'a') as logfile:
        logfile.write("\n\n{0:s}: {1:s}".format(str(time.ctime()), msg))
        logfile.flush()
        

#reference_dataset, reference_digest = None, None
def test_workload(linux_proc, golden_run=False):
    try:     
        linux_proc.sendline('./demo')
        time.sleep(1)
        workload_status = linux_proc.prompt(timeout=5)
        output = linux_proc.before
        result = re.findall("result\s=\s([a-zA-Z]+)", output)
        timeout_msg =  re.findall("TIMEOUT reached for\s([a-zA-Z]+)\s", output)
        os_msg =  re.findall("([a-zA-Z]+)\sfault", output)
        #dataset = ''.join(e for e in output if e.isalnum())
        #digest = hashlib.md5(dataset).hexdigest()
        #print("Workload result: {0:s}:{1:s}".format(digest, dataset))
    except Exception as e:
        return "Status: {{Testbench_Exception: {0:s} }}".format(str(e))     
        
    msg = "result={0:s}, timeout_msg={1:s}, os_msg={2:s}".format(str(result), str(timeout_msg), str(os_msg))        
    if workload_status == False:
        if terminate_workload():
            return "Status: {{timeout_unhandled: {0:s} }}".format(msg)
        else:
            if get_linux_terminal():
                terminate_workload()
                return "Status: {{Session_Crash: {0:s} }}".format(msg)
            else:
                return "Status: {{Linux_Crash: {0:s} }}".format(msg)
        
    if golden_run:
        #reference_dataset = dataset
        #reference_digest = '130a54d1d91f9ab44a317136aca166e5'        
        return "Status: {{Masked: pass}}"  
    else:
        if len(os_msg) > 0:
            return "Status: {{Linux_Error: {0:s} }}".format(msg)
        elif len(timeout_msg) > 0:
            if timeout_msg[0] == 'HEAD':
                log('Timeout_HEAD:\n{0:s}'.format(timeout_msg[0]))
                return "Status: {{Timeout_HEAD: {0:s} }}".format(msg)
            elif timeout_msg[0] == "TRAIL":
                log('Timeout_TRAIL:\n{0:s}'.format(timeout_msg[0]))
                return "Status: {{Timeout_TRAIL: {0:s} }}".format(msg)
            else:
                log('Timeout_Unknown:\n{0:s}'.format(timeout_msg[0]))
                return "Status: {{Timeout_Unknown: {0:s} }}".format(msg)
        elif len(result) > 0:
            if result[0] == 'pass':
                return "Status: {{Masked: {0:s} }}".format(msg)
            elif result[0] == 'fail':
                log('SignalledFailure:\n{0:s}'.format(msg))
                return "Status: {{Signalled_Failure: {0:s} }}".format(msg)
            else:
                log('SDC:\n{0:s}'.format(msg))
                return "Status: {{SDC: {0:s} }}".format(msg)
        else:
            log('UndefinedFailureMode:\n{0:s}'.format(msg))
            return "Status: {{UndefinedFailureMode: {0:s} }}".format(msg)            


def terminate_workload():
    try:
        linux_proc.sendcontrol('z')
        time.sleep(0.5)
        recover_status = linux_proc.prompt(timeout=5)
        output = linux_proc.before
        log("sendcontrol(c): {0:s}".format(output))
        
        linux_proc.send('\003')
        time.sleep(0.5)
        recover_status = linux_proc.prompt(timeout=5)
        output = linux_proc.before
        log("send(003): {0:s}".format(output))        
        
        linux_proc.sendline('pkill demo -c')
        time.sleep(0.5)
        recover_status = linux_proc.prompt(timeout=5)
        output = linux_proc.before
        log("pkill demo -c: {0:s}".format(output))        
        
        result = re.findall("([a-zA-Z0-9]+)", output)
    except Exception as e:
        log('pkill exception: {0:s}\n'.format(str(e)))
        return False
    if (recover_status == True) and (len(result) > 0):
        return True
    else:
        return False
        

    
    

HOST = 'localhost'
PORT = 12345
sct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sct.bind((HOST, PORT))
sct.listen(5)

eth_config("/home2/tuil/selene_axi4/selene-hardware/selene-soc/selene-xilinx-vcu118")
boot_linux("/home2/tuil/selene_axi4/selene-hardware/selene-soc/selene-xilinx-vcu118")
t = Thread(target=capture_grmon_out, args=(grmon_proc.stdout, grmon_message_buf))
t.daemon=True
t.start()

get_linux_terminal()

print("DUT ready")
sys.stdout.write("DUT ready\n")
res = None

while True:
    conn, addr = sct.accept()
    data = (conn.recv(1024)).strip()[0]
    print("\nReceived command: {0}".format(data))
    if data == "1":
        res = test_workload(linux_proc, False)
        
    elif data == "2":
        print("Rebooting Linux")
        #boot_linux("/home2/tuil/selene_axi4/selene-hardware/selene-soc/selene-xilinx-vcu118")
        get_linux_terminal()
        res = "Status: {{OK}}"
        
    elif data == "3":
        if terminate_workload():
            res = "Status: {{pass: {0:s} }}".format('No message')
        else:
            if get_linux_terminal():
                terminate_workload()
                res = "Status: {{pass: {0:s} }}".format('No message')
            else:
                res = "Status: {{fail: {0:s} }}".format('No message')
        
    elif data == "100":
        break
    
    else:
        #unknown command
        res = "Status: {{Unknown command}}"
        time.sleep(1)
    conn.sendall(res)            
    #print("Received from {0:s} : {1:s}".format(str(addr), str(data)))
    




linux_proc.close(force=True)
grmon_proc.close(force=True)
logfile.close()