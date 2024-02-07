# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A model of FPGA layout and design netlist
#       
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

import os
import sys
import re
DAVOSPATH = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
sys.path.insert(1, DAVOSPATH)
from Davos_Generic import *

TileTypesS7 = {'CLB': ['CLBLL', 'CLBLL_R', 'CLBLL_L', 'CLBLM', 'CLBLM_L', 'CLBLM_R'],
               'INT': ['INT_L', 'INT_R']}

TileTypesUSP = {'CLB': ['CLEL', 'CLEL_L', 'CLEL_R', 'CLEM', 'CLEM_L', 'CLEM_R'],
                'INT': ['INT']}

SliceTypesS7 = {'CLB': ['SLICEL', 'SLICEM']}

SliceTypesUSP = {'CLB': ['SLICEL', 'SLICEM']}

class Pblock:
    def __init__(self, TileNotation, X1, Y1, X2, Y2, name):
        self.TileNotation = TileNotation
        self.X1, self.Y1, self.X2, self.Y2 = X1, Y1, X2, Y2
        self.name = name

    def to_string(self):
        return('Pblock: name={0:s}, {1:s} : X{2:d}Y{3:d} > X{4:d}Y{5:d}'.format(
            self.name, "Tiles" if self.TileNotation else "Slices", self.X1, self.Y1, self.X2, self.Y2))




class DevSlice:
    def __init__(self, xmltag):
        self.Name = ''
        self.X, self.Y = 0, 0
        self.Type = ''
        self.Offset = 0
        self.Tile = None
        self.build_from_xml(xmltag)

    def build_from_xml(self, xmltag):
        if xmltag is not None:
            self.Name = xmltag.get('name')
            self.X, self.Y = map(int, re.findall("X([0-9]+)Y([0-9]+)", self.Name)[0])
            self.Type = xmltag.get('type')


class DevTile:
    def __init__(self, xmltag):
        self.Name = ''
        self.X, self.Y = 0, 0
        self.Type = ''
        self.Column = 0
        self.SliceDict = {}
        self.ClockRegion = None
        self.build_from_xml(xmltag)

    def build_from_xml(self, xmltag):
        if xmltag is not None:
            self.Name = xmltag.get('name')
            self.X, self.Y = map(int, re.findall("X([0-9]+)Y([0-9]+)", self.Name)[0])
            self.Type = xmltag.get('type')
            self.Column = int(xmltag.get('column'))
            for item in xmltag.findall('Slice'):
                slice = DevSlice(item)
                slice.Tile = self
                self.SliceDict[slice.X, slice.Y, slice.Type] = slice


class DevClockRegion:
    def __init__(self, xmltag):
        self.Name = ''
        self.X, self.Y = 0, 0
        self.TileDict = {}
        self.TileYmin, self.TileYmax = None, None
        self.build_from_xml(xmltag)

    def build_from_xml(self, xmltag):
        if xmltag!=None:
            self.Name = xmltag.get('name')
            self.X, self.Y = map(int, re.findall('X([0-9]+)Y([0-9]+)', self.Name)[0])
            for item in xmltag.findall('Tile'):
                tile = DevTile(item)
                tile.ClockRegion = self
                self.TileDict[tile.X, tile.Y, tile.Type] = tile
                if tile.Type in TileTypesS7['CLB']+TileTypesUSP['CLB']:
                    if (self.TileYmin is None) or (tile.Y < self.TileYmin):
                        self.TileYmin = tile.Y
                    if (self.TileYmax is None) or (tile.Y > self.TileYmax):
                        self.TileYmax = tile.Y

    def get_TileY_range(self):
        return self.TileYmin, self.TileYmax


class DevSRL:
    def __init__(self, xmltag):
        self.name = ''
        self.config_index = 0
        self.layout_index = 0
        self.ClockRegionDict = {}
        self.SwBoxDict = {}
        self.TileYmin, self.TileYmax = 0, 0
        self.build_from_xml(xmltag)
        self.get_TileY_range()

    def build_from_xml(self, xmltag):
        if xmltag != None:
            self.Name = xmltag.get('name')
            self.layout_index = int(re.findall('SLR([0-9]+)', self.Name)[0])
            self.config_index =int(xmltag.get('config_order_index'))
            for tag in xmltag.findall('ClockRegion'):
                c = DevClockRegion(tag)
                #if c.TileYmin is None or c.TileYmax is None:
                #    print('DevSRL.build_from_xml: skipping clockRegion[{0:d}:{1:d}]'.format(c.X, c.Y))
                #    continue
                self.ClockRegionDict[(c.X, c.Y)] = c
            for cr_key, cr in self.ClockRegionDict.iteritems():
                for tile_key, tile in cr.TileDict.iteritems():
                    if tile.Type in TileTypesS7['INT']+TileTypesUSP['INT']:
                        self.SwBoxDict[tile.X] = tile.Column
            for cr_key, cr in self.ClockRegionDict.iteritems():
                for tile_key, tile in cr.TileDict.iteritems():
                    if tile.Type in TileTypesS7['CLB']+TileTypesUSP['CLB']:
                        tile.Offset = tile.Column - self.SwBoxDict[tile.X]


    def get_TileY_range(self):
        self.TileYmin = min(c.TileYmin for c in self.ClockRegionDict.values())
        if self.TileYmin == None:
            self.TileYmin = 0        
        self.TileYmax = max(c.TileYmax for c in self.ClockRegionDict.values())
        return(self.TileYmin, self.TileYmax)


