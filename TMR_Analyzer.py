# Multithreaded analysis of fault injection results for redundant designs
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


target_filter = ''

# Script entry point when launched directly
if __name__ == "__main__":
    sys.stdin = open('/dev/tty')
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
        inj_descriptors = [x for x in datamodel.LaunchedInjExp_dict.values() if x.ModelID == model.ID]
        os.chdir(conf.work_dir)
        with ZF.ZipFile("RESPACK_{0}.zip".format(model.Label), 'r') as zp:
            zp.extractall(conf.work_dir)

        print('Processing simulation traces: {0}'.format(conf.label))
        datamodel.reference.reference_dump = simDump()
        datamodel.reference.reference_dump.build_labels_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.list_init_file)), config.SBFI.analyzer.rename_list)
        datamodel.reference.reference_dump.normalize_array_labels(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
        datamodel.reference.reference_dump.build_vectors_from_file(os.path.normpath(os.path.join(conf.work_dir, toolconf.result_dir, toolconf.reference_file)))
        datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels = datamodel.reference.reference_dump.get_labels_copy()
        datamodel.reference.JnGrLst = config.SBFI.analyzer.join_group_list.copy()
        datamodel.reference.reference_dump.join_output_columns(datamodel.reference.JnGrLst.copy())

        tw = config.SBFI.analyzer.time_window if config.SBFI.analyzer.time_window is not None else (datamodel.reference.reference_dump.vectors[0].time, datamodel.reference.reference_dump.vectors[-1].time)

        domains = ['Core0', 'Core1', 'Core2']
        T = Table('SummaryFaultSim', ['Node', 'InjTime', 'Duration', 'FailureMode'] + domains)
        row_cnt = 0
        valid_exp, failures, c1_failures, c2_failures, c3_failures = 0, 0, 0, 0, 0
        for InjDesc in inj_descriptors:
            stat_flag = (target_filter in target_dict[InjDesc.TargetID].NodeFullPath) or target_filter == ''
            InjDesc.DomainMatch = {}
            for k in domains:
                InjDesc.DomainMatch[k] = '-'
            inj_dump = simDump()
            inj_dump.set_labels_copy(datamodel.reference.initial_internal_labels, datamodel.reference.initial_output_labels)
            if inj_dump.build_vectors_from_file(os.path.join(conf.work_dir, toolconf.result_dir, InjDesc.Dumpfile)) == None:
                InjDesc.Status = 'E'  # error
            else:
                try:
                    T.add_row()
                    T.put(row_cnt, T.labels.index('Node'), datamodel.Target_lst[InjDesc.TargetID].NodeFullPath)
                    T.put(row_cnt, T.labels.index('InjTime'), InjDesc.InjectionTime)
                    T.put(row_cnt, T.labels.index('Duration'), InjDesc.InjectionDuration)

                    InjDesc.Status = 'S'  # Simulation successful and dumpfile exists
                    ref_v = datamodel.reference.reference_dump.vectors[-1]
                    inj_v = inj_dump.vectors[-1]
                    indices_1, indices_2, indices_3 = datamodel.reference.reference_dump.domain_indices[domains[0]], datamodel.reference.reference_dump.domain_indices[domains[1]], datamodel.reference.reference_dump.domain_indices[domains[2]]
                    m1, m2, m3, tmr = 0, 0, 0, 0
                    for i in range(len(indices_1)):
                        v1, v2, v3 = inj_v.outputs[indices_1[i]], inj_v.outputs[indices_2[i]], inj_v.outputs[indices_3[i]]
                        h1, h2, h3 = int(v1, 16), int(v2, 16), int(v3, 16)
                        if h1 != int(ref_v.outputs[indices_1[i]], 16):
                            m1 += 1
                        if h2 != int(ref_v.outputs[indices_2[i]], 16):
                            m2 += 1
                        if h3 != int(ref_v.outputs[indices_3[i]], 16):
                            m3 += 1
                        voted = (h1 & h2) | (h1 & h3) | (h2 & h3)
                        if voted != int(ref_v.outputs[indices_1[i]], 16):
                            tmr += 1
                    if tmr > 0:
                        InjDesc.FailureMode = 'C'
                    elif m1 > 0 or m2 > 0 or m3 > 0:
                        InjDesc.FailureMode = 'L'
                    else:
                        InjDesc.FailureMode = 'M'

                    InjDesc.DomainMatch['Core0'] = 'V' if m1 == 0 else 'X'
                    InjDesc.DomainMatch['Core1'] = 'V' if m2 == 0 else 'X'
                    InjDesc.DomainMatch['Core2'] = 'V' if m3 == 0 else 'X'
                    if stat_flag:
                        valid_exp += 1
                        if m1 > 0: c1_failures += 1
                        if m2 > 0: c2_failures += 1
                        if m3 > 0: c3_failures += 1
                        if tmr > 0: failures += 1

                    T.put(row_cnt, T.labels.index('FailureMode'), InjDesc.FailureMode)
                    for k in domains:
                        T.put(row_cnt, T.labels.index(k), InjDesc.DomainMatch[k])
                    row_cnt += 1
                except Exception as e:
                    T.put(row_cnt, T.labels.index('FailureMode'), 'EXC')
                    for k in domains:
                        T.put(row_cnt, T.labels.index(k), 'EXC')
                    row_cnt += 1
                    continue


        with open(os.path.join(config.report_dir, 'Summary_{0}_{1}.csv'.format(config.experiment_label, conf.label)), 'w') as f:
            f.write(T.to_csv())

        with open(os.path.join(config.report_dir, 'Statistics.log'), 'a') as f:
            f.write('\n{0:30s}: Failures: {1:5d}/{2:5d}: {3} : {4} : {5}'.format(conf.label,
                                                                     failures, valid_exp,
                                                                     c1_failures, c2_failures, c3_failures))

        for d in [toolconf.result_dir, toolconf.code_dir]:
            if os.path.exists(os.path.join(conf.work_dir, d)):
                shutil.rmtree(os.path.join(conf.work_dir, d))



