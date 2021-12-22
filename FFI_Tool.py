#!python
# Host-side standalone application to support Xilinx SEU emulation tool
# Requires python 2.x and pyserial library 
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# MIT license
# Latest version available at: https://github.com/IlyaTuzov/DAVOS/tree/master/XilinxInjector

import os
import sys
from FFI.Host_Microblaze import *
from FFI.FFI_ReportBuilder import *
import xml.etree.ElementTree as ET
from Davos_Generic import *
from Datamanager import *



def run_zynq_injector(davosconf, modelconf):
    Injector = InjectorHostManager(modelconf.work_dir,
                                   0,
                                   os.path.join(modelconf.work_dir, davosconf.FFI.hdf_path),
                                   os.path.join(modelconf.work_dir, davosconf.FFI.init_tcl_path),
                                   os.path.join(modelconf.work_dir, davosconf.FFI.injectorapp_path),
                                   davosconf.FFI.memory_buffer_address,
                                   True)
    Injector.RecoveryNodeNames = davosconf.FFI.post_injection_recovery_nodes
    Injector.CustomLutMask = davosconf.FFI.custom_lut_mask
    Injector.Profiling = davosconf.FFI.profiling
    Injector.DAVOS_Config = davosconf
    Injector.target_logic = davosconf.FFI.target_logic.lower()
    Injector.DutScope = davosconf.FFI.dut_scope
    Injector.DevicePart = davosconf.FFI.device_part
    Injector.PblockCoord = davosconf.FFI.pblock_coodrinates
    Injector.extra_xsct_commands = davosconf.FFI.extra_xsct_commands

    if davosconf.FFI.injector_phase:
        # Select Zynq device
        devconfig = davosconf.FFI.platformconf
        if len(devconfig) == 0:
            devconfig = Injector.get_devices('Cortex-A9 MPCore #0')
        print "Available Devices:{}".format("".join(["\n\t" + str(x) for x in devconfig]))
        devId = int(raw_input("Select Device {}:".format(str(range(len(devconfig))))))
        # Configure the injector
        Injector.configure(devconfig[devId]['TargetId'], devconfig[devId]['PortID'], "", "")
        # Clean the cache
        if raw_input('Clean the cache before running: Y/N: ').lower().startswith('y'):
            Injector.cleanup_platform()

        # remove/force regenerate bitmask file
        if (os.path.exists(Injector.Output_FrameDescFile)): os.remove(Injector.Output_FrameDescFile)
        # Prepare the injection environment to launch the injector App
        check = Injector.check_fix_preconditions()
        print("Essential bits per type: " + str(Injector.EssentialBitsPerBlockType))
        # raw_input('Preconditions fixed....')
        if check:
            # raw_input("Preconditions fixed, press any key to run the injector >")
            jdesc = JobDescriptor(1)
            jdesc.UpdateBitstream = davosconf.FFI.update_bitstream
            jdesc.Celltype = 1 if davosconf.FFI.target_logic.lower() in ['ff',
                                                                         'ff+lutram'] else 2 if davosconf.FFI.target_logic.lower() in [
                'lut',
                'lutram'] else 3 if davosconf.FFI.target_logic.lower() == 'bram' else 2 if davosconf.FFI.target_logic.lower() == 'type0' else 0
            jdesc.Blocktype = 0 if davosconf.FFI.target_logic.lower() in ['lut', 'ff', 'type0', 'ff+lutram',
                                                                          'lutram'] else 1 if davosconf.FFI.target_logic.lower() in [
                'bram'] else 2
            jdesc.Essential_bits = 1
            jdesc.CheckRecovery = 1
            jdesc.LogTimeout = davosconf.FFI.log_timeout
            jdesc.StartIndex = 0
            jdesc.Masked = 0
            jdesc.Signaled = 0
            jdesc.Latent = 0
            jdesc.Failures = 0
            jdesc.sample_size_goal = davosconf.FFI.sample_size_goal  # if not Injector.Profiling else len(Injector.ProfilingResult)
            jdesc.error_margin_goal = davosconf.FFI.error_margin_goal
            jdesc.FaultMultiplicity = davosconf.FFI.fault_multiplicity
            jdesc.SamplingWithouRepetition = 1  # tracking of tested targets
            jdesc.Mode = davosconf.FFI.mode  # 101 - Sampling, 102 - Exhaustive, 201 - Fault List
            jdesc.DetailedLog = 1
            jdesc.PopulationSize = Injector.EssentialBitsPerBlockType[jdesc.Blocktype]
            jdesc.WorkloadDuration = davosconf.FFI.workload_duration
            jdesc.DetectLatentErrors = davosconf.FFI.detect_latent_errors
            jdesc.InjectionTime = davosconf.FFI.injection_time
            res = Injector.run(OperatingModes.SampleUntilErrorMargin, jdesc, False)
            print("Result: SampleSize: {0:9d}, Failures: {1:9d}, FailureRate: {2:3.5f} +/- {3:3.5f} ".format(
                res.ExperimentsCompleted, res.Failures, res.failure_rate, res.failure_error))
            Injector.cleanup()
        else:
            raw_input("Preconditions fix failed, check the logfile for details, press any key to exit >")

    if davosconf.FFI.reportbuilder_phase:
        build_FFI_report(davosconf)



def run_microblaze_injector(davosconf, modelconf):
    Injector = NOELV_FFI_App(modelconf.work_dir, FPGASeries.S7, davosconf.FFI.device_part)
    Injector.initialize()
    pb = Pblock(davosconf.FFI.pblock['X1'], davosconf.FFI.pblock['Y1'], davosconf.FFI.pblock['X2'], davosconf.FFI.pblock['Y2'], davosconf.FFI.pblock['name'])
    if davosconf.FFI.target_logic == 'type0':
        Injector.sample_SEU(pb, CellTypes.EssentialBits, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
    elif davosconf.FFI.target_logic == 'lut':
        Injector.design.map_luts(davosconf.FFI.dut_scope, pb)
        Injector.sample_SEU(pb, CellTypes.LUT, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
    Injector.export_fault_list_bin(1000)
    Injector.export_fault_list_csv()
    random.seed(davosconf.FFI.seed)

    raw_input('Injector configured, Press any key to run the experiment...')
    Injector.connect_microblaze()
    Injector.connect_grmon(davosconf.FFI.grmon_script, davosconf.FFI.grmon_uart)
    Injector.run()




if __name__ == "__main__":
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    tree = parse_xml_config(sys.argv[1]).getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    davosconf.toolconf = toolconf
    davosconf.file = sys.argv[1]
    if not os.path.exists(davosconf.report_dir):
        os.makedirs(davosconf.report_dir)


    for modelconf in davosconf.parconf:
        if davosconf.FFI.injector == Injectors.Microblaze:
            run_microblaze_injector(davosconf, modelconf)
        elif davosconf.FFI.injector == Injectors.Zynq:
            run_zynq_injector(davosconf, modelconf)

