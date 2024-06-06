


#include <stdio.h>
#include <stdlib.h>
#include "platform.h"
#include "xilfpga.h"
#include "xilfpga_pcap.h"
//#include "xilfpga_pcap.lc"
#include "/opt/Xilinx/Vitis/2022.2/data/embeddedsw/lib/sw_services/xilfpga_v6_3/src/interface/zynqmp/xilfpga_pcap.c"
#include "SeuInjector.h"


u32 PCAP_DataBuffer[1000];

//readback offsets within the group of two slices
const u32 rb_os_word[32] = {
    0, 0, 0, 0,  0, 0, 1, 1,    //top: 0, label: 0 - 7  (A-H)
    0, 0, 0, 0,  1, 1, 1, 1,    //top: 0, label: 8 - 15 (A2-H2)
    1, 1, 1, 1,  2, 2, 2, 2,    //top: 1, label: 0 - 7  (A-H)
    1, 2, 2, 2,  2, 2, 2, 2,    //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 rb_os_bit[32]  = {
    2, 4, 8, 10, 26,28, 0, 2,  //top: 0, label: 0 - 7  (A-H)
    14,16,20,22,  6, 8,12,14,  //top: 0, label: 8 - 15 (A2-H2)
    18,20,24,26, 10,12,16,18,  //top: 1, label: 0 - 7  (A-H)
    30, 0, 4, 6, 22,24,28,30   //top: 1, label: 8 - 15 (A2-H2)
    };


//set-reset level (0 -> set, 1 -> reset)
const u32 sr_os_word[32] = {
    0, 0, 0, 0,  0, 0, 0, 1,    //top: 0, label: 0 - 7  (A-H)
    0, 0, 0, 0,  1, 1, 1, 1,    //top: 0, label: 8 - 15 (A2-H2)
    1, 1, 1, 1,  2, 2, 2, 2,    //top: 1, label: 0 - 7  (A-H)
    1, 2, 2, 2,  2, 2, 2, 2     //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 sr_os_bit[32]  = {
    1, 5, 7,11,  25,29,31, 3,   //top: 0, label: 0 - 7  (A-H)
    13,17,19,23,  5, 9,11,15,   //top: 0, label: 8 - 15 (A2-H2)
    17,21,23,27,  9,13,15,19,   //top: 1, label: 0 - 7  (A-H)
    29, 1, 3, 7, 21,25,27,31    //top: 1, label: 8 - 15 (A2-H2)
    };

//inverter of set-reset line
const u32 inv_os_far[32] =  {
    9, 9, 9, 9,   8, 8, 8, 8,   //top: 0, label: 0 - 7  (A-H)
    9, 9, 9, 9,   8, 8, 8, 8,   //top: 0, label: 8 - 15 (A2-H2)
    9, 9, 9, 9,   8, 8, 8, 8,   //top: 1, label: 0 - 7  (A-H)
    9, 9, 9, 9,   8, 8, 8, 8    //top: 1, label: 8 - 15 (A2-H2)

    };

const u32 inv_os_word[32] = {
    0, 0, 0, 0,   0, 0, 0, 0,   //top: 0, label: 0 - 7  (A-H)
    0, 0, 0, 0,   0, 0, 0, 0,   //top: 0, label: 8 - 15 (A2-H2)
    2, 2, 2, 2,   2, 2, 2, 2,   //top: 1, label: 0 - 7  (A-H)
    2, 2, 2, 2,   2, 2, 2, 2    //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 inv_os_bit[32]  = {
    18,18,18,18, 31,31,31,31,  //top: 0, label: 0 - 7  (A-H)
    18,18,18,18, 31,31,31,31,  //top: 0, label: 8 - 15 (A2-H2)
    2, 2, 2, 2,  15,15,15,15,   //top: 1, label: 0 - 7  (A-H)
    2, 2, 2, 2,  15,15,15,15    //top: 1, label: 8 - 15 (A2-H2)
    };

