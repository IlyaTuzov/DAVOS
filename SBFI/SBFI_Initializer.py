# Initialization module requried to set-up the fault injection experiments
# 1. Extracts the fault injection taregets from the set of input models
#    according to fault dictionary and parameters from <Initializatio> tag of config.xml
# 2. Accomplished Model Matching, both Implementation-to-Implementation and Implementation-to-RTL
# 3. Configures the post-injection observation process
#    Exports following files: 
#       1. Simulation nodes with/without matching (XML formatted)
#       2. Script to set-up the observation process (observation targets: existing or virtually reconstructed signals)
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
from Davos_Generic import *
from Datamanager import *
import re

TraceListOnlyForMatchedNodes = False
arr_name_ptn = re.compile("(.*)\([0-9]+\)$")

def InitializeHDLModels(config, toolconf, c):
    timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S')
    injection_unit_paths = sorted(list(set([i.unit_path for i in config.SBFI.injection_scopes])))
    observation_unit_paths = sorted(list(set([i.unit_path for i in config.SBFI.observation_scopes])))
    f_inj_instances = '{0}/inj_instances_log.txt'.format(toolconf.code_dir)
    f_observ_instances = '{0}/obs_instances_log.txt'.format(toolconf.code_dir)
    f_observ_outputs = '{0}/obs_outputs_log.txt'.format(toolconf.code_dir)

    # Fault Models Description
    fault_dict = FaultDict(os.path.normpath(os.path.join(config.call_dir, config.SBFI.fault_dictionary)))
    reg_reconstruct_macrocells = RegisterReconstructionDict(
        ET.parse(os.path.join(config.call_dir, config.SBFI.fault_dictionary)).getroot().findall('register_reconstruction')[0])
    reg_reconstruct_macrocell_names = reg_reconstruct_macrocells.get_macrocells_names()


    cdata = ConfigInitNodes(c.label)
    cdata.export_folder = c.work_dir
    ent_types = set()
    os.chdir(c.work_dir)
    if c.design_type == 'netlist':
        prim_list = fault_dict.get_prim_list()
        # Observable macrocells
        observable_macrocells = ObservableMacrocellDict(
            ET.parse(os.path.join(config.call_dir, config.SBFI.fault_dictionary)).getroot().findall('observation_spec')[0])
        observable_macrocell_names = observable_macrocells.get_macrocells_names()
        nodename_regexp = re.compile('(.+)\s\S')
        nodetype_regexp = re.compile('\((.+)\)')
    elif c.design_type == 'rtl':
        prim_list = ['signal']
        observable_macrocell_names = ['signal']
        nodename_regexp = re.compile('\{(.+)\}')

    if os.path.exists(os.path.join(c.work_dir, toolconf.injnode_list)) and not config.SBFI.clean_run:
        print('{0}: Using existing list of fault targets'.format(c.label))
    else:
        # extract all entities from the design tree for each injection scope
        for i in config.SBFI.injection_scopes:
            print('\n\t{0} : Parsing Injection Scope: {1}'.format(c.label, i.unit_path))
            with open('parsescript.do', 'w') as parse_script_file:
                if c.design_type == 'netlist':
                    runscript = "vsim -c -restore {0} -do \"do find instances -file {1} -recursive {2}/{3} \nquit\n\" > parse_log.txt".format(c.checkpoint,
                                                                                                                                              f_inj_instances,
                                                                                                                                              i.unit_path,
                                                                                                                                              i.node_filter if i.node_filter != "" else "*", )
                elif c.design_type == 'rtl':
                    runscript = "vsim -c -restore {0} -do \"do {1} {2}/{3} {4} on on {5} \nquit\n\" > parse_log.txt".format(c.checkpoint,
                                                                                                                            os.path.join(config.call_dir, toolconf.support_script_dir, toolconf.rtl_parse_script),
                                                                                                                            i.unit_path,
                                                                                                                            i.node_filter if i.node_filter != "" else "*",
                                                                                                                            f_inj_instances,
                                                                                                                            i.scope_filter)
            proc = subprocess.Popen(runscript, shell=True)
            proc.wait()
            print 'Appending nodes'
            with open(os.path.join(c.work_dir, f_inj_instances), 'r') as f:
                for s in f.readlines():
                    x = DesignNode()
                    if c.design_type == 'netlist':
                        wt = re.findall('(.*)\s\((.*?)\)$', s)
                        if len(wt) > 0:
                            x.type = wt[0][-1].lower()
                            x.name = wt[0][0]
                        else:  # string does not match the pattern for netlist
                            continue
                    elif c.design_type == 'rtl':
                        x.name = re.findall(nodename_regexp, s)[0]
                        x.type = 'signal'
                    full_path = x.name.split('/')
                    x.name = full_path[-1]
                    x.unit_path = '/'.join(full_path[:-1])
                    if not x.unit_path.endswith('/'):  x.unit_path += '/'
                    if x.type in prim_list:
                        if cdata.find_node_by_type_and_name_and_unit(x.type, x.name, x.unit_path) == None:
                            x.group = i.unit_path
                            cdata.all_nodes.append(x)
                            ent_types.add(x.type)

        for ent in ent_types:
            print('\tNodes of type [{0}] : {1}'.format(ent, len(cdata.get_nodes_by_type(cdata.all_nodes, ent))))
        # Export implementation details
        ent_type_list = list(ent_types)
        IMPL_TABLE = Table('Implementations')
        IMPL_TABLE.add_column('IMPL_LABEL')
        for ent_i in range(0, len(ent_type_list), 1):
            IMPL_TABLE.add_column(ent_type_list[ent_i])
        IMPL_TABLE.add_row()
        IMPL_TABLE.put_to_last_row(0, cdata.config_label)
        for ent_i in range(0, len(ent_type_list), 1):
            IMPL_TABLE.put_to_last_row(ent_i + 1, str(len(cdata.get_nodes_by_type(cdata.all_nodes, ent_type_list[ent_i]))))
        with open(os.path.join(config.call_dir, c.work_dir, 'Impl_summary.csv'), 'w') as impl_summary:
            impl_summary.write(IMPL_TABLE.to_csv())
        cdata.all_nodes.sort(key=lambda x: x.type)
        # 2.5. Export SimNodes.xml
        with open(os.path.join(cdata.export_folder, toolconf.injnode_list), 'w') as node_file:
            node_file.write('<!-- Fault injection Targets, generated by ' + sys.argv[0] + ' at ' + timestamp + '-->')
            node_file.write('\n\n<data>\n' + cdata.all_nodes_to_xml() + '\n</data>')

