/*
 * SeuInjector.h
 *
 *  Created on: 2 Oct 2018
 *      Author: ILYA Tuzov 
 *              Universidad Politecnica de Valencia
 *  
 *  SEU emulation library for Zynq SoC and 7-Series
 *
 */

#ifndef SRC_SEUINJECTOR_H_
#define SRC_SEUINJECTOR_H_


#include "xil_types.h"
#include "BitArray.h"
#include "xdevcfg.h"

#define DCFG_DEVICE_ID		XPAR_XDCFG_0_DEVICE_ID



/*-------------------------- PCAP and DevConfig handlers------------------------------- */
#define FRAME_SIZE			101
#define MAX_FRAMES 			20000
#define MAX_EXPERIMENTS		5
#define MAX_TRACE_ITEMS		1000
// Addresses of the Configuration Registers
#define XHI_CRC				0
#define XHI_FAR				1
#define XHI_FDRI			2
#define XHI_FDRO			3
#define XHI_CMD				4
#define XHI_CTL				5
#define XHI_MASK			6
#define XHI_STAT			7
#define XHI_LOUT			8
#define XHI_COR				9
#define XHI_MFWR			10
#define XHI_CBC				11
#define XHI_IDCODE			12
#define XHI_AXSS			13
#define XHI_COR_1			14
#define XHI_CSOB			15
#define XHI_WBSTAR			16
#define XHI_TIMER			17
#define XHI_BOOTSTS			22
#define XHI_CTL_1			24
#define XHI_BSPI			31

// Configuration Commands
#define XHI_CMD_NULL			0
#define XHI_CMD_WCFG			1
#define XHI_CMD_MFW				2
#define XHI_CMD_DGHIGH			3
#define XHI_CMD_RCFG			4
#define XHI_CMD_START			5
#define XHI_CMD_RCAP			6
#define XHI_CMD_RCRC			7
#define XHI_CMD_AGHIGH			8
#define XHI_CMD_SWITCH			9
#define XHI_CMD_GRESTORE		10
#define XHI_CMD_SHUTDOWN		11
#define XHI_CMD_GCAPTURE		12
#define XHI_CMD_DESYNCH			13
#define XHI_CMD_IPROG			15
#define XHI_CMD_CRCC			16
#define XHI_CMD_LTIMER			17

#define IDCODE_MASK				0x0FFFFFFF
#define XHI_NOOP_PACKET 		0x20000000	//NO Operation
#define XHI_SYNC_PACKET			0xAA995566
#define XHI_DUMMY_PACKET		0xFFFFFFFF
#define XHI_BUS_WTH_PACKET		0x000000BB
#define	XHI_BUS_DET_PACKET		0x11220044
#define XHI_SHUTDOWN_PACKET		0x0000000B
#define XHI_DEVICE_ID_READ		0x28018001

//SLCR registers
#define SLCR_LOCK	0xF8000004 			// SLCR Write Protection Lock
#define SLCR_UNLOCK	0xF8000008 			// SLCR Write Protection Unlock
#define SLCR_LVL_SHFTR_EN 0xF8000900 	// SLCR Level Shifters Enable
#define SLCR_PCAP_CLK_CTRL XPAR_PS7_SLCR_0_S_AXI_BASEADDR + 0x168 // SLCR PCAP clock control register address
#define SLCR_PCAP_CLK_CTRL_EN_MASK 0x1
#define SLCR_LOCK_VAL	0x767B
#define SLCR_UNLOCK_VAL	0xDF0D
#define XHI_FAR_BLOCK_SHIFT_7 			23
#define XHI_FAR_TOP_BOTTOM_SHIFT_7 		22
#define XHI_FAR_ROW_ADDR_SHIFT_7 		17
#define XHI_FAR_COLUMN_ADDR_SHIFT_7 	 7
#define XHI_FAR_MINOR_ADDR_SHIFT_7 		 0
#define UNUSED_BITS						26
#define FarSetup(Block, Top, Row, ColumnAddress, MinorAddress)  \
		(Block << XHI_FAR_BLOCK_SHIFT_7) | \
		((Top << XHI_FAR_TOP_BOTTOM_SHIFT_7) | \
		(Row << XHI_FAR_ROW_ADDR_SHIFT_7) | \
		(ColumnAddress << XHI_FAR_COLUMN_ADDR_SHIFT_7) | \
		(MinorAddress << XHI_FAR_MINOR_ADDR_SHIFT_7))



