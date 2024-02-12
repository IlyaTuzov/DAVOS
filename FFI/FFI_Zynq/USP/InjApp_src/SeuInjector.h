#ifndef BAFFI_DEF

#include "xtime_l.h"

#define HOST_BUF 			0x7DF00000
#define HOST_SOCKET_ADR 	(HOST_BUF+0x0)
#define HOST_FAULT_LIST_ADR (HOST_BUF+0x200)
#define HOST_BITSTREAM 		(HOST_BUF+0x100000)
//dow -data /home/tuil/Lenet5/MiniLenetFloat_22/DavosGenerated/Faultlist_0.bin 0x7DF00200


#define GPIO_DEVICE_ID		XPAR_XGPIOPS_0_DEVICE_ID
#define PL0_THR_CTRL 0x00FF5E00D0
#define PL0_THR_CNT 0x00FF5E00D4
#define GPIO_MASK_DATA_5_MSW_OFFSET  0XFF0A002C
#define GPIO_DIRM_5_OFFSET           0XFF0A0344
#define GPIO_OEN_5_OFFSET            0XFF0A0348
#define GPIO_DATA_5_OFFSET           0XFF0A0054
#define PL0_THR_CTRL_OFFSET 		 0xFF5E00D0
#define PL0_THR_CNT_OFFSET 			 0xFF5E00D4

#define IDCODE_MASK				0x0FFFFFFF
#define XHI_NOOP_PACKET 		0x20000000
#define XHI_SYNC_PACKET			0xAA995566
#define XHI_DUMMY_PACKET		0xFFFFFFFF
#define XHI_BUS_WTH_PACKET		0x000000BB
#define	XHI_BUS_DET_PACKET		0x11220044
#define XHI_SHUTDOWN_PACKET		0x0000000B
#define XHI_DEVICE_ID_READ		0x28018001v


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

#define XHI_TYPE_1_PACKET_MAX_WORDS 2048

#define FRAME_SIZE 93
#define PAD_WORDS 25


typedef enum{
	S7 = 1,
	US = 2,
	USP = 3
} FpgaSeries;


typedef struct{
	u32 BLOCK ;
	u32 TOP;
	u32 HCLKROW;
	u32 MAJOR;
	u32 MINOR;
} FarFields;


typedef struct{
	u32 Id;
	u32 Offset;
	u32 CellType;
	u32 FaultModel;
	u32 SLR;
	u32 FAR;
	u32 word;
	u32 mask;
	u32 time;
	u32 Duration;
	u32 ReferenceWordData;
} FaultDescriptor;




typedef enum {
	Unknown	 ,
	Masked 	 ,
	Latent 	 ,
	Hang	 ,
	SDC		 ,
	Signalled,
	NUM_FAILURE_MODES
} FailureMode;

static const char *FailureModeLabels[NUM_FAILURE_MODES] = {"Unknown", "Masked", "Latent", "Hang", "SDC", "Signalled"};


typedef struct{
	u32 			SlrId[10];
	uint32_t 		* host_socket_ptr;
	FaultDescriptor * fault_list_ptr;
	u32 			FrameData[FRAME_SIZE];
	u32 			DebugMode;
	u32				FaultListSize;
	u32				StatFmodeCount[NUM_FAILURE_MODES];
	XTime			Tstart;
} InjectorDescriptor;



u32 FPGA_ReadFrame(u32 FAR, u32 *FrameBuffer);
u32 FPGA_WriteFrame(u32 FAR, u32 *FrameBuffer, u32 SlrIDcode);
int ProcessFaultDescriptor(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc, int recover);
int Inject(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc);
int Recover(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc);



void PSU_Mask_Write(unsigned long offset, unsigned long mask, unsigned long val);
unsigned long PL_reset();
void RunClock(u32 cnum);
void WaitClockStops();
char *Fmode_to_string(FailureMode f);
void Log_Result(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc, FailureMode fmode, char *message);
void get_stat_msg(InjectorDescriptor *InjDesc, char *buffer);

#endif
