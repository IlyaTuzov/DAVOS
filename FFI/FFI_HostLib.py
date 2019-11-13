#!python
# Host-side application to support Xilinx SEU emulation tool
# Requires python 2.x and pyserial library 
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# MIT license
# Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector

import os
import sys
from serial import Serial
import subprocess
import serial.tools.list_ports
import re
import shutil
import glob
import struct
import datetime
import random
import time
#sys.path.insert(0, os.path.abspath(".."))
from Davos_Generic import Table
from BitstreamParser import *
from NetlistParser import *

class OperatingModes:
    Exhaustive, SampleExtend, SampleUntilErrorMargin = range(3)


res_ptn  = re.compile(r'Tag.*?([0-9]+).*?Injection Result.*?Injections.*?([0-9]+).*?([0-9]+).*?Masked.*?([0-9]+).*?Rate.*?([0-9\.]+).*?([0-9\.]+).*?Failures.*?([0-9]+).*?Rate.*?([0-9\.]+).*?([0-9\.]+)', re.M)
stat_ptn = re.compile(r'Tag.*?([0-9]+).*?Injection.*?([0-9]+).*?([0-9]+).*?Masked.*?([0-9]+).*?Rate.*?([0-9\.]+).*?([0-9\.]+).*?Failures.*?([0-9]+).*?Rate.*?([0-9\.]+).*?([0-9\.]+).*?Latent.*?([0-9]+).*?Rate.*?([0-9\.]+).*?([0-9\.]+)', re.M)
recovery_ptn = re.compile(r'([0-9]+).*?seconds.*?Experiments.*?([0-9]+).*?([0-9]+).*?Masked.*?([0-9]+).*?([0-9\.]+).*?([0-9\.]+).*?Failures.*?([0-9]+).*?([0-9\.]+).*?([0-9\.]+)')

ram_search_ptn = re.compile(r'([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=([0-9a-zA-Z_]+)\s+Ram=B:(BIT|PARBIT)([0-9]+)', re.M)
ff_search_ptn = re.compile(r'([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=([0-9a-zA-Z_]+)\s+Latch=([0-9a-zA-Z\.]+)\s+Net=(.*)', re.M)



class JobDescriptor:
    def __init__(self, BitstreamId):
        self.BitstreamId = BitstreamId
        self.SyncTag = 0            #this is to handshake with the device and filter messages on serial port
        self.BitstreamAddr = 0
        self.BitstreamSize = 0
        self.BitmaskAddr   = 0
        self.BitmaskSize   = 0
        self.FaultListAdr  = 0
        self.FaultListSize = 0
        self.UpdateBitstream = 0
        self.Mode = 0 # 0 - exhaustive, 1 - sampling
        self.Blocktype = 0 # 0 - CLB , 1 - BRAM, >=2 both
        self.Celltype = 0   # 0 - ANY, 1-FF, 2-LUT, 3-BRAM, 4-Type0
        self.Essential_bits = 0 # 0 - target all bits, 1 - only masked bits
        self.LogTimeout = 1000  #report intermediate results each 1000 experiments
        self.CheckRecovery = 0
        self.EssentialBitsCount = 0
        self.StartIndex = 0
        self.ExperimentsCompleted = 0
        self.Failures = 0
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
        self.InjectionTime = 0;     # 0-random, > 0 - inject before clock cycle 'InjectionTime', e.g. InjectionTime==1 - inject at the workload start 
        #these fields are not exported to device (for internal use)
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
        specificator = '<L'         #Little Endian
        with open(fname, 'wb') as f:
            f.write(struct.pack(specificator, 0xAABBCCDD)) #Start Sequence
            f.write(struct.pack(specificator, self.BitstreamId))
            f.write(struct.pack(specificator, self.SyncTag))
            f.write(struct.pack(specificator, self.BitstreamAddr)) 
            f.write(struct.pack(specificator, self.BitstreamSize)) 
            f.write(struct.pack(specificator, self.BitmaskAddr)) 
            f.write(struct.pack(specificator, self.BitmaskSize)) 
            f.write(struct.pack(specificator, self.FaultListAdr)) 
            f.write(struct.pack(specificator, self.FaultListSize)) 
            f.write(struct.pack(specificator, self.UpdateBitstream))
            f.write(struct.pack(specificator, self.Mode))
            f.write(struct.pack(specificator, self.Blocktype))
            f.write(struct.pack(specificator, self.Celltype))
            f.write(struct.pack(specificator, self.Essential_bits))
            f.write(struct.pack(specificator, self.CheckRecovery))
            f.write(struct.pack(specificator, self.LogTimeout))
            f.write(struct.pack(specificator, self.StartIndex))
            f.write(struct.pack(specificator, self.ExperimentsCompleted))
            f.write(struct.pack(specificator, self.Failures))
            f.write(struct.pack(specificator, self.Masked))
            f.write(struct.pack(specificator, self.Latent))
            f.write(struct.pack(specificator, self.SDC))
            f.write(struct.pack(specificator, self.sample_size_goal))
            f.write(struct.pack('<f', self.error_margin_goal))
            f.write(struct.pack(specificator, self.FaultMultiplicity))
            f.write(struct.pack(specificator, self.FilterFrames))
            f.write(struct.pack('<f', self.PopulationSize))
            f.write(struct.pack(specificator, self.WorkloadDuration))
            f.write(struct.pack(specificator, self.SamplingWithouRepetition))
            f.write(struct.pack(specificator, self.DetailedLog))
            f.write(struct.pack(specificator, self.DetectLatentErrors))
            f.write(struct.pack(specificator, self.InjectionTime))
            
            
            



