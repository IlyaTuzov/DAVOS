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
from FFI.FFI_Host_Monitored import *
#from FFI.FFI_ReportBuilder import *
import xml.etree.ElementTree as ET
from Davos_Generic import *
from Datamanager import *
from Reportbuilder import *


def run_zynq_injector(davosconf, modelconf):
    Injector = FFIHostZynq(modelconf.work_dir, davosconf.FFI.device_part)
    #Injector = FFIHostZynq(modelconf.work_dir,
    #                       0,
    #                       os.path.join(modelconf.work_dir, davosconf.FFI.hdf_path),
    #                       os.path.join(modelconf.work_dir, davosconf.FFI.init_tcl_path),
    #                       os.path.join(modelconf.work_dir, davosconf.FFI.injectorapp_path),
    #                       davosconf.FFI.memory_buffer_address,
    #                       True)
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
            Injector.sample_SEU(pb, CellTypes.EssentialBits, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'lut':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, False)
            Injector.design.map_lut_cells(davosconf.FFI.dut_scope, pb)
            Injector.sample_SEU(pb, CellTypes.LUT, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'ff':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.FF, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'bram':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.BRAM, davosconf.FFI)
        Injector.export_fault_list_full()
        Injector.export_fault_list_csv()
        raw_input('Injector configured, Press any key to run the experiment...')
        Injector.run()
        




def run_microblaze_injector(davosconf, modelconf):
    Injector = FFIHostMicroblaze(modelconf.work_dir, davosconf.FFI.device_part, davosconf.FFI.dut_script)
    Injector.FmodesToReset += davosconf.FFI.failure_modes_to_reset

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
            Injector.sample_SEU(pb, CellTypes.EssentialBits, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'lut':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, False)
            Injector.design.map_lut_cells(davosconf.FFI.dut_scope, pb)
            Injector.sample_SEU(pb, CellTypes.LUT, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'ff':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.FF, davosconf.FFI)
        elif davosconf.FFI.target_logic == 'bram':
            Injector.initialize(hashing, "", davosconf.FFI.dut_scope, pb, True)
            Injector.sample_SEU(pb, CellTypes.BRAM, davosconf.FFI)
        Injector.export_fault_list_bin(1000)
        #Injector.export_fault_list_full()
        Injector.export_fault_list_csv()
        #raw_input('Injector configured, Press any key to run the experiment...')
        Injector.restart_all('DAVOS started')
        Injector.run()

    if davosconf.FFI.reportbuilder_phase:
        if not davosconf.FFI.injector_phase:
            #restore Injector state from most recent log file
            logfiles = sorted(glob.glob(os.path.join(Injector.design.generatedFilesDir, 'LOG*.csv')))
            restore_file = logfiles[-1]
            #Injector.initialize(False, restore_file, "", None, False)
            Injector.load_fault_list_csv(restore_file)
        datamodel = DataModel()
        if not os.path.exists(davosconf.report_dir):
            os.makedirs(davosconf.report_dir)
        datamodel.ConnectDatabase(davosconf.get_DBfilepath(False), davosconf.get_DBfilepath(True))
        datamodel.RestoreHDLModels(davosconf.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
        model = datamodel.GetHdlModel(modelconf.label)
        ExpDescIdCnt = datamodel.GetMaxKey(DataDescriptors.InjectionExp) + 1
        for faultconf in Injector.fault_list:
            node = '/'.join(faultconf.SeuItems[0].DesignNode.split('/')[:-1])
            injcase = faultconf.SeuItems[0].DesignNode.split('/')[-1]
            target = datamodel.GetOrAppendTarget(node, davosconf.FFI.target_logic.upper(), injcase)
            InjDesc = InjectionDescriptor()
            InjDesc.InjectionTime = float(faultconf.SeuItems[0].Time)
            InjDesc.FailureMode = faultconf.FailureMode.upper()
            InjDesc.ID = ExpDescIdCnt
            InjDesc.ModelID = model.ID
            InjDesc.TargetID = target.ID
            InjDesc.FaultModel = 'BitFlip'
            InjDesc.ForcedValue = ''
            InjDesc.InjectionDuration = float(0)
            InjDesc.ObservationTime = float(0)
            InjDesc.Node = target.NodeFullPath
            InjDesc.InjCase = target.InjectionCase
            InjDesc.Status = 'F'
            InjDesc.FaultToFailureLatency = float(0)
            InjDesc.ErrorCount = 0
            InjDesc.Dumpfile = ''
            datamodel.LaunchedInjExp_dict[InjDesc.ID] = InjDesc
            ExpDescIdCnt += 1
        datamodel.SaveHdlModels()
        datamodel.SaveTargets()
        datamodel.SaveInjections()
        build_report(davosconf, davosconf.toolconf, datamodel, True)
        datamodel.SyncAndDisconnectDB()
    print("BAFFI: experiment finished, exiting")


if __name__ == "__main__":
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    tree = parse_xml_config(sys.argv[1]).getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    davosconf.toolconf = toolconf
    davosconf.file = sys.argv[1]
    if not os.path.exists(davosconf.report_dir):
        os.makedirs(davosconf.report_dir)

    for modelconf in davosconf.parconf:
        random.seed(davosconf.FFI.seed)
        if davosconf.FFI.injector == Injectors.Microblaze:
            run_microblaze_injector(davosconf, modelconf)
        elif davosconf.FFI.injector == Injectors.Zynq:
            run_zynq_injector(davosconf, modelconf)