//inverter of CLK line
const u32 iclk_os_far[32] =  {
	8, 8, 8, 8,   8, 8, 8, 8,   //top: 0, label: 0 - 7  (A-H)
	8, 8, 8, 8,   8, 8, 8, 8,   //top: 0, label: 8 - 15 (A2-H2)
	8, 8, 8, 8,   8, 8, 8, 8,   //top: 1, label: 0 - 7  (A-H)
	8, 8, 8, 8,   8, 8, 8, 8    //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 iclk_os_word[32] = {
    0, 0, 0, 0,   0, 0, 0, 0,   //top: 0, label: 0 - 7  (A-H)
    0, 0, 0, 0,   0, 0, 0, 0,   //top: 0, label: 8 - 15 (A2-H2)
    2, 2, 2, 2,   2, 2, 2, 2,   //top: 1, label: 0 - 7  (A-H)
    2, 2, 2, 2,   2, 2, 2, 2    //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 iclk_os_bit[32]  = {
    19,19,19,19, 29,29,29,29,  //top: 0, label: 0 - 7  (A-H)
	19,19,19,19, 29,29,29,29,  //top: 0, label: 8 - 15 (A2-H2)
    3, 3, 3, 3,  13,13,13,13,   //top: 1, label: 0 - 7  (A-H)
	3, 3, 3, 3,  13,13,13,13    //top: 1, label: 8 - 15 (A2-H2)
    };


//inverter of set-reset line
const u32 dcon_os_far[32] =  {
    14,14,14,14,  14,14,14,14,   //top: 0, label: 0 - 7  (A-H)
	15,15,15,15,  15,15,15,15,   //top: 0, label: 8 - 15 (A2-H2)
	15,15,15,15,  15,15,15,15,   //top: 1, label: 0 - 7  (A-H)
	15,15,15,15,  15,15,15,15    //top: 1, label: 8 - 15 (A2-H2)

    };

const u32 dcon_os_word[32] = {
    0, 0, 0, 0,   0, 1, 1, 1,   //top: 0, label: 0 - 7  (A-H)
    0, 0, 0, 0,   0, 0, 0, 0,   //top: 0, label: 8 - 15 (A2-H2)
    1, 1, 1, 2,   2, 2, 2, 2,   //top: 1, label: 0 - 7  (A-H)
	0, 0, 0, 0,   0, 0, 0, 0    //top: 1, label: 8 - 15 (A2-H2)
    };

const u32 dcon_os_bit[32]  = {
     2,8,14,20,  26, 0, 6,12,  //top: 0, label: 0 - 7  (A-H)
	0, 0, 0, 0,   0, 0, 0, 0,  //top: 0, label: 8 - 15 (A2-H2)
    17,23,29,3,   9,15,21,27,   //top: 1, label: 0 - 7  (A-H)
	0, 0, 0, 0,   0, 0, 0, 0    //top: 1, label: 8 - 15 (A2-H2)
    };



//label: 0-7 (A-H), 8-15 (A2-H2)
FF_CBL get_ff_clb(u32 Y, u32 label, u32 FAR){
	FF_CBL res;
	u32 c = Y % 60;
	u32 group = c / 2;
	u32 top = c % 2;
	u32 idx = top*16 + label;
	u32 base_word = group<15 ? group*3 : (group*3) + 3;
	res.rb_far = (FAR & 0xFFFFFF00) | 0x0C;
	res.rb_word = base_word + rb_os_word[idx];
	res.rb_bit = rb_os_bit[idx];
	res.sr_far = (FAR & 0xFFFFFF00) | 0x0C;
	res.sr_word = base_word + sr_os_word[idx];
	res.sr_bit = sr_os_bit[idx];
	res.inv_far = (FAR & 0xFFFFFF00) | inv_os_far[idx];
	res.inv_word = base_word + inv_os_word[idx];
	res.inv_bit = inv_os_bit[idx];
	res.iclk_far = (FAR & 0xFFFFFF00) | iclk_os_far[idx];
	res.iclk_word = base_word + iclk_os_word[idx];
	res.iclk_bit = iclk_os_bit[idx];
	res.dcon_far = (FAR & 0xFFFFFF00) | dcon_os_far[idx];
	res.dcon_word = base_word + dcon_os_word[idx];
	res.dcon_bit = dcon_os_bit[idx];
	return res;
};


