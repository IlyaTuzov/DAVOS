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
from zipfile import ZipFile
DAVOSPATH = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../..'))
sys.path.insert(1, DAVOSPATH)
from Davos_Generic import *
from Datamanager import *

target_filter = ''
ANALYSIS_MODE = 2

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

ref_bus_trace = None
def trace_fault_effect(ref_trace, master_trace, slave_trace, time_window, mode):
    global ref_bus_trace
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
        bus_labels = ['core0.ahbo.hbusreq', 'core0.ahbo.hburst', 'core0.ahbo.htrans', 'core0.ahbo.hwdata',
                      'core0.ahbo.hwrite', 'core0.ahbo.haddr', 'core0.ahbo.hsize']
        if ref_bus_trace is None:
            ref_bus_trace = ref_trace.select_columns(bus_labels)
        mas_bus_trace = master_trace.select_columns(bus_labels)
        slv_bus_trace = slave_trace.select_columns(bus_labels)
        ref_vf = [v for v in ref_bus_trace.vectors if v.time > time_window[0]]
        mas_vf = [v for v in mas_bus_trace.vectors if v.time > time_window[0]]
        slv_vf = [v for v in slv_bus_trace.vectors if v.time > time_window[0]]
        for i in range(len(ref_vf)):
            master_reference = False if (len(mas_vf) <= i) else (mas_vf[i].internals == ref_vf[i].internals)
            master_slave = False if ((len(mas_vf) <= i) or (len(slv_vf)<=i)) else (mas_vf[i].internals == slv_vf[i].internals)
            if master_reference:
                if master_slave:
                    continue
                else:
                    return 'false_alarm'
            else:
                if master_slave:
                    return 'sdc'
                else:
                    return 'signaled_failure'
        return 'masked'



