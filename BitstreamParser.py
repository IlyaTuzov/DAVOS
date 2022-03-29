# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A datamodel representing the bitstream of Xilinx FPGAs.
#       Implements an API to parse and manipulate FPGA bitstreams.
#       Supported FPGAs: Xilinx 7-series, Ultrascale, Ultrascale+
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

from Davos_Generic import *
import struct
import ast
from collections import OrderedDict
import copy

DAVOSPATH = os.path.dirname(os.path.realpath(__file__))


class ByteOrder:
    LittleEndian, BigEndian = range(2)


class FPGASeries:
    S7, US, USP = range(3)

    @staticmethod
    def to_string(val):
        d = {0:'7-Series', 1:'Ultra Scale', 2:'Ultra Scale Plus'}
        if val in d.keys():
            return d[val]
        else:
            return 'Unknown'


FrameSizeDict = {FPGASeries.S7: 101, FPGASeries.US: 123, FPGASeries.USP: 93}

map_L = [63, 47, 62, 46, 61, 45, 60, 44, 15, 31, 14, 30, 13, 29, 12, 28, 59, 43, 58, 42, 57, 41, 56, 40, 11, 27, 10, 26,
         9, 25, 8, 24, 55, 39, 54, 38, 53, 37, 52, 36, 7, 23, 6, 22, 5, 21, 4, 20, 51, 35, 50, 34, 49, 33, 48, 32, 3,
         19, 2, 18, 1, 17, 0, 16]
map_M = [31, 15, 30, 14, 29, 13, 28, 12, 63, 47, 62, 46, 61, 45, 60, 44, 27, 11, 26, 10, 25, 9, 24, 8, 59, 43, 58, 42,
         57, 41, 56, 40, 23, 7, 22, 6, 21, 5, 20, 4, 55, 39, 54, 38, 53, 37, 52, 36, 19, 3, 18, 2, 17, 1, 16, 0, 51, 35,
         50, 34, 49, 33, 48, 32]


class FarFields:
    def __init__(self, series, BlockType, Top, Row, Major, Minor):
        self.series = series
        self.BlockType, self.Top, self.Row, self.Major, self.Minor = BlockType, Top, Row, Major, Minor

    @staticmethod
    def from_FAR(FAR, series):
        if series == FPGASeries.S7:
            return FarFields(series, (FAR>>23)&0x7, (FAR>>22)&0x1, (FAR>>17)&0x1F, (FAR>>7)&0x3FF, FAR&0x7F)
        elif series == FPGASeries.US:
            return FarFields(series, (FAR>>23)&0x7, 0x0,           (FAR>>17)&0x3F, (FAR>>7)&0x3FF, FAR&0x7F)
        elif series == FPGASeries.USP:
            return FarFields(series, (FAR>>24)&0x7, 0x0,           (FAR>>18)&0x3F, (FAR>>8)&0x3FF, FAR&0xFF)
        else:
            print('FarFields: unknown FPGA series')
            return None

    def to_string(self):
        return("Block={0:3d}, Top={1:3d}, Row={2:3d}, Column={3:3d}, Minor={4:3d}".format(self.BlockType, self.Top, self.Row, self.Major, self.Minor))

    def get_far(self):
        if self.series == FPGASeries.S7:
            return (self.BlockType<<23) | (self.Top<<22) | (self.Row<<17) | (self.Major<<7) | (self.Minor)
        elif self.series == FPGASeries.US:
            return (self.BlockType<<23) |                  (self.Row<<17) | (self.Major<<7) | (self.Minor)
        elif self.series == FPGASeries.USP:
            return (self.BlockType<<23) |                  (self.Row<<18) | (self.Major<<8) | (self.Minor)
        else:
            print "get_far() : unknown FPGA series"
            return 0x0


class FrameStatistics:
    def __init__(self):
        self.Empty = True
        self.EssentialBitsCount = 0
        self.Type = 0


class FrameDesc:
    def __init__(self, FAR=0x0, Series=FPGASeries.S7, SLR_ID=0x0):
        self.FAR = FAR
        self.SLR_ID = SLR_ID
        self.Series = Series
        self.coord = FarFields.from_FAR(self.FAR, self.Series)
        self.data = []
        self.mask = []
        self.ebc_data = []
        self.custom_mask = []
        self.stat = FrameStatistics()
        self.type = 'Unknown'
        self.size = FrameSizeDict[self.Series]

    def SetFar(self, FAR):
        self.FAR = FAR
        self.Coord = FarFields.from_FAR(self.FAR, self.Series)

    def GetFar(self):
        return(self.FAR)

    def update_stat(self):
        self.stat.Type = FarFields.from_FAR(self.FAR, self.Series).BlockType
        # flag[0] - not_empty - when at least one word is not masked-out
        self.stat.EssentialBitsCount = sum([bin(i).count("1") for i in self.mask])
        for i in self.data:
            if i!=0x0:
                self.stat.Empty=False
                break

    def to_string(self, log_data, log_mask, log_word_indexes):
        res = "\nFAR : {0:08x} ({1:s})\tSLR: {2:08x}".format(self.FAR, self.coord.to_string(), self.SLR_ID)
        if log_word_indexes:
            res += "\nWord: " + ' : '.join(['{0:8d}'.format(i) for i in range(self.size)])
        if log_data:
            res += "\nData: " + ' : '.join(['{0:08x}'.format(self.data[i]) for i in range(self.size)])
        if log_mask:
            if len(self.ebc_data) > 0:
                res += "\nEBC : " + ' : '.join(['{0:08x}'.format(self.ebc_data[i]) for i in range(self.size)])
            else:
                res += "\nEBC : " + ' : '.join(['--------' for i in range(FrameSizeDict[self.Series])])
            if len(self.mask) > 0:
                res += "\nMask: " + ' : '.join(['{0:08x}'.format(self.mask[i]) for i in range(self.size)])
            else:
                res += "\nMask: " + ' : '.join(['--------' for i in range(FrameSizeDict[self.Series])])
        return res


