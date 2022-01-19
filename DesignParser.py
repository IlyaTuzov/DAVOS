# Datamodel that relates a netlist with a floorplan and a bitstream of Vivado FPGA design
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------
import subprocess
import os
import re
import shutil
import glob
from BitstreamParser import *
import xml.etree.ElementTree as ET

DAVOSPATH = os.path.dirname(os.path.realpath(__file__))

class DevTileColumn:
    def __init__(self, xmltag):
        self.Type = ''
        self.X = 0
        self.Ymin, self.Ymax = 0, 0
        self.build_from_xml(xmltag)

    def build_from_xml(self, xmltag):
        if xmltag!=None:
            self.Type = xmltag.get('type')
            self.X = int(xmltag.get('X'))
            self.Ymin = int(xmltag.get('MinY'))
            self.Ymax = int(xmltag.get('MaxY'))


class DevClockRegion:
    def __init__(self, xmltag):
        self.name = ''
        self.X, self.Y = 0, 0
        self.column_dict = {}
        self.build_from_xml(xmltag)
        self.get_TileY_range()

    def build_from_xml(self, xmltag):
        if xmltag!=None:
            self.name = xmltag.get('name')
            self.X, self.Y = map(int, re.search('X([0-9]+)Y([0-9]+)', self.name).groups())
            for tag in xmltag.findall('COLUMN'):
                c = DevTileColumn(tag)
                self.column_dict[c.X] = c

    def get_TileY_range(self):
        self.TileYmin = min(c.Ymin for c in self.column_dict.values())
        self.TileYmax = max(c.Ymax for c in self.column_dict.values())
        return(self.TileYmin, self.TileYmax)


class DevSRL:
    def __init__(self, xmltag):
        self.name = ''
        self.config_index = 0
        self.layout_index = 0
        self.clock_region_dict = {}
        self.TileY_min, self.TileY_max = 0, 0
        self.build_from_xml(xmltag)
        self.get_TileY_range()

    def build_from_xml(self, xmltag):
        if xmltag != None:
            self.name = xmltag.get('name')
            self.layout_index = int(re.findall('SLR([0-9]+)', self.name)[0])
            self.config_index =int(xmltag.get('config_order_index'))
            for tag in xmltag.findall('CLOCK_REGION'):
                c = DevClockRegion(tag)
                self.clock_region_dict[(c.X, c.Y)] = c

    def get_TileY_range(self):
        self.TileYmin = min(c.TileYmin for c in self.clock_region_dict.values())
        self.TileYmax = max(c.TileYmax for c in self.clock_region_dict.values())
        return(self.TileYmin, self.TileYmax)


class DevLayout:
    def __init__(self, xmltag):
        self.part = ''
        self.slr_by_config_index = {}
        self.slr_by_layout_index = {}
        self.build_from_xml(xmltag)
        cr = self.slr_by_layout_index[0].clock_region_dict.values()[0]
        self.cr_height = cr.TileYmax - cr.TileYmin + 1

    def build_from_xml(self, xmltag):
        if xmltag != None:
            self.part = xmltag.get('part')
            for tag in xmltag.findall('SLR'):
                c = DevSRL(tag)
                self.slr_by_config_index[c.config_index] = c
                self.slr_by_layout_index[c.layout_index] = c

    def get_Tile_local_coordinates(self, globalX, globalY):
        for slr_id, slr in self.slr_by_layout_index.iteritems():
            if globalY >= slr.TileYmin and globalY <= slr.TileYmax:
                return(slr, globalX, globalY-slr.TileYmin)

    #returns: list of (clock_region_obj, TileX, TileY, TileType)
    def get_Tiles_in_area(self, BottomLeft_X, BottomLeft_Y, TopRight_X, TopRight_Y):
        res = []
        filter_enabled = (BottomLeft_X is not None) and (BottomLeft_Y is not None) and (TopRight_X is not None) and (TopRight_Y is not None)
        for slr_id, slr in self.slr_by_layout_index.iteritems():
            for cr_id, cr in slr.clock_region_dict.iteritems():
                for cl_id, cl in cr.column_dict.iteritems():
                    for y in range(cl.Ymin, cl.Ymax+1):
                        tile = (cr, cl.X, y, cl.Type)
                        if filter_enabled:
                            if (tile[1] >= BottomLeft_X) and (tile[1] <= TopRight_X) and (tile[2] >= BottomLeft_Y) and (tile[2] <= TopRight_Y):
                                res.append(tile)
                        else:
                            res.append(tile)
        return(res)


