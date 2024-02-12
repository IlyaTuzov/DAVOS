# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Base library for the definition of the host-side of FPGA-based fault injectors,
#       whose workflow is controlled from the FPGA (evaluation board)
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

from FFI_Host_Base import *
from serial import Serial
import serial.tools.list_ports
import datetime
import re


class JobDescriptor:
    def __init__(self, BitstreamId):
        self.BitstreamId = BitstreamId
        self.SyncTag = 0  # this is to handshake with the device and filter messages on serial port
        self.BitstreamAddr = 0
        self.BitstreamSize = 0
        self.BitmaskAddr = 0
        self.BitmaskSize = 0
        self.FaultListAdr = 0
        self.FaultListSize = 0
        self.UpdateBitstream = 0
        self.Mode = 0  # 0 - exhaustive, 1 - sampling
        self.Blocktype = 0  # 0 - CLB , 1 - BRAM, >=2 both
        self.Celltype = 0  # 0 - ANY, 1-FF, 2-LUT, 3-BRAM, 4-Type0
        self.Essential_bits = 0  # 0 - target all bits, 1 - only masked bits
        self.LogTimeout = 1000  # report intermediate results each 1000 experiments
        self.CheckRecovery = 0
        self.EssentialBitsCount = 0
        self.StartIndex = 0
        self.ExperimentsCompleted = 0
        self.Failures = 0
        self.Signaled = 0
        self.Masked = 0
        self.Latent = 0
        self.SDC = 0
        self.sample_size_goal = 0
        self.error_margin_goal = float(0.0)
        self.FaultMultiplicity = 1
        self.FilterFrames = 0
        self.PopulationSize = 0.0
        self.WorkloadDuration = 0
        self.SamplingWithouRepetition = 0
        self.DetailedLog = 1
        self.DetectLatentErrors = 1
        self.InjectionTime = 0  # 0-random, > 0 - inject before clock cycle 'InjectionTime', e.g. InjectionTime==1 - inject at the workload start
        # these fields are not exported to device (for internal use)
        self.failure_rate = float(0.0)
        self.failure_error = float(50.0)
        self.masked_rate = float(0.0)
        self.masked_error = float(50.0)
        self.latent_rate = float(0.0)
        self.latent_error = float(0.0)
        self.InjectorError = False
        self.Time = None
        self.InjectorError = False
        self.VerificationSuccess = True

    def ExportToFile(self, fname):
        specificator = '<L'  # Little Endian
        with open(fname, 'wb') as f:
            f.write(struct.pack(specificator, 0xAABBCCDD))  # Start Sequence
            for i in [ self.BitstreamId, self.SyncTag, self.BitstreamAddr, self.BitstreamSize,
                       self.BitmaskAddr, self.BitmaskSize, self.FaultListAdr, self.FaultListSize,
                       self.UpdateBitstream, self.Mode, self.Blocktype, self.Celltype, self.Essential_bits,
                       self.CheckRecovery, self.LogTimeout, self.StartIndex, self.ExperimentsCompleted,
                       self.Failures, self.Signaled, self.Masked, self.Latent, self.SDC, self.sample_size_goal]:
                f.write(struct.pack(specificator, i))
            f.write(struct.pack('<f', self.PopulationSize))
            f.write(struct.pack('<f', self.error_margin_goal))
            for i in [ self.FaultMultiplicity, self.FilterFrames, self.WorkloadDuration, self.SamplingWithouRepetition,
                       self.DetailedLog, self.DetectLatentErrors, self.InjectionTime]:
                f.write(struct.pack(specificator, i))








class FFIHostMonitored(FFIHostBase):
    def __init__(self, targetDir, DevicePart, portname):
        super(FFIHostMonitored, self).__init__(targetDir, DevicePart)
        self.serialport = None
        self.portname = portname
        self.logtimeout = 5

    def connect_serial_port(self):
        if self.serialport != None:
            if self.serialport.isOpen():
                self.serialport.close()
        try:
            self.serialport = serial.Serial(self.portname, 115200, timeout = self.logtimeout)
            self.serialport.open()
            print("Conneted to serial port: {0:s}".format(self.portname))
        except Exception as e:
           print('Exception when opening serial port: {0:s}'.format(str(e)))


    def launch_injector_app(self):
        print("ERROR: Invoked abstract method launch_injector_app() of FFIHostMonitored class")

    def run(self):
        print("Running BAFFI in monitored mode")
        zynq_statms_ptn = re.compile("\[\s*(\d+\.\d+)\s*s\].*?FaultId=\s*([0-9]+).*?Fmode=\s*?([a-zA-Z]+)")
        FpgaAppTrace_fname = os.path.join(self.generatedFilesDir, 'FpgaAppTrace_{0:s}.txt'.format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))
        exp_start_time = time.time()
        with open(FpgaAppTrace_fname, 'a') as trace:
            self.connect_serial_port()
            self.launch_injector_app()
            faultid = 0
            timest = 0.0
            while( faultid != len(self.fault_list)-1 ):
                line = self.serialport.readline()
                if line != None:
                    trace.write(line)
                    if line.find('FFI experiment completed') >= 0:
                        break
                matchDesc = re.search(zynq_statms_ptn, line)
                if matchDesc is not None:
                    faultid = int(matchDesc.group(2))
                    faultdesc = self.fault_list[faultid]
                    faultdesc.FailureMode = matchDesc.group(3)
                    faultdesc.exp_time = float(matchDesc.group(1)) - timest
                    timest = float(matchDesc.group(1))
                    self.InjStat.append(faultdesc.FailureMode)
                    print("Fault [{0:5d}]: {1:10s}, Target: {2:s}\n\tExp.Time: {3:.3f} s / {4:.1f} s, Statistics: {5:s}\n".format(
                        faultid, faultdesc.FailureMode, faultdesc.SeuItems[0].DesignNode,
                        faultdesc.exp_time, float(time.time() - exp_start_time), self.InjStat.to_string()))
                    for row in self.faultdesc_format_str(faultid):
                        self.logfile.write('\n'+';'.join(row))
                    self.logfile.flush()
        self.serialport.close()




class FFIHostZynq(FFIHostMonitored):
    def __init__(self, targetDir, DevicePart, hw_config, fsbl_file, injector_app, portname):
        super(FFIHostZynq, self).__init__(targetDir, DevicePart, portname)
        self.mic_script = os.path.join(self.moduledir, 'FFI/FFI_Zynq/zynq_init.tcl')
        self.hw_config = hw_config
        self.fsbl_file = fsbl_file
        self.injector_app = injector_app

    def launch_injector_app(self):
        script = 'xsct {0:s} {1:s} {2:s} {3:s} {4:s} {5:s}'.format(
            self.mic_script, 
            self.design.files['BIT'][0], 
            self.hw_config, 
            self.fsbl_file,
            self.injector_app,
            self.faultload_files[0] )
        print('Running Zynq Injector App: {0:s}'.format(script))
        with open(os.path.join(self.generatedFilesDir, 'Zynq_init.log'), 'w') as logfile, \
                open(os.path.join(self.generatedFilesDir, 'Zynq_init.err'), 'w') as errfile:
            proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=logfile, stderr=errfile, shell=True)
            proc.wait()
        print('Launched Zynq Injector App')



