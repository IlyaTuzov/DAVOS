/*
 *  SeuInjector.c
 *
 *  SEU emulation library for Zynq SoC and 7-Series
 *
 *  Created on: 2 Oct 2018
 *      Author: Ilya Tuzov
 *              Universidad Politecnica de Valencia
 *
 *  MIT license
 *  Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector
 */

#include "xparameters.h"	// SDK generated parameters
#include "xsdps.h"
#include "xil_printf.h"
#include "ff.h"
#include "xil_cache.h"
#include "xplatform_info.h"
#include <stdio.h>
#include <stdlib.h>
#include "xil_types.h"
#include "xil_io.h"
#include "xil_exception.h"
#include "xscugic.h"
#include "xparameters_ps.h"
#include "math.h"
#include "string.h"
#include "xtime_l.h"
#include "SeuInjector.h"








InjectionStatistics InjectorRun(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc,  int (*CustomInjectionFlow)()){
	InjectionStatistics res;
	int Status;

	//Mode 0 - handshake
	if(JobDesc->mode == 0){
		char readbuf[255]="";
	    init_platform();
	    printf("Input something:\n");
	    readconsole(&readbuf[0]);
	    printf("Received: %s\n", readbuf);
	    printf("Result: Success\n");
		return(res);
	}
	//Mode 1 - Cache cleanup
	else if(InjDesc->cache_enabled == 1 && JobDesc->mode == 1){
		printf("Files Before cleanup: \n"); listdir("");
		cleanup();
		printf("Files After cleanup: \n");  listdir("");
		printf("Result: Success\n");
		return(res);
	}

	else if(JobDesc->mode == 4){
		FarIncrTest(InjDesc, JobDesc, 0);
		printf("Tag_%9d | Profiling Result: %8d frames, at 0x%08x\n",JobDesc->SyncTag, InjDesc->FramesCount, InjDesc->FarItems );
		return(res);
	}

	char bitfilename [13]="";
	char maskfilename[13]="";
	sprintf(bitfilename, "%08d.bin", JobDesc->BitstreamId);
	sprintf(maskfilename, "%08d.msk", JobDesc->BitstreamId);
	UINT BytesCount;
	static FIL fil;		// File object
	FRESULT Res;

	if(InjDesc->cache_enabled){
		//Update cache: save bitstream and maskfile to SD card
		if(JobDesc->UpdateBitstream){
			printf("Saving bitstream %s to SD card...\n", bitfilename);
			Res= f_open(&fil, bitfilename, FA_CREATE_ALWAYS | FA_WRITE);
			Res= f_lseek(&fil, 0);
			Res= f_write(&fil, (const void*) JobDesc->BitstreamAddr , JobDesc->BitstreamSize, &BytesCount);
			Res = f_close(&fil);
			printf("\twritten %8x / %8x [bytes]: completed %s\n", BytesCount, JobDesc->BitstreamSize, BytesCount==JobDesc->BitstreamSize?"successfully":"with error");

			printf("Saving bitmask %s to SD card...\n", maskfilename);
			Res= f_open(&fil, maskfilename, FA_CREATE_ALWAYS | FA_WRITE);
			Res= f_lseek(&fil, 0);
			Res= f_write(&fil, (const void*) JobDesc->BitmaskAddr , JobDesc->BitmaskSize, &BytesCount);
			Res = f_close(&fil);
			printf("\twritten %8x / %8x [bytes]: completed %s\n", BytesCount, JobDesc->BitmaskSize, BytesCount==JobDesc->BitmaskSize?"successfully":"with error");
		}
		//Cache lookup: load bitstream and mask files from SD card
		else{
			printf("Reading bitstream %s from SD card...\n", bitfilename);
			Res = f_open(&fil, bitfilename, FA_READ);
			if(Res != FR_OK){ 		//if not found - forward an exception to host application through serial port
				printf("Error: %s  %s\n\n", bitfilename, (Res == FR_NO_FILE)||(Res == FR_NO_PATH) ? "not found in cache (SD)" : "Unknown Error");
				return(res);
			}
			Res = f_lseek(&fil, 0);
			Res = f_read(&fil, (void*)JobDesc->BitstreamAddr, JobDesc->BitstreamSize, &BytesCount);
			Res = f_close(&fil);
			printf("\tread %8x / %8x [bytes]: completed %s\n", BytesCount, JobDesc->BitstreamSize, BytesCount==JobDesc->BitstreamSize?"successfully":"with error");

			printf("Reading bitmask %s from SD card...\n", maskfilename);
			Res = f_open(&fil, maskfilename, FA_READ);
			if(Res != FR_OK){ //if not found - forward an exception to host application through serial port
				printf("Error: %s  %s\n\n", maskfilename, (Res == FR_NO_FILE)||(Res == FR_NO_PATH) ? "not found in cache (SD)" : "Unknown Error");
				return(res);
			}
			Res = f_lseek(&fil, 0);
			Res = f_read(&fil, (void*)JobDesc->BitmaskAddr, JobDesc->BitmaskSize, &BytesCount);
			Res = f_close(&fil);
			printf("\tread %8x / %8x [bytes]: completed %s\n", BytesCount, JobDesc->BitmaskSize, BytesCount==JobDesc->BitmaskSize?"successfully":"with error");
		}
	}

	//Load Frame Descriptors
	printf("Loading Frame Descriptors\n");
	InitInjectorFromDesignDescriptionFile(InjDesc, JobDesc, 0);

	//Program FPGA (Initial) with Complete Bitstream
	ClockThrottle(0x1);
	Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));

	//ResetPL(1000);


	//Check the golden run trace (fault-free run)
	int failure_mode = RunDutTest(0);
	SaveCheckpoint(InjDesc);



	if(failure_mode > 0) printf("ERROR: Golden Run mismatch\n");
	else printf("Golden Run Verify Trace Vector: success\n");
	int goldenrun_match = (failure_mode > 0) ? 0 : 1;

	if(JobDesc->FilterFrames){
		//InitInjectionDescriptors();
		printf("Filtering Frame Descriptors\n");
		FilterFrameDescriptors(InjDesc, InjDesc->ReferenceFrames, InjDesc->FrameDescriptorsCount, 0, 0);
		printf("Read Frame Descriptor File: ClbFramesCount = %d, RambFramesCount = %5d\n", InjDesc->ClbFramesCount, InjDesc->RambFramesCount);
	}



	if(JobDesc->mode == 101){
		printf("Running Sampling Mode\n\n");
		res = RunSampling(InjDesc, JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc->SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}
	else if(JobDesc->mode == 102){
		printf("Running Exhaustive Mode\n\n");
		res = RunExhaustive(InjDesc, JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc->SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}
	else if(JobDesc->mode == 201){
		printf("Running Exhaustive Injection From Fault List\n\n");
		res = RunFaultList(InjDesc, JobDesc, 1);
		printf("Tag_%9d | Injection Result: Injections = %9d of %.0f,  Masked: %6d, Masked Rate= %.3f +/- %.3f, Failures = %5d, Failure Rate = %.5f +/- %.5f, FuncVerification = %s\n\n", JobDesc->SyncTag, res.injections, res.population, res.masked, res.masked_rate, res.masked_error_margin, res.failures, res.failure_rate, res.failure_error_margin,  "Success" );
	}

	return(res);

}




//************* INJECTION PROCEDURES IN DIFFERENT OPMODES *********************


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
		if(JobDesc->mode==101){
			InjPoint = NextRandomInjectionTarget(InjDesc, JobDesc);
		}
		else{
			InjPoint = NextConsecutiveInjectionTarget(InjDesc, JobDesc, InjDesc->LastInjectionCoordinates);
			InjDesc->LastInjectionCoordinates = InjPoint;
		}
		InjPoint.InjTime = InjTime;
		int err = FlipBits(InjDesc, InjPoint, 0, 1);
	}
	//3. Run the rest of workload cycles
	RunClockCount((u16)(WorkloadDuration-InjTime));							//run the rest of workload
	WaitClockStops();
}



//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunSampling(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	int errframecnt=0;
	float N = (JobDesc->InjectionTime==0) ? JobDesc->PopulationSize * JobDesc->WorkloadDuration : JobDesc->PopulationSize;

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