class ConfColumnDescriptor:
    def __init__(self, SLR, Block, Top, Row, Column, FrameNum, Type):
        self.SLR = SLR
        self.Block = Block
        self.Top = Top
        self.Row = Row
        self.Column = Column
        self.FrameNum = FrameNum
        self.Type = Type

    def to_string(self):
        return "SLR: {0:08x}, Block: {1:2d}, Top: {2:2d}, Row: {3:3d}, Column: {4:3d}, Minor Frames: {5:3d}, Type: {6:s}".format(
                self.SLR, self.Block, self.Top, self.Row, self.Column, self.FrameNum, self.Type)

class ConfMemLayout:
    def __init__(self):
        self.TopRows, self.BottomRows = 0, 0
        self.Columns = 0
        self.RowHeight = 0
        self.ColumnTypes = ['SW', 'CLB', 'DSP', 'BRAMTYPE0', 'BRAMTYPE1', 'LAGUNA', 'UNKNOWN']
        self.ColumnDescriptors = []
        self.TileColumnIndexes = {i : [] for i in self.ColumnTypes}

    def to_string(self, short=True):
        res = "TopRows: {0:d}, BottomRows: {1:d}, Columns: {2:d}, RowHeight: {3:d}".format(
            self.TopRows, self.BottomRows, self.Columns, self.RowHeight)
        res += '\n\tColumnIndexes: {0:s}'.format('\n\t\t'.join(['{0:s} : {1:s}'.format(str(k), str(v)) for k, v in self.TileColumnIndexes.iteritems()]))
        if not short:
            for desc in self.ColumnDescriptors:
                res += "\n\t{0:s}".format(desc.to_string())
        return(res)
        

class BitfileType:
    Debug, Regular = range(2)


class FileTypes:
    EBC, EBD, BIT, BIN, LL = range (5)


class BitstreamStatistics:
    def __init__(self):
        self.UtilizedFrames = 0
        self.Type0Frames = 0
        self.Type1Frames = 0
        self.EssentialBitsCount = 0


#Config memory of Super Logic Region
class SuperLogicRegion:
    def __init__(self, SLR_ID, Series):
        self.SLR_ID = SLR_ID
        self.FarList = []
        self.Frames = dict()
        self.layout = ConfMemLayout()
        self.stat = BitstreamStatistics()
        self.Empty = True
        self.Series = Series

    def put_frame(self, frame):
        if not self.Empty:
            if frame.FAR == self.FarList[-1]:
                print("FAR = {0:08x} already registered (pad frame)".format(frame.FAR))
                return
        self.FarList.append(frame.FAR)
        self.Frames[frame.FAR] = frame
        self.Empty = False

    def get_frame_by_FAR(self, FAR):
        return self.Frames[FAR]

    def get_frame_by_index(self, index):
        FAR = self.FarList[index]
        return self.Frames[FAR]

    def update_stat(self):
        self.stat = BitstreamStatistics()
        for frame in self.Frames.values():
            frame.update_stat()
            if not frame.stat.Empty:
                self.stat.UtilizedFrames += 1
            if frame.stat.Type == 0:
                self.stat.Type0Frames += 1
            elif frame.stat.Type == 1:
                self.stat.Type1Frames += 1
            self.stat.EssentialBitsCount += frame.stat.EssentialBitsCount

    def to_string(self):
        res = '\nCM Fragment ID = {0:08x}:\n{1:30s}: {2:8d}\n{3:30s}: {4:8d}\n{5:30s}: {6:8d}\n{7:30s}: {8:8d}\n{9:30s}: {10:8d}\n{11:30s}: {12:s}'.format(
            self.SLR_ID,
            "    Fragment  Frames", len(self.FarList),
            "        Type-0", self.stat.Type0Frames,
            "        Type-1", self.stat.Type1Frames,
            "    Utilized Frames", self.stat.UtilizedFrames,
            "    Essential bits", self.stat.EssentialBitsCount,
            "    Layout", self.layout.to_string())
        return res

    def get_frames_of_column(self, column_FAR):
        res = []
        idx = self.FarList.index(column_FAR)
        if idx >= 0:
            first = FarFields.from_FAR(column_FAR, self.Series)
            current = first
            while (first.BlockType == current.BlockType) and (first.Top == current.Top) and (first.Row == current.Row) and (first.Major == current.Major):
                res.append(self.get_frame_by_index(idx))
                idx += 1
                current = FarFields.from_FAR(self.FarList[idx], self.Series)
        return res


