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
from multiprocessing import Pool
from zipfile import ZipFile
DAVOSPATH = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../..'))
sys.path.insert(1, DAVOSPATH)
from Davos_Generic import *
from Datamanager import *

target_filter = ''
ANALYSIS_MODE = 2
PAIRING_MODE = 1

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
        self.ReferenceTrace.build_vectors_from_file(self.ReferenceFile, True)


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
        bus_labels = ['clk', 'core0.ahbo.hbusreq', 'core0.ahbo.hindex' , 'core0.ahbo.hburst' , 'core0.ahbo.htrans' ,
                      'core0.ahbo.hwdata' , 'core0.ahbo.hwrite' , 'core0.ahbo.haddr'  , 'core0.ahbo.hirq'   ,
                      'core0.ahbo.hlock'  , 'core0.ahbo.hprot'  , 'core0.ahbo.hsize'  , 'core0.ahbo.hconfig(0)',
                      'core0.ahbo.hconfig(1)','core0.ahbo.hconfig(2)', 'core0.ahbo.hconfig(3)', 'core0.ahbo.hconfig(4)',
                      'core0.ahbo.hconfig(5)','core0.ahbo.hconfig(6)', 'core0.ahbo.hconfig(7)', 'core0.ahbi.hready']
        if ref_bus_trace is None:
            ref_bus_trace = ref_trace.select_columns(bus_labels)
        mas_bus_trace = master_trace.select_columns(bus_labels)
        slv_bus_trace = slave_trace.select_columns(bus_labels)
        ref_vf = [v for v in ref_bus_trace.select_vectors_multiple_filters({'clk':'1', 'core0.ahbi.hready':'1'}) if v.time > time_window[0]]
        mas_vf = [v for v in mas_bus_trace.select_vectors_multiple_filters({'clk':'1', 'core0.ahbi.hready':'1'}) if v.time > time_window[0]]
        slv_vf = [v for v in slv_bus_trace.select_vectors_multiple_filters({'clk':'1', 'core0.ahbi.hready':'1'}) if v.time > time_window[0]]
        for i in range(len(ref_vf)):
            master_reference = False if (len(mas_vf) <= i) else (mas_vf[i].internals == ref_vf[i].internals)
            master_slave = False if ((len(mas_vf) <= i) or (len(slv_vf)<=i)) else (mas_vf[i].internals == slv_vf[i].internals)
            if master_reference:
                if master_slave:
                    continue
                else:
                    #mas_bus_trace.vectors = mas_vf
                    #slv_bus_trace.vectors = slv_vf
                    #mas_bus_trace.to_html("H_{0:d}_{1:s}.html".format(i, master_trace.desc.dumpfile))
                    #slv_bus_trace.to_html("T_{0:d}_{1:s}.html".format(i, master_trace.desc.dumpfile))
                    return 'false_alarm'
            else:
                if master_slave:
                    return 'sdc'
                else:
                    return 'signaled_failure'
        return 'masked'



def trace_diversity(ref_trace, head_trace, trail_trace, inj_time, offset, c_index):   
    c_index_I0, c_index_I1, c_index_R0, c_index_R1 = c_index['Inst0'], c_index['Inst1'], c_index['Regf0'], c_index['Regf1']
    time_points = [v.time for v in ref_trace.select_vectors('clk', '1')]
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
    try:
        cpu_state['inst_head']  = head_trace.vector_dict[t+offset].internals[c_index_I0:c_index_I1+1]
        cpu_state['inst_trail'] = trail_trace.vector_dict[t].internals[c_index_I0:c_index_I1+1]
        cpu_state['regf_head']  = head_trace.vector_dict[t+offset].internals[c_index_R0:c_index_R1+1]
        cpu_state['regf_trail'] = trail_trace.vector_dict[t].internals[c_index_R0:c_index_R1+1]
    except KeyError as e:
        print('Missing vector at time: {0:s} in head {1:s}, trail: {2:s}'.format(str(t), str(head_trace.index), str(trail_trace.index)))
    #print('inj_time={0:0.1f}, time_points[0] = {1:0.1f}, inst_head = {2:0.1f}, inst_trail = {3:0.1f}'.format(
    #    inj_time, time_points[0], head_trace.vector_dict[t+offset].time, trail_trace.vector_dict[t].time))
    return( float(mismatches_inst)/compared_vectors, float(mismatches_regf)/compared_vectors, cpu_state)