#Export Frame Descriptors File (N frame items: {u32 FAR, u32 flags, FrameSize word items: {u32 data[i], u32 mask[i]}}
# | DescriptorList_offset,  DescriptorList_items                | 4B + 4B
# | RecoveryFrames_offset,  RecoveryFrames_items                | 4B + 4B
# | <-- DescriptorList_offset = 16                              | 
# | FAR_0, flags, NumOfEsBits, FrameSize x {data[i], mask[i]}   | 4B + 4B + 4B + (4B + 4B)x101 = 416B
# | ....                                                        | ... 416B x DescriptorList_items
# | <-- RecoveryFrames_offset = 16+ 412B xDescriptorList_items  |
# | FAR_0, FAR_1, ...                                           |       4B x RecoveryFrames_items
def export_DescriptorFile(fname, BIN_FrameList, RecoveryFrames, CheckpointFrames):
    specificator = '<I'         #Little Endian
    with open(os.path.join(os.getcwd(), fname), 'wb') as f:
        f.write(struct.pack(specificator, 24))                                                                  # DescriptorList_offset
        f.write(struct.pack(specificator, len(BIN_FrameList)))                                                  # DescriptorList_items
        f.write(struct.pack(specificator, 24 + (12+8*FrameSize)*len(BIN_FrameList)))                            # RecoveryFrames_offset
        f.write(struct.pack(specificator, len(RecoveryFrames)))                                                 # RecoveryFrames_items
        f.write(struct.pack(specificator, 24 + (12+8*FrameSize)*len(BIN_FrameList) + 4*len(RecoveryFrames)))    # CheckpointFrames_offset
        f.write(struct.pack(specificator, len(CheckpointFrames)))                                               # CheckpointFrames_items
        for frame in BIN_FrameList:                                     # 416B x DescriptorList_items
            frame.UpdateFlags()
            f.write(struct.pack(specificator, frame.GetFar()))
            f.write(struct.pack(specificator, int(frame.flags)))
            f.write(struct.pack(specificator, int(frame.EssentialBitsCount)))
            for i in range(FrameSize):
                f.write(struct.pack(specificator, frame.data[i]))
                f.write(struct.pack(specificator, frame.mask[i]))    
        for item in RecoveryFrames:                                     # 4B x RecoveryFrames_items
            f.write(struct.pack(specificator, item))
        for item in CheckpointFrames:                                   # 4B x RecoveryFrames_items
            f.write(struct.pack(specificator, item))




def ExportFaultList(ProfilingRes, fname):
        specificator = '<L'         #Little Endian
        with open(fname, 'wb') as f:
            #f.write(struct.pack(specificator, len(ProfilingRes)))
            for i in range(len(ProfilingRes)):
                ProfilingRes[i]['ID'] = i
                ProfilingRes[i]['InjRes'] = int(0)
                f.write(struct.pack(specificator, ProfilingRes[i]['ID']))
                f.write(struct.pack(specificator, ProfilingRes[i]['BitstreamCoordinates'][0])) #FAR
                f.write(struct.pack(specificator, ProfilingRes[i]['BitstreamCoordinates'][1])) #word
                f.write(struct.pack(specificator, ProfilingRes[i]['BitstreamCoordinates'][2])) #bit
                f.write(struct.pack('<f',         ProfilingRes[i]['Actime']))
                f.write(struct.pack(specificator, ProfilingRes[i]['InjRes']))



def LoadFaultList(fname):
    ProfilingRes=[]
    with open(fname,'rb') as f:
        N = os.stat(fname).st_size / (4*6)
        for i in range(N):
            item={'ID' : struct.unpack('<L',f.read(4))[0],
                  'BitstreamCoordinates' : (struct.unpack('<L',f.read(4))[0], struct.unpack('<L',f.read(4))[0], struct.unpack('<L',f.read(4))[0]),
                  'Actime' : struct.unpack('<f',f.read(4))[0],
                  'InjRes': struct.unpack('<L',f.read(4))[0]
                  }
            ProfilingRes.append(item)
    return(ProfilingRes)






    
    
    






       