#define SLCR_CAN_RST_ADDR 0xF8000220
#define SLCR_CAN_RST_VALUE 0xF
#define SLCR_WDT_CLK_SEL (XPS_SYS_CTRL_BASEADDR + 0x304)
#define SLCR_LOCK_ADDR (XPS_SYS_CTRL_BASEADDR + 0x4)
#define SLCR_UNLOCK_ADDR (XPS_SYS_CTRL_BASEADDR + 0x8)
#define SLCR_FPGA_RST_CTRL_ADDR (XPS_SYS_CTRL_BASEADDR + 0x240)
#define SLCR_LVL_SHFTR_EN_ADDR (XPS_SYS_CTRL_BASEADDR + 0x900)
#define SLCR_LVL_SHFTR_EN_VALUE 0xF
#define SLCR_LOCK_KEY_VALUE 0x767B
#define SLCR_UNLOCK_KEY_VALUE 0xDF0D
#define SLCR_MIO_LOOPBACK (XPS_SYS_CTRL_BASEADDR + 0x804)
#define READ_WRITE_MUL_FACTOR 0x10
#define COUNTS_PER_MICROSECOND COUNTS_PER_SECOND/1000000

//System Level Control registers (see UG585 Appendix B.28 (page 1571)
#define SLCR_CLK0_THROTTLE_CTRL_ADR (XPS_SYS_CTRL_BASEADDR + 0x174) //PL Clock 0 Throttle Control
#define SLCR_CLK0_THROTTLE_CNT_ADR  (XPS_SYS_CTRL_BASEADDR + 0x178) //PL Clock 0 Throttle Count control
#define SLCR_CLK0_THROTTLE_STA_ADR  (XPS_SYS_CTRL_BASEADDR + 0x17C)	//PL Clock 0 Throttle Status read


typedef struct{
	u32 BLOCK;
	u32 TOP;
	u32 HCLKROW;
	u32 MAJOR;
	u32 MINOR;
} FarFields;


typedef struct{
	u32 FailureFlags[FRAME_SIZE];
} InjectionDetail;

typedef struct{
	u32  FAR;
	u32  Flags;	//flags[0] - not empty (at least one word is not masked), flags[1] - is pad frame / is injectable
	u32  EssentialBitsCount;
	u32  Data[FRAME_SIZE];
	u32  Mask[FRAME_SIZE];
	u32	 Tested[FRAME_SIZE];	//to keep track of tested bits
	InjectionDetail* InjResult[MAX_EXPERIMENTS];
} FrameDescriptor;


typedef struct{
	u32 BitstreamId;
	u32 SyncTag;
	u32 BitstreamAddr;
	u32 BitstreamSize;
	u32 BitmaskAddr;
	u32 BitmaskSize;
	u32 UpdateBitstream;
	u32 mode;				//0 handshake and exit, 1- cleanup (SD card cache) and exit, 2 - SEU injection sampling, 3 - SEU  injection exhaustive, 4 - profiling
	u32 BlockType;			//0 - CLB, 1 - BRAM, >=2 Any
	u32 Essential_bits;		//0 - target all bits, 1 - only masked bits
	u32 CheckRecovery;		//> 0 - rerun workload to check is system continues to work after CheckRecovery experiments
	u32 LogTimeout;			//Intermediate result will be reported to console each time LogTimeout experiments are completed
	u32 StartIndex;
	u32 ExperimentsCompleted;
	u32 CurrentFailureCount;
	u32 CurrentMaskedCount;
	u32 CurrentLatentCount;
	u32 CurrentSDCCount;
	u32 SampleSizeGoal;
	float ErrorMarginGoal;
	u32 FaultMultiplicity;
} JobDescriptor;


typedef struct{
	u32 FAR;
	u32 word;
	u32 bit;
	int FrameIndex;
} InjectionCoorditates;





typedef struct{
    XDcfg  DevConigInterface;		// Device Configuration Interface Instance
    XDcfg* DevcI;
    XDcfg_Config *ConfigPtr;

    FrameDescriptor ReferenceFrames[MAX_FRAMES];
    u32 FrameDescriptorsCount, ClbFramesCount, RambFramesCount;
    FrameDescriptor RecoveryDescriptorList[MAX_FRAMES];			//FRAMES to recover after each injection (e.g. ROM frames)
    u32 RecoveryFarCount;
    u32 LastTargetedFrames[MAX_FRAMES];		//List of frames (indexes in ReferenceFrames list) targeted since last recovery
    u32 LastTargetedFramesCount;
    u32 EssentialBitsPerBlockType[8];

    u32 FrameBuffer[FRAME_SIZE*2];  		//For readFrame intermediate
    u32 ReadFrameData[FRAME_SIZE];  		//Readback Frame Data to pass from readFrame
    u32 WriteFrameData[FRAME_SIZE];			//Write Frame Data to pass to writeFrame
    u32 WriteBuffer[300+FRAME_SIZE*1000];	//For custom bitstream (writeFrame, writeFrames)
    u32 FarItems[MAX_FRAMES] ;      		//valid FAR indexes obtained at profiling (FAR auto-increment mode)
    int FramesCount;						//number of valid FAR indexes
    int BramMaskedIndexes[FRAME_SIZE];
    int BramMaskedCount;

    int cache_enabled;
    int (*WorkloadRunFunc)(int);

} InjectorDescriptor;

