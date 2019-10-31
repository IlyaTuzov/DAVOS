#!python
# Host-side standalone application to support Xilinx SEU emulation tool
# Requires python 2.x and pyserial library 
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# MIT license
# Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector

import os
import sys
from serial import Serial
from XilinxInjector.InjHostLib import *
import xml.etree.ElementTree as ET
from Davos_Generic import *
from Datamanager import *




        

if __name__ == "__main__":

    if len(sys.argv) > 1:   #XML config file as input
        toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
        normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
        normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
        xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
        tree = xml_conf.getroot()
        davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
        config = davosconf #.FaultInjectionConfig
        config.toolconf = toolconf
        config.file = normconfig


#        InitializeHDLModels(davosconf.FaultInjectionConfig, davosconf.toolconf)

        Injector = InjectorHostManager(config.FaultInjectionConfig.parconf[0].work_dir, 
                                       0, 
                                       os.path.join(config.FaultInjectionConfig.parconf[0].work_dir, "./MicZC.sdk/BD_wrapper_hw_platform_0/system.hdf"),
                                       os.path.join(config.FaultInjectionConfig.parconf[0].work_dir, "./MicZC.sdk/BD_wrapper_hw_platform_0/ps7_init.tcl"),
                                       os.path.join(config.FaultInjectionConfig.parconf[0].work_dir, "./MicZC.sdk/InjectorApp/Debug/InjectorApp.elf"),
                                       0x3E000000)
        #Setup nodes to force recover after each injection (BRAMs as ROM)
        Injector.RecoveryNodeNames = davosconf.ExperimentalDesignConfig.design_genconf.post_injection_recovery_nodes
        Injector.CustomLutMask = False
        Injector.Profiling = False
        Injector.DAVOS_Config = config

    #proj_path = 'C:/Projects/GENETIC/Microblaze/MicZC'
    #Injector = InjectorHostManager(proj_path, 
    #                               0, 
    #                               os.path.join(proj_path, "./MicZC.sdk/BD_wrapper_hw_platform_0/system.hdf"),
    #                               os.path.join(proj_path, "./MicZC.sdk/BD_wrapper_hw_platform_0/ps7_init.tcl"),
    #                               os.path.join(proj_path, "./MicZC.sdk/InjectorApp/Debug/InjectorApp.elf"),
    #                               0x3E000000)
    ##Setup nodes to force recover after each injection (BRAMs as ROM)
    #Injector.RecoveryNodeNames = ['ramloop']
#    Injector.attachMemConfig(   os.path.join(proj_path, "./MicZC.sdk/BD_wrapper_hw_platform_0/BD_wrapper.mmi"), 
#                                os.path.join(proj_path, "./MicZC.sdk/AppM/Debug/AppM.elf"), 
#                                'BD_i/microblaze_0' )


    #Tab = Table('LutMapList')
    #Tab.build_from_csv(os.path.join(config.FaultInjectionConfig.parconf[0].work_dir, 'LutMapList.csv'))
    #LutMapList = TableToLutList(Tab)  
    #AggregateInjectionResults(LutMapList, os.path.join(config.FaultInjectionConfig.parconf[0].work_dir,'./log/ProfilingResult.log'))
    ###AggregateInjectionResults(LutMapList, os.path.join(config.FaultInjectionConfig.parconf[0].work_dir,'./log/ProfilingResult.log'), os.path.join(config.FaultInjectionConfig.parconf[0].work_dir,'SummaryFaultSim.csv'))
    #with open(os.path.join(config.FaultInjectionConfig.parconf[0].work_dir,'LutMapList_Upd_ext.csv'),'w') as f:
    #    zTab = LutListToTable(LutMapList, True, False)
    #    print('zT built')
    #    f.write(zTab.to_csv())
    ###ExportProfilingStatistics(LutMapList, os.path.join(config.FaultInjectionConfig.parconf[0].work_dir,'PerFrame.csv'))
    #raw_input('Updated')


    #raw_input('Hello')
    #Select Zynq device
    devconfig = [{'TargetId':'2', 'PortID':'COM3'}] 
    if len(devconfig) == 0:
        devconfig = Injector.get_devices('Cortex-A9 MPCore #0')     
    print "Available Devices:{}".format("".join(["\n\t"+str(x) for x in devconfig])) 
    devId = int(raw_input("Select Device {}:".format(str(range(len(devconfig))))))

    #Configure the injector
    Injector.configure(devconfig[devId]['TargetId'], devconfig[devId]['PortID'], "", "")
    #Injector.configure(devconfig[devId]['TargetId'], devconfig[devId]['PortID'], "AVR_ZC702.xpr", "impl_1")

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
        jdesc.UpdateBitstream = 1
        jdesc.Blocktype = 0
        jdesc.Essential_bits = 1
        jdesc.CheckRecovery = 1
        jdesc.LogTimeout = 1
        jdesc.StartIndex = 0
        jdesc.Masked = 0
        jdesc.Failures = 0
        jdesc.sample_size_goal = 10000 if not Injector.Profiling else len(Injector.ProfilingResult)
        jdesc.error_margin_goal = float(0) 
        jdesc.FaultMultiplicity = 1
        jdesc.PopulationSize = float(14000)*Injector.EssentialBitsPerBlockType[jdesc.Blocktype]
        jdesc.SamplingWithouRepetition = 0  #disable tracking of tested targets
        jdesc.Mode = 104    
        
        res = Injector.run(OperatingModes.SampleUntilErrorMargin, jdesc, False)
        print("Result: SampleSize: {0:9d}, Failures: {1:9d}, FailureRate: {2:3.5f} +/- {3:3.5f} ".format(res.ExperimentsCompleted, res.Failures, res.failure_rate, res.failure_error))    
        Injector.cleanup()
    else:
        raw_input("Preconditions fix failed, check the logfile for details, press any key to exit >")

    
