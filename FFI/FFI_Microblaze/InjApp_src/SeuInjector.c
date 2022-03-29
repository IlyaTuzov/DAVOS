 /*
   Copyright (c) 2018 by Universitat Politecnica de Valencia.
   This file is a part of the DAVOS toolkit
   and is released under the "MIT license agreement".
   Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
   ------------------------------------------------------------------------------------------------------
   Description:
      An library for implementing FPGA-based fault injection tools
      that access Configuration memory through the ICAP interface

   Author: Ilya Tuzov, Universitat Politecnica de Valencia
   ------------------------------------------------------------------------------------------------------
*/

#include "platform.h"
#include <xil_types.h>
#include <xil_assert.h>
#include <xhwicap.h>
#include "xparameters.h"
#include <stdio.h>
#include <stdlib.h>
#include <xil_printf.h>
#include "xgpio.h"
#include "SeuInjector.h"



FarFields parseFAR(u32 FAR, FpgaSeries series){
	FarFields res;
	if(series==S7){
		res.BLOCK 	= (FAR >> 23) & 0x00000007;
		res.TOP 	= (FAR >> 22) & 0x00000001;
		res.HCLKROW	= (FAR >> 17) & 0x0000001F;
		res.MAJOR 	= (FAR >> 7)  & 0x000003FF;
		res.MINOR 	=  FAR  	  & 0x0000007F;
	}
	else if(series==US){
		res.BLOCK 	= (FAR >> 23) & 0x00000007;
		res.TOP 	= 0;
		res.HCLKROW	= (FAR >> 17) & 0x0000003F;
		res.MAJOR 	= (FAR >> 7)  & 0x000003FF;
		res.MINOR 	=  FAR  	  & 0x0000007F;
	}
	else if(series==USP){
		res.BLOCK 	= (FAR >> 24) & 0x00000007;
		res.TOP 	= 0;
		res.HCLKROW	= (FAR >> 18) & 0x0000003F;
		res.MAJOR 	= (FAR >> 8)  & 0x000003FF;
		res.MINOR 	=  FAR  	  & 0x000000FF;
	}
	return(res);
}



int cmpfunc (const void * a, const void * b) {
   return ( *(int*)a - *(int*)b );
}


u32 input_int(int radix){
	u32 res = 0;
	char8 key;
	while(1) {
		key = inbyte();
		if(radix==10){
			if(key>=48 && key <=57){
				res = res*10+key-48;
			}
		}
		else if(radix==16){
			if(key=='A' || key=='a')      res = res*16+0xA;
			else if(key=='B' || key=='b') res = (res<<4)+0xB;
			else if(key=='C' || key=='c') res = (res<<4)+0xC;
			else if(key=='D' || key=='d') res = (res<<4)+0xD;
			else if(key=='E' || key=='e') res = (res<<4)+0xE;
			else if(key=='F' || key=='f') res = (res<<4)+0xF;
			else if(key>=48 && key <=57)   res = (res<<4)+key-48;
		}
		if(key == '\n' || key =='\r')break;
	}
	return(res);
}


void log_Frame(InjectorDescriptor * InjDesc, u32 SlrID, u32 FAR){
	int Status = readFrame(&(InjDesc->HwIcap), SlrID, FAR, InjDesc->FrameData, 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: SLR: %08x, FAR: %08x, Status: %d\r\n", SlrID, FAR, Status);
		return XST_FAILURE;
	}
	printf("SLR: %08x, FAR: %08x\n\r", InjDesc->SlrId[SlrID], FAR);
	for(int k = 0; k < FRAME_SIZE; k++) printf("Frame Word %03d -> \t %08x \n\r", k  , InjDesc->FrameData[k]);
}


int ProcessFaultDescriptor(InjectorDescriptor * InjDesc, int FdescOffset){
	FaultDescriptor fdesc, fdesc_next;
	int offset = FdescOffset;
	do{
		fdesc =	*(InjDesc->fault_list_ptr + offset);
		fdesc_next = *(InjDesc->fault_list_ptr + offset + 1);
		FlipBits(InjDesc, &fdesc);
		offset++;
	} while(fdesc.Id == fdesc_next.Id);

	return(0);
}


