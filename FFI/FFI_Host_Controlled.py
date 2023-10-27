# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Base library for the definition of the host-side of FPGA-based fault injectors,
#       whose workflow is completely controlled from the host
#
# Authors: Ilya Tuzov, Universitat Politecnica de Valencia
#          Gabriel Cobos Tello, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

from FFI_Host_Base import *
import pexpect
import commands


class FFIHostControlled(FFIHostBase):
    def __init__(self, targetDir, DevicePart, testbench_script):
        super(FFIHostControlled, self).__init__(targetDir, DevicePart)
        self.restart_period = 10000
        self.testbench_proc = None
        self.testbench_script = testbench_script
        self.testbench_port = 12345
        self.consec_failures = 0
        self.consec_timeouts = 0

    def load_faultlist(self, part_idx):
        print('Warning: Invoked abstract method load_faultlist() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

    def inject_fault(self, idx):
        print('Warning: Invoked abstract method inject_fault() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

    def remove_fault(self, idx):
        print('Warning: Invoked abstract method remove_fault() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

    def run_workload(self):
        res = self.serv_communicate('localhost', self.testbench_port, "1\n", 200)
        if res is not None:
            self.LastFmode = res.split(':')[0]
        else:
            self.LastFmode = 'hang'
        print("\t{0:20s}: {1:s} -- {2:s}".format('Injection result: ', self.LastFmode, str(res)))
        self.testbench_proc.expect(r'.+')
        return res

    def dut_recover(self):
        #detect hang loops (several consecutive hangs)
        if self.LastFmode in self.FmodesToReset:
            if self.LastFmode == self.PrevFmode:
                self.restart_all('Repeated failure mode {0} : DUT and MIC restart'.format(self.LastFmode))
                return
            #try to recover testbench without reloading a bitstream
            try:
                res = self.serv_communicate('localhost', self.testbench_port, "3\n", 200)
            except Exception as e:
                res = None
            #res = self.serv_communicate('localhost', self.testbench_port, "2\n", 200)
            #if res != 'ok':
            #    self.restart_all('testbench hang')
            #    self.LastFmode = "hang"
            #    return
            
            if res is not None: 
                if res.lower().split(':')[0] == 'pass':
                    print("\tDUT recovery check (post-SEU-remove): Ok, {0:s}".format(res))
                else:
                    print("\tDUT recovery check (post-SEU-remove): Fail, {0:s}".format(res))
                    #raw_input('Tesbench hang, press any key to restart...')
                    self.restart_all('testbench hang')
                    #self.LastFmode = "hang"
                    #status = self.serv_communicate('localhost', self.testbench_port, "2\n", 200)
                    #status = self.connect_testbench(1, 300)        #!!!!!
                    #if status > 0:
                    #    self.restart_all('testbench hang')
                    #    self.LastFmode = "hang"
                    #    return
                    #res = self.serv_communicate('localhost', self.testbench_port, "1\n", 10)
                    #if res is not None:
                    #    if res.lower().split(':')[0] not in self.FmodesToReset:
                    #        print("\tDUT recovery check (post-Reset): Ok")
                    #    else:
                    #        print("\tDUT recovery check (post-Reset): Fail")
                    #        self.restart_all('testbench hang')         
                    #else:
                    #    print("\tDUT recovery check (post-Reset): testbench Hang")
                    #    self.restart_all('testbench hang')
                    #    return
            else:
                print("\tDUT recovery check (post-SEU-remove): Fail")
                #status = self.serv_communicate('localhost', self.testbench_port, "2\n", 200)
                #status = self.connect_testbench(3, 300)        #!!!!!
                #if status > 0:
                #raw_input('Tesbench hang (None), press any key to restart...')
                self.restart_all('testbench hang')
                #self.LastFmode = "hang"


    def restart_kernel(self):
        print('Warning: Invoked abstract method restart_kernel() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

    def restart_all(self, message):
         print('Warning: Invoked abstract method restart_kernel() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)       


    def connect_testbench(self, attempts=1, maxtimeout=300):
        for i in range(attempts):
            if self.testbench_proc is not None:
                self.testbench_proc.close(force=True)
            # terminate any process that blocks testbench port (if any)
            for k in range(2):
                commands.getoutput('fuser -k %d/tcp' %(self.testbench_port))
            time.sleep(1)
            print('Running: {0:s} : attempt {1:d}'.format(self.testbench_script, i))
            try:
                self.testbench_proc = pexpect.spawn(self.testbench_script, timeout=maxtimeout)
                #self.testbench_proc.logfile_read = sys.stdout
                self.testbench_proc.expect('DUT ready', timeout=maxtimeout)
                print('testbench started at localhost:{0:d}'.format(self.testbench_port))
                return (0)
            except Exception as e:
                print('connect_testbench() failure')
        return (1)


    def run(self):
        self.PartIdx = -1
        exp_start_time = time.time()
        for idx in range(len(self.fault_list)):
            start_time = time.time()
            faultdesc = self.fault_list[idx]
            reloaded = False
            if (idx > 0) and (idx % self.restart_period == 0):
                self.restart_kernel()
                reloaded = True
            if (faultdesc.PartIdx > self.PartIdx) or reloaded:
                self.load_faultlist(faultdesc.PartIdx)
                self.PartIdx = faultdesc.PartIdx
            self.inject_fault(idx)
            self.run_workload()
            if self.fault_list[idx].FaultModel == FaultModels.PermanentSBU:
                self.remove_fault(idx)
            else:
                print("\t{0:20s}: {1:s}".format('Fault removal', 'Not required for transient faults'))
            self.dut_recover()
            self.InjStat.append(self.LastFmode)
            self.PrevFmode = self.LastFmode
            faultdesc.FailureMode = self.LastFmode
            print("\t{0:20s}: {1:.1f} seconds (Total: {2:.1f} seconds), Statistics: {3:s}\n".format(
                'Exp. Time', float(time.time() - start_time), float(time.time() - exp_start_time),
                self.InjStat.to_string()))
            for row in self.faultdesc_format_str(idx):
                self.logfile.write('\n'+';'.join(row))
            self.logfile.flush()
        print('Experimental result: {0:s}\nCompleted in {1:.1f} seconds'.format(
        self.InjStat.to_string(), float(time.time() - exp_start_time)))

    def serv_communicate(self, host, port, in_cmd, timeout=10):
        try:
            sct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sct.connect((host, port))
            sct.settimeout(timeout)
            sct.sendall(in_cmd)
            buf = sct.recv(1024)
            s = re.search(st_pattern, buf)
            if s:
                return (s.group(1).lower())
            else:
                print('serv_communicate(): return status: {0:s}'.format(str(buf)))
                return (None)
        except socket.timeout as e:
            print('Testbench Timeout')
            return (None)
