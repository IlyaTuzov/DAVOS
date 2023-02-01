# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Defines a data model for configuring DAVOS toolkit (project configuration)
#       Hierarchical data structure is obtained by parsing an input XML file
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
import sqlite3
import copy
import threading
import ast
from Davos_Generic import *
__metaclass__ = type

#-------------------------------------------------------------#
#1. Configuration Data Model with embedded XML deserializers
#1.0 SBFI Tool configuration
#-------------------------------------------------------------#
class ToolOptions:
    def __init__(self, xnode=None):
        self.support_script_dir = './SupportScripts'
        if xnode is None:
            self.script_dir = "./iscripts"
            self.checkpoint_dir = "./icheckpoints"
            self.result_dir = "./iresults"
            self.log_dir = "./ilogs"
            self.dataset_dir = "./idatasets"
            self.code_dir = "./code"
            self.injnode_list = "./code/SimNodes.xml"
            self.list_init_file = "./code/simInitModel.do"
            self.par_lib_path = "./code/ISE_PAR"
            self.reference_file = "reference.lst"
            self.std_start_checkpoint = "startpoint.sim"
            self.archive_tool_script = "zip -r"
            self.rtl_parse_script = "modelsim_rtl_nodes.do"
            self.finish_flag = "Sampling/FinishFlag"
            self.exp_desc_file = "_summary.csv"
        else:
            self.build_from_xml(xnode)            
     
    def build_from_xml(self, xnode):
        self.script_dir = xnode.get('script_dir', "./iscripts")
        self.checkpoint_dir = xnode.get('checkpoint_dir', "./icheckpoints")
        self.result_dir = xnode.get('result_dir', "./iresults")
        self.log_dir = xnode.get('log_dir', "./ilogs")
        self.dataset_dir = xnode.get('dataset_dir', "./idatasets")
        self.code_dir = xnode.get('code_dir', "./code")
        self.injnode_list = xnode.get('injnode_list',"./code/SimNodes.xml")
        self.list_init_file = xnode.get('list_init_file', "./code/simInitModel.do")
        self.par_lib_path = xnode.get('par_lib_path',"./code/ISE_PAR")
        self.reference_file = xnode.get('reference_file', "reference.lst")
        self.std_start_checkpoint = xnode.get('std_start_checkpoint', "startpoint.sim")
        self.archive_tool_script = xnode.get('archive_tool_script', "zip -r")
        self.rtl_parse_script = xnode.get('rtl_parse_script', "dadse_rtl_nodes.do")
        self.finish_flag = xnode.get('finish_flag', "Sampling/FinishFlag")
        self.exp_desc_file = xnode.get('exp_desc_file', "_summary.csv")
        return(0)




 


# 1.2 Configuration parameters: used by initializer module 
class ObservationScope:
    def __init__(self, xnode):
        if xnode is None:
            self.node_filter = ""
            self.unit_path = ""
            self.label_prefix = ""
            self.sampling_options = ""
            self.scope_filter = ""
            self.group = ""
            self.domain = "Root"
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.unit_path = xnode.get('unit_path')
        self.node_filter = xnode.get('node_filter')
        self.label_prefix = xnode.get('label_prefix')
        self.sampling_options = xnode.get('sampling_options','')
        self.scope_filter = xnode.get('scope_filter', '')
        self.group = xnode.get('group', 'internals').lower()
        self.domain = xnode.get('domain', 'Root')


class InjectionScope:
    def __init__(self, xnode):
        if xnode is None:
            self.unit_path = ""
            self.node_filter = ""
            self.scope_filter = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.unit_path = xnode.get('unit_path')
        self.node_filter = xnode.get('node_filter', '')
        self.scope_filter = xnode.get('scope_filter', '')



