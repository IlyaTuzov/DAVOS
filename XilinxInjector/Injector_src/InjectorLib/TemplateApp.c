/*
 * SeuInjector.c
 *
 *  Created on: 2 Oct 2018
 *      Author: ILYA Tuzov 
 *              Universidad Politecnica de Valencia
 *  
 *  Template SEU emulation Application 
 *  DUT Example: MC8051 core implemented on ZC702 board
 */
 
 
#include "xparameters.h"	// SDK generated parameters
#include "platform.h"
#include <stdio.h>
#include <stdlib.h>
#include "ff.h"				//Xilinx File system library for caching of Injector data
#include "xgpiops.h"		//General-Purpose IO to interact with DUT
#include "SeuInjector.h"	//Injector library

//Address of the buffer memory section for the files uploaded from the host (DEFINE separate section in the linker script to prevent memory conflicts)
#define BUFFER_ADDR 			0x3E000000

//General-Purpose IO (GPIO for interaction with DUT)
static XGpioPs PsGpioPort;
extern XGpioPs_Config XGpioPs_ConfigTable[XPAR_XGPIOPS_NUM_INSTANCES];

static FATFS fatfs;


InjectorDescriptor 	InjDesc;
JobDescriptor 		JobDesc;


//Workload-specific variables
#define WorkloadClocks 			35000		//Workload (matrix processing) duration in clock cycyles
#define ClkPerItemReadout  		200			//Clocks to readout each result item (array/matrix item)
#define TraceVectorItems 		20			//Size of Workload result (number of items to readout)
u32 TraceVectorInj[TraceVectorItems];
//reference Workload processign result, obtained by simulation in Keil uVision and ModelSim
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




int RunDutTest(int StopAtFirstMismatch);	//Run Workload and check the failure mode
int CustomInjectionFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc);


int main()
{
	XGpioPs_Config* GpioConfigPtr;	//GPIO to interact with DUT

	init_uart();
	Xil_DCacheDisable();		//Disable the caches for correct PCAP operation
	Xil_ICacheDisable();

	//PS GPIO Intialization
	GpioConfigPtr = XGpioPs_LookupConfig(XPAR_PS7_GPIO_0_DEVICE_ID);
	if(GpioConfigPtr == NULL)return XST_FAILURE;
	int Status = XGpioPs_CfgInitialize(&PsGpioPort, GpioConfigPtr, GpioConfigPtr->BaseAddr);
	if(XST_SUCCESS != Status) print(" PS GPIO INIT FAILED \n\r");
	printf("EMIO-GPIO banks: %d, pins: %d\n", PsGpioPort.MaxBanks, PsGpioPort.MaxPinNum);

	//Mount SD card
	TCHAR *Path = "0:/";
	FRESULT Res = f_mount(&fatfs, Path, 0);
	if (Res != FR_OK) { printf("Error Mounting FAT-FS\n"); }

	//Auto-initialize the injector structures,  using the DevC ID from Xparameters, pass a DUT-specific callback function to Run the Workload and check it's outputs
	InjectorInitialize(&InjDesc, XPAR_XDCFG_0_DEVICE_ID, &RunDutTest);
	InjDesc.cache_enabled = 1;				//enable caching of InjectorData, logical drive should be previously mounted (on SD card)

	ReadJobDesc(&JobDesc, BUFFER_ADDR, 1);	//Parse Job Data, uploaded from host



	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);

	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);

	//Run with custom injection flow
	//JobDesc.FaultMultiplicity = 3;
	//InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, &CustomInjectionFlow);

    cleanup_platform();
    return(0);
}




//Runs workload for given DUT
//Checks outputs and returns failure mode:
//0 : masked (no fault effect), > 0 : failure (any)
int RunDutTest(int StopAtFirstMismatch){
	//Run DUT-specific workload
	RunClockCount(100);
	ResetPL(0);			//reset the DUT
	//DUT (MC8051) interacts with PS through IO ports connected to GPIO
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
	//supply the input data to DUT
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);

	//activate the PS->PL clock for WorkloadClocks cycles and wait for completion
	RunClockCount((u16)WorkloadClocks);
	WaitClockStops();

	//Read-out the Workload processing results from DUT memory, item by item (vector/matrix of 16-bit integers)
	//Memory address on port_3 -> mapped on GPIO BANK_2 [31:24]
	//Result 16-bits -> mapped on GPIO BANK_2 [23:8]
	int mismatches = 0;
	memset(&TraceVectorInj[0], 0, sizeof(TraceVectorInj));
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
		XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, i<<24);
		RunClockCount(ClkPerItemReadout);
		WaitClockStops();
		TraceVectorInj[i] = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) >> 8) & 0x0000FFFF;
		if(TraceVectorInj[i]!=TraceVectorRef[i]){
			mismatches++;
			//printf("CheckTraces: Trace mismatch %2d: %08x <> %08x\n", i, TraceVectorInj[i], TraceVectorRef[i]);
			if(StopAtFirstMismatch) break;
		}
	}


	return(mismatches > 0);
}







//Example of Custom Injection Flow
//Inject multiple random faults at random time along the Workload execution
int CustomInjectionFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc){
	RunClockCount(100);
	ResetPL(0);			//reset the DUT
	//Run DUT-specific workload
	//DUT (MC8051) interacts with PS through IO ports connected to GPIO
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);

	int InjTime = rand()%WorkloadClocks;					//Injection time at which fault is injected (measured in clock cycles)
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);	//supply input data to DUT
	RunClockCount((u16)InjTime);							//run workload until injection time
	WaitClockStops();
	//Inject randomly distributed faults
	for(int i=0;i<JobDesc->FaultMultiplicity;i++){
		InjectionCoorditates InjPoint = NextRandomInjectionTarget(InjDesc, JobDesc);
		FlipBits(InjDesc, InjPoint, 0, 0);
	}
	RunClockCount((u16)(WorkloadClocks-InjTime));			//run the rest of workload
	WaitClockStops();

	//Read-out the Workload processing results from DUT memory, item by item (vector/matrix of 16-bit integers)
	//Memory address on port_3 -> mapped on GPIO BANK_2 [31:24]
	//Result 16-bits -> mapped on GPIO BANK_2 [23:8]
	int mismatches = 0;
	memset(&TraceVectorInj[0], 0, sizeof(TraceVectorInj));
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
		XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, i<<24);
		RunClockCount(ClkPerItemReadout);
		WaitClockStops();
		TraceVectorInj[i] = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) >> 8) & 0x0000FFFF;
		if(TraceVectorInj[i]!=TraceVectorRef[i]){
			mismatches++;
			break;
		}
	}

	return(mismatches > 0);
}