int FlipBits(InjectorDescriptor * InjDesc, FaultDescriptor *fdesc){
	if(InjDesc->DebugMode) printf("Injecting: Id=%3d, CellType=%1d, FAR=%08x, word=%3d, mask=%08x, time=%6d\n\r", fdesc->Id, fdesc->CellType, fdesc->FAR, fdesc->word, fdesc->mask, fdesc->time);
	int Status = readFrame(&(InjDesc->HwIcap), fdesc->SLR, fdesc->FAR, InjDesc->FrameData, 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Read Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	InjDesc->FrameData[fdesc->word] = InjDesc->FrameData[fdesc->word] ^ fdesc->mask;
	Status = writeFrame(&(InjDesc->HwIcap), fdesc->SLR, InjDesc->SlrId[fdesc->SLR], fdesc->FAR, InjDesc->FrameData, 0);
	if (Status != XST_SUCCESS) {
		if(InjDesc->DebugMode) printf("Failed to Write Frame: %d \r\n", Status);
		return XST_FAILURE;
	}
	if(InjDesc->DebugMode){
		for(int k = 0; k < FRAME_SIZE; k++) printf("Frame Word %03d -> \t %08x \n\r", k  , InjDesc->FrameData[k]);
	}
	return(0);
}




int readFrame(XHwIcap *InstancePtr, u32 SlrConfigIndex, u32 FAR, u32 *FrameBuffer, int Capture) {

	u32 Packet;
	u32 Data;
	int Status;
	u32 WriteBuffer[200];
	u32 Index = 0;

	Xil_AssertNonvoid(InstancePtr != NULL);
	Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);
	Xil_AssertNonvoid(FrameBuffer != NULL);



	for(int i=0;i<SlrConfigIndex;i++){
		WriteBuffer[Index++] = 0x3003c000;
		WriteBuffer[Index++] = 0x50cbd9dc; //0x57FFFFFF;
		WriteBuffer[Index++] = 0xFFFFFFFF;
		WriteBuffer[Index++] = 0x000000BB;
		WriteBuffer[Index++] = 0x11220044;
		WriteBuffer[Index++] = 0xFFFFFFFF;
		WriteBuffer[Index++] = 0xAA995566;
		WriteBuffer[Index++] = 0x20000000;
	}

	// DUMMY and SYNC
	WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
	WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
	WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	WriteBuffer[Index++] = XHI_SYNC_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;


	// Reset CRC
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_RCRC;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;


	// GCAPTURE
	if(Capture>0){
		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1; //Type1_Packet(2, XHI_CMD, 0x1);
		WriteBuffer[Index++] = XHI_CMD_GCAPTURE;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;

		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1; //Type1_Packet(2, XHI_CMD, 0x1);
		WriteBuffer[Index++] = XHI_CMD_RCAP;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}

	// Setup CMD register to read configuration
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_RCFG;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Setup FAR register
	Packet = XHwIcap_Type1Write(XHI_FAR) | 1;
	Data = FAR; //XHwIcap_Custom_SetupFar7series(Top, Block, HClkRow,  MajorFrame, MinorFrame);
	WriteBuffer[Index++] = Packet;
	WriteBuffer[Index++] = Data;

	// Create Type one packet
	Packet = XHwIcap_Type1Read(XHI_FDRO);
	WriteBuffer[Index++] = Packet;
	WriteBuffer[Index++] = XHI_TYPE_2_READ | ((InstancePtr->WordsPerFrame << 1)+READBACK_PAD_WORDS );

	for(int i = 0; i < 32; i++) {
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}

	//Write the data to the FIFO and initiate the transfer of data present in the FIFO to the ICAP device
	Status = XHwIcap_DeviceWrite(InstancePtr, (u32 *)&WriteBuffer[0], Index);
		if (Status != XST_SUCCESS)  { return XST_FAILURE; }

	// Wait till the write is done
	while (XHwIcap_IsDeviceBusy(InstancePtr) != FALSE);

	//read null frame and discard
	Status = XHwIcap_DeviceRead(InstancePtr, FrameBuffer, InstancePtr->WordsPerFrame+READBACK_PAD_WORDS-2);
	//read frame data
	Status = XHwIcap_DeviceRead(InstancePtr, FrameBuffer, InstancePtr->WordsPerFrame);
		if (Status != XST_SUCCESS)  { return XST_FAILURE; }

	/* Send DESYNC command*/
	Status = XHwIcap_CommandDesync(InstancePtr);
		if (Status != XST_SUCCESS)  { return XST_FAILURE; }


	return XST_SUCCESS;
}