# Script entry point when launched directly
def proc_traces(trace_range):
    global ref_bus_trace
    config = trace_range[2]
    conf = trace_range[3]
    toolconf =  trace_range[4]
    desctable = trace_range[5]
    # extract SBFI configuration from input XML
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
    ref_bus_trace = None

    model = [x for x in datamodel.HdlModel_lst if x.Label == conf.label][0]
    #inj_descriptors = [x for x in datamodel.LaunchedInjExp_dict.values() if x.ModelID == model.ID]
    os.chdir(conf.work_dir)
    #desctable = ExpDescTable(conf.label)
    dataset = ZipFile("{0}/{1}.zip".format(conf.work_dir, conf.label) , 'r')
    simfiles = dataset.namelist()
    #with dataset.open('iresults/_summary.csv') as f:
    #    desctable.build_from_csv_file(f, "Other")

    #print('Processing simulation traces: {0}'.format(conf.label))
    datamodel.reference.reference_dump = simDump()
    with dataset.open('code/simInitModel.do') as f:
        datamodel.reference.reference_dump.build_labels_from_file(f, config.SBFI.analyzer.rename_list)
    with dataset.open('iresults/{0}'.format(toolconf.reference_file)) as f:
        datamodel.reference.reference_dump.normalize_array_labels(f)
    with dataset.open('iresults/{0}'.format(toolconf.reference_file)) as f:
        datamodel.reference.reference_dump.build_vectors_from_file(f, True)
    datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels = datamodel.reference.reference_dump.get_labels_copy()
    datamodel.reference.JnGrLst = config.SBFI.analyzer.join_group_list.copy()
    datamodel.reference.reference_dump.join_output_columns(datamodel.reference.JnGrLst.copy())

    tw = config.SBFI.analyzer.time_window if config.SBFI.analyzer.time_window is not None \
        else (datamodel.reference.reference_dump.vectors[0].time, datamodel.reference.reference_dump.vectors[-1].time)

    c_index = dict()
    vname, c_index['Inst0'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.r.d.inst(0)')
    vname, c_index['Inst1'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.r.wb.ctrl(0).inst')
    vname, c_index['Regf0'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.rf.data1')
    vname, c_index['Regf1'] = datamodel.reference.reference_dump.get_index_by_label('u0.iu0.rf_re4')

    inst_lbl = datamodel.reference.reference_dump.internal_labels[c_index['Inst0']:c_index['Inst1']+1]
    regf_lbl = datamodel.reference.reference_dump.internal_labels[c_index['Regf0']:c_index['Regf1']+1]

    T = Table('SummaryFaultSim', ['Node', 'InjTime', 'StaggerDelay', 'FailureMode', 'DiversityInst', 'DiversityRegfile',
                                  'activity_match_local', 'activity_match_total',
                                  'Head_Inst ({0:s})'.format(':'.join(inst_lbl).replace('u0.iu0.','')),
                                  'Trail_Inst ({0:s})'.format(':'.join(inst_lbl).replace('u0.iu0.','')),
                                  'HeadRF ({0:s})'.format(':'.join(regf_lbl).replace('u0.iu0.','')),
                                  'TrailRF ({0:s})'.format(':'.join(regf_lbl).replace('u0.iu0.',''))])

    cmp_groups, group = {}, None
    head_trace, trail_trace = None, None

    for sim_id in range(trace_range[0], trace_range[1]+1):
        sim_desc = desctable.items[sim_id]
        trail_trace = simDump()
        trail_trace.set_labels_copy(datamodel.reference.initial_internal_labels,
                                    datamodel.reference.initial_output_labels)
        try:
            with dataset.open('iresults/{0}'.format(sim_desc.dumpfile)) as f:
                trail_trace.build_vectors_from_file(f, True)
        except Exception as e:
            print("Missing trace file: {0:s}".format(sim_desc.dumpfile))
            continue
        for base_trace in sim_desc.base_traces:
            head_id, offset, offset_group = base_trace[0], base_trace[1], base_trace[2]
            head_desc = desctable.items[head_id]
            head_trace = simDump()
            head_trace.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
            try:
                with dataset.open('iresults/{0}'.format(head_desc.dumpfile)) as f:
                    head_trace.build_vectors_from_file(f, True)
            except Exception as e:
                print("Missing trace file: {0:s}".format(head_desc.dumpfile))
                continue
            head_trace.index = head_id
            trail_trace.index = sim_id
            head_trace.inj_target = sim_desc.target
            head_trace.inj_time = sim_desc.injection_time

            if offset_group not in cmp_groups:
                group = {'masked': 0,
                         'signaled_failure': 0,
                         'sdc': 0,
                         'false_alarm': 0,
                         'master_hang': 0,
                         'mismatches_interface': 0,
                         'mismatches_outputs': 0,
                         'diversity_inst' : float(0),
                         'diversity_regf' : float(0),
                         'activity_match_local' : float(0),
                         'activity_match_total' : float(0),
                         'trace_count' : 0}
                cmp_groups[offset_group] = group
            else:
                group = cmp_groups[offset_group]

            mi, mo = 0, 0 #compare_traces(master_trace, slave_trace, (tw[0]+ desctable.items[sim_id].injection_time, tw[1]))
            if mi > 0: group['mismatches_interface'] += 1
            if mo > 0: group['mismatches_outputs'] += 1

            head_trace.desc = head_desc
            trail_trace.desc = sim_desc
            failure_mode = trace_fault_effect(
                datamodel.reference.reference_dump, head_trace, trail_trace,
                (tw[0]+ desctable.items[sim_id].injection_time + offset, tw[1]), ANALYSIS_MODE)
            group[failure_mode] += 1

            diversity_inst, diversity_regf, cpu_state = trace_diversity(datamodel.reference.reference_dump, head_trace, trail_trace,
                desctable.items[sim_id].injection_time, offset, c_index)
            group['diversity_inst'] += diversity_inst
            group['diversity_regf'] += diversity_regf
            group['activity_match_local'] += sim_desc.activity_match_local
            group['activity_match_total'] += sim_desc.activity_match_total

            group['trace_count'] += 1
            T.add_row([sim_desc.target, head_trace.inj_time, offset, failure_mode,
                       '{0:0.2f}'.format(100*diversity_inst), '{0:0.2f}'.format(100*diversity_regf),
                       '{0:0.2f}'.format(sim_desc.activity_match_local), '{0:0.2f}'.format(sim_desc.activity_match_total),
                       ':'.join(cpu_state['inst_head']), ':'.join(cpu_state['inst_trail']),
                       ':'.join(cpu_state['regf_head']), ':'.join(cpu_state['regf_trail'])])
        if ((sim_id-trace_range[0])%10==0) or (sim_id==trace_range[1]-1):
            with open(os.path.join(conf.logdir, 'results_{0:06d}-{1:06d}.txt'.format(trace_range[0], trace_range[1]-1)), 'a') as f:
                f.write("Pocessed {0:d} traces:\n".format(sim_id-trace_range[0]))
                f.write(groups_to_string(cmp_groups))
    return(T, cmp_groups)


def groups_to_string(groups):
    res = "Offset, masked, signaled_failure, sdc, false_alarm, master_hang, mismatches_interface, mismatchs_outputs, " \
          "diversity_inst, diversity_regf, activity_match_local, activity_match_total\n"
    for offset in sorted(groups.keys()):
        group = groups[offset]
        group['diversity_inst_perc'] = 100 * group['diversity_inst'] / group['trace_count']
        group['diversity_regf_perc'] = 100 * group['diversity_regf'] / group['trace_count']
        group['activity_match_local_perc'] = group['activity_match_local'] / group['trace_count']
        group['activity_match_total_perc'] = group['activity_match_total'] / group['trace_count']

        res += "{0:16s}, {1:5d}, {2:5d}, {3:5d}, {4:5d}, {5:5d}, {6:5d}, {7:5d}, {8:0.2f}, {9:0.2f}, {10:0.2f}, {11:0.2f}\n".format(
            str(offset), group['masked'], group['signaled_failure'], group['sdc'], group['false_alarm'], group['master_hang'],
            group['mismatches_interface'], group['mismatches_outputs'], group['diversity_inst_perc'],
            group['diversity_regf_perc'], group['activity_match_local_perc'], group['activity_match_total_perc'])
    return(res)


def merge_groups_list(grlist):
    res = {}
    for offset in sorted(grlist[0].keys()):
        res[offset] = copy.deepcopy(grlist[0][offset])
        for v in grlist[1:]:
            if offset in v:
                res[offset] = {key: res[offset].get(key, 0) + v[offset].get(key, 0)
                               for key in set(res[offset]) | set(v[offset])}
    return(res)



if __name__ == "__main__":
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    tree = parse_xml_config(sys.argv[1]).getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    config.file = sys.argv[1]
    print (to_string(config, "Configuration: "))
    offset_groups = config.SBFI.fault_model[0].stagger_offsets


    for conf in config.parconf:        
        logdir = os.path.join(conf.work_dir, 'stg_results_{0}'.format(conf.label))
        if not os.path.exists(logdir):
            os.mkdir(logdir)
        conf.logdir = logdir

        desctable = ExpDescTable(conf.label)
        dataset = ZipFile("{0}/{1}.zip".format(conf.work_dir, conf.label), 'r')
        simfiles = dataset.namelist()
        with dataset.open('iresults/_summary.csv') as f:
            desctable.build_from_csv_file(f, "Other")
        RegDescTable = Table('registers')
        with dataset.open('iresults/registers.csv') as f:
            RegDescTable.build_from_csv(f)


        script_dict = {}
        for i in desctable.items:
            script_dict[(i.target, i.injection_time)] = i.index
        for i in desctable.items:
            i.head_index = script_dict[(i.target, i.head_time)]
            head = desctable.items[i.head_index]
            i.activity_match_total = 100.0*len(i.active_nodes.intersection(head.active_nodes)) / RegDescTable.rownum()
            i.activity_match_local = 100.0*len(i.active_nodes.intersection(head.active_nodes)) / len(i.active_nodes.union(head.active_nodes))

        head, trail = None, None
        fix_head_indexes = set()
        target_groups = {}
        target = None
        for i in range(0, len(desctable.items)):
            desc =  desctable.items[i]
            if target != desc.target:
                fix_head_indexes.add(i)
                target = desc.target
            desc.base_traces = []
            if desc.target not in target_groups:
                target_groups[desc.target] = [i]
            else:
                target_groups[desc.target].append(i)

        if PAIRING_MODE == 1:
            for target in target_groups:
                for i in target_groups[target]:
                    trail = desctable.items[i]
                    for j in target_groups[target]:
                        if i != j and desctable.items[j].injection_time == trail.head_time:
                            offset = desctable.items[j].injection_time - trail.injection_time
                            d = [group for group in offset_groups if group[0] <= offset <= group[1]]
                            trail.base_traces.append((j, offset, str(d[0])))
                            break


        elif PAIRING_MODE == 2:
            for target in target_groups:
                for i in target_groups[target]:
                    head = desctable.items[i]
                    for j in target_groups[target]:
                        trail = desctable.items[j]
                        if j not in fix_head_indexes:
                            offset = head.injection_time - trail.injection_time
                            d = [group for group in offset_groups if group[0] <= offset <= group[1]]
                            if len(d) > 0:
                                trail.base_traces.append((i, offset, str(d[0])))

        # for i in range(0, len(desctable.items)):
        #     x = sorted(desctable.items[i].base_traces, key=lambda t: t[1], reverse=True)
        #     if len(x) > 0:
        #         desctable.items[i].base_traces = x[0:1]

        # head, trail = None, None
        # head_idx = 0
        # for i in range(0, len(desctable.items)):
        #     desctable.items[i].base_trace_idx = -2
        #     sys.stdout.write('processing {0:05d}\r'.format(i))
        #     if (head is None) or (head.target != desctable.items[i].target):
        #         head_idx = i
        #         head = desctable.items[i]
        #         head.base_trace_idx = -1
        #         head.offset = 0
        #         head.offset_group = ""
        #         vacant_groups = offset_groups[:]
        #     else:
        #         trail = desctable.items[i]
        #         offset = head.injection_time - trail.injection_time
        #         d = [group for group in vacant_groups if group[0] <= offset <= group[1]]
        #         if len(d)>0:
        #             trail.base_trace_idx = head_idx
        #             trail.offset = offset
        #             trail.offset_group = str(d[0])
        #             vacant_groups.remove(d[0])
        #         else:
        #             for j in range(head_idx, i):
        #                 offset = desctable.items[j].injection_time - trail.injection_time
        #                 d = [group for group in vacant_groups if group[0] <= offset <= group[1]]
        #                 if len(d)>0:
        #                     trail.base_trace_idx = j
        #                     trail.offset = offset
        #                     trail.offset_group = str(d[0])
        #                     vacant_groups.remove(d[0])
        #             if desctable.items[i].base_trace_idx < 0:
        #                 print('No base trace: ' + str(i))

        for i in range(0, len(desctable.items)):
            if len(desctable.items[i].base_traces) == 0:
                print('No base trace: ' +str(i))
        print('Number of non-linked traces: {0:d}'.format(len([i for i in desctable.items if len(i.base_traces) == 0])))

        proc_num = config.maxproc
        # trace_num, group_size = 12000, 12
        # group_num = trace_num/group_size
        # groups_per_proc = group_num/proc_num
        # input_items = [(i*groups_per_proc, (i+1)*groups_per_proc) for i in range(0, proc_num)] + \
        #               [(groups_per_proc*proc_num, groups_per_proc*proc_num+group_num-groups_per_proc*proc_num)]
        # input_items = [(i[0]*group_size, i[1]*group_size, config, conf, toolconf) for i in input_items]
        chunksize = len(desctable.items) / proc_num
        input_items = []

        for i in range(0, proc_num):
            left = 0 if i == 0 else input_items[i - 1][1] + 1
            right = left + chunksize
            if i==proc_num-1:
                right = len(desctable.items) - 1
            else:
                while desctable.items[right].target == desctable.items[right+1].target:
                    right += 1
            input_items.append((left, right, config, conf, toolconf, desctable))


        print('Starting pool of {0:d} analyzers'.format(proc_num))
        p = Pool(proc_num)
        res = p.map(proc_traces, input_items)
        tables = [i[0] for i in res]
        groups = [i[1] for i in res]
        T = Table.merge(conf.label, tables)
        T.to_csv(',', False, os.path.join(conf.logdir, 'SBFI_{0:s}.csv'.format(conf.label)))

        Res = merge_groups_list(groups)
        with open(os.path.join(conf.logdir, 'Result.txt'), 'w') as f:
            f.write(groups_to_string(Res))


