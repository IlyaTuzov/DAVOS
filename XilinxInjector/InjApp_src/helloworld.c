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

#define BUFFER_ADDR 			0x3E000000

static FATFS fatfs;
static XGpioPs PsGpioPort;
extern XGpioPs_Config XGpioPs_ConfigTable[XPAR_XGPIOPS_NUM_INSTANCES];
InjectorDescriptor 	InjDesc;
JobDescriptor 		JobDesc;



#define WorkloadClocks 					14000		//Workload duration in clock cycyles
#define ClkPerItemReadout  				150			//Clocks to readout each result item
#define TraceVectorItems 				20			//Size of Workload result (number of items to readout)
u32 TraceVectorInj[TraceVectorItems];
u32 TraceVectorRef[TraceVectorItems] = {
		0x0000C12E,
		0x0000C92C,
		0x0000DB59,
		0x000068D1,
		0x00008186,
		0x000045F6,
		0x0000DC2A,
		0x0000BD44,
		0x0000E539,
		0x00006066,
		0x0000397F,
		0x0000AF84,
		0x00008A57,
		0x00008A15,
		0x00009CD1,
		0x0000A813,
		0x000057D7,
		0x00003CD3,
		0x0000AC7D,
        0x0000D475};

int RunDutTest(int StopAtFirstMismatch);	//Run Workload and check the failure mode
int CustomInjectionFlow();
InjectionStatistics RunCustomFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);




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

	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);

	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);

	//Run with custom injection flow
	//InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, &CustomInjectionFlow);

	//RunDutTest(0);
	//list_reference_frames(&InjDesc);
	//list_minor_frames(&InjDesc);

	if(JobDesc.mode > 10){
		printf("Running Custom Injection Flow Without Callbacks\n\n");
		res = RunCustomFlowWithoutCallbacks(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}


    cleanup_platform();
    return 0;
}









int RunDutTest(int StopAtFirstMismatch){
	int mismatches = 0;
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0x007E00FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0x007E00FF);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000000);

	//ClockThrottle(0x0);
	RunClockCount(WorkloadClocks);
	ResetPL(1);			//reset the DUT
	WaitClockStops();


	for(u32 i=0;i<TraceVectorItems;i++){
		TraceVectorInj[i] = 0;
		for(u32 j=0;j<2;j++){
			u32 dout = (((~j) & 0x1) << 7) | (j << 6) | (i & 0x3F);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, dout);
			//while( (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) & 0x00010000) == 0); // WE: 0--> 1
	        //while( (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) & 0x00010000) ); // WE: 1--> 0
			RunClockCount(ClkPerItemReadout);
			WaitClockStops();
			//printf("i=%2i, j=%2i, dout=%08x, din = %08x\n", i, j, dout, XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2));
			u32 v = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) & 0x0000FF00) >> 8;
			TraceVectorInj[i] = j>0 ?  TraceVectorInj[i]  | (v << 8) : TraceVectorInj[i] | v;
		}
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			if(StopAtFirstMismatch) break;
		}
	}
	//for(u32 i=0;i<TraceVectorItems;i++) printf("\nVect[%02d]=%08x", i, TraceVectorInj[i]);
	return(mismatches > 0);
}



