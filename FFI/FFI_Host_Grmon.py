import pexpect
import commands
from FFI_Host_Microblaze import *


class FFIHostGrmon(FFIHostMicroblaze):
    def __init__(self, targetDir, DevicePart, dut_script):
        super(FFIHostGrmon, self).__init__(targetDir, DevicePart)
        print('NOELV_FFI_App object as subclass')
        self.proc_grmon = None
        self.dut_script = dut_script
        self.dut_port = 12345
        self.consec_failures = 0
        self.consec_timeouts = 0

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
                self.proc_grmon.expect('DUT ready', timeout=maxtimeout)
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
        res = self.serv_communicate('localhost', self.dut_port, "1\n", 10)
        if res is not None:
            msg_tag = res.split(':')[0]
            self.LastFmode = self.InjStat.get_failure_mode(msg_tag)
            print("\t{0:20s}: {1:s}".format('Injection result', res))
        else:
            self.LastFmode = FailureModes.Hang
            print("\t{0:20s}: {1:s}".format('Injection result', 'Hang'))
            # self.restart_all('GRMON Hang')
        self.proc_grmon.expect(r'.+')
        return res

    def dut_recover(self):
        #detect hang loops (several consecutive hangs)
        if self.LastFmode == FailureModes.Hang:
            self.consec_failures+=1
        elif self.LastFmode == FailureModes.Timeout:
            self.consec_timeouts+=1
        else:
            self.consec_failures=0
            self.consec_timeouts=0
        if self.consec_failures >= 2 or self.consec_timeouts >= 2:
            self.consec_failures=0
            self.consec_timeouts=0
            self.restart_all('Several consecutive GRMON hangs')
            return
            
        if self.LastFmode == FailureModes.Hang:
            status = self.connect_dut(3, 30)
            if status > 0:
                self.restart_all('GRMON hang')
                return
        if self.LastFmode != FailureModes.Masked:
            #If no hang loops detected - try to recover grmon without reloading a bitstream
            res = self.serv_communicate('localhost', self.dut_port, "1\n", 10)
            if res is not None:
                if self.InjStat.get_failure_mode(res.lower().split(':')[0]) == FailureModes.Masked:
                    print "\tDUT recovery check (post-SEU-remove): Ok"
                else:
                    #if self.InjStat.get_failure_mode(res.lower().split(':')[0]) in [FailureModes.ReplicaFail, FailureModes.ReplicaTimeout]:
                    #    self.LastFmode = FailureModes.ReplicaHang
                    #else:
                    #    self.LastFmode = FailureModes.Hang
                    print "\tDUT recovery check (post-SEU-remove): Fail"
                    # try to reset the DUT
                    # res = self.serv_communicate('localhost', self.dut_port, "2\n", 10)
                    # if res is not None:
                    #    print("\tDUT has been reset")
                    # else:
                    #    print "\tDUT recovery check (post-SEU-remove): DUT Hang"
                    status = self.connect_dut(3, 30)
                    if status > 0:
                        self.restart_all('GRMON hang')
                        return
                    # run workload after reset
                    res = self.serv_communicate('localhost', self.dut_port, "1\n", 10)
                    if res is not None:
                        if self.InjStat.get_failure_mode(res.lower().split(':')[0]) == FailureModes.Masked:
                            print "\tDUT recovery check (post-Reset): Ok"
                        else:
                            print "\tDUT recovery check (post-Reset): Fail"
                            #status = self.connect_dut(3, 30)
                            #if status > 0:
                            self.restart_all('GRMON hang')
                            #return
                    else:
                        print "\tDUT recovery check (post-Reset): GRMON Hang"
                        #status = self.connect_dut(3, 30)
                        #if status > 0:
                        self.restart_all('GRMON hang')
                        return
            else:
                print "\tDUT recovery check (post-SEU-remove): Hang"
                status = self.connect_dut(3, 30)
                if status > 0:
                    self.restart_all('GRMON hang')
                self.LastFmode = FailureModes.Hang

    def cleanup(self):
        super(FFIHostGrmon, self).cleanup()
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

    Injector = FFIHostGrmon(project_dir, FPGASeries.S7, device_part, dut_script)
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