//Run Custom injection Flow by this function (mode > 10)  if callbacks are not working properly on target platform
InjectionStatistics RunExhaustive(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	int errframecnt=0;
	float N = JobDesc->PopulationSize;
	InjectionCoorditates start = {.FAR= 0, .FrameIndex=0, .word=0, .bit=0 };
	InjDesc->LastInjectionCoordinates=start;

	InjectionStatistics res = {.complete_reconfigurations=0, .failure_error_margin=0.0, .failure_rate=0.0, .failures=0, .injections=0, .masked=0, .masked_error_margin=0.0, .masked_rate=0.0, .latent=0, .latent_rate=0.0, .latent_error_margin=0.0, .population =  JobDesc->PopulationSize };
	printf("Injector RunInExhaustiveMode: %s, BlockType = %d (%s), PopulationSize = %.0f\n", JobDesc->Essential_bits>0?"Essential bits":"Blind", JobDesc->BlockType,   JobDesc->BlockType==0?"CLB":"BRAM", N);

	if(JobDesc->StartIndex > 0){
		res.injections = (int) JobDesc->StartIndex;
		res.failures = (int) JobDesc->CurrentFailureCount;
		res.masked   = (int) JobDesc->CurrentMaskedCount;
        //skip all previosly tested targets (recover the state of random target generator)
        for(int i=0;i<JobDesc->StartIndex;i++) NextConsecutiveInjectionTarget(InjDesc, JobDesc, InjDesc->LastInjectionCoordinates);
	}


	ClockThrottle(0x1);
	int Status = ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));

	for(int run_id=0;run_id<N;run_id++){

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
	    	res.failure_rate = 100.0*res.failures/res.injections;
	    	res.masked_rate = 100.0*res.masked/res.injections;
	    	res.latent_rate = 100.0*res.latent/res.injections;
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





InjectionCoorditates NextRandomInjectionTarget(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc){
	InjectionCoorditates res;
	FarFields Frame;
	while(1){
		//Select random frame
		res.FrameIndex = InjDesc->MaskedFramesIndexes[rand()%InjDesc->MaskedFramesCount];
		//skip pad frames
		if(get_bit(InjDesc->ReferenceFrames[res.FrameIndex].Flags, 1) == 1) continue;
		res.FAR = InjDesc->ReferenceFrames[res.FrameIndex].FAR;
		Frame = parseFAR(res.FAR);

		//proceed only when logic type matches
		if(JobDesc->BlockType < 2 && Frame.BLOCK != JobDesc->BlockType) continue;	//filer FAR items when CLB or BRAM selected (0 or 1), otherwise  (BlockType>=2) - proceed with any
		//Select random word and random bit
		res.word = rand()%FRAME_SIZE;
		if(Frame.BLOCK == 0 && res.word==50) continue;	//Word 50 in CLB is not accessible for injection
		res.bit = rand()%32;
		//skip non-essential bits (mask == 0)
		if(JobDesc->Essential_bits > 0){
			if(get_bit(InjDesc->ReferenceFrames[res.FrameIndex].Mask[res.word], res.bit) == 0) continue;
		}
		//skip tested bits
		if(JobDesc->SamplingWithoutRepetition){
			if(get_bit(InjDesc->ReferenceFrames[res.FrameIndex].Tested[res.word], res.bit) == 1) continue;
			else set_bit(InjDesc->ReferenceFrames[res.FrameIndex].Tested[res.word], res.bit, 1);
		}
		break;
	}
	//printf("RandomTarget [%d]: (%5d, %5d, %5d, %5d, %5d) (%5d, %5d)\n", res.FrameIndex, Frame.BLOCK, Frame.TOP, Frame.HCLKROW, Frame.MAJOR, Frame.MINOR, res.word, res.bit);
	res.CellType = JobDesc->CellType;
	return(res);
}



InjectionCoorditates NextConsecutiveInjectionTarget(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, InjectionCoorditates prev){
	InjectionCoorditates res = {.FrameIndex=prev.FrameIndex, .FAR=prev.FAR, .word=prev.word, .bit=prev.bit, .CellType=JobDesc->CellType, .InjTime=0};
	FarFields Frame;


	if(res.FrameIndex<InjDesc->MaskedFramesIndexes[0]) res.FrameIndex = InjDesc->MaskedFramesIndexes[0];
	//printf("Start: %d,%d,%d,%d\n", res.FrameIndex, res.FAR, res.word, res. bit);

	while( res.FrameIndex <= InjDesc->MaskedFramesIndexes[InjDesc->MaskedFramesCount-1] ){
		res.bit++;
		if(res.bit>=32){ res.bit=0; res.word++;};
		if(res.word>=101){
			res.word=0;
			int found = 0;
			for(int i=0;i<InjDesc->MaskedFramesCount;i++){
				if(InjDesc->MaskedFramesIndexes[i] > res.FrameIndex){
					res.FrameIndex = InjDesc->MaskedFramesIndexes[i];
					found = 1;
					break;
				}
			}
			if(found==0){
			printf("returning prev\n");
			input_int();
			return(prev);
			}
		};
		res.FAR = InjDesc->ReferenceFrames[res.FrameIndex].FAR;
		Frame = parseFAR(res.FAR);

		//proceed only when logic type matches
		if(JobDesc->BlockType < 2 && Frame.BLOCK != JobDesc->BlockType) continue;	//filer FAR items when CLB or BRAM selected (0 or 1), otherwise  (BlockType>=2) - proceed with any
		if(Frame.BLOCK == 0 && res.word==50) continue;	//Word 50 in CLB is not accessible for injection
		if(JobDesc->Essential_bits > 0){
			if(get_bit(InjDesc->ReferenceFrames[res.FrameIndex].Mask[res.word], res.bit) == 0) continue;
		}

		return(res);




}
	printf("Reached Last Target\n");
	return(prev);

}



InjectionCoorditates GetTargetFromInjectionList(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int index, FaultListItem * item){
	InjectionCoorditates res;
	FaultListItem *adr = JobDesc->FaultListAdr + index*sizeof(FaultListItem);

	*(item)  = *(adr);
	res.FAR  = item->FAR;
	res.word = item->word;
	res.bit  = item->bit;

	for(int i=0;i<InjDesc->FrameDescriptorsCount;i++){
		if(InjDesc->ReferenceFrames[i].FAR == res.FAR){
			res.FrameIndex = i;
			break;
		}
	}
	return(res);
}



//*******************INJECTOR SETUP FUNCTIONS***********************

//return code: 0 - success, 1 - error
int InjectorInitialize(InjectorDescriptor * InjDesc, u16 DeviceId, int (*WorkloadRunFunc)(), void (*TriggerGSRFunc)()){
	int Status;
	//Device Configuration Module
	InjDesc->ConfigPtr = XDcfg_LookupConfig(DeviceId);
	Status = XDcfg_CfgInitialize(&(InjDesc->DevConigInterface), InjDesc->ConfigPtr, InjDesc->ConfigPtr->BaseAddr);
	if (Status != XST_SUCCESS) { return 1; }
	//XDcfg_SetLockRegister(&(InjDesc->DevConigInterface), XDCFG_UNLOCK_DATA);
	InjDesc->DevcI = &(InjDesc->DevConigInterface);
	Status = XDcfg_SelfTest(InjDesc->DevcI);
	if (Status != XST_SUCCESS) { return 1; }
	memset(InjDesc->FarItems, 0, sizeof(InjDesc->FarItems));

	int MaskableBramWords[] = {4, 14, 24, 34, 44, 55, 65, 75, 85, 95};
	InjDesc->BramMaskedCount = sizeof(MaskableBramWords)/sizeof(MaskableBramWords[0]);
	memcpy(InjDesc->BramMaskedIndexes, MaskableBramWords, sizeof(MaskableBramWords));
	memset(InjDesc->EssentialBitsPerBlockType, 0, sizeof(InjDesc->EssentialBitsPerBlockType));

	//DUT-specific parameters
	InjDesc->WorkloadRunFunc = WorkloadRunFunc;
	InjDesc->TriggerGSRFunc = TriggerGSRFunc;

  return(0);
}







void ReadJobDesc(JobDescriptor* JobDesc, const u32* Adr, int verbose){
	u32* ptr_u32 = Adr;
	u32 syncword =  *(ptr_u32); ptr_u32++;
	if(syncword == 0xAABBCCDD){
		JobDescriptor * buf = ptr_u32;
		*(JobDesc) = *(buf);
		printf("Init Finished\n");
	}
	else{
		printf("ERROR in function: ReadJobDesc  Sync word not present\n");
	}
}



void InitInjectorFromDesignDescriptionFile(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int verbose){
	u32* ptr_u32 = JobDesc->BitmaskAddr;
	u32 FrameDescOffset  = 				*(ptr_u32); ptr_u32++;
	InjDesc->FrameDescriptorsCount = 	*(ptr_u32); ptr_u32++;
	u32 RecoveryFramesOffset = 			*(ptr_u32); ptr_u32++;
	InjDesc->RecoveryFarCount = 		*(ptr_u32); ptr_u32++;
	u32 checkpointFramesOffset =		*(ptr_u32); ptr_u32++;
	InjDesc->RegisterFramesNum = 		*(ptr_u32); ptr_u32++;
	
	//ReferenceFrames = 		 (FrameDescriptor*) malloc(FrameDescriptorsCount*sizeof(FrameDescriptor));
	//RecoveryDescriptorList = (u32*) malloc(RecoveryFarCount*sizeof(u32));
	//FrameDescriptor* ptr_frame_desc = JobDesc.BitmaskAddr + FrameDescOffset;

	ptr_u32 = JobDesc->BitmaskAddr + FrameDescOffset;
	InjDesc->ClbFramesCount = 0; InjDesc->RambFramesCount = 0;
	for(int i=0; i<InjDesc->FrameDescriptorsCount; i++ ){
		InjDesc->ReferenceFrames[i].FAR  = *(ptr_u32); ptr_u32++;
		InjDesc->ReferenceFrames[i].Flags = *(ptr_u32); ptr_u32++;
		InjDesc->ReferenceFrames[i].EssentialBitsCount = *(ptr_u32); ptr_u32++;
		for(int k=0;k<FRAME_SIZE;k++){
			InjDesc->ReferenceFrames[i].Data[k] = *(ptr_u32); ptr_u32++;
			InjDesc->ReferenceFrames[i].Mask[k] = *(ptr_u32); ptr_u32++;
			InjDesc->ReferenceFrames[i].Tested[k] = 0;
		}
		FarFields FC = parseFAR(InjDesc->ReferenceFrames[i].FAR);
		if(FC.BLOCK == 0){ 		InjDesc->ClbFramesCount++;  InjDesc->EssentialBitsPerBlockType[0] += InjDesc->ReferenceFrames[i].EssentialBitsCount;  }
		else if(FC.BLOCK == 1){ InjDesc->RambFramesCount++; InjDesc->EssentialBitsPerBlockType[1] += InjDesc->ReferenceFrames[i].EssentialBitsCount;  }
	}

	ptr_u32 = JobDesc->BitmaskAddr + RecoveryFramesOffset;
	for(int i=0;i<InjDesc->RecoveryFarCount;i++, ptr_u32++){
		u32 FAR = *(ptr_u32);
		for(int k=0;k<InjDesc->FrameDescriptorsCount;k++){
			if(FAR == InjDesc->ReferenceFrames[k].FAR){
				InjDesc->RecoveryDescriptorList[i] = InjDesc->ReferenceFrames[k];
				break;
			}
		}
	}

	ptr_u32 = JobDesc->BitmaskAddr + checkpointFramesOffset;
	for(int i=0;i<InjDesc->RegisterFramesNum;i++, ptr_u32++){
		InjDesc->RegisterFramesCaptured[i].FAR = *(ptr_u32);
	}

	InjDesc->MaskedFramesCount=0;
	for(int i=0; i<InjDesc->FrameDescriptorsCount; i++ ){
		if(InjDesc->ReferenceFrames[i].EssentialBitsCount > 0){
			InjDesc->MaskedFramesIndexes[InjDesc->MaskedFramesCount++] = i;
		}
	}
	for(int i=0;i<InjDesc->MaskedFramesCount;i++){
		printf("MaskedFrameIndex[%5d]=%5d\n", i, InjDesc->MaskedFramesIndexes[i]);
	}
	//for(int i=0;i<InjDesc->RegisterFramesNum;i++) printf("Checkpoint FAR [%3d] = %08x\n", i, InjDesc->RegisterFramesCaptured[i].FAR);
}


//Check which frames are injectable, set flag[1] - is pad frame
//if BuildMask==1 - setup mask array of each frame descriptor by checking whether each word is injectable or not
void FilterFrameDescriptors(InjectorDescriptor* InjDesc, FrameDescriptor* FrameDesc, int DescCount, int BuildMask, int log_verbosity){
	FarFields FC;
	//pad frame
	for(int i=0;i<DescCount;i++){

		 //1. If it's explicitly excluded
		if(IsExcluded(FrameDesc[i].FAR)){
			FrameDesc[i].Flags = set_bit(FrameDesc[i].Flags, 1, 1);
			continue;
		}
		//2. Or if none of it's words can be modified

		FC = parseFAR(FrameDesc[i].FAR);
		BitArray buf = GetInjectableWords(InjDesc, FC);
		FrameDesc[i].Flags = set_bit(FrameDesc[i].Flags, 1, (CountOnes(buf) == 0) ? 1 : 0 );
		if(BuildMask > 0){
			for(int k=0;k<FRAME_SIZE;k++)
				FrameDesc[i].Mask[k] = (BitArray_GetBit(buf, k) > 0) ? 0xFFFFFFFF : 0x00000000;
		}

	}
}



BitArray GetInjectableWords(InjectorDescriptor* InjDesc, FarFields FC){
	BitArray res = BitArrayNew(FRAME_SIZE);
	int Status;
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
	for(int k=0;k<FRAME_SIZE;k++){ InjDesc->WriteFrameData[k] = ~InjDesc->ReadFrameData[k]; };
	MaskFrameData(InjDesc, FC, &(InjDesc->WriteFrameData[0]));
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), 0);
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR,  (u32 *) &(InjDesc->ReadFrameData[0] ), 0);
	for(u32 word=0;word<FRAME_SIZE;word++){
		if(InjDesc->WriteFrameData[word] == InjDesc->ReadFrameData[word]){
			BitArray_SetBit(&res, word, IsMaskableWordIndex(InjDesc, FC, word) == 0);
		}
		else{
			BitArray_SetBit(&res, word, 0);
		}
	}
	for(int k=0;k<FRAME_SIZE;k++){ InjDesc->WriteFrameData[k] = ~InjDesc->WriteFrameData[k]; };
	MaskFrameData(InjDesc, FC, &(InjDesc->WriteFrameData[0]));
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), 0);
	return(res);
}




