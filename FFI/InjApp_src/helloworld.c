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



#define WorkloadClocks 					35000		//Workload duration in clock cycyles
#define TimeoutClocks					5000

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


#define BaseAdr 0x3FC00000


/* Write to memory location or register */
#define X_mWriteReg(BASE_ADDRESS, RegOffset, data) \
           *(unsigned int *)(BASE_ADDRESS + RegOffset) = ((unsigned int) data)
/* Read from memory location or register */
#define X_mReadReg(BASE_ADDRESS, RegOffset) \
           *(unsigned int *)(BASE_ADDRESS + RegOffset)

int RunDutTest(int StopAtFirstMismatch);	//Run Workload and check the failure mode
int CustomInjectionFlow();
InjectionStatistics RunSamplingFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);
InjectionStatistics RunExhaustiveFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);
InjectionStatistics RunFaultList(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);

InjectionStatistics RunCustom(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);



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
	InjectorInitialize(&InjDesc, XPAR_XDCFG_0_DEVICE_ID, &RunDutTest);
	InjDesc.cache_enabled = 1;				//enable caching of InjectorData, logical drive should be previously mounted (on SD card)

	ReadJobDesc(&JobDesc, BUFFER_ADDR, 1);	//Parse Job Data, uploaded from host
	JobDesc.FilterFrames = 0;				//ENABLE FRAME FILTERING ONLY IF EXTERNAL BITMASK IS NOT USED
	//JobDesc.UpdateBitstream = 1;

	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);

	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);


	Status = ReloadCompleteBitstream(InjDesc.DevcI, JobDesc.BitstreamAddr, (JobDesc.BitstreamSize >> 2));
	RunDutTest(1);
	SaveCheckpoint(&InjDesc);



	//RunCustom(&InjDesc, &JobDesc, 1);
	//input_int();


	JobDesc.mode = 101;
	JobDesc.BlockType = 1;


	if(JobDesc.mode == 101){
		printf("Running Sampling Mode Without Callbacks\n\n");
		res = RunSamplingFlowWithoutCallbacks(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}
	else if(JobDesc.mode == 102){
		printf("Running Exhaustive Mode Without Callbacks\n\n");
		res = RunExhaustiveFlowWithoutCallbacks(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}
	else if(JobDesc.mode == 103){
		printf("Running Exhaustive Injection From Fault List\n\n");
		res = RunFaultList(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}

    cleanup_platform();
    return 0;
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
		//printf("%d : %08x\n",i, TraceVectorInj[i]);
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			if(StopAtFirstMismatch)break;
		}
	}
	//printf("Mismatches: %d \n", mismatches);
	return(mismatches > 0);
}



//Example of Custom Injection Flow
//Inject multiple random faults at random time along the Workload execution
//int CustomInjectionFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc){
int CustomInjectionFlow(){
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x3F);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x3F);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);

	ResetPL(1000);

	int InjTime = rand()%(WorkloadClocks);			//Injection time at which fault is injected (measured in clock cycles)
	//printf("Running CustomInjectionFlow time = %d\n", InjTime);
	RunClockCount((u16)InjTime);							//run workload until injection time
	WaitClockStops();
	//Inject randomly distributed faults
	InjectionCoorditates InjPoint;
	FarFields Frame;

	for(int i=0;i<JobDesc.FaultMultiplicity;i++){
		InjPoint = NextRandomInjectionTarget(&InjDesc, &JobDesc);

		if(JobDesc.BlockType==1){
			int err = FlipBits(&InjDesc, InjPoint, 0, 1, 1);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x20);
			CustomSleep(10);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
			CustomSleep(10);
		}
		else{
			int err = FlipBits(&InjDesc, InjPoint, 0, 0, 1);
		}
	}

	RunClockCount((u16)(WorkloadClocks-InjTime));			//run the rest of workload
	WaitClockStops();

	int mismatches=0;
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, i<<24);
		RunClockCount(200);
		WaitClockStops();
		TraceVectorInj[i] = TraceVectorInj[i] = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) >> 8) & 0x0000FFFF;
		//printf("%d : %08x\n",i, TraceVectorInj[i]);
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			break;
		}
	}
	Frame = parseFAR(InjPoint.FAR);
	//if(mismatches > 0) printf("Time = %5d, Failure at: FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d Mismatches=%5d \n", InjTime, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit, mismatches);
	//else printf("Time = %5d, Masked at: FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d Mismatches=%5d \n", InjTime, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit, mismatches);
	return(mismatches > 0);
}




