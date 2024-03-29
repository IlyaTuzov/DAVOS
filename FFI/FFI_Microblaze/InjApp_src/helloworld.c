 /*
   Copyright (c) 2018 by Universitat Politecnica de Valencia.
   This file is a part of the DAVOS toolkit
   and is released under the "MIT license agreement".
   Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
   ------------------------------------------------------------------------------------------------------
   Description:
      A Microblaze-based application for FPGA-based fault injection
      based on the FFI library

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


#define DEBUG_MODE 0





InjectorDescriptor InjDesc;


void test_clk_ctrl(InjectorDescriptor *InjDesc){
	xil_printf("test_clk_ctrl started\n\r");

	*(InjDesc->clock_ctrl_ptr + 0) = 100;
	*(InjDesc->clock_ctrl_ptr + 2) = 0x04;
	*(InjDesc->clock_ctrl_ptr + 1) = 0x01;
	*(InjDesc->clock_ctrl_ptr + 1) = 0x00;

    while(*(InjDesc->clock_ctrl_ptr + 3) != 0x0);

    u32 cnt = XGpio_DiscreteRead(&(InjDesc->Gpio), 1);
    printf("Test result cnt = %d\n\r", cnt);
}



int InjectorInitialize(InjectorDescriptor *InjDesc){
	InjDesc->host_socket_ptr   = (uint32_t*) HOST_SOCKET_ADR;
	InjDesc->fault_list_ptr    = (FaultDescriptor*) HOST_FAULT_LIST_ADR;
	InjDesc->clock_ctrl_ptr    = (uint32_t*) CLK_CTRL_BASE;

	int Status;
	u32 ConfigRegData;
	/* Initialize the GPIO driver */
	Status = XGpio_Initialize(&(InjDesc->Gpio), XPAR_GPIO_0_DEVICE_ID);
	if (Status != XST_SUCCESS) {
		xil_printf("Gpio Initialization Failed\r\n");
		return XST_FAILURE;
	}
	XGpio_SetDataDirection(&(InjDesc->Gpio), 1, 0x00);

	/* Initialize the HwIcap instance */
	InjDesc->CfgPtr = XHwIcap_LookupConfig(HWICAP_DEVICEID);
		if (InjDesc->CfgPtr == NULL) { return XST_FAILURE; }
	Status = XHwIcap_CfgInitialize(&(InjDesc->HwIcap), InjDesc->CfgPtr, InjDesc->CfgPtr->BaseAddress);
		if (Status != XST_SUCCESS) { return XST_FAILURE;}
	Status = XHwIcap_GetConfigReg(&(InjDesc->HwIcap), XHI_IDCODE, &ConfigRegData);
		if (Status != XST_SUCCESS) { return XST_FAILURE; }
		InjDesc->HwIcap.DeviceIdCode = ConfigRegData & 0x0FFFFFFF;
	printf("ICAP: Device ID          = %08x\n\r", ConfigRegData);
	printf("ICAP: Frame Size         = %03d\n\r", InjDesc->HwIcap.WordsPerFrame);
	printf("ICAP: Readback pad words = %03d\n\r", READBACK_PAD_WORDS);

	InjDesc->SlrId[0] = InjDesc->HwIcap.DeviceIdCode; //0x04b31093;
	InjDesc->SlrId[1] = 0x04b22093;
	InjDesc->SlrId[2] = 0x04b24093;

	InjDesc->DebugMode = DEBUG_MODE;
	return(0);
}



int main()
{
    init_platform();
	InjectorInitialize(&InjDesc);
	printf("Injector Initialized\n\r");

	/*
	FaultDescriptor fdesc = {.CellType=0, .FAR=0x0, .Id=0x0, .Offset=0x0, .SLR=0x0, .mask=0x0, .time=0x0, .word=0x0};
    while(1){
    	//print("Input SLR index (0 to 10):\n\r");
    	//fdesc.SLR = input_int(16);
    	print("Input FAR:\n\r");
    	fdesc.FAR = input_int(16);
    	print("Input word:\n\r");
    	fdesc.word = input_int(16);
    	print("Input mask:\n\r");
    	fdesc.mask = input_int(16);
    	FlipBits(&InjDesc, &fdesc);
    	log_Frame(&InjDesc, fdesc.SLR, fdesc.FAR);
    }
	 */



    /* HOST_SOCKET_ADR + offset
     * 					 in:	0 (+0)  : 	Command	(0x0 - NOP,  0x1 - Inject, 0x2 - Recover, 0xF - Terminate)
     * 					 in:	1 (+4)  :	Data	(Fault list index)
     * 					 out:   2 (+8)  :	Status	(0x0 - idle, 0x1 - busy,   0x2 - error)
     * 					 out:   3 (+A) :    Message to host (e.g. echo fault.Id after successful injection)
     */
    printf("Fault list address = %08x\n\r", InjDesc.fault_list_ptr);
    u32 * ptr_cmd    = InjDesc.host_socket_ptr + 0;
    u32 * ptr_data   = InjDesc.host_socket_ptr + 1;
    u32 * ptr_status = InjDesc.host_socket_ptr + 2;
    u32 * message    = InjDesc.host_socket_ptr + 3;
    u32 host_cmd=0, host_data=0;

    while(1){
    	//printf("Input data (0xFFFF to exit loop)\n\r");
    	do{
    		host_cmd 	= *ptr_cmd;
    		host_data	= *ptr_data;
    	} while( host_cmd == 0x0);

    	int Status=0;
    	if(DEBUG_MODE) printf("FFI command: %d, data: %08x\n\r", host_cmd, host_data);
    	*ptr_cmd = 0x0;

    	if(host_cmd==0xF){
    		break;
    	}
    	else if(host_cmd==0x1){
    		*ptr_status = 0x1;
    		Status = ProcessFaultDescriptor(&InjDesc, host_data);
    	}
    	else if(host_cmd==0x2){
    		//stub for recover routine: in case of non-changeable CM recovery is equivalent to flipping the bits again
    		*ptr_status = 0x1;
    		Status = ProcessFaultDescriptor(&InjDesc, host_data);
    	}

    	if(Status==0){
    		*ptr_status = 0x0;
    		*message 	= host_data;
    	}
    	else{
    		*ptr_status = 0x2;
    	}
    };


	//test_clk_ctrl();




    cleanup_platform();
    return 0;
}





