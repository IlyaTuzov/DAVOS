# Adaptation of Base FFI to the Microblaze-based injector, and its application to the NOELV (DUT)
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

from FFI_Host_Controlled import *
from DesignParser import *
import pexpect
import commands


class FFIHostMicroblaze(FFIHostControlled):
    def __init__(self, targetDir, series, DevicePart):
        super(FFIHostMicroblaze, self).__init__(targetDir, series, DevicePart)
        self.mic_script = os.path.join(self.moduledir, 'FFI_Microblaze/microblaze_server.do')
        self.mic_app    = os.path.join(self.moduledir, 'FFI_Microblaze/InjApp_build/InjAppRelease.elf')
        self.mic_port   = 12346
        self.proc_xsct = None

    def connect_microblaze(self):
        if self.proc_xsct is not None:
            self.proc_xsct.close(force=True)
        #terminate any process that blocks microblaze port (if any)
        for i in range(2):
            commands.getoutput('fuser -k %d/tcp' %(self.mic_port))    
        time.sleep(1)
        #launch microblaze host app (xsct server at localhost:self.mic_port) 
        cmd = 'xsct {0:s} {1:d} {2:s} {3:s}'.format(self.mic_script, self.mic_port, self.design.files['BIT'], self.mic_app)
        print('Running: {0:s}'.format(cmd))
        self.proc_xsct = pexpect.spawn(cmd, timeout=60)
        self.proc_xsct.expect('XSCT Connected', timeout=60)
        print('XSCT started at localhost:{0:d}'.format(self.mic_port))        

    def load_faultlist(self, part_idx):
        cmd = "{0:d} {1:s}\n".format(10, self.faultload_files[part_idx])
        res = self.serv_communicate('localhost', self.mic_port, cmd)
        MIC_OK = False
        if res is not None:
            status = res.split()
            if status[0] == 'ok':
                print('Faultlist loaded: {0:s}'.format(status[1]))
                MIC_OK = True
        if not MIC_OK:
            print('Load faultlist: error')
            self.restart_all('')

    def restart_kernel(self):
        cmd = "{0:d} {1:s}\n".format(11, self.mic_app)
        res = self.serv_communicate('localhost', self.mic_port, cmd)
        MIC_OK = False
        if res is not None:
            status = res.split()
            if status[0] == 'ok':
                print('Microblaze kernel restarted: {0:s}'.format(status[1]))
                MIC_OK = True
        if not MIC_OK:
            print('restart_kernel: error')
            self.restart_all('')

    def restart_all(self, message):
        print('Restarting XSCT and GRMON: '+message)
        self.connect_microblaze()
        self.load_faultlist(self.PartIdx)            

    def inject_fault(self, idx):
        data = self.fault_list[idx].SeuItems[0].Offset
        res = self.serv_communicate('localhost', self.mic_port, "{0:d} {1:d}\n".format(1, data))
        MIC_OK = False
        if res is not None:
            status = map(int, res.split())
            if (status[0] == 0) and (status[1] == data):
                MIC_OK = True
            print("Exp: {0:d}, Target: {1:s} \n\t{2:20s}: {3:s}".format(
                idx, self.fault_list[idx].SeuItems[0].DesignNode, 'Injection status', 'Ok' if MIC_OK else 'Fail'))
        else:
            print("Microblaze connection error")               
        if not MIC_OK:
            print('inject_fault() failure: Relaunching microblaze')
            self.restart_all('')

    def remove_fault(self, idx):
        data = self.fault_list[idx].SeuItems[0].Offset
        res = self.serv_communicate('localhost', self.mic_port, "{0:d} {1:d}\n".format(2, data))
        MIC_OK = False
        if res is not None:
            status = map(int, res.split())
            if (status[0] == 0) and (status[1] == data):
                MIC_OK = True
            print("\t{0:20s}: {1:s}".format('Fault removal', 'Ok' if MIC_OK else 'Fail'))
        else:
            print("Microblaze connection error")        
        if not MIC_OK:
            print('remove_fault() failure: Relaunching microblaze')
            self.restart_all('')

    def cleanup(self):
        self.proc_xsct.close(force=True)    
        self.logfile.close()
    
    

    


