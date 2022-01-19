# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

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
from SBFI.SBFI_Profiler import *



#Export Frame Descriptors File (N frame items: {u32 FAR, u32 flags, FrameSize word items: {u32 data[i], u32 mask[i]}}
# | DescriptorList_offset,  DescriptorList_items                | 4B + 4B
# | RecoveryFrames_offset,  RecoveryFrames_items                | 4B + 4B
# | <-- DescriptorList_offset = 16                              | 
# | FAR_0, flags, NumOfEsBits, FrameSize x {data[i], mask[i]}   | 4B + 4B + 4B + (4B + 4B)x101 = 416B
# | ....                                                        | ... 416B x DescriptorList_items
# | <-- RecoveryFrames_offset = 16+ 412B xDescriptorList_items  |
# | FAR_0, FAR_1, ...                                           |       4B x RecoveryFrames_items
def export_DescriptorFile(fname, BIN_FrameList, RecoveryFrames):
    specificator = '<I'         #Little Endian
    with open(os.path.join(os.getcwd(), fname), 'wb') as f:
        f.write(struct.pack(specificator, 16))                      # DescriptorList_offset
        f.write(struct.pack(specificator, len(BIN_FrameList)))          # DescriptorList_items
        f.write(struct.pack(specificator, 16 + (12+8*FrameSize)*len(BIN_FrameList)))   # RecoveryFrames_offset
        f.write(struct.pack(specificator, len(RecoveryFrames)))     # RecoveryFrames_items
        for frame in BIN_FrameList:                                     # 416B x DescriptorList_items
            frame.UpdateFlags()
            f.write(struct.pack(specificator, frame.GetFar()))
            f.write(struct.pack(specificator, int(frame.flags)))
            f.write(struct.pack(specificator, int(frame.EssentialBitsCount)))
            for i in range(FrameSize):
                f.write(struct.pack(specificator, frame.data[i]))
                f.write(struct.pack(specificator, frame.mask[i]))    
        for item in RecoveryFrames:                                 # 4B x RecoveryFrames_items
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





