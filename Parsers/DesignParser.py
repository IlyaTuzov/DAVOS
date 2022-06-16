# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A datamodel that provides a bit-accurate mapping
#       between the design netlist, FPGA floorplan, and the bitstream
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------


import subprocess
import os
import sys
import re
import shutil
import glob
import xml.etree.ElementTree as ET
from BitstreamParser import *
from NetlistModel import *
DAVOSPATH = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
sys.path.insert(1, DAVOSPATH)
import Davos_Generic
import pickle


class VivadoDesignModel:
    def __init__(self, targetDir, DevicePart=None):
        self.targetDir = targetDir
        self.generatedFilesDir = os.path.normpath(os.path.join(self.targetDir, 'DavosGenerated'))
        if not os.path.exists(self.generatedFilesDir):
            os.makedirs(self.generatedFilesDir)
        self.VivadoProjectFile = (lambda l: l[0] if l is not None and len(l)>0 else '')(glob.glob(os.path.join(self.targetDir,'*.xpr')))
        if not os.path.exists(self.VivadoProjectFile):
            print "Warning: Vivado project file not found in: {0}".format(self.targetDir)
        self.ImplementationRun = '*'
        self.files = {
            'BIT' : [os.path.join(self.generatedFilesDir, 'Bitstream.bit')],
            'EBC' : [os.path.join(self.generatedFilesDir, 'Bitstream.ebc')],
            'EBD' : [os.path.join(self.generatedFilesDir, 'Bitstream.ebd')],
            'LL'  : [os.path.join(self.generatedFilesDir, 'Bitstream.ll')],
            'CELLS': [os.path.join(self.generatedFilesDir, 'CELLS.csv')]
        }
        if DevicePart is not None and DevicePart != "":
            self.DevicePart = DevicePart
        else:
            tree = ET.parse(self.VivadoProjectFile).getroot()
            vivado_config = tree.find('Configuration')
            for tag in vivado_config.findall('Option'):
                if tag.get("Name").lower() == "part":
                    self.DevicePart = tag.get("Val")
                    print("Extracted device part from the project file: {0} = {1}".format(self.VivadoProjectFile, self.DevicePart))
                    break

        details = DevicePartDetails(self.DevicePart)
        if details.series == None:
            print('Error: VivadoDesignModel: invalid DevicePart specified: {0}, exiting'.format(self.DevicePart))
            exit(0)
        self.series = details.series
        print(details.to_string())
        self.CM = ConfigMemory(self.series)
        self.netlist = Netlist()
        self.dev_layout = None





    @staticmethod
    def parse_fpga_layout(devicepart):
        support_scripts_path = os.path.join(DAVOSPATH, 'SupportScripts')
        workdir = os.path.join(DAVOSPATH, 'Parsers', 'DeviceSupport', 'tmp').replace("\\", '/')
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        shutil.copyfile(os.path.join(support_scripts_path, 'template.vhd'), os.path.join(workdir, 'template.vhd'))
        script = "vivado -nolog -nojournal -mode batch -source {0}/VivadoParseLayout.do -tclargs \"{1}\" \"{2}\" \"{3}\" \"{4}\" ".format(
            support_scripts_path, "*", devicepart, "*", workdir).replace("\\", "/")
        print 'Running: {0}'.format(script)
        with open(os.path.join(workdir, '_LayoutParser.log'), 'w') as logfile, \
                open(os.path.join(workdir, '_LayoutParser.err'), 'w') as errfile:
            proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=logfile, stderr=errfile, shell=True)
            proc.wait()
        if os.path.exists(os.path.join(workdir, 'LAYOUT.xml')):
            tree = ET.parse(os.path.join(workdir, 'LAYOUT.xml')).getroot()
            layout = DevLayout(tree)
            shutil.copyfile(os.path.join(workdir, 'LAYOUT.xml'),
                            os.path.join(DAVOSPATH, 'Parsers', 'DeviceSupport', 'LAYOUT_{0}.xml'.format(devicepart)))
        else:
            print 'parse_fpga_layout(): layout not found: {0}'.format(os.path.join(workdir, 'LAYOUT.xml'))
            return
        bitfile = os.path.join(workdir, '{0}.bit'.format(devicepart))
        if os.path.exists(bitfile):
            CM = ConfigMemory()
            CM.load_bitstream(bitfile, BitfileType.Debug)
        else:
            print 'parse_fpga_layout(): bitfile not found: {0}'.format(bitfile)
            return
        shutil.rmtree(workdir)
        print 'Layout parsed for FPGA part: {0}'.format(devicepart)

    @staticmethod
    def get_parts(tag='LAYOUT'):
        devsupport_dir = os.path.join(DAVOSPATH, 'Parsers', 'DeviceSupport')
        res = []
        for i in glob.glob('{0:s}/{1:s}*'.format(devsupport_dir, tag)):
            r = re.findall(r'\_([a-zA-Z0-9\-]+)\.', i)
            if len(r)>0:
                res.append(r[0])
        return res

    @staticmethod
    def get_matching_devices(ptn):
        res = []
        with open(os.path.join(DAVOSPATH, 'FFI', 'devicelist.txt'), 'r') as f:
            devicelist = f.read().splitlines()
        for i in devicelist:
            if ptn in i:
                res.append(i)
        return(res)

    def load_layout(self, devicepart):
        layoutfile = glob.glob('{0:s}/LAYOUT*{1:s}*.xml'.format(os.path.join(DAVOSPATH, 'Parsers', 'DeviceSupport'), devicepart))
        if len(layoutfile) == 0:
            print('Error: load_layout: device layout not found for device part: {0} in {1}'.format(devicepart, os.getcwd()))
            print('Device layout can be added to DAVOS by running: python DesignParser.py op=addlayout part={0:s}'.format(devicepart))
            exit(1)
        tree = ET.parse(os.path.join(os.getcwd(), layoutfile[0])).getroot()
        self.dev_layout = DevLayout(tree)

    def check_preconditions(self):
        res = True
        if not os.path.exists(self.files['EBD'][0]):
            fileset = sorted(glob.glob(os.path.join(self.generatedFilesDir, '*.ebd')))
            if len(fileset) > 0:
                self.files['EBD'] = fileset
            fileset = sorted(glob.glob(os.path.join(self.generatedFilesDir, '*.ebc')))
            if len(fileset) > 0:
                self.files['EBC'] = fileset
        for fileset in self.files.values():
            for fname in fileset:
                if not os.path.exists(fname):
                    res = False
                    console_message('check_preconditions: missing: {0:s}\n'.format(fname), ConsoleColors.Default)
                else:
                    console_message('check_preconditions: available: {0:s}\n'.format(fname), ConsoleColors.Default)
        return res

    def fix_preconditions(self):
        os.chdir(self.targetDir)
        while not self.check_preconditions():
            print('Running Vivado to obtain input files')
            parser_path = os.path.join(DAVOSPATH, 'SupportScripts', 'VivadoParseNetlist.do')
            script = "vivado -mode batch -source {0} -tclargs {1} \"{2}\" {3} {4} 1 1".format(
                parser_path, self.VivadoProjectFile, self.ImplementationRun, 'cells',
                self.generatedFilesDir).replace("\\", "/")
            with open(os.path.join(self.generatedFilesDir, '_NetlistParser.log'), 'w') as logfile, \
                    open(os.path.join(self.generatedFilesDir, '_NetlistParser.err'), 'w') as errfile:
                proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=logfile, stderr=errfile, shell=True)
                proc.wait()

    def getFarList_for_Pblock(self, X1, Y1, X2, Y2):
        res = []
        columns = set()
        for x in range(X1, X2+1):
            for y in range(Y1, Y2+1):
                slr, xl, yl = self.dev_layout.get_Tile_local_coordinates(x, y)
                cm_slr_id = self.CM.SLR_ID_LIST[slr.config_index]
                fragment = self.CM.FragmentDict[cm_slr_id]
                cr_y = yl/self.dev_layout.cr_height

                #in 7-series each column[x] maps to one major_frame[x]
                if self.series == FPGASeries.S7:
                    if yl >= fragment.layout.BottomRows * self.dev_layout.cr_height:
                        Top = 0
                        Row = cr_y - fragment.layout.BottomRows
                    else:
                        Top = 1
                        Row = fragment.layout.BottomRows-1-cr_y
                    FAR = FarFields(self.series, 0, Top, Row, x, 0).get_far()
                    columns.add((slr.config_index, FAR))

                #in ultrascale+ most columns are composed of 3 subcolumns:  LeftHandResource--Switchbox--RighhandResource
                #These columns map onto 3 consecutive major frames
                elif self.series == FPGASeries.USP:
                    Top = 0
                    Row = cr_y - fragment.layout.BottomRows
                    maj_frame = slr.fragment.layout.TileColumnIndexes['SW'][x]
                    #add major frame of the Switchbox column
                    columns.add((slr.config_index, FarFields(self.series, 0, Top, Row, maj_frame, 0).get_far() ))
                    #add major frame of the LeftHandResource column
                    if maj_frame-1 >= 0:
                        columns.add((slr.config_index, FarFields(self.series, 0, Top, Row, maj_frame-1, 0).get_far() ))
                    #add major frame of the RighhandResource column
                    if maj_frame+1 < slr.fragment.layout.Columns:
                        columns.add((slr.config_index, FarFields(self.series, 0, Top, Row, maj_frame+1, 0).get_far() ))
        for i in sorted(list(columns), key=lambda x: (x[0], x[1])):
            res += self.CM.get_frames_of_column(i[0], i[1])
        return res


    #tileX to localize column
    #tileY to localize slr, top, row, word offset
    #left_right = 0/1 for series7 to localize minor_frame_range (26--29 or 32--36)
    #           = -1/+1 for USP to localize major column (as offset from INT column)
    #label (A5/A6/B5/B6/C5/C6/D5/D6) to cut 64 bits fragment with LUT BEL content
    #result: SLR, and list (64 items) of tuples (FAR, word, bit)
    def get_lut_bel_fragment(self, tileX, tileY, left_right, label):
        slr, tileX_local, tileY_local = self.dev_layout.get_Tile_local_coordinates(tileX, tileY)
        cm_slr_id = self.CM.SLR_ID_LIST[slr.config_index]
        fragment = self.CM.FragmentDict[cm_slr_id]
        clkregionY_local = tileY_local / self.dev_layout.cr_height
        tileY_local = tileY_local % self.dev_layout.cr_height
        #For Series7
        if self.series == FPGASeries.S7:
            if clkregionY_local + 1 > slr.fragment.layout.BottomRows:
                Top, Row = 0, (clkregionY_local - slr.fragment.layout.BottomRows)
            else:
                Top, Row = 1, (slr.fragment.layout.BottomRows - clkregionY_local - 1)
            Column = tileX_local
            if left_right == 0:
                minor = [32, 33, 34, 35]
            else:
                minor = [26, 27, 28, 29]
            word = tileY_local*2
            #skip word 50 (reserved for frame CRC)
            if word >= 50:
                word += 1
            if label in ['A5', 'A6']:
                word, offset = word, 0
            elif label in ['B5', 'B6']:
                word, offset = word, 16
            elif label in ['C5', 'C6']:
                word, offset = word+1, 0
            elif label in ['D5', 'D6']:
                word, offset = word+1, 16
            else:
                print('get_lut_bel_fragment(): unknown bel label {0:s}'.format(label))
                return
            quarter = [[], [], [], []]
            for i in range(16):
                for j in range(4):
                    quarter[j].append((FarFields(self.series, 0, Top, Row, Column, minor[j]).get_far(), word, i+offset))
            coordlist = quarter[3] + quarter[2] + quarter[1] + quarter[0]
            res = {k: v for k, v in enumerate(coordlist)}
            return (slr, res)
        #For Ultrascale+
        elif self.series == FPGASeries.USP:
            Top = 0
            Row = clkregionY_local - fragment.layout.BottomRows
            Column = slr.fragment.layout.TileColumnIndexes['SW'][tileX] + left_right
            if label in ['C5', 'C6', 'D5', 'D6', 'F5', 'F6']:
                minor = [0, 1, 2, 3]
            elif label in ['B5', 'B6', 'E5', 'E6', 'G5', 'G6']:
                minor = [4, 5, 6, 7]
            elif label in ['A5', 'A6', 'H5', 'H6']:
                minor = [8, 9, 10, 11]
            else:
                print "Error in get_lut_bel_fragment(): unknown LUT label {0:s}".format(label)
                return
            word_base = 3*(tileY_local/2) + 3*(tileY_local/30)
            if label in ['A5', 'A6', 'B5', 'B6', 'C5', 'C6']:
                offset = 0 if (tileY_local % 2 == 0) else 48
            elif label in ['D5', 'D6', 'E5', 'E6']:
                offset = 16 if (tileY_local % 2 == 0) else 64
            elif label in ['F5', 'F6', 'G5', 'G6', 'H5', 'H6']:
                offset = 32 if (tileY_local % 2 == 0) else 80
            else:
                print "Error in get_lut_bel_fragment(): unknown LUT label {0:s}".format(label)
                return
            word = word_base + (offset / 32)
            assert word < 93, 'word index {0:d} exceeds Frame size (92 words)'.format(word)
            offset = offset % 32
            quarter = [[], [], [], []]
            for i in range(16):
                for j in range(4):
                    quarter[j].append((FarFields(self.series, 0, Top, Row, Column, minor[j]).get_far(), word, i+offset))
            coordlist = quarter[3] + quarter[2] + quarter[1] + quarter[0]
            res = {k: v for k, v in enumerate(coordlist)}
            return (slr, res)
        else:
            print 'get_lut_bel_fragment() : lut mapping is not supported for this FPGA series: {0:s}'.format(str(self.series))






    def map_lut_cells(self, unit_path="", pb=None):
        if self.series == FPGASeries.S7:
            for item in self.netlist.get_cells(NetlistCellGroups.LUT):
                item.slr, item.bitmap = self.get_lut_bel_fragment(item.slice.Tile.X,
                                                                  item.slice.Tile.Y,
                                                                  item.slice.X % 2,
                                                                  item.label)
        elif self.series == FPGASeries.USP:
            for item in self.netlist.get_cells(NetlistCellGroups.LUT):
                item.slr, item.bitmap = self.get_lut_bel_fragment(item.slice.Tile.X,
                                                                  item.slice.Tile.Y,
                                                                  item.slice.Tile.Offset,
                                                                  item.label)
        else:
            print 'map_luts() : lut mapping is not supported for this FPGA series: {0:s}'.format(str(self.series))
        print('Mapped LUTS in dut_scope = \"{0:s}\", pblock = {1:s}: {2:d}'.format(
            unit_path,
            pb.to_string() if pb is not None else "None",
            len(self.netlist.get_cells(NetlistCellGroups.LUT))))


    def map_lut_bels_from_layout(self, pb, reorder=False, skip_empty=False):
        res = []
        clb_slices = self.dev_layout.get_Slices_in_Pblock(pb)
        print 'CLB Slices in {0:s} : {1:d}'.format('FPGA' if pb is None else pb.to_string(), len(clb_slices))
        cnt = 0
        if self.series == FPGASeries.S7:
            labels = ['A6', 'B6', 'C6', 'D6']
        elif self.series == FPGASeries.USP:
            labels = ['A6', 'B6', 'C6', 'D6', 'E6', 'F6', 'G6', 'H6']
        else:
            print 'get_luts_from_layout(): lut mapping not defined for series {0:s}, exiting'.format(
                FPGASeries.to_string(self.series))
            return None
        for slice in clb_slices:
            for label in labels:
                lut = LutCellDescritor()
                lut.slice = slice
                if self.series == FPGASeries.S7:
                    left_right = slice.X % 2
                    lut.name = 'Tile_X{0:03d}Y{1:03d}:Slice_{2:s}:Label_{3:s}'.format(
                        slice.Tile.X, slice.Tile.Y, 'L' if left_right == 0 else 'R', label)
                elif self.series == FPGASeries.USP:
                    left_right = slice.Tile.Offset
                    lut.name = 'Tile_X{0:03d}Y{1:03d}:Slice_{2:s}:Label_{3:s}'.format(
                        slice.Tile.X, slice.Tile.Y, 'L' if left_right == -1 else 'R', label)
                lut.beltype = 'LUT_OR_MEM6' if slice.Type == 'SLICEM' else 'LUT6'
                lut.type = 'LUT6'
                lut.label = label
                slr, lut.bitmap = self.get_lut_bel_fragment(lut.slice.Tile.X, lut.slice.Tile.Y, left_right, label)
                lut_content = 0x0
                for bit_idx in range(63, -1, -1):
                    (far, word, bit) = lut.bitmap[bit_idx]
                    frame = self.CM.get_frame_by_FAR(far, slr.ID)
                    lut_content = (lut_content << 1) | ((frame.data[word] >> bit) & 0x1)
                if skip_empty and ((self.series == FPGASeries.S7 and lut_content == 0x0) or
                                   (self.series == FPGASeries.USP and lut_content == 0x0101000000000000)):
                    continue
                if reorder:
                    bitmap = map_M if lut.beltype == 'LUT_OR_MEM6' else map_L
                    for bit in range(64):
                        lut.init = lut.init | (((lut_content >> bitmap[bit]) & 0x1) << bit)
                else:
                    lut.init = lut_content
                res.append(lut)
            cnt += 1
            if cnt % 1000 == 0:
                console_message('Processed Slices ({0:3.1f}%): {1:s}'.format(100.0 * float(cnt) / len(clb_slices), slice.Name),
                                ConsoleColors.Green, True)
        return res

    def cells_to_table(self, celldesclist, labels):
        res = Table('Cells', ['Slice', 'Bel'] + labels)
        for cell in celldesclist:
            data = [str(cell.slice.Name), str(cell.label)]
            data += ['0x{0:016x}'.format(getattr(cell, item)) if item in ['init'] else str(getattr(cell, item))
                    for item in labels]
            res.add_row(data)
        return res

    def initialize(self, skip_files=False, unit_path="", pb=None, load_ll_file=True):
        if not skip_files:
            self.fix_preconditions()
            self.CM.set_series(self.series)
            self.load_layout(self.DevicePart)
            self.netlist.load_netlist_cells(self.files['CELLS'][0], self.dev_layout, unit_path, pb)
            if load_ll_file:
                self.netlist.load_logic_location_file(self.files['LL'][0], self.dev_layout, unit_path, pb, True)
            self.CM.load_bitstream(self.files['BIT'][0], BitfileType.Regular)
            for i in range(len(self.CM.SLR_ID_LIST)):
                self.CM.load_essential_bits(self.files['EBC'][i], FileTypes.EBC, self.CM.SLR_ID_LIST[i])
                self.CM.load_essential_bits(self.files['EBD'][i], FileTypes.EBD, self.CM.SLR_ID_LIST[i])
        self.CM.print_stat()
        self.CM.log(os.path.join(self.generatedFilesDir, 'bitlog.txt'), True, True, True, True)
        for slr_idx, slr in self.dev_layout.slr_by_config_index.iteritems():
            slr.ID = self.CM.SLR_ID_LIST[slr_idx]
            slr.fragment = self.CM.FragmentDict[slr.ID]
            print('SLR layout index = {0:d} : config index = {1:d} : chip id = {2:08x}'.format(slr.layout_index, slr.config_index, slr.fragment.SLR_ID))