class DevicePartDetails:
    def __init__(self, name=''):
        self.series = None      #S7, US, USP
        self.family = ''        #virtex, kintex, spartan, artix
        self.size = ''          #e.g. 485 (thousands of cells)
        self.package = ''       #e.g. flga2104
        self.speed_grade = ''   #e.g. -2e
        if name != '':
            self.parse(name)

    def parse(self, name):
        s7_devices = {'7s':'spartan', '7a':'artix', '7k':'kintex', '7vx':'virtex', '7vh':'virtex-hpc', '7z':'zynq'}
        us_devices = {'vu':'virtex', 'ku':'kintex', 'ka':'artix'}
        ptn = 'xc({0:s})([0-9]+)(p|t)?\-?([a-z0-9]+)(\-[a-z0-9])?'.format('|'.join(s7_devices.keys() + us_devices.keys()))
        match = re.match(ptn, name)
        if match:
            if match.group(1) in s7_devices.keys():
                self.series = FPGASeries.S7
                self.family = s7_devices[match.group(1)]
            elif match.group(1) in us_devices.keys():
                if match.group(3) == 'p':
                    self.series = FPGASeries.USP
                else:
                    self.series = FPGASeries.US
                self.family = us_devices[match.group(1)]
            self.size = match.group(2)
            self.package = match.group(4)
            self.speed_grade = 'not specified' if (len(match.groups())<5 or match.group(5) is None) else match.group(5)

    def to_string(self):
        return 'Device Part Details: Series={0:s}, family={1:s}, size = {2:s}, package={3:s}, speed grade={4:s}'.format(
            FPGASeries.to_string(self.series), self.family, self.size, self.package, self.speed_grade)