u32 CheckFrameWordIsInjectable(InjectorDescriptor* InjDesc, FarFields FC, u32 word){
	int Status;
	int match=1;
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
	for(int k=0;k<FRAME_SIZE;k++){ InjDesc->WriteFrameData[k] = InjDesc->ReadFrameData[k]; };
	InjDesc->WriteFrameData[word] = ~(InjDesc->ReadFrameData[word]);
	MaskFrameData(InjDesc, FC, &(InjDesc->WriteFrameData[0]));
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), 0);
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
	for(int k=0;k<FRAME_SIZE;k++){
		if(InjDesc->WriteFrameData[k] != InjDesc->ReadFrameData[k]){
			match = 0;
			break;
		}
	}
	InjDesc->WriteFrameData[word] = ~(InjDesc->WriteFrameData[word]);
	MaskFrameData(InjDesc, FC, &(InjDesc->WriteFrameData[0]));
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), 0);
	if(match) return(1);
	return(0);
}







int ProfileFarMap(InjectorDescriptor* InjDesc, u32* FarDesc, u32 BlockType, u32 Top){
	int Status;
	u32 FAR, FAR_PREV;
	u32 FAR_BLOCK = 0;
	u32 FAR_TOP = 0;
	u32 FAR_HCLKROW = 0;
	u32 FAR_MAJOR = 0;
	u32 FAR_MINOR = 0;
	InjDesc->FramesCount = 0;
	for(u32 e=0; e<2; e++){
		printf("\n\nE=%d\n\n", e);
		FAR = FarSetup(BlockType, Top, 0, 0, e);
		FAR_PREV = FAR;
		//iterate over frames
		for(int i=0; i< 20000; i++){
			FAR_BLOCK 	= (FAR >> 23) & 0x00000007;
			FAR_TOP 	= (FAR >> 22) & 0x00000001;
			FAR_HCLKROW	= (FAR >> 17) & 0x0000001F;
			FAR_MAJOR 	= (FAR >> 7)  & 0x000003FF;
			FAR_MINOR 	= (FAR  	  & 0x0000007F) | e;
			if(FAR_BLOCK != BlockType)break;

			Status = readFrame(InjDesc, FAR_TOP, FAR_BLOCK, FAR_HCLKROW, FAR_MAJOR, FAR_MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
				if (Status != XST_SUCCESS) {
					printf("readFrame failure: %d \r\n", Status);
					return XST_FAILURE;
				}
			if(FAR_BLOCK == BlockType && FAR_TOP == Top){
				//printf("\nAppending[%4d]: FAR=%08x || BLOCK=%2d, TOP=%2d, ROW=%2d, MAJOR=%2d, MINOR=%2d", (*TotalItems), FAR, FAR_BLOCK, FAR_TOP, FAR_HCLKROW, FAR_MAJOR, FAR_MINOR);
				InjDesc->FarItems[InjDesc->FramesCount] = FAR;
				InjDesc->FramesCount++;
			}
			FAR_PREV = FAR;
			if (XDcfg_GetConfigReg(InjDesc, XHI_FAR, &FAR) != XST_SUCCESS) {
				printf("\nFAR read failure");
				return XST_FAILURE;
				}
			if(FAR==FAR_PREV)break;
		}
	}
	return  XST_SUCCESS;
}


//***********************CACHE MANAGEMENT FUNCTIONS**********************************

//retrieve file list from mounted storage
int GetFileList(FILINFO FileDesc[]){
	DIR dir;
	FRESULT Res = f_opendir(&dir, "");
	int FileDescCounter = 0;
	while(1){
		Res = f_readdir(&dir, &FileDesc[FileDescCounter]);
		if(FileDesc[FileDescCounter].fname[0] != '\0'){
			FileDescCounter++;
		}
		else {break; }
	};
	return(FileDescCounter);
}


//remove all BIN and MSK files from mounted storage
int cleanup(){
	DIR dir;
	FILINFO FileDesc;
	FRESULT Res = f_opendir(&dir, "");
	int FileDescCounter=0, RemovedFiles = 0;
	while(1){
		Res = f_readdir(&dir, &FileDesc);
		if(FileDesc.fname[0] != '\0'){
			FileDescCounter++;
			printf("\t%5d | File: %16s | size = %x\n", FileDescCounter, FileDesc.fname, FileDesc.fsize);
			if(strstr(FileDesc.fname, ".BIN") != NULL || strstr(FileDesc.fname, ".MSK") != NULL){
				printf("\t\t\tRemoving file: %s\n", FileDesc.fname);
				f_unlink(FileDesc.fname);
				RemovedFiles++;
			}
		}
		else {break; }
	};
	printf("CLEANUP FINISHED: %i files removed\n", RemovedFiles);
	return(RemovedFiles);
}


//list all files on the mounted storage (to stdout)
void listdir(const TCHAR* path){
	DIR dir;
	FILINFO FileDesc;
	FRESULT Res = f_opendir(&dir, path);
	int FileDescCounter=0;
	while(1){
		Res = f_readdir(&dir, &FileDesc);
		if(FileDesc.fname[0] != '\0'){
			FileDescCounter++;
			printf("\t%5d | File: %16s | size = %x\n", FileDescCounter, FileDesc.fname, FileDesc.fsize);
		}
		else {break; }
	};
}



















//*********BITSTREAM MANAGEMENT FUCNTIONS*****************************








//When mask == 0 : flips target.bit of target.word in Frame target.FAR
//When mask != 0 : applies bitwise XOR to target.word in Frame target.FAR
//returns: 0 - success, 1 - memory modification not applied (error)
int FlipBits(InjectorDescriptor* InjDesc, InjectionCoorditates target, u32 mask, int verbose){
	int Status;
	FarFields FC = parseFAR(target.FAR);
	//Readback-capture and write back Frames with FFs
	int capture_restore = target.CellType==2 ? 0 : 1;

	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), capture_restore);
	memcpy(&(InjDesc->WriteFrameData[0]), &(InjDesc->ReadFrameData[0]), FRAME_SIZE*sizeof(u32));
	//Flip the masked bit(s)
	if(mask != 0){
		InjDesc->WriteFrameData[target.word] = (InjDesc->WriteFrameData[target.word]) ^ mask;
	}
	else{
		InjDesc->WriteFrameData[target.word] = (InjDesc->WriteFrameData[target.word]) ^ (1 << target.bit);
	}
	//Write back
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), capture_restore);
	if(capture_restore){ TriggerGSR(); };


	saveInjectionTarget(InjDesc, target);


	//read again to check that faulty value has been written
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
	int match = 1;
	for(u32 k=0;k<FRAME_SIZE;k++){
		if(InjDesc->WriteFrameData[k] != InjDesc->ReadFrameData[k]){
			match = 0;
			break;
		}
	}
	if(match == 0){
		if(verbose>0) printf("BitFlip Error: Locked target at FAR=(%5d, %5d, %5d, %5d, %5d), Word = %3d, Bit = %2d\n", FC.BLOCK, FC.TOP, FC.HCLKROW, FC.MAJOR, FC.MINOR, target.word, target.bit);
		return(1);
	}

	return(0);
}