def compare_bitfiles(bitfile_list, pb, resfilename):
    targetDir = '/'.join(bitfile_list[0].split('/')[:-1])
    CM = ConfigMemory()
    CM.load_bitstream(bitfile_list[0], BitfileType.Regular)
    ref_design = VivadoDesignModel(os.path.normpath(targetDir), CM.DevicePart)
    ref_design.CM = CM
    ref_design.load_layout(ref_design.DevicePart)
    ref_design.initialize(True)
    framelist = ref_design.getFarList_for_Pblock(pb.X1, pb.Y1, pb.X2, pb.Y2)
    res = dict()
    with open(resfilename, 'w') as logfile:
        for cmp_file in bitfile_list[1:]:
            #logfile.write("\n{0:s}".format(cmp_file))
            cmp_CM = ConfigMemory()
            cmp_CM.load_bitstream(cmp_file, BitfileType.Regular)
            #cmp_CM.log(os.path.join(targetDir, '{0:s}.txt'.format(cmp_file)), True, True, True, True)
            for ref_frame in framelist:
                cmp_frame = cmp_CM.get_frame_by_FAR(ref_frame.FAR)
                for word in range(cmp_CM.FrameSize):
                    mask = ref_frame.data[word] ^ cmp_frame.data[word]
                    if (ref_frame.data[word] != cmp_frame.data[word]):
                        bit_index = Davos_Generic.get_index_of_bit(mask, 1, 32)
                        c = (ref_frame.coord.BlockType, ref_frame.coord.Top, ref_frame.coord.Row, ref_frame.coord.Major,
                             ref_frame.coord.Minor, word)
                        if c not in res:
                            res[c] = []
                        res[c].append(bit_index)
        for k in sorted(res.keys(), key = lambda x: (x[0], x[1], x[2], x[3], x[4], x[5])):
            res[k] = sorted(list(set(res[k])))
            logfile.write("\nBlock={0:01d}, Top={1:01d}, Row={2:01d}, Major={3:03d}, Minor={4:03d}, Word={5:02d}, Bits={6:s}".format(
                k[0], k[1], k[2], k[3], k[4], k[5], ",".join([str(i) for i in res[k]])))
        return res



