# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Base library for the definition of the host-side of FPGA-based fault injectors
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

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
davos_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
sys.path.insert(1, davos_dir)
from Davos_Generic import Table
from Parsers.DesignParser import *
import hashlib

class SEU_item:
    def __init__(self):
        self.Offset = 0x0
        self.DesignNode = ''
        self.CellY = 0
        self.CellLabel = 0
        self.SLR, self.FAR = 0x0, 0x0
        self.Word, self.Bit, self.Mask = 0x0, 0x0, 0x0
        self.Time = 0
        self.Duration = 0
        self.ReferenceWord = 0x0

class FaultModels:
    PermanentSBU, TransientSBU = range(2)

class FaultDescriptor:
    def __init__(self, Id, CellType, FaultModel, multiplicity=1):
        self.Id = Id
        self.CellType = CellType
        self.Multiplicity = multiplicity
        self.SeuItems = []
        self.PartIdx = 0
        self.FailureMode = '-'
        self.FaultModel = FaultModel


class CellTypes:
    EssentialBits, LUT, FF, BRAM, LUTRAM = range(5)


class InjectionStatistics:
    def __init__(self):
        self.population_size = int(0)
        self.sample_size = int(0)
        self.abs = {}
        self.per = {}
        self.err = {}

    def append(self, fmode):
        if fmode in self.abs:
            self.abs[fmode] += 1
        else:
            self.abs[fmode] = 1
        self.update_stat()

    def get_error_margin(self, p, sample_size, population_size, t=1.96):
        return t*math.sqrt(p*(1-p)*(population_size-sample_size) / (sample_size*(population_size-1)))

    def update_stat(self):
        self.sample_size = sum(self.abs.values())
        for fmode, val in self.abs.iteritems():
            self.per[fmode] = self.abs[fmode] / float(self.sample_size)
            self.err[fmode] = self.get_error_margin(self.per[fmode], self.sample_size, self.population_size, 1.96)
            self.per[fmode] *= 100.0
            self.err[fmode] *= 100.0

    def to_string(self):
        return (", ".join([u"{0:s}: {1:3d} ({2:2.2f}% \u00B1 {3:2.2f}%)".format(
            k, self.abs[k], self.per[k], self.err[k])
            for k in sorted(self.abs.keys())])).encode('utf-8')


st_pattern = re.compile("Status:\s?{(.*?)}")


class LogFormats:
    csv, txt = range(2)


CellLabelEncoding = {
    'A6LUT': 0, 'A5LUT': 0, 
    'B6LUT': 1, 'B5LUT': 1, 
    'C6LUT': 2, 'C5LUT': 2, 
    'D6LUT': 3, 'D5LUT': 3, 
    'E6LUT': 4, 'E5LUT': 4, 
    'F6LUT': 5, 'F5LUT': 5, 
    'G6LUT': 6, 'G5LUT': 6, 
    'H6LUT': 7, 'H5LUT': 7, 
    'AFF':  0,  'BFF':  1, 'CFF':  2,  'DFF':  3,
    'EFF':  4,  'FFF':  5, 'GFF':  6,  'HFF':  7,
    'AFF2': 8,  'BFF2': 9, 'CFF2': 10, 'DFF2': 11,
    'EFF2': 12, 'FFF2': 13,'GFF2': 14, 'HFF2': 15
}

