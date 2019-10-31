
from Davos_Generic import *
import struct
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
        self.EssentialBitsCount = 0
        for i in self.mask:
            for bit in range(32):
                if (i >> bit) & 0x1 == 1:
                    self.EssentialBitsCount += 1
        if self.EssentialBitsCount > 0:
            self.flags = self.flags | 0x1        


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
        if bitstream[i]==0x30002001:
            i+=1; FAR = bitstream[i]
            startFrameIndex = 0
            while FarList[startFrameIndex] != FAR: startFrameIndex+=1
            #WCFG command: Write config 
            while not (bitstream[i] == 0x30008001 and bitstream[i+1]==0x00000001): i+=1
            while bitstream[i] & 0xFFFFF800 != 0x30004000: i+=1
            WordCount = bitstream[i] & 0x7FF; i+=1
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
            
                

def SetCustomLutMask(SwBox_top, SwBox_row, SwBox_major, SwBox_minor, LUTCOORD, BIN_FrameList, lutmap):
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
                    F[3-quarter].custom_mask[offset] |= (0x1 << bit_index)
                    #global mapping
                    x.append((F[3-quarter].GetFar(), offset, bit_index))
                globalmap.append(x)
            return(INIT, globalmap)     