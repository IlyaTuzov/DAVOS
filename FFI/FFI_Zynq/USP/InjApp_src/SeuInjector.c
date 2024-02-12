


#include <stdio.h>
#include <stdlib.h>
#include "platform.h"
#include "xilfpga.h"
#include "xilfpga_pcap.h"
//#include "xilfpga_pcap.lc"
#include "/opt/Xilinx/Vitis/2022.2/data/embeddedsw/lib/sw_services/xilfpga_v6_3/src/interface/zynqmp/xilfpga_pcap.c"
#include "SeuInjector.h"


u32 PCAP_DataBuffer[1000];



int InjectorInitialize(InjectorDescriptor *InjDesc){
	printf("Initializing fault injector\n");
	InjDesc->host_socket_ptr   = (uint32_t*) HOST_SOCKET_ADR;
	InjDesc->SlrId[0] = 0x04a5a093;
	//InjDesc->SlrId[1] = 0x04b22093;
	//InjDesc->SlrId[2] = 0x04b24093;
	InjDesc->DebugMode = 1;

	if( *((u32*)(HOST_FAULT_LIST_ADR + 0x0)) != 0xFA01FA01){
		printf("Error: fault list synq word not found\n");
		return(1);
	}
	InjDesc->FaultListSize = *((u32*)(HOST_FAULT_LIST_ADR + 4));
	printf("Fault list size: %d\n", InjDesc->FaultListSize);
	InjDesc->fault_list_ptr    = (FaultDescriptor*) (HOST_FAULT_LIST_ADR + 0x40);
	u32 RefDataFlag = *((u32*)(HOST_FAULT_LIST_ADR + 8));
	//RefDataFlag = 0;

	u32 data[FRAME_SIZE];
	FaultDescriptor * fdesc;
	if(RefDataFlag == 0){
		for(int i=0;i<InjDesc->FaultListSize;i++){
			fdesc = InjDesc->fault_list_ptr + i;
			FPGA_ReadFrame(fdesc->FAR, data);
			fdesc->ReferenceWordData = data[fdesc->word];
			printf("ReferenceWordData[%d] = 0x%08x\n", i, fdesc->ReferenceWordData);
		}
	}
	printf("Encodingn of failure modes:\n");
	for(int i=Masked;i<=Signalled;i++){
		printf("\tFailureMode[%d] = %s\n", i, FailureModeLabels[i]);
	}
	XTime_GetTime(&InjDesc->Tstart);
	return(0);
}

void get_stat_msg(InjectorDescriptor *InjDesc, char *buffer){
	u32 total = 0;
	for(int i=0;i<NUM_FAILURE_MODES;i++){ total+=InjDesc->StatFmodeCount[i]; }
	sprintf(buffer, "Frate: ");
	for(int i=0;i<NUM_FAILURE_MODES;i++){
		float f_rate = (100.0* InjDesc->StatFmodeCount[i]) / total;
		sprintf(buffer + strlen(buffer), "%s= %d (%0.2f%%), ", FailureModeLabels[i], InjDesc->StatFmodeCount[i], f_rate);
	}
}


void Log_Result(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc, FailureMode fmode, char *message){
	InjDesc->StatFmodeCount[fmode]++;
	char buffer[255];
	get_stat_msg(InjDesc, buffer);
	XTime CTime;
	XTime_GetTime(&CTime);
	printf("[%8.5f s] FaultId=%5d, Fmode= %15s, %s :: %s\n",
			1.0*(CTime-InjDesc->Tstart)/(COUNTS_PER_SECOND), fdesc->Id,
			FailureModeLabels[fmode], buffer, message);
}


int ProcessFaultDescriptor(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc, int recover){
	u32 current_id;
	FaultDescriptor *f_item = fdesc;
	u32 Id = f_item->Id;
	do{
		//printf("Processing fault descriptor at: 0x%08x\n", (u32) fdesc);
		if(recover){
			Recover(InjDesc, f_item);
		}
		else{
			Inject(InjDesc, f_item);
		}
		f_item++;
	} while(Id == f_item->Id);

	return(0);
}


