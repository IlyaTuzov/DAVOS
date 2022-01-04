# Multithreaded analysis of fault injection traces
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

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

EnhancedAnalysisOfLatentErrors = False


def check_outputs(ref_trace, inj_trace, time_window, mode, max_time_violation):
    """
    Locates mismatches on DUT outputs (any mismatch is treated as DUT failure)
    Args:
        mode ():
        ref_trace ():
        inj_trace ():
        time_window ():

    Returns:
         dictionary: key='DomainLabel', val= [number of mismatches, time of first mismatch]
    """
    res = dict((k, [0, None]) for k in ref_trace.domain_indices.keys())
    time_points = sorted(list(set([i.time for i in ref_trace.vectors + inj_trace.vectors
                                   if (i.time >= time_window[0])])))
    if mode == TraceCheckModes.MAV:
        for t in time_points:
            ref_v = ref_trace.get_vector_by_time(t, None)
            inj_v = inj_trace.get_vector_by_time(t, None)
            for k, v in ref_trace.domain_indices.items():
                for i in v:
                    if ref_v.outputs[i] != inj_v.outputs[i]:
                        res[k][0] += 1
                        if res[k][1] is None:
                            res[k][1] = t
                        break

    elif mode == TraceCheckModes.MLV and len(time_points) > 0:
        ref_v = ref_trace.get_vector_by_time(time_points[-1], None)
        inj_v = inj_trace.get_vector_by_time(time_points[-1], None)
        for k, v in ref_trace.domain_indices.items():
            for i in v:
                if ref_v.outputs[i] != inj_v.outputs[i]:
                    res[k][0] = 1
                    res[k][1] = time_points[-1]
                    break
    return res


def check_tmr(ref_trace, inj_trace, time_window, mode, max_time_violation):
    if len(ref_trace.domain_indices.keys()) < 3:
        print('SBFI analyzer error: number of domains ({0}) is less than required for TMR')
        return None
    time_points = sorted(list(set([i.time for i in ref_trace.vectors + inj_trace.vectors
                                   if (i.time >= time_window[0])])))
    ref_v = ref_trace.get_vector_by_time(time_points[-1], None)
    inj_v = inj_trace.get_vector_by_time(time_points[-1], None)
    tmr_match = True
    m1, m2, m3 = 0, 0, 0
    t1, t2, t3 = None, None, None
    domains = sorted(ref_trace.domain_indices.keys())
    rsize = len(ref_trace.domain_indices[domains[0]])
    for item_id in range(rsize):
        i1, i2, i3 = ref_trace.domain_indices[domains[0]][item_id], ref_trace.domain_indices[domains[1]][item_id], ref_trace.domain_indices[domains[2]][item_id]
        h1, h2, h3 = int(inj_v.outputs[i1], 16), int(inj_v.outputs[i2], 16), int(inj_v.outputs[i3], 16)
        if h1 != int(ref_v.outputs[i1], 16):
            m1 += 1
            if t1 is None: t1 = time_points[-1]
        if h2 != int(ref_v.outputs[i2], 16):
            m2 += 1
            if t2 is None: t2 = time_points[-1]
        if h3 != int(ref_v.outputs[i3], 16):
            m3 += 1
            if t3 is None: t3 = time_points[-1]
        voted = (h1 & h2) | (h1 & h3) | (h2 & h3)
        if voted != int(ref_v.outputs[i1], 16):
            tmr_match = False
    return {domains[0]: (m1, t1), domains[1]: (m2, t2), domains[2]: (m3, t3)}, tmr_match





def count_latent_errors(ref_trace, inj_trace, time_window):
    mismatches = 0
    #    time_points = sorted(list(set([i.time for i in ref_trace.vectors + inj_trace.vectors
    #                                   if (i.time >= time_window[0]) and (i.time <= time_window[1])])))
    time_points = sorted(list(set([i.time for i in ref_trace.vectors + inj_trace.vectors
                                   if (i.time >= time_window[0])])))

    if len(time_points) > 0:
        ref_v = ref_trace.get_vector_by_time(time_points[-1], None)
        inj_v = inj_trace.get_vector_by_time(time_points[-1], None)
        for i in range(len(ref_v.internals)):
            if ref_v.internals[i] != inj_v.internals[i]:
                mismatches += 1
    return mismatches