void PrintInjectorInfo(InjectorDescriptor* InjDesc);


typedef struct{
	int failures;
	int masked;
	int injections;
	double failure_rate;
	double failure_error_margin;
	double masked_rate;
	double masked_error_margin;
	int complete_reconfigurations;
	int population;
} InjectionStatistics;




int InjectorInitialize(InjectorDescriptor * InjDesc, u16 DeviceId, int (*WorkloadRunFunc)());
void SetReferenceTrace(InjectorDescriptor * InjDesc, u32* RefVect);
InjectionStatistics InjectorRun(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc,  int (*CustomInjectionFlow)(InjectorDescriptor* , JobDescriptor* ));
InjectionStatistics RunInSamplingMode(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc,  int (*CustomInjectionFlow)(InjectorDescriptor* , JobDescriptor* ), int verbose);
InjectionStatistics RunInExhaustiveMode(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, u32* FarFirst, u32* FarLast, int verbose, int expId);
InjectionCoorditates NextRandomInjectionTarget(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc);

void saveInjectionTarget(InjectorDescriptor* InjDesc, u32 TargetedFrameIndex);
int recoverInjectedFrames(InjectorDescriptor* InjDesc);


u32 Type1_Packet(u32 Opcode, u32 RegAdr, u32 WordCnt);
u32 Type2_Packet(u32 Opcode, u32 WordCnt);
FarFields parseFAR(u32 FAR);
int XDcfg_GetConfigReg(InjectorDescriptor* InjDesc, u32 ConfigReg, u32 *RegData);
int readFrame(InjectorDescriptor* InjDesc, long Top,  long Block, long HClkRow, long MajorFrame, long MinorFrame, u32 *FrameData);
int writeFrame(InjectorDescriptor* InjDesc, long Top,  long Block, long HClkRow, long MajorFrame, long MinorFrame, u32 *FrameData);
int writeFrames(InjectorDescriptor* InjDesc, int StartIndex, u32 FrameCount, FrameDescriptor* FrameArray);
int ProfileFarMap(InjectorDescriptor* InjDesc, u32* FarDesc, u32 BlockType, u32 Top);
void ReadbackTest(int blocktype);
int FaultInjectionTest(InjectorDescriptor * InjDesc, FarFields Adr, int byteIndexToFlip, int verbose);
int IsExcluded(u32 item);
void RetrieveInjectableFrames();
void MaskFrameData(InjectorDescriptor* InjDesc, FarFields FC, u32 *FrameData);
int IsMaskableWordIndex(InjectorDescriptor* InjDesc, FarFields FC, u32 index);
int FlipBits(InjectorDescriptor* InjDesc, InjectionCoorditates target, u32 mask, int verbose);
int WriteVerifyFrame(InjectorDescriptor* InjDesc, u32 FAR, u32* WriteData);
void print_frame(FrameDescriptor* Frame);

int ReloadCompleteBitstream(XDcfg *Instance, u32 StartAddress, u32 WordLength);
void ReRunWorkload();
void CaptureTraceVector(u32* ResVector);
int recover_bitstream(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int RecoverFrameList);
void InitInjectorFromDesignDescriptionFile(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);
void InitInjectionDescriptors();
void FilterFrameDescriptors(InjectorDescriptor* InjDesc, FrameDescriptor* FrameDesc, int DescCount, int BuildMask, int log_verbosity);
BitArray GetInjectableWords(InjectorDescriptor* InjDesc, FarFields FC);




int cmpfuncInt (const void * a, const void * b);
int cmpfuncFrameDescriptor (const void * a, const void * b);
u32 set_bit(u32 data, u32 bit_index, u32 val);
u32 get_bit(u32 data, u32 bit_index);
int getIndexbyFAR(u32 FAR);


void sleep(unsigned int microseconds);
void ResetPL(u32 duration_us);
void ClockThrottle(u32 mask);
void RunClockCount(u16 clknum);



int input_int();
void readconsole(char readbuf[]);
int GetFileList(FILINFO FileDesc[]);


#endif /* SRC_SEUINJECTOR_H_ */