int writeFrame(XHwIcap *InstancePtr, u32 SlrConfigIndex, u32 SlrIDcode, u32 FAR, u32 *FrameBuffer, int Restore)
{
	u32 TotalWords;
	int Status;
	u32 WriteBuffer[200];
	u32 PadFrame[FRAME_SIZE+READBACK_PAD_WORDS];
	u32 Index = 0;


	Xil_AssertNonvoid(InstancePtr != NULL);
	Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);
	Xil_AssertNonvoid(FrameBuffer != NULL);


	// DUMMY and SYNC
	WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
	WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	WriteBuffer[Index++] = XHI_SYNC_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Reset CRC
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_RCRC;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//WriteBuffer[Index++] = XHI_NOOP_PACKET;


	// ID register
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_IDCODE) | 1;
	WriteBuffer[Index++] = SlrIDcode;

	// Setup CMD register - write configuration
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_WCFG;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Setup FAR
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_FAR) | 1;
	WriteBuffer[Index++] = FAR;
	//printf("WRITE-FAR: %8x\n\r", WriteBuffer[Index-1]);
	WriteBuffer[Index++] = XHI_NOOP_PACKET;

	// Setup Packet header.
	TotalWords = (InstancePtr->WordsPerFrame << 1) + READBACK_PAD_WORDS;
	if (TotalWords < XHI_TYPE_1_PACKET_MAX_WORDS)  {
		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_FDRI) | TotalWords;
	}
	else {
		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_FDRI);
		WriteBuffer[Index++] = XHI_TYPE_2_WRITE | TotalWords;
	}

	//debug trace
	//for(u32 v = 0;v<Index;v++){ printf("Buf[%u] = %08x\n", v, WriteBuffer[v]); }

	// Write the Header data into the FIFO and intiate the transfer of data present in the FIFO to the ICAP device
	Status = XHwIcap_DeviceWrite(InstancePtr, (u32 *)&WriteBuffer[0], Index);
	if (Status != XST_SUCCESS)  { return XST_FAILURE; }

	// Write the modified frame data.
	Status = XHwIcap_DeviceWrite(InstancePtr, FrameBuffer, InstancePtr->WordsPerFrame);
		if (Status != XST_SUCCESS) { return XST_FAILURE;}

	// Write out the pad frame. The pad frame was read from the device before the data frame.
	for(int i=0;i<FRAME_SIZE+READBACK_PAD_WORDS;i++){ PadFrame[i]=0xFFFFFFFF; };
	Status = XHwIcap_DeviceWrite(InstancePtr, &PadFrame[0], InstancePtr->WordsPerFrame+READBACK_PAD_WORDS);
	if (Status != XST_SUCCESS) { return XST_FAILURE; }

	Index = 0;
	//Restore Registers
	if(Restore){
		WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1; //Type1_Packet(2, XHI_CMD, 0x1);
		WriteBuffer[Index++] = XHI_CMD_GRESTORE;
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}

	// Park the FAR
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_FAR) | 1;
	WriteBuffer[Index++] = XHwIcap_SetupFar(0, 0, 3, 33, 0);
	// Append CRC
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_RCRC;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	// Initiate startup sequence
	WriteBuffer[Index++] = XHwIcap_Type1Write(XHI_CMD) | 1;
	WriteBuffer[Index++] = XHI_CMD_START;
	WriteBuffer[Index++] = XHI_NOOP_PACKET;
	// Desynchronize the device
	WriteBuffer[Index++] = (XHwIcap_Type1Write(XHI_CMD) | 1);
	WriteBuffer[Index++] = XHI_CMD_DESYNCH;
	for(int i = 0; i < 10; i++) {
		WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}

	//debug trace
	//for(u32 v = 0;v<Index;v++){ printf("Buf[%u] = %08x\n", v, WriteBuffer[v]); }

	// Intiate the transfer of data present in the FIFO to the ICAP device
	Status = XHwIcap_DeviceWrite(InstancePtr, &WriteBuffer[0], Index);
		if (Status != XST_SUCCESS)  { return XST_FAILURE; }


	return XST_SUCCESS;
}