class ModelItem(object):
    def __init__(self, xnode):
        if xnode is None:
            self.path = ""
            self.array_items = []
            self.group = ""
            self.options = ""
            self.label = ""
            self.type = ""
            self.sampling_options = ""
            self.domain = "Root"
        else:
            self.path = xnode.get('path', '')
            match_desc = re.search('([0-9]+):([0-9]+)', xnode.get('array_range', ''))
            self.array_items = [] if match_desc is None else range(int(match_desc.group(1)), int(match_desc.group(2))+1)
            self.group = xnode.get('group', 'internals').lower()
            self.options = xnode.get('options','')
            self.label = xnode.get('label','')
            self.type = xnode.get('type', 'SIGNAL')
            self.sampling_options = xnode.get('sampling_options', '')
            self.domain = xnode.get('domain', 'Root')







#1.3 Configuration parameters: used by injector (simulation) module
class TimeModes:
    ClockCycle, Relative, Absolute  = range(3)

class CheckpointModes:
    ColdRestore, WarmRestore = range(2)


class FaultModelConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.model = ""
            self.target_logic = []
            self.profiling = None
            self.experiments_per_target = int(0)
            self.multiplicity = int(0)
            self.time_mode = TimeModes.Relative
            self.time_start = float(0)
            self.time_end = float(0)
            self.increment_time_step = float(0)
            self.activity_time_start = float(0)
            self.activity_time_end = float(0)
            self.inactivity_time_start = float(0)
            self.inactivity_time_end = float(0)
            self.forced_value = ""
            self.rand_seed = int(0)
            self.sample_size = int(0)
            self.duration_min, self.duration_max = float(0), float(0)
            self.modifier = ''
            self.trigger_expression = ''
            self.simulataneous_faults = False
            self.CCF = None
        else:
            self.build_from_xml(xnode)
                 
    def build_from_xml(self, xnode):
        self.model = xnode.get('model')
        self.target_logic = re.findall('[a-zA-Z0-9_]+', xnode.get('target_logic').lower())
        self.profiling = xnode.get('profiling', '')
        self.experiments_per_target = int(xnode.get('experiments_per_target', '1'))
        self.multiplicity = int(xnode.get('multiplicity', '1'))
        if xnode.get('time_mode', '').lower() == 'clockcycle': self.time_mode = TimeModes.ClockCycle
        elif xnode.get('time_mode', '').lower() == 'absolute': self.time_mode = TimeModes.Absolute
        else:  self.time_mode = TimeModes.Relative
        self.rand_seed = int(xnode.get('rand_seed', '1'))
        self.sample_size = int(xnode.get('sample_size', '0'))        
        self.forced_value = xnode.get('forced_value', '')
        self.duration_min, self.duration_max = float(xnode.get('duration_min', '0')), float(xnode.get('duration_max', '0'))
        self.modifier = xnode.get('modifier', '')
        self.trigger_expression = xnode.get('trigger_expression', '')
        self.time_start = float(xnode.get('injection_time_start', '0'))
        self.increment_time_step = float(xnode.get('increment_time_step', '0'))
        self.time_end = float(xnode.get('injection_time_end', '0'))
        self.activity_time_start = float(xnode.get('activity_time_start', '0'))
        self.activity_time_end = float(xnode.get('activity_time_end', '0'))
        self.inactivity_time_start = float(xnode.get('inactivity_time_start', '0'))
        self.inactivity_time_end = float(xnode.get('inactivity_time_end', '0'))
        self.multiplicity = int(xnode.get('multiplicity', '1'))
        self.simulataneous_faults = True if int(xnode.get('simultaneous_faults','')=='yes') else False
        self.CCF = re.findall('{(.*?)}', xnode.get('CCF',''))




        return(0)