def recover_statistics(fname):
    res = dict()
    if os.path.exists(fname):
        with open(fname, 'rU') as f:
            lines = f.readlines()
            for i in range(len(lines)-1, -1, -1):
                l = lines[i]
                matchDesc = re.search(recovery_ptn, l)
                if matchDesc:
                    res['Time'] = int(matchDesc.group(1))
                    res['ExperimentsCompleted'] = int(matchDesc.group(2))
                    res['EssentialBitsCount'] = int(matchDesc.group(3))
                    res['Masked'] = int(matchDesc.group(4))
                    res['masked_rate'] = float(matchDesc.group(5))
                    res['masked_error'] = float(matchDesc.group(6))
                    res['Failures'] = int(matchDesc.group(7))
                    res['failure_rate'] = float(matchDesc.group(8))
                    res['failure_error'] = float(matchDesc.group(9))
                    break
    return(res)



class InjectorHostManager:
    def __init__(self, targetDir, modelId, HwDescFile_path, InitTcl_path, InjectorApp_path, MemoryBufferAddress):       
        #Attach target dir and modelID
        self.targetDir, self.modelId = targetDir, modelId
        self.HwDescFile_path = HwDescFile_path          #Hardware description file for the target platform (system.hdf)
        self.InitTcl_path = InitTcl_path                #TCL to initialize the APU (ps7_init.tcl)
        self.InjectorApp_path = InjectorApp_path        #Injector App executable (.elf)
        self.MemoryBufferAddress = MemoryBufferAddress  #External data uploaded to / downloaded from this address (JobDescriptor, Bitstream, Bitmask)
        #required input files (defaults)
        self.Input_BitstreamFile  = os.path.join(targetDir, 'Bitstream.bit')
        self.Input_EBCFile        = os.path.join(targetDir, 'Bitstream.ebc')
        self.Input_EBDFile        = os.path.join(targetDir, 'Bitstream.ebd')
        self.Input_LLFile         = os.path.join(targetDir, 'Bitstream.ll')
        self.Input_CellDescFile   = os.path.join(targetDir, 'Bels.csv')
        self.Input_BinstreamFile  = self.Input_BitstreamFile.replace('.bit', '.bin')        
        self.Input_FarListFile    = os.path.join(targetDir, 'FarArray.txt')
        self.logdir = os.path.join(targetDir, 'log')
        if not os.path.exists(self.logdir): os.makedirs(self.logdir)    
        self.logfilename =    os.path.join(self.logdir, 'Injector.log')    
        self.recovered_statistics = recover_statistics(self.logfilename)
        self.logfile = open(self.logfilename, 'a', 0)
        self.logfile.write('Injector instantiated: {}\n\n'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        #list of internal memories to recover after injection
        self.RecoveryNodeNames = []        
        #Job descriptor file to be uploaded to the device before each run
        self.JobDescFile = os.path.join(targetDir, 'JobDesc.dat')
        self.EssentialBitsPerBlockType = [] 
        #Create a job descriptor object (to be used at runtime)
        self.jdesc = None 
        self.verbosity = 1      #0 - small log (only errors and results), 1 - detailed log
        self.MemConfig = []
        self.CustomLutMask = False
        self.Profiling = False
        self.DAVOS_Config = None
        #bitmask file to be created by this manager
        self.Output_FrameDescFile = os.path.join(self.targetDir, 'FrameDescriptors.dat')
        self.FaultListFile    = os.path.join(self.targetDir, 'FaultList.dat')
        self.LutMapFile = os.path.join(self.targetDir, 'LutMapList.csv')
        self.ProfilingResult = None
        self.target_logic = 'type0'
        self.DutScope = ''

    def configure(self, targetid, portname, VivadoProjectFile = '', ImplementationRun=''):
        self.targetid = targetid                        #Target CPU id on Xilinx HW server
        self.portname =  portname                       #Serial port name to interact with the target App (monitor the injection statistics, etc.)
        self.serialport = None                          #Serial port connection (established later at App startup)
        #Provide Vivado project file to generate intstream/bitmask/bells files
        self.VivadoProjectFile = VivadoProjectFile if VivadoProjectFile != '' else (lambda l: l[0] if l is not None and len(l)>0 else '')(glob.glob(os.path.join(self.targetDir,'*.xpr')))
        self.ImplementationRun = ImplementationRun if ImplementationRun != '' else '-filter {CURRENT_STEP == route_design || CURRENT_STEP == write_bitstream}'

    def attachMemConfig(self, meminfo, elf, proc):
         self.MemConfig.append({'meminfo':meminfo, 'elf':elf, 'proc':proc})


    def get_devices(self, device_tag = 'Cortex-A9 MPCore #0'):
        """
            Relates the connected Xilinx targets with their serial ports on the host side
    
            Returns:
                (list of dictionaries): [{target_id, portname}]
        """
        os.chdir(self.targetDir)
        res = []
        proc = subprocess.Popen('xsct', stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        out, err = proc.communicate("connect \nputs [targets] \nexit".encode())
        content = re.findall(r'^\s+?([0-9]+)\s(.*?)$', out.decode(), re.MULTILINE|re.DOTALL)    
        for i in content:
            if i[1].strip().find(device_tag) >= 0:
                desc = dict()
                desc['TargetId']=i[0].strip()
                desc['TargetLbl']=i[1].strip()
                res.append(desc)

        jobdesc = JobDescriptor(0)
        jobdesc.Mode = 0    #handshake mode
        jobdesc.ExportToFile('Jobdesc.dat')
        for desc in res:
            script = """
                connect
                target {0}
                rst
                loadhw {1}/
                source {2}
                ps7_init
                dow {3}
                dow -data {4} 0x{5:08x}
                con
                disconnect
                exit
            """.format(desc['TargetId'], self.HwDescFile_path, self.InitTcl_path, self.InjectorApp_path, os.path.join(os.getcwd(), 'Jobdesc.dat'), self.MemoryBufferAddress).replace('\\','/')
            for portdesc in serial.tools.list_ports.comports():
                print "Testing target {}, port {}".format(desc['TargetId'], portdesc[0])
                port = serial.Serial(portdesc[0], 115200, timeout = 30)
                proc = subprocess.Popen('xsct', stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
                out, err = proc.communicate(script.encode())
                proc.wait()
                port.write('target_{}\n'.format(desc['TargetId']).encode())
                while(True): 
                    line = port.readline().decode().replace('\n','')
                    if line != None:
                        if len(line) > 0 :
                            if line.find('target_{}'.format(desc['TargetId'])) >= 0:
                                desc['PortID'] = portdesc[0]
                                desc['PortName'] = portdesc[1]
                                print('Connected: target {} : Port {}'.format(str(desc['TargetId']), str(desc['PortID'] )))
                                break
                        else:
                            break
                port.close()
                if 'PortID' in desc: break
        return(res)



    def cleanup_platform(self):
        print("cleanup_platform: {}".format(str(self.targetid)))
        jobdesc = JobDescriptor(0)
        jobdesc.Mode = 1    #cleanup mode
        jobdesc.ExportToFile(os.path.join(os.getcwd(), 'Jobdesc.dat'))
        script = """
            connect
            target {0}
            rst
            loadhw {1}
            source {2}
            ps7_init
            dow {3}
            dow -data {4} 0x{5:08x}
            con
            disconnect
            exit
        """.format(str(self.targetid), self.HwDescFile_path, self.InitTcl_path, self.InjectorApp_path, os.path.join(os.getcwd(), 'Jobdesc.dat'), self.MemoryBufferAddress).replace('\\','/')
        port = serial.Serial(self.portname, 115200, timeout = 30)
        proc = subprocess.Popen('xsct', stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
        out, err = proc.communicate(script.encode())
        proc.wait()
        if err: print str(err)
        while(True): 
            line = port.readline().decode().replace('\n','')
            print line
            if line != None:
                if len(line) > 0 :
                    if line.find('Result') >= 0 and line.find('Success') >= 0:
                        print("Cleanup completed on target {}".format(str(self.targetid)))
                        break
                else:
                    break
        port.close()
        #raw_input('Press any key')




    def check_fix_preconditions(self):
        print "Running Fix preconditions, see detailed log in {}\nwait...".format(self.logfilename)
        os.chdir(self.targetDir)
        for i in [self.Input_BitstreamFile, self.Input_EBCFile, self.Input_EBDFile, self.Input_LLFile, self.Input_CellDescFile, 'LUTMAP.csv']:
            if not os.path.exists(i):
                print("Input files not found, running Vivado to obtain them...")
                out, err = ParseVivadoNetlist(self.VivadoProjectFile, self.ImplementationRun, self.targetDir)
                self.logfile.write(out)
                self.logfile.write((err if err != None else 'Successfully generated input files')+'\n')
        if not os.path.exists(self.Input_BinstreamFile):
            script = 'write_cfgmem -force -format BIN -interface SMAPx32 -disablebitswap -loadbit "up 0x0 {}" -file {}'.format(self.Input_BitstreamFile, self.Input_BinstreamFile)    
            proc = subprocess.Popen('vivado -mode tcl'.format(), stdin=subprocess.PIPE, stdout=subprocess.PIPE , shell=True)
            out, err = proc.communicate(script.replace('\\','/').encode())
            self.logfile.write((err if err != None else 'Successfully converted to Bin')+'\n')    
        #Profiling (obtain a list of valid FAR entries)
        if not os.path.exists(self.Input_FarListFile):
            self.jdesc = JobDescriptor(0)
            self.jdesc.UpdateBitstream = 1
            self.jdesc.Mode = 4    #profiling mode
            self.launch_injector_app()
            while(True): 
                line = self.serialport.readline().replace('\n','')
                if line != None:
                    matchDesc = re.search(r".*?Profiling Result:.*?([0-9]+).*?frames.*?at.*?0x([0-9abcdef]+)", line)
                    if matchDesc:
                        framesnum = matchDesc.group(1)
                        resaddr   = matchDesc.group(2)
                        break
            self.serialport.close()
            script = """connect\ntarget {0}\nmrd -bin -file FarArray.dat 0x{1} {2}""".format(self.targetid, resaddr, framesnum)
            proc = subprocess.Popen('xsct', stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            out, err = proc.communicate(script.encode())
            proc.wait()
            with open("FarArray.dat", 'rb') as rb, open(self.Input_FarListFile, "w") as rt:     
                for i in range(int(framesnum)):
                    rt.write("{0:08x}\n".format(struct.unpack('<L', rb.read(4))[0]))
        #post-fix check
        check = True
        for i in [self.Input_FarListFile, self.Input_BitstreamFile, self.Input_BinstreamFile, self.Input_EBCFile, self.Input_EBDFile, self.Input_LLFile, self.Input_CellDescFile]:
            if not os.path.exists(i):
                self.logfile.write('Injector Error: no file found {}\n'.format(str(i)))
                check = False
        if not check: return(check)
        self.GenerateFaultload()
        return(check)
        



    def GenerateFaultload(self):
        #Step 1: Build the list of frame addresses (obtained by running InjApp in profiling mode)
        FarList = LoadFarList(self.Input_FarListFile)
   
        #Step 2: Build the list of frame discriptors for complete bitstream (*.bit or *.bin)
        BIN_FrameList = bitstream_to_FrameList(self.Input_BinstreamFile, FarList)

        if self.target_logic=='type0' or self.target_logic=='all' or (self.target_logic=='lut' and not self.CustomLutMask):
            #Step 3: Build the list of frame descriptors from EBC+EBD (essential bits)
            EBC_FrameList = EBC_to_FrameList(self.Input_EBCFile, self.Input_EBDFile, FarList)

            #Step 4: Compare BIN to EBC and, if no mismatches found, copy essential bits mask to BIN
            mismatches = 0
            for i in range(len(EBC_FrameList)):
                for k in range(FrameSize):
                    if EBC_FrameList[i].data[k] != BIN_FrameList[i].data[k]:
                        if self.verbosity > 0:
                            self.logfile.write('Check EBC vs BIT: mismatch at Frame[{0:08x}]: Block={1:5d}, Top={2:5d}, Row={3:5d}, Major={4:5d}, Minor={5:5d}\n'.format(BIN_FrameList[i].GetFar(), BIN_FrameList[i].BlockType, BIN_FrameList[i].Top, BIN_FrameList[i].Row, self.Major, BIN_FrameList[i].Minor))
                        mismatches+=1
            if mismatches == 0: self.logfile.write('\nCheck EBC vs BIT: Complete Match\n')
            else: self.logfile.write('Check EBC vs BIT: Mismatches Count = {0:d}\n'.format(mismatches))
            if mismatches ==0:
                for i in range(len(EBC_FrameList)):
                    if (self.target_logic in ['type0', 'all']) or (self.target_logic=='lut' and BIN_FrameList[i].Minor in [26,27,28,29, 32,33,34,35]):
                        BIN_FrameList[i].mask = EBC_FrameList[i].mask



        if self.CustomLutMask:
            LutDescTab = Table('LutMap'); LutDescTab.build_from_csv(os.path.join(self.targetDir, 'LUTMAP.csv'))
            print('Mapping LUTs to bitstream')
            LutMapList = MapLutToBitstream(LutDescTab, BIN_FrameList, self.DutScope)
            with open(self.LutMapFile,'w') as f:
                f.write(LutListToTable(LutMapList).to_csv())
            if self.Profiling and self.DAVOS_Config != None:
                if not os.path.exists(self.FaultListFile):
                    print('Profiling LUTs switching activity')
                    self.ProfilingResult = Estimate_LUT_switching_activity(LutMapList, self.DAVOS_Config)
                    ExportFaultList(self.ProfilingResult, self.FaultListFile)
                else:
                    self.ProfilingResult = LoadFaultList(self.FaultListFile) #load from file
                with open(self.LutMapFile,'w') as f:
                    f.write(LutListToTable(LutMapList).to_csv())
                
            if self.target_logic in ['type0','all','lut']:
                for i in BIN_FrameList:
                    if i.Minor in [26,27,28,29, 32,33,34,35]:
                        if i.custom_mask==[]: 
                            i.mask = [0x0]*FrameSize
                        else:
                            for k in range(FrameSize):
                                i.mask[k] = i.custom_mask[k] #(i.mask[k] ^ i.custom_mask[k]) & i.mask[k]


        #Step 5: append targets from LL file (FF and BRAM)
        RecoveryRamLocations = []
        FAR_CLB = set()
        T = Table('Cells')
        T.build_from_csv(self.Input_CellDescFile)
        for node in self.RecoveryNodeNames:
            #print("Locations for {}".format(node))
            for i in T.query({'Node':node, 'BellType':'RAMB'}):
                RecoveryRamLocations.append(i['CellLocation']) 
        #print("Recovery Ram Locations: {}".format(str(RecoveryRamLocations)) )
        self.logfile.write('Recovery RAM Location: ' + str(RecoveryRamLocations)+'\n')        
        #Set mask=1 for all bits of used BRAM (from *.ll file)
        #And build FAR recovery list - include all FAR from *.ll file containing bits of selected design units (e.g. ROM inferred on BRAM)
        FARmask = dict()
        RecoveryFrames = set()
        CheckpointFrames = set()


        with open(self.Input_LLFile, 'r') as f:
            for line in f:
                matchDesc , t = re.search(ram_search_ptn,line), 1
                if not matchDesc: 
                    matchDesc, t = re.search(ff_search_ptn,line), 2
                if matchDesc:
                    FAR = int(matchDesc.group(1), 16)
                    offset = int(matchDesc.group(2))
                    block = matchDesc.group(3)
                    if t==1 and (block in RecoveryRamLocations):
                        RecoveryFrames.add(FAR)
                    elif t==2:
                        CheckpointFrames.add(FAR)

                    if (t==1 and self.target_logic=='bram') or (t==2 and self.target_logic in ['ff', 'type0']) or self.target_logic == 'all':
                        word, bit =offset/32, offset%32
                        if FAR in FARmask:
                            desc = FARmask[FAR]
                        else:
                            desc = FrameDesc(FAR)
                            desc.mask=[0]*FrameSize
                            FARmask[FAR] = desc
                        desc.mask[word] |= 1<<bit

                        
        for key in sorted(FARmask):
            for i in BIN_FrameList:
                if i.GetFar() == key:
                    i.mask = FARmask[key].mask
                    if self.verbosity > 2: self.logfile.write("{0:08x} : {1:s}\n".format(i.GetFar(), ' '.join(['{0:08x}'.format(x) for x in i.mask])))
                    break
        self.logfile.write('Recovery FAR: {}\n'.format(",".join(["{0:08x}".format(i) for i in sorted(list(RecoveryFrames))])))
        #Export the resulting descriptor

        with open(os.path.join(self.targetDir,'BitLog.txt'),'w') as f:
            for i in BIN_FrameList:
                if all(v==0 for v in i.mask): continue
                else: 
                    f.write(i.to_string(2)+'\n\n')

        export_DescriptorFile(self.Output_FrameDescFile, BIN_FrameList, RecoveryFrames, CheckpointFrames)
        populationsize = 0
        for i in list(range(0, 9)): self.EssentialBitsPerBlockType.append(0)
        for i in BIN_FrameList:
            populationsize += i.EssentialBitsCount
            self.EssentialBitsPerBlockType[i.BlockType] += i.EssentialBitsCount
            #self.logfile.write('FAR: {0:08x} = {1:5d} Essential bits\n'.format(i.GetFar(), i.EssentialBitsCount))
        self.logfile.write('Population Size: {0:10d}\n'.format(populationsize))
        self.logfile.write('CheckpointFrames = '+ ', '.join(['{0:08x}'.format(int(x)) for x in CheckpointFrames]))







    def cleanup(self):
        self.logfile.write('Injector stopped: {}\n\n'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.logfile.flush()
        self.logfile.close()

        
                


    def export_JobDescriptor(self):
        self.jdesc.ExportToFile(self.JobDescFile)
        self.jdesc.BitstreamAddr = self.MemoryBufferAddress + os.stat(self.JobDescFile).st_size
        while(self.jdesc.BitstreamAddr%0x10000 > 0): self.jdesc.BitstreamAddr += 1   #Bitstream should be aligned at 64KB in the memory to prevent DMA errors
        self.jdesc.BitstreamSize = os.stat(self.Input_BinstreamFile).st_size
        self.jdesc.BitmaskAddr = self.jdesc.BitstreamAddr + self.jdesc.BitstreamSize
        if os.path.exists(self.Output_FrameDescFile): 
            self.jdesc.BitmaskSize = os.stat(self.Output_FrameDescFile).st_size

        self.jdesc.FaultListAdr = self.jdesc.BitmaskAddr+self.jdesc.BitmaskSize
        if os.path.exists(self.FaultListFile): 
            self.jdesc.FaultListSize = os.stat(self.FaultListFile).st_size / (8*4)
        self.jdesc.ExportToFile(self.JobDescFile)
        if self.jdesc.UpdateBitstream > 0:
            self.logtimeout = 180   #more time for responce if bitstream is uploaded
        else:
            self.logtimeout = 15

    def export_devrun_script(self):
        script = """
        connect
        targets
        target {0}
        rst
        loadhw {1}
        source {2}
        ps7_init
        ps7_post_config
        dow {3}
        dow -data {4}           0x{5:08x}
        """.format(str(self.targetid), self.HwDescFile_path, self.InitTcl_path, self.InjectorApp_path, self.JobDescFile, self.MemoryBufferAddress)
        if self.jdesc.UpdateBitstream == 1:
            script += """\ndow -data {0}  0x{1:08x}\n""".format(self.Input_BinstreamFile, self.jdesc.BitstreamAddr)
            if os.path.exists(self.Output_FrameDescFile): 
                 script += """dow -data {0}  0x{1:08x}\n""".format(self.Output_FrameDescFile, self.jdesc.BitmaskAddr)
            if os.path.exists(self.FaultListFile): 
                    script += """dow -data {0}  0x{1:08x}\n""".format(self.FaultListFile, self.jdesc.FaultListAdr)

        script += "con \n exit \n"
        script = script.replace('\\','/')
        fname = os.path.join(self.targetDir, "InjectorStart.tcl")
        with open(fname,'w') as f:
            f.write(script)
        return(fname, script)




    def launch_injector_app(self):
        self.export_JobDescriptor()
        if self.serialport != None:
            if self.serialport.isOpen():
                self.serialport.close()
        self.serialport = serial.Serial(self.portname, 115200, timeout = self.logtimeout)
        try:
            self.serialport.open()
        except:
           self.logfile.write('\nSerial port is already open')
        success = False
        while not success:
            fname, script = self.export_devrun_script()
            proc = subprocess.Popen('xsct', stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
            out, err = proc.communicate(script.encode())
            #proc = subprocess.Popen('xsct {}'.format(fname), shell=True)
            proc.wait()
            if err != None and err.lower().find('no target') >= 0:
                success = False
                self.logfile.write('launch_injector_app: Injector run unsuccessful, retrying...')
            else:
                success = True
                self.logfile.write('launch_injector_app: Launched injector app')



    def run(self, operating_mode, jobdesc, recover_from_log = True):
        self.jdesc = jobdesc
        self.jdesc.InjectorError = False
        print("Running the injector...")
        #check if logged results satisfy the sample size or error margin - then simply return them without launching the experimentation
        if recover_from_log and len(self.recovered_statistics) > 0:
            self.jdesc.ExperimentsCompleted = self.recovered_statistics['ExperimentsCompleted']
            self.jdesc.StartIndex = self.jdesc.ExperimentsCompleted
            self.jdesc.EssentialBitsCount = self.recovered_statistics['EssentialBitsCount']
            self.jdesc.Masked = self.recovered_statistics['Masked']
            self.jdesc.masked_rate = self.recovered_statistics['masked_rate']
            self.jdesc.masked_error = self.recovered_statistics['masked_error']
            self.jdesc.Failures = self.recovered_statistics['Failures']
            self.jdesc.failure_rate = self.recovered_statistics['failure_rate']
            self.jdesc.failure_error = self.recovered_statistics['failure_error']
            self.jdesc.Time = self.recovered_statistics['Time']
            if operating_mode == OperatingModes.SampleUntilErrorMargin: #Stop experimentation if error margin goal reached
                if self.jdesc.error_margin_goal >= self.jdesc.masked_error or self.jdesc.error_margin_goal >= self.jdesc.failure_error:
                    self.logfile.write('\nReturning recovered statistics: Error margin reached')
                    self.jdesc.InjectorError, self.jdesc.VerificationSuccess = False, True
                    return(self.jdesc)
            elif operating_mode == OperatingModes.SampleExtend:         #Stop experimentation if sample size goal reached
                if self.jdesc.ExperimentsCompleted >= self.jdesc.sample_size_goal:
                    self.logfile.write('\nReturning recovered statistics: Sample size reached')
                    self.jdesc.InjectorError, self.jdesc.VerificationSuccess = False, True
                    return(self.jdesc)

        self.jdesc.SyncTag = random.randint(100, 1000000)
        self.launch_injector_app()       

        start_time = time.time()
        last_msg_time = start_time
        while((self.jdesc.Mode in [102, 103]) or (self.jdesc.error_margin_goal <= self.jdesc.masked_error) or (self.jdesc.error_margin_goal <= self.jdesc.failure_error) or (self.jdesc.ExperimentsCompleted <= self.jdesc.sample_size_goal)): 
            line = self.serialport.readline().replace('\n','')
            if line != None:
                if len(line) > 0 :
                    #self.logfile.write('\n'+line)
                    if int( time.time() - last_msg_time ) > self.logtimeout:
                        self.logfile.write('Valid Message Timeout\n\tRestaring from next intjection point')
                        hang_move_delta = 1
                        self.jdesc.StartIndex += hang_move_delta
                        self.jdesc.ExperimentsCompleted = self.jdesc.StartIndex
                        self.jdesc.Failures += hang_move_delta
                        self.export_JobDescriptor()
                        self.launch_injector_app()  
                        last_msg_time = time.time()                     
                        continue

                    if line.find('ERROR: Golden Run') >= 0:
                        last_msg_time = time.time()
                        self.jdesc.InjectorError, self.jdesc.VerificationSuccess = False, False
                        self.logfile.write(line+'\n')
                        break
                    if(self.verbosity>0): self.logfile.write('[{0:5d}] seconds: {1}'.format(int(time.time() - start_time), line))
                    if line.find('not found in cache') >= 0:
                        last_msg_time = time.time()
                        self.logfile.write('Uploading bitstream and bitmask...\n')
                        self.jdesc.UpdateBitstream = 1
                        self.launch_injector_app()                    
                        self.jdesc.UpdateBitstream = 0

                    matchDesc = re.search(res_ptn, line)
                    if matchDesc:
                        syncCheck = int(matchDesc.group(1))                        
                        if syncCheck == self.jdesc.SyncTag:
                            last_msg_time = time.time()
                            self.jdesc.ExperimentsCompleted = int(matchDesc.group(2))
                            self.jdesc.StartIndex = self.jdesc.ExperimentsCompleted
                            self.jdesc.EssentialBitsCount = int(matchDesc.group(3))
                            self.jdesc.Masked = int(matchDesc.group(4))
                            self.jdesc.masked_rate = float(matchDesc.group(5))
                            self.jdesc.masked_error = float(matchDesc.group(6))
                            self.jdesc.Failures = int(matchDesc.group(7))
                            self.jdesc.failure_rate = float(matchDesc.group(8))
                            self.jdesc.failure_error = float(matchDesc.group(9))
                            self.logfile.write('[{0:5d}] seconds | Exhaustive Result: {1:9d}, Masked: {2:9d}, masked_rate: {3:3.4f} +/- {4:3.4f}, Failures: {5:9d},  failure_rate: {6:3.4f} +/- {7:3.4f}\n'.format(int(time.time() - start_time), self.jdesc.ExperimentsCompleted, self.jdesc.Masked, self.jdesc.masked_rate, self.jdesc.masked_error, self.jdesc.Failures, self.jdesc.failure_rate, self.jdesc.failure_error))
                            break
                    else:
                        matchDesc = re.search(stat_ptn, line)
                        if matchDesc:
                            syncCheck = int(matchDesc.group(1))
                            if syncCheck == self.jdesc.SyncTag:
                                last_msg_time = time.time()
                                self.jdesc.ExperimentsCompleted = int(matchDesc.group(2))
                                self.jdesc.StartIndex = self.jdesc.ExperimentsCompleted
                                self.jdesc.EssentialBitsCount = int(matchDesc.group(3))
                                self.jdesc.Masked = int(matchDesc.group(4))
                                self.jdesc.masked_rate = float(matchDesc.group(5))
                                self.jdesc.masked_error = float(matchDesc.group(6))
                                self.jdesc.Failures = int(matchDesc.group(7))
                                self.jdesc.failure_rate = float(matchDesc.group(8))
                                self.jdesc.failure_error = float(matchDesc.group(9))
                                self.jdesc.Latent = int(matchDesc.group(10))
                                self.jdesc.latent_rate = float(matchDesc.group(11))
                                self.jdesc.latent_error = float(matchDesc.group(12))

                                stat = '[{0:5d}] seconds | Experiments: {1:9d} / {2:9d}, Masked: {3:9d}, masked_rate: {4:3.4f} +/- {5:3.4f}, Failures: {6:9d},  failure_rate: {7:3.4f} +/- {8:3.4f}, Latent: {9:9d}, latent_rate: {10:3.4f} +/- {11:3.4f}'.format(int(time.time() - start_time), self.jdesc.ExperimentsCompleted,self.jdesc.EssentialBitsCount, self.jdesc.Masked, self.jdesc.masked_rate, self.jdesc.masked_error, self.jdesc.Failures, self.jdesc.failure_rate, self.jdesc.failure_error, self.jdesc.Latent, self.jdesc.latent_rate, self.jdesc.latent_error)
                                self.logfile.write(stat+'\n')
                                if self.verbosity > 0: sys.stdout.write(stat+'\n'); sys.stdout.flush()

                else:
                    self.logfile.write('Timeout - hang\n\tRestaring from next intjection point')
                    hang_move_delta = 1
                    self.jdesc.StartIndex += hang_move_delta
                    self.jdesc.ExperimentsCompleted = self.jdesc.StartIndex
                    self.jdesc.Failures += hang_move_delta
                    self.export_JobDescriptor()
                    self.launch_injector_app()                           
        self.serialport.close()
        self.jdesc.InjectorError, self.jdesc.VerificationSuccess = False, True
        return(self.jdesc)



