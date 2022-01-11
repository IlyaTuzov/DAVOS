# Host application to control FPGA-based fault injection via Xilinx Microblaze IP
# Includes adaptation to Gaisler NOELV/grmon designs under test
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

import os
import sys
import subprocess
import re
import shutil
import glob
import struct
import datetime
import random
import time
import math
import socket
import pexpect
import commands
davos_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
sys.path.insert(1, davos_dir)
from Davos_Generic import Table
from DesignParser import *


class SEU_item:
    def __init__(self):
        self.Offset = 0x0
        self.DesignNode = ''
        self.SLR, self.FAR = 0x0, 0x0
        self.Word, self.Bit, self.Mask = 0x0, 0x0, 0x0
        self.Time = 0


class FaultDescriptor:
    def __init__(self, Id, CellType, multiplicity=1):
        self.Id = Id
        self.CellType = CellType
        self.Multiplicity = multiplicity
        self.SeuItems = []
        self.PartIdx = 0
        self.FailureMode = '-'




class CellTypes:
    EssentialBits, LUT, FF, BRAM, LUTRAM = range(5)
        

class FailureModes:
    Masked, Latent, SDC, Hang, Other = range(5)
    
    @staticmethod
    def to_string(fmode):
        if fmode == FailureModes.Masked:
            return('Masked')
        elif fmode == FailureModes.Latent:
            return('Latent')
        elif fmode == FailureModes.SDC:
            return('SDC')
        elif fmode == FailureModes.Hang:
            return('Hang')
        else:
            return('Other')


class InjectionStatistics:
    def __init__(self):
        self.population_size = int(0)
        self.sample_size = int(0)
        self.Masked_a = int(0)
        self.Masked_p = float(0)
        self.Masked_e = float(0)
        self.Latent_a = int(0)
        self.Latent_p = float(0)
        self.Latent_e = float(0)
        self.SDC_a    = int(0)
        self.SDC_p    = float(0)
        self.SDC_e    = float(0)
        self.Hang_a   = int(0)
        self.Hang_p   = float(0)
        self.Hang_e   = float(0)
        self.Other_a   = int(0)
        self.Other_p   = float(0)
        self.Other_e   = float(0)

        
    @staticmethod
    def get_failure_mode(msg):
        if 'pass'in msg.lower():
            return(FailureModes.Masked)
        if 'latent'in msg.lower():
            return(FailureModes.Latent)            
        elif 'sdc' in msg.lower():
             return(FailureModes.SDC)
        elif 'hang' in msg.lower():
             return(FailureModes.Hang)
        else:        
            return(FailureModes.Other)
            
    def append(self, fmode):
        if fmode == FailureModes.Masked:
            self.Masked_a += 1
        elif fmode == FailureModes.Latent:
            self.Latent_a += 1
        elif fmode == FailureModes.SDC:
            self.SDC_a += 1
        elif fmode == FailureModes.Hang:
            self.Hang_a += 1
        else:
            self.Other_a += 1
        self.update_stat()
        
    def update_stat(self):
        self.sample_size = self.Masked_a + self.Latent_a + self.SDC_a + self.Hang_a
        self.Masked_p = self.Masked_a / float(self.sample_size)
        self.Latent_p = self.Latent_a / float(self.sample_size)
        self.SDC_p    = self.SDC_a    / float(self.sample_size)
        self.Hang_p   = self.Hang_a   / float(self.sample_size)
        self.Masked_e = 1.96*math.sqrt( self.Masked_p*(1-self.Masked_p)*(self.population_size-self.sample_size)/(self.sample_size*(self.population_size-1)) )
        self.Latent_e = 1.96*math.sqrt( self.Latent_p*(1-self.Latent_p)*(self.population_size-self.sample_size)/(self.sample_size*(self.population_size-1)) )
        self.SDC_e    = 1.96*math.sqrt( self.SDC_p*(1-self.SDC_p)*(self.population_size-self.sample_size)/(self.sample_size*(self.population_size-1)) )
        self.Hang_e   = 1.96*math.sqrt( self.Hang_p*(1-self.Hang_p)*(self.population_size-self.sample_size)/(self.sample_size*(self.population_size-1)) )
        self.Masked_p *= 100; self.Latent_p *= 100; self.SDC_p *= 100; self.Hang_p *= 100; self.Masked_e *= 100; self.Latent_e *= 100; self.SDC_e *= 100; self.Hang_e *= 100; 
                  
    def to_string(self):
        return(u"Masked: {0:3d} ({1:2.2f}% \u00B1 {2:2.2f}%), Latent: {3:3d} ({4:2.2f}% \u00B1 {5:2.2f}%), SDC: {6:3d} ({7:2.2f}% \u00B1 {8:2.2f}%), Hang: {9:3d} ({10:2.2f}% \u00B1 {11:2.2f}%)".format(
            self.Masked_a, self.Masked_p, self.Masked_e, self.Latent_a, self.Latent_p, self.Latent_e, self.SDC_a, self.SDC_p, self.SDC_e, self.Hang_a, self.Hang_p, self.Hang_e).encode('utf-8'))