class SBFIConfigInjector:
    def __init__(self, xnode):
        self.fault_model = []
        if xnode is None:
            self.checkpont_mode = CheckpointModes.ColdRestore
            self.reference_check_pattern = ''
            self.workload_split_factor = int(0)            
            self.campaign_label = "AFIT_"
            self.compile_project = False
            self.cleanup_folders = False
            self.create_scripts = False
            self.create_checkpoints = False
            self.create_precise_checkpoints = False
            self.create_injection_scripts = False
            self.run_faultinjection = False
            self.remove_par_lib_after_checkpoint_stored = False
            self.cancel_pending_tasks = False
            self.sim_time_checkpoints = ""
            self.sim_time_injections = ""
            self.work_label = ""
            self.wlf_remove_time = ""
            self.run_cleanup = ""
            self.monitoring_mode = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.maxproc = int(xnode.get('maxproc'))
        self.workload_split_factor = int(xnode.get('workload_split_factor'))        
        self.campaign_label = xnode.get('campaign_label')
        self.checkpont_mode = CheckpointModes.WarmRestore if xnode.get('checkpont_mode', '').lower() == 'warmrestore' else CheckpointModes.ColdRestore
        self.reference_check_pattern = xnode.get('reference_check_pattern', '')
        self.compile_project = True if xnode.get('compile_project').lower() == "on" else False
        self.cleanup_folders = True if xnode.get('cleanup_folders').lower() == "on" else False
        self.create_scripts = True if xnode.get('create_scripts').lower() == "on" else False
        self.create_checkpoints = True if xnode.get('create_checkpoints').lower() == "on" else False
        self.create_precise_checkpoints = True if xnode.get('create_precise_checkpoints').lower() == "on" else False
        self.create_injection_scripts = True if xnode.get('create_injection_scripts').lower() == "on" else False
        self.run_faultinjection = True if xnode.get('run_faultinjection').lower() == "on" else False
        self.remove_par_lib_after_checkpoint_stored = True if xnode.get('remove_par_lib_after_checkpoint_stored').lower() == "on" else False
        self.cancel_pending_tasks = True if xnode.get('cancel_pending_tasks').lower() == "on" else False
        self.sim_time_checkpoints = xnode.get('sim_time_checkpoints')
        self.sim_time_injections = xnode.get('sim_time_injections')
        self.work_label = xnode.get('work_label')
        self.wlf_remove_time = int(xnode.get('wlf_remove_time'))
        self.run_cleanup = xnode.get('run_cleanup')
        self.monitoring_mode = xnode.get('monitoring_mode', '')
        for i in xnode.findall('faultload'):
            self.fault_model.append(FaultModelConfig(i))
        return(0) 


#1.4 Configuration parameters: used by Analyzer module
class JoinGroup:
    def __init__(self, label=""):
        self.join_label = label
        self.src_labels = []
        self.src_indexes = []
        
    def to_str(self):
        res = "\tJOIN_GROUP: " + self.join_label + " :"
        for i in self.src_labels:
            res += "\n\t\t"+i
        return(res)

    def copy(self):
        res = JoinGroup(self.join_label)
        for i in self.src_labels:
            res.src_labels.append(i)
        return(res)

class JoinGroupList:
    def __init__(self):
        self.group_list = []
        
    def init_from_tag(self, tag):
        for c in tag.findall('group'):
            a = JoinGroup(c.get('label'))
            for i in c.findall('item'):
                a.src_labels.append(i.get('label'))
            self.group_list.append(a)

    def to_str(self):
        res = "JOIN_GROUPS: "
        for c in self.group_list:
            res += "\n" + c.to_str()
        return(res)
    
    def copy(self):
        res = JoinGroupList()
        for c in self.group_list:
            res.group_list.append(c.copy())
        return(res)

class RenameItem:
    def __init__(self, ifrom="", ito=""):
        self.ifrom = ifrom
        self.ito = ito
    def to_string(self):
        return('From: ' + self.ifrom + ", To: " + self.ito)


class TraceCheckModes:
    MLV, MAV = range(2)