class Pblock:
    def __init__(self, X1, Y1, X2, Y2, name):
        self.X1, self.Y1, self.X2, self.Y2 = X1, Y1, X2, Y2
        self.name = name

    def to_string(self):
        return('Pblock: name={0:s}, X{1:d}Y{2:d} : X{3:d}Y{4:d}'.format(self.name, self.X1, self.Y1, self.X2, self.Y2))


class NetlistCellGroups:
    LUT, FF, Bram, Lutram, Other = range(5)

    @staticmethod
    def to_string(celltype):
        lbl = {0: 'LUT', 1: 'Register', 2: 'BRAM', 3: 'LUTRAM', 4: 'Other'}
        return lbl[celltype]


class NetlistCellDescriptor(object):
    def __init__(self, name="", group=NetlistCellGroups.Other):
        self.name = name
        self.group = group
        self.celltype = ""
        self.beltype = ""
        self.label = ""
        self.sliceX, self.sliceY = 0, 0
        self.tileX, self.tileY = 0, 0
        self.clkregionX, self.clkregionY = 0, 0
        self.connections = {}
        self.slr = None
        self.bitmap = dict()    # key: bit_index, value: (FAR, word, bit)


class LutCellDescritor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Other):
        super(LutCellDescritor, self).__init__(name, group)
        self.init = 0x0


ff_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=SLICE_X([0-9]+)Y([0-9]+)\s+Latch=([0-9a-zA-Z\.]+)\s+Net=(.*)', re.M)
class RegCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.FF):
        super(RegCellDescriptor, self).__init__(name, group)
        self.init = 0x0

    @staticmethod
    def from_ll_string(ll_string):
        m = re.match(ff_match_ptn, ll_string)
        if m is not None:
            res = RegCellDescriptor(m.group(7))
            res.sliceX, res.sliceY = int(m.group(4)), int(m.group(5))
            res.label = m.group(6).replace('FF.', '').replace('Q', 'FF')
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            res.bitmap[0] = (FAR, word, bit)
            return res
        return None


bramram_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=(RAMB18|RAMB36)_X([0-9]+)Y([0-9]+)\s+Ram=B:(BIT|PARBIT)([0-9]+)', re.M)
class BramCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Bram):
        super(BramCellDescriptor, self).__init__(name, group)
        self.bitmap_ecc = dict()

    @staticmethod
    def from_ll_string(ll_string):
        m = re.match(bramram_match_ptn, ll_string)
        if m is not None:
            res = BramCellDescriptor()
            res.sliceX, res.sliceY = int(m.group(5)), int(m.group(6))
            res.label = m.group(4)
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            if m.group(7) == 'BIT':
                res.bitmap[int(m.group(8))] = (FAR, word, bit)
            elif m.group(7) == 'PARBIT':
                res.bitmap_ecc[int(m.group(8))] = (FAR, word, bit)
            return res
        return None


lutram_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=SLICE_X([0-9]+)Y([0-9]+)\s+Ram=(A|B|C|D):([0-9]+)', re.M)
class LutramCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Lutram):
        super(LutramCellDescriptor, self).__init__(name, group)

    @staticmethod
    def from_ll_string(ll_string):
        m = re.match(lutram_match_ptn, ll_string)
        if m is not None:
            res = LutramCellDescriptor()
            res.sliceX, res.sliceY = int(m.group(4)), int(m.group(5))
            res.label = m.group(6)
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            res.bitmap[int(m.group(7))] = (FAR, word, bit)
            return res
        return None