class DevLayout:
    def __init__(self, xmltag):
        self.part = ''
        self.slr_by_config_index = {}
        self.slr_by_layout_index = {}
        self.slice_by_coord_dict = {}
        self.slice_by_name_dict = {}
        self.clb_column_dict = {} #TileX -> [sliceX]
        self.build_from_xml(xmltag)
        cr = self.slr_by_layout_index[0].ClockRegionDict.values()[0]
        self.cr_height = cr.TileYmax - cr.TileYmin + 1

    def build_from_xml(self, xmltag):
        if xmltag != None:
            self.part = xmltag.get('part')
            for tag in xmltag.findall('Slr'):
                c = DevSRL(tag)
                self.slr_by_config_index[c.config_index] = c
                self.slr_by_layout_index[c.layout_index] = c
            self.extract_slices()
            print "FPGA layout loaded for device part: {0}".format(self.part)
            SlicesPerType={}
            for k in self.slice_by_coord_dict.keys():
                if k[2] not in SlicesPerType:
                    SlicesPerType[k[2]] = 0
                SlicesPerType[k[2]] += 1
            for s, t in sorted( ((v,k) for k,v in SlicesPerType.iteritems()), reverse=True):
                print "\tSlices of type {0:20s} : {1:d}".format(t, s)
            #for k in sorted(self.clb_column_dict.keys()):
            #    print "CLB Column {0:03d} : Slices {1:s}".format(k, str(self.clb_column_dict[k]))


    def extract_slices(self):
        for slr_key, slr in self.slr_by_layout_index.iteritems():
            for cr_key, cr in slr.ClockRegionDict.iteritems():
                for tile_key, tile in cr.TileDict.iteritems():
                    for slice_key, slice in tile.SliceDict.iteritems():
                        self.slice_by_coord_dict[slice_key] = slice
                        self.slice_by_name_dict[slice.Name] = slice
                        #add bottom slice to TileDict
                        if slice_key[1] == 0:
                            if slice.Type in SliceTypesS7['CLB'] + SliceTypesUSP['CLB']:
                                if slice.Tile.X not in self.clb_column_dict:
                                    self.clb_column_dict[slice.Tile.X] = []
                                self.clb_column_dict[slice.Tile.X].append(slice.X)


    def get_Tile_local_coordinates(self, globalX, globalY):
        for slr_id, slr in self.slr_by_layout_index.iteritems():
            if globalY >= slr.TileYmin and globalY <= slr.TileYmax:
                return(slr, globalX, globalY-slr.TileYmin)

    def get_Slices_in_Pblock(self, Pblock):
        res = {}
        if Pblock is None:
            res = {k: v for k, v in self.slice_by_coord_dict.iteritems()
                   if v.Type in SliceTypesS7['CLB'] + SliceTypesUSP['CLB']}
        else:
            if Pblock.TileNotation:
                slice_column_indexes = []
                for TileX in range(Pblock.X1, Pblock.X2+1):
                    if TileX in self.clb_column_dict:
                        slice_column_indexes += self.clb_column_dict[TileX]
            else:
                slice_column_indexes = range(Pblock.X1, Pblock.X2+1)
            slice_column_indexes.sort()
            for x in slice_column_indexes:
                for y in range(Pblock.Y1, Pblock.Y2+1):
                    for t in SliceTypesS7['CLB'] + SliceTypesUSP['CLB']:
                        if (x, y, t) in self.slice_by_coord_dict:
                            res[(x, y, t)] = self.slice_by_coord_dict[(x, y, t)]
        return sorted(res.values(), key=lambda item: (item.X, item.Type, item.Y))





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
        self.slice = None
        self.connections = {}
        self.slr = None
        self.bitmap = dict()    # key: bit_index, value: (FAR, word, bit)

    def bitmap_to_string(self):
        FAR_set, word_set, bit_set = set(), set(), set()
        for bit in self.bitmap:
            item = self.bitmap[bit]
            FAR_set.add(item[0])
            word_set.add(item[1])
            bit_set.add(item[2])
        return("(FAR: {0:s}) : (word: {1:s}) : (bit: {2:s})".format(
            ' '.join(['0x{0:08X}'.format(i) for i in sorted(list(FAR_set))]),
            ' '.join(['{0:d}'.format(i) for i in sorted(list(word_set))]),
            ' '.join(['{0:d}'.format(i) for i in sorted(list(bit_set))]) ))



