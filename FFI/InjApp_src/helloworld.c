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

#define WorkloadClocks 					35000		//Workload duration in clock cycyles
#define ROW 4
#define COL 5
#define TraceVectorItems ROW*COL
#define NSIZE 4



u32 TraceVectorInj[TraceVectorItems];
u32 TraceVectorRef[TraceVectorItems] = {
		0x0000f9b9,
		0x0000fa8d,
		0x0000fc5f,
		0x00000a7b,
		0x0000f35b,
		0x000045f6,
		0x0000dc2a,
		0x0000bd44,
		0x0000e539,
		0x00006066,
		0x0000397f,
		0x0000af84,
		0x00008a57,
		0x00008a15,
		0x00009cd1,
		0x0000a813,
		0x000057d7,
		0x00003cd3,
		0x0000ac7d,
		0x0000d475};


void TriggerGSR(){
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x20);
	CustomSleep(1);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
	CustomSleep(1);
	//printf("GSR triggered\n");
}



int RunDutTest(int StopAtFirstMismatch){
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x3F);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x3F);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);

	ResetPL(1000);

	RunClockCount(WorkloadClocks);
	WaitClockStops();
	int mismatches=0;
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, i<<24);
		RunClockCount(200);
		WaitClockStops();
		TraceVectorInj[i] = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) >> 8) & 0x0000FFFF;
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			if(StopAtFirstMismatch)break;
		}
	}
	//printf("Mismatches: %d \n", mismatches);
	return(mismatches > 0);
}



int InjectionFlowDutEnvelope(){
	//1. Set the DUT input data
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x3F);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x3F);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);
	ResetPL(100);

	//2. Run WorkloadClocks, and inject faults within this time interval
	RunInjectionFlow(&InjDesc, &JobDesc, WorkloadClocks);

	//3. Read-out and verify the outputs (failures)
	int mismatches=0;
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, i<<24);
		RunClockCount(200);
		WaitClockStops();
		TraceVectorInj[i] = TraceVectorInj[i] = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) >> 8) & 0x0000FFFF;
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			break;
		}
	}
	return(mismatches > 0);
}


