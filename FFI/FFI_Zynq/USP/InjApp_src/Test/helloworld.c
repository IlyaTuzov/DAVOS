

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

#include "xcnn.h"
#include "cnn_input_images.h"
#include "cnn_labels_and_predictions.h"

const int IMAGE_HEIGHT = 28;
const int IMAGE_WIDTH = 28;
const int NUM_IMAGES = 100; // 1 - 100




FailureMode TestRun(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc);
void readResult();
int checkResult(int num_image);
void readMem(int num_image);
void initMem(int num_image);


XCnn instancePtr;
XGpioPs Gpio;
InjectorDescriptor InjDesc;




/* Writes the stated image to the specified memory address (0x00) */
void initMem(int num_image) {
	u32* base = (u32*) XPAR_PSU_DDR_0_S_AXI_BASEADDR;
	u32 offset = 0x0;
	u32 data;

	for (int i = 0; i < IMAGE_HEIGHT; i++) {
		for (int j = 0; j < IMAGE_WIDTH; j++) {
			data = *(unsigned int*) &INPUT_IMAGES[num_image][0][i][j];
			*(base + offset) = data;
			offset++;
		}
	}
}

/* Reads an image from the specified memory address (0x00), just for testing */
void readMem(int num_image) {
	u32* base = (u32*) XPAR_PSU_DDR_0_S_AXI_BASEADDR;
	u32 offset = 0x0;
	u32 read;
	u32 reference;

	for (int i = 0; i < IMAGE_HEIGHT; i++) {
		for (int j = 0; j < IMAGE_WIDTH; j++) {
			reference = *(unsigned int*) &INPUT_IMAGES[num_image][0][i][j];
			read = *(base + offset);
			printf("data[%d][0][%d][%d] 0x%08X (%.10f) = 0x%08X (%.10f)\n\r",
					num_image, i, j,
					read, *(float*) &read,
					reference, (float) INPUT_IMAGES[num_image][0][i][j]);
			offset++;
		}
	}

}

/* Checks and returns whether the provided result is correct (1) or wrong (0) */
int checkResult(int num_image) {
	u32* base = (u32*) XPAR_PSU_DDR_0_S_AXI_BASEADDR;
	u32 offset = 0x310; // 784 = 28 x 28
	u32 read;
	float data;

	float max;
	int index;

	//printf("Image %d\n", num_image);

	read = *(base + offset);
	offset++;
	max = *(float*) &read;
	index = 0;
	//printf("%d -> 0x%08X, %.10f \n\r", 0, read, max);

	for (int i = 1; i < 10; i++) {
		read = *(base + offset);
		data = *(float*) &read;
		if (data > max) {
			max = data;
			index = i;
		}
		//printf("%d -> 0x%08X, %.10f \n\r", i, read, data);
		offset++;
	}
	//printf("max[%d] = %.10f\n", index, max);
	if (index == res_cnn_prediction[num_image]) return 1;
	else return 0;

}

/* Reads the provided result from memory, just for testing */
void readResult() {
	u32* base = (u32*) XPAR_PSU_DDR_0_S_AXI_BASEADDR;
	u32 offset = 0x310; // 784 = 28 x 28
	u32 read;

	for (int i = 0; i < 10; i++) {
		read = *(base + offset);
		printf("%d -> 0x%08X, %.10f \n\r", i, read, *(float*) &read);
		offset++;
	}
}




FailureMode TestRun(InjectorDescriptor *InjDesc, FaultDescriptor *fdesc){
	FailureMode res = Unknown;
	u32 mismatches = 0;

	int results[100];
	XCnn_Initialize(&instancePtr, XPAR_CPU_ID);
	XCnn_DisableAutoRestart(&instancePtr);
	// wait until IDLE
	while (!XCnn_IsIdle(&instancePtr));
	// Set memory address (0x00) to get the image
	XCnn_Set_input_image(&instancePtr, 0);
	// wait until IDLE
	while (!XCnn_IsIdle(&instancePtr));
	// set the memory address to store the result (28 x28 = 784)
	XCnn_Set_classification(&instancePtr, 0xC40); // 28 x 28 = 768 x 4 = 3136


	//1. Inject fault
	ProcessFaultDescriptor(InjDesc, fdesc, 0);

	//2. Run workload
	for (int num_image = 0; num_image < NUM_IMAGES; num_image++) {
		// wait until IDLE
		while (!XCnn_IsIdle(&instancePtr));
		// write the image to the specified memory address (0x00)
		initMem(num_image);
		// start
		XCnn_Start(&instancePtr);
		// wait until done
		while(!XCnn_IsDone(&instancePtr));
		// Store whether the provided result is right (1) or wrong (0)
		results[num_image] = checkResult(num_image);
		if(results[num_image] == 0) mismatches += 1;
	}


	//3. Remove fault
	ProcessFaultDescriptor(InjDesc, fdesc, 1);

	//4. Analyze results, determine failure mode
	if(mismatches == 0){
		res = Masked;
	}
	else{
		res = SDC;
	}

	char msg[255];
	sprintf(msg, "Mismatches: %d / %d, ", mismatches, NUM_IMAGES);
	for (int i = 0; i < NUM_IMAGES; i++) {
			sprintf(msg+strlen(msg), "%d", results[i]);
	}

	//5. Log results print statistics to stdout
	Log_Result(InjDesc, fdesc, res, msg);

	return(res);
}




int main()
{

    init_platform();
	Xil_DCacheDisable();		//Disable the caches for correct PCAP operation
	Xil_ICacheDisable();


    //GPIO test
	/*
    XGpioPs_Config *ConfigPtr;
    ConfigPtr = XGpioPs_LookupConfig(GPIO_DEVICE_ID);
    Status = XGpioPs_CfgInitialize(&Gpio, ConfigPtr, ConfigPtr->BaseAddr);
    printf("EMIO-GPIO banks: %d, pins: %d\n", Gpio.MaxBanks, Gpio.MaxPinNum);
    XGpioPs_SetDirection(&Gpio, XGPIOPS_BANK3, 0x0);
	XGpioPs_SetOutputEnable(&Gpio, XGPIOPS_BANK3, 0x0);
	*/

    //PCAP test
    XFpga XFpgaInstance = {0U};
	int Status = XFpga_Initialize(&XFpgaInstance);
	if (Status != XST_SUCCESS) {
		printf("XFpga_Initialize: fail");
	}


	InjectorInitialize(&InjDesc);
	InjDesc.DebugMode = 0;

	int FaultListOffset=0;
	FaultDescriptor *fdesc = InjDesc.fault_list_ptr + FaultListOffset;
	for (u32 i=0;i<InjDesc.FaultListSize;i++){
		TestRun(&InjDesc, fdesc);

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

