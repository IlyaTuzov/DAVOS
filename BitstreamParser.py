from Davos_Generic import *
from collections import OrderedDict
import copy
from XilinxInjector.BitstreamParseLib import *

def get_lut_to_bel_map(cellType, BelEquation):
    inputnum = int(re.findall('LUT([0-9]+)', cellType)[0])
    for i in range(10): BelEquation = BelEquation.replace('A{0:d}+~A{0:d}'.format(i),'')
    for term in BelEquation.split('+'):
        vardict = OrderedDict.fromkeys(re.findall('(A[0-9]+)', term))
        if len(vardict) == inputnum:
            return( OrderedDict(zip(['I{0:d}'.format(i) for i in range(inputnum)], vardict.keys())) )

def TableToLutList(LutDescTab, ClockRows = 3):
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
        res.append(item)
    return(res)


def LutListToTable(LutList):
    res = Table('Luts')
    for lbl in ['name', 'celltype','cellloc','abcd' ,'beltype','clkrow','tileloc','init', 'connections', 'lutindex', 'combcell', 'bitsequence', 'bit_i', 'match', 'cbelinputs']:
        res.add_column(lbl, map(str, [LutList[i][lbl] for i in range(len(LutList))]))
    return(res)


def MapLutToBitstream(LutDescTab, BIN_FrameList):
    LutCells = TableToLutList(LutDescTab)
    for i in range(len(LutCells)):
        if LutCells[i]['combcell']==None:
            for j in range(i+1, len(LutCells)):
                if LutCells[i]['cellloc'] == LutCells[j]['cellloc'] and LutCells[i]['abcd'] == LutCells[j]['abcd']:
                    LutCells[i]['combcell'] = LutCells[j]
                    LutCells[i]['cbelinputs'] = list( set(LutCells[j]['connections'].values()) - set(LutCells[i]['connections'].values()) )
                    LutCells[j]['combcell'] = LutCells[i]
                    LutCells[j]['cbelinputs'] = list( set(LutCells[i]['connections'].values()) - set(LutCells[j]['connections'].values()) )
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
            rows = Map.search_rows(r,0)
            res.append(  [val[-1] for val in rows ] )     
        node['bitsequence'] = ','.join(map(str, res))

        #2. GET LUT BEL content from bitstream
        BITSTREAM = SetCustomLutMask(node['top'], node['row'], node['major'], node['minor'], node['lutindex'], BIN_FrameList, res)
        BIT_INIT = 0x0000000000000000
        w = 2**len(node['connections'])
        for bit in range(w): 
            BIT_INIT = BIT_INIT | (((BITSTREAM>>res[bit][0])&0x1)<<bit)

        node['bit_i'] =  '{bits}\'h{num:0{width}X}'.format(bits=w,num=BIT_INIT, width=w/4)
        node['match'] = 'Y' if node['init'] == node['bit_i'] else 'N'

    T = LutListToTable(LutCells)
    with open('ResT.csv','w') as f:
        f.write(T.to_csv())


if __name__ == "__main__":


    verbosity = 1
    logfile = open('C:/Projects/Profiling/Models/MC8051_ZC/parselog.txt','w')
    LUTMAP_FILE = 'C:/Projects/Profiling/Models/MC8051_ZC/LUTMAP.csv'
    SHADOWLUTS_FILE = 'C:/Projects/Profiling/Models/MC8051_ZC/SHADOWLUTS.csv'
    FARARRAY_FILE = 'C:/Projects/Profiling/Models/MC8051_ZC/FarArray.txt'
    BITSTREAM_FILE = 'C:/Projects/Profiling/Models/MC8051_ZC/Bitstream.bin'
    Input_EBCFile = 'C:/Projects/Profiling/Models/MC8051_ZC/Bitstream.ebc'
    Input_EBDFile = 'C:/Projects/Profiling/Models/MC8051_ZC/Bitstream.ebd'

    LutDescTab = Table('LutMap')
    LutDescTab.build_from_csv(LUTMAP_FILE)
    ShadowLutsTab = Table('ShadowLuts')
 

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



    MapLutToBitstream(LutDescTab, BIN_FrameList)









    #log non-empty frames
    with open('C:/Projects/Profiling/Models/MC8051_ZC/BitLog.txt','w') as f:
        for i in BIN_FrameList:
            if i.flags & 0x1 > 0:
                f.write(i.to_string(2)+'\n\n')


    with open(LUTMAP_FILE.replace('.csv','_res.csv'), 'w') as f:
        f.write(LutDescTab.to_csv())

    logfile.close()