InjectionStatistics RunCustom(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	InjectionStatistics res;
	int FAR_t [610] = { 0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x0000099f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a1f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000a9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000b9f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000c1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d1f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000d9f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e1f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000e9f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f1f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x00000f9f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000101f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000111f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f,  0x0000119f};
	int offset [610] = {1155,  1180,  1185,  1210,  1219,  1220,  1244,  1283,  1284,  1308,  1347,  1372,  1377,  1411,  1412,  1436,  1476,  1539,  1540,  1564,  1565,  1569,  1570,  1595,  1635,  1636,  1637,  1661,  1699,  1891,  1892,  2019,  2020,  2044,  2045,  2083,  2084,  2108,  2148,  2211,  2212,  2236,  2237,  2275,  2300,  2660,  2661,  2679,  2685,  2690,  1539,  1540,  1564,  1565,  1635,  1660,  1665,  1828,  1891,  1892,  1916,  1917,  1921,  1922,  1947,  1955,  1956,  1980,  1985,  2019,  2020,  2045,  2083,  2084,  2108,  2109,  2114,  2147,  2148,  2173,  2211,  2212,  2236,  2237,  2275,  2276,  2277,  2301,  2306,  2339,  2340,  2365,  2595,  2596,  2598,  2614,  2620,  2621,  2625,  2626,  2659,  2662,  2678,  2684,  2723,  2724,  2748,  2749,  2753,  2754,  2787,  2812,  1540,  1635,  1660,  1699,  1700,  1724,  1729,  1763,  1764,  1788,  1789,  1794,  1819,  1827,  1828,  1829,  1847,  1852,  1853,  1891,  1892,  1916,  1917,  1921,  1955,  2019,  2020,  2044,  2049,  2074,  2084,  2147,  2148,  2173,  2211,  2275,  2339,  2404,  2595,  2659,  2684,  2723,  1475,  1476,  1477,  1478,  1494,  1495,  1500,  1501,  1540,  1564,  1565,  1569,  1570,  1635,  1636,  1700,  1724,  1725,  1729,  1730,  1763,  1764,  1788,  1789,  1793,  1827,  1892,  1955,  1956,  1981,  2020,  2083,  2084,  2108,  2109,  2148,  2173,  2211,  2212,  2236,  2237,  2242,  2267,  2275,  2276,  2300,  2305,  2339,  2340,  2365,  2403,  2404,  2428,  1411,  1475,  1476,  1477,  1478,  1494,  1495,  1500,  1501,  1539,  1540,  1564,  1635,  1660,  1665,  1700,  1724,  1763,  1764,  1788,  1789,  1793,  1794,  1818,  1819,  1827,  1891,  1892,  2019,  2020,  2044,  2083,  2084,  2108,  2113,  2147,  2148,  2172,  2173,  2211,  2212,  2237,  2275,  2339,  2340,  2403,  2404,  2429,   579,   580,   604,   609,   964,   989,  1028,  1053,  1475,  1476,  1500,  1539,  1564,  1565,  1635,  1660,  1661,  1665,  1666,  1690,  1691,  1699,  1700,  1701,  1725,  1730,  1755,  1763,  1764,  1788,  1789,  1828,  1891,  1892,  1916,  1917,  1921,  1955,  1956,  1981,  1986,  2019,  2020,  2022,  2045,  2084,  2109,  2147,  2148,  2173,  2211,  2212,  2237,  2275,  2276,  2301,  2306,  2339,  2364,  2403,  2428,   452,   516,   541,   579,   580,   604,   605,   643,   668,   669,   673,   707,   708,   710,   732,   737,   762,   963,   988,  1027,  1052,  1539,  1540,  1565,  1570,  1636,  1637,  1660,  1661,  1665,  1666,  1690,  1691,  1700,  1724,  1725,  1729,  1754,  1763,  1764,  1827,  1852,  1892,  1955,  1956,  2019,  2020,  2021,  2044,  2045,  2083,  2084,  2109,  2276,   387,   388,   413,   452,   477,   643,   707,   732,   772,   836,  1219,  1475,  1476,  1539,  1540,  1564,  1565,  1569,  1570,  1594,  1636,  1637,  1660,  1661,  1665,  1666,  1691,  1699,  1700,  1702,  1724,  1725,  1729,  1730,  1754,  1755,  1763,  1764,  1788,  1892,  1917,  1955,  1956,  2019,  2020,  2021,  2045,  2050,  2083,  2084,  2086,  2109,  2211,  2212,  2236,  2237,  2241,  2266,  2275,  2276,  2300,  2305,  2339,   451,   772,   835,  1117,  1220,  1411,  1475,  1476,  1500,  1539,  1540,  1564,  1635,  1636,  1637,  1660,  1661,  1665,  1666,  1690,  1691,  1699,  1700,  1725,  1763,  1764,  1827,  1828,  1852,  1853,  1857,  1858,  1883,  1891,  1892,  1917,  1922,  1947,  1955,  1980,  2019,  2020,  2022,  2038,  2044,  2045,  2083,  2084,  2108,  2113,  2138,  2147,  2172,  2177,  2202,  2211,  2212,  2236,  2241,  2266,  2275,  2276,  2301,  2306,  2339,  2340,  2342,  2365,  2403,   579,   643,   899,  1156,  1411,  1635,  1660,  1665,  1690,  1699,  1700,  1724,  1763,  1764,  1827,  1828,  1891,  1892,  1916,  1917,  1922,  1947,  1955,  1956,  1981,  2019,  2020,  2021,  2044,  2045,  2148,  2212,  2275,  2278,  2294,  2300,  1476,  1699,  1700,  1763,  1764,  1827,  1828,  1853,  1891,  1892,  1955,  1956,  1980,  1981,  1985,  1986,  2011,  2019,  2020,  2084,  2147,  2148,  2211,  2212,  2214,  2276,  2301,  1348,  1373,  1476,  1763,  1788,  1793,  1827,  2147,  2148,  2172,  2177,  2211,  2212,  2236,  2237,  2241,  1700,  1892,  1917,  1922,  2084,  2109,  2148,  2211,  2212,  1699,  1700,  1764,  1828,  1892,  1893,  1917,  1922,  2147,  2148,  2211,  2212,  2275,  2276,  2301,  2306};





		for(int i=0;i<606;i++){


			int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
			ResetPL(1000);

			XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0xFF0000FF);
			XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0xFF0000FF);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000009);


			XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK3, 0x3F);
			XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK3, 0x3F);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00000000);

			int InjTime = rand()%(10000);			//Injection time at which fault is injected (measured in clock cycles)
			RunClockCount((u16)InjTime);							//run workload until injection time
			WaitClockStops();


			InjectionCoorditates InjPoint = {.FAR=FAR_t[i], .word=offset[i]/32, .bit=offset[i]%32, .FrameIndex=0x359};
			FlipBits(InjDesc, InjPoint, 0, 1, 1);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x20);
			CustomSleep(10);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK3, 0x00);
			CustomSleep(10);

			RunClockCount((u16)(WorkloadClocks-InjTime));			//run the rest of workload
			WaitClockStops();


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

			int fmode=0;
			if(mismatches > 0){fmode=1;}
			else if(CountCheckpointMismatches(InjDesc) > 0){fmode=2;}
			else { fmode = 0; };

			printf("Injecting: %8d at (%08x, %d, %d) || %8d\n", i, InjPoint.FAR, InjPoint.word, InjPoint.bit,  fmode);
		}

	return(res);
}