def GenerateFaultload(targetDir, DAVOS_Config, logfile, verbosity, Input_FarListFile, Input_EBCFile, Input_EBDFile, Input_BinstreamFile, CustomLutMask):
    Output_FrameDescFile = os.path.join(targetDir, 'FrameDescriptors.dat')
    FaultListFile = os.path.join(targetDir, 'FaultList.dat')
    LutMapFile = os.path.join(targetDir, 'LutMapList.csv')
    if os.path.exists(Output_FrameDescFile):
        return(Output_FrameDescFile, FaultListFile, LutMapFile)

    #Step 1: Build the list of frame addresses: from input file, build it if not exist (run profiler through xcst)
    FarList = LoadFarList(Input_FarListFile)
    check  = dict()
    for i in FarList:
        F = FrameDesc(i)
        key = "{0:02d}_{1:02d}_{2:02d}_{3:02d}".format(F.BlockType, F.Top, F.Row, F.Major)
        if key in check:
            check[key] += 1
        else:
            check[key]=0
    if verbosity > 1:
        for k,v in sorted(check.items(), key=lambda x:x[0]):
            logfile.write('{0:s} = {1:d}\n'.format(k, v))        
    #Step 2: Build the list of frame descriptors from EBC+EBD (essential bits)
    EBC_FrameList = EBC_to_FrameList(Input_EBCFile, Input_EBDFile, FarList)
               
    #Step 3: Build the list of frame discriptors for complete bitstream (*.bit or *.bin)
    BIN_FrameList = parse_bitstream(Input_BinstreamFile, FarList)

    #Step 4: Compare BIN to EBC and If no mismatches found
    #        copy essential bits (mask from) to BIN (all descriptors will be collected there)
    mismatches = 0
    for i in range(len(EBC_FrameList)):
        for k in range(FrameSize):
            if EBC_FrameList[i].data[k] != BIN_FrameList[i].data[k]:
                if verbosity > 0:
                    logfile.write('Check EBC vs BIT: mismatch at Frame[{0:08x}]: Block={1:5d}, Top={2:5d}, Row={3:5d}, Major={4:5d}, Minor={5:5d}\n'.format(BIN_FrameList[i].GetFar(), BIN_FrameList[i].BlockType, BIN_FrameList[i].Top, BIN_FrameList[i].Row, Major, BIN_FrameList[i].Minor))
                mismatches+=1
    if mismatches == 0: logfile.write('\nCheck EBC vs BIT: Complete Match\n')
    else: logfile.write('Check EBC vs BIT: Mismatches Count = {0:d}\n'.format(mismatches))
    if mismatches ==0:
        for i in range(len(EBC_FrameList)):
            BIN_FrameList[i].mask = EBC_FrameList[i].mask

    if CustomLutMask:
        LutDescTab = Table('LutMap'); LutDescTab.build_from_csv(os.path.join(targetDir, 'LUTMAP.csv'))
        print('Mapping LUTs to bitstream')
        LutMapList = MapLutToBitstream(LutDescTab, BIN_FrameList)
        with open(LutMapFile,'w') as f:
            f.write(LutListToTable(LutMapList).to_csv())
        if DAVOS_Config != None and DAVOS_Config.FFIConfig.profiling: 
            if not os.path.exists(FaultListFile):
                print('Profiling LUTs switching activity')
                ProfilingResult = Estimate_LUT_switching_activity(LutMapList, DAVOS_Config)
                ExportFaultList(ProfilingResult, FaultListFile)
            else:
                ProfilingResult = LoadFaultList(FaultListFile) #load from file
            with open(LutMapFile,'w') as f:
                f.write(LutListToTable(LutMapList).to_csv())


        with open(os.path.join(targetDir,'BitLog.txt'),'w') as f:
            for i in BIN_FrameList:
                if all(v==0 for v in i.custom_mask): continue
                else: 
                    f.write(i.to_string(2)+'\n\n')
                

        for i in BIN_FrameList:
            if i.custom_mask==[]:
                i.mask = [0x0]*FrameSize
            else:
                for k in range(FrameSize):
                    i.mask[k] = i.custom_mask[k] #(i.mask[k] ^ i.custom_mask[k]) & i.mask[k]
        #raw_input('Difference with custom mask...')
            



    #Step 5: append descriptors for FAR items which should be recovered after injection (BRAM) 
    RecoveryRamLocations = []
    FAR_CLB = set()
    T = Table('Cells')
    T.build_from_csv(Input_CellDescFile)
    for node in RecoveryNodeNames:
        #print("Locations for {}".format(node))
        for i in T.query({'Node':node, 'BellType':'RAMB'}):
            RecoveryRamLocations.append(i['CellLocation']) 
    #print("Recovery Ram Locations: {}".format(str(RecoveryRamLocations)) )
    logfile.write('Recovery RAM Location: ' + str(RecoveryRamLocations)+'\n')        
    #Set mask=1 for all bits of used BRAM (from *.ll file)
    #And build FAR recovery list - include all FAR from *.ll file containing bits of selected design units (e.g. ROM inferred on BRAM)
    FARmask = dict()
    RecoveryFrames = set()
    with open(Input_LLFile, 'r') as f:
        for line in f:
            matchDesc = re.search(r'([0-9abcdefABCDEF]+)\s+([0-9]+)\s+Block=([0-9a-zA-Z_]+)\s+Ram=B:(BIT|PARBIT)([0-9]+)',line, re.M)
            if matchDesc:
                FAR = int(matchDesc.group(1), 16)
                offset = int(matchDesc.group(2))
                block = matchDesc.group(3)
                if block in RecoveryRamLocations:
                    RecoveryFrames.add(FAR)
                word=offset/32
                bit = offset%32
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
                if verbosity > 2: logfile.write("{0:08x} : {1:s}\n".format(i.GetFar(), ' '.join(['{0:08x}'.format(x) for x in i.mask])))
                break
    logfile.write('Recovery FAR: {}\n'.format(",".join(["{0:08x}".format(i) for i in sorted(list(RecoveryFrames))])))
    #Export the resulting descriptor
    export_DescriptorFile(Output_FrameDescFile, BIN_FrameList, RecoveryFrames)
    populationsize = 0
    for i in list(range(0, 9)): EssentialBitsPerBlockType.append(0)
    for i in BIN_FrameList:
        populationsize += i.EssentialBitsCount
        EssentialBitsPerBlockType[i.BlockType] += i.EssentialBitsCount
        #logfile.write('FAR: {0:08x} = {1:5d} Essential bits\n'.format(i.GetFar(), i.EssentialBitsCount))
    print("Essential bits per type: "+str(EssentialBitsPerBlockType))
    logfile.write('Population Size: {0:10d}\n'.format(populationsize))

    return(Output_FrameDescFile, FaultListFile, LutMapFile)