class ConfigMemory:
    def __init__(self, series = FPGASeries.S7):
        self.set_series(series)
        self.DevicePart = ""
        self.VivadoVersion = ""
        self.BitstreamFile = ""
        self.SLR_ID_LIST = []
        self.FragmentDict = dict()
        self.moduledir = DAVOSPATH #os.path.dirname(os.path.realpath(__file__))
        self.DeviceDetails = DevicePartDetails()
        print('Config Memory Model instantiated from: {0}'.format(self.moduledir))

    def set_series(self, series):
        self.Series = series
        self.FrameSize = FrameSizeDict[self.Series]

    def get_frame_by_FAR(self, FAR, chip_id=None):
        if chip_id is not None:
            fragment = self.FragmentDict[chip_id]
        else:
            fragment = self.FragmentDict.values()[0]
        return fragment.get_frame_by_FAR(FAR)

    def put_frame(self, frame):
        if frame.SLR_ID not in self.FragmentDict.keys():
            fragment = SuperLogicRegion(frame.SLR_ID, self.Series)
            self.FragmentDict[frame.SLR_ID] = fragment
        else:
            fragment = self.FragmentDict[frame.SLR_ID]
        fragment.put_frame(frame)

    def update_stat(self):
        for fragment in self.FragmentDict.values():
            fragment.update_stat()

    def get_frames_of_column(self, slr_idx, column_FAR):
        fragment = self.FragmentDict[self.SLR_ID_LIST[slr_idx]]
        return fragment.get_frames_of_column(column_FAR)

    def load_bitstream(self, fname, filetype=BitfileType.Regular):
        self.BitstreamFile = fname
        FrameSize = FrameSizeDict[self.Series]
        res = []
        if fname.endswith('.bin'):
            specificator = '<I'
        elif fname.endswith('.bit'):
            specificator = '>I'
        else:
            raw_input('bitstream_to_FrameList: Unknown file format')
            return (None)
        header = []
        bus_width_detect = 0x0
        with open(fname, 'rb') as f:
            while bus_width_detect != 0x000000BB11220044:
                data = f.read(1)
                header.append(struct.unpack('>c', data)[0])
                bus_width_detect = ((bus_width_detect << 8) | struct.unpack('>B', data)[0] & 0xFF) & 0xFFFFFFFFFFFFFFFF
            matchDesc = re.search("Version=([0-9]+.*?[0-9]+.*?[a-zA-Z]+).*?([0-9a-zA-Z\\-]+)", ''.join(header))
            if matchDesc:
                self.VivadoVersion = matchDesc.group(1)
                self.DevicePart = matchDesc.group(2)
                if not self.DevicePart.startswith('xc'):
                    self.DevicePart = 'xc'+self.DevicePart
                self.DeviceDetails = DevicePartDetails(self.DevicePart)
                print 'Parse bitstream: device part detected: {0:s}'.format(self.DeviceDetails.to_string())
                self.set_series(self.DeviceDetails.series)
            else:
                print "load_bitstream: device part is not found in the bitstream header"
            bitstream = [0x000000BB, 0x11220044]
            data = f.read()
            for i in range(0, len(data), 4):
                bitstream.append(struct.unpack(specificator, data[i:i+4])[0])

        # In a debug bitstream data are written frame by frame with CRC check after each frame
        if filetype == BitfileType.Debug:
            i=0
            while i < len(bitstream)-5:
                #bus width detect, followed by two pad words, and one sync word
                if [ bitstream[i], bitstream[i+1], bitstream[i+2], bitstream[i+3], bitstream[i+4] ] == [0x000000BB, 0x11220044, 0xFFFFFFFF, 0xFFFFFFFF, 0xAA995566] :
                    #extract Device_ID from ICcode register
                    while(bitstream[i] != 0x30018001): i += 1
                    IDcode = bitstream[i+1]
                    self.SLR_ID_LIST.append(IDcode)

                #FDRI register: word count = FrameSize (101 or 123 or 93)
                if bitstream[i] == (0x30004000 | self.FrameSize):
                    #CRC check goes after the frame data
                    if bitstream[i+self.FrameSize+1] == 0x30002001 and bitstream[i+self.FrameSize+3]==0x30000001:
                        #extract FAR and data for the located data frame
                        FAR = bitstream[i+self.FrameSize+2]
                        frame = FrameDesc(FAR, self.Series, IDcode)
                        frame.data = bitstream[i+1:i+self.FrameSize+1]
                        #frame.update_stat()
                        self.put_frame(frame)
                        i += (self.FrameSize+4)
                    else:
                        i += 1
                else:
                    i += 1
            #export FAR List
            farlistfile = os.path.join(self.moduledir, 'FFI/DeviceSupport/FARLIST_{0}.txt'.format(self.DevicePart))
            with open(farlistfile, 'w') as f:
                for id in self.SLR_ID_LIST:
                    for far in self.FragmentDict[id].FarList:
                        f.write('0x{0:08x} 0x{1:08x}\n'.format(id, far))

        #In a regular bitstream data are written as one big packet
        elif filetype == BitfileType.Regular:
            os.chdir(os.path.join(self.moduledir, 'FFI/DeviceSupport'))
            farlistfile = glob.glob('FARLIST*{0:s}*.txt'.format(self.DevicePart))
            if len(farlistfile) > 0:
                print('Using cached FarList: {0:s}'.format(farlistfile[0]))
                with open(farlistfile[0],'r') as f:
                    for line in f:
                        t = line.split(' ')
                        SLR_ID = int(t[0], 16)
                        FAR = int(t[1], 16)
                        if SLR_ID not in self.FragmentDict.keys():
                            fragment = SuperLogicRegion(SLR_ID, self.Series)
                            self.FragmentDict[SLR_ID] = fragment
                            self.SLR_ID_LIST.append(SLR_ID)
                        else:
                            fragment = self.FragmentDict[SLR_ID]
                        fragment.FarList.append(FAR)

            else:
                print('load_bitstream: FAR list file not found for device part: {0}'.format(self.DevicePart))
                print('Device layout can be added to DAVOS by running: python DesignParser.py op=addlayout part={0:s}'.format(
                        self.DevicePart))
                return
            i, FrameIndex, fragment = 0, 0, None
            fragment_found = False
            while i < len(bitstream)-5:
                if [ bitstream[i], bitstream[i+1], bitstream[i+2], bitstream[i+3], bitstream[i+4] ] == [0x000000BB, 0x11220044, 0xFFFFFFFF, 0xFFFFFFFF, 0xAA995566] :
                    #extract Device_ID from ICcode register
                    while(bitstream[i] != 0x30018001): i += 1
                    IDcode = bitstream[i+1]
                    fragment = self.FragmentDict[IDcode]
                    FrameIndex = 0
                    fragment_found = True

                # Find command: write FAR register
                if fragment_found and bitstream[i] == 0x30002001:  # write FAR register 1 word
                    i += 1
                    FAR = bitstream[i]
                    while FrameIndex < len(fragment.FarList) and fragment.FarList[FrameIndex] != FAR:
                        FrameIndex += 1
                    # look ahead: Command register --> WCFG command (write config data)
                    while i < len(bitstream) and not (bitstream[i] == 0x30008001 and bitstream[i+1] == 0x00000001) :
                        i += 1
                    # look ahead: FDRI register
                    while i < len(bitstream) and (bitstream[i] & 0xFFFFF800 != 0x30004000):
                        i += 1
                    if i >= len(bitstream): break
                    WordCount = bitstream[i] & 0x7FF
                    if WordCount == 0:
                        # big data packet: WordCount in following Type2Packet
                        i += 1
                        WordCount = bitstream[i] & 0x7FFFFFF
                    i += 1
                    FrameCnt = 0
                    PadIndex = 0
                    while FrameCnt < (WordCount / self.FrameSize):
                        if FrameIndex + FrameCnt - PadIndex < len(fragment.FarList):
                            FAR = fragment.FarList[FrameIndex + FrameCnt - PadIndex]
                            frame = FrameDesc(FAR, self.Series, IDcode)
                            frame.data = bitstream[i:i + self.FrameSize]
                            fragment.Frames[frame.FAR] = frame
                        else:
                            print("load_bitstream: Skipping extra (pad) frames idx: {0:d}".format(FrameIndex+FrameCnt-PadIndex))
                            fragment_found = False
                        i += self.FrameSize
                        FrameCnt += 1
                        if FrameIndex+FrameCnt-PadIndex < len(fragment.FarList)-1:
                            f1 = FarFields.from_FAR(fragment.FarList[FrameIndex+FrameCnt-PadIndex], self.Series)
                            f2 = FarFields.from_FAR(fragment.FarList[FrameIndex+FrameCnt-PadIndex+1], self.Series)
                            if (f1.Row != f2.Row) or (f1.Top != f2.Top):
                                PadIndex += 2
                                FrameCnt += 2
                                i += self.FrameSize * 2
                    FrameIndex += (FrameCnt - PadIndex)
                    fragment_found = False
                else:
                    i += 1
        self.update_stat()
        for id in self.SLR_ID_LIST:
            fragment = self.FragmentDict[id]
            for far in range(len(fragment.FarList)):
                f = FarFields.from_FAR(fragment.FarList[far], self.Series)
                if (f.Top == 0) and (f.Row >= fragment.layout.TopRows):
                    fragment.layout.TopRows = f.Row+1
                elif (f.Top == 1) and (f.Row >= fragment.layout.BottomRows):
                    fragment.layout.BottomRows = f.Row + 1
                if f.Major >= fragment.layout.Columns:
                    fragment.layout.Columns = f.Major + 1
                if self.Series == FPGASeries.S7:
                    fragment.layout.RowHeight = 50
                elif self.Series == FPGASeries.US or self.Series == FPGASeries.USP:
                    fragment.layout.RowHeight = 60
                
            for i in range(len(fragment.FarList)-1):
                x1, x2 = FarFields.from_FAR(fragment.FarList[i], self.Series), FarFields.from_FAR(fragment.FarList[i+1], self.Series)
                if x1.Major != x2.Major:
                    desc = ConfColumnDescriptor(id, x1.BlockType, x1.Top, x1.Row, x1.Major, x1.Minor+1, 'UNKNOWN')
                    if self.Series == FPGASeries.USP:
                        if desc.FrameNum == 76:
                            desc.Type = "SW"
                        elif desc.FrameNum == 16:
                            desc.Type = "CLB"
                        elif desc.FrameNum == 6:
                            desc.Type = "BRAMTYPE0"
                        #elif desc.FrameNum == 8:
                        #    desc.Type = "DSP"
                    elif self.Series == FPGASeries.S7:
                        if desc.FrameNum == 36:
                            desc.Type = "CLB"
                    fragment.layout.ColumnDescriptors.append(desc)
                    if desc.Top == 0 and desc.Row == 0:
                        fragment.layout.TileColumnIndexes[desc.Type].append(desc.Column)
        print('Bitstream parsed: {0:s}\n\tVivado Version: {1:s}\n\tDevice part: {2:s}'.format(
            self.BitstreamFile, self.VivadoVersion, self.DevicePart))


    def load_essential_bits(self, filename, file_type, slr_id):
        if slr_id not in self.FragmentDict.keys():
            print("load_essential_bits: invalid slr_id: {0:08x}".format(slr_id))
            return
        fragment = self.FragmentDict[slr_id]
        header_parsed = False
        words = []
        with open(filename, 'r') as f:
            for line in f:
                if not header_parsed:
                    buf = re.findall("Part:\s*?([0-9a-zA-Z\\-]+)", line)
                    if len(buf) > 0:
                        self.DevicePart = buf[0]
                        continue
                    buf = re.findall("Bits:\s*?([0-9]+)", line)
                    if len(buf) > 0:
                        wordnum = int(buf[0]) / 32
                        header_parsed = True
                        continue
                else:
                    words.append(int(line, 2))
        if self.Series == FPGASeries.S7:
            w = self.FrameSize
        elif self.Series == FPGASeries.USP:
            w = self.FrameSize+25
        for frame_id in range(fragment.stat.Type0Frames):
            frame = fragment.get_frame_by_index(frame_id)
            if file_type == FileTypes.EBC:
                frame.ebc_data = words[w:w+self.FrameSize]
            elif file_type == FileTypes.EBD:
                frame.mask = words[w:w+self.FrameSize]
            w += self.FrameSize
            #skip pad frame between clock rows
            next_frame = fragment.get_frame_by_index(frame_id+1)
            if (frame.coord.Row != next_frame.coord.Row) or (frame.coord.Top != next_frame.coord.Top):
                w += self.FrameSize * 2
        print('Essential bits loaded: {0:s} into SLR: {1:08x}'.format(filename, slr_id))        


    def print_stat(self):
        print('Bitstream statistics:')
        for id in self.SLR_ID_LIST:
            fragment = self.FragmentDict[id]
            fragment.update_stat()
            print(fragment.to_string())


    def log(self, fname, skipEmptyFrames, log_data, log_mask, log_word_indexes):
        with open(fname, 'w') as f:
            f.write('CM_LAYOUT:\n')
            for chip_id, fragment in self.FragmentDict.iteritems():
                f.write('\nFragment {0:s} : \n{1:s}'.format(str(chip_id), fragment.layout.to_string(False)))
            f.write('\n\n\nCM_CONTENT:\n')
            for chip_id, fragment in self.FragmentDict.iteritems():
                for i in fragment.FarList:
                    frame = fragment.Frames[i]
                    if (not skipEmptyFrames) or (not frame.stat.Empty):
                        f.write(frame.to_string(log_data, log_mask, log_word_indexes)+'\n')
        print('CM logged into: {0:s}'.format(fname))