#python DesignParser.py op=parse_bitstream bitfile=C:/Projects/FFIMIC/bitstream/Top.bit area=X77Y2:X151Y147 skipempty=true bitorder=false
#python DesignParser.py op=parse_netlist project=C:/Projects/FFIMIC area=X77Y2:X151Y147
#python DesignParser.py op=addlayout part=xcku3p-ffva676-2-e
#python DesignParser.py op=lutmap


if __name__ == "__main__":

    options = dict( (key.strip(), val.strip())
                    for key, val in (item.split('=') for item in sys.argv[1:]))

    pb = None
    if 'area' in options:
        matchDesc = re.search('([a-zA-Z]+)\s*?:X([0-9]+)Y([0-9]+)\s*?:\s*?X([0-9]+)Y([0-9]+)', options['area'])
        if matchDesc:
            pb = Pblock('TILE' in matchDesc.group(1).upper(), int(matchDesc.group(2)), int(matchDesc.group(3)),
                        int(matchDesc.group(4)), int(matchDesc.group(5)), '')

    if options['op'].lower() == 'lutmap':
        vivado_script = "C:/Projects/LUTMAP/lutmap.do"
        workdir = "C:/Projects/LUTMAP/UltrascalePlus/"
        proj_path = os.path.join(workdir, "UltrascalePlus.xpr")
        SliceX, TileX = 6, 4
        for SliceY in range(5):
            for Label in ['SLICEL.A6LUT', 'SLICEL.B6LUT', 'SLICEL.C6LUT', 'SLICEL.D6LUT',
                          'SLICEL.E6LUT', 'SLICEL.F6LUT', 'SLICEL.G6LUT', 'SLICEL.H6LUT']:
                LOC = "SLICE_X{0:d}Y{1:d}".format(SliceX, SliceY)
                item_label = "{0:s}_{1:s}".format(LOC, Label)
                export_path = os.path.join(workdir, item_label)
                if not os.path.exists(export_path):
                    os.makedirs(export_path)
                script = "vivado -mode batch -source {0:s} -tclargs \"{1:s}\" \"{2:s}\" \"{3:s}\" \"{4:s}\"".format(
                    vivado_script, proj_path, LOC, Label, export_path).replace("\\", "/")
                print 'Running: {0}'.format(script)
                with open(os.path.join(export_path, '_LayoutParser.log'), 'w') as logfile, \
                        open(os.path.join(export_path, '_LayoutParser.err'), 'w') as errfile:
                    proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=logfile, stderr=errfile, shell=True)
                    proc.wait()
                TileY = SliceY
                bitfile_list = sorted(glob.glob("{0:s}/*.bit".format(export_path)))
                pb = Pblock(True, TileX, TileY, TileX, TileY, "")
                compare_bitfiles(bitfile_list, pb, os.path.join(workdir, "{0:s}.txt".format(item_label)))
                Davos_Generic.zip_folder(export_path, os.path.join(workdir, '{0:s}.zip'.format(item_label)))
                shutil.rmtree(export_path)



    if options['op'].lower() == 'parse_bitstream':
        if 'bitfile' not in options:
            print('Error: bitfile paramater not specified, exiting')
            exit()
        CM = ConfigMemory()
        options['bitfile'] = options['bitfile'].replace('\\', '/')
        targetDir = '/'.join(options['bitfile'].split('/')[:-1])
        CM.load_bitstream(options['bitfile'], BitfileType.Regular)
        design = VivadoDesignModel(os.path.normpath(targetDir), CM.DevicePart)
        design.CM = CM
        design.load_layout(design.DevicePart)
        design.initialize(True)
        bitorder = False
        if 'bitorder' in options:
            if options['bitorder'].lower() == 'true':
                bitorder = True
        skipempty = False
        if 'skipempty' in options:
            if options['skipempty'].lower() == 'true':
                skipempty = True
        lutbels = design.map_lut_bels_from_layout(pb, bitorder, skipempty)
        #lutbels = sorted(lutbels, key = lambda item: (item.slice.Tile.ClockRegion.X, item.slice.Tile.ClockRegion.Y, item.name))
        lutbels = sorted(lutbels, key = lambda item: (item.slice.X, item.slice.Y, item.name))
        desctable = design.cells_to_table(lutbels, ['name', 'beltype', 'init'])
        resfile = os.path.join(design.generatedFilesDir, 'LUTS.csv')
        with open(resfile, 'w') as f:
            f.write(desctable.to_csv())
        print('Result exported to: {0}'.format(resfile))

    if options['op'].lower() == 'parse_netlist':
        if 'project' not in options:
            print('Error: project paramater not specified, exiting')
            exit()
        design = VivadoDesignModel(os.path.normpath(options['project']))
        design.initialize()



    if options['op'].lower() == 'addlayout':
        print('Parsing FPGA layout')
        if 'part' not in options:
            print('Error: FPGA part not specified')
        parts = VivadoDesignModel.get_matching_devices(options['part'])
        if (len(parts) == 1) or (len(parts) > 1 and options['part'] in parts):
            VivadoDesignModel.parse_fpga_layout(parts[0])
        elif len(parts) == 0:
            print('No matching devices found for {0:s}'.format(options['part']))
        else:
            print('Ambiguous part parameter {0:s}, please select one of the following matching parts: \n\t{1:s}'.format(
                options['part'], '\n\t'.join(parts)))


    if options['op'].lower() == 'list_parts':
        print('Available FPGA descriptors:\n\t{0}'.format('\n\t'.join(VivadoDesignModel.get_parts()) ))

    print("Completed")