class Netlist:
    def __init__(self):
        self.CellsDict = {
            NetlistCellGroups.LUT:    [],
            NetlistCellGroups.FF:     [],
            NetlistCellGroups.Bram:   [],
            NetlistCellGroups.Lutram: [],
            NetlistCellGroups.Other:  [] }
        self.statistics = dict()

    def load_netlist_cells(self, CellDescFile, unit_path="", pb=None):
        CellDescTab = Table('LutMap')
        CellDescTab.build_from_csv(CellDescFile)
        for i in range(CellDescTab.rownum()):
            label = CellDescTab.getByLabel('BEL', i).split('.')[-1].upper()
            celltype = CellDescTab.getByLabel('CellType', i).upper()
            name = CellDescTab.getByLabel('Node', i)
            if label in ['AFF', 'A5FF', 'BFF', 'B5FF', 'CFF', 'C5FF', 'DFF', 'D5FF']:
                item = RegCellDescriptor(name, NetlistCellGroups.FF)
                item.label = label
            elif label in ['A5LUT', 'A6LUT', 'B5LUT', 'B6LUT', 'C5LUT', 'C6LUT', 'D5LUT', 'D6LUT']:
                if celltype.startswith('DMEM'):
                    item = LutramCellDescriptor(name, NetlistCellGroups.Lutram)
                    item.label = label[0]
                else:
                    item = LutCellDescritor(name, NetlistCellGroups.LUT)
                    item.label = label
            elif label in ['RAMB18E1', 'RAMB36E1']:
                item = BramCellDescriptor(name, NetlistCellGroups.Bram)
                item.label = label[:6]
            else:
                item = NetlistCellDescriptor(name, NetlistCellGroups.Other)
                item.label = label
            item.celltype = celltype.split('.')[-1]
            item.sliceX = int(re.findall('X([0-9]+)', CellDescTab.getByLabel('CellLocation', i))[0])
            item.sliceY = int(re.findall('Y([0-9]+)', CellDescTab.getByLabel('CellLocation', i))[0])
            item.beltype = CellDescTab.getByLabel('BellType', i)
            item.clkregionX = int(re.findall('X([0-9]+)', CellDescTab.getByLabel('ClockRegion', i))[0])
            item.clkregionY = int(re.findall('Y([0-9]+)', CellDescTab.getByLabel('ClockRegion', i))[0])
            item.tileX = int(re.findall('X([0-9]+)', CellDescTab.getByLabel('Tile', i))[0])
            item.tileY = int(re.findall('Y([0-9]+)', CellDescTab.getByLabel('Tile', i))[0])
            #INIT attributes are present in LUT, LUTRAM and FF
            if item.group in [NetlistCellGroups.LUT, NetlistCellGroups.FF, NetlistCellGroups.Lutram]:
                match = re.search('h([0-9a-f]+)', CellDescTab.getByLabel('INIT', i).lower())
                item.init = 0x0 if not match else int(match.group(1), 16)
            for c in re.findall('([I0-9]+):([A0-9]+)', CellDescTab.getByLabel('CellConnections', i)):
                item.connections[c[0]] = c[1]
            if unit_path != "":
                if not item.name.startswith(unit_path):
                    continue
            if pb is not None:
                if not (item.tileX >= pb.X1) and (item.tileX <= pb.X2) and (item.tileY >= pb.Y1) and (item.tileY <= pb.Y2):
                    continue
            self.CellsDict[item.group].append(item)
        print("\n\nLoaded netlist cells in Unit path=\"{0:s}\", Pblock={1:s}\n{2:s}\n\n".format(
            unit_path, "None" if pb is None else pb.to_string(), self.update_statistics()))

    def get_cells(self, group):
        return self.CellsDict[group]

    def update_statistics(self):
        for group, cellst in self.CellsDict.iteritems():
            self.statistics[group] = dict()
            for cell in cellst:
                if cell.celltype not in self.statistics[group]:
                    self.statistics[group][cell.celltype] = 0
                self.statistics[group][cell.celltype] += 1
        return '\n'.join(['Group {0} : \n\t{1}'.format(NetlistCellGroups.to_string(group), '\n\t'.join(
            ['{0:16s} : {1:d}'.format(celltype, num) for celltype, num in celltypes.iteritems()]))
                          for group, celltypes in self.statistics.iteritems()])

    def load_logic_location_file(self, fname, match_cell_list=True):
        print('Parsing Logic Location File: {0:s}'.format(fname))
        start_time = time.time()
        cells_by_coordinates = {}
        matched_ll_items_per_type = {NetlistCellGroups.FF: 0, NetlistCellGroups.Bram: 0, NetlistCellGroups.Lutram: 0}
        if match_cell_list:
            for cellgroup, cells in self.CellsDict.iteritems():
                for cell in cells:
                    cells_by_coordinates[(cell.sliceX, cell.sliceY, cell.label)] = cell
        num_items = sum(1 for line in open(fname))
        with open(fname, 'r') as f:
            cnt = 0
            for line in f:
                item = RegCellDescriptor.from_ll_string(line)
                if item is None:
                    item = BramCellDescriptor.from_ll_string(line)
                if item is None:
                    item = LutramCellDescriptor.from_ll_string(line)
                if item is None:
                    continue
                if match_cell_list:
                    if (item.sliceX, item.sliceY, item.label) in cells_by_coordinates:
                        refcell = cells_by_coordinates[(item.sliceX, item.sliceY, item.label)]
                        for bit in item.bitmap.keys():
                            refcell.bitmap[bit] = item.bitmap[bit]
                        matched_ll_items_per_type[item.group] += 1
                else:
                    self.CellsDict[item.group].append(item)
                if cnt%1000 == 0:
                    console_message('LL items processed {0:d} ({1:3.1f}%)'.format(cnt, 100.0*float(cnt)/num_items),
                                    ConsoleColors.Green, True)
                cnt+=1
        print('LL file parsed in {0:.1f} seconds'.format(time.time()-start_time))
        print('Matched LL file items: \n\t{0:s}'.format('\n\t'.join(['{0:10s}: {1:8d}'.format(
            NetlistCellGroups.to_string(k), v) for k, v in matched_ll_items_per_type.iteritems()])))