class CLB_LUTS:
    EA, EB, EC, ED, OA, OB, OC, OD  = range(8)

    @staticmethod
    def from_coord(Xcoord, ABCD):
        if Xcoord%2 == 0:
            res = CLB_LUTS.EA if ABCD=='A' else CLB_LUTS.EB if ABCD=='B' else CLB_LUTS.EC if ABCD=='C' else CLB_LUTS.ED
        else:
            res = CLB_LUTS.OA if ABCD=='A' else CLB_LUTS.OB if ABCD=='B' else CLB_LUTS.OC if ABCD=='C' else CLB_LUTS.OD
        return(res)




def get_index_of_1(data):
    for i in range(64):
        if (data >> i) & 0x1 == 1:
            return(i) 
    return(-1) 

def get_bitindex(num, val):
    for i in range(64):
        if (num>>i)&0x1 == val:
            return(i)













    
    
def ExtractLUT_INIT(SwBox_top, SwBox_row, SwBox_major, SwBox_minor, LUTCOORD, BIN_FrameList):
    for i in range(len(BIN_FrameList)):
        f = BIN_FrameList[i]
        if f.BlockType == 0 and f.Top == SwBox_top and f.Row == SwBox_row and f.Major == SwBox_major:
            if LUTCOORD in [CLB_LUTS.OA, CLB_LUTS.OB, CLB_LUTS.OC, CLB_LUTS.OD]:
                F1, F2, F3, F4 = BIN_FrameList[i+26], BIN_FrameList[i+27], BIN_FrameList[i+28], BIN_FrameList[i+29], 
            else:
                F1, F2, F3, F4 = BIN_FrameList[i+32], BIN_FrameList[i+33], BIN_FrameList[i+34], BIN_FrameList[i+35], 
            offset = SwBox_minor*2
            if offset >= 50: offset+=1
            #print('{}\n\n{}\n\n{}\n\n{}'.format(F1.to_string(2), F2.to_string(2), F3.to_string(2), F4.to_string(2)))
            if LUTCOORD in [CLB_LUTS.OA, CLB_LUTS.EA]:
                W1, W2, W3, W4 = F1.data[offset] & 0xFFFF, F2.data[offset] & 0xFFFF, F3.data[offset] & 0xFFFF, F4.data[offset] & 0xFFFF
            elif LUTCOORD in [CLB_LUTS.OB, CLB_LUTS.EB]:
                W1, W2, W3, W4 = (F1.data[offset] & 0xFFFF0000)>>16, (F2.data[offset] & 0xFFFF0000)>>16, (F3.data[offset] & 0xFFFF0000)>>16, (F4.data[offset] & 0xFFFF0000)>>16
            elif LUTCOORD in [CLB_LUTS.OC, CLB_LUTS.EC]:
                W1, W2, W3, W4 = F1.data[offset+1] & 0xFFFF, F2.data[offset+1] & 0xFFFF, F3.data[offset+1] & 0xFFFF, F4.data[offset+1] & 0xFFFF
            elif LUTCOORD in [CLB_LUTS.OD, CLB_LUTS.ED]:
                W1, W2, W3, W4 = (F1.data[offset+1] & 0xFFFF0000)>>16, (F2.data[offset+1] & 0xFFFF0000)>>16, (F3.data[offset+1] & 0xFFFF0000)>>16, (F4.data[offset+1] & 0xFFFF0000)>>16
            #INIT = (W4 << 48) | (W3 << 32) | (W2 << 16) | W1
            INIT = (W1<<48)|(W2<<32)|(W3<<16)|W4
            return(INIT)
            
                

