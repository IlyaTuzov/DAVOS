from FFI_Host_Base import *



class FFIHostControlled(FFIHostBase):
    def __init__(self, targetDir, series, DevicePart):
        super(FFIHostControlled, self).__init__(targetDir, series, DevicePart)
        self.restart_period = 100

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
        print('Warning: Invoked abstract method run_workload() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)
        self.InjStat.append('pass')

    def dut_recover(self):
        print('Warning: Invoked abstract method run_workload() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

    def restart_kernel(self):
        print('Warning: Invoked abstract method restart_kernel() in {0:s} (this method must be overridden in subclass)',
              self.__class__.__name__)

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
            self.remove_fault(idx)
            self.dut_recover()
            self.InjStat.append(self.LastFmode)
            faultdesc.FailureMode = FailureModes.to_string(self.LastFmode)
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
            sct.send(in_cmd)
            buf = sct.recv(1024)
            s = re.search(st_pattern, buf)
            if s:
                return (s.group(1))
            else:
                print('serv_communicate(): return status: {0:s}'.format(str(buf)))
                return (None)
        except socket.timeout as e:
            return (None)