int Inject(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc){
	if(InjDesc->DebugMode) printf("Injecting: Id=%3d, CellType=%1d, FAR=%08x, word=%3d, mask=%08x, time=%6d\n", fdesc->Id, fdesc->CellType, fdesc->FAR, fdesc->word, fdesc->mask, fdesc->time);
	int Status = FPGA_ReadFrame(fdesc->FAR, InjDesc->FrameData);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	//Check or save reference data
	if(InjDesc->FrameData[fdesc->word] != fdesc->ReferenceWordData){
		printf("WARNING: ReferenceWordData mismatch (%08x != %08x)\n", InjDesc->FrameData[fdesc->word], fdesc->ReferenceWordData);
	}
	//Apply fault mask to the selected FAR and Word
	InjDesc->FrameData[fdesc->word] = InjDesc->FrameData[fdesc->word] ^ fdesc->mask;
	Status = FPGA_WriteFrame(fdesc->FAR, InjDesc->FrameData, InjDesc->SlrId[0]);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Write Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	return(0);
}


int Recover(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc){
	if(InjDesc->DebugMode) printf("Recovering: Id=%3d, CellType=%1d, FAR=%08x, word=%3d, mask=%08x, time=%6d\n", fdesc->Id, fdesc->CellType, fdesc->FAR, fdesc->word, fdesc->mask, fdesc->time);
	int Status = FPGA_ReadFrame(fdesc->FAR, InjDesc->FrameData);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	//InjDesc->FrameData[fdesc->word] = fdesc->ReferenceWordData;
	InjDesc->FrameData[fdesc->word] = InjDesc->FrameData[fdesc->word] ^ fdesc->mask;
	Status = FPGA_WriteFrame(fdesc->FAR, InjDesc->FrameData, InjDesc->SlrId[0]);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Write Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	return(0);
}

