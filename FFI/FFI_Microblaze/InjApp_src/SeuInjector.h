 /*
 FPGA-based fault injection library for ICAP-based applications

 --------------------------------------------------------------------------------------------
 Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
 Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
 --------------------------------------------------------------------------------------------
*/


#define FRAME_SIZE 101
#define HWICAP_DEVICEID			XPAR_HWICAP_0_DEVICE_ID


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
#define XHI_NOOP_PACKET 		0x20000000
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






#define printf  xil_printf
#define CLK_CTRL_BASE 0x44A00000
#define HOST_BUF 			0x20000
#define HOST_SOCKET_ADR 	(HOST_BUF+0x0)
#define HOST_FAULT_LIST_ADR (HOST_BUF+0x200)



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
	u32 SLR;
	u32 FAR;
	u32 word;
	u32 mask;
	u32 time;
} FaultDescriptor;


typedef struct{
	XHwIcap_Config *CfgPtr;
	XHwIcap HwIcap;
	XGpio Gpio;
	uint32_t 		* clock_ctrl_ptr;
	uint32_t 		* host_socket_ptr;
	FaultDescriptor * fault_list_ptr;
	u32 			FrameData[FRAME_SIZE];
	u32 			DebugMode;
} InjectorDescriptor;


int readFrame(XHwIcap *InstancePtr, u32 FAR, u32 *FrameBuffer, int Capture);
int writeFrame(XHwIcap *InstancePtr, u32 FAR, u32 *FrameData, int Restore);
int FlipBits(InjectorDescriptor * InjDesc, int FdescOffset);
void log_Frame(InjectorDescriptor * InjDesc, u32 FAR);

FarFields parseFAR(u32 FAR);
int input_int();
int cmpfunc (const void * a, const void * b);

