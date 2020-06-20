
from Davos_Generic import *
import struct
import ast
from collections import OrderedDict
import copy



FrameSize = 101                         #Frame size 101 words for 7-Seres and Zynq

class ByteOrder:
    LittleEndian, BigEndian = range(2)

class CLB_LUTS:
    EA, EB, EC, ED, OA, OB, OC, OD  = range(8)

    @staticmethod
    def from_coord(Xcoord, ABCD):
        if Xcoord%2 == 0:
            res = CLB_LUTS.EA if ABCD=='A' else CLB_LUTS.EB if ABCD=='B' else CLB_LUTS.EC if ABCD=='C' else CLB_LUTS.ED
        else:
            res = CLB_LUTS.OA if ABCD=='A' else CLB_LUTS.OB if ABCD=='B' else CLB_LUTS.OC if ABCD=='C' else CLB_LUTS.OD
        return(res)

class FrameDesc:
    def __init__(self, FAR=None):
        if FAR != None:
            self.SetFar(FAR)
        else:
            self.BlockType, self.Top, self.Row, self.Major, self.Minor = 0, 0, 0, 0, 0
        self.data = []
        self.mask = []
        self.custom_mask = []
        self.flags = 0x00000000
        self.EssentialBitsCount = 0
        self.type = 'Unknown'

    def SetFar(self, FAR):
        self.BlockType = (FAR >> 23) & 0x00000007
        self.Top =       (FAR >> 22) & 0x00000001
        self.Row =       (FAR >> 17) & 0x0000001F
        self.Major =     (FAR >>  7) & 0x000003FF
        self.Minor =      FAR  	     & 0x0000007F

    def GetFar(self):
        return( (self.BlockType << 23) |(self.Top << 22) | (self.Row << 17) | (self.Major << 7) | self.Minor )

    def UpdateFlags(self):
        #flag[0] - not_empty - when at least one word is not masked-out
        self.EssentialBitsCount = sum([bin(i).count("1") for i in self.mask])
        if self.EssentialBitsCount > 0:
            self.flags = self.flags | 0x1        

    def get_stat(self):        
        stat={'TotalBits': sum([bin(i).count("1") for i in self.mask]),
              'CustomBits': sum([bin(i).count("1") for i in self.custom_mask])}
        return(stat)
        
        

        

    def MatchedWords(self, Pattern):
        res = 0
        for i in self.data:
            if i == Pattern:
                res+=1
        return(res)
        

    def to_string(self, verbosity=0):
        res = "Frame[{0:08x}]: Block={1:5d}, Top={2:5d}, Row={3:5d}, Major={4:5d}, Minor={5:5d}".format(self.GetFar(), self.BlockType, self.Top, self.Row, self.Major, self.Minor)
        if verbosity > 1:
            res += '\nIndex: ' + ' '.join(['{0:8d}'.format(i) for i in range(len(self.data))])
            res += '\nData : ' + ' '.join(['{0:08x}'.format(i) for i in self.data])
            res += '\nMask : ' + ' '.join(['{0:08x}'.format(i) for i in self.mask])   
            res += '\nCMask: ' + ' '.join(['{0:08x}'.format(i) for i in self.custom_mask])                        
        return(res)




def binary_file_to_u32_list(fname, e):
    res = []
    specificator = '>I' if e==ByteOrder.BigEndian else '<I'
    with open(fname, 'rb') as f:
        while True:
            data = f.read(4)
            if not data: break
            res.append(struct.unpack(specificator, data)[0])
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



def getFarListForTile(TileName):
    match = re.search('(BRAM|CLB).*?X([0-9]+)Y([0-9]+)', TileName)
    res = []
    T_rows, B_rows = 1, 2
    if match:
        X = int(match.group(2))
        Y = int(match.group(3))
        if Y/50 > B_rows-1:
            top, row = 0, Y/50 - B_rows
        else:
            top, row = 1, B_rows - Y/50 - 1
        major = X
        if match.group(1) == 'BRAM':
            for minor in range(28):
                res.append((0x0 << 23) |(top << 22) | (row << 17) | (major << 7) | minor)
    return(res)