InjectionStatistics RunFaultList(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	InjectionStatistics res = {.complete_reconfigurations=0, .failure_error_margin=50.0, .failure_rate=0.0, .failures=0, .injections=0, .masked=0, .masked_error_margin=50.0, .masked_rate=0.0, .population =  JobDesc->FaultListItems };
	FaultListItem item;
	ClockThrottle(0x1);
	int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
	InjectionCoorditates InjPoint;
	int errframecnt=0;


	for(int i=0;i<JobDesc->FaultListItems;i++){
		InjPoint = GetTargetFromInjectionList(InjDesc, JobDesc, i, &item);
		int locked = FlipBits(InjDesc, InjPoint, 0, 0, 1); if(locked>0) errframecnt++;


		RunClockCount(100); ResetPL(0);

		int failure = RunDutTest(1);
		item.injres = failure;
		if(failure > 0) res.failures++;
		else res.masked++;

		res.injections++;
		printf(">> Injecting: %8d at %08x || %8d;%8d;%8d;%8d;%14.10f;%8d\n", i, InjPoint.FrameIndex, item.ID,item.FAR,item.word,item.bit,item.actime, failure);

		if(res.injections % JobDesc->LogTimeout == 0){
	    	res.failure_rate = 100.0*res.failures/res.injections;
	    	res.masked_rate = 100.0*res.masked/res.injections;
	    	printf("Tag_%9d | Injection[%9d] / [%.0f]  complete_reconfigurations= %5d | locked_targets= %5d | Masked: %6d, Rate= %.3f +/- %.3f | Failures: %6d, Rate = %.3f +/- %.3f\n", JobDesc->SyncTag,  res.injections,  0.0,  res.complete_reconfigurations, errframecnt, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin);
		}
		ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));