void saveInjectionTarget(InjectorDescriptor* InjDesc, InjectionCoorditates target){
	for(int i=0;i<InjDesc->LastTargetsCount;i++){
		//check if target already saved
		if(InjDesc->LastTargets[i].FAR == target.FAR && InjDesc->LastTargets[i].word == target.word && InjDesc->LastTargets[i].bit == target.bit) return;
	}
	InjDesc->LastTargets[InjDesc->LastTargetsCount] = target;
	if(InjDesc->LastTargetsCount < sizeof(InjDesc->LastTargets)/sizeof(InjectionCoorditates)) InjDesc->LastTargetsCount++;
}


int recover_bitstream(InjectorDescriptor* InjDesc, JobDescriptor* JobDesc, int RecoverFrameList, int CompleteReconfig){
    int stuck;
    if(CompleteReconfig==0){
		for(int i=0;i<InjDesc->LastTargetsCount;i++){
			int FrameIndex = InjDesc->LastTargets[i].FrameIndex;
			FrameDescriptor* desc = &InjDesc->ReferenceFrames[FrameIndex];
			stuck = WriteVerifyFrame(InjDesc, desc->FAR, &(desc->Data[0]));
			if(stuck) {
				break;
			}
			FarFields FC = parseFAR(desc->FAR);
			//recover ALL CLB minor frames in this Major Frame: 30 to 35
			if(FC.BLOCK==0 && FC.MINOR >= 30 ){
				int startIndex = FrameIndex - (FC.MINOR - 30);
				writeFrames(InjDesc, startIndex, 6, &(InjDesc->ReferenceFrames[0]));
			}
		};
		InjDesc->LastTargetsCount=0;
		if(RecoverFrameList) writeFrames(InjDesc, 0, InjDesc->RecoveryFarCount, &(InjDesc->RecoveryDescriptorList[0]));
    }
	else{
		printf("recover_bitstream: complete reconfig\n");
		ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
		InjDesc->LastTargetsCount=0;
	}
    return(stuck);
}


int ReloadCompleteBitstream(XDcfg *Instance, u32 StartAddress, u32 WordLength)
{
	int Status;
	volatile u32 IntrStsReg = 0;
	// Clear DMA and PCAP Done Interrupts
	XDcfg_IntrClear(Instance, (XDCFG_IXR_DMA_DONE_MASK | XDCFG_IXR_D_P_DONE_MASK));
	// Transfer bitstream from DDR into fabric in non secure mode
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	Status = XDcfg_Transfer(Instance, (u32 *) StartAddress, WordLength, (u32 *) XDCFG_DMA_INVALID_ADDRESS, 0, XDCFG_NON_SECURE_PCAP_WRITE);
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	if (Status != XST_SUCCESS) return Status;
	// Poll DMA Done Interrupt
	while ((IntrStsReg & XDCFG_IXR_DMA_DONE_MASK) != XDCFG_IXR_DMA_DONE_MASK) IntrStsReg = XDcfg_IntrGetStatus(Instance);
	// Poll PCAP Done Interrupt
	while ((IntrStsReg & XDCFG_IXR_D_P_DONE_MASK) != XDCFG_IXR_D_P_DONE_MASK) IntrStsReg = XDcfg_IntrGetStatus(Instance);
	return XST_SUCCESS;
}


int XDcfg_GetConfigReg(InjectorDescriptor* InjDesc, u32 ConfigReg, u32 *RegData){
	u32 IntrStsReg;
	u32 StatusReg;
	unsigned int CmdIndex;
	unsigned int CmdBuf[18];

	// Clear the interrupt status bits
	XDcfg_IntrClear(InjDesc->DevcI, (XDCFG_IXR_PCFG_DONE_MASK | XDCFG_IXR_D_P_DONE_MASK | XDCFG_IXR_DMA_DONE_MASK));
	// Check if DMA command queue is full
	StatusReg = XDcfg_ReadReg(InjDesc->DevcI->Config.BaseAddr, XDCFG_STATUS_OFFSET);
	if ((StatusReg & XDCFG_STATUS_DMA_CMD_Q_F_MASK) == XDCFG_STATUS_DMA_CMD_Q_F_MASK) {
		printf("Read Config Reg failure: DMA full");
		return XST_FAILURE;
	}
	// Register Readback in non secure mode. Create the data to be written to read back the Configuration Registers from PL Region
	CmdIndex = 0;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_BUS_WTH_PACKET; 	/* Bus Width Sync Word */
	CmdBuf[CmdIndex++] = XHI_BUS_DET_PACKET; 	/* Bus Width Detect */
	CmdBuf[CmdIndex++] = XHI_DUMMY_PACKET;
	CmdBuf[CmdIndex++] = XHI_SYNC_PACKET; 	/* Sync Word */
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	CmdBuf[CmdIndex++] = Type1_Packet(1, ConfigReg, 0x1);
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	XDcfg_Transfer(InjDesc->DevcI, (&CmdBuf[0]), CmdIndex, RegData, 1, XDCFG_PCAP_READBACK);
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	// Poll IXR_DMA_DONE
	IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	while ((IntrStsReg & XDCFG_IXR_DMA_DONE_MASK) != XDCFG_IXR_DMA_DONE_MASK) {
		IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	}
	// Poll IXR_D_P_DONE
	while ((IntrStsReg & XDCFG_IXR_D_P_DONE_MASK) != XDCFG_IXR_D_P_DONE_MASK) {
		IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	}

	CmdIndex = 0;
	CmdBuf[CmdIndex++] = Type1_Packet(2, XHI_CMD, 0x1);	// P1 write CMD REG
	CmdBuf[CmdIndex++] = XHI_CMD_DESYNCH;				// Desync
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;
	CmdBuf[CmdIndex++] = XHI_NOOP_PACKET;

	XDcfg_InitiateDma(InjDesc->DevcI, (u32)(&CmdBuf[0]), XDCFG_DMA_INVALID_ADDRESS, CmdIndex, 0);
	/* Poll IXR_DMA_DONE */
	IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	while ((IntrStsReg & XDCFG_IXR_DMA_DONE_MASK) != XDCFG_IXR_DMA_DONE_MASK) IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	/* Poll IXR_D_P_DONE */
	while ((IntrStsReg & XDCFG_IXR_D_P_DONE_MASK) != XDCFG_IXR_D_P_DONE_MASK) IntrStsReg = XDcfg_IntrGetStatus(InjDesc->DevcI);
	return XST_SUCCESS;
}





int WriteVerifyFrame(InjectorDescriptor* InjDesc, u32 FAR, u32* WriteData){
	int Status;
	FarFields FC = parseFAR(FAR);
	Status = writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(WriteData[0]), 0);
	Status = readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
	int match = 1;
	for(u32 k=0;k<FRAME_SIZE;k++){
		if(WriteData[k] != InjDesc->ReadFrameData[k]){
			match = 0;
			break;
		}
	}
	if(match == 0){
		//printf("WriteVerifyFrame Error: \n");
		//for(u32 k=0;k<FRAME_SIZE;k++) printf("Written[%3d] = %08x | Read[%3d] = %08x\n", k, WriteData[k], k, ReadFrameData[k]);
		return(1);
	}
	return(0);
}