def SetCustomLutMask(SwBox_top, SwBox_row, SwBox_major, SwBox_minor, LUTCOORD, BIN_FrameList, lutmap, skip_mask=False, series = FPGASeries.S7):
    FrameSize = FrameSizeDict[series]
    for i in range(len(BIN_FrameList)):
        f = BIN_FrameList[i]
        if f.BlockType == 0 and f.Top == SwBox_top and f.Row == SwBox_row and f.Major == SwBox_major:
            if LUTCOORD in [CLB_LUTS.OA, CLB_LUTS.OB, CLB_LUTS.OC, CLB_LUTS.OD]:
                F = [BIN_FrameList[i+26+k] for k in range(4)] 
            else:
                F = [BIN_FrameList[i+32+k] for k in range(4)] 
            offset = SwBox_minor*2
            if offset >= 50: offset+=1  #word 50 is reserved for clk configuration
            if LUTCOORD in [CLB_LUTS.OC, CLB_LUTS.EC, CLB_LUTS.OD, CLB_LUTS.ED]: offset += 1
            (Rshift, bitmask) = (0, 0xFFFF) if LUTCOORD in [CLB_LUTS.OA, CLB_LUTS.EA, CLB_LUTS.OC, CLB_LUTS.EC] else (16, 0xFFFF0000)
            INIT = (((F[0].data[offset] & bitmask) >> Rshift) << 48) | (((F[1].data[offset] & bitmask) >> Rshift) << 32) | (((F[2].data[offset] & bitmask) >> Rshift) << 16) | ((F[3].data[offset] & bitmask) >> Rshift)
            for frame in F: 
                if frame.custom_mask == []: frame.custom_mask = [0x00000000]*FrameSize
            globalmap=[]
            for item in lutmap:
                x=[]
                for i in item:
                    #essential bits mask
                    quarter = i/16
                    bit_index = i%16 if LUTCOORD in[CLB_LUTS.OA, CLB_LUTS.EA, CLB_LUTS.OC, CLB_LUTS.EC] else (i%16) + 16 
                    if not skip_mask: 
                        F[3-quarter].custom_mask[offset] |= (0x1 << bit_index)
                    #global mapping
                    x.append((F[3-quarter].GetFar(), offset, bit_index))
                globalmap.append(x)
            return(INIT, globalmap)     



def get_lut_to_bel_map(cellType, BelEquation):
    inputnum = int(re.findall('LUT([0-9]+)', cellType)[0])
    for i in range(10): BelEquation = BelEquation.replace('A{0:d}+~A{0:d}'.format(i),'')
    for term in BelEquation.split('+'):
        vardict = OrderedDict.fromkeys(re.findall('(A[0-9]+)', term))
        if len(vardict) == inputnum:
            return( OrderedDict(zip(['I{0:d}'.format(i) for i in range(inputnum)], vardict.keys())) )