def LoadFarList(far_file):
    FarSet = set()
    with open(far_file, 'r') as f:
        for line in f:
            val = re.findall('[0-9abcdefABCDEF]+', line)
            if len(val) > 0: 
                FarSet.add(int('0x'+val[-1], 16))
    FarList = list(FarSet)
    FarList.sort()
    #insert 2 pad frames after each HCLKROW and fix missed frames
    FixFrames=[]
    for i in range(len(FarList)-1):
        F1 = FrameDesc(FarList[i])
        F2 = FrameDesc(FarList[i+1])
        if (F2.BlockType > F1.BlockType) or (F2.Top > F1.Top) or (F2.Row > F1.Row):
            FixFrames.append(FrameDesc(F1.GetFar()+1))
            FixFrames.append(FrameDesc(F1.GetFar()+2))
        delta = F2.Minor - F1.Minor
        if delta > 1:
            for i in range(1,delta):
                FixFrames.append(FrameDesc(F1.GetFar()+i))
    for i in FixFrames:
        FarList.append(i.GetFar())
    FarList.sort()
    return(FarList)    
    

def bitstream_to_FrameList(fname, FarList):
    res = []
    if fname.endswith('.bin'):
        bitstream = binary_file_to_u32_list(fname, ByteOrder.LittleEndian)
    elif fname.endswith('.bit'):
        bitstream = binary_file_to_u32_list(fname, ByteOrder.BigEndian)
    else:
        raw_input('bitstream_to_FrameList: Unknown file format')
        return(none)
    i = 0
    while not (bitstream[i] == 0xaa995566): i+=1
    while i < len(bitstream):
        #Find command: write FAR register
        if bitstream[i]==0x30002001:                    #write FAR register 1 word
            i+=1; FAR = bitstream[i]                    #FAR register value
            startFrameIndex = 0
            while FarList[startFrameIndex] != FAR: startFrameIndex+=1       
            #WCFG command: Write config 
            while not (bitstream[i] == 0x30008001 and bitstream[i+1]==0x00000001): i+=1     #Command register --> WCFG command (write config data)
            while bitstream[i] & 0xFFFFF800 != 0x30004000: i+=1                             #Packet type 1: Write FDRI register
            WordCount = bitstream[i] & 0x7FF; i+=1                                          #if 0 - word count in the next packet type 2
             #big data packet: WordCount in following Type2Packet
            if WordCount == 0: 
                WordCount = bitstream[i] & 0x7FFFFFF; i+=1
            for FrameCnt in range(WordCount/FrameSize):
                if startFrameIndex+FrameCnt >= len(FarList):
                    return(res)
                Frame = FrameDesc(FarList[startFrameIndex+FrameCnt])
                for k in range(FrameSize):
                    Frame.data.append(bitstream[i])
                    Frame.mask.append(0x00000000)
                    i+=1    
                res.append(Frame)
        i+=1
    return(res)


#Parse EBC bitstream file (BlockType 0 only - no BRAM) and essential bits file (ebd)    
def EBC_to_FrameList(ebc_fname, ebd_fname, FarList):
    res = []
    bitstream = []
    maskstream = []
    with open(ebc_fname, 'r') as f:
        for line in f:
            i = re.findall(r'^[01]+', line, flags=re.MULTILINE)
            if len(i) > 0:
                bitstream.append(int(i[0],2))
    with open(ebd_fname, 'r') as f:
        for line in f:
            i = re.findall(r'^[01]+', line, flags=re.MULTILINE)
            if len(i) > 0:
                maskstream.append(int(i[0],2))
    for i in range(len(FarList)):
        F = FrameDesc(FarList[i])
        if F.BlockType > 0: 
            return(res)
        F.data = bitstream[FrameSize + FrameSize*i : FrameSize + FrameSize*(i+1)]
        F.mask = maskstream[FrameSize + FrameSize*i : FrameSize + FrameSize*(i+1)]
        F.UpdateFlags()
        res.append(F)
    return(res)





def ParseBitstream(bitstream_file, far_file):
    FarList = LoadFarList(far_file)
    BIN_FrameList = bitstream_to_FrameList(bitstream_file, FarList)
    print("[               ] : {5}\n\n".format(0, 0, 0, 0, 0, " ".join(["{0:8d}".format(i) for i in range(FrameSize)])))
    for frame in BIN_FrameList: 
        if frame.CountNullWords() != FrameSize:
            print("[{0:2d},{1:2d},{2:2d},{3:2d},{4:3d}] : {5}".format(frame.BlockType, frame.Top, frame.Row, frame.Major, frame.Minor, " ".join(["{0:08x}".format(frame.data[i]) for i in range(FrameSize)])))
        
    

    
    
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
            
                