double GetDurationUseconds(XTime StartTime){
	XTime CurrentTime;
	double tickusec = COUNTS_PER_MICROSECOND;
	XTime_GetTime(&CurrentTime);
	double res = (CurrentTime - StartTime) / tickusec;
	return( res );
}


int waitPcapDone(InjectorDescriptor* InjDesc, int waitQueueEmpty,  u32 TimeoutUseconds){
	XTime StartTime;
	int Status = XDcfg_IntrGetStatus(InjDesc->DevcI);

	/* Poll IXR_DMA_DONE */
	XTime_GetTime(&StartTime);
	while ((Status & XDCFG_IXR_DMA_DONE_MASK) != XDCFG_IXR_DMA_DONE_MASK){
		Status = XDcfg_IntrGetStatus(InjDesc->DevcI);
		if(GetDurationUseconds(StartTime) > TimeoutUseconds)return(1);
	}
	/* Poll IXR_D_P_DONE */
	XTime_GetTime(&StartTime);
	while ((Status & XDCFG_IXR_D_P_DONE_MASK) != XDCFG_IXR_D_P_DONE_MASK){
		Status = XDcfg_IntrGetStatus(InjDesc->DevcI);
		if(GetDurationUseconds(StartTime) > TimeoutUseconds) return(1);
	}

	if(waitQueueEmpty){
		XTime_GetTime(&StartTime);
		/* Wait till DMA command queue is empty*/
		Status = XDcfg_ReadReg(InjDesc->DevConigInterface.Config.BaseAddr, XDCFG_STATUS_OFFSET);
		while((Status & XDCFG_STATUS_DMA_CMD_Q_E_MASK) != XDCFG_STATUS_DMA_CMD_Q_E_MASK){
			Status = XDcfg_ReadReg(InjDesc->DevConigInterface.Config.BaseAddr, XDCFG_STATUS_OFFSET);
			if(GetDurationUseconds(StartTime) > TimeoutUseconds) return(1);
		}
	}

	return(0);
}


int readFrame(InjectorDescriptor* InjDesc, long Top,  long Block, long HClkRow, long MajorFrame, long MinorFrame, u32 *FrameData, int Capture){
	for(int attempts = 0; attempts < 5; attempts++){
		u32 Status;
		u32 Index = 0;
		u32 FAR = FarSetup(Block, Top, HClkRow,  MajorFrame, MinorFrame);
		// DUMMY and SYNC
		InjDesc->WriteBuffer[Index++] = XHI_DUMMY_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_DUMMY_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_SYNC_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		//InjDesc->WriteBuffer[Index++] = XHI_SHUTDOWN_PACKET;
		//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Reset CRC
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;

			// ID register
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_IDCODE, 0x1);
		InjDesc->WriteBuffer[Index++] = 0x03727093; //InjDesc->DevcI->Config.DeviceId & 0x0FFFFFFF;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = 0x00000000;

		//GLUTMASK_B
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
		InjDesc->WriteBuffer[Index++] = 0x00000500;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
		InjDesc->WriteBuffer[Index++] = 0x00000500;


		// GCAPTURE
		if(Capture>0){
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_GCAPTURE;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;

		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_RCAP;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		}


		// Setup CMD register to read configuration
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_RCFG;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup FAR register
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FAR, 0x1);
		InjDesc->WriteBuffer[Index++] = FAR;
		// Create Type one packet
		InjDesc->WriteBuffer[Index++] = Type1_Packet(1, XHI_FDRO, 0);
		InjDesc->WriteBuffer[Index++] = Type2_Packet(1, FRAME_SIZE << 1 );
		for(int i = 0; i < 32; i++) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		while(Index % 16 != 0) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		//for(int i=0;i<Index;i++)printf("Cmd[%2d] = %08x\n", i, InjDesc->WriteBuffer[i]);
		//Enable the pcap clock
		Status = Xil_In32(SLCR_PCAP_CLK_CTRL);
		if (!(Status & SLCR_PCAP_CLK_CTRL_EN_MASK)) {
			Xil_Out32(SLCR_UNLOCK, SLCR_UNLOCK_VAL);
			Xil_Out32(SLCR_PCAP_CLK_CTRL, (Status | SLCR_PCAP_CLK_CTRL_EN_MASK));
			Xil_Out32(SLCR_UNLOCK, SLCR_LOCK_VAL);
		}
		// Select PCAP interface for partial reconfiguration
		XDcfg_EnablePCAP(InjDesc->DevcI);

		XDcfg_SetControlRegister(InjDesc->DevcI, XDCFG_CTRL_PCAP_MODE_MASK);
		// Clear the interrupt status bits
		XDcfg_IntrClear(InjDesc->DevcI, (XDCFG_IXR_PCFG_DONE_MASK | XDCFG_IXR_D_P_DONE_MASK | XDCFG_IXR_DMA_DONE_MASK) );
		// Check if DMA command queue is full
		Status = XDcfg_ReadReg(InjDesc->DevConigInterface.Config.BaseAddr, XDCFG_STATUS_OFFSET);
		if ((Status & XDCFG_STATUS_DMA_CMD_Q_F_MASK) == XDCFG_STATUS_DMA_CMD_Q_F_MASK) return XST_FAILURE;
		//Write the data to the FIFO and initiate the transfer of data present in the FIFO to the ICAP device

		Xil_DCacheFlush();
		Xil_DCacheInvalidate();
		Status = XDcfg_Transfer(InjDesc->DevcI,
				(u32 *)InjDesc->WriteBuffer, Index,
				InjDesc->FrameBuffer, FRAME_SIZE << 1,
				XDCFG_PCAP_READBACK);
		if (Status != XST_SUCCESS) printf("Read Frame: XDcfg_Transfer failed \r\n");
		//printf("ReadFrame: XDcfg_Transfer finished\n");
		Xil_DCacheFlush();
		Xil_DCacheInvalidate();

		//XTime StartTime;
		//XTime_GetTime(&StartTime);
		//while(GetDurationUseconds(StartTime) < 10000);

		if(waitPcapDone(InjDesc, 1, 10000) > 0){
			printf("ReadFrame: timeout retry\n");
			continue; //Timeout - retry
		}


/*
		Status = XDcfg_ReadReg(InjDesc->DevConigInterface.Config.BaseAddr, XDCFG_STATUS_OFFSET);
		if ((Status & XDCFG_STATUS_DMA_CMD_Q_F_MASK) == XDCFG_STATUS_DMA_CMD_Q_F_MASK) return XST_FAILURE;
	*/

		Index = 0;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
		InjDesc->WriteBuffer[Index++] = 0X00000100;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
		InjDesc->WriteBuffer[Index++] = 0X00000000;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);	// P1 write CMD REG
		InjDesc->WriteBuffer[Index++] = XHI_CMD_DESYNCH;					// Desync
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		while(Index % 16 != 0) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		XDcfg_InitiateDma(InjDesc->DevcI, (u32)(&InjDesc->WriteBuffer[0]), XDCFG_DMA_INVALID_ADDRESS, Index, 0);


		if(waitPcapDone(InjDesc, 1, 10000) > 0){
			printf("ReadFrame: timeout retry\n");
			continue; //Timeout - retry
		}

		memcpy(&FrameData[0], &(InjDesc->FrameBuffer[FRAME_SIZE]), FRAME_SIZE*sizeof(u32));
			//mask BRAM Frame
		MaskFrameData(InjDesc, parseFAR(FAR), &FrameData[0]);
		//for(int i=0;i<FRAME_SIZE;i++) FrameData[i] = FrameBuffer[i+FRAME_SIZE];
		return XST_SUCCESS;
	}

	return(1); //PCAP hang

}