# Build trace scripts (observation lists)
    if os.path.exists(os.path.join(c.work_dir, toolconf.list_init_file)) and not config.SBFI.clean_run:
        print('{0}: Using existing trace script'.format(c.label))
    else:
        ent_types = set()
        trace_items = {'internals': [], 'outputs': []}
        os.chdir(c.work_dir)
        node_set = set()
        for i in config.SBFI.observation_scopes:
            cdata = ConfigInitNodes(c.label)
            cdata.export_folder = c.work_dir
            print('\n\t{0} : Parsing Observation Scope: {1}'.format(c.label, i.unit_path))
            with open('parsescript.do', 'w') as parse_script_file:
                if c.design_type == 'netlist':
                    runscript = "vsim -c -restore {0} -do \"do find instances -file {1} -recursive {2}/{3} \nquit\n\" > parse_log.txt".format(c.checkpoint,
                                                                                                                                              f_observ_instances,
                                                                                                                                              i.unit_path,
                                                                                                                                              i.node_filter if i.node_filter != "" else "*", )
                elif c.design_type == 'rtl':
                    runscript = "vsim -c -restore {0} -do \"do {1} {2}/{3} {4} on on {5} \nquit\n\" > parse_log.txt".format(c.checkpoint,
                                                                                                                            os.path.join(config.call_dir, toolconf.support_script_dir, toolconf.rtl_parse_script),
                                                                                                                            i.unit_path,
                                                                                                                            i.node_filter if i.node_filter != "" else "*",
                                                                                                                            f_observ_instances,
                                                                                                                            i.scope_filter)
            proc = subprocess.Popen(runscript, shell=True)
            proc.wait()
            print 'Appending nodes'
            with open(os.path.join(c.work_dir, f_observ_instances), 'r') as f:
                for s in f.readlines():
                    x = DesignNode()
                    if c.design_type == 'netlist':
                        wt = re.findall('(.*)\s\((.*?)\)$', s)
                        if len(wt) > 0:
                            x.type = wt[0][-1].lower()
                            x.name = wt[0][0]
                        else:  # string does not match the pattern for netlist
                            continue
                    elif c.design_type == 'rtl':
                        x.name = re.findall(nodename_regexp, s)[0]
                        if x.name.endswith(')'): x.name = re.findall('(.*)\([0-9]+\)$', x.name)[0]
                        if x.name.endswith(']'): x.name = re.findall('(.*)\[[0-9]+\]$', x.name)[0]
                        x.type = 'signal'
                        full_path = x.name.split('/')
                        x.name = full_path[-1]
                        x.unit_path = '/'.join(full_path[:-1])
                        if not x.unit_path.endswith('/'):  x.unit_path += '/'
                        if x.type in observable_macrocell_names:
                            if cdata.find_node_by_type_and_name_and_unit(x.type, x.name, x.unit_path) is None:
                                cdata.all_nodes.append(x)
                                ent_types.add(x.type)

            trace = "\n\n# Signals in scope: {0}\nenv {0}\n".format(i.unit_path)
            if c.design_type == 'rtl':
                for x in cdata.all_nodes:
                    subpath_prefix = x.unit_path[len(i.unit_path):]
                    if subpath_prefix.startswith('/'): subpath_prefix = subpath_prefix[1:]
                    obs_item = ("add list {0} -label {{{1}}} {{{2}}}; #domain={{{3}}}".format(i.sampling_options, i.label_prefix + subpath_prefix.replace('/', '_') + x.name, subpath_prefix + x.name, i.domain)).replace('[', '(').replace(']', ')')
                    if obs_item not in node_set:
                        trace += '\n\t' + obs_item
                        node_set.add(obs_item)
            if i.group not in trace_items:
                trace_items[i.group] = []
            trace_items[i.group].append(trace)

        for i in config.SBFI.observation_items:
            if len(i.array_items) > 0:
                trace = '\n'.join(['add list {0} -label {{{1}[{2}]}} {{{3}[{4}]}}; #domain={{{5}}}'.format(i.sampling_options, i.label if i.label != "" else i.path, k, i.path, k, i.domain) for k in i.array_items])
            else:
                trace = "\nadd list {0} -label {{{1}}} {{{2}}}; #domain={{{3}}}".format(i.sampling_options, i.label if i.label != "" else i.path, i.path, i.domain)
            if i.group not in trace_items:
                trace_items[i.group] = []
            trace_items[i.group].append(trace)

        with open(os.path.join(c.work_dir, toolconf.list_init_file), 'w') as f:
            f.write("# Observation targets list\n# Generated by: {0}\n# {1}\n\nview list\nradix hex".format(sys.argv[0], timestamp))
            for group in sorted(trace_items.keys()):
                f.write('\n\n#<{0}>\n{1}\n#</{0}>'.format(group.upper(), '\n'.join(trace_items[group])))
            f.close()