class SBFIConfigAnalyzer:
    def __init__(self, xnode):
        self.join_group_list = JoinGroupList()
        self.rename_list = []
        if xnode is None:
            self.error_flag_signal = ""
            self.error_flag_active_value = ""
            self.trap_type_signal = ""
            self.mode = TraceCheckModes.MAV
            self.time_window = None
            self.max_time_violation = int(0)
            self.threads = int(1)
            self.domain_mode = ""
            self.check_range_columns = []
        else:
            self.build_from_xml(xnode)

           
    def build_from_xml(self, xnode):
        self.error_flag_signal = xnode.get('error_flag_signal','')
        self.error_flag_active_value = xnode.get('error_flag_active_value','')
        self.trap_type_signal = xnode.get('trap_type_signal','')
        self.mode = TraceCheckModes.MLV if xnode.get('mode','').upper()=='MLV' else TraceCheckModes.MAV
        self.domain_mode = xnode.get('domain_mode','').upper()
        match_desc = re.search('([0-9]+):([0-9]+)', xnode.get('time_window', ''))
        self.time_window = None if match_desc is None else (int(match_desc.group(1)), int(match_desc.group(2)))
        self.max_time_violation = int(xnode.get('max_time_violation','0'))
        self.threads = int(xnode.get('threads','1'))
        tag = xnode.findall('join_groups')
        if len(tag) > 0: self.join_group_list.init_from_tag(tag[0])
        tag = xnode.findall('rename_list')
        if len(tag) > 0:
            for c in tag[0].findall('item'):
                self.rename_list.append(RenameItem(c.get('from'), c.get('to')))
        self.check_range_columns = xnode.get('check_range_columns', '').replace(' ', '').split(',')



#1.5 Configuration Items for HDL models under test (annex for genconfig)
class ParConfig:
    def __init__(self, xnode):
        self.report_dir = ""
        if xnode is None:
            self.work_dir = ""
            self.checkpoint = ""
            self.design_type = ""
            self.label = ""
            self.clk_period = float(0)
            self.workload_time = int(0)
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.work_dir = xnode.get('work_dir')
        self.checkpoint = xnode.get('checkpoint', '')
        self.design_type = xnode.get('design_type', 'RTL').lower()
        self.label = xnode.get('label')
        self.clk_period = float(xnode.get('clk_period'))
        self.workload_time = int(xnode.get('simulation_time'))

        

class Platforms:
    Multicore, Grid, GridLight = range(3)

#1.6 Root SBFI Configuration Object
class SBFIConfiguration:
    def __init__(self, xnode):
        self.clean_run = False
        self.checkpoint_mode = CheckpointModes.ColdRestore
        self.initializer_phase = False
        self.profiler_phase = False
        self.injector_phase = False
        self.reportbuilder_phase = False
        self.time_quota = '20:00:00'
        self.fault_dictionary = ''
        self.injection_scopes = []
        self.observation_scopes = []
        self.injection_items = []
        self.observation_items = []
        self.fault_model = []
        self.analyzer = None
        self.workload_split_factor = 20
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.clean_run = True if xnode.get('clean_run','').lower() == 'on' else False
        self.checkpoint_mode = CheckpointModes.WarmRestore if xnode.get('checkpoint_mode', '').lower() == 'warmrestore' else CheckpointModes.ColdRestore
        self.initializer_phase = True if xnode.get('initializer_phase', '') == 'on' else False
        self.profiler_phase = True if xnode.get('profiler_phase', '') == 'on' else False
        self.injector_phase = True if xnode.get('injector_phase', '') == 'on' else False
        self.reportbuilder_phase = True if xnode.get('reportbuilder_phase', '') == 'on' else False
        self.time_quota = xnode.get('time_quota', '20:00:00')
        self.fault_dictionary = xnode.get('fault_dictionary')
        for i in xnode.findall('InjectionScope'):
            self.injection_scopes.append(InjectionScope(i))
        for i in xnode.findall('ObservationScope'):
            self.observation_scopes.append(ObservationScope(i))
        for i in xnode.findall('InjectionItem'):
            self.injection_items.append(ModelItem(i))
        for i in xnode.findall('ObservationItem'):
            self.observation_items.append(ModelItem(i))
        for i in xnode.findall('faultload'):
            self.fault_model.append(FaultModelConfig(i))
        tag = xnode.findall('Analyzer')
        if len(tag) > 0: self.analyzer = SBFIConfigAnalyzer(tag[0])