class FFIHostNOELV(FFIHostMicroblaze):
    def __init__(self, targetDir, series, DevicePart, dut_script):
        super(FFIHostNOELV, self).__init__(targetDir, series, DevicePart)
        print('NOELV_FFI_App object as subclass')
        self.proc_grmon = None
        self.dut_script = dut_script
        self.dut_port = 12345

    def connect_dut(self, attempts=1, maxtimeout=60):
        for i in range(attempts):
            if self.proc_grmon is not None:
                self.proc_grmon.close(force=True)
            # terminate any process that blocks grmon port (if any)
            for k in range(2):
                commands.getoutput('fuser -k %d/tcp' %(self.dut_port))
            time.sleep(1)
            print('Running: {0:s} : attempt {1:d}'.format(self.dut_script, i))
            try:
                self.proc_grmon = pexpect.spawn(self.dut_script, timeout=maxtimeout)
                self.proc_grmon.expect('DUT has been initialized', timeout=maxtimeout)
                print('GRMON started at localhost:{0:d}'.format(self.dut_port))
                return (0)
            except Exception as e:
                print('connect_dut() failure')
        return (1)

    def restart_all(self, message):
        try:
            self.proc_grmon.close(force=True)
        except Exception as e:
            pass
        try:
            self.proc_xsct.close(force=True)
        except Exception as e:
            pass
        commands.getoutput('fuser -k %d/tcp' % (self.dut_port))
        commands.getoutput('fuser -k %d/tcp' % (self.mic_port))
        i = 0
        while True:
            i += 1
            print('Restarting XSCT and GRMON {0:s}: attempt {1:d}'.format(message, i))
            self.connect_microblaze()
            status = self.connect_dut(2, 60)
            if status == 0:
                if self.PartIdx >= 0:
                    self.load_faultlist(self.PartIdx)
                print("XSCT and GRMON restarted")
                return (0)
                # print("restart_all(): failure, exiting")
        # sys.exit(0)

    def run_workload(self):
        res = self.serv_communicate('localhost', self.dut_port, "1\n", 1)
        if res is not None:
            self.LastFmode = InjectionStatistics.get_failure_mode(res)
            print("\t{0:20s}: {1:s}".format('Injection result', res))
        else:
            self.LastFmode = FailureModes.Hang
            print("\t{0:20s}: {1:s}".format('Injection result', 'Hang'))
            # self.restart_all('GRMON Hang')
        return (res)

    def dut_recover(self):
        if self.LastFmode != FailureModes.Masked:
            res = self.serv_communicate('localhost', self.dut_port, "1\n", 1)
            if res is not None:
                if 'pass' in res.lower():
                    print "\tDUT recovery check (post-SEU-remove): Ok"
                else:
                    self.LastFmode = FailureModes.Hang
                    print "\tDUT recovery check (post-SEU-remove): Fail"
                    # try to reset the DUT
                    # res = self.serv_communicate('localhost', self.dut_port, "2\n", 10)
                    # if res is not None:
                    #    print("\tDUT has been reset")
                    # else:
                    #    print "\tDUT recovery check (post-SEU-remove): DUT Hang"
                    status = self.connect_dut(1, 15)
                    if status > 0:
                        self.restart_all('GRMON hang')
                        return
                    # run workload after reset
                    res = self.serv_communicate('localhost', self.dut_port, "1\n", 1)
                    if res is not None:
                        if 'pass' in res.lower():
                            print "\tDUT recovery check (post-Reset): Ok"
                        else:
                            print "\tDUT recovery check (post-Reset): Fail"
                            status = self.connect_dut(1, 15)
                            if status > 0:
                                self.restart_all('GRMON hang')
                            return
                    else:
                        print "\tDUT recovery check (post-Reset): GRMON Hang"
                        status = self.connect_dut(1, 15)
                        if status > 0:
                            self.restart_all('GRMON hang')
                        return
            else:
                print "\tDUT recovery check (post-SEU-remove): Hang"
                status = self.connect_dut(1, 15)
                if status > 0:
                    self.restart_all('GRMON hang')
                self.LastFmode = FailureModes.Hang

    def cleanup(self):
        super(FFIHostNOELV, self).cleanup()
        self.proc_grmon.close(force=True)


if __name__ == "__main__":
    project_dir = os.path.normpath("/home/tuil/FFI/NOELV")
    device_part = '7vx485tffg1761'
    dut_script = os.path.join(project_dir, 'host_grmon.do')
    pb = Pblock(77, 2, 151, 147, 'NOELV')
    sample_size = 245
    multiplicity = 1
    fault_part_size = 50
    grmon_script = "grmon -u -ucli -uart /dev/ttyUSB2 -c /tmp/FFI/FFIMIC/host_grmon_1.do"
    random.seed(1000)

    Injector = FFIHostNOELV(project_dir, FPGASeries.S7, device_part, dut_script)
    Injector.initialize()
    Injector.sample_SEU(pb, CellTypes.EssentialBits, sample_size, multiplicity)
    Injector.export_fault_list_bin(fault_part_size)
    Injector.export_fault_list_csv()
    Injector.dut_script = grmon_script
    Injector.dut_port = 12345
    Injector.connect_microblaze()
    Injector.connect_dut()
    Injector.run()
    print("Completed")


