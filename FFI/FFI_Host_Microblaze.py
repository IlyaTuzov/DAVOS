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
# ---------------------------------------------------------------------------------------------s---------


from FFI_Host_Controlled import *
from Parsers.DesignParser import *
import pexpect
import commands

MIC_APPS = {
    FPGASeries.S7:  'FFI/FFI_Microblaze/InjApp_build/InjApp_S7.elf',
    FPGASeries.USP: 'FFI/FFI_Microblaze/InjApp_build/InjApp_USP.elf'
    }

class FFIHostMicroblaze(FFIHostControlled):
    def __init__(self, targetDir, DevicePart):
        super(FFIHostMicroblaze, self).__init__(targetDir, DevicePart)
        self.mic_script = os.path.join(self.moduledir, 'FFI/FFI_Microblaze/microblaze_server.do')
        self.mic_app = self.mic_app = os.path.join(self.moduledir, MIC_APPS[self.design.series])
        self.mic_port = 12346
        self.proc_xsct = None

    def connect_microblaze(self):
        self.mic_app = os.path.join(self.moduledir, MIC_APPS[self.design.series])
        if self.proc_xsct is not None:
            self.proc_xsct.close(force=True)
        #terminate any process that blocks microblaze port (if any)
        for i in range(2):
            commands.getoutput('fuser -k %d/tcp' %(self.mic_port))    
        time.sleep(1)
        #launch microblaze host app (xsct server at localhost:self.mic_port) 
        cmd = 'xsct {0:s} {1:d} {2:s} {3:s}'.format(self.mic_script, self.mic_port, self.design.files['BIT'][0], self.mic_app)
        print('Running: {0:s}'.format(cmd))
        self.proc_xsct = pexpect.spawn(cmd, timeout=100)
        self.proc_xsct.expect('XSCT Connected', timeout=100)
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
    
    

    

