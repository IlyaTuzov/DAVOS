

#include <stdio.h>
#include <stdlib.h>
#include "platform.h"
#include "xil_printf.h"
#include "xtime_l.h"
#include "xil_cache.h"

#include "xgpiops.h"
#include "xilfpga.h"
#include "xilfpga_pcap.h"
#include "SeuInjector.h"


XGpioPs Gpio;
InjectorDescriptor InjDesc;






void TriggerGSR(){
	XGpioPs_Write(&Gpio, XGPIOPS_BANK4, 0x0);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK4, 0x1);
	usleep(1);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK4, 0x0);
	usleep(1);
}


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



int RunDutTest(int StopAtFirstMismatch){
	u32 input_data = 0x9;
	XGpioPs_SetDirection(&Gpio,    XGPIOPS_BANK3, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&Gpio, XGPIOPS_BANK3, 0xFF0000FF);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK3, input_data);
	XGpioPs_SetDirection(&Gpio,    XGPIOPS_BANK4, 0x3F);
	XGpioPs_SetOutputEnable(&Gpio, XGPIOPS_BANK4, 0x3F);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK4, 0x00000000);
	PL_reset_sync();

	RunClock(WorkloadClocks);
	WaitClockStops();
	int mismatches=0;
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_Write(&Gpio, XGPIOPS_BANK3, i<<24);
		RunClock(200);
		WaitClockStops();
		TraceVectorInj[i] = (XGpioPs_Read(&Gpio, XGPIOPS_BANK3) >> 8) & 0x0000FFFF;
		printf("result[%i] = %08x\n",i, TraceVectorInj[i]);
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			if(StopAtFirstMismatch)break;
		}
	}
	printf("Mismatches: %d \n", mismatches);
	return(mismatches > 0);
}



int InjectionFlowDutEnvelope(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc){
	FailureMode res = Unknown;
	int mismatches=0;

	//1. Set the DUT input data
	u32 input_data = 0x9;
	XGpioPs_SetDirection(&Gpio,    XGPIOPS_BANK3, 0xFF0000FF);
	XGpioPs_SetOutputEnable(&Gpio, XGPIOPS_BANK3, 0xFF0000FF);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK3, input_data);
	XGpioPs_SetDirection(&Gpio,    XGPIOPS_BANK4, 0x3F);
	XGpioPs_SetOutputEnable(&Gpio, XGPIOPS_BANK4, 0x3F);
	XGpioPs_Write(&Gpio, XGPIOPS_BANK4, 0x00000000);
	PL_reset_sync();

	//2. Run WorkloadClocks, and inject faults within this time interval
	RunInjectionFlow(InjDesc, fdesc, WorkloadClocks);

	//3. Read-out and verify the outputs (failures)
	for(u32 i=0;i<TraceVectorItems;i++){
		XGpioPs_Write(&Gpio, XGPIOPS_BANK3, i<<24);
		RunClock(200);
		WaitClockStops();
		TraceVectorInj[i] = (XGpioPs_Read(&Gpio, XGPIOPS_BANK3) >> 8) & 0x0000FFFF;
		//printf("result[%i] = %08x\n",i, TraceVectorInj[i]);
		if(TraceVectorInj[i] != TraceVectorRef[i]){
			mismatches++;
			//if(StopAtFirstMismatch)break;
		}
	}
	//4. Remove fault
	ProcessFaultDescriptor(InjDesc, fdesc, 1);

	//5. Failure mode
	if(mismatches == 0){
		res = Masked;
	}
	else{
		res = SDC;
	}
	char msg[255];
	sprintf(msg, "Mismatches: %d / %d, ", mismatches, TraceVectorItems);
	//Log results print statistics to stdout
	Log_Result(InjDesc, fdesc, res, msg);
	return(res);
}




void RunInjectionFlow(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc, int WorkloadDuration){
	//1. Run the workload until the fault injection time
	if(fdesc->time > 0){
		RunClock(fdesc->time);
		WaitClockStops();
	}
	//2. Inject randomly distributed faults
	ProcessFaultDescriptor(InjDesc, fdesc, 0);
	//3. Run the rest of workload cycles
	RunClock((u16)(WorkloadDuration-fdesc->time));
	WaitClockStops();
}


int main()
{

    init_platform();
	Xil_DCacheDisable();		//Disable the caches for correct PCAP operation
	Xil_ICacheDisable();
	int Status;
    XGpioPs_Config *ConfigPtr;


    //GPIO test
    ConfigPtr = XGpioPs_LookupConfig(GPIO_DEVICE_ID);
    Status = XGpioPs_CfgInitialize(&Gpio, ConfigPtr, ConfigPtr->BaseAddr);
    printf("EMIO-GPIO banks: %d, pins: %d\n", Gpio.MaxBanks, Gpio.MaxPinNum);

    //PCAP test
    XFpga XFpgaInstance = {0U};
	Status = XFpga_Initialize(&XFpgaInstance);
	if (Status != XST_SUCCESS) {
		printf("XFpga_Initialize: fail");
	}


	InjectorInitialize(&InjDesc);
	InjDesc.DebugMode = 0;

	StopClock();

	//RunDutTest(0);


	int FaultListOffset=0;
	FaultDescriptor *fdesc = InjDesc.fault_list_ptr + FaultListOffset;
	for (u32 i=0;i<InjDesc.FaultListSize;i++){
		InjectionFlowDutEnvelope(&InjDesc, fdesc);

		//lookup next FaultId
		u32 current_id = fdesc->Id;
		while(current_id == fdesc->Id) fdesc++;
	}






	char buffer[255];
	get_stat_msg(&InjDesc, buffer);
	printf("FFI experiment completed, Statistics: %s\n", buffer);

    cleanup_platform();
    return 0;
}