class FFIHostBase(object):
    def __init__(self, targetDir, DevicePart):
        self.design = VivadoDesignModel(os.path.normpath(targetDir), DevicePart)
        self.generatedFilesDir = os.path.normpath(os.path.join(targetDir, 'DavosGenerated'))
        self.faultload_files = []
        self.fault_list = []
        self.moduledir = davos_dir
        self.InjStat = InjectionStatistics()
        self.LastFmode, self.PrevFmode = None, None
        self.FmodesToReset = ['hang']
        self.PartIdx = -1
        
        

    #  injection_time_interval, fault_duration_interval
    def sample_SEU(self, pb, cell_type, exp_conf):
        random.seed(12345)
        if cell_type == CellTypes.EssentialBits:
            framelist = self.design.getFarList_for_Pblock(pb.X1, pb.Y1, pb.X2, pb.Y2)
            self.InjStat.population_size = sum(frame.stat.EssentialBitsCount for frame in framelist)
            for i in range(exp_conf.sample_size_goal):
                fexp_conf = FaultDescriptor(i, CellTypes.EssentialBits, exp_conf.fault_model, exp_conf.fault_multiplicity)
                for j in range(exp_conf.fault_multiplicity):
                    seu = SEU_item()
                    essential_bit_mask = 0x0
                    while (essential_bit_mask >> seu.Bit) & 0x1 == 0x0:
                        frame = random.choice(framelist)
                        seu.FAR = frame.FAR
                        seu.SLR = self.design.CM.SLR_ID_LIST.index(frame.SLR_ID)
                        seu.Word = random.randint(0, self.design.CM.FrameSize-1)
                        seu.Bit = random.randint(0, 31)
                        essential_bit_mask = frame.mask[seu.Word]
                    seu.Mask = 0x1 << seu.Bit
                    seu.ReferenceWord = frame.data[seu.Word]
                    f = FarFields.from_FAR(seu.FAR, self.design.series)
                    seu.DesignNode = 'EB:{0:08x}:(Type_{1:01d}/Top_{2:01d}/Row_{3:01d}/Column_{4:03d}/Frame_{5:02d})/Word_{6:03d}/Bit_{7:02d}'.format(
                        seu.SLR, f.BlockType, f.Top, f.Row, f.Major, f.Minor, seu.Word, seu.Bit)
                    seu.Slice = "-"
                    seu.Bel = "-"
                    seu.Time = random.randint(exp_conf.injection_time[0], exp_conf.injection_time[1])
                    seu.Duration = 0 if fexp_conf.FaultModel == FaultModels.PermanentSBU else random.randint(exp_conf.fault_duration[0], exp_conf.fault_duration[1]) 
                    fexp_conf.SeuItems.append(seu)
                self.fault_list.append(fexp_conf)
        
        elif cell_type == CellTypes.LUT:
            lutcells = self.design.netlist.get_cells(NetlistCellGroups.LUT)
            self.InjStat.population_size = sum(len(lut.bitmap.keys()) for lut in lutcells)
            for i in range(exp_conf.sample_size_goal):
                fexp_conf = FaultDescriptor(i, CellTypes.LUT, exp_conf.fault_model, exp_conf.fault_multiplicity)
                for j in range(exp_conf.fault_multiplicity):
                    seu = SEU_item()
                    essential_bit_mask = 0x0
                    while (essential_bit_mask >> seu.Bit) & 0x1 == 0x0:
                        lut = random.choice(lutcells)
                        seu.CellY = int(lut.slice.Y)                        
                        seu.CellLabel = CellLabelEncoding[lut.beltype.replace('SLICEM_', '').replace('SLICEL_', '')]
                        seu.SLR = self.design.CM.SLR_ID_LIST.index(lut.slr.fragment.SLR_ID)
                        lut_bit_index = random.choice(lut.bitmap.keys())
                        seu.FAR, seu.Word, seu.Bit = lut.bitmap[lut_bit_index]
                        frame = self.design.CM.get_frame_by_FAR(seu.FAR, lut.slr.fragment.SLR_ID)
                        essential_bit_mask = frame.mask[seu.Word]
                    seu.Mask = 0x1 << seu.Bit
                    seu.ReferenceWord = frame.data[seu.Word]
                    seu.DesignNode = '{0:s}/bit_{1:02d}'.format(lut.name, lut_bit_index)
                    seu.Slice = lut.slice.Name
                    seu.Bel = lut.beltype
                    seu.Time = random.randint(exp_conf.injection_time[0], exp_conf.injection_time[1])
                    seu.Duration = 0 if fexp_conf.FaultModel == FaultModels.PermanentSBU else random.randint(exp_conf.fault_duration[0], exp_conf.fault_duration[1]) 
                    fexp_conf.SeuItems.append(seu)
                self.fault_list.append(fexp_conf)
        
        elif cell_type == CellTypes.FF:
            ffcells = self.design.netlist.get_cells(NetlistCellGroups.FF)
            self.InjStat.population_size = sum(len(ff.bitmap.keys()) for ff in ffcells)
            for i in range(exp_conf.sample_size_goal):
                fexp_conf = FaultDescriptor(i, CellTypes.FF, exp_conf.fault_model, exp_conf.fault_multiplicity)
                for j in range(exp_conf.fault_multiplicity):
                    seu = SEU_item()
                    ff = random.choice(ffcells)
                    seu.CellY = int(ff.slice.Y)                        
                    seu.CellLabel = CellLabelEncoding[ff.beltype]
                    if ff.slr is None:
                        ff.slr = self.design.dev_layout.get_Tile_local_coordinates(ff.slice.Tile.X, ff.slice.Tile.Y)[0]
                    seu.SLR = self.design.CM.SLR_ID_LIST.index(ff.slr.fragment.SLR_ID)
                    seu.FAR, seu.Word, seu.Bit = ff.bitmap[0]
                    frame = self.design.CM.get_frame_by_FAR(seu.FAR, ff.slr.fragment.SLR_ID)
                    seu.Mask = 0x0
                    seu.ReferenceWord = frame.data[seu.Word]
                    seu.DesignNode = ff.name
                    seu.Slice = ff.slice.Name
                    seu.Bel = ff.beltype                   
                    seu.Time = random.randint(exp_conf.injection_time[0], exp_conf.injection_time[1])
                    seu.Duration = 0
                    fexp_conf.SeuItems.append(seu)
                self.fault_list.append(fexp_conf)
        clock_cycles = (exp_conf.injection_time[1] - exp_conf.injection_time[0])
        if clock_cycles > 0: self.InjStat.population_size *= clock_cycles


        print('Sampled faults: {0:d} (population size = {1:d})'.format(exp_conf.sample_size_goal, self.InjStat.population_size))

    def export_fault_list_bin(self, part_size=1000):
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
                        #Export SEU descriptor to the binary file (10 words x 32-bit)
                        for atr in [fdesc.Id, seu.Offset, fdesc.CellType, fdesc.FaultModel,
                                    seu.CellY, seu.CellLabel,
                                    seu.SLR,  seu.FAR,    seu.Word,       seu.Mask, 
                                    seu.Time, seu.Duration, seu.ReferenceWord]:
                            f.write(struct.pack(specificator, atr))
                            
                            
    def export_fault_list_full(self):
        specificator = '<L'         #Little Endian
        fname = os.path.join(self.generatedFilesDir, 'Faultlist_0.bin')
        self.faultload_files.append(fname)
        with open(fname, 'wb') as f:
            #Header: Base + 0x0
            for atr in [0xFA01FA01, len(self.fault_list), 0x1, 0x0,
                        0x0, 0x0, 0x0, 0x0,
                        0x0, 0x0, 0x0, 0x0,
                        0x0, 0x0, 0x0, 0x0]:
                f.write(struct.pack(specificator, atr))
            offset = 0
            #Fault descriptors: Base + 0x40 + i*11*4 
            for i in range(len(self.fault_list)):
                fdesc = self.fault_list[i]
                fdesc.PartIdx = 0
                for seu in fdesc.SeuItems:
                    seu.Offset = offset
                    for atr in [fdesc.Id, seu.Offset, fdesc.CellType, fdesc.FaultModel,
                                seu.CellY, seu.CellLabel,
                                seu.SLR,  seu.FAR,    seu.Word,       seu.Mask, 
                                seu.Time, seu.Duration, seu.ReferenceWord]:
                        f.write(struct.pack(specificator, atr))  

    def get_fdesc_labels(self):
        return ['Id', 'PartIdx', 'CellType', 'FaultModel', 'Multiplicity', 'FailureMode', 'Offset', 'DesignNode', 'SLR', 'FAR',
                'Word', 'Bit', 'Mask', 'Time', 'Duration', 'ReferenceWord', 'Slice', 'Bel', 'CellY', 'CellLabel']

    def faultdesc_format_str(self, idx):
        res = []
        fdesc = self.fault_list[idx]
        for seu in fdesc.SeuItems:
            res.append(map(str, [
                fdesc.Id, fdesc.PartIdx, fdesc.CellType, fdesc.FaultModel, fdesc.Multiplicity,  fdesc.FailureMode,
                seu.Offset, seu.DesignNode, '0x{0:08x}'.format(seu.SLR), '0x{0:08x}'.format(seu.FAR), seu.Word, seu.Bit,
                '0x{0:08x}'.format(seu.Mask), seu.Time, seu.Duration, '0x{0:08x}'.format(seu.ReferenceWord), seu.Slice, 
                seu.Bel, seu.CellY, seu.CellLabel]))
        return res

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
                int(Fdesctab.getByLabel('FaultModel', i)),
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
                seu.Duration = int(Fdesctab.getByLabel('Duration', i))
                fdesc.SeuItems.append(seu)
                i += 1
            self.fault_list.append(fdesc)
        print('Fault descriptors restored from {0:s} : {1:d} items'.format(infile, len(self.fault_list)))

    def initialize(self, hashing=False, logifle_to_restore="", unit_path="", pb=None, load_ll_file=True):
        start_time = time.time()
        if logifle_to_restore == "":
            self.logfilename = os.path.join(self.generatedFilesDir, 'LOG_{0:s}.csv'.format(
                datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")))
            self.logfile = open(self.logfilename, 'a')
            self.logfile.write('sep = ;\n'+';'.join(self.get_fdesc_labels()))
            print('Injector {0:s} instantiated from {1:s}'.format(self.__class__.__name__, self.moduledir))
        else:
            self.logfilename = logifle_to_restore
            self.load_fault_list_csv(self.logfilename)
            self.logfile = open(self.logfilename, 'a')
            print('Injector {0:s} Restored from logfile {1:s}'.format(self.__class__.__name__, self.logfilename))
        if hashing:
            cfg = (unit_path, pb.to_string() if pb is not None else '', load_ll_file)
            digest = hashlib.md5(str(cfg)).hexdigest()
            dumpfile = os.path.join(self.generatedFilesDir, '{0:s}.pickle'.format(digest))
            if os.path.exists(dumpfile):
                with open(dumpfile, 'rb') as f:
                    print 'Loading cached DesignModel from {0:s}, config = {1:s}'.format(dumpfile, str(cfg))
                    self.design = pickle.load(f)
            else:
                self.design.initialize(False, unit_path, pb, load_ll_file)
                with open(dumpfile, 'wb') as f:
                    pickle.dump(self.design, f)
        else:
            self.design.initialize(False, unit_path, pb, load_ll_file)
        print('FFI Design Model initialized in {0:.1f} seconds'.format(time.time() - start_time))

    def cleanup(self):
        self.logfile.close()


