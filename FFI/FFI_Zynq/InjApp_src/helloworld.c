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



#define WorkloadDuration 100
u32 a[WorkloadDuration], b[WorkloadDuration], op[WorkloadDuration], res_ref[WorkloadDuration], zero_ref[WorkloadDuration];

void reference_result(u32 a, u32 b, u32 op, u32* res, u32* zero);
void GenerateWorkload();






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


	//Mount SD card to use file caching
	TCHAR *Path = "0:/";
	FRESULT Res = f_mount(&fatfs, Path, 0);
	if (Res != FR_OK) { printf("Error Mounting FAT-FS\n"); }


	//Auto-initialize the injector structures,  using the DevC ID from Xparameters, pass a DUT-specific callback function to Run the Workload and check it's outputs
	InjectorInitialize(&InjDesc, XPAR_XDCFG_0_DEVICE_ID);
	InjDesc.cache_enabled = 1;				//enable caching of InjectorData, logical drive should be previously mounted (on SD card)

	ReadJobDesc(&JobDesc, BUFFER_ADDR, 1);	//Parse Job Data, uploaded from host
	JobDesc.FilterFrames = 0;				//ENABLE FRAME FILTERING ONLY IF EXTERNAL BITMASK IS NOT USED
	//JobDesc.UpdateBitstream=0;
	PrintInjectorInfo(&InjDesc);
	print_job_desc(&JobDesc);




	GenerateWorkload();
	//input_int();


	//Run default injection flow (custom flow argument is NULL) wait for results,
	//intermediate results will be logged to stdio and monitored by host App
	InjectionStatistics res = InjectorRun(&InjDesc, &JobDesc, NULL);



    cleanup_platform();
    return 0;
}







/* ------------------------------------------------
 * Adapt the functions below according to the DUT
 * ------------------------------------------------ */

void reference_result(u32 a, u32 b, u32 op, u32* res, u32* zero){
	switch(op){
	case 0:
		*res = a&b;
		break;
	case 1:
		*res = a|b;
		break;
	case 2:
		*res = a+b;
		break;
	case 6:
		*res = a-b;
		break;
	case 7:
		*res = a < b;
		break;
	default:
		*res = 0;
		break;
	}
	*res = (*res) & 0xF;
	*zero = *res == 0x0;
}


void GenerateWorkload(){
	srand(1);
	//generate workload and compute reference results
	for(int i = 0; i<WorkloadDuration; i++){
		a[i] = rand()%16;
		b[i] = rand()%16;
		op[i] = rand()%8;
		reference_result(a[i],b[i],op[i], &(res_ref[i]), &(zero_ref[i]) );
		printf("Workload_Vector[%3d]: a=%3x, b=%3x, op=%3x, res=%3x\n", i, a[i], b[i], op[i], res_ref[i]);
	}
}

void TriggerGSR(){
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x000000);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x100000);
	CustomSleep(1);
	XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2, 0x000000);
	CustomSleep(1);
}








int RunDutTest(int InjectionFlag, int StopAtFirstMismatch, int* alarm){
	u32 mismatches = 0;
	*alarm=0;
	int InjTime;

	ResetPL(1, 100);			//reset the DUT
	XGpioPs_SetDirection(&PsGpioPort,    XGPIOPS_BANK2, 0x00107FFF);
	XGpioPs_SetOutputEnable(&PsGpioPort, XGPIOPS_BANK2, 0x00107FFF);

	//Pick injection time (UUT clock cycle)
	if(InjectionFlag){
		if(JobDesc.InjectionTime <= 0)  InjTime = rand() % WorkloadDuration;	//by default inject at the workload start
		else InjTime = JobDesc.InjectionTime-1;									//Precise injection time
	}

	RunClockCount(1); WaitClockStops();
	for(u32 i=0; i<WorkloadDuration; i++){
		//Inject SEUs confjgured by JobDesc at the selected time instant
		if(InjectionFlag && i==InjTime){
			InjectSEU(&InjDesc, &JobDesc, InjTime);
		}

		u32 inp = ((op[i]<<12) & 0xF000) | ((b[i]<<8) & 0xF00)  | ((a[i]<<4) & 0xF0)   |  0x0001 ;
		XGpioPs_Write(&PsGpioPort, XGPIOPS_BANK2,  inp   );
		RunClockCount(1); WaitClockStops();
		u32 res_buf = (XGpioPs_Read(&PsGpioPort, XGPIOPS_BANK2) & 0xFFFF8000) >> 15;
		u32 res_uut = res_buf >> 1;
		u32 zero_uut = res_buf & 0x1;


		if(res_ref[i] != res_uut) mismatches++;
		//printf("res_ref = %10d, res_uut = %10d, mismatches=%2d\n", res_ref, res_uut, mismatches);
		if(StopAtFirstMismatch) break;
	}


	return(mismatches > 0);
}