def SetCustomLutMask(SwBox_top, SwBox_row, SwBox_major, SwBox_minor, LUTCOORD, BIN_FrameList, lutmap, skip_mask=False):
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

def VivadoParseTableToLutList(LutDescTab, ClockRows = 3):
    res=[]
    TopRows, BottomRows = ClockRows/2, ClockRows/2 +  ClockRows%2
    for i in range(LutDescTab.rownum()):
        item = {'name':     LutDescTab.getByLabel('Node', i),
                'celltype': re.findall('(LUT[0-9]+)', LutDescTab.getByLabel('CellType', i))[0],
                'cellloc':  map(int, re.findall('X([0-9]+)Y([0-9]+)', LutDescTab.getByLabel('CellLocation',i))[0]),
                'abcd' :    re.findall('([A-Z]+)[0-9]+', LutDescTab.getByLabel('BEL',i))[0],
                'beltype':  LutDescTab.getByLabel('BellType',i),
                'clkrow':   int(re.findall('Y([0-9]+)', LutDescTab.getByLabel('ClockRegion',i))[0]),
                'tileloc':  map(int, re.findall('X([0-9]+)Y([0-9]+)', LutDescTab.getByLabel('Tile',i))[0]),
                'init':     LutDescTab.getByLabel('INIT',i)
                }
        item['connections'] = dict()
        for c in re.findall('([I0-9]+):([A0-9]+)', LutDescTab.getByLabel('CellConnections',i)):
            item['connections'][c[0]]=c[1]
        if item['clkrow']+1 > BottomRows : #Top part of device
            item['top'], item['row'] = 0, (item['clkrow']-BottomRows)
        else:
            item['top'], item['row'] = 1, (BottomRows-item['clkrow']-1)
        item['major'], item['minor'] = int(item['tileloc'][0]), int(item['tileloc'][1])%50
        item['lutindex'] = CLB_LUTS.from_coord(int(item['cellloc'][0]), item['abcd'])
        item['combcell'] = None
        item['cbelinputs']=[]
        item['Actime'] = []
        item['SwitchCount'] = []
        item['globalmap'] = []
        item['Label']=''
        item['node_main'], item['node_compl'] = None, None
        item['FailureModeEmul'] = []
        item['FailureModeSim']  = []

        res.append(item)
    return(res)


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
    map_L = [63,47,62,46,61,45,60,44,15,31,14,30,13,29,12,28,59,43,58,42,57,41,56,40,11,27,10,26, 9,25, 8,24,55,39,54,38,53,37,52,36, 7,23, 6,22, 5,21, 4,20,51,35,50,34,49,33,48,32, 3,19, 2,18, 1,17, 0,16]
    map_M = [31,15,30,14,29,13,28,12,63,47,62,46,61,45,60,44,27,11,26,10,25, 9,24, 8,59,43,58,42,57,41,56,40,23, 7,22, 6,21, 5,20, 4,55,39,54,38,53,37,52,36,19, 3,18, 2,17, 1,16, 0,51,35,50,34,49,33,48,32]
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
        skip_mask = False if DutScope=='' else (not node['name'].startswith(DutScope))
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

    LutDescTab = Table('LutMap')
    LutDescTab.build_from_csv(LUTMAP_FILE)

    FarList = LoadFarList(FARARRAY_FILE)
    EBC_FrameList = EBC_to_FrameList(Input_EBCFile, Input_EBDFile, FarList)
    BIN_FrameList = bitstream_to_FrameList(BITSTREAM_FILE, FarList)

    mismatches = 0
    for i in range(len(EBC_FrameList)):
        for k in range(FrameSize):
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

    LutMapList = MapLutToBitstream(LutDescTab, BIN_FrameList)

    with open(os.path.join(proj_path, 'ResT.csv'),'w') as f:
        f.write(LutListToTable(LutMapList).to_csv())

    #log non-empty frames
    with open(os.path.join(proj_path,'BitLog.txt'),'w') as f:
        for i in BIN_FrameList:
            if i.flags & 0x1 > 0:
                f.write(i.to_string(2)+'\n\n')


    logfile.close()