class ExperiementalDesignConfiguration:
    def __init__(self, xnode):
        self.call_dir = os.getcwd()
        self.platform = Platforms.Multicore
        self.ConfigFile = ''
        self.max_proc = int(1)
        self.retry_attempts = int(2)
        self.overwrite_existing = True
        self.build_factorial_design = True
        self.implement_design = True
        self.implement_default_config = True
        self.build_testbench_random_inputs = True
        self.first_index = int(0)
        self.last_index = int(0)
        self.design_genconf = None    # ExperimentalDesignGenerics
        self.flow = None              # ImplementationFlow
        self.factorial_config = None  # FactorialDesignConfig
        if xnode != None:
            self.build_from_xml(xnode)
        self.statfile = 'Statistics.xml'

    def build_from_xml(self, xnode):
        self.max_proc = int(xnode.get('max_proc','1'))
        self.retry_attempts = int(xnode.get('retry_attempts','2'))
        self.overwrite_existing = True if (xnode.get('overwrite_existing', '')).lower() == 'on' else False
        self.build_factorial_design = True if (xnode.get('build_factorial_design', '')).lower() == 'on' else False
        self.implement_design = True if (xnode.get('implement_design', '')).lower() == 'on' else False
        self.implement_default_config = True if (xnode.get('implement_default_config', '')).lower() == 'on' else False
        self.build_testbench_random_inputs = True if (xnode.get('build_testbench_random_inputs', '')).lower() == 'on' else False
        self.first_index = int(0) if xnode.get('first_index','') == '' else int(xnode.get('first_index'))
        self.last_index = int(0) if xnode.get('last_index','') == '' else int(xnode.get('last_index'))
        self.design_genconf = ExperimentalDesignGenerics(xnode.findall('generic')[0])
        self.flow = ImplementationFlow(xnode.findall('ImplementationFlow')[0])
        self.factorial_config = FactorialDesignConfig(xnode.findall('factorial_design')[0])
        self.design_genconf.design_dir = os.path.abspath(os.path.join(self.call_dir, self.design_genconf.design_dir))
        self.design_genconf.tool_log_dir = os.path.abspath(os.path.join(self.call_dir, self.design_genconf.design_dir, 'Logs'))


class ExperimentalDesignGenerics:
    def __init__(self, xnode):
        self.design_label = ''
        self.design_dir = ''
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.design_label = xnode.get('design_label','NonameDesign_')
        self.design_dir = xnode.get('design_dir','')
        self.template_dir = xnode.get('template_dir','')
        self.log_dir = xnode.get('log_dir','')
        self.netlist_dir = xnode.get('netlist_dir','')
        self.clk_net = xnode.get('clk_net','')
        self.rst_net = xnode.get('rst_net','')
        self.testbench_template_file = xnode.get('testbench_template_file','')
        self.sim_project_file = xnode.get('sim_project_file','')
        self.testbench_file = xnode.get('testbench_file','')
        self.testbench_top_unit = xnode.get('testbench_top_unit','')
        self.clk_constant = xnode.get('clk_constant','')
        self.uut_root = xnode.get('uut_root','')
        self.std_start_time = float(xnode.get('std_start_time','0'))
        self.std_observation_time = float(xnode.get('std_observation_time','0'))
        self.std_clock_period = float(xnode.get('std_clock_period','0'))
        self.constraint_file = xnode.get('constraint_file','')
        cp = xnode.get('custom_parameters','')
        if cp != '': self.custom_parameters = ast.literal_eval(cp)


        





class FactorialDesignConfig:
    def __init__(self, xnode):
        self.table_of_factors = ''
        self.resolution = 0
        self.factors = []
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.table_of_factors = xnode.get('table_of_factors','')
        self.resolution = 0 if xnode.get('resolution')=='' else int(xnode.get('resolution'))
        self.design_type = xnode.get('design_type','')
        for i in xnode.findall('factor'):
            self.factors.append(IFactor(i))

    def GetFactorByName(self, key):
        for f in self.factors:
            if f.factor_name == key:
                return(f)
        return(None)


            


class IFactor:
    def __init__(self, tag):
        self.factor_name = None #X1....X31
        self.option_name = None #power, opt_mode
        self.phase_name = None  #synthesis/translate/map/par
        self.setting = dict()   #option_value[X.value]=Speed
        self.from_xml(tag)

    def from_xml(self, tag):
        if tag != None:
            self.factor_name = tag.get('name', '')
            self.option_name = tag.get('option', '')
            self.phase_name = tag.get('phase', '')
            for i in tag.findall('setting'):
                self.setting[int(i.get('factor_value'))] = i.get('option_value')