//Example of Custom Injection Flow
//Inject multiple random faults at random time along the Workload execution
//int CustomInjectionFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc){
int CustomInjectionFlow(){
	int mismatches = 0;
	RunClockCount(100);
	ResetPL(1);			//reset the DUT
	//Run DUT-specific workload
	//DUT (AVR) interacts with PS through IO ports connected to GPIO
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0x007E00FF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0x007E00FF);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x00000000);	//set DUT inputs

	int InjTime = rand()%WorkloadClocks;					//Injection time at which fault is injected (measured in clock cycles)
	//printf("Running CustomInjectionFlow time = %d\n", InjTime);
	RunClockCount((u16)InjTime);							//run workload until injection time
	WaitClockStops();
	//Inject randomly distributed faults
	InjectionCoorditates InjPoint;
	FarFields Frame;

	for(int i=0;i<JobDesc.FaultMultiplicity;i++){
		InjPoint = NextRandomInjectionTarget(&InjDesc, &JobDesc);
		int err = FlipBits(&InjDesc, InjPoint, 0, 1);
	}



	RunClockCount((u16)(WorkloadClocks-InjTime));			//run the rest of workload
	WaitClockStops();

	//Read-out the Workload processing results from DUT memory, item by item (vector/matrix of 16-bit integers)
	for(u32 i=0;i<TraceVectorItems;i++){
		TraceVectorInj[i] = 0;
		for(u32 j=0;j<2;j++){
			u32 dout = (((~j) & 0x1) << 7) | (j << 6) | (i & 0x3F);
			XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, dout);
			RunClockCount(ClkPerItemReadout);
			WaitClockStops();
			u32 v = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) & 0x0000FF00) >> 8;
			TraceVectorInj[i] = j>0 ?  TraceVectorInj[i]  | (v << 8) : TraceVectorInj[i] | v;
		}
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			break;
		}
	}
	//if(mismatches > 0) printf("Time = %5d, Failure at: FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d Mismatches=%5d \n", InjTime, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit, mismatches);
	//else printf("Time = %5d, Masked at: FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d Mismatches=%5d \n", InjTime, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit, mismatches);
	return(mismatches > 0);
}




//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunCustomFlowWithoutCallbacks(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	int errframecnt=0;
	float N = JobDesc->PopulationSize;

	InjectionStatistics res = {.complete_reconfigurations=0, .failure_error_margin=50.0, .failure_rate=0.0, .failures=0, .injections=0, .masked=0, .masked_error_margin=50.0, .masked_rate=0.0, .population =  N };
	printf("Injector RunInSamplingMode: %s, BlockType = %d (%s), PopulationSize = %.0f, min_sample_size=%d, max_error_margin = %0.5f\n", JobDesc->Essential_bits>0?"Essential bits":"Blind", JobDesc->BlockType,   JobDesc->BlockType==0?"CLB":"BRAM", N, JobDesc->SampleSizeGoal, JobDesc->ErrorMarginGoal);

	if(JobDesc->StartIndex > 0){
		res.injections = (int) JobDesc->StartIndex;
		res.failures = (int) JobDesc->CurrentFailureCount;
		res.masked   = (int) JobDesc->CurrentMaskedCount;
	}


	ClockThrottle(0x1);
	int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));


	while( 		(JobDesc->SampleSizeGoal>0 && res.injections<JobDesc->SampleSizeGoal) 																	/* until given sample size */
			||  (JobDesc->ErrorMarginGoal>0 && (res.failure_error_margin>JobDesc->ErrorMarginGoal || res.masked_error_margin>JobDesc->ErrorMarginGoal)) /* until given error margin */
			|| 	(JobDesc->SampleSizeGoal==0 && JobDesc->ErrorMarginGoal==0 && res.injections < N) )														/* until sampling complete population */
	{

		int	failure = CustomInjectionFlow();

		res.injections++;
	    if(failure > 0) res.failures++;
	    else res.masked++;
	    if(res.injections % JobDesc->LogTimeout == 0 || res.injections >= N){
	    	res.failure_rate = 1.0*res.failures/res.injections;
	    	res.masked_rate = 1.0*res.masked/res.injections;
	    	if((N-res.injections) > 0){
		    	res.failure_error_margin = 2.576*sqrt( res.failure_rate*(1-res.failure_rate)*(N-res.injections)/(res.injections*(N-1)) );
		    	res.masked_error_margin =  2.576*sqrt( res.masked_rate*(1-res.masked_rate)*(N-res.injections)/(res.injections*(N-1)) );
	    	}
	    	else{
	    		res.failure_error_margin = 0.0;
	    		res.masked_error_margin = 0.0;
	    	}
	    	res.failure_rate *= 100.0; res.masked_rate  *= 100.0; res.failure_error_margin *= 100.0; res.masked_error_margin *= 100.0;
	    	printf("Tag_%9d | Injection[%9d] / [%.0f]  complete_reconfigurations= %5d | locked_targets= %5d | Masked: %6d, Rate= %.3f +/- %.3f | Failures: %6d, Rate = %.3f +/- %.3f\n", JobDesc->SyncTag,  res.injections,  N,  res.complete_reconfigurations, errframecnt, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin);
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
					printf("Complete bitstream reloaded\n");
			    }
			}
		}

	}


	return(res);
}