/*
	    recover_bitstream(InjDesc, JobDesc,  item.injres);

		//check that system has been recovered (slows down the experimentation when Tworkload ~ Trecovery)
		if(JobDesc->CheckRecovery > 0){
			if(res.injections % JobDesc->CheckRecovery == 0){
				//Execute Workload and check failure mode
			    failure = RunDutTest(1);
			    if(failure){
					//printf("Complete reconfiguration required after Injection[%5d] FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d\n", res.injections, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit);
					int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
					res.complete_reconfigurations++;
					if (Status != XST_SUCCESS) { xil_printf("ReloadCompleteBitstream ERROR \n\r");}
					//printf("Complete bitstream reloaded\n");
			    }
			}
		}
*/

	}

	return(res);
}



//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunSamplingFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	int errframecnt=0;
	float N = JobDesc->PopulationSize;

	InjectionStatistics res = {.complete_reconfigurations=0, .failure_error_margin=50.0, .failure_rate=0.0, .failures=0, .injections=0, .masked=0, .masked_error_margin=50.0, .masked_rate=0.0, .latent=0, .latent_rate=0.0, .latent_error_margin=50.0, .population =  N };
	printf("Injector RunInSamplingMode: %s, BlockType = %d (%s), PopulationSize = %.0f, min_sample_size=%d, max_error_margin = %0.5f\n", JobDesc->Essential_bits>0?"Essential bits":"Blind", JobDesc->BlockType,   JobDesc->BlockType==0?"CLB":"BRAM", N, JobDesc->SampleSizeGoal, JobDesc->ErrorMarginGoal);

	if(JobDesc->StartIndex > 0){
		res.injections = (int) JobDesc->StartIndex;
		res.failures = (int) JobDesc->CurrentFailureCount;
		res.masked   = (int) JobDesc->CurrentMaskedCount;
        //skip all previosly tested targets (recover the state of random target generator)
        for(int i=0;i<JobDesc->StartIndex;i++) NextRandomInjectionTarget(InjDesc, JobDesc);
        printf("\n\nRANDOM GENERATOR RECOVERED\n");
	}


	ClockThrottle(0x1);
	int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));


	while( 		(JobDesc->SampleSizeGoal>0 && res.injections<JobDesc->SampleSizeGoal) 																	/* until given sample size */
			||  (JobDesc->ErrorMarginGoal>0 && (res.failure_error_margin>JobDesc->ErrorMarginGoal || res.masked_error_margin>JobDesc->ErrorMarginGoal)) /* until given error margin */
			|| 	(JobDesc->SampleSizeGoal==0 && JobDesc->ErrorMarginGoal==0 && res.injections < N) )														/* until sampling complete population */
	{


		int	failure   = CustomInjectionFlow();
		int cp_mismatches = CountCheckpointMismatches(InjDesc);

		res.injections++;
	    if(failure > 0) res.failures++;
	    else if(cp_mismatches > 0 && failure==0) res.latent++;
	    else res.masked++;
	    if(res.injections % JobDesc->LogTimeout == 0 || res.injections >= N){
	    	res.failure_rate = 1.0*res.failures/res.injections;
	    	res.masked_rate = 1.0*res.masked/res.injections;
	    	res.latent_rate = 1.0*res.latent/res.injections;
	    	if((N-res.injections) > 0){
		    	res.failure_error_margin = 2.576*sqrt( res.failure_rate*(1-res.failure_rate)*(N-res.injections)/(res.injections*(N-1)) );
		    	res.masked_error_margin =  2.576*sqrt( res.masked_rate*(1-res.masked_rate)*(N-res.injections)/(res.injections*(N-1)) );
		    	res.latent_error_margin =  2.576*sqrt( res.latent_rate*(1-res.latent_rate)*(N-res.injections)/(res.injections*(N-1)) );
	    	}
	    	else{
	    		res.failure_error_margin = 0.0;
	    		res.masked_error_margin = 0.0;
	    		res.latent_error_margin = 0.0;
	    	}
	    	res.failure_rate *= 100.0; res.masked_rate  *= 100.0; res.failure_error_margin *= 100.0; res.masked_error_margin *= 100.0; res.latent_rate *= 100.0; res.latent_error_margin *= 100.0;
	    	printf("Tag_%9d | Injection[%9d] / [%.0f]  complete_reconfigurations= %5d | locked_targets= %5d | Masked: %6d, Rate= %.3f +/- %.3f | Failures: %6d, Rate = %.3f +/- %.3f | Latent: %6d, Rate = %.3f +/- %.3f\n", JobDesc->SyncTag,  res.injections,  N,  res.complete_reconfigurations, errframecnt, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin, res.latent, res.latent_rate, res.latent_error_margin);
	    }

	    //ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));


	    //Recover to fault-free state
	    recover_bitstream(InjDesc, JobDesc,  failure);

		//check that system has been recovered (slows down the experimentation when Tworkload ~ Trecovery)
		if(JobDesc->CheckRecovery > 0){
			if(res.injections % JobDesc->CheckRecovery == 0){
				//Execute Workload and check failure mode
			    failure = RunDutTest(1);
			    if(failure){
					//printf("Complete reconfiguration required after Injection[%5d] FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d\n", res.injections, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit);
					int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
					res.complete_reconfigurations++;
					if (Status != XST_SUCCESS) { xil_printf("ReloadCompleteBitstream ERROR \n\r");}
					//printf("Complete bitstream reloaded\n");
			    }
			}
		}

	}


	return(res);
}