class ImplementationFlow:
    def __init__(self, tag = None):
        self.name = ''
        self.phases = []
        self.entry_phase = None #ImplementationPhase
        self.from_xml(tag)

    def from_xml(self, tag):
        if tag != None:
            self.name = tag.get('name', '')
            for c in tag.findall('phase'):
                self.phases.append(ImplementationPhase(c))
            #now link the phases in a chain by pointer
            #find first
            for c in self.phases:
                if c.name == tag.get('EntryPhase'):
                    self.entry_phase = c
                    break
            if self.entry_phase == None:
                raw_input('ImplementationFlow: entry phase not found in configuration xml\nPress any key to continue...')
            current = self.entry_phase
            while current != None:
                found = False
                for c in self.phases:
                    if current.next == c.name:
                        current.next = c
                        found = True
                        break
                if found:
                    current = current.next
                else:
                    current.next = None
                    current = None
            #link constraint -> return_to_phase:
            for c in self.get_phase_chain():
                if c.constraint_to_adjust != None:
                    for p in self.get_phase_chain():
                        if p.name == c.constraint_to_adjust.return_to_phase:
                            c.constraint_to_adjust.return_to_phase = p
                            p.constraints_to_export.append(c.constraint_to_adjust)
                            break

    def get_phase_chain(self):
        res = []
        current = self.entry_phase
        while current != None:
            res.append(current)
            current = current.next
        return(res)

    def get_phase(self, name):
        for p in self.get_phase_chain():
            if p.name == name:
                return(p)
        return(None)

    def to_string(self):
        res = 'ImplementationFlow: ' + self.name
        for c in self.get_phase_chain():
            res += "\n\n" + c.to_string()
        return(res)



class ImplementationPhase:
    def __init__(self, tag = None):
        self.name = ''
        self.script_builder = ''
        self.result_handler = ''
        self.postcondition_handler = ''
        self.next = None
        self.postcondition = []
        self.options = [] #IOption
        self.constraint_to_adjust = None
        self.constraints_to_export = []
        self.from_xml(tag)
        self.logfile = '_'+self.name+'.log'
        self.resultfiles = []
        self.reportfile = ''

    def from_xml(self, tag):
        if tag != None:
            self.name = tag.get('name')
            self.script = tag.get('script','')
            self.script_builder = tag.get('script_builder','')
            self.result_handler = tag.get('result_handler','')
            self.postcondition_handler = tag.get('postcondition_handler','')
            self.next = tag.get('next','')
            for c in tag.findall('option'):
                self.options.append(IOption(c))
            constraints = tag.findall('Constraint')
            if len(constraints) > 0:
                self.constraint_to_adjust = ImplementationConstraint(constraints[0])

    def to_string(self):
        res = "\n\nPhase: " + self.name + " : " + self.script + " : " + self.script_builder + " : Next = "
        if self.next != None: res += self.next.name
        else: res += "None"
        for c in self.options:
            res += "\n\t" + c.to_string()
        return(res)

    def get_option(self, name):
        for i in self.options:
            if i.name == name:
                return(i)
        return(None)


    
                 
class IOption:
    def __init__(self, tag = None):
        self.name = ''    #power, opt_mode....
        self.default = ''  #No/Yes, Speed/Area...
        self.path = ''
        self.modifier = ''
        self.from_xml(tag)

    def from_xml(self, tag):
        if tag != None:
            self.name = tag.get('name')
            self.default = tag.get('default')
            self.path = tag.get('path','')
            self.modifier = tag.get('modifier','')

    def to_string(self):
        return("Option: " + self.name + " = " + self.default + " : Path = " + self.path + " : Mod = " + self.modifier)


class AdjustGoal:
    min, max = range(2)