int writeFrame(InjectorDescriptor* InjDesc, long Top,  long Block, long HClkRow, long MajorFrame, long MinorFrame, u32 *FrameData, int restore){
	int Status;
	u32 Index = 0;
	u32 FAR = FarSetup(Block, Top, HClkRow,  MajorFrame, MinorFrame);
		// DUMMY and SYNC
	InjDesc->WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_SYNC_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Reset CRC
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// ID register
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_IDCODE, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x03727093; //InjDesc->DevcI->Config.DeviceId & 0x0FFFFFFF;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000000;
		//GLUTMASK_B
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000400;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000400;
		//configuration option register 0
	//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_COR, 0x1);
	//InjDesc->WriteBuffer[Index++] = 0x02003FE5;
		//shutdown
	//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	//InjDesc->WriteBuffer[Index++] = XHI_SHUTDOWN_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		//GHIGH_B Q1
	//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	//InjDesc->WriteBuffer[Index++] = 0x00000008;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup CMD register - write configuration
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_WCFG;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup FAR
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FAR, 0x1);
	InjDesc->WriteBuffer[Index++] = FAR;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup Packet header.
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FDRI, FRAME_SIZE*2);
		//Append the data frame
	for(int i=0;i<FRAME_SIZE;i++) InjDesc->WriteBuffer[Index++] = FrameData[i];
		//Append the pad frame
	for(int i=0;i<FRAME_SIZE;i++) InjDesc->WriteBuffer[Index++] = 0xFFFFFFFF;
		//Set-Reset FFs
	if(restore>0){
		//printf("GRESTORE toggled\n");
		InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		InjDesc->WriteBuffer[Index++] = XHI_CMD_GRESTORE;
		InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
			//Deassert GHIGH_B signal - activate all interconnects
		//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
		//InjDesc->WriteBuffer[Index++] = 0x00000003;
		//for(int i=0;i<100;i++) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	}
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0X00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0X00000000;
		// Park the FAR
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FAR, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x03BE0000;
		// Append CRC
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
		// Initiate startup sequence
	//InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	//InjDesc->WriteBuffer[Index++] = XHI_CMD_START;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Desynchronize the device
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_DESYNCH;
	for(int i=0;i<16;i++) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//align to 64 bytes (16 words)
	while(Index % 16 != 0) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//for(int i=0;i<Index;i++)printf("WriteBuf[%3d] = %08x\n", i, InjDesc->WriteBuffer[i]);

	//Enable the pcap clock
	Status = Xil_In32(SLCR_PCAP_CLK_CTRL);
	if (!(Status & SLCR_PCAP_CLK_CTRL_EN_MASK)) {
		Xil_Out32(SLCR_UNLOCK, SLCR_UNLOCK_VAL);
		Xil_Out32(SLCR_PCAP_CLK_CTRL, (Status | SLCR_PCAP_CLK_CTRL_EN_MASK));
		Xil_Out32(SLCR_UNLOCK, SLCR_LOCK_VAL);
	}
	// Select PCAP interface for partial reconfiguration
	XDcfg_EnablePCAP(InjDesc->DevcI);
	XDcfg_SetControlRegister(InjDesc->DevcI, XDCFG_CTRL_PCAP_PR_MASK);
	// Clear the interrupt status bits
	XDcfg_IntrClear(InjDesc->DevcI, (XDCFG_IXR_PCFG_DONE_MASK | XDCFG_IXR_D_P_DONE_MASK | XDCFG_IXR_DMA_DONE_MASK) );
	// Check if DMA command queue is full
	Status = XDcfg_ReadReg(InjDesc->DevConigInterface.Config.BaseAddr, XDCFG_STATUS_OFFSET);
	if ((Status & XDCFG_STATUS_DMA_CMD_Q_F_MASK) == XDCFG_STATUS_DMA_CMD_Q_F_MASK) return XST_FAILURE;
	//Write the data to the FIFO and initiate the transfer of data present in the FIFO to the ICAP device
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	Status = XDcfg_Transfer(InjDesc->DevcI,
			(u32 *)InjDesc->WriteBuffer, Index,
			(u32 *)XDCFG_DMA_INVALID_ADDRESS, 0,
			XDCFG_NON_SECURE_PCAP_WRITE);
	if (Status != XST_SUCCESS) printf("Write Frame: XDcfg_Transfer failed \r\n");
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	waitPcapDone(InjDesc, 1, 10000);

	return XST_SUCCESS;
}




int writeFrames(InjectorDescriptor* InjDesc, int StartIndex, u32 FrameCount, FrameDescriptor* FrameArray){
	int Status;
	u32 Index = 0;
		// DUMMY and SYNC
	InjDesc->WriteBuffer[Index++] = XHI_DUMMY_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_BUS_WTH_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_BUS_DET_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_SYNC_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Reset CRC
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// ID register
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_IDCODE, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x03727093; //InjDesc->DevcI->Config.DeviceId & 0x0FFFFFFF;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000000;
		//GLUTMASK_B
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000400;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x00000400;
		// Setup CMD register - write configuration
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_WCFG;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup FAR
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FAR, 0x1);
	InjDesc->WriteBuffer[Index++] = FrameArray[StartIndex].FAR;
	InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
		// Setup Packet header.
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FDRI, 0 );
	InjDesc->WriteBuffer[Index++] = Type2_Packet(2, FRAME_SIZE*(FrameCount+1) );
		//Append the data frame
	for(int i=StartIndex; i < StartIndex+FrameCount; i++){
		memcpy(&InjDesc->WriteBuffer[Index], FrameArray[i].Data, FRAME_SIZE*sizeof(u32));
		Index += FRAME_SIZE;
	}
		//Append the pad frame
	for(int k=0;k<FRAME_SIZE;k++) InjDesc->WriteBuffer[Index++] = 0xFFFFFFFF;

	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_MASK, 0x1);
	InjDesc->WriteBuffer[Index++] = 0X00000100;
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CTL, 0x1);
	InjDesc->WriteBuffer[Index++] = 0X00000000;
		// Park the FAR
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_FAR, 0x1);
	InjDesc->WriteBuffer[Index++] = 0x03BE0000;
		// Append CRC
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_RCRC;
		// Desynchronize the device
	InjDesc->WriteBuffer[Index++] = Type1_Packet(2, XHI_CMD, 0x1);
	InjDesc->WriteBuffer[Index++] = XHI_CMD_DESYNCH;
	for(int i=0;i<16;i++) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//align to 64 bytes (16 words)
	while(Index % 16 != 0) InjDesc->WriteBuffer[Index++] = XHI_NOOP_PACKET;
	//for(int i=0;i<Index;i++)printf("WriteBuf[%3d] = %08x\n", i, InjDesc->WriteBuffer[i]);

	//Enable the pcap clock
	Status = Xil_In32(SLCR_PCAP_CLK_CTRL);
	if (!(Status & SLCR_PCAP_CLK_CTRL_EN_MASK)) {
		Xil_Out32(SLCR_UNLOCK, SLCR_UNLOCK_VAL);
		Xil_Out32(SLCR_PCAP_CLK_CTRL, (Status | SLCR_PCAP_CLK_CTRL_EN_MASK));
		Xil_Out32(SLCR_UNLOCK, SLCR_LOCK_VAL);
	}
	// Select PCAP interface for partial reconfiguration
	XDcfg_EnablePCAP(InjDesc->DevcI);
	XDcfg_SetControlRegister(InjDesc->DevcI, XDCFG_CTRL_PCAP_PR_MASK);
	// Clear the interrupt status bits
	XDcfg_IntrClear(InjDesc->DevcI, (XDCFG_IXR_PCFG_DONE_MASK | XDCFG_IXR_D_P_DONE_MASK | XDCFG_IXR_DMA_DONE_MASK) );
	// Check if DMA command queue is full
	Status = XDcfg_ReadReg(InjDesc->DevcI->Config.BaseAddr, XDCFG_STATUS_OFFSET);
	if ((Status & XDCFG_STATUS_DMA_CMD_Q_F_MASK) == XDCFG_STATUS_DMA_CMD_Q_F_MASK) return XST_FAILURE;
	//Write the data to the FIFO and initiate the transfer of data present in the FIFO to the ICAP device
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	Status = XDcfg_Transfer(InjDesc->DevcI,
			(u32 *)InjDesc->WriteBuffer, Index,
			(u32 *)XDCFG_DMA_INVALID_ADDRESS, 0,
			XDCFG_NON_SECURE_PCAP_WRITE);
	if (Status != XST_SUCCESS) printf("Write Frame: XDcfg_Transfer failed \r\n");
	Xil_DCacheFlush();
	Xil_DCacheInvalidate();
	waitPcapDone(InjDesc, 1, 1000000);

	return XST_SUCCESS;
}




//*******************GENERIC FUNCTIONS*****************************
FarFields parseFAR(u32 FAR){
	FarFields res;
	res.BLOCK 	= (FAR >> 23) & 0x00000007;
	res.TOP 	= (FAR >> 22) & 0x00000001;
	res.HCLKROW	= (FAR >> 17) & 0x0000001F;
	res.MAJOR 	= (FAR >> 7)  & 0x000003FF;
	res.MINOR 	=  FAR  	  & 0x0000007F;
	return(res);
}


int IsExcluded(u32 item){
	FarFields F = parseFAR(item);
	if(F.BLOCK == 0){
		if(F.TOP==0 && F.MAJOR<19 ) return(1);
		if(F.TOP==1 && F.HCLKROW==0 && F.MAJOR<19 ) return(1);
		if(F.TOP==1 && F.HCLKROW==0 && F.MAJOR==50 ) return(1);
		if(F.MAJOR > 70) return(1);
		if(F.MAJOR < 3) return(1);
	}
	else if(F.BLOCK == 1){
		if(F.TOP==0 && F.MAJOR<2 ) return(1);
		if(F.TOP==1 && F.HCLKROW==0 && F.MAJOR<2 ) return(1);
	}
	return(0);
}



u32 Type1_Packet(u32 Opcode, u32 RegAdr, u32 WordCnt){
	return( (1 << 29) | ((Opcode & 0x3) << 27) | ((RegAdr & 0x3FFF) << 13) | (WordCnt & 0x7FF) );
}

u32 Type2_Packet(u32 Opcode, u32 WordCnt){
	return( (2 << 29) | ((Opcode & 0x3) << 27) | (WordCnt & 0x7FFFFFF) );
}



void MaskFrameData(InjectorDescriptor* InjDesc, FarFields FC, u32 *FrameData){
	if(FC.BLOCK == 1){
		for(int i=0;i<InjDesc->BramMaskedCount;i++) FrameData[InjDesc->BramMaskedIndexes[i]] = FrameData[InjDesc->BramMaskedIndexes[i]]  & 0xFFFDFFFF;
	}
}

int IsMaskableWordIndex(InjectorDescriptor* InjDesc, FarFields FC, u32 index){
	if(index == 50) return(1);
	if(FC.BLOCK == 1){
		for(int i=0;i<InjDesc->BramMaskedCount;i++)
			if(index == InjDesc->BramMaskedIndexes[i])
				return(1);
	}
	return(0);
}