u32 FPGA_ReadFrame(u32 FAR, u32 *FrameBuffer){
	u32 Status = XFPGA_FAILURE;
	u32 NumFrames = 2*FRAME_SIZE + PAD_WORDS;
	u32 RegVal;
	u32 cmdindex;
	u32 CmdBuf[XFPGA_DATA_CONFIG_CMD_LEN];
	s32 i;

	Status = XFpga_GetFirmwareState();

	/* Enable the PCAP clk */
	RegVal = Xil_In32(PCAP_CLK_CTRL);
	RegVal |= 0x3F00U;
	Xil_Out32(PCAP_CLK_CTRL, RegVal | PCAP_CLK_EN_MASK);

	/* Take PCAP out of Reset */
	Status = XFpga_PcapInit(1U);
	if (Status != XFPGA_SUCCESS) {
		Status = XPFGA_ERROR_PCAP_INIT;
		Xfpga_Printf(XFPGA_DEBUG, "PCAP init failed\n\r");
		goto END;
	}
	cmdindex = 0U;

	/* Step 1 */
	CmdBuf[cmdindex] = 0xFFFFFFFFU; /* Dummy Word */
	cmdindex++;
	CmdBuf[cmdindex] = 0x000000BBU; /* Bus Width Sync Word */
	cmdindex++;
	CmdBuf[cmdindex] = 0x11220044U; /* Bus Width Detect */
	cmdindex++;
	CmdBuf[cmdindex] = 0xFFFFFFFFU; /* Dummy Word */
	cmdindex++;
	CmdBuf[cmdindex] = 0xAA995566U; /* Sync Word */
	cmdindex++;

	/* Step 2 */
	CmdBuf[cmdindex] = 0x02000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;
	/* Step 3 */         /* Type 1 Write 1 Word to CMD */
	//CmdBuf[cmdindex] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	//cmdindex++;
	//CmdBuf[cmdindex] = 0x0000000BU; /* SHUTDOWN Command */
	//cmdindex++;
	//CmdBuf[cmdindex] = 0x02000000U; /* Type 1 NOOP Word 0 */
	//cmdindex++;

	/* Step 4 */         /* Type 1 Write 1 Word to CMD */
	CmdBuf[cmdindex] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	cmdindex++;
	CmdBuf[cmdindex] = 0x00000007U; /* RCRC Command */
	cmdindex++;
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	/* Step 5 --- 5 NOOPS Words */
	for (i = 0 ; i < (s32)5 ; i++) {
		CmdBuf[cmdindex] = 0x20000000U;
		cmdindex++;
	}

	/* Step 6 */         /* Type 1 Write 1 Word to CMD */
	CmdBuf[cmdindex] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	cmdindex++;
	CmdBuf[cmdindex] = 0x00000004U; /* RCFG Command */
	cmdindex++;
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	/* Step 7 */         /* Type 1 Write 1 Word to FAR */
	CmdBuf[cmdindex] = Xfpga_RegAddr(FAR1, OPCODE_WRITE, 0x1U);
	cmdindex++;
	CmdBuf[cmdindex] = FAR;
	cmdindex++;

	/* Step 8 */          /* Type 1 Read 0 Words from FDRO */
	CmdBuf[cmdindex] =  Xfpga_RegAddr(FDRO, OPCODE_READ, 0U);
	cmdindex++;
			      /* Type 2 Read Wordlenght Words from FDRO */
	CmdBuf[cmdindex] = Xfpga_Type2Pkt(OPCODE_READ, NumFrames);
	cmdindex++;

	/* Step 9 --- 64 NOOPS Words */
	for (i = 0 ; i < (s32)64 ; i++) {
		CmdBuf[cmdindex] = 0x20000000U;
		cmdindex++;
	}

	XCsuDma_EnableIntr(CsuDmaPtr, XCSUDMA_DST_CHANNEL,
			   XCSUDMA_IXR_DST_MASK);

	/* Flush the DMA buffer */
	Xil_DCacheFlushRange(PCAP_DataBuffer, NumFrames * 4U);

	/* Set up the Destination DMA Channel*/
	XCsuDma_Transfer(CsuDmaPtr, XCSUDMA_DST_CHANNEL,
			PCAP_DataBuffer, NumFrames, 0U);

	Status = XFpga_PcapWaitForDone();
	if (Status != XFPGA_SUCCESS) {
		Xfpga_Printf(XFPGA_DEBUG, "Write to PCAP Failed\n\r");
		Status = XFPGA_FAILURE;
		goto END;
	}

	Status = XFpga_WriteToPcap(cmdindex, (UINTPTR)CmdBuf);
	if (Status != XFPGA_SUCCESS) {
		Xfpga_Printf(XFPGA_DEBUG, "Write to PCAP Failed\n\r");
		Status = XFPGA_FAILURE;
		goto END;
	}

	/*
	 * Setup the  SSS, setup the DMA to receive from PCAP source
	 */
	Xil_Out32(CSU_CSU_SSS_CFG, XFPGA_CSU_SSS_SRC_DST_DMA);
	Xil_Out32(CSU_PCAP_RDWR, 0x1U);


	/* wait for the DST_DMA to complete and the pcap to be IDLE */
	Status = XCsuDma_WaitForDoneTimeout(CsuDmaPtr, XCSUDMA_DST_CHANNEL);
	if (Status != XFPGA_SUCCESS) {
		Xfpga_Printf(XFPGA_DEBUG, "Read from PCAP Failed\n\r");
		Status = XFPGA_FAILURE;
		goto END;
	}

	/* Acknowledge the transfer has completed */
	XCsuDma_IntrClear(CsuDmaPtr, XCSUDMA_DST_CHANNEL, XCSUDMA_IXR_DONE_MASK);

	Status = XFpga_PcapWaitForidle();
	if (Status != XFPGA_SUCCESS) {
		Xfpga_Printf(XFPGA_DEBUG, "Reading data from PL through PCAP Failed\n\r");
		Status = XFPGA_FAILURE;
		goto END;
	}

	cmdindex = 0U;
	/* Step 11 */
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	/* Step 12 */
	CmdBuf[cmdindex] = 0x30008001U; /* Type 1 Write 1 Word to CMD */
	cmdindex++;
	CmdBuf[cmdindex] = 0x00000005U; /* START Command */
	cmdindex++;
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	/* Step 13 */
	CmdBuf[cmdindex] = 0x30008001U; /* Type 1 Write 1 Word to CMD */
	cmdindex++;
	CmdBuf[cmdindex] = 0x00000007U; /* RCRC Command */
	cmdindex++;
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	/* Step 14 */
	CmdBuf[cmdindex] = 0x30008001U; /* Type 1 Write 1 Word to CMD */
	cmdindex++;
	CmdBuf[cmdindex] = 0x0000000DU; /* DESYNC Command */
	cmdindex++;

	/* Step 15 */
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;
	CmdBuf[cmdindex] = 0x20000000U; /* Type 1 NOOP Word 0 */
	cmdindex++;

	Status = XFpga_WriteToPcap(cmdindex, (UINTPTR)CmdBuf);
	if (Status != XFPGA_SUCCESS) {
		Xfpga_Printf(XFPGA_DEBUG, "Write to PCAP 1 Failed\n\r");
		Status = XFPGA_FAILURE;
	}
END:
	/* Disable the PCAP clk */
	RegVal = Xil_In32(PCAP_CLK_CTRL);
	Xil_Out32(PCAP_CLK_CTRL, RegVal & ~(PCAP_CLK_EN_MASK));
	memcpy(FrameBuffer, (u32*) &PCAP_DataBuffer[FRAME_SIZE+PAD_WORDS], FRAME_SIZE*4);

	return Status;
}