def process_dumps_in_linst(config, toolconf, conf, datamodel, DescItems, baseindex):
    model = datamodel.GetHdlModel(conf.label)
    basetime = datamodel.reference.reference_dump.vectors[-1].time - conf.workload_time
    ExpDescIdCnt = baseindex
    tw = config.SBFI.analyzer.time_window if config.SBFI.analyzer.time_window is not None else (datamodel.reference.reference_dump.vectors[0].time, datamodel.reference.reference_dump.vectors[-1].time)
    print("Analysis of traces, time window: {0}".format(str(tw)))

    err_signal_index = None, None
    if config.SBFI.analyzer.error_flag_signal != '':
        if '{{{0}}}'.format(config.SBFI.analyzer.error_flag_signal) in datamodel.reference.reference_dump.internal_labels:
            err_signal_index = 0, datamodel.reference.reference_dump.internal_labels.index('{{{0}}}'.format(config.SBFI.analyzer.error_flag_signal))
        elif '{{{0}}}'.format(config.SBFI.analyzer.error_flag_signal) in datamodel.reference.reference_dump.output_labels:
            err_signal_index = 1, datamodel.reference.reference_dump.output_labels.index('{{{0}}}'.format(config.SBFI.analyzer.error_flag_signal))

    for item in DescItems:
        if ExpDescIdCnt % 10 == 0:
            sys.stdout.write("\r%s: Processing dump: %6i" % (conf.label, ExpDescIdCnt))
            sys.stdout.flush()
        target = datamodel.GetOrAppendTarget(item.target, item.instance_type, item.injection_case)
        InjDesc = InjectionDescriptor()
        InjDesc.ID = ExpDescIdCnt
        InjDesc.ModelID = model.ID
        InjDesc.TargetID = target.ID
        InjDesc.FaultModel = item.fault_model
        InjDesc.ForcedValue = item.forced_value
        InjDesc.InjectionTime = item.injection_time
        InjDesc.InjectionDuration = item.duration
        InjDesc.ObservationTime = item.observation_time
        InjDesc.Node = item.target
        InjDesc.InjCase = item.injection_case
        InjDesc.DomainMatch = {}
        for k in datamodel.reference.reference_dump.domain_indices.keys():
            InjDesc.DomainMatch[k] = '-'
        inj_dump = simDump()
        inj_dump.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
        if inj_dump.build_vectors_from_file(os.path.join(conf.work_dir, toolconf.result_dir, item.dumpfile)) == None:
            InjDesc.Status = 'E'  # error
        else:
            InjDesc.Status = 'S'  # Simulation successful and dumpfile exists

            err_raised = False
            if err_signal_index[0] is not None:
                for v in inj_dump.vectors:
                    if err_signal_index[0] == 0:
                        if v.internals[err_signal_index[1]] == config.SBFI.analyzer.error_flag_active_value:
                            err_raised = True
                            break
                    elif err_signal_index[0] == 1:
                        if v.outputs[err_signal_index[1]] == config.SBFI.analyzer.error_flag_active_value:
                            err_raised = True
                            break

            InjDesc.ErrorCount = count_latent_errors(datamodel.reference.reference_dump, inj_dump, tw)
            InjDesc.FaultToFailureLatency = float(0)

            if config.SBFI.analyzer.domain_mode.upper() in ['', 'SIMPLEX']:
                output_match_res = check_outputs(datamodel.reference.reference_dump, inj_dump, tw, config.SBFI.analyzer.mode, config.SBFI.analyzer.max_time_violation)
                for k, v in output_match_res.items():
                    InjDesc.DomainMatch[k] = 'V' if v[0] == 0 else 'X'
                out_misnum = sum(v[0] for k, v in output_match_res.items())
                if out_misnum > 0:
                    first_mismatch = min(v[1] for k, v in output_match_res.items() if v[1] is not None)
                    InjDesc.FaultToFailureLatency = first_mismatch - basetime - float(InjDesc.InjectionTime)
                    if InjDesc.FaultToFailureLatency < 0:  InjDesc.FaultToFailureLatency = float(0)
                # Determine failure mode
                if out_misnum == 0:
                    if InjDesc.ErrorCount == 0:
                        InjDesc.FailureMode = 'M'  # Masked fault
                    else:
                        InjDesc.FailureMode = 'L'  # Latent fault
                else:
                    if err_raised:
                        InjDesc.FailureMode = 'S'  # Signaled Failure
                    else:
                        InjDesc.FailureMode = 'C'  # Silent Data Corruption
            elif config.SBFI.analyzer.domain_mode.upper() in ['TMR']:
                output_match_res, tmr_match = check_tmr(datamodel.reference.reference_dump, inj_dump, tw, config.SBFI.analyzer.mode, config.SBFI.analyzer.max_time_violation)
                for k, v in output_match_res.items():
                    InjDesc.DomainMatch[k] = 'V' if v[0] == 0 else 'X'
                if not tmr_match:
                    InjDesc.FailureMode = 'C'
                    first_mismatch = min(v[1] for k, v in output_match_res.items() if v[1] is not None)
                    InjDesc.FaultToFailureLatency = first_mismatch - basetime - float(InjDesc.InjectionTime)
                elif sum(i == 'V' for i in InjDesc.DomainMatch.values()) < 3:
                    InjDesc.FailureMode = 'L'  # Latent fault
                else:
                    InjDesc.FailureMode = 'M'  # Masked fault



        # rename dumpfile to string of unique index {InjDesc.ID}.lst
        InjDesc.Dumpfile = '{0:010d}.lst'.format(InjDesc.ID)
        src = os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, item.dumpfile))
        dst = os.path.normpath(os.path.join(conf.work_dir, 'irespack', InjDesc.Dumpfile))
        if os.path.exists(src): shutil.copy(src, dst)
        datamodel.LaunchedInjExp_dict[InjDesc.ID] = InjDesc
        ExpDescIdCnt += 1