def trace_diversity(ref_trace, head_trace, trail_trace, inj_time, offset, c_index):   
    c_index_I0, c_index_I1, c_index_R0, c_index_R1 = c_index['Inst0'], c_index['Inst1'], c_index['Regf0'], c_index['Regf1']
    time_points = [v.time for v in ref_trace.select_vectors('sample_clk', '1')]
    compared_vectors, missing_vectors = 0, 0
    mismatches_inst, mismatches_regf = 0, 0
    for t in time_points:
        if t>=time_points[0]+inj_time and t<=time_points[-1]-offset:
            try:
                inst_trail = trail_trace.vector_dict[t].internals[c_index_I0:c_index_I1+1]
                inst_head = head_trace.vector_dict[t+offset].internals[c_index_I0:c_index_I1+1]
                regf_trail = trail_trace.vector_dict[t].internals[c_index_R0:c_index_R1+1]
                regf_head = head_trace.vector_dict[t+offset].internals[c_index_R0:c_index_R1+1]    

                compared_vectors+=1
                if inst_trail != inst_head:
                    mismatches_inst += 1
                if regf_trail != regf_head:
                    mismatches_regf += 1
            except KeyError as e:
                missing_vectors+=1
    
    cpu_state = dict()
    t_inj_a = time_points[0]+inj_time
    t = [time_points[i] for i in range(len(time_points)) if time_points[i]<=t_inj_a and time_points[i+1]>=t_inj_a][0]
    cpu_state['inst_head']  = head_trace.vector_dict[t+offset].internals[c_index_I0:c_index_I1+1]    
    cpu_state['inst_trail'] = trail_trace.vector_dict[t].internals[c_index_I0:c_index_I1+1]
    cpu_state['regf_head']  = head_trace.vector_dict[t+offset].internals[c_index_R0:c_index_R1+1]
    cpu_state['regf_trail'] = trail_trace.vector_dict[t].internals[c_index_R0:c_index_R1+1]   
    
    #print('inj_time={0:0.1f}, time_points[0] = {1:0.1f}, inst_head = {2:0.1f}, inst_trail = {3:0.1f}'.format(
    #    inj_time, time_points[0], head_trace.vector_dict[t+offset].time, trail_trace.vector_dict[t].time))
    return( float(mismatches_inst)/compared_vectors, float(mismatches_regf)/compared_vectors, cpu_state)


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


    for conf in config.parconf:
        model = [x for x in datamodel.HdlModel_lst if x.Label == conf.label][0]
        #inj_descriptors = [x for x in datamodel.LaunchedInjExp_dict.values() if x.ModelID == model.ID]
        os.chdir(conf.work_dir)
        desctable = ExpDescTable(conf.label)
        dataset = ZipFile("{0}/{1}.zip".format(conf.work_dir, conf.label) , 'r')
        simfiles = dataset.namelist()
        with dataset.open('iresults/_summary.csv') as f:
            desctable.build_from_csv_file(f, "Other")

        print('Processing simulation traces: {0}'.format(conf.label))
        datamodel.reference.reference_dump = simDump()
        with dataset.open('code/simInitModel.do') as f:
            datamodel.reference.reference_dump.build_labels_from_file(f, config.SBFI.analyzer.rename_list)
        with dataset.open('iresults/{0}'.format(toolconf.reference_file)) as f:
            datamodel.reference.reference_dump.normalize_array_labels(f)
        with dataset.open('iresults/{0}'.format(toolconf.reference_file)) as f:
            datamodel.reference.reference_dump.build_vectors_from_file(f)
        datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels = datamodel.reference.reference_dump.get_labels_copy()
        datamodel.reference.JnGrLst = config.SBFI.analyzer.join_group_list.copy()
        datamodel.reference.reference_dump.join_output_columns(datamodel.reference.JnGrLst.copy())
        
        tw = config.SBFI.analyzer.time_window if config.SBFI.analyzer.time_window is not None \
            else (datamodel.reference.reference_dump.vectors[0].time, datamodel.reference.reference_dump.vectors[-1].time)

        c_index = dict()
        vname, c_index['Inst0'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.r.d.inst(0)')
        vname, c_index['Inst1'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.r.wb.ctrl(1).inst')
        vname, c_index['Regf0'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.rf.data1')
        vname, c_index['Regf1'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.rf_re4')    
        
        inst_lbl = datamodel.reference.reference_dump.internal_labels[c_index['Inst0']:c_index['Inst1']+1]
        regf_lbl = datamodel.reference.reference_dump.internal_labels[c_index['Regf0']:c_index['Regf1']+1]

        T = Table('SummaryFaultSim', ['Node', 'InjTime', 'StaggerDelay', 'FailureMode', 
                                      'Head_Inst ({0:s})'.format(':'.join(inst_lbl).replace('u0.iu0.','')), 
                                      'Trail_Inst ({0:s})'.format(':'.join(inst_lbl).replace('u0.iu0.','')), 
                                      'HeadRF ({0:s})'.format(':'.join(regf_lbl).replace('u0.iu0.','')), 
                                      'TrailRF ({0:s})'.format(':'.join(regf_lbl).replace('u0.iu0.',''))])
        row_cnt = 0
        mis_interface_by_offsets = {}
        mis_outputs_by_offsets = {}
        datacorruption_by_offsets = {}

        cmp_groups, group = {}, None
        head_trace, trail_trace = None, None

        for sim_id in range(0, len(desctable.items)):
            sim_desc = desctable.items[sim_id]
            if (head_trace is None) or (head_trace.inj_target != sim_desc.target):
                head_trace = simDump()
                head_trace.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
                with dataset.open('iresults/{0}'.format(sim_desc.dumpfile)) as f:
                    head_trace.build_vectors_from_file(f)
                head_trace.inj_target = sim_desc.target
                head_trace.inj_time = sim_desc.injection_time

            else:
                offset = head_trace.inj_time - sim_desc.injection_time
                if offset not in cmp_groups:
                    group = {'masked': 0,
                             'signaled_failure': 0,
                             'sdc': 0,
                             'false_alarm': 0,
                             'master_hang': 0,
                             'mismatches_interface': 0,
                             'mismatches_outputs': 0,
                             'diversity_inst' : float(0),
                             'diversity_regf' : float(0),
                             'trace_count' : 0}
                    cmp_groups[offset] = group
                else:
                    group = cmp_groups[offset]
                trail_trace = simDump()
                trail_trace.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
                with dataset.open('iresults/{0}'.format(sim_desc.dumpfile)) as f:
                    trail_trace.build_vectors_from_file(f)
                mi, mo = 0, 0 #compare_traces(master_trace, slave_trace, (tw[0]+ desctable.items[sim_id].injection_time, tw[1]))
                if mi > 0: group['mismatches_interface'] += 1
                if mo > 0: group['mismatches_outputs'] += 1

                failure_mode = trace_fault_effect(
                    datamodel.reference.reference_dump, head_trace, trail_trace,
                    (tw[0]+ desctable.items[sim_id].injection_time + offset, tw[1]), ANALYSIS_MODE)
                group[failure_mode] += 1

                diversity_inst, diversity_regf, cpu_state = trace_diversity(datamodel.reference.reference_dump, head_trace, trail_trace,
                    desctable.items[sim_id].injection_time, offset, c_index)
                group['diversity_inst'] += diversity_inst
                group['diversity_regf'] += diversity_regf
                group['trace_count'] += 1
                T.add_row([sim_desc.target, head_trace.inj_time, offset, failure_mode, 
                           ':'.join(cpu_state['inst_head']), ':'.join(cpu_state['inst_trail']), 
                           ':'.join(cpu_state['regf_head']), ':'.join(cpu_state['regf_trail'])])
            if sim_id % 100 == 0:
                sys.stdout.write('Processed {0:6d} traces\n'.format(sim_id))
                print("Offset, masked, signaled_failure, sdc, false_alarm, master_hang, mismatches_interface, mismatchs_outputs, diversity_inst, diversity_regf")
                for offset in sorted(cmp_groups.keys()):
                    group = cmp_groups[offset]
                    group['diversity_inst_perc'] = 100*group['diversity_inst'] / group['trace_count']
                    group['diversity_regf_perc'] = 100*group['diversity_regf'] / group['trace_count']
                    print("{0:7.1f}, {1:5d}, {2:5d}, {3:5d}, {4:5d}, {5:5d}, {6:5d}, {7:5d}, {8:0.2f}, {9:0.2f}".format(
                        offset, group['masked'], group['signaled_failure'], group['sdc'], group['false_alarm'], group['master_hang'],
                        group['mismatches_interface'], group['mismatches_outputs'], group['diversity_inst_perc'], group['diversity_regf_perc'] ))
        T.to_csv(',', False, os.path.join(conf.work_dir, 'SBFI_{0:s}.csv'.format(conf.label)))