class ImplementationConstraint:
    def __init__(self, tag = None):
        self.placeholder = ''
        self.goal = None        #AdjustGoal
        self.start_value = None #int or float
        self.adjust_step = None #int or float
        self.return_to_phase = None
        self.check_handler = None
        self.from_xml(tag)
        #generated by tool
        self.current_value = None
        self.converged = False
        self.iteration = int(1)


    def from_xml(self, tag):
        if tag != None:
            self.placeholder = tag.get('placeholder','')
            if tag.get('goal','') == 'min':
                self.goal = AdjustGoal.min
            elif tag.get('goal','') == 'max':
                self.goal = AdjustGoal.max
            else:
                raw_input('ImplementationConstraint error: undefined goal (should be either min or max)')
            self.start_value = tag.get('start_value')
            self.adjust_step = tag.get('adjust_step')
            if (self.start_value.find('.') >= 0) or (self.adjust_step.find('.') >= 0):
                self.start_value = float(self.start_value)
                self.adjust_step = float(self.adjust_step)
            else:
                self.start_value = int(self.start_value)
                self.adjust_step = int(self.adjust_step)
            self.return_to_phase = tag.get('return_to_phase')
            self.check_handler = tag.get('check_handler', '')


class DerivedMetric:
    def __init__(self, xnode):
        self.name = ''
        self.handler = ''
        self.custom_arg = dict()
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.get('name')
        self.handler = xnode.get('handler')
        a = xnode.get('custom_arg','')
        self.custom_arg = dict() if a=='' else ast.literal_eval(a)



class McdmScenario:
    def __init__(self, xnode):
        self.name = ''
        self.scoremodel = ''
        self.variables = dict()
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.get('name')
        self.scoremodel = xnode.get('scoremodel')
        for i in xnode.findall('variable'):
            self.variables[str(i.get('name'))] = {'goal':AdjustGoal.min if i.get('goal').lower()=='min' else AdjustGoal.max, 'weight':float(i.get('weight'))}

class DecisionSupportConfiguration:
    def __init__(self, xnode):
        self.call_dir = os.getcwd()
        self.DerivedMetrics = []
        self.MCDM = []
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.task = xnode.get('task', '')
        self.method = xnode.get('method', '')
        a = xnode.findall('DerivedMetrics')
        if len(a) > 0:
            for x in a[0].findall('DerivedMetric'):
                self.DerivedMetrics.append(DerivedMetric(x))
        for i in xnode.findall('MCDM')[0].findall('Scenario'):
            self.MCDM.append(McdmScenario(i))


class Injectors:
    Microblaze, Zynq = range(2)

class FFIConfiguration:
    def __init__(self, xnode):
        self.injector = Injectors.Microblaze
        self.injector_phase = False
        self.reportbuilder_phase = False
        self.dut_scope=''
        self.target_logic = ""
        self.custom_lut_mask = False
        self.profiling = False
        self.mode = 101
        self.sample_size_goal = 100
        self.seed = 1
        self.error_margin_goal = 0.1
        self.fault_multiplicity = 1
        self.injection_time = 0
        self.post_injection_recovery_nodes = []
        self.hdf_path = ""
        self.init_tcl_path = ""
        self.injectorapp_path = ""
        self.memory_buffer_address = 0x3E000000
        self.platformconf = []
        self.pblock = None
        self.dut_script = ""
        if xnode != None:
            self.build_from_xml(xnode)


    def build_from_xml(self, xnode):
        self.injector = Injectors.Microblaze if xnode.get('injector', '').lower() == 'microblaze' else Injectors.Zynq
        self.injector_phase = True if xnode.get('injector_phase', '') == 'on' else False
        self.reportbuilder_phase = True if xnode.get('reportbuilder_phase', '') == 'on' else False
        self.device_part = xnode.get('device_part', '').lower()
        self.dut_scope = xnode.get('dut_scope','')
        matchDesc = re.search('([0-9a-zA-Z]+)\s*?:([0-9a-zA-Z]+)\s*?:\s*?X([0-9]+)Y([0-9]+)\s*?:\s*?X([0-9]+)Y([0-9]+)',
                              xnode.get('pblock','').upper().replace(' ',''))
        if matchDesc:
            self.pblock = {
                'name': matchDesc.group(1),
                'notation': matchDesc.group(2),
                'X1': int(matchDesc.group(3)),
                'Y1': int(matchDesc.group(4)),
                'X2': int(matchDesc.group(5)),
                'Y2': int(matchDesc.group(6))
            }
        self.target_logic = xnode.get('target_logic', '').lower()
        self.custom_lut_mask = True if xnode.get('custom_lut_mask', '') == 'on' else False
        self.profiling = True if xnode.get('profiling', '') == 'on' else False
        self.mode = int(xnode.get('mode', '101'))
        self.sample_size_goal = int(xnode.get('sample_size_goal','100'))
        self.seed = int(xnode.get('seed','1'))        
        self.error_margin_goal = float(xnode.get('error_margin_goal', '0.5'))
        self.fault_multiplicity = int(xnode.get('fault_multiplicity', '1'))
        self.injection_time = int(xnode.get('injection_time', '0'))
        self.dut_script = xnode.get('dut_script', '')

        cp = xnode.get('post_injection_recovery_nodes', '')
        if cp != '': self.post_injection_recovery_nodes = ast.literal_eval(cp)
        self.hdf_path = xnode.get('hdf_path', '')
        self.init_tcl_path = xnode.get('init_tcl_path', '')
        self.injectorapp_path = xnode.get('injectorapp_path', '')
        self.memory_buffer_address = int(xnode.get('memory_buffer_address', '0x3E000000'), 16)
        cp = xnode.get('platformconf', '[]')
        if cp != '': self.platformconf = ast.literal_eval(cp)