st_pattern = re.compile("Status:\s?{(.*?)}")

class LogFormats:
    csv, txt = range(2)

class InjectorMicroblazeManager(object):
    def __init__(self, targetDir, series, DevicePart):
        self.design = VivadoDesignModel(os.path.normpath(targetDir), series, DevicePart)
        self.generatedFilesDir = os.path.normpath(os.path.join(targetDir, 'DavosGenerated'))
        self.faultload_files = []
        self.fault_list = []
        self.faultload_files = []
        self.moduledir = davos_dir #os.path.dirname(os.path.realpath(__file__))
        self.mic_script = os.path.join(self.moduledir, 'FFI_Microblaze/microblaze_server.do')
        self.mic_app    = os.path.join(self.moduledir, 'FFI_Microblaze/InjApp_build/InjAppRelease.elf')
        self.mic_port   = 12346
        self.InjStat = InjectionStatistics()
        self.LastFmode = None
        self.PartIdx = -1
        self.proc_xsct = None
        self.restart_period = 100



    def initialize(self, logifle_to_restore = ""):
        if logifle_to_restore == "":
            self.logfilename = os.path.join(self.generatedFilesDir, 'LOG_{0:s}.csv'.format(
                datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))
            self.logfile = open(self.logfilename, 'a')
            self.logfile.write('sep = ;\n'+';'.join(self.get_fdesc_labels()))
            print('Injector Micriblaze Host Controller instantiated from {0}'.format(self.moduledir))
        else:
            self.logfilename = logifle_to_restore
            self.load_fault_list_csv(self.logfilename)
            self.logfile = open(self.logfilename, 'a')
            print('Injector Micriblaze Host Controller Restored from logfile {0}'.format(self.logfilename))
        self.design.initialize()

    def sample_SEU(self, pb, cell_type, sample_size, multiplicity):
        if cell_type == CellTypes.EssentialBits:
            framelist = self.design.getFarList_for_Pblock(pb.X1, pb.Y1, pb.X2, pb.Y2)
            self.InjStat.population_size = sum(frame.stat.EssentialBitsCount for frame in framelist)
            for i in range(sample_size):
                fconf = FaultDescriptor(i, CellTypes.EssentialBits, multiplicity)
                for j in range(multiplicity):
                    seu = SEU_item()
                    essential_bit_mask = 0x0
                    while (essential_bit_mask >> seu.Bit) & 0x1 == 0x0:
                        frame = random.choice(framelist)
                        seu.FAR = frame.FAR
                        seu.SLR = frame.SLR_ID
                        seu.Word = random.randint(0, self.design.CM.FrameSize-1)
                        seu.Bit = random.randint(0, 31)
                        essential_bit_mask = frame.mask[seu.Word]
                    seu.Mask = 0x1 << seu.Bit
                    f = FarFields.from_FAR(seu.FAR, self.design.series)
                    seu.DesignNode = 'EB:{0:08x}:(Type_{1:01d}/Top_{2:01d}/Row_{3:01d}/Column_{4:03d}/Frame_{5:02d})/Word_{6:03d}/Bit_{7:02d}'.format(
                        seu.SLR, f.BlockType, f.Top, f.Row, f.Major, f.Minor, seu.Word, seu.Bit)
                    fconf.SeuItems.append(seu)
                self.fault_list.append(fconf)
        elif cell_type == CellTypes.LUT:
            self.InjStat.population_size = sum(len(lut.bitmap) for lut in self.design.LutCellList)
            for i in range(sample_size):
                fconf = FaultDescriptor(i, CellTypes.LUT, multiplicity)
                for j in range(multiplicity):
                    seu = SEU_item()
                    essential_bit_mask = 0x0
                    while (essential_bit_mask >> seu.Bit) & 0x1 == 0x0:
                        lut = random.choice(self.design.LutCellList)
                        seu.SLR = lut.slr.fragment.SLR_ID
                        lut_bit_index = random.randint(0, len(lut.bitmap)-1)

                        seu.FAR, seu.Word, seu.Bit = lut.bitmap[lut_bit_index]
                        frame = self.design.CM.get_frame_by_FAR(seu.FAR, seu.SLR)
                        essential_bit_mask = frame.mask[seu.Word]
                    seu.Mask = 0x1 << seu.Bit
                    seu.DesignNode = '{0:s}/bit_{1:02d}'.format(lut.name, lut_bit_index)
                    fconf.SeuItems.append(seu)
                self.fault_list.append(fconf)
        print('Sampled faults: {0:d} (population size = {1:d})'.format(sample_size, self.InjStat.population_size))

    def export_fault_list_bin(self, part_size = 1000):
        specificator = '<L'         #Little Endian
        nparts = int(math.ceil(float(len(self.fault_list))/part_size))
        for part_idx in range(nparts):
            fname = os.path.join(self.generatedFilesDir, 'Faultlist_{0:d}.bin'.format(part_idx))
            self.faultload_files.append(fname)
            offset = 0
            with open(fname, 'wb') as f:
                for i in range(part_size):
                    if part_idx*part_size+i >= len(self.fault_list):
                        break
                    fdesc = self.fault_list[part_idx*part_size+i]
                    fdesc.PartIdx = part_idx
                    for seu in fdesc.SeuItems:
                        seu.Offset = offset
                        offset += 1
                        #Export SEU descriptor to file (7 words x 32-bit)
                        f.write(struct.pack(specificator, fdesc.Id))
                        f.write(struct.pack(specificator, seu.Offset))
                        f.write(struct.pack(specificator, fdesc.CellType))
                        f.write(struct.pack(specificator, seu.SLR))
                        f.write(struct.pack(specificator, seu.FAR))
                        f.write(struct.pack(specificator, seu.Word))
                        f.write(struct.pack(specificator, seu.Mask))
                        f.write(struct.pack(specificator, seu.Time))


    def get_fdesc_labels(self):
        return( ['Id', 'PartIdx', 'CellType', 'Multiplicity', 'FailureMode', 'Offset', 'DesignNode', 'SLR', 'FAR', 'Word', 'Bit', 'Mask', 'Time'] )

    def faultdesc_format_str(self, idx):
        res = []
        fdesc = self.fault_list[idx]
        for seu in fdesc.SeuItems:
            res.append(map(str, [
                fdesc.Id, fdesc.PartIdx, fdesc.CellType, fdesc.Multiplicity, fdesc.FailureMode,
                seu.Offset, seu.DesignNode, '0x{0:08x}'.format(seu.SLR), '0x{0:08x}'.format(seu.FAR), seu.Word, seu.Bit, '0x{0:08x}'.format(seu.Mask), seu.Time,
            ]))
        return(res)
        
    def export_fault_list_csv(self):
        self.FdescFile = os.path.join(self.generatedFilesDir, 'Faultlist.csv')
        FdescTable = Table('Faultlist', self.get_fdesc_labels())
        for idx in range(len(self.fault_list)):
            for row in self.faultdesc_format_str(idx):
                FdescTable.add_row(row)
        FdescTable.to_csv(';', True, self.FdescFile)
        print('Fault List exported to: {0}'.format(self.FdescFile))

    def load_fault_list_csv(self, infile):
        Fdesctab = Table('Fdesc')
        Fdesctab.build_from_csv(infile)
        fdesc, idx, i, MaxRows = None, -1, 0, Fdesctab.rownum()
        while i < MaxRows:
            fdesc = FaultDescriptor(
                int(Fdesctab.getByLabel('Id', i)),
                int(Fdesctab.getByLabel('CellType', i)),
                int(Fdesctab.getByLabel('Multiplicity', i)))
            fdesc.PartIdx = int(Fdesctab.getByLabel('PartIdx', i))
            fdesc.FailureMode = Fdesctab.getByLabel('FailureMode', i)
            for seu_idx in range(fdesc.Multiplicity):
                seu = SEU_item()
                seu.Offset = int(Fdesctab.getByLabel('Offset', i))
                seu.DesignNode = Fdesctab.getByLabel('DesignNode', i)
                seu.SLR = int(Fdesctab.getByLabel('SLR', i), 16)
                seu.FAR = int(Fdesctab.getByLabel('FAR', i), 16)
                seu.Word = int(Fdesctab.getByLabel('Word', i))
                seu.Bit = int(Fdesctab.getByLabel('Bit', i))
                seu.Mask = int(Fdesctab.getByLabel('Mask', i), 16)
                seu.Time = int(Fdesctab.getByLabel('Time', i))
                fdesc.SeuItems.append(seu)
                i += 1
            self.fault_list.append(fdesc)
        print('Fault descriptors restored from {0:s} : {1:d} items'.format(infile, len(self.fault_list)))


    def serv_communicate(self, host, port, in_cmd, timeout = 10):
        try:
            sct = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sct.connect((host, port))
            sct.settimeout(timeout)
            sct.send(in_cmd)
            buf = sct.recv(1024)
            s = re.search(st_pattern, buf)
            if s: 
                return(s.group(1))
            else:
                print('serv_communicate(): return status: {0:s}'.format(str(buf)))
                return(None)
        except socket.timeout as e:
            return(None)
        
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
        
    def run_workload(self):
        print('\trun_worload(): running superclass stub, this method must be implemented in subclass')
        time.sleep(0.1)
        self.InjStat.append('pass')
        
    def dut_recover(self):
        print('\tdut_recover(): running superclass stub, this method must be implemented in subclass')
        time.sleep(0.1)        
    
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
            print("\t{0:20s}: {1:.1f} seconds (Total: {2:.1f} seconds), Statistics: {3:s}\n".format('Exp. Time', float(time.time() - start_time), float(time.time() - exp_start_time), self.InjStat.to_string()))
            for row in self.faultdesc_format_str(idx):
                self.logfile.write('\n'+';'.join(row))
            self.logfile.flush()
        print('Experimental result: {0:s}\nCompleted in {1:.1f} seconds'.format(
        self.InjStat.to_string(), float(time.time() - exp_start_time))) 
            
    def cleanup(self):
        self.proc_xsct.close(force=True)    
        self.logfile.close()
    
    

    





       