//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunExhaustiveFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	int errframecnt=0;

	InjectionStatistics res = {.complete_reconfigurations=0, .failure_error_margin=0.0, .failure_rate=0.0, .failures=0, .injections=0, .masked=0, .masked_error_margin=0.0, .masked_rate=0.0, .population =  0 };



	ClockThrottle(0x1);
	int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));

	for(int FrameIndex=0; FrameIndex < InjDesc->FrameDescriptorsCount; FrameIndex++){
	    //skip pad frames
	    if(get_bit(InjDesc->ReferenceFrames[FrameIndex].Flags, 1) == 1) continue;
	    u32 FAR = InjDesc->ReferenceFrames[FrameIndex].FAR;
	    FarFields Frame = parseFAR(FAR);

	    //proceed only when logic type matches
	    if(Frame.BLOCK != JobDesc->BlockType) continue;

	    for(u32 Word=0; Word<FRAME_SIZE; Word++){
			if(Frame.BLOCK == 0 && Word==50) continue;	//Word 50 in CLB is not accessible for injection

			for(u32 bit=0; bit<32; bit++){
				//skip non-essential bits (mask == 0)
				if(JobDesc->Essential_bits>0)
					if(get_bit(InjDesc->ReferenceFrames[FrameIndex].Mask[Word], bit) == 0) continue;

				res.injections++;
				InjectionCoorditates InjPoint = {.FAR = FAR, .FrameIndex = FrameIndex, .word = Word, .bit = bit};
				FlipBits(InjDesc, InjPoint, 0, 0, 1);
				int failure = RunDutTest(1);
				printf(">> Injecting: %8d at %08x (Block=%5d, Top=%5d, Row=%5d, Major=%5d, Minor=%5d) || %8d;%8d;%8d;%8d\n", res.injections, InjPoint.FrameIndex, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.FAR, InjPoint.word, InjPoint.bit, failure);

				if(failure > 0) res.failures++;
				else res.masked++;

				if(res.injections % JobDesc->LogTimeout == 0){
			    	res.failure_rate = 100.0*res.failures/res.injections;
			    	res.masked_rate = 100.0*res.masked/res.injections;
			    	printf("Tag_%9d | Injection[%9d] / [%.0f]  complete_reconfigurations= %5d | locked_targets= %5d | Masked: %6d, Rate= %.3f +/- %.3f | Failures: %6d, Rate = %.3f +/- %.3f\n", JobDesc->SyncTag,  res.injections,  0.0,  res.complete_reconfigurations, errframecnt, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin);
				}


			    recover_bitstream(InjDesc, JobDesc,  failure);

				//check that system has been recovered (slows down the experimentation when Tworkload ~ Trecovery)
				if(JobDesc->CheckRecovery > 0){
					if(res.injections % JobDesc->CheckRecovery == 0){
						//Execute Workload and check failure mode
					    failure = RunDutTest(1);
					    if(failure){
							//printf("Complete reconfiguration required after Injection[%5d] FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d\n", res.injections, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit);
							int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
							res.complete_reconfigurations++;
							if (Status != XST_SUCCESS) { xil_printf("ReloadCompleteBitstream ERROR \n\r");}
							//printf("Complete bitstream reloaded\n");
					    }
					}
				}

			}
	    }


	}


	return(res);
}