class DavosConfiguration:
    def __init__(self, xnode):
        self.report_dir = ''
        self.experiment_label = ''
        self.platform = Platforms.Multicore
        self.maxproc = 1
        self.call_dir = os.getcwd()
        self.DesignBuilder_enable = False
        self.SBFI_enable = False
        self.FFI_enable = False
        self.DecisionSupport_enable = False
        self.ExperimentalDesignConfig = None
        self.SBFI = None
        self.FFI = None
        self.DecisionSupportConfig = None
        self.dbfile = ''
        self.parconf=[]
        if xnode != None:
            self.build_from_xml(xnode)
        self.ConfigFile = ''
        for c in self.parconf:
            c.work_dir = os.path.normpath(os.path.join(self.call_dir, c.work_dir))


    def build_from_xml(self, xnode):
        self.report_dir = os.path.normpath(xnode.get('report_dir', '').replace('#RUNDIR', self.call_dir))
        self.experiment_label = xnode.get('experiment_label', 'Exp1')
        v = xnode.get('platform', 'multicore').lower()
        if v == 'multicore': self.platform = Platforms.Multicore
        elif v == 'grid': self.platform = Platforms.Grid
        elif v == 'gridlight': self.platform = Platforms.GridLight
        self.maxproc = int(xnode.get('maxproc','1'))
        self.DesignBuilder_enable = True if xnode.get('DesignBuilder', '') == 'on' else False
        self.SBFI_enable = True if xnode.get('SBFI', '') == 'on' else False
        self.FFI_enable = True if xnode.get('FFI', '') == 'on' else False
        self.DecisionSupport = True if xnode.get('DecisionSupport', '') == 'on' else False
        self.dbfile = '{0}.db'.format(self.experiment_label)
        tag = xnode.findall('ExperimentalDesign')
        if len(tag) > 0: self.ExperimentalDesignConfig = ExperiementalDesignConfiguration(tag[0])
        tag = xnode.findall('SBFI')
        if len(tag) > 0: self.SBFI = SBFIConfiguration(tag[0])
        tag = xnode.findall('FFI')
        if len(tag) > 0: self.FFI = FFIConfiguration(tag[0])
        tag = xnode.findall('DecisionSupport')
        if len(tag) > 0: self.DecisionSupportConfig = DecisionSupportConfiguration(tag[0])
        for c in xnode.findall('ModelConfig'):
            self.parconf.append(ParConfig(c))
        self.parconf.sort(key=lambda x: x.label, reverse = False)


    def get_DBfilepath(self, backup_path = False):
        if not backup_path:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile)) )
        else:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile.replace('.db', '_Backup.db')) )  )   