u32 FPGA_WriteFrame(u32 FAR, u32 *FrameBuffer, u32 SlrIDcode){
	int Status;
	u32 TotalWords = 2*FRAME_SIZE + PAD_WORDS;
	u32 WriteBuffer[1000];
	u32 Index = 0;

	Status = XFpga_GetFirmwareState();

	/* Enable the PCAP clk */
	u32 RegVal = Xil_In32(PCAP_CLK_CTRL);
	RegVal |= 0x3F00U;
	Xil_Out32(PCAP_CLK_CTRL, RegVal | PCAP_CLK_EN_MASK);

	/* Take PCAP out of Reset */
	Status = XFpga_PcapInit(1U);
	if (Status != XFPGA_SUCCESS) {
		Status = XPFGA_ERROR_PCAP_INIT;
		Xfpga_Printf(XFPGA_DEBUG, "PCAP init failed\n\r");
		return 1;
	}


	// DUMMY and SYNC
	WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
	WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	WriteBuffer[Index++] = XHI_SYNC_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Reset CRC
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 0x1U);
	WriteBuffer[Index++] = XHI_CMD_RCRC;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// ID register
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_IDCODE, OPCODE_WRITE, 0x1U);
	WriteBuffer[Index++] = SlrIDcode;

	// Setup CMD register - write configuration
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 0x1U);
	WriteBuffer[Index++] = XHI_CMD_WCFG;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Setup FAR
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_FAR, OPCODE_WRITE, 0x1U);
	WriteBuffer[Index++] = FAR;
	//printf("WRITE-FAR: %8x\n\r", WriteBuffer[Index-1]);
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Setup Packet header.
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_FDRI, OPCODE_WRITE, TotalWords);
	for(int i=0;i<FRAME_SIZE;i++) WriteBuffer[Index++] = FrameBuffer[i];
	for(int i=0;i<FRAME_SIZE+PAD_WORDS;i++) WriteBuffer[Index++] = 0xFFFFFFFF;


	//Restore Registers
/*
	if(Restore){
		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1; //Type1_Packet(2, XHI_CMD, 0x1);
		WriteBuffer[Index++] = XHI_CMD_GRESTORE;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}
*/


	// Append CRC
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 1);
	WriteBuffer[Index++] = XHI_CMD_RCRC;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	// Initiate startup sequence
	/*
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 1);
	WriteBuffer[Index++] = XHI_CMD_START;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	 */
	// Desynchronize the device
	WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 1);
	WriteBuffer[Index++] = XHI_CMD_DESYNCH;
	for(int i = 0; i < 10; i++) {
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}



	Status = XFpga_WriteToPcap(Index, &WriteBuffer[0]);
	if (Status != XFPGA_SUCCESS) {
		printf("PCAP write fail");
		Status = XFPGA_PCAP_UPDATE_ERR(
			(u32)XFPGA_ERROR_BITSTREAM_LOAD_FAIL, (u32)0U);
	}

	if (Status != XFPGA_SUCCESS) {
		printf("XFPGA_PCAP_UPDATE_ERR fail");
		Xfpga_Printf(XFPGA_DEBUG, "FPGA fail to write Bitstream into PL Error Code: 0x%08x\r\n", Status);
		return 1;
	}

	Status = XFpga_PLWaitForDone();
	if (Status != XFPGA_SUCCESS) {
		printf("XFpga_PLWaitForDone fail");
		Status = XFPGA_PCAP_UPDATE_ERR(Status, (u32)0U);
		Xfpga_Printf(XFPGA_DEBUG,
			"FPGA fail to get the PCAP Done status Error Code:0x%08x\r\n",
			Status);
	}

	return 0;

}