def LutListToTable(LutList, expand = False, no_duplicate_sim_cases = False):
    labels = ['name', 'celltype','cellloc','abcd' ,'beltype','clkrow','tileloc','init', 'connections', 'lutindex', 'combcell', 'bitsequence', 'bit_i', 'match', 'cbelinputs', 'Label', 'Actime', 'SwitchCount',  'FailureModeEmul', 'FailureModeSim', 'Emul_vs_Sim', 'globalmap']
    if not expand:
        res = Table('Luts')
        res.add_column('simnode', [(LutList[i]['node_main'].name if (('node_main' in LutList[i]) and  LutList[i]['node_main']!=None) else LutList[i]['simnode'] if 'simnode' in LutList[i] else '') for i in range(len(LutList))])
        for lbl in labels:
            res.add_column(lbl, map(str, [LutList[i][lbl] if lbl in LutList[i] else '' for i in range(len(LutList))]))
    else:
        res = Table('Luts', ['simnode', 'InitReg_bit'] + labels)
        for lut in LutList:
            #print('\n\n>> {0} \n{1}'.format(str(lut['Actime']), str(lut['FailureModeEmul'])))
            for i in range(len(lut['FailureModeEmul'])):
                if len(lut['FailureModeEmul'][i]) > 0:
                    for j in range(len(lut['FailureModeEmul'][i])) if not no_duplicate_sim_cases else range(1):
                        res.add_row(map(str, [lut['simnode'], str(i), lut['name'], lut['celltype'], lut['cellloc'], lut['abcd'], lut['beltype'], lut['clkrow'], lut['tileloc'], lut['init'], lut['connections'], lut['lutindex'], lut['combcell'], 
                                              lut['bitsequence'][i] if type(lut['bitsequence'][i] != list) else lut['bitsequence'][i][j], 
                                              lut['bit_i'], lut['match'], lut['cbelinputs'], lut['Label'], 
                                              '' if len(lut['Actime'])==0 else lut['Actime'][i][0] if (j >= len(lut['Actime'][i])) else lut['Actime'][i][j],
                                              '' if len(lut['SwitchCount'])==0 else lut['SwitchCount'][i][0] if (j >= len(lut['SwitchCount'][i])) else lut['SwitchCount'][i][j],
                                              lut['FailureModeEmul'][i][j], 
                                              lut['FailureModeSim'][i] if len(lut['FailureModeSim'])>0 else -1,
                                              lut['Emul_vs_Sim'][i] if 'Emul_vs_Sim' in lut else '',
                                              lut['globalmap'][i][j]
                                     ]))
    return(res)


def TableToLutList(LutDescTab):
    res = []
    for i in range(LutDescTab.rownum()):
        item = dict()
        for lbl in ['simnode', 'name', 'celltype', 'abcd', 'beltype', 'init', 'bit_i', 'match', 'combcell', 'Label']:
                item[lbl] = LutDescTab.getByLabel(lbl, i)
        for lbl in ['clkrow', 'lutindex']:
            item[lbl] = int(LutDescTab.getByLabel(lbl, i))
        for lbl in ['cellloc', 'tileloc', 'connections',  'bitsequence', 'cbelinputs', 'globalmap', 'Actime', 'SwitchCount', 'FailureModeEmul']:
            if lbl in LutDescTab.labels:
                item[lbl] = ast.literal_eval(LutDescTab.getByLabel(lbl, i))
        item['FailureModeSim'] = ast.literal_eval(LutDescTab.getByLabel('FailureModeSim', i)) if 'FailureModeSim' in LutDescTab.labels else []
        item['Emul_vs_Sim'] = ast.literal_eval(LutDescTab.getByLabel('Emul_vs_Sim', i)) if 'Emul_vs_Sim' in LutDescTab.labels and LutDescTab.getByLabel('Emul_vs_Sim', i) != '' else []

        res.append(item)
    return(res)

        