def process_dumps(config, toolconf, conf, datamodel):
    timestart = datetime.datetime.now().replace(microsecond=0)
    os.chdir(conf.work_dir)
    packdir = os.path.join(conf.work_dir, 'irespack')
    if os.path.exists(packdir): shutil.rmtree(packdir)
    os.mkdir(packdir)
    shutil.copy(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)), os.path.normpath(os.path.join(packdir, toolconf.reference_file)))
    datamodel.reference.reference_dump = simDump()
    datamodel.reference.reference_dump.build_labels_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.list_init_file)), config.SBFI.analyzer.rename_list)
    datamodel.reference.reference_dump.normalize_array_labels(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
    datamodel.reference.reference_dump.build_vectors_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
    datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels = datamodel.reference.reference_dump.get_labels_copy()
    datamodel.reference.JnGrLst = config.SBFI.analyzer.join_group_list.copy()
    datamodel.reference.reference_dump.join_output_columns(datamodel.reference.JnGrLst.copy())
    desctable = ExpDescTable(conf.label)
    desctable.build_from_csv_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.exp_desc_file)), "Other")


    print('Processing simulation traces')
    progress = 0
    for i in desctable.items:
        target = datamodel.GetOrAppendTarget(i.target, i.instance_type, i.injection_case)
        progress += 1
        if progress % 100 == 0:
            sys.stdout.write('Targets appended: {0:06d}\r'.format(progress))

    # Prepare multithreaded analysis of dumps
    threadnum = config.SBFI.analyzer.threads
    ExpDescIdCnt = datamodel.GetMaxKey(DataDescriptors.InjectionExp) + 1
    threadlist = []
    step = (len(desctable.items) / threadnum) + 1
    index = 0
    while index < len(desctable.items):
        if index + step <= len(desctable.items):
            items = desctable.items[index:index + step]
        else:
            items = desctable.items[index:]
        baseindex = ExpDescIdCnt + index
        print('Starting analysis thread: {0} + {1}'.format(str(baseindex), str(len(items))))
        t = Thread(target=process_dumps_in_linst, args=(config, toolconf, conf, datamodel, items, baseindex))
        threadlist.append(t)
        index += step
    for t in threadlist:
        t.start()
    for t in threadlist:
        t.join()

    datamodel.SaveTargets()
    datamodel.SaveInjections()

    injsummary = datamodel.LaunchedInjExp_dict.values()
    domains = sorted(injsummary[0].DomainMatch.keys())

    T = Table('SummaryFaultSim', ['Node', 'InjCase', 'InjTime', 'Duration', 'FailureMode'] + domains)

    for i in range(len(injsummary)):
        T.add_row()
        T.put(i, T.labels.index('Node'), injsummary[i].Node)
        T.put(i, T.labels.index('InjCase'), injsummary[i].InjCase)
        T.put(i, T.labels.index('InjTime'), injsummary[i].InjectionTime)
        T.put(i, T.labels.index('Duration'), injsummary[i].InjectionDuration)
        T.put(i, T.labels.index('FailureMode'), injsummary[i].FailureMode)
        for k in domains:
            T.put(i, T.labels.index(k), injsummary[i].DomainMatch[k])

    with open(os.path.join(config.report_dir, 'Summary_{0}_{1}.csv'.format(config.experiment_label, conf.label)), 'w') as f:
        f.write(T.to_csv())
    datamodel.LaunchedInjExp_dict.clear()

    dumppack = "RESPACK_{0}.zip".format(conf.label)
    os.chdir(conf.work_dir)
    zip_folder(packdir, os.path.join(config.report_dir, dumppack))
    zip_folder(toolconf.code_dir, os.path.join(config.report_dir, dumppack))
    shutil.rmtree(packdir)

    domain_stats = {}
    valid_exp = sum(i.Status == 'S' for i in injsummary)
    failures = sum(i.FailureMode == 'C' for i in injsummary)
    for i in range(len(injsummary)):
        for k in domains:
            if k not in domain_stats:
                domain_stats[k] = 0
            if injsummary[i].DomainMatch[k] == 'X':
                domain_stats[k] += 1
    with open(os.path.join(config.report_dir, 'Statistics.log'), 'a') as f:
        f.write('\n{0:30s}: Failures: {1:5d}/{2:5d}: {3}'.format(conf.label,
                                                                 failures, valid_exp,
                                                                 '; '.join(['{0:10s}:{1:5d}'.format(k, domain_stats[k]) for k in sorted(domain_stats.keys())])))

    print('\n\nAnalysys completed, time taken: ' + str(time_to_seconds(datetime.datetime.now().replace(microsecond=0) - timestart)))