void disconnect_SliceReg(InjectorDescriptor * InjDesc, u32 Y, u32 label, u32 FAR){
	FF_CBL ff = get_ff_clb(Y, label, FAR);

	FPGA_ReadFrame(ff.dcon_far, InjDesc->FrameData, 0);
	InjDesc->FrameData[ff.dcon_word] ^= (1 << ff.dcon_bit);
	FPGA_WriteFrame(ff.dcon_far, InjDesc->FrameData, InjDesc->SlrId[0], 0);
	printf("disconnect_SliceReg: LUT[%d] (%08x, %d, %d) set to %d\n",label, ff.dcon_far, ff.dcon_word, ff.dcon_bit,  (InjDesc->FrameData[ff.dcon_word] >> ff.dcon_bit) & 0x1);
}



//Returns current state of 16 CLB Flip-Flops [15:0] = [ H2,G2,F2,E2,D2,C2,B2,A2, H,G,F,E,D,C,B,A ]
u16 readback_slice_reg(InjectorDescriptor * InjDesc, u32 Y, u32 FAR){
	u32 buffer[FRAME_SIZE];
	FPGA_ReadFrame(FAR, buffer, 1);
	u16 result = 0x0;
	for(int i=0;i<16;i++){
		FF_CBL ff = get_ff_clb(Y, i, FAR);
		u16 v = (buffer[ff.rb_word] >> ff.rb_bit) & 0x1;
		result = result | (v << i );
	}
	return(~result);
}





void Set_SliceReg(InjectorDescriptor * InjDesc, u32 Y, u32 FAR, u16 val){
	FPGA_ReadFrame(FAR, InjDesc->FrameData, 0);
	u32 buffer[FRAME_SIZE];
	FF_CBL ff;
	memcpy(buffer, InjDesc->FrameData, FRAME_SIZE*4);
	for(int i=0;i<16;i++){
		ff = get_ff_clb(Y, i, FAR);
		if( (val>>i)&0x1 ){
			//set FF=1 (SR bit = 0)
			InjDesc->FrameData[ff.sr_word] &= ~(1 << ff.sr_bit);
		}
		else{
			//reset FF=0 (SR bit = 1)
			InjDesc->FrameData[ff.sr_word] |= (1 << ff.sr_bit);
		}
	}
	FPGA_WriteFrame(FAR, InjDesc->FrameData, InjDesc->SlrId[0], 0);
	//trigger SR line AFF to DFF
	ff = get_ff_clb(Y, 0, FAR);
	BitFlip(InjDesc, ff.inv_far, ff.inv_word, ff.inv_bit);
	BitFlip(InjDesc, ff.iclk_far, ff.iclk_word, ff.iclk_bit);
	BitFlip(InjDesc, ff.iclk_far, ff.iclk_word, ff.iclk_bit);
	BitFlip(InjDesc, ff.inv_far, ff.inv_word, ff.inv_bit);
	//trigger SR line EFF to HFF
	ff = get_ff_clb(Y, 4, FAR);
	BitFlip(InjDesc, ff.inv_far, ff.inv_word, ff.inv_bit);
	BitFlip(InjDesc, ff.iclk_far, ff.iclk_word, ff.iclk_bit);
	BitFlip(InjDesc, ff.iclk_far, ff.iclk_word, ff.iclk_bit);
	BitFlip(InjDesc, ff.inv_far, ff.inv_word, ff.inv_bit);
	//recover SR bits to original state
	FPGA_WriteFrame(FAR, buffer, InjDesc->SlrId[0], 0);
}


void Flip_SliceReg(InjectorDescriptor * InjDesc, u32 Y, u32 label, u32 FAR){
	//printf("Flip_SliceReg: Y=%d, Label=%d, FAR=%08x\n", Y, label, FAR);
	u16 slice_flops = readback_slice_reg(InjDesc, Y, FAR);
	slice_flops = slice_flops ^ (1 << label);
	Set_SliceReg(InjDesc, Y, FAR, slice_flops);
}


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
			FPGA_ReadFrame(fdesc->FAR, data, 0);
			fdesc->ReferenceWordData = data[fdesc->word];
			printf("ReferenceWordData[%d] = 0x%08x\n", i, fdesc->ReferenceWordData);
		}
	}
	printf("Encoding of failure modes:\n");
	for(int i=Masked;i<=Signalled;i++){
		printf("\tFailureMode[%d] = %s\n", i, FailureModeLabels[i]);
	}
	for(int i=0;i<InjDesc->FaultListSize;i++){
		fdesc = InjDesc->fault_list_ptr + i;
		printf("FaultId: %5d, CellType: %d, FaultModel: %d, Y: %3d, Label: %2d, FAR: %08x, Time: %8d\n",
				fdesc->Id, fdesc->CellType, fdesc->FaultModel, fdesc->CellY, fdesc->CellLabel, fdesc->FAR, fdesc->time);
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
	printf("[%8.5f s] FaultId=%5d, Time=%d, Fmode= %15s, %s :: %s\n\n",
			1.0*(CTime-InjDesc->Tstart)/(COUNTS_PER_SECOND), fdesc->Id, fdesc->time,
			FailureModeLabels[fmode], buffer, message);
	//usleep(100000);
}