def MapLutToBitstream(LutDescTab, BIN_FrameList, DutScope=''):
    LutCells = VivadoParseTableToLutList(LutDescTab)
    for i in range(len(LutCells)):
        if LutCells[i]['combcell']==None:
            for j in range(i+1, len(LutCells)):
                if LutCells[i]['cellloc'] == LutCells[j]['cellloc'] and LutCells[i]['abcd'] == LutCells[j]['abcd']:
                    LutCells[i]['combcell'] = LutCells[j]
                    #LutCells[i]['cbelinputs'] = list( set(LutCells[j]['connections'].values()) - set(LutCells[i]['connections'].values()) )
                    LutCells[i]['cbelinputs'] = [LutCells[j]['connections'][x] for x in sorted([y for y in LutCells[j]['connections'].keys() if LutCells[j]['connections'][y] in list( set(LutCells[j]['connections'].values()) - set(LutCells[i]['connections'].values()) )], reverse=False)]
                    LutCells[j]['combcell'] = LutCells[i]
                    #LutCells[j]['cbelinputs'] = list( set(LutCells[i]['connections'].values()) - set(LutCells[j]['connections'].values()) )
                    LutCells[j]['cbelinputs'] = [LutCells[i]['connections'][x] for x in sorted([y for y in LutCells[i]['connections'].keys() if LutCells[i]['connections'][y] in list( set(LutCells[i]['connections'].values()) - set(LutCells[j]['connections'].values()) )], reverse=False)]
                    break

    #Bitstream mapping for complete 6-input LUT
    vars = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
    T_L = Table('LUT_L', vars)
    for i in range(2**len(vars)):
        T_L.add_row( [(i>>j)&0x1 for j in range(len(vars))] )
    T_L.add_column('Bit', map_L)
    T_M = Table('LUT_M', vars)
    for i in range(2**len(vars)):
        T_M.add_row( [(i>>j)&0x1 for j in range(len(vars))] )
    T_M.add_column('Bit', map_M)


    for node in LutCells:
        if   node['beltype'] in ['LUT5','LUT6']:                Map = copy.deepcopy(T_L)
        elif node['beltype'] in ['LUT_OR_MEM5','LUT_OR_MEM6']:  Map = copy.deepcopy(T_M)
        #1. MAP LUT INIT (functional) to BEL INIT
        #filter-out unused inputs (and LUT rows)
        for v in vars:
            if not v in node['connections'].values() + node['cbelinputs'] + ['Bit']:
                if node['beltype'][-1]=='6' and v == 'A6' and node['combcell'] != None:
                    Map.filter(v, 0)
                elif node['beltype'][-1]=='5' and v == 'A6':
                    Map.filter(v, 1)
                else:
                    Map.filter(v, 0)
        res = []
        #reorder columns according to connections of logical LUT
        sequence = [node['connections'][key] for key in sorted(node['connections'].keys(), reverse=False)] + node['cbelinputs']
        Map.reorder_columns(sequence + ['Bit'])
        for i in range(2**len(node['connections'])):
            r = [(i>>j)&0x1 for j in range(len(node['connections']))]
            if len(node['cbelinputs'])==0:
                rows = Map.search_rows(r,0)
                res.append(  [val[-1] for val in rows ] )    
            else:
                z = []
                for k in range(2**len(node['cbelinputs'])):
                    x = [(k>>j)&0x1 for j in range(len(node['cbelinputs']))]
                    rows = Map.search_rows(r+x,0)
                    z.append(rows[0][-1])
                res.append(  z )    

        node['bitsequence'] = ','.join(map(str, res))

        #2. GET LUT BEL content from bitstream
        skip_mask = False if DutScope in ['', '/'] else (not node['name'].startswith(DutScope))
        #if not skip_mask: print('Selected LUT cell: scope {} : {}'.format(DutScope, node['name'].replace(DutScope, '')))
        BITSTREAM, node['globalmap'] = SetCustomLutMask(node['top'], node['row'], node['major'], node['minor'], node['lutindex'], BIN_FrameList, res, skip_mask)
        BIT_INIT = 0x0000000000000000
        w = 2**len(node['connections'])
        try:
            for bit in range(w): 
                BIT_INIT = BIT_INIT | (((BITSTREAM>>res[bit][0])&0x1)<<bit)
        except:
            pass
        node['bit_i'] =  '{bits}\'h{num:0{width}X}'.format(bits=w,num=BIT_INIT, width=w/4)
        node['match'] = 'Y' if node['init'] == node['bit_i'] else 'N'

    return(LutCells)









if __name__ == "__main__":

    proj_path = 'C:/Projects/Profiling/Models/MC8051_ZC/'
    Tab = Table('LutMapList')
    Tab.build_from_csv(os.path.join(proj_path, 'LutMapList.csv'))
    TableToLutList(Tab)
    verbosity = 1
    logfile = open(os.path.join(proj_path, 'parselog.txt'),'w')
    LUTMAP_FILE = os.path.join(proj_path,'LUTMAP.csv')
    FARARRAY_FILE = os.path.join(proj_path,'FarArray.txt')
    BITSTREAM_FILE = os.path.join(proj_path,'Bitstream.bin')
    Input_EBCFile = os.path.join(proj_path,'Bitstream.ebc')
    Input_EBDFile = os.path.join(proj_path,'Bitstream.ebd')

    CellDescTab = Table('LutMap')
    CellDescTab.build_from_csv(LUTMAP_FILE)

    FarList = LoadFarList(FARARRAY_FILE)
    EBC_FrameList = EBC_to_FrameList(Input_EBCFile, Input_EBDFile, FarList)
    BIN_FrameList = parse_bitstream(BITSTREAM_FILE, FarList)

    mismatches = 0
    for i in range(len(EBC_FrameList)):
        for k in range(FrameSizeDict[FPGASeries.S7]):
            if EBC_FrameList[i].data[k] != BIN_FrameList[i].data[k]:
                if self.verbosity > 0:
                    logfile.write('Check EBC vs BIT: mismatch at Frame[{0:08x}]: Block={1:5d}, Top={2:5d}, Row={3:5d}, Major={4:5d}, Minor={5:5d}\n'.format(BIN_FrameList[i].GetFar(), BIN_FrameList[i].BlockType, BIN_FrameList[i].Top, BIN_FrameList[i].Row, self.Major, BIN_FrameList[i].Minor))
                mismatches+=1
    if mismatches == 0: logfile.write('\nCheck EBC vs BIT: Complete Match\n')
    else: logfile.write('Check EBC vs BIT: Mismatches Count = {0:d}\n'.format(mismatches))
    if mismatches ==0:
        for i in range(len(EBC_FrameList)):
            BIN_FrameList[i].mask = EBC_FrameList[i].mask
            BIN_FrameList[i].UpdateFlags()

    LutMapList = MapLutToBitstream(CellDescTab, BIN_FrameList)

    with open(os.path.join(proj_path, 'ResT.csv'),'w') as f:
        f.write(LutListToTable(LutMapList).to_csv())

    #log non-empty frames
    with open(os.path.join(proj_path,'BitLog.txt'),'w') as f:
        for i in BIN_FrameList:
            if i.flags & 0x1 > 0:
                f.write(i.to_string(2)+'\n\n')


    logfile.close()


