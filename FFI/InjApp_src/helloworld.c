/*
 *  TemplateApp.c
 *
 *  Template SEU emulation Application
 *  DUT Example: MC8051 core implemented on ZC702 board
 *
 *  Created on: 2 Oct 2018
 *      Author: Ilya Tuzov
 *              Universidad Politecnica de Valencia
 *
 *  MIT license
 *  Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector
 */



#include "xparameters.h"	// SDK generated parameters
#include "platform.h"
#include <stdio.h>
#include <stdlib.h>
#include "xgpiops.h"		//General-Purpose IO to interact with DUT
#include "ff.h"				//Xilinx File system library for caching of Injector data
#include "SeuInjector.h"	//Injector library
#include "xtime_l.h"

#define BUFFER_ADDR 			0x3E000000
static FATFS fatfs;
static XGpioPs PsGpioPort;
extern XGpioPs_Config XGpioPs_ConfigTable[XPAR_XGPIOPS_NUM_INSTANCES];
InjectorDescriptor 	InjDesc;
JobDescriptor 		JobDesc;







int main()
{


	XGpioPs_Config* GpioConfigPtr;	//GPIO to interact with DUT

	init_platform();
	//init_uart();
	Xil_DCacheDisable();		//Disable the caches for correct PCAP operation
	Xil_ICacheDisable();

	//PS GPIO Intialization
	GpioConfigPtr = XGpioPs_LookupConfig(XPAR_PS7_GPIO_0_DEVICE_ID);
	if(GpioConfigPtr == NULL)return XST_FAILURE;
	int Status = XGpioPs_CfgInitialize(&PsGpioPort, GpioConfigPtr, GpioConfigPtr->BaseAddr);
	if(XST_SUCCESS != Status) print(" PS GPIO INIT FAILED \n\r");
	printf("EMIO-GPIO banks: %d, pins: %d\n", PsGpioPort.MaxBanks, PsGpioPort.MaxPinNum);


	//RunDutTest(1);

	//input_int();

	//Mount SD card to use file caching
	TCHAR *Path = "0:/";
	FRESULT Res = f_mount(&fatfs, Path, 0);
	if (Res != FR_OK) { printf("Error Mounting FAT-FS\n"); }


	//Auto-initialize the injector structures,  using the DevC ID from Xparameters, pass a DUT-specific callback function to Run the Workload and check it's outputs
	InjectorInitialize(&InjDesc, XPAR_XDCFG_0_DEVICE_ID, &RunDutTest, &TriggerGSR);
	InjDesc.cache_enabled = 1;				//enable caching of InjectorData, logical drive should be previously mounted (on SD card)

	ReadJobDesc(&JobDesc, BUFFER_ADDR, 1);	//Parse Job Data, uploaded from host
	JobDesc.FilterFrames = 0;				//ENABLE FRAME FILTERING ONLY IF EXTERNAL BITMASK IS NOT USED
	//JobDesc.UpdateBitstream=0;
	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);

	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);



    cleanup_platform();
    return 0;
}







/* ------------------------------------------------
 * Adapt the functions below according to the DUT
 * ------------------------------------------------ */

u32 test_vector_size = 10;

void TriggerGSR(){
	//XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000);
	//XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x20000);
	//CustomSleep(1);
	//XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000);
	//CustomSleep(1);
	//printf("GSR triggered\n");
}



int RunDutTest(int StopAtFirstMismatch){
	u32 mismatches = 0;


	ResetPL(100);			//reset the DUT
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFFFFFFFF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFFFFFFFF);
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x00000000);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);

	for(int i=0;i<test_vector_size;i++){
		u32 a = (i+1)*4+1;
		u32 b = (i+5)*11;
		u32 res_ref = a+b;


		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00010000  | (a & 0xFFFF)  ); 		RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00020000  | ((a>>16) & 0xFFFF) ); 	RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00030000  | (b & 0xFFFF) ); 		RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00040000  | ((b>>16) & 0xFFFF)); 	RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000001); 							RunClockCount(100); WaitClockStops();
		u32 res_uut = XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK3);  						RunClockCount(100); WaitClockStops();

		if(res_ref != res_uut) mismatches++;
		//printf("res_ref = %10d, res_uut = %10d, mismatches=%2d\n", res_ref, res_uut, mismatches);
	}


	return(mismatches > 0);
}



int InjectionFlowDutEnvelope(u32* alarm){
	u32 mismatches = 0;
	*alarm=0;

	ResetPL(100);			//reset the DUT
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFFFFFFFF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFFFFFFFF);
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x00000000);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);

	RunInjectionFlow(&InjDesc, &JobDesc, 1);


	for(int i=0;i<test_vector_size;i++){
		u32 a = (i+1)*4+1;
		u32 b = (i+5)*11;
		u32 res_ref = a+b;

		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00010000  | (a & 0xFFFF)  ); 		RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00020000  | ((a>>16) & 0xFFFF) ); 	RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00030000  | (b & 0xFFFF) ); 		RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00040000  | ((b>>16) & 0xFFFF)); 	RunClockCount(100); WaitClockStops();
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000001); 							RunClockCount(100); WaitClockStops();
		u32 res_uut = XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK3);  						RunClockCount(100); WaitClockStops();

		if(res_ref != res_uut) mismatches++;
		//printf("res_ref = %10d, res_uut = %10d, mismatches=%2d\n", res_ref, res_uut, mismatches);
	}


	return(mismatches > 0);
}


