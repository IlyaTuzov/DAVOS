# Initialization module requried to set-up the fault injection experiments
# 1. Extracts the fault injection taregets from the set of input models
#    according to fault dictionary and parameters from <Initializatio> tag of config.xml
# 2. Accomplished Model Matching, both Implementation-to-Implementation and Implementation-to-RTL
# 3. Configures the post-injection observation process
#    Exports following files: 
#       1. Simulation nodes with/without matching (XML formatted)
#       2. Script to set-up the observation process (observation targets: existing or virtually reconstructed signals)
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

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

def InitializeHDLModels(config, toolconf):   
    timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S')

    #Append Sampling/finish flag if not present
    if config.genconf.finish_flag == '' and config.injector.compile_project:
        sampl = toolconf.finish_flag.split('/')
        for c in config.parconf:
            with open(os.path.join(c.work_dir, '_fit_sampling.vhd'), 'w') as f:
                f.write('entity ' + sampl[0] + ' is\nend ' + sampl[0] + ';\narchitecture rtl of ' + sampl[0] + ' is\n\tsignal ' + sampl[1] + ' : bit := \'0\';\nbegin\nend rtl;\n')
        with open(os.path.normpath(os.path.join(config.call_dir, config.parconf[0].work_dir, config.genconf.compile_script)), 'r+') as f:
            c= f.read()
            if c.find('_fit_sampling.vhd') < 0:
                f.seek(0)
                f.write(c +'\nvcom -work work ./_fit_sampling.vhd\n')
        with open(os.path.normpath(os.path.join(config.call_dir, config.parconf[0].work_dir, config.genconf.run_script)), 'r+') as f:
            c= f.read()
            if c.find('work.sampling') < 0:
                f.seek(0)
                f.write(c.replace('\n',' ').replace('\r', ' ') + ' work.sampling\n')

    injection_unit_paths   = []
    observation_unit_paths = []
    for c in config.initializer.injection_scopes:
        if not c.unit_path in injection_unit_paths:
            injection_unit_paths.append(c.unit_path)
    for c in config.initializer.observation_scopes:
        if not c.unit_path in observation_unit_paths:
            observation_unit_paths.append(c.unit_path)


    f_inj_instances = toolconf.code_dir + '/inj_instances_log.txt'
    f_observ_instances = toolconf.code_dir + '/obs_instances_log.txt'
    f_observ_outputs = toolconf.code_dir + '/obs_outputs_log.txt'

    #Fault Models Description
    fault_dict = FaultDict(config.genconf.library_specification)
    reg_reconstruct_macrocells = RegisterReconstructionDict(ET.parse(config.genconf.library_specification).getroot().findall('register_reconstruction')[0])
    reg_reconstruct_macrocell_names = reg_reconstruct_macrocells.get_macrocells_names()

    if config.genconf.design_type == 'netlist':
        prim_list = fault_dict.get_prim_list()
        #Observable macrocells
        observable_macrocells = ObservableMacrocellDict(ET.parse(config.genconf.library_specification).getroot().findall('observation_spec')[0])
        observable_macrocell_names = observable_macrocells.get_macrocells_names()
        nodename_regexp = re.compile('(.+)\s\S')
        nodetype_regexp = re.compile('\((.+)\)')
    elif config.genconf.design_type == 'rtl':
        prim_list = ['signal']
        observable_macrocell_names = ['signal']
        nodename_regexp = re.compile('\{(.+)\}')


    inj_match_nodelist=None
    if config.initializer.match_pattern_file != '':
            nmp_tree = ET.parse(config.initializer.match_pattern_file).getroot()
            nmp_nodes = ConfigNodes('generic', nmp_tree)
            inj_match_nodelist = nmp_nodes.get_all_by_typelist(reg_reconstruct_macrocell_names)
            for i in inj_match_nodelist:
                i.ptn = i.name.replace(config.initializer.trim_path,'').replace('\\','').replace('[','(').replace(']',')').replace(' ','').replace('.','/')
                i.ptn = i.ptn.replace('_reg(','(')
                if i.ptn.endswith('_rep'):
                    i.ptn = i.ptn[:-4]
                if i.ptn.endswith('_reg'):
                    i.ptn = i.ptn[:-4]
                i.ptn = re.sub('_rep__[0-9]+', '', i.ptn)



    #2.  Build lists of injection nodes
    if config.initializer.build_injection_list:
        configs_inj_targets = []
        ent_types = set()
        for c in config.parconf:
            cdata = ConfigInitNodes(c.label)
            cdata.export_folder = c.work_dir
            configs_inj_targets.append(cdata)
            os.chdir(c.work_dir)
            create_folder(c.work_dir, toolconf.code_dir)
            #Compile the design
            if config.injector.compile_project:
                print('\n\tCOMPILING: ' + c.label)
                compile_script = "vsim -c -do \"do " + config.genconf.compile_script + " " + c.compile_options + " ;quit\" > compile_log.txt"
                proc = subprocess.Popen(compile_script, shell=True)
                print "RUN: " + compile_script
                proc.wait()
            #2.1. extract all entities from the design tree for each injection scope
            for i in injection_unit_paths:
                print('\n\t'+c.label+': Parsing Injection Scope: ' + i)
                with open('parsescript.do','w') as parse_script_file:
                    if config.genconf.design_type == 'netlist':
                        parse_script_file.write("do " + config.genconf.run_script + " " + c.run_options + "\nfind instances -file " + f_inj_instances + " -recursive " + i + "/* \nquit\n")
                    elif config.genconf.design_type == 'rtl':
                        shutil.copyfile(os.path.join(config.call_dir, toolconf.support_script_dir, toolconf.rtl_parse_script), os.path.join(c.work_dir, toolconf.rtl_parse_script))
                        parse_script_file.write("do " + config.genconf.run_script + " " + c.run_options + "\ndo " + toolconf.rtl_parse_script + " " + i + "/* " + f_inj_instances + " on -internal" + "\nquit\n")
                runscript = "vsim -c -do \"do parsescript.do\" > parse_log.txt"
                print "RUN: " + runscript
                proc = subprocess.Popen(runscript, shell=True)
                proc.wait()
                with open(os.path.join(c.work_dir, f_inj_instances),'r') as f:
                    content = f.readlines()
                print 'Appending nodes'
                for scope in config.initializer.injection_scopes:
                    if(scope.unit_path == i):
                        for s in content:
                            #s = s.replace('[','(').replace(']',')')
                            x = DesignNode()
                            #wl = s.split(' ')
                            if config.genconf.design_type == 'netlist':
                                wt = re.findall('(.*)\s\((.*?)\)$', s)
                                if len(wt) > 0:
                                    x.type = wt[0][-1].lower()
                                    x.name = wt[0][0]
                                    #x.name = re.findall(nodename_regexp, s)[0]                             
                                else: #string does not match the pattern for netlist
                                    continue
                            elif config.genconf.design_type == 'rtl':
                                x.name = re.findall(nodename_regexp, s)[0]
                                x.type = 'signal'
                            full_path = x.name.split('/')
                            x.name = full_path[-1]
                            x.unit_path = '/'.join(full_path[:-1])
                            if not x.unit_path.endswith('/'):  x.unit_path+='/'
                            if((x.name.startswith(scope.node_prefix) or scope.node_prefix=='') and (x.type in prim_list)):
                                if(cdata.find_node_by_type_and_name_and_unit(x.type,x.name,x.unit_path) == None):
                                    x.group = scope.unit_path
                                    cdata.all_nodes.append(x)
                                    ent_types.add(x.type)



        #2.2. Find common targets (firm matching: key = type & name & path)
        common_inj_nodes = ConfigInitNodes('COMMON')
        cnt = 0
        print('Phase 2: matching nodes\n\n')
        bufnodelist = configs_inj_targets[0].all_nodes[:]
        clen = len(configs_inj_targets[0].all_nodes)
        if len(configs_inj_targets) > 1:
            for x in bufnodelist:
                sys.stdout.write('matching node [%5d of %5d]\r' % (cnt, clen))
                sys.stdout.flush() 
                cnt += 1
                match = True
                for ct in configs_inj_targets:
                    if(ct.find_node_by_type_and_name_and_unit(x.type, x.name, x.unit_path) == None):
                        match = False
                        break
                if(match == True):
                    common_inj_nodes.all_nodes.append(x)
                    for ct in configs_inj_targets:
                        ct.remove_selected()

        bufnodelist = configs_inj_targets[0].all_nodes[:]
        #Soft matching just for registers: any FF type, 
        #name suffix is masked by regex to select groups with backward register balancing 'reg_a_0 == reg_a_0_BRB2'
        if (len(configs_inj_targets) > 1) and (config.genconf.design_type == 'netlist'):
            for x in bufnodelist:
                if(x.type in reg_reconstruct_macrocell_names):
                    mask_suffix = '_BRB[0-9]+'
                    skey = re.sub(mask_suffix, '', x.name)
                    match = True
                    for ct in configs_inj_targets:
                        if(ct.select_pseudo_common_items(reg_reconstruct_macrocell_names, skey, x.unit_path, mask_suffix) == []):
                            match = False
                            break
                    if(match == True):
                        for ct in configs_inj_targets:
                            for i in ct.selected:
                                ct.pseudo_common_nodes.append(i)
                            ct.remove_selected()
        #the rest of targets are specific (neither common nor pseudo-common)
        for ct in configs_inj_targets:
            ct.specific_nodes = ct.all_nodes


        print('\n\nCommon items')
        for ent in ent_types:
            print('\tof type [' + ent + '] : ' +str(len(common_inj_nodes.get_nodes_by_type(common_inj_nodes.all_nodes, ent))))
        #2.3. Find specific nodes, put them to common_nodes[i].specific_nodes
        for ct in configs_inj_targets:
            print('\nConfig [' + ct.config_label + '] Pseudo-common nodes:')
            for ent in ent_types:
                print('\tof type [' + ent + '] : ' +str(len(ct.get_nodes_by_type(ct.pseudo_common_nodes, ent))))
            print('\nConfig [' + ct.config_label + '] Specific nodes:')
            for ent in ent_types:
                print('\tof type [' + ent + '] : ' +str(len(ct.get_nodes_by_type(ct.specific_nodes, ent))))


        #2.3.2. Export implementation details
        ent_type_list = list(ent_types)
        IMPL_TABLE = Table('Implementations')
        IMPL_TABLE.add_column('IMPL_LABEL')
        for ent_i in range(0, len(ent_type_list), 1):
            IMPL_TABLE.add_column(ent_type_list[ent_i])
        for ct in configs_inj_targets:
            IMPL_TABLE.add_row()
            IMPL_TABLE.put_to_last_row(0,ct.config_label)
            for ent_i in range(0, len(ent_type_list), 1):
                IMPL_TABLE.put_to_last_row(ent_i+1, str(len(ct.get_nodes_by_type(ct.specific_nodes, ent_type_list[ent_i])) + len(ct.get_nodes_by_type(ct.pseudo_common_nodes, ent_type_list[ent_i]))+ len(common_inj_nodes.get_nodes_by_type(common_inj_nodes.all_nodes, ent_type_list[ent_i])) ) )
        with open(os.path.join(config.call_dir, config.parconf[0].work_dir, 'Impl_summary.csv'),'w') as impl_summary:
            impl_summary.write(IMPL_TABLE.to_csv())

        #2.4. Sort by prim type
        common_inj_nodes.all_nodes.sort(key = lambda x: x.type)
        for ct in configs_inj_targets:
            ct.specific_nodes.sort(key = lambda x: x.type)


        all_inj_nodes = common_inj_nodes.all_nodes + ct.pseudo_common_nodes + ct.specific_nodes
        #2.5. Export SimNodes.xml
        for ct in configs_inj_targets: 
            node_file = open(os.path.join(ct.export_folder, toolconf.injnode_list),'w')
            node_file.write('<!-- Fault injection Targets, generated by ' + sys.argv[0] + ' at '+ timestamp +'-->')
            if(inj_match_nodelist != None):
                inj_nodes, matched_regs = ct.match_to_xml(inj_match_nodelist)
                node_file.write('\n\n<data>\n' + inj_nodes  +'\n</data>')
            else:
                node_file.write('\n\n<data>\n' + common_inj_nodes.all_nodes_to_xml() + '\n' + ct.pseudo_common_nodes_to_xml() + '\n' + ct.specific_nodes_to_xml() +'\n</data>')            
            node_file.close()



    #3. Build dump initialization scripts (observation lists)
    if config.initializer.build_dump_init_script:
        #3.1. Generic observation nodes
        GenericInternalObservationContent = "\n"
        GenericExternalObservationContent = "\n"
        if config.genconf.finish_flag == '':
            GenericInternalObservationContent += '\n#Sampling (finish) flag\n\tadd list -label FinishFlag Sampling/FinishFlag'
        else:
            GenericInternalObservationContent += '\n#Sampling (finish) flag\n\tadd list -label {0} {1}'.format(config.genconf.finish_flag, config.genconf.finish_flag)
        # signal
        for c in config.initializer.generic_observation_nodes.signals:
            content = "\n# " + c.comment
            content += "\n\tadd list " + c.options + " -label " + c.label + " {" + c.path + "}"
            if(c.location == 'OUTPUTS'):
                GenericExternalObservationContent += content
            else:
                GenericInternalObservationContent += content
        # virtual_signal
        for c in config.initializer.generic_observation_nodes.virtual_signals:
            if not c.env.endswith('/'):  c.env+='/'
            content = "\n# " + c.comment
            content += "\n\tquietly virtual signal -env " + c.env + " -install " + c.env + " " + c.expression + " " + c.label
            content += "\n\tadd list " + c.options + " -label " + c.label + " " + c.env + c.label
            if(c.location == 'OUTPUTS'):
                GenericExternalObservationContent += content
            else:
                GenericInternalObservationContent += content
        # memarray
        for c in config.initializer.generic_observation_nodes.memarrays:
            mcontent = "\n# " + c.comment
            for address in range(c.low_address, c.high_address+1, 1):
                mcontent += "\n\tadd list " + c.options + " -label " + c.label + "(" + str(address) + ") {" + c.path + "(" + str(address) + ")}"
            if(c.location == 'OUTPUTS'):
                GenericExternalObservationContent += mcontent
            else:
                GenericInternalObservationContent += mcontent

        #3.2. Design specific observation nodes
        ent_types = set()
        for c in config.parconf:
            SimInitContent = "# Observation targets list\n# Generated by: " + sys.argv[0]+"\n# " + timestamp + "\n\n"+  'view list\nradix hex\n' + '#<INTERNALS>\n' + GenericInternalObservationContent 
            if not TraceListOnlyForMatchedNodes:
                ent_paths = set()                
                cdata = ConfigInitNodes(c.label)
                cdata.export_folder = c.work_dir
                os.chdir(c.work_dir)
                #design has been previously compiled
                #extract all entities from the design tree for each observation scope
                for i in observation_unit_paths:
                    print('\n\t'+c.label+': Parsing Observation Scope: ' + i)
                    parse_script_file = open('parsescript.do','w')
                    if config.genconf.design_type == 'netlist':
                        parse_script_file.write("do " + config.genconf.run_script + " " + c.run_options + "\nfind instances -file " + f_observ_instances + " -recursive " + i + "/*" + "\nfind signals -out -inout -file " + f_observ_outputs + " " + i + "/*" + " \nquit\n")
                    elif config.genconf.design_type == 'rtl':
                        shutil.copyfile(os.path.join(config.call_dir, toolconf.support_script_dir, toolconf.rtl_parse_script), os.path.join(c.work_dir, toolconf.rtl_parse_script))
                        parse_script_file.write("do " + config.genconf.run_script + " " + c.run_options + "\ndo " + toolconf.rtl_parse_script + " " + i + "/* " + f_observ_instances + " on -internal" + "\nquit\n")
                    parse_script_file.close()
                    runscript = "vsim -c -do \"do parsescript.do\" > parse_log.txt"
                    print "RUN: " + runscript
                    proc = subprocess.Popen(runscript, shell=True)
                    proc.wait()
                    with open(os.path.join(c.work_dir, f_observ_instances),'r') as f:
                        content = f.readlines()
                    for scope in config.initializer.observation_scopes:
                        if(scope.unit_path == i):
                            for s in content:
                                #s = s.replace('[','(').replace(']',')')
                                x = DesignNode()
                                #wl = s.split(' ')
                                if config.genconf.design_type == 'netlist':
                                    wt = re.findall('(.*)\s\((.*?)\)$', s)
                                    if len(wt) > 0:
                                        x.type = wt[0][-1].lower()
                                        x.name = wt[0][0]
                                    else: #string does not match the pattern for netlist
                                        continue
                                elif config.genconf.design_type == 'rtl':
                                    x.name = re.findall(nodename_regexp, s)[0]
                                    if(x.name.endswith(')')): x.name = re.findall('(.*)\([0-9]+\)$',x.name)[0]
                                    if(x.name.endswith(']')): x.name = re.findall('(.*)\[[0-9]+\]$',x.name)[0]
                                    x.type = 'signal'
                                #x = DesignNode()
                                #x.name = re.findall(nodename_regexp, s)[0]
                                #if(genconf.design_type == 'netlist'):
                                #    x.type = re.findall(nodetype_regexp, s)[0].lower()
                                #elif(genconf.design_type == 'rtl'):
                                #    if(x.name.endswith(')')): x.name = re.findall('(.*)\([0-9]+\)$',x.name)[0]
                                #    x.type = 'signal'
                                full_path = x.name.split('/')
                                x.name = full_path[-1]
                                x.unit_path = '/'.join(full_path[:-1])
                                if not x.unit_path.endswith('/'):  x.unit_path+='/'
                                if((x.name.startswith(scope.node_prefix) or scope.node_prefix=='') and (x.type in observable_macrocell_names)):
                                    x.node_prefix = scope.node_prefix
                                    if(cdata.find_node_by_type_and_name_and_unit(x.type,x.name,x.unit_path) == None):
                                        cdata.all_nodes.append(x)
                                        ent_types.add(x.type)
                                        ent_paths.add(x.unit_path)
                unit_path_list = list(ent_paths)
                unit_path_list = sorted(unit_path_list)
                #For NETLIST append real registers and those reconstructed from FFs
                if config.genconf.design_type == 'netlist':
                    reg_reconstruct_nodes = []
                    rst_observation_nodes = []
                    if config.initializer.virtual_register_reconstruction:
                        #Split cdata.all_nodes in 2 arrays:  nodes used for register reconstruction  and the rest of them
                        for i in cdata.all_nodes:
                            if i.type in reg_reconstruct_macrocell_names:
                                reg_reconstruct_nodes.append(i)
                            else:
                                rst_observation_nodes.append(i)
                    else:
                        rst_observation_nodes = cdata.all_nodes
                    #rst_observation_nodes.sort(key = lambda x: x.name)
                    for scope in config.initializer.observation_scopes:
                        for p in unit_path_list:
                            if p.startswith(scope.unit_path):
                                subpath_prefix = p[len(scope.unit_path):].replace('/','_')
                                #Append real registers 
                                Registers_Init_Content = "\n\n# Registers in scope: " + p + ', path_prefix: ' + subpath_prefix + ', item_prefix: ' + scope.node_prefix
                                Registers_Init_Content += "\nenv {" + p + "}"
                                for x in rst_observation_nodes:
                                    if p == x.unit_path and x.name.startswith(scope.node_prefix):
                                        for port in observable_macrocells.get_macrocell_ports(x.type):
                                            if(scope.node_prefix!=''):
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + x.name.replace(scope.node_prefix, scope.label_prefix) + "_"+ port + "} {" + x.name + "/" + port + "}"
                                            else:
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + x.name + "_"+ port + "} {" + x.name + "/" + port + "}"
                                #Build and Append Virtual registers
                                if config.initializer.virtual_register_reconstruction:
                                    reglist = RegisterList()
                                    fflist = []
                                    for x in reg_reconstruct_nodes:
                                        if(x.node_prefix == scope.node_prefix and x.unit_path == p):
                                            fflist.append(x)
                                    fflist.sort(key = lambda x: x.name)
                                    for item in fflist:
                                        index_m = re.findall("_[0-9]+$", item.name)
                                        index_brb = re.findall("BRB([0-9]+)$", item.name)
                                        if(index_m != []):
                                            index = index_m[0].replace("_","")
                                            name = rreplace(item.name, index_m[0], '',1)
                                            creg = reglist.find(name) 
                                            if(creg != None):
                                                creg.indexes.append(IndexTypeTuple(int(index), item.type))
                                            else:
                                                creg = Register(name)
                                                creg.index_separator = '_'
                                                creg.indexes.append(IndexTypeTuple(int(index), item.type))
                                                reglist.add(creg)
                                        elif(index_brb != []):
                                            name = rreplace(item.name, index_brb[0], '',1)
                                            creg = reglist.find(name) 
                                            if(creg != None):
                                                creg.indexes.append(IndexTypeTuple(int(index_brb[0]), item.type))
                                            else:
                                                creg = Register(name)
                                                creg.index_separator = ''
                                                creg.indexes.append(IndexTypeTuple(int(index_brb[0]), item.type))
                                                reglist.add(creg)
                                        else:
                                            creg = Register(item.name)
                                            creg.single_bit_type =  item.type
                                            reglist.add(creg)
                                    reglist.sort()
                                    #Build virtual signals
                                    for i in reglist.items:
                                        (bus_def, bus_name) = i.virtual_bus(reg_reconstruct_macrocells, 0, i.index_separator, scope.unit_path)
                                        if(bus_def == ""):
                                            port = reg_reconstruct_macrocells.get_macrocell_port(i.single_bit_type)
                                            if(scope.node_prefix!=''):
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + i.name.replace(scope.node_prefix, scope.label_prefix) + "_"+ port + "} {" + i.name + "/" + port + "}"
                                            else:
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + i.name + "_"+ port + "} {" + i.name + "/" + port + "}"
                                        else:
                                            Registers_Init_Content += "\n" + bus_def
                                            if(scope.node_prefix!=''):
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + bus_name.replace(scope.node_prefix, scope.label_prefix) + "} {" + bus_name + "}"
                                            else:
                                                Registers_Init_Content += "\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + bus_name + "} {" + bus_name + "}"
                                SimInitContent += '\n' + Registers_Init_Content
                #For RTL append internal signals
                elif config.genconf.design_type == 'rtl':
                    for scope in config.initializer.observation_scopes:
                        for p in unit_path_list:
                            if p.startswith(scope.unit_path):
                                subpath_prefix = p[len(scope.unit_path):].replace('/','_')
                                #Append signals
                                SimInitContent += "\n\n# Signals in scope: " + p + ', path_prefix: ' + subpath_prefix + ', prefix: ' + scope.label_prefix
                                SimInitContent += "\nenv {"+ p +"}"
                                for x in cdata.all_nodes:
                                    if(x.unit_path == p):
                                        if(scope.node_prefix!=''):
                                            SimInitContent += ("\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + x.name.replace(scope.node_prefix, scope.label_prefix)  + "} {" + x.name + "}").replace('[','(').replace(']',')')
                                        else:
                                            SimInitContent += ("\n\tadd list " + scope.sampling_options  + " -label {" + subpath_prefix + x.name + "} {" + x.name + "}").replace('[','(').replace(']',')')
                                    
                #elif config.genconf.design_type == 'rtl' and inj_match_nodelist != None:
                #    for node in all_inj_nodes:
                #        for d in inj_match_nodelist:
                #            if remove_delimiters(d.name) == remove_delimiters(node.unit_path + node.name) :
                #                #SimInitContent += ("\nenv " + node.unit_path.replace('[','(').replace(']',')') + "\n\tadd list " + '-notrigger'  + " -label " + node.name + " " + node.unit_path + node.name).replace('[','(').replace(']',')')
                #                SimInitContent += ("\nenv {" + node.unit_path.replace('[','(').replace(']',')') + "}\n\tadd list " + '-notrigger'  + " -label {" + node.unit_path + node.name + "} {" + node.unit_path + node.name + "}").replace('[','(').replace(']',')')                        
                #                break
            elif matched_regs!=None :
                SimInitContent += "\n#matched registers\n" + "\n".join(["\tadd list -notrigger -label {0} {1}".format(x.unit_path+x.name, x.unit_path+x.name) for x in matched_regs])
            initmodel_file = open(os.path.join(c.work_dir, toolconf.list_init_file),'w')
            initmodel_file.write(SimInitContent + '\n#</INTERNALS>')
            initmodel_file.write('\n\n#<OUTPUTS>\n'   + GenericExternalObservationContent + '\n#</OUTPUTS>')
            initmodel_file.close()
    raw_input('Initialized... press any key to continue...')



