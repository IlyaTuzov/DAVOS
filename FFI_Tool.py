#!python
# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Host-side standalone application to control FPGA-based fault injection
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

import os
import sys
from FFI.FFI_Host_Microblaze import *
from FFI.FFI_Host_Grmon import *
from FFI.Host_Zynq import *
#from FFI.FFI_ReportBuilder import *
import xml.etree.ElementTree as ET
from Davos_Generic import *
from Datamanager import *



def run_zynq_injector(davosconf, modelconf):
    Injector = FFIHostZynq(modelconf.work_dir,
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
            jdesc.Celltype = 1 if davosconf.FFI.target_logic.lower() in ['ff', 'ff+lutram'] \
                else 2 if davosconf.FFI.target_logic.lower() in ['lut','lutram'] \
                else 3 if davosconf.FFI.target_logic.lower() == 'bram' \
                else 2 if davosconf.FFI.target_logic.lower() == 'type0' \
                else 0
            jdesc.Blocktype = 0 if davosconf.FFI.target_logic.lower() in ['lut', 'ff', 'type0', 'ff+lutram', 'lutram'] \
                else 1 if davosconf.FFI.target_logic.lower() in ['bram'] \
                else 2
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
        pass
        #build_FFI_report(davosconf)



def run_microblaze_injector(davosconf, modelconf):
    Injector = FFIHostGrmon(modelconf.work_dir, davosconf.FFI.device_part, davosconf.FFI.dut_script)
    Injector.InjStat.register_failure_mode('masked', FailureModes.Masked)
    Injector.InjStat.register_failure_mode('fail', FailureModes.Fail)
    Injector.InjStat.register_failure_mode('hang', FailureModes.Hang)
    #Injector.InjStat.register_failure_mode('timeout', FailureModes.Timeout) 
    #Injector.InjStat.register_failure_mode('Other', FailureModes.Other)    
    Injector.InjStat.register_failure_mode('replicafail', FailureModes.ReplicaFail)
    Injector.InjStat.register_failure_mode('replicatimeout', FailureModes.ReplicaTimeout)
    #Injector.InjStat.register_failure_mode('replicahang', FailureModes.ReplicaHang)

    random.seed(davosconf.FFI.seed)
    hashing = False
    
    if davosconf.FFI.injector_phase:
        if davosconf.FFI.pblock is not None:
            pb = Pblock('TILE' in davosconf.FFI.pblock['notation'].upper(),
                        davosconf.FFI.pblock['X1'],
                        davosconf.FFI.pblock['Y1'],
                        davosconf.FFI.pblock['X2'],
                        davosconf.FFI.pblock['Y2'],
                        davosconf.FFI.pblock['name'])
        else:
            pb = None
        if davosconf.FFI.target_logic == 'type0':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, False)
            Injector.sample_SEU(pb, CellTypes.EssentialBits, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
        elif davosconf.FFI.target_logic == 'lut':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, False)
            Injector.design.map_lut_cells(davosconf.FFI.dut_scope, pb)
            Injector.sample_SEU(pb, CellTypes.LUT, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
        elif davosconf.FFI.target_logic == 'ff':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.FF, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
        elif davosconf.FFI.target_logic == 'bram':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.BRAM, davosconf.FFI.sample_size_goal, davosconf.FFI.fault_multiplicity)
        Injector.export_fault_list_bin(1000)
        Injector.export_fault_list_csv()
        #raw_input('Injector configured, Press any key to run the experiment...')
        Injector.restart_all('DAVOS started')
        Injector.run()

    if davosconf.FFI.reportbuilder_phase:
        if not davosconf.FFI.injector_phase:
            #restore Injector state from most recent log file
            logfiles = sorted(glob.glob(os.path.join(Injector.design.generatedFilesDir, 'LOG*.csv')))
            restore_file = logfiles[-1]
            Injector.initialize(False, restore_file, "", None, False)
            #print('Test successful')


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