class LutCellDescritor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Other):
        super(LutCellDescritor, self).__init__(name, group)
        self.init = 0x0

#                                   1           2                      3          4              5                 6                              7                      8
ff_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+(SLR[0-9]+)?\s*([0-9]+)?\s*Block=(SLICE_X[0-9]+Y[0-9]+)\s+Latch=([0-9a-zA-Z\.]+)\s+Net=(.*)', re.M | re.IGNORECASE)
class RegCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.FF):
        super(RegCellDescriptor, self).__init__(name, group)
        self.init = 0x0

    @staticmethod
    def from_ll_string(ll_string, layout=None):
        m = re.match(ff_match_ptn, ll_string)
        if m is not None:
            res = RegCellDescriptor(m.group(8))
            if layout is not None:
                celloc = m.group(6)
                res.slice = layout.slice_by_name_dict[celloc]
            res.label = m.group(7).replace('FF.', '').replace('Q', 'FF')
            #res.slr=int(m.group(5))
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            res.bitmap[0] = (FAR, word, bit)
            return res
        return None

#                                    1            2                      3          4              5                 6               7                        8           9
bram_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+(SLR[0-9]+)?\s*([0-9]+)?\s*Block=(RAMB18|RAMB36)_(X[0-9]+Y[0-9]+)\s+Ram=B:(BIT|PARBIT)([0-9]+)', re.M | re.IGNORECASE)
class BramCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Bram):
        super(BramCellDescriptor, self).__init__(name, group)
        self.bitmap_ecc = dict()

    @staticmethod
    def from_ll_string(ll_string, layout):
        m = re.match(bram_match_ptn, ll_string)
        if m is not None:
            res = BramCellDescriptor()
            if layout is not None:
                celloc = '{0}_{1}'.format(m.group(6), m.group(7))
                res.slice = layout.slice_by_name_dict[celloc]
            res.label = m.group(6)
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            # res.slr=int(m.group(5))
            if m.group(8) == 'BIT':
                res.bitmap[int(m.group(9))] = (FAR, word, bit)
            elif m.group(8) == 'PARBIT':
                res.bitmap_ecc[int(m.group(9))] = (FAR, word, bit)
            return res
        return None

#                                      1            2                      3          4              5                 6                            7                  8
lutram_match_ptn = re.compile(r'Bit\s+([0-9]+)\s+0x([0-9abcdefABCDEF]+)\s+([0-9]+)\s+(SLR[0-9]+)?\s*([0-9]+)?\s*Block=(SLICE_X[0-9]+Y[0-9]+)\s+Ram=(A|B|C|D|E|F|G|H):([0-9]+)', re.M | re.IGNORECASE)
class LutramCellDescriptor(NetlistCellDescriptor):
    def __init__(self, name="", group=NetlistCellGroups.Lutram):
        super(LutramCellDescriptor, self).__init__(name, group)

    @staticmethod
    def from_ll_string(ll_string, layout):
        m = re.match(lutram_match_ptn, ll_string)
        if m is not None:
            res = LutramCellDescriptor()
            if layout is not None:
                celloc = m.group(6)
                res.slice = layout.slice_by_name_dict[celloc]
            res.label = m.group(7)
            FAR, offset = int(m.group(2), 16), int(m.group(3))
            word, bit = offset/32, offset%32
            # res.slr=int(m.group(5))
            res.bitmap[int(m.group(8))] = (FAR, word, bit)
            return res
        return None


BELTYPES_S7 = {'REG': ['AFF', 'A5FF', 'BFF', 'B5FF', 'CFF', 'C5FF', 'DFF', 'D5FF'],
               'LUT': ['A5LUT', 'A6LUT', 'B5LUT', 'B6LUT', 'C5LUT', 'C6LUT', 'D5LUT', 'D6LUT'],
               'BRAM': ['RAMB18E1', 'RAMB36E1']}

BELTYPES_USP = {'REG': ['AFF', 'AFF2', 'BFF', 'BFF2', 'CFF', 'CFF2', 'DFF', 'DFF2',
                        'EFF', 'EFF2', 'FFF', 'FFF2', 'GFF', 'GFF2', 'HFF', 'HFF2'],
               'LUT': ['A5LUT', 'A6LUT', 'B5LUT', 'B6LUT', 'C5LUT', 'C6LUT', 'D5LUT', 'D6LUT',
                       'E5LUT', 'E6LUT', 'F5LUT', 'F6LUT', 'G5LUT', 'G6LUT', 'H5LUT', 'H6LUT'],
               'BRAM': ['RAMB18E2_L', 'RAMB18E2_U', 'RAMB36E2']}