int ProcessFaultDescriptor(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc, int recover){
	u32 current_id;
	FaultDescriptor *f_item = fdesc;
	u32 Id = f_item->Id;
	do{
		//printf("Processing fault descriptor at: 0x%08x\n", (u32) fdesc);
		if( (f_item->CellType == 0) || (f_item->CellType == 1) ){
			if(recover){
				Recover_Bitmask(InjDesc, f_item);
			}
			else{
				Inject_Bitmask(InjDesc, f_item);
			}
		}
		else if( f_item->CellType == 2 ){
			if(!recover){
				Flip_SliceReg(InjDesc, f_item->CellY, f_item->CellLabel, f_item->FAR);
			}
		}
		f_item++;
	} while(Id == f_item->Id);

	return(0);
}


int Inject_Bitmask(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc){
	if(InjDesc->DebugMode) printf("Injecting: Id=%3d, CellType=%1d, Y=%d, Label=%d, FAR=%08x, word=%3d, mask=%08x, time=%6d\n", fdesc->Id, fdesc->CellType,  fdesc->CellY, fdesc->CellLabel, fdesc->FAR, fdesc->word, fdesc->mask, fdesc->time);
	int Status = FPGA_ReadFrame(fdesc->FAR, InjDesc->FrameData, 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	//Check or save reference data
	if(InjDesc->FrameData[fdesc->word] != fdesc->ReferenceWordData){
		printf("WARNING: ReferenceWordData mismatch [%08x, %d]: %08x != %08x\n", fdesc->FAR, fdesc->word,
				InjDesc->FrameData[fdesc->word], fdesc->ReferenceWordData);
	}
	//Apply fault mask to the selected FAR and Word
	InjDesc->FrameData[fdesc->word] = InjDesc->FrameData[fdesc->word] ^ fdesc->mask;
	Status = FPGA_WriteFrame(fdesc->FAR, InjDesc->FrameData, InjDesc->SlrId[0], 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Write Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	return(0);
}


void BitFlip(InjectorDescriptor * InjDesc, u32 FAR, u32 word, u32 bit){
	FPGA_ReadFrame(FAR, InjDesc->FrameData, 0);
	InjDesc->FrameData[word] = InjDesc->FrameData[word] ^ (1<<bit);
	FPGA_WriteFrame(FAR, InjDesc->FrameData, InjDesc->SlrId[0], 0);
}

int Recover_Bitmask(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc){
	if(InjDesc->DebugMode) printf("Recovering: Id=%3d, CellType=%1d, FAR=%08x, word=%3d, mask=%08x, time=%6d\n", fdesc->Id, fdesc->CellType, fdesc->FAR, fdesc->word, fdesc->mask, fdesc->time);
	int Status = FPGA_ReadFrame(fdesc->FAR, InjDesc->FrameData, 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	//InjDesc->FrameData[fdesc->word] = fdesc->ReferenceWordData;
	InjDesc->FrameData[fdesc->word] = InjDesc->FrameData[fdesc->word] ^ fdesc->mask;
	Status = FPGA_WriteFrame(fdesc->FAR, InjDesc->FrameData, InjDesc->SlrId[0], 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Write Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	return(0);
}


u32 FPGA_ReadFrame(u32 FAR, u32 *FrameBuffer, u32 ReadbackCaptureEnable){
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
	CmdBuf[cmdindex++] = 0xFFFFFFFFU; /* Dummy Word */
	CmdBuf[cmdindex++] = 0x000000BBU; /* Bus Width Sync Word */
	CmdBuf[cmdindex++] = 0x11220044U; /* Bus Width Detect */
	CmdBuf[cmdindex++] = 0xFFFFFFFFU; /* Dummy Word */
	CmdBuf[cmdindex++] = 0xAA995566U; /* Sync Word */

	/* Step 2 */
	CmdBuf[cmdindex++] = 0x02000000U; /* Type 1 NOOP Word 0 */
	/* Step 3 */         /* Type 1 Write 1 Word to CMD */
	//CmdBuf[cmdindex++] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	//CmdBuf[cmdindex++] = 0x0000000BU; /* SHUTDOWN Command */
	//CmdBuf[cmdindex++] = 0x02000000U; /* Type 1 NOOP Word 0 */

	/* Step 4 */         /* Type 1 Write 1 Word to CMD */
	/*
	CmdBuf[cmdindex++] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	CmdBuf[cmdindex++] = 0x00000007U; // RCRC Command
	CmdBuf[cmdindex++] = 0x20000000U; // Type 1 NOOP Word 0
	 */


	if(ReadbackCaptureEnable){
		CmdBuf[cmdindex++] = 0x30008001;	//CMD write
		CmdBuf[cmdindex++] = 0x00000000;	//NULL
		CmdBuf[cmdindex++] = 0x3000C001;	//MSK write
		CmdBuf[cmdindex++] = 0x00800000;	//CAPTURE bit[23]
		CmdBuf[cmdindex++] = 0x30030001;	//CTL1 write
		CmdBuf[cmdindex++] = 0x00800000;	//CAPTURE bit[23]
	}



	/* Step 5 --- 5 NOOPS Words */
	for (i = 0 ; i < 8 ; i++) {
		CmdBuf[cmdindex++] = 0x20000000U;
	}

	/* Step 7 */         /* Type 1 Write 1 Word to FAR */
	CmdBuf[cmdindex++] = Xfpga_RegAddr(FAR1, OPCODE_WRITE, 0x1U);
	CmdBuf[cmdindex++] = FAR;

	/* Step 6 */         /* Type 1 Write 1 Word to CMD */
	CmdBuf[cmdindex++] = Xfpga_RegAddr(CMD, OPCODE_WRITE, 0x1U);
	CmdBuf[cmdindex++] = 0x00000004U; /* RCFG Command */
	//CmdBuf[cmdindex++] = 0x20000000U; /* Type 1 NOOP Word 0 */



	/* Step 8 */          /* Type 1 Read 0 Words from FDRO */
	CmdBuf[cmdindex++] =  0x28006000; //Xfpga_RegAddr(FDRO, OPCODE_READ, 0U);
			      /* Type 2 Read Wordlenght Words from FDRO */
	CmdBuf[cmdindex++] = Xfpga_Type2Pkt(OPCODE_READ, NumFrames);


	/* Step 9 --- 64 NOOPS Words */
	for (i = 0 ; i < (s32)64 ; i++) {
		CmdBuf[cmdindex++] = 0x20000000U;
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
	//CmdBuf[cmdindex++] = 0xFFFFFFFFU; /* Dummy Word */
	//CmdBuf[cmdindex++] = 0x000000BBU; /* Bus Width Sync Word */
	//CmdBuf[cmdindex++] = 0x11220044U; /* Bus Width Detect */
	//CmdBuf[cmdindex++] = 0xFFFFFFFFU; /* Dummy Word */
	//CmdBuf[cmdindex++] = 0xAA995566U; /* Sync Word */
	//CmdBuf[cmdindex++] = 0x20000000U; /* Type 1 NOOP Word 0 */

	if(ReadbackCaptureEnable){
		CmdBuf[cmdindex++] = 0x3000C001; //MSK write
		CmdBuf[cmdindex++] = 0x00800000; //CAPTURE bit[23]
		CmdBuf[cmdindex++] = 0x30030001; //CTL1 write
		CmdBuf[cmdindex++] = 0x00000000; //CAPTURE bit[23]
		CmdBuf[cmdindex++] = 0x20000000;
		CmdBuf[cmdindex++] = 0x20000000;
	}


	/* Step 12 */
	/*
	CmdBuf[cmdindex++] = 0x30008001U; // Type 1 Write 1 Word to CMD
	CmdBuf[cmdindex++] = 0x00000005U; // START Command
	CmdBuf[cmdindex++] = 0x20000000U; // Type 1 NOOP Word 0
	*/

	/* Step 13 */
	CmdBuf[cmdindex++] = 0x30008001U; /* Type 1 Write 1 Word to CMD */
	CmdBuf[cmdindex++] = 0x00000007U; /* RCRC Command */
	CmdBuf[cmdindex++] = 0x20000000U; /* Type 1 NOOP Word 0 */

	/* Step 14 */
	CmdBuf[cmdindex++] = 0x30008001U; /* Type 1 Write 1 Word to CMD */
	CmdBuf[cmdindex++] = 0x0000000DU; /* DESYNC Command */

	/* Step 15 */
	CmdBuf[cmdindex++] = 0x20000000U; /* Type 1 NOOP Word 0 */
	CmdBuf[cmdindex++] = 0x20000000U; /* Type 1 NOOP Word 0 */

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


u32 FPGA_WriteFrame(u32 FAR, u32 *FrameBuffer, u32 SlrIDcode, u32 Restore){
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
		printf("PCAP init failed\n\r");
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

	if(Restore){
		WriteBuffer[Index++] = Xfpga_RegAddr(XHI_CMD, OPCODE_WRITE, 1); //Type1_Packet(2, XHI_CMD, 0x1);
		WriteBuffer[Index++] = XHI_CMD_GRESTORE;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}



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
		printf("FPGA fail to write Bitstream into PL Error Code: 0x%08x\r\n", Status);
		return 1;
	}

	Status = XFpga_PLWaitForDone();
	if (Status != XFPGA_SUCCESS) {
		printf("XFpga_PLWaitForDone fail");
		Status = XFPGA_PCAP_UPDATE_ERR(Status, (u32)0U);
		printf("FPGA fail to get the PCAP Done status Error Code:0x%08x\r\n", Status);
	}

	return 0;

}




void PSU_Mask_Write(unsigned long offset, unsigned long mask, unsigned long val){
	unsigned long RegVal = 0x0;
	RegVal = Xil_In32(offset);
	RegVal &= ~(mask);
	RegVal |= (val & mask);
	Xil_Out32(offset, RegVal);
}

unsigned long PL_reset() {
	PSU_Mask_Write(GPIO_MASK_DATA_5_MSW_OFFSET, 0xFFFF0000U, 0x80000000U);
	PSU_Mask_Write(GPIO_DIRM_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	PSU_Mask_Write(GPIO_OEN_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	usleep(1);
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x00000000U);
	usleep(1);
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
}


void PL_reset_sync() {
	u32 cnum = 1000;
	PSU_Mask_Write(PL0_THR_CTRL_OFFSET, 0x00000003, 0x0);
	PSU_Mask_Write(PL0_THR_CNT_OFFSET, 0x0000FFFF, cnum);
	PSU_Mask_Write(PL0_THR_CTRL_OFFSET, 0x00000003, 0x2);
	PSU_Mask_Write(GPIO_MASK_DATA_5_MSW_OFFSET, 0xFFFF0000U, 0x80000000U);
	PSU_Mask_Write(GPIO_DIRM_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	PSU_Mask_Write(GPIO_OEN_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x00000000U);
	WaitClockStops();
	PSU_Mask_Write(GPIO_DATA_5_OFFSET, 0xFFFFFFFFU, 0x80000000U);
}


void RunClock(u32 cnum){
	PSU_Mask_Write(PL0_THR_CTRL_OFFSET, 0x00000003, 0x0);
	PSU_Mask_Write(PL0_THR_CNT_OFFSET, 0x0000FFFF, cnum);
	PSU_Mask_Write(PL0_THR_CTRL_OFFSET, 0x00000003, 0x2);
	//usleep(1);
}

void WaitClockStops(){
	while((Xil_In32(PL0_THR_CTRL_OFFSET) & 0x00008000) != 0);
}

void StopClock(){
	RunClock(1);
	while((Xil_In32(PL0_THR_CTRL_OFFSET) & 0x00008000) != 0);
}

