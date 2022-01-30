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
            return ('Masked')
        elif fmode == FailureModes.Latent:
            return ('Latent')
        elif fmode == FailureModes.SDC:
            return ('SDC')
        elif fmode == FailureModes.Hang:
            return ('Hang')
        else:
            return ('Other')


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
        self.SDC_a = int(0)
        self.SDC_p = float(0)
        self.SDC_e = float(0)
        self.Hang_a = int(0)
        self.Hang_p = float(0)
        self.Hang_e = float(0)
        self.Other_a = int(0)
        self.Other_p = float(0)
        self.Other_e = float(0)

    @staticmethod
    def get_failure_mode(msg):
        if 'pass' in msg.lower():
            return (FailureModes.Masked)
        if 'latent' in msg.lower():
            return (FailureModes.Latent)
        elif 'sdc' in msg.lower():
            return (FailureModes.SDC)
        elif 'hang' in msg.lower():
            return (FailureModes.Hang)
        else:
            return (FailureModes.Other)

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
        self.SDC_p = self.SDC_a / float(self.sample_size)
        self.Hang_p = self.Hang_a / float(self.sample_size)
        self.Masked_e = 1.96 * math.sqrt(
            self.Masked_p * (1 - self.Masked_p) * (self.population_size - self.sample_size) / (
                        self.sample_size * (self.population_size - 1)))
        self.Latent_e = 1.96 * math.sqrt(
            self.Latent_p * (1 - self.Latent_p) * (self.population_size - self.sample_size) / (
                        self.sample_size * (self.population_size - 1)))
        self.SDC_e = 1.96 * math.sqrt(self.SDC_p * (1 - self.SDC_p) * (self.population_size - self.sample_size) / (
                    self.sample_size * (self.population_size - 1)))
        self.Hang_e = 1.96 * math.sqrt(self.Hang_p * (1 - self.Hang_p) * (self.population_size - self.sample_size) / (
                    self.sample_size * (self.population_size - 1)))
        self.Masked_p *= 100
        self.Latent_p *= 100
        self.SDC_p *= 100
        self.Hang_p *= 100
        self.Masked_e *= 100
        self.Latent_e *= 100
        self.SDC_e *= 100
        self.Hang_e *= 100

    def to_string(self):
        return (
            u"Masked: {0:3d} ({1:2.2f}% \u00B1 {2:2.2f}%), Latent: {3:3d} ({4:2.2f}% \u00B1 {5:2.2f}%), SDC: {6:3d} ({7:2.2f}% \u00B1 {8:2.2f}%), Hang: {9:3d} ({10:2.2f}% \u00B1 {11:2.2f}%)".format(
                self.Masked_a, self.Masked_p, self.Masked_e, self.Latent_a, self.Latent_p, self.Latent_e, self.SDC_a,
                self.SDC_p, self.SDC_e, self.Hang_a, self.Hang_p, self.Hang_e).encode('utf-8'))


st_pattern = re.compile("Status:\s?{(.*?)}")


class LogFormats:
    csv, txt = range(2)





class FFIHostBase(object):
    def __init__(self, targetDir, series, DevicePart):
        self.design = VivadoDesignModel(os.path.normpath(targetDir), series, DevicePart)
        self.generatedFilesDir = os.path.normpath(os.path.join(targetDir, 'DavosGenerated'))
        self.faultload_files = []
        self.fault_list = []
        self.moduledir = davos_dir
        self.InjStat = InjectionStatistics()
        self.LastFmode = None
        self.PartIdx = -1

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
            lustcells = self.design.netlist.get_cells(NetlistCellGroups.LUT)
            self.InjStat.population_size = sum(len(lut.bitmap.keys()) for lut in lustcells)
            for i in range(sample_size):
                fconf = FaultDescriptor(i, CellTypes.LUT, multiplicity)
                for j in range(multiplicity):
                    seu = SEU_item()
                    essential_bit_mask = 0x0
                    while (essential_bit_mask >> seu.Bit) & 0x1 == 0x0:
                        lut = random.choice(lustcells)
                        seu.SLR = lut.slr.fragment.SLR_ID
                        lut_bit_index = random.choice(lut.bitmap.keys())
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
        return (
        ['Id', 'PartIdx', 'CellType', 'Multiplicity', 'FailureMode', 'Offset', 'DesignNode', 'SLR', 'FAR', 'Word',
         'Bit', 'Mask', 'Time'])

    def faultdesc_format_str(self, idx):
        res = []
        fdesc = self.fault_list[idx]
        for seu in fdesc.SeuItems:
            res.append(map(str, [
                fdesc.Id, fdesc.PartIdx, fdesc.CellType, fdesc.Multiplicity, fdesc.FailureMode,
                seu.Offset, seu.DesignNode, '0x{0:08x}'.format(seu.SLR), '0x{0:08x}'.format(seu.FAR), seu.Word, seu.Bit,
                '0x{0:08x}'.format(seu.Mask), seu.Time,
            ]))
        return (res)

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

    def initialize(self, logifle_to_restore="", unit_path="", pb=None):
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
        self.design.initialize(False, unit_path, pb)

    def cleanup(self):
        self.logfile.close()


