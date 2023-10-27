# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Adaptation of Host-controlled FFI to the Microblaze-based injectors,
#       and its application to the NOEL-V processor (DUT)
#
# Authors: Ilya Tuzov, Universitat Politecnica de Valencia
#          Gabriel Cobos Tello, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------


from FFI_Host_Controlled import *
from Parsers.DesignParser import *


MIC_APPS = {
    FPGASeries.S7:  'FFI/FFI_Microblaze/InjApp_build/InjApp_S7.elf',
    FPGASeries.USP: 'FFI/FFI_Microblaze/InjApp_build/InjApp_USP.elf'
    }

class FFIHostMicroblaze(FFIHostControlled):
    def __init__(self, targetDir, DevicePart, testbench_script):
        super(FFIHostMicroblaze, self).__init__(targetDir, DevicePart, testbench_script)
        self.mic_script = os.path.join(self.moduledir, 'FFI/FFI_Microblaze/microblaze_server.do')
        self.mic_app = self.mic_app = os.path.join(self.moduledir, MIC_APPS[self.design.series])
        self.mic_port = 12346
        self.mic_proc = None

    def connect_microblaze(self):
        self.mic_app = os.path.join(self.moduledir, MIC_APPS[self.design.series])
        if self.mic_proc is not None:
            self.mic_proc.close(force=True)
        #terminate any process that blocks microblaze port (if any)
        for i in range(2):
            commands.getoutput('fuser -k %d/tcp' %(self.mic_port))    
        time.sleep(1)
        #launch microblaze host app (xsct server at localhost:self.mic_port) 
        cmd = 'xsct {0:s} {1:d} {2:s} {3:s}'.format(self.mic_script, self.mic_port, self.design.files['BIT'][0], self.mic_app)
        print('Running: {0:s}'.format(cmd))
        self.mic_proc = pexpect.spawn(cmd, timeout=100)
        self.mic_proc.expect('XSCT Connected', timeout=100)
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
        try:
            self.testbench_proc.close(force=True)
        except Exception as e:
            pass
        try:
            self.mic_proc.close(force=True)
        except Exception as e:
            pass
        commands.getoutput('fuser -k %d/tcp' % (self.testbench_port))
        commands.getoutput('fuser -k %d/tcp' % (self.mic_port))
        i = 0
        while True:
            i += 1
            print('Restarting XSCT and testbench {0:s}: attempt {1:d}'.format(message, i))
            self.connect_microblaze()
            status = self.connect_testbench(1, 300)
            if status == 0:
                if self.PartIdx >= 0:
                    self.load_faultlist(self.PartIdx)
                print("XSCT and testbench restarted")
                return (0)



    def inject_fault(self, idx):
        data = self.fault_list[idx].SeuItems[0].Offset
        cmd = 1 if self.fault_list[idx].FaultModel==FaultModels.PermanentSBU else 3
        res = self.serv_communicate('localhost', self.mic_port, "{0:d} {1:d}\n".format(cmd, data))
        MIC_OK = False
        if res is not None:
            status = map(int, res.split())
            if (status[0] == 0) and (status[1] == data):
                MIC_OK = True
            print("Exp: {0:d}, Target: {1:s}, Duration: {2:d}, FFI cmd: {3:d} \n\t{4:20s}: {5:s} ".format(
                idx, self.fault_list[idx].SeuItems[0].DesignNode, self.fault_list[idx].SeuItems[0].Duration, cmd, 
                'Injection status', 'Ok' if MIC_OK else 'Fail'))
        else:
            print("Microblaze connection error")               
        if not MIC_OK:
            print('inject_fault() failure: Relaunching microblaze')
            self.restart_all('')
        self.mic_proc.expect(r'.+')

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
        self.mic_proc.close(force=True)    
        self.testbench_proc.close(force=True)        
        self.logfile.close()
    
    

    