class VivadoDesignModel:
    def __init__(self, targetDir, series, DevicePart):
        self.targetDir = targetDir
        self.DevicePart = DevicePart
        self.generatedFilesDir = os.path.normpath(os.path.join(self.targetDir, 'DavosGenerated'))
        if not os.path.exists(self.generatedFilesDir):
            os.makedirs(self.generatedFilesDir)
        self.VivadoProjectFile = (lambda l: l[0] if l is not None and len(l)>0 else '')(glob.glob(os.path.join(self.targetDir,'*.xpr')))
        self.ImplementationRun = '*'
        self.files = {
            'BIT' : os.path.join(self.generatedFilesDir, 'Bitstream.bit'),
            'EBC' : os.path.join(self.generatedFilesDir, 'Bitstream.ebc'),
            'EBD' : os.path.join(self.generatedFilesDir, 'Bitstream.ebd'),
            'LL'  : os.path.join(self.generatedFilesDir, 'Bitstream.ll'),
            'CELLS': os.path.join(self.generatedFilesDir, 'CELLS.csv')
        }
        self.series = series
        self.CM = ConfigMemory(self.series)
        self.netlist = Netlist()
        self.dev_layout = None
        self.moduledir = DAVOSPATH
        print('Vivado Design Module instantiated from: {0}'.format(self.moduledir))

    @staticmethod
    def parse_fpga_layout(devicepart):
        support_scripts_path = os.path.join(DAVOSPATH, 'SupportScripts')
        workdir = os.path.join(DAVOSPATH, 'FFI', 'DeviceSupport', 'tmp').replace("\\", '/')
        if not os.path.exists(workdir):
            os.makedirs(workdir)
        shutil.copyfile(os.path.join(support_scripts_path, 'template.vhd'), os.path.join(workdir, 'template.vhd'))
        script = "vivado -mode batch -source {0}/VivadoParseLayout.do -tclargs \"{1}\" \"{2}\" \"{3}\" \"{4}\" ".format(
            support_scripts_path, "*", devicepart, "*", workdir).replace("\\", "/")
        print 'Running: {0}'.format(script)
        with open(os.path.join(workdir, '_LayoutParser.log'), 'w') as logfile, \
                open(os.path.join(workdir, '_LayoutParser.err'), 'w') as errfile:
            proc = subprocess.Popen(script, stdin=subprocess.PIPE, stdout=logfile, stderr=errfile, shell=True)
            proc.wait()
        bitfile = os.path.join(workdir, '{0}.bit'.format(devicepart))
        if os.path.exists(bitfile):
            CM = ConfigMemory()
            CM.load_bitstream(bitfile, BitfileType.Debug)
        else:
            print 'parse_fpga_layout(): bitfile not found: {0}'.format(bitfile)
            return
        layoutfile = os.path.join(workdir, 'LAYOUT_{0}.xml'.format(devicepart))
        if os.path.exists(layoutfile):
            shutil.copyfile(layoutfile, os.path.join(DAVOSPATH, 'FFI', 'DeviceSupport', 'LAYOUT_{0}.xml'.format(devicepart)))
        else:
            print 'parse_fpga_layout(): layout not found: {0}'.format(layoutfile)
            return
        shutil.rmtree(workdir)
        print 'Layout parsed for FPGA part: {0}'.format(devicepart)

    @staticmethod
    def get_parts(tag='LAYOUT'):
        devsupport_dir = os.path.join(DAVOSPATH, 'FFI/DeviceSupport')
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
        os.chdir(os.path.join(self.moduledir, 'FFI/DeviceSupport'))
        layoutfile = glob.glob('LAYOUT*{0:s}*.xml'.format(devicepart))
        if len(layoutfile) == 0:
            print('load_layout: device layout not found for device part: {0} in {1}'.format(devicepart, os.getcwd()))
            print('Device layout can be added to DAVOS by running: python DesignParser.py op=addlayout part={0:s}'.format(devicepart))
            return
        tree = ET.parse(os.path.join(os.getcwd(), layoutfile[0])).getroot()
        self.dev_layout = DevLayout(tree)

    def check_preconditions(self):
        res = True
        for fname in self.files.values():
            if not os.path.exists(fname):
                res = False
                print('check_preconditions: {0:55s} : missing'.format(fname))
            else:
                print('check_preconditions: {0:55s} : available'.format(fname))
        return res

    def fix_preconditions(self):
        os.chdir(self.targetDir)
        if not self.check_preconditions():
            print('Running Vivado to obtain input files')
            parser_path = os.path.join(DAVOSPATH, 'SupportScripts', 'VivadoParseNetlist.do')
            script = "vivado -mode batch -source {0} -tclargs {1} \"{2}\" {3} {4} ".format(
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
                if yl >= fragment.layout.BottomRows * self.dev_layout.cr_height:
                    Top = 0
                    Row = cr_y - fragment.layout.BottomRows
                else:
                    Top = 1
                    Row = fragment.layout.BottomRows-1-cr_y
                FAR = FarFields(self.series, 0, Top, Row, x, 0).get_far()
                columns.add((slr.config_index, FAR))
        columnlist = sorted(list(columns), key = lambda x: (x[0], x[1]))
        for i in columnlist:
            res += self.CM.get_frames_of_column(i[0], i[1])
        # for i in res:
        #     print(i.to_string(False, False, False))
        return(res)


    #tileX to localize column
    #tileY to localize slr, top, row, word offset
    #sliceX to localize minor_frame_range (26--29 or 32--36)
    #label (A5/A6/B5/B6/C5/C6/D5/D6) to cut 64 bits fragment with LUT BEL content
    #result: SLR, and list (64 items) of tuples (FAR, word, bit)
    def get_lut_bel_fragment(self, tileX, tileY, sliceX, label):
        if self.series == FPGASeries.S7:
            slr, tileX_local, tileY_local = self.dev_layout.get_Tile_local_coordinates(tileX, tileY)
            clkregionY_local = tileY_local / 50
            if clkregionY_local + 1 > slr.fragment.layout.BottomRows:
                Top, Row = 0, (clkregionY_local - slr.fragment.layout.BottomRows)
            else:
                Top, Row = 1, (slr.fragment.layout.BottomRows - clkregionY_local - 1)
            Column = tileX_local
            if sliceX % 2 == 1:
                m1, m2, m3, m4 = 26, 27, 28, 29
            else:
                m1, m2, m3, m4 = 32, 33, 34, 35
            offset = (tileY_local % 50)*2
            #skip word 50 (reserved for frame CRC)
            if offset >= 50:
                offset += 1
            if label in ['A5LUT', 'A6LUT']:
                offset, shift = offset, 0
            elif label in ['B5LUT', 'B6LUT']:
                offset, shift = offset, 16
            elif label in ['C5LUT', 'C6LUT']:
                offset, shift = offset+1, 0
            elif label in ['D5LUT', 'D6LUT']:
                offset, shift = offset+1, 16
            else:
                print('get_lut_bel_fragment(): unknown bel label {0:s}'.format(label))
                return
            q1, q2, q3, q4 = [], [], [], []
            for i in range(16):
                q1.append( (FarFields(self.series, 0, Top, Row, Column, m1).get_far(), offset, i+shift) )
                q2.append( (FarFields(self.series, 0, Top, Row, Column, m2).get_far(), offset, i+shift) )
                q3.append( (FarFields(self.series, 0, Top, Row, Column, m3).get_far(), offset, i+shift) )
                q4.append( (FarFields(self.series, 0, Top, Row, Column, m4).get_far(), offset, i+shift) )
            coordlist = q4 + q3 + q2 + q1
            res = {k: v for k, v in enumerate(coordlist)}
            return (slr, res)
        else:
            print 'get_lut_bel_fragment() : lut mapping is not supported for this FPGA series: {0:s}'.format(str(self.series))

    def map_lut_cells(self, unit_path="", pb=None):
        if self.series == FPGASeries.S7:
            for item in self.netlist.get_cells(NetlistCellGroups.LUT):
                item.slr, item.bitmap = self.get_lut_bel_fragment(item.tileX, item.tileY, item.sliceX, item.label)
        else:
            print 'map_luts() : lut mapping is not supported for this FPGA series: {0:s}'.format(str(self.series))
        print('Mapped LUTS in dut_scope = \"{0:s}\", pblock = {1:s}: {2:d}'.format(
            unit_path,
            pb.to_string() if pb is not None else "None",
            len(self.netlist.get_cells(NetlistCellGroups.LUT))))

    def map_lut_bels_from_layout(self, pb, reorder=False, skip_empty=False):
        res = []
        if pb != None:
            clb_tiles = self.dev_layout.get_Tiles_in_area(pb.X1, pb.Y1, pb.X2, pb.Y2)
            print 'CLB Tiles in {0:s} : {1:d}'.format(pb.to_string(), len(clb_tiles))
        else:
            clb_tiles = self.dev_layout.get_Tiles_in_area(None, None, None, None)
            print 'CLB Tiles : {0:d}'.format(len(clb_tiles))
        for tile in clb_tiles:
            # tile[0] - clock_region_obj, tile[1] - TileX, tile[2] - TileY, tile[3] - TileType
            if self.series == FPGASeries.S7:
                for even_odd in range(2):
                    for label in ['A6', 'B6', 'C6', 'D6']:
                        lut = LutCellDescritor()
                        lut.name = 'Tile_X{0:03d}Y{1:03d}:Slice_{2:s}:Label_{3:s}'.format(
                            tile[1], tile[2], 'L' if even_odd==0 else 'R', label)
                        lut.type = 'LUT6'
                        lut.label = label
                        lut.beltype = 'LUT_OR_MEM6' if (tile[3] in ['CLBLM_L', 'CLBLM_R']) and even_odd == 0 else 'LUT6'
                        lut.clkregionX, lut.clkregionY = tile[0].X, tile[0].Y
                        lut.tileX, lut.tileY = tile[1], tile[2]
                        slr, lut.bitmap = self.get_lut_bel_fragment(lut.tileX, lut.tileY, even_odd, label)
                        lut_content = 0x0
                        for bit_idx in range(63, -1, -1):
                            (far, word, bit) = lut.bitmap[bit_idx]
                            frame = self.CM.get_frame_by_FAR(far, slr.ID)
                            lut_content = (lut_content << 1) | ((frame.data[word] >> bit) & 0x1)
                        if skip_empty and lut_content == 0x0:
                            continue
                        if reorder:
                            bitmap = map_M if lut.beltype == 'LUT_OR_MEM6' else map_L
                            for bit in range(64):
                                lut.init = lut.init | (((lut_content >> bitmap[bit]) & 0x1) << bit)
                        else:
                            lut.init = lut_content
                        res.append(lut)
            else:
                print 'get_luts_from_layout(): lut mapping not defined for series {0:s}, exiting'.format(FPGASeries.to_string(self.series))
                return None
        return res

    def cells_to_table(self, celldesclist, labels):
        res = Table('Cells', labels)
        for cell in celldesclist:
            data = ['0x{0:016x}'.format(getattr(cell, item)) if item in ['init'] else str(getattr(cell, item))
                    for item in labels]
            res.add_row(data)
        return res

    def initialize(self, skip_files=False, unit_path="", pb=None):
        if not skip_files:
            self.fix_preconditions()
            self.netlist.load_netlist_cells(self.files['CELLS'], unit_path, pb)
            self.netlist.load_logic_location_file(self.files['LL'], True)
            self.CM.set_series(self.series)
            self.load_layout(self.DevicePart)
            self.CM.load_bitstream(self.files['BIT'], BitfileType.Regular)
            self.CM.load_essential_bits(self.files['EBC'], FileTypes.EBC, self.CM.SLR_ID_LIST[0])
            self.CM.load_essential_bits(self.files['EBD'], FileTypes.EBD, self.CM.SLR_ID_LIST[0])
        self.CM.print_stat()
        self.CM.log(os.path.join(self.generatedFilesDir, 'bitlog.txt'), True, True, True, True)
        for slr_idx, slr in self.dev_layout.slr_by_config_index.iteritems():
            slr.ID = self.CM.SLR_ID_LIST[slr_idx]
            slr.fragment = self.CM.FragmentDict[slr.ID]
            print('SLR layout index = {0:d} : config index = {1:d} : chip id = {2:08x}'.format(slr.layout_index, slr.config_index, slr.fragment.SLR_ID))



#python DesignParser.py op=parse_luts bitfile=C:/Projects/FFIMIC/bitstream/Top.bit area=X77Y2:X151Y147 skipempty=true bitorder=true
#python DesignParser.py op=addlayout part=xc7a100tcsg324-1




if __name__ == "__main__":

    options = dict( (key.strip(), val.strip())
                    for key, val in (item.split('=') for item in sys.argv[1:]))

    if options['op'].lower() == 'parse_luts':
        CM = ConfigMemory()
        options['bitfile'] = options['bitfile'].replace('\\', '/')
        targetDir = '/'.join(options['bitfile'].split('/')[:-1])
        CM.load_bitstream(options['bitfile'], BitfileType.Regular)
        design = VivadoDesignModel(os.path.normpath(targetDir), CM.Series, CM.DevicePart)
        design.CM = CM
        design.load_layout(design.DevicePart)
        design.initialize(True)
        pb = None
        if 'area' in options:
            matchDesc = re.search('X([0-9]+)Y([0-9]+)\s*?:\s*?X([0-9]+)Y([0-9]+)', options['area'])
            if matchDesc:
                pb = Pblock(int(matchDesc.group(1)), int(matchDesc.group(2)), int(matchDesc.group(3)),
                            int(matchDesc.group(4)), '')
        bitorder = False
        if 'bitorder' in options:
            if options['bitorder'].lower() == 'true':
                bitorder = True
        skipempty = False
        if 'skipempty' in options:
            if options['skipempty'].lower() == 'true':
                skipempty = True
        lutbels = design.map_lut_bels_from_layout(pb, bitorder, skipempty)
        lutbels = sorted(lutbels, key = lambda item: (item.clkregionX, item.clkregionY, item.name))
        desctable = design.cells_to_table(lutbels, ['name', 'beltype', 'clkregionX', 'clkregionY', 'init'])
        resfile = os.path.join(design.generatedFilesDir, 'LUTS.csv')
        with open(resfile, 'w') as f:
            f.write(desctable.to_csv())
        print('Result exported to: {0}'.format(resfile))


    if options['op'].lower() == 'addlayout':
        print 'Parsing FPGA layout'
        if 'part' not in options:
            print 'Error: FPGA part not specified'
        parts = VivadoDesignModel.get_matching_devices(options['part'])
        if (len(parts) == 1) or (len(parts) > 1 and options['part'] in parts):
            VivadoDesignModel.parse_fpga_layout(parts[0])
        elif len(parts) == 0:
            print 'No matching devices found for {0:s}'.format(options['part'])
        else:
            print 'Ambiguous part parameter {0:s}, please select one of the following matching parts: \n\t{1:s}'.format(
                options['part'], '\n\t'.join(parts))


    if options['op'].lower() == 'list_parts':
        print 'Available FPGA descriptors:\n\t{0}'.format('\n\t'.join(VivadoDesignModel.get_parts()) )

    print "Completed"




