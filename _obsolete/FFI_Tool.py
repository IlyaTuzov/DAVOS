#!python
# Host-side standalone application to support Xilinx SEU emulation tool
# Requires python 2.x and pyserial library 
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# MIT license
# Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector

import os
import sys
from serial import Serial
from FFI.Host_Zynq import *
from FFI.FFI_ReportBuilder import *
import xml.etree.ElementTree as ET
from Davos_Generic import *
from Datamanager import *





        

if __name__ == "__main__":



    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    tree = parse_xml_config(sys.argv[1]).getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    davosconf.toolconf = toolconf
    davosconf.file = sys.argv[1]
    if not os.path.exists(davosconf.report_dir):
        os.makedirs(davosconf.report_dir)

    for modelconf in davosconf.parconf:

        Injector = FFIHostZynq(modelconf.work_dir,
                               0,
                               os.path.join(modelconf.work_dir, davosconf.FFIConfig.hdf_path),
                               os.path.join(modelconf.work_dir, davosconf.FFIConfig.init_tcl_path),
                               os.path.join(modelconf.work_dir, davosconf.FFIConfig.injectorapp_path),
                               davosconf.FFIConfig.memory_buffer_address,
                               True)
        Injector.RecoveryNodeNames = davosconf.FFIConfig.post_injection_recovery_nodes
        Injector.CustomLutMask = davosconf.FFIConfig.custom_lut_mask
        Injector.Profiling = davosconf.FFIConfig.profiling
        Injector.DAVOS_Config = davosconf
        Injector.target_logic = davosconf.FFIConfig.target_logic.lower()
        Injector.DutScope = davosconf.FFIConfig.dut_scope
        Injector.DevicePart = davosconf.FFIConfig.device_part
        Injector.PblockCoord = davosconf.FFIConfig.pblock_coodrinates
        Injector.extra_xsct_commands = davosconf.FFIConfig.extra_xsct_commands



        if davosconf.FFIConfig.injector_phase:
            #Select Zynq device
            devconfig = davosconf.FFIConfig.platformconf
            if len(devconfig) == 0:
                devconfig = Injector.get_devices('Cortex-A9 MPCore #0')     
            print "Available Devices:{}".format("".join(["\n\t"+str(x) for x in devconfig])) 
            devId = int(raw_input("Select Device {}:".format(str(range(len(devconfig))))))
            #Configure the injector
            Injector.configure(devconfig[devId]['TargetId'], devconfig[devId]['PortID'], "", "")
            #Clean the cache
            if raw_input('Clean the cache before running: Y/N: ').lower().startswith('y'):                                   
                Injector.cleanup_platform()

            #remove/force regenerate bitmask file
            if(os.path.exists(Injector.Output_FrameDescFile)): os.remove(Injector.Output_FrameDescFile)
            #Prepare the injection environment to launch the injector App    
            check = Injector.check_fix_preconditions()    
            print("Essential bits per type: "+str(Injector.EssentialBitsPerBlockType))
            #raw_input('Preconditions fixed....')
            if check:
                #raw_input("Preconditions fixed, press any key to run the injector >")
                jdesc = JobDescriptor(1)
                jdesc.UpdateBitstream = davosconf.FFIConfig.update_bitstream
                jdesc.Celltype = 1 if davosconf.FFIConfig.target_logic.lower() in ['ff', 'ff+lutram'] else 2 if davosconf.FFIConfig.target_logic.lower() in ['lut', 'lutram'] else 3 if davosconf.FFIConfig.target_logic.lower()=='bram' else 2 if davosconf.FFIConfig.target_logic.lower()=='type0' else 0
                jdesc.Blocktype = 0 if davosconf.FFIConfig.target_logic.lower() in ['lut', 'ff', 'type0', 'ff+lutram', 'lutram'] else 1 if davosconf.FFIConfig.target_logic.lower() in ['bram'] else 2
                jdesc.Essential_bits = 1
                jdesc.CheckRecovery = 1
                jdesc.LogTimeout = davosconf.FFIConfig.log_timeout
                jdesc.StartIndex = 0
                jdesc.Masked = 0
                jdesc.Signaled = 0
                jdesc.Latent = 0
                jdesc.Failures = 0
                jdesc.sample_size_goal  = davosconf.FFIConfig.sample_size_goal # if not Injector.Profiling else len(Injector.ProfilingResult)
                jdesc.error_margin_goal = davosconf.FFIConfig.error_margin_goal
                jdesc.FaultMultiplicity = davosconf.FFIConfig.fault_multiplicity
                jdesc.SamplingWithouRepetition = 1  #tracking of tested targets 
                jdesc.Mode = davosconf.FFIConfig.mode            #101 - Sampling, 102 - Exhaustive, 201 - Fault List
                jdesc.DetailedLog = 1
                jdesc.PopulationSize = Injector.EssentialBitsPerBlockType[jdesc.Blocktype]
                jdesc.WorkloadDuration = davosconf.FFIConfig.workload_duration
                jdesc.DetectLatentErrors = davosconf.FFIConfig.detect_latent_errors
                jdesc.InjectionTime = davosconf.FFIConfig.injection_time
                res = Injector.run(OperatingModes.SampleUntilErrorMargin, jdesc, False)
                print("Result: SampleSize: {0:9d}, Failures: {1:9d}, FailureRate: {2:3.5f} +/- {3:3.5f} ".format(res.ExperimentsCompleted, res.Failures, res.failure_rate, res.failure_error))    
                Injector.cleanup()
            else:
                raw_input("Preconditions fix failed, check the logfile for details, press any key to exit >")

    
        if davosconf.FFIConfig.reportbuilder_phase:
            build_FFI_report(davosconf)