int cmpfuncInt (const void * a, const void * b) {
   return ( *(int*)a - *(int*)b );
}

int cmpfuncFrameDescriptor (const void * a, const void * b) {
	FrameDescriptor* cmpA = (FrameDescriptor*)a;
	FrameDescriptor* cmpB = (FrameDescriptor*)b;
   return ( cmpA->FAR - cmpB->FAR );
}


u32 set_bit(u32 data, u32 bit_index, u32 val){
	u32 mask = ~(1 << bit_index);
	return( (data & mask) | (val << bit_index)  );
}

u32 get_bit(u32 data, u32 bit_index){
	return( (data >> bit_index) & 0x1);
}


void print_job_desc(JobDescriptor* JobDesc){
	printf("Job Descriptor: \n\tBitstreamId=%08d \n\tBitstreamAddr=%08x \n\tBitstreamSize=%08x \n\tBitmaskAddr=  %08x \n\tBitmaskSize=  %08x \n\tFaultListAdr=  %08x \n\tFaultListItems=  %08x \n\tUpdateBitstream=%d \n\tmode=%d \n\tBlockType=%d \n\tCellType=%d \n\tEssential_bits=%d \n\tCheckRecovery=%d \n\tLogTimeout=%d \n\tStartIndex=%d \n\tExperimentsCompleted=%d \n\tCurrentFailureCount=%d \n\tCurrentMaskedCount=%d \n\tCurrentLatentCount=%d \n\tCurrentSDCCount=%d \n\tSampleSizeGoal=%d \n\tErrorMarginGoal=%.3f \n\tFaultMultiplicity=%d \n\tPopulationSize=%.0f \n\tSamplingWithoutRepetition = %d \n\n", JobDesc->BitstreamId, JobDesc->BitstreamAddr, JobDesc->BitstreamSize, JobDesc->BitmaskAddr, JobDesc->BitmaskSize, JobDesc->FaultListAdr, JobDesc->FaultListItems, JobDesc->UpdateBitstream, JobDesc->mode, JobDesc->BlockType, JobDesc->CellType, JobDesc->Essential_bits, JobDesc->CheckRecovery, JobDesc->LogTimeout, JobDesc->StartIndex, JobDesc->ExperimentsCompleted, JobDesc->CurrentFailureCount, JobDesc->CurrentMaskedCount, JobDesc->CurrentLatentCount, JobDesc->CurrentSDCCount, JobDesc->SampleSizeGoal, JobDesc->ErrorMarginGoal, JobDesc->FaultMultiplicity, JobDesc->PopulationSize, JobDesc->SamplingWithoutRepetition);
}


void PrintInjectorInfo(InjectorDescriptor* InjDesc){
	printf("Injector descriptor:");
	printf("\n\tBram Mask Indexes: "); for(int i=0;i<InjDesc->BramMaskedCount;i++)printf("%i,", InjDesc->BramMaskedIndexes[i]);
	printf("\n");
}


int percentage(int ind, int total){
	return((100*ind)/total);
}


void readconsole(char readbuf[]){
	int i=0;
	while(i<255) {
		readbuf[i] = inbyte();
		if(readbuf[i]=='\r' || readbuf[i]=='\n') break;
		i++;
	}
}


int input_int(){
	int res = 0;
	char8 key;
	while(1) {
		key = inbyte();
		if(key>=48 && key <=57){
			res = res*10+key-48;
		}
		if(key == '\r' || key =='\n')break;
	}
	return(res);
}



void print_frame(FrameDescriptor* Frame){
	printf("FAR = %08x\tFlags=%08x\n", Frame->FAR, Frame->Flags);
	printf("Data: ");
	for(int k=0;k<FRAME_SIZE;k++) printf("%08x ", Frame->Data[k]);
	printf("\nMask: ");
	for(int k=0;k<FRAME_SIZE;k++) printf("%08x ", Frame->Mask[k]);
	printf("\n");
}

void list_reference_frames(InjectorDescriptor * InjDesc){
	while(1){
		FarFields FC;
		printf("Input Block:\n");
		FC.BLOCK=input_int();
		printf("Input Top:\n");
		FC.TOP = input_int();
		printf("Input HCLKROW:\n");
		FC.HCLKROW = input_int();
		printf("Input MAJOR:\n");
		FC.MAJOR = input_int();
		printf("Input MINOR:\n");
		FC.MINOR = input_int();
		for(int i=0;i<InjDesc->FrameDescriptorsCount;i++){
			u32 FAR = FarSetup(FC.BLOCK, FC.TOP, FC.HCLKROW, FC.MAJOR, FC.MINOR);
			if(InjDesc->ReferenceFrames[i].FAR == FAR){
				print_frame(&(InjDesc->ReferenceFrames[i]));
				break;
			}
		}
	}
}

//************ CONTROL OF DUT CLOCK AND RESET  ************************



void CustomSleep(unsigned int microseconds)
{
  XTime tEnd, tCur;
  XTime_GetTime(&tCur);
  tEnd  = tCur + (((XTime) microseconds) * COUNTS_PER_MICROSECOND);
  do{
    XTime_GetTime(&tCur);
  } while (tCur < tEnd);
}


void SleepNS(unsigned int nanoseconds)
{
  XTime tEnd, tCur;
  XTime_GetTime(&tCur);
  tEnd  = tCur + (((XTime) nanoseconds) * COUNTS_PER_MICROSECOND)/1000;
  do{
    XTime_GetTime(&tCur);
  } while (tCur < tEnd);
}




void ResetPL(u32 duration_us){
	//Xil_DCacheFlush();
	//Xil_DCacheInvalidate();
	Xil_Out32(SLCR_UNLOCK_ADDR, SLCR_UNLOCK_KEY_VALUE);
    Xil_Out32(SLCR_LVL_SHFTR_EN_ADDR, SLCR_LVL_SHFTR_EN_VALUE);
    Xil_Out32(SLCR_FPGA_RST_CTRL_ADDR, 0x0);
    //Xil_DCacheFlush();
    Xil_Out32(SLCR_FPGA_RST_CTRL_ADDR, 0xf);	//rstN = 0 - default
    Xil_Out32(SLCR_CLK0_THROTTLE_CTRL_ADR, 0);
    Xil_Out32(SLCR_CLK0_THROTTLE_CNT_ADR, duration_us);
    Xil_Out32(SLCR_CLK0_THROTTLE_CTRL_ADR, 1);
    //Xil_DCacheFlush();
    while((Xil_In32(SLCR_CLK0_THROTTLE_STA_ADR) & 0xFFFF));
    Xil_Out32(SLCR_FPGA_RST_CTRL_ADDR, 0x0);
    //Xil_DCacheFlush();
    Xil_Out32(SLCR_LOCK_ADDR, SLCR_LOCK_KEY_VALUE);
}



void ClockThrottle(u32 mask){
	/* SLCR unlock */
	Xil_Out32(SLCR_UNLOCK_ADDR, SLCR_UNLOCK_KEY_VALUE);
    /* SLCR Enabling Level shifting */
    Xil_Out32(SLCR_LVL_SHFTR_EN_ADDR, SLCR_LVL_SHFTR_EN_VALUE);
    //Enable clock throttling
    Xil_Out32(SLCR_CLK0_THROTTLE_CNT_ADR, mask);
    Xil_Out32(SLCR_CLK0_THROTTLE_CTRL_ADR, mask);
    /* SLCR lock */
    Xil_Out32(SLCR_LOCK_ADDR, SLCR_LOCK_KEY_VALUE);
}


void RunClockCount(u16 clknum){
	Xil_Out32(SLCR_UNLOCK_ADDR, SLCR_UNLOCK_KEY_VALUE);
    /* SLCR Enabling Level shifting */
    Xil_Out32(SLCR_LVL_SHFTR_EN_ADDR, SLCR_LVL_SHFTR_EN_VALUE);
    Xil_Out32(SLCR_CLK0_THROTTLE_CTRL_ADR, 0);
    Xil_Out32(SLCR_CLK0_THROTTLE_CNT_ADR, clknum);
    Xil_Out32(SLCR_CLK0_THROTTLE_CTRL_ADR, 1);
    //Xil_DCacheFlush();
    Xil_Out32(SLCR_LOCK_ADDR, SLCR_LOCK_KEY_VALUE);
}


void WaitClockStops(){
	//when clock stops SLCR_CLK0_THROTTLE_STA_ADR equals 0
	while(Xil_In32(SLCR_CLK0_THROTTLE_STA_ADR) & 0xFFFF);
}


//*************************** TEST FUNCTIONS *********************

