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
InjectionStatistics RunUnifiedFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);
InjectionStatistics RunFaultList(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose);


//Redefine these functions (on the bottom if this file)
int RunDutTest(int StopAtFirstMismatch);	//Run Workload and check the failure mode
int InjectionFlowDutEnvelope();
void TriggerGSR();



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
	//JobDesc.UpdateBitstream = 1;

	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);

	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);


	Status = ReloadCompleteBitstream(InjDesc.DevcI, JobDesc.BitstreamAddr, (JobDesc.BitstreamSize >> 2));
	RunDutTest(1);
	SaveCheckpoint(&InjDesc);



	if(JobDesc.mode == 101){
		printf("Running Sampling Mode Without Callbacks\n\n");
		res = RunUnifiedFlow(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}
	else if(JobDesc.mode == 201){
		printf("Running Exhaustive Injection From Fault List\n\n");
		res = RunFaultList(&InjDesc, &JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc.SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}

    cleanup_platform();
    return 0;
}





//Fault injection flow (modify carefully if needed)
void RunInjectionFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int WorkloadDuration){
	//1. Run the workload until the fault injection time
	int InjTime;
	if(JobDesc->InjectionTime <= 0)  InjTime = rand()%(WorkloadDuration);		//by default inject at the workload start
	else InjTime = JobDesc->InjectionTime-1;									//Precise injection time

	if(InjTime > 0){
		RunClockCount((u16)InjTime);										//run workload until injection time
		WaitClockStops();
	}

	//2. Inject randomly distributed faults
	InjectionCoorditates InjPoint;
	FarFields Frame;
	for(int i=0;i<JobDesc->FaultMultiplicity;i++){
		InjPoint = NextRandomInjectionTarget(InjDesc, JobDesc);
		InjPoint.InjTime = InjTime;
		int err = FlipBits(InjDesc, InjPoint, 0, 1);
	}
	//3. Run the rest of workload cycles
	RunClockCount((u16)(WorkloadDuration-InjTime));							//run the rest of workload
	WaitClockStops();
}



//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunUnifiedFlow(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
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


		int	failure   = InjectionFlowDutEnvelope();
		int cp_mismatches = 0;
		if(JobDesc->DetectLatentErrors){
			cp_mismatches = CountCheckpointMismatches(InjDesc);
		}

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

	    if(JobDesc->DetailedLog){
	    	InjectionCoorditates InjPoint = InjDesc->LastTargets[InjDesc->LastTargetsCount-1];
	    	printf(">> Run[%5d]: %8d:%8d:%8d:%8d:%s\n", res.injections, InjPoint.FAR, InjPoint.word, InjPoint.bit, InjPoint.InjTime, failure==1?"SDC":(cp_mismatches>0?"LATENT":"MASKED"));
	    }

	    //Recover to fault-free state
	    recover_bitstream(InjDesc, JobDesc, failure, 0);

		//check that system has been recovered (slows down the experimentation when Tworkload ~ Trecovery)
		if(JobDesc->CheckRecovery > 0){
			if(res.injections % JobDesc->CheckRecovery == 0){
				//Execute Workload and check failure mode
			    failure = RunDutTest(1);
			    if(failure){
					//printf("Complete reconfiguration required after Injection[%5d] FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d\n", res.injections, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, InjPoint.word, InjPoint.bit);
			    	recover_bitstream(InjDesc, JobDesc, failure, 1);
					res.complete_reconfigurations++;
					if (Status != XST_SUCCESS) { xil_printf("ReloadCompleteBitstream ERROR \n\r");}
			    }
			}
		}

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
		int locked = FlipBits(InjDesc, InjPoint, 0, 1); if(locked>0) errframecnt++;


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

	}

	return(res);
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
		//printf("%d : %08x\n",i, TraceVectorInj[i]);
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
		//printf("%d : %08x\n",i, TraceVectorInj[i]);
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			break;
		}
	}
	return(mismatches > 0);
}