class NOELV_FFI_App(InjectorMicroblazeManager):
    def __init__(self, targetDir, series, DevicePart, dut_script):
        super(NOELV_FFI_App, self).__init__(targetDir, series, DevicePart)
        print('NOELV_FFI_App object as subclass')
        self.proc_grmon = None
        self.dut_script = dut_script
        self.dut_port = 12345

    def connect_dut(self, attempts=1, maxtimeout=60):
        for i in range(attempts):
            if self.proc_grmon is not None:
                self.proc_grmon.close(force=True)
            #terminate any process that blocks grmon port (if any)
            for k in range(2):
                commands.getoutput('fuser -k %d/tcp' %(self.dut_port))
            time.sleep(1)
            print('Running: {0:s} : attempt {1:d}'.format(self.dut_script, i))
            try:
                self.proc_grmon = pexpect.spawn(self.dut_script, timeout=maxtimeout)
                self.proc_grmon.expect('DUT has been initialized', timeout=maxtimeout)
                print('GRMON started at localhost:{0:d}'.format(self.dut_port))
                return(0)
            except Exception as e:
                print('connect_dut() failure')
        return(1)

    def restart_all(self, message):
        try:
            self.proc_grmon.close(force=True)
        except Exception as e:
            pass
        try:
            self.proc_xsct.close(force=True)
        except Exception as e:
            pass
        commands.getoutput('fuser -k %d/tcp' %(self.dut_port))
        commands.getoutput('fuser -k %d/tcp' %(self.mic_port))
        i = 0
        while True:
            i+=1
            print('Restarting XSCT and GRMON {0:s}: attempt {1:d}'.format(message, i))
            self.connect_microblaze()
            status = self.connect_dut(2, 60)
            if status == 0:            
                if self.PartIdx >= 0:
                    self.load_faultlist(self.PartIdx)
                print("XSCT and GRMON restarted")
                return(0)        
        #print("restart_all(): failure, exiting")
        #sys.exit(0)

    def run_workload(self):
        res = self.serv_communicate('localhost', self.dut_port, "1\n", 1)
        if res is not None: 
            self.LastFmode = InjectionStatistics.get_failure_mode(res)
            print("\t{0:20s}: {1:s}".format('Injection result', res))
        else:
            self.LastFmode = FailureModes.Hang
            print("\t{0:20s}: {1:s}".format('Injection result', 'Hang'))
            #self.restart_all('GRMON Hang')
        return(res)
        
    def dut_recover(self):
        if self.LastFmode != FailureModes.Masked:
            res = self.serv_communicate('localhost', self.dut_port, "1\n", 1)
            if res is not None: 
                if 'pass' in res.lower():
                    print "\tDUT recovery check (post-SEU-remove): Ok"
                else:
                    self.LastFmode = FailureModes.Hang
                    print "\tDUT recovery check (post-SEU-remove): Fail"
                    #try to reset the DUT
                    #res = self.serv_communicate('localhost', self.dut_port, "2\n", 10)
                    #if res is not None: 
                    #    print("\tDUT has been reset")
                    #else:
                    #    print "\tDUT recovery check (post-SEU-remove): DUT Hang"
                    status = self.connect_dut(1,15)
                    if status > 0:
                        self.restart_all('GRMON hang')
                        return
                    #run workload after reset
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
                        status = self.connect_dut(1,15)
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
        super(NOELV_FFI_App, self).cleanup()
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
    
    
    Injector = NOELV_FFI_App(project_dir, FPGASeries.S7, device_part)
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