class Netlist:
    def __init__(self):
        self.CellsDict = {
            NetlistCellGroups.LUT:    [],
            NetlistCellGroups.FF:     [],
            NetlistCellGroups.Bram:   [],
            NetlistCellGroups.Lutram: [],
            NetlistCellGroups.Other:  [] }
        self.statistics = dict()

    def load_netlist_cells(self, CellDescFile, dev_layout, unit_path="", pb=None):
        CellDescTab = Table('Cells')
        CellDescTab.build_from_csv(CellDescFile)
        for i in range(CellDescTab.rownum()):
            label = CellDescTab.getByLabel('BEL', i).split('.')[-1].upper()
            celltype = CellDescTab.getByLabel('CellType', i).upper()
            name = CellDescTab.getByLabel('Node', i)
            if label in BELTYPES_S7['REG'] + BELTYPES_USP['REG']:
                item = RegCellDescriptor(name, NetlistCellGroups.FF)
                item.label = label
            elif label in BELTYPES_S7['LUT'] + BELTYPES_USP['LUT']:
                if celltype.startswith('DMEM') or celltype.startswith('CLB.LUTRAM'):
                    item = LutramCellDescriptor(name, NetlistCellGroups.Lutram)
                    item.label = label[0]
                else:
                    item = LutCellDescritor(name, NetlistCellGroups.LUT)
                    item.label = label[0:2]

            elif label in BELTYPES_S7['BRAM'] + BELTYPES_USP['BRAM']:
                item = BramCellDescriptor(name, NetlistCellGroups.Bram)
                item.label = label[:6]
            else:
                item = NetlistCellDescriptor(name, NetlistCellGroups.Other)
                item.label = label
            item.celltype = celltype.split('.')[-1]
            celloc = CellDescTab.getByLabel('CellLocation', i)
            item.slice = dev_layout.slice_by_name_dict[celloc]
            item.beltype = CellDescTab.getByLabel('BellType', i)

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
                if not ((item.slice.Tile.X >= pb.X1) and (item.slice.Tile.X <= pb.X2) and
                        (item.slice.Tile.Y >= pb.Y1) and (item.slice.Tile.Y <= pb.Y2)):
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


    def load_logic_location_file(self, fname, dev_layout, unit_path="", pb=None, match_cell_list=True):
        print('Parsing Logic Location File: {0:s}'.format(fname))
        start_time = time.time()
        cells_by_coordinates = {}
        matched_ll_items_per_type = {NetlistCellGroups.FF: 0, NetlistCellGroups.Bram: 0, NetlistCellGroups.Lutram: 0}
        if match_cell_list:
            for cellgroup, cells in self.CellsDict.iteritems():
                for cell in cells:
                    cells_by_coordinates[(cell.slice.X, cell.slice.Y, cell.label)] = cell
        num_items = sum(1 for line in open(fname))
        with open(fname, 'r') as f:
            cnt = 0
            for line in f:
                item = RegCellDescriptor.from_ll_string(line, dev_layout)
                if item is None:
                    item = BramCellDescriptor.from_ll_string(line, dev_layout)
                if item is None:
                    item = LutramCellDescriptor.from_ll_string(line, dev_layout)
                if item is None:
                    continue
                cnt += 1
                if cnt%1000 == 0:
                    console_message('LL items processed {0:06d} ({1:3.1f}%)'.format(
                        cnt, 100.0*float(cnt)/num_items), ConsoleColors.Green, True)
                if pb is not None:
                    if not ((item.slice.Tile.X >= pb.X1) and (item.slice.Tile.X <= pb.X2) and
                            (item.slice.Tile.Y >= pb.Y1) and (item.slice.Tile.Y <= pb.Y2)):
                        continue
                if match_cell_list:
                    if (item.slice.X, item.slice.Y, item.label) in cells_by_coordinates:
                        refcell = cells_by_coordinates[(item.slice.X, item.slice.Y, item.label)]
                        if unit_path != "" and not refcell.name.startswith(unit_path):
                            continue
                        for bit in item.bitmap.keys():
                            refcell.bitmap[bit] = item.bitmap[bit]
                        matched_ll_items_per_type[item.group] += 1
                else:
                    self.CellsDict[item.group].append(item)
        print('LL file parsed in {0:.1f} seconds'.format(time.time()-start_time))
        print('Matched LL file items: \n\t{0:s}'.format('\n\t'.join(['{0:10s}: {1:8d}'.format(
            NetlistCellGroups.to_string(k), v) for k, v in matched_ll_items_per_type.iteritems()])))




