# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Multithreaded analysis of fault injection traces for redundant designs
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

import sys
import xml.etree.ElementTree as ET
import re
import os
import stat
import subprocess
import shutil
import datetime
import time
import random
import glob
import threading
from threading import Thread
from Davos_Generic import *
from Datamanager import *


target_filter = ''

class CompareGroup:
    def __init__(self, TargetNode, InjTime):
        self.TargetNode = TargetNode
        self.InjTime = InjTime
        self.ReferenceFile = ''
        self.ReferenceTrace = None
        self.MismatchesInterfaces = 0
        self.MismatchesResults = 0
        self.FailureModes = {}

    def load_trace(self, internal_labels, output_labels, trace_file):
        self.ReferenceFile = trace_file
        self.ReferenceTrace = simDump()
        self.ReferenceTrace.set_labels_copy(internal_labels, output_labels)
        self.ReferenceTrace.build_vectors_from_file(self.ReferenceFile)



def compare_traces(ref_trace, inj_trace, time_window):
    mismatches_int, mismatches_out = 0, 0
    time_points = sorted(list(set([i.time for i in ref_trace.vectors + inj_trace.vectors
                                   if (i.time >= time_window[0])])))
    for t in time_points:
        ref_v = ref_trace.get_vector_by_time(t, None)
        inj_v = inj_trace.get_vector_by_time(t, None)
        if (ref_v is None) and (inj_v is None):
            continue
        elif ((ref_v is None) and (inj_v is not None)) or ((ref_v is not None) and (inj_v is None)):
            mismatches_int += 1
            mismatches_out += 1
            continue
        else:
            for i in range(len(ref_trace.internal_labels)):
                if ref_v.internals[i] != inj_v.internals[i]:
                    mismatches_int += 1
            for i in range(len(ref_trace.output_labels)):
                if ref_v.outputs[i] != inj_v.outputs[i]:
                    mismatches_out += 1
    return (mismatches_int, mismatches_out)

def trace_fault_effect(ref_trace, master_trace, slave_trace, time_window, mode):
    if mode == 1:
        time_point = ref_trace.vectors[-1].time
        ref_v = ref_trace.get_vector_by_time(time_point, None)
        master_v = master_trace.get_vector_by_time(time_point, None)
        slave_v = slave_trace.get_vector_by_time(time_point, None)
        if master_v is None:
            return 'master_hang'
        master_reference = (ref_v.outputs == master_v.outputs)
        master_slave = False if (slave_v is None) else (master_v.outputs == slave_v.outputs)
        if master_reference:
            if master_slave:
                return 'masked'
            else:
                return 'false_alarm'
        else:
            if master_slave:
                return 'sdc'
            else:
                return 'signaled_failure'
    elif mode == 2:
        pass



# Script entry point when launched directly
if __name__ == "__main__":
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    # extract SBFI configuration from input XML
    tree = parse_xml_config(sys.argv[1]).getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    config.file = sys.argv[1]
    print (to_string(config, "Configuration: "))
    #fault_dict = FaultDict(os.path.join(config.call_dir, config.SBFI.fault_dictionary))
    # Prepare data model
    datamodel = None
    if config.platform == Platforms.Multicore or config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        if not os.path.exists(config.report_dir):
            os.makedirs(config.report_dir)
        datamodel = DataModel()
        datamodel.ConnectDatabase(config.get_DBfilepath(False), config.get_DBfilepath(True))
        datamodel.RestoreHDLModels(config.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
        datamodel.RestoreEntity(DataDescriptors.InjectionExp)
        datamodel.SaveHdlModels()

    toolconf.result_dir = 'irespack'
    target_dict = dict((x.ID, x) for x in datamodel.Target_lst)

    for conf in config.parconf:
        model = [x for x in datamodel.HdlModel_lst if x.Label == conf.label][0]
        #inj_descriptors = [x for x in datamodel.LaunchedInjExp_dict.values() if x.ModelID == model.ID]
        os.chdir(conf.work_dir)
        desctable = ExpDescTable(conf.label)
        desctable.build_from_csv_file(
            os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.exp_desc_file)), "Other")

        print('Processing simulation traces: {0}'.format(conf.label))
        datamodel.reference.reference_dump = simDump()
        datamodel.reference.reference_dump.build_labels_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.list_init_file)), config.SBFI.analyzer.rename_list)
        datamodel.reference.reference_dump.normalize_array_labels(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
        datamodel.reference.reference_dump.build_vectors_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
        datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels = datamodel.reference.reference_dump.get_labels_copy()
        datamodel.reference.JnGrLst = config.SBFI.analyzer.join_group_list.copy()
        datamodel.reference.reference_dump.join_output_columns(datamodel.reference.JnGrLst.copy())

        tw = config.SBFI.analyzer.time_window if config.SBFI.analyzer.time_window is not None else (datamodel.reference.reference_dump.vectors[0].time, datamodel.reference.reference_dump.vectors[-1].time)

        T = Table('SummaryFaultSim', ['Node', 'InjTime', 'Duration', 'FailureMode'])
        row_cnt = 0
        mis_interface_by_offsets = {}
        mis_outputs_by_offsets = {}
        datacorruption_by_offsets = {}

        cmp_groups, group = {}, None
        master_trace, slave_trace = None, None

        for sim_id in range(0, len(desctable.items)):
            sim_desc = desctable.items[sim_id]
            if (master_trace is None) or (master_trace.inj_target != sim_desc.target):
                master_trace = simDump()
                master_trace.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
                master_trace.build_vectors_from_file(os.path.join(conf.work_dir, toolconf.result_dir, sim_desc.dumpfile))
                master_trace.inj_target = sim_desc.target
                master_trace.inj_time = sim_desc.injection_time

            else:
                offset = sim_desc.injection_time - master_trace.inj_time
                if offset not in cmp_groups:
                    group = {'masked': 0,
                             'signaled_failure': 0,
                             'sdc': 0,
                             'false_alarm': 0,
                             'master_hang': 0,
                             'mismatches_interface': 0,
                             'mismatches_outputs': 0}
                    cmp_groups[offset] = group
                else:
                    group = cmp_groups[offset]
                slave_trace = simDump()
                slave_trace.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
                slave_trace.build_vectors_from_file(os.path.join(conf.work_dir, toolconf.result_dir, sim_desc.dumpfile))
                #mi, mo = compare_traces(master_trace, slave_trace, (tw[0]+ desctable.items[sim_id].injection_time, tw[1]))
                mi, mo = 0, 0
                if mi > 0: group['mismatches_interface'] += 1
                if mo > 0: group['mismatches_outputs'] += 1

                failure_mode = trace_fault_effect(
                    datamodel.reference.reference_dump, master_trace, slave_trace,
                    (tw[0]+ desctable.items[sim_id].injection_time, tw[1]), 1)
                group[failure_mode] += 1

            if sim_id % 100 == 0:
                sys.stdout.write('Processed {0:6d} traces\r'.format(sim_id))

        print("Offset, masked, signaled_failure, sdc, false_alarm, master_hang, mismatches_interface, mismatchs_outputs")
        for offset in sorted(cmp_groups.keys()):
            group = cmp_groups[offset]
            print("{0:7.1f}, {1:5d}, {2:5d}, {3:5d}, {4:5d}, {5:5d}, {6:5d}, {7:5d}".format(
                offset, group['masked'], group['signaled_failure'], group['sdc'], group['false_alarm'], group['master_hang'],
                group['mismatches_interface'], group['mismatches_outputs'] ))