int FaultInjectionTest(InjectorDescriptor * InjDesc, FarFields Adr, int byteIndexToFlip, int verbose){
	int Status;
	// 1. Read one frame from configuration memory
	if(verbose > 0) printf("\n\n\nFault injection Test Phase-1: Read (BLOCK=%2d, TOP=%2d, ROW=%2d, MAJOR=%2d, MINOR=%2d)\n", Adr.BLOCK, Adr.TOP, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR );
	Status = readFrame(InjDesc, Adr.TOP, Adr.BLOCK, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
		if (Status != XST_SUCCESS) {
			printf("Failed to Read Frame: %d \r\n", Status);
			return XST_FAILURE;
		}
		if(verbose > 1){
			for (int k = 0; k < FRAME_SIZE; k++) printf("Frame Word %03d -> \t %08x \n", k  , InjDesc->ReadFrameData[k]);
			for (int k = 0; k < FRAME_SIZE; k++) printf("%08x", InjDesc->ReadFrameData[k]);
			printf("\n");
		}
	// 2. Modify the frame data (inject faults)
	if(verbose > 0) printf("Fault injection Test Phase-2: Modify frame data - flip byte %3d", byteIndexToFlip);
	for(int k=0;k<FRAME_SIZE;k++){ InjDesc->WriteFrameData[k] = InjDesc->ReadFrameData[k]; }
	//inverse the bits in some config word
	InjDesc->WriteFrameData[byteIndexToFlip]= ~(InjDesc->ReadFrameData[byteIndexToFlip]);
	// 3. Write back modified frame (same frame coordinates)
	if(verbose > 0) printf("\nFault injection Test Phase-3: Write back modified frame (BLOCK=%2d, TOP=%2d, ROW=%2d, MAJOR=%2d, MINOR=%2d)", Adr.BLOCK, Adr.TOP, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR );
	Status = writeFrame(InjDesc, Adr.TOP, Adr.BLOCK, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR, (u32 *) &(InjDesc->WriteFrameData[0]), 0);
		if (Status != XST_SUCCESS) {
			printf("Failed to write Frame: %d \r\n", Status);
			return XST_FAILURE;
		}

	// 4. Read the same frame again to check that changes were applied
	if(verbose > 0) printf("\nFault injection Test Phase-4: Readback after injection (BLOCK=%2d, TOP=%2d, ROW=%2d, MAJOR=%2d, MINOR=%2d)\n", Adr.BLOCK, Adr.TOP, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR );
	Status = readFrame(InjDesc, Adr.TOP, Adr.BLOCK, Adr.HCLKROW, Adr.MAJOR, Adr.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
		if (Status != XST_SUCCESS) {
			printf("Failed to Read Frame: %d \r\n", Status);
			return XST_FAILURE;
		}
		if(verbose > 1){
			for (int k = 0; k < FRAME_SIZE; k++) printf("Frame Word %03d -> \t %08x \n", k  , InjDesc->ReadFrameData[k]);
			for (int k = 0; k < FRAME_SIZE; k++) printf("%08x", InjDesc->ReadFrameData[k]);
			printf("\n");
		}
		if(InjDesc->WriteFrameData[byteIndexToFlip] == InjDesc->ReadFrameData[byteIndexToFlip]){
			if(verbose > 0) printf("Injection check: success\n");
		}
		else{
			if(verbose > 0)printf("Injection check: faulty value not valid (doesn't match after write back)\n");
			return(1);
		}
		return(0);
		//printf("\nSystem is still alive after injection :)");
}







void readback_manual_test(InjectorDescriptor * InjDesc, JobDescriptor* JobDesc){
	FarFields FC;
	u32 read_frame_data[FRAME_SIZE];
  //  ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, JobDesc->BitstreamSize >> 2);
	while(1){
		printf("Input Block:\n");
		FC.BLOCK=input_int();
		printf("Input Top:\n");
		FC.TOP = input_int();
		printf("Input HCLKROW:\n");
		FC.HCLKROW = input_int();
		printf("Input MAJOR:\n");
		FC.MAJOR = input_int();
		printf("Input MINOR:\n");
		FC.MINOR = input_int();
		readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, read_frame_data, 0);
		MaskFrameData(InjDesc, FC, read_frame_data);
		printf("\n");
		for(int i=0;i<FRAME_SIZE;i++) printf("%08x ", read_frame_data[i]);
		printf("\nalter cell:\n");
		u32 k =  input_int();
		if(k > 0){
			read_frame_data[k] = read_frame_data[k]^0x1;
			printf("Writing %08x\n", read_frame_data[k]);
			writeFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, read_frame_data, 0);
		}
	}
}



void list_minor_frames(InjectorDescriptor * InjDesc){
	FarFields FC;
	u32 read_frame_data[FRAME_SIZE];
	while(1){
		printf("Input Block:\n");
		FC.BLOCK=input_int();
		printf("Input Top:\n");
		FC.TOP = input_int();
		printf("Input HCLKROW:\n");
		FC.HCLKROW = input_int();
		printf("Input MAJOR:\n");
		FC.MAJOR = input_int();
		printf("\n");
		for(int i=0;i<FRAME_SIZE;i++) printf("%8d ", i);
		printf("\n");
		for(FC.MINOR = 0; FC.MINOR < 127; FC.MINOR++){
			readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, read_frame_data, 0);
			MaskFrameData(InjDesc, FC, read_frame_data);
			printf("\n");
			for(int i=0;i<FRAME_SIZE;i++) printf("%08x ", read_frame_data[i]);
		}
	}
}



void FarIncrTest(InjectorDescriptor * InjDesc, JobDescriptor* JobDesc, int verbose){
	u32 FAR;
	FarFields FC;
	ReloadCompleteBitstream(InjDesc->DevcI, JobDesc->BitstreamAddr, (JobDesc->BitstreamSize >> 2));
	ClockThrottle(0x1);
	InjDesc->FramesCount = 0;
	printf("Profiling started\n");
	for(u32 e = 0; e < 2; e++){
		FAR = e;
		FC = parseFAR(FAR);
		while(FC.BLOCK <= 1){
			//printf("FAR[%5d] =  %5d, %5d, %5d, %5d, %5d\n", InjDesc->FramesCount,  FC.BLOCK, FC.TOP, FC.HCLKROW, FC.MAJOR, FC.MINOR);
			if(InjDesc->FramesCount==0 || InjDesc->FramesCount>0 && InjDesc->FarItems[InjDesc->FramesCount-1]!=FAR) InjDesc->FarItems[InjDesc->FramesCount++] = FAR;
			readFrame(InjDesc, FC.TOP, FC.BLOCK, FC.HCLKROW, FC.MAJOR, FC.MINOR, (u32 *) &(InjDesc->ReadFrameData[0]), 0);
			XDcfg_GetConfigReg(InjDesc, XHI_FAR, &FAR);
			FAR = FAR | e;
			FC = parseFAR(FAR);
		};
	}
	qsort(InjDesc->FarItems, InjDesc->FramesCount, sizeof(u32), cmpfuncInt);
	for(int i=0;i<InjDesc->FramesCount;i++){
		FarFields FC = parseFAR(InjDesc->FarItems[i]);
		if(verbose) printf("%08x\n", InjDesc->FarItems[i]);
	}
}



//Update content of LUT BEL (INIT) located by coordinates: Top, HClkRow, CLB Column, SliceX, SliceY, ABCD= 1-4 (A-D)
void UpdateLutINIT(InjectorDescriptor* InjDesc, long Top, long HClkRow, long Column, long SliceX, long SliceY, u32 ABCD, u64 INIT){
	u32 FrameBuffer [FRAME_SIZE * 2];
	u32 minor= (SliceX%2==0) ? 32 : 26;
	u32 word = (SliceY%50)*2;
	if(word>=50)word++;
	if(ABCD>1) word++; //LUT C or D
	u32 halfword = (ABCD==1 || ABCD==3) ? 1 : 0;


	for(int i=0;i<4;i++){
		readFrame(InjDesc, Top,  0, HClkRow, Column, minor+i, &(FrameBuffer[0]), 0);

		u32 data = FrameBuffer[word];
		u32 INIT_Fragment = (INIT >> ((3-i)*16))&0x0000FFFF;
		if(halfword==0) data = (data&0xFFFF0000) |  INIT_Fragment;
		else data = (data&0x0000FFFF) | (INIT_Fragment<<16);
		FrameBuffer[word] = data;

		writeFrame(InjDesc, Top,  0, HClkRow, Column, minor+i, &(FrameBuffer[0]), 0);
	};
}

void SaveCheckpoint(InjectorDescriptor* InjDesc){
	for(int i=0;i<InjDesc->RegisterFramesNum;i++){
		FarFields x = parseFAR(InjDesc->RegisterFramesCaptured[i].FAR);
		readFrame(InjDesc, x.TOP, x.BLOCK, x.HCLKROW, x.MAJOR, x.MINOR, &(InjDesc->RegisterFramesCaptured[i].Data[0]), 1);
	}
	printf("Checkpoint saved\n");
}

void restoreCheckpoint(InjectorDescriptor* InjDesc){
	for(int i=0;i<InjDesc->RegisterFramesNum;i++){
		FarFields x = parseFAR(InjDesc->RegisterFramesCaptured[i].FAR);
		writeFrame(InjDesc, x.TOP, x.BLOCK, x.HCLKROW, x.MAJOR, x.MINOR, &(InjDesc->RegisterFramesCaptured[i].Data[0]), 1);
	}
}


int CountCheckpointMismatches(InjectorDescriptor* InjDesc){
	int res = 0;
	u32 trace[FRAME_SIZE];
	for(int i=0;i<InjDesc->RegisterFramesNum;i++){
		FarFields x = parseFAR(InjDesc->RegisterFramesCaptured[i].FAR);
		readFrame(InjDesc, x.TOP, x.BLOCK, x.HCLKROW, x.MAJOR, x.MINOR, &(trace[0]), 1);
		for(int word=0;word<FRAME_SIZE;word++){
			if(InjDesc->RegisterFramesCaptured[i].Data[word] != trace[word]) res++;
		}
	}
	return(res);
}


