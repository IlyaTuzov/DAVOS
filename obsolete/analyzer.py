# SBFI Analysis tool
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import lxml
import shutil
import time
import glob
import gc
import subprocess
from fit_generic import *
import sqlite3

    
def get_strcontains_index(ilist, ikey):
    for i in range(0, len(ilist), 1):
        if ilist[i].find(ikey) >= 0:
            return(i)
    return(None)

class ExpDescItem:
    def __init__(self):
        self.index = int(0);
        self.target = ""
        self.instance_type = ""
        self.fault_model = ""
        self.injection_case = ""
        self.forced_value = ""
        self.duration = ""
        self.injection_time = int(0)
        self.observation_time = int(0)
        self.generic_fault_model = None
        self.max_activity_duration = float(0)
        self.max_activity_relative_from = ''
        self.max_activity_relative_to = ''
        self.effective_switches = int(0)
        self.effective_switches_from = ''
        self.effective_switches_to = ''
        self.logic_group = ''
        self.profiled_value = ''
        self.on_trigger = ''
        
    def build_from_csv_line(self, line, itemsep, ind):
        values = line.split(itemsep) 
        if ind['INDEX'] != None: self.index = int(values[ind['INDEX']])
        if ind['TARGET'] != None: self.target = values[ind['TARGET']]
        if ind['INSTANCE_TYPE'] != None: self.instance_type = values[ind['INSTANCE_TYPE']]
        if ind['FAULT_MODEL'] != None: self.fault_model = values[ind['FAULT_MODEL']]
        if ind['FORCED_VALUE'] != None: self.forced_value = (values[ind['FORCED_VALUE']]).replace('*','x').replace('#','') #.replace('+','plus')
        if ind['DURATION'] != None: self.duration = (values[ind['DURATION']]).replace('*','x')
        if ind['TIME_INSTANCE'] != None:  self.injection_time = int(values[ind['TIME_INSTANCE']])
        if ind['OBSERVATION_TIME'] != None:  self.observation_time = int(values[ind['OBSERVATION_TIME']])
        if ind['INJECTION_CASE'] != None:  self.injection_case = values[ind['INJECTION_CASE']]

        if ind['MAX_ACTIVITY_DURATION'] != None:
            try:
                self.max_activity_duration = float(values[ind['MAX_ACTIVITY_DURATION']])
            except ValueError:
               self.max_activity_duration = float(0)
        if ind['EFFECTIVE_SWITHES']  != None:
            try:
                self.effective_switches = float(values[ind['EFFECTIVE_SWITHES']])
            except ValueError:
                self.effective_switches = float(0)
        if ind['PROFILED_VALUE'] != None: self.profiled_value = values[ind['PROFILED_VALUE']] 
        if ind['ON_TRIGGER'] != None: self.on_trigger = values[ind['ON_TRIGGER']] 
        return(self)
    
    def to_string(self):
        return( str(self.index) + " | " +  self.target + " | " + self.instance_type + " | " + self.fault_model + " | " + self.forced_value + " | " + str(self.injection_time) + " | " + str(self.observation_time))
    
    
    
class ExpDescTable:
    def __init__(self, label=""):
        self.label = label
        self.items = []

            
    def build_from_csv_file(self, fname, default_logic_type = 'Other'):
        with open(fname, 'r') as csv_file:
            lines = csv_file.readlines()
        itemsep = re.findall("sep\s*?=\s*?([;,]+)", lines[0])[0]
        for i in lines:
            if i.find('INDEX') >= 0:
                headers = i.split(itemsep)
                break
        ind = dict()
        ind['INDEX'] = get_strcontains_index(headers, 'INDEX')
        ind['TARGET'] = get_strcontains_index(headers, 'TARGET')
        ind['INSTANCE_TYPE'] = get_strcontains_index(headers, 'INSTANCE_TYPE')
        ind['FAULT_MODEL'] = get_strcontains_index(headers, 'FAULT_MODEL')
        ind['FORCED_VALUE'] = get_strcontains_index(headers, 'FORCED_VALUE')
        ind['DURATION'] = get_strcontains_index(headers, 'DURATION')
        ind['TIME_INSTANCE'] = get_strcontains_index(headers, 'TIME_INSTANCE')
        ind['OBSERVATION_TIME'] = get_strcontains_index(headers,'OBSERVATION_TIME')
        ind['MAX_ACTIVITY_DURATION'] = get_strcontains_index(headers, 'MAX_ACTIVITY_DURATION')
        ind['EFFECTIVE_SWITHES'] = get_strcontains_index(headers, 'EFFECTIVE_SWITHES')
        ind['PROFILED_VALUE'] = get_strcontains_index(headers, 'PROFILED_VALUE')
        ind['ON_TRIGGER'] = get_strcontains_index(headers, 'ON_TRIGGER')
        ind['INJECTION_CASE'] = get_strcontains_index(headers, 'INJECTION_CASE')

        for l in lines:
            if re.match('^\s*?[0-9]+', l):
                c = ExpDescItem()
                c.build_from_csv_line(l, itemsep, ind)
                if c.instance_type == "": c.instance_type = default_logic_type
                self.items.append(c)
        return(len(self.items))
    
    def get_by_index(self, index):
        for c in self.items:
            if(c.index == index):
                return(c)
        return(None)    
        
    
    def normalize_targets(self):
        for c in self.items:
            c.target = c.target.replace('/O}','}')
            c.target = c.target.replace('/','_')
    
    def filter(self, key, value):
        if key == 'profiled_value':
            buf = []
            cnt = 0
            for i in self.items:
                if i.profiled_value == value:
                    buf.append(i)
                    cnt +=1
            self.items = buf
            print 'Filter Matched: Key = ' + key + ' Value = ' + str(value) + '  cnt = ' + str(cnt)
        
    
class TrapDescription:
    def __init__(self):
        self.name = ""
        self.description = ""
        self.priority = ""
        self.trap_type = "00"
    def to_string(self):
        return( "Trap: " + self.name + ", Description: " + self.description  + ", Priority: " + self.priority + ", Trap type: " + self.trap_type )

class TrapDescriptionTable:
    def __init__(self):
        self.items = []
    def build_from_file(self, fname):
        if(fname != ""):
            tree = ET.parse(fname).getroot()
            for xnode in tree.findall('item'):
                name = xnode.get('trap')
                description = xnode.get('description')
                priority = xnode.get('priority')
                trap_type = xnode.get('tt')
                if(trap_type.find('-') == -1):
                    t_item = TrapDescription()
                    t_item.name = name
                    t_item.description = description
                    t_item.priority = priority
                    t_item.trap_type = trap_type
                    self.items.append(t_item)
                else:
                    vals = trap_type.split('-')
                    vlow = int(vals[0], 16)
                    vhigh = int(vals[1], 16)
                    for vind in range(vlow, vhigh+1, 1):
                        t_item = TrapDescription()
                        t_item.name = name
                        t_item.description = description
                        t_item.priority = priority
                        t_item.trap_type = "%X" % vind
                        self.items.append(t_item)
                        
    def to_string(self):
        res = ""
        for c in self.items:
            res += "\n" + c.to_string()
        return(res)
    def get_by_trap_type(self, tt):
        for c in self.items:
            if(c.trap_type == tt):
                return(c)
        return(None)
#----------------------------------------------------------------------------------

class HierNode:
    def __init__(self, name = ''):
        self.root = None
        self.parent = None
        self.childs = []
        self.name = name
        self.hier_level = 0
        self.error_total = 0
        self.error_rate = float(0.0)
        self.pass_flag = False
        
    def find(self, iname):
        for c in self.childs:
            if(c.name == iname):
                return(c)
        return(None)
    
    def add_by_name(self, iname):
        res = HierNode(iname)        
        res.root = self.root
        res.parent = self
        res.hier_level = self.hier_level + 1
        self.childs.append(res)
        return(res)
    
    def reset_flags(self):
        self.pass_flag = True
        for c in self.childs:
            c.reset_flags()
            
    def increment_error_counter(self):
        if(self.pass_flag == False):
            self.error_total += 1
        for c in self.childs:
            c.increment_error_counter()
    
    def compute_error_rate(self, exp_num):
        self.error_rate = 100.0 * float(self.error_total) / float(exp_num)
        for c in self.childs:
            c.compute_error_rate(exp_num)
        
    def tree_to_string(self):
        res = "\n"
        for i in range(0, self.hier_level, 1):
            res += "\t"
        res += self.name + ": " + str(self.error_total)
        for c in self.childs:
            res += c.tree_to_string()
        return(res)
        
    def tree_to_html_rows(self):
        res = []
        row = HtmlTableRow(3)
        label = ""
        for i in range(0, self.hier_level, 1):
            label += "|\t"
        label += self.name
        row.put_data(0, label)
        row.put_data(1, str(self.error_total))
        row.put_data(2, str("%2.2f" % self.error_rate) + "%")        
        res.append(row)
        for c in self.childs:
            res.extend(c.tree_to_html_rows())
        return(res)
        

    
class ReportItem:
    def __init__(self):
        self.failure = False
        self.last_solution_correct = "-"
        self.number_of_errors = 0
        self.internal_error_detected = False
        self.trap_type = "-"
        self.inj_description = None
        self.group_name = ""
        self.masked_fault = False
        self.latent_fault = False
        self.signalled_failure = False
        self.silent_data_corruption = False
        self.hang = False
        self.failure_mode = ""
        self.check_vector = [] # False / True for each internal signal listed in the dump
        self.internal_values_vector = [] #Free memory when not needed!!! (takes much memory)
        self.latency_fault_to_failure = "-"
        self.matched = False
        
    def to_string(self):
        result = "No description"
        if(self.inj_description != None):
            result = self.inj_description.to_string()
        result += "\nFailure: " + str(self.failure) + ", Last Solution Correct: " + self.last_solution_correct + ", Numver of errors: " + str(self.number_of_errors) + ", Internal Error detected: " + str(self.internal_error_detected) + ", Trap type: " + self.trap_type
        result += "\nGroup Name: " + self.group_name
        return( result )
    
    def set_group_name_by_fault_model(self):
        if(self.inj_description.logic_group != ''):
            self.group_name = self.inj_description.logic_group + '-' + self.inj_description.fault_model
        else:
            self.group_name = self.inj_description.fault_model
        if(self.inj_description.forced_value != ""):
            self.group_name += "-" + self.inj_description.instance_type
        if(self.inj_description.injection_case != ""):
            self.group_name += "-" + self.inj_description.injection_case
        if(self.inj_description.forced_value != ""):
            self.group_name += "-" + self.inj_description.forced_value

        #if(self.inj_description.duration != ""):
        #    self.group_name += "-" + self.inj_description.duration            
        #if(self.inj_description.generic_fault_model != None):
        #     self.group_name += "_[" + str(self.inj_description.generic_fault_model.time_start) + '-'+ str(self.inj_description.generic_fault_model.time_end) + "]"
        #if(self.inj_description.max_activity_relative_from != ''):
        #    self.group_name += "_ActInt[" + self.inj_description.max_activity_relative_from + ' - ' + self.inj_description.max_activity_relative_to + ']'
        #if(self.inj_description.effective_switches_from != ''):
        #    self.group_name += "_EffectiveSwitches[" + self.inj_description.effective_switches_from + ' - ' + self.inj_description.effective_switches_to + ']'
        #if(self.inj_description.profiled_value != ''):
        #     self.group_name += '_ProfiledValue[' + self.inj_description.profiled_value + ']'
        
        
        return(self.group_name)
    
    
class ReportGroup:
    def __init__(self, label=""):
        self.label = label
        self.logpage_link = ""
        self.report_items = []
        self.entity_labels = [] # for items of check_vector
        self.hierarchy_report_path = ""
        self.hierarchy_tree_path = ""
        self.hroot = None
        self.hleaves = []
        #statistics for the group
        self.failure_number = int(0)
        self.failure_rate = float(0.0)
        self.recover_number = int(0)
        self.hang_number = int(0)
        self.recover_rate = float(0.0)
        self.error_avg_number = int(0)
        self.internal_error_detected_number = int(0)
        self.internal_error_detected_rate = float(0.0)      
        self.trap_types = {}
        self.trap_list = []
        self.masked_fault_number = int(0)
        self.latent_fault_number = int(0)
        self.signalled_failure_number = int(0)
        self.silent_data_corruption_number = int(0)
        
        self.fault_to_failure_latency_min = float(10000000000000.0)
        self.fault_to_failure_latency_max = float(0.0)
        self.fault_to_failure_latency_mean = float(0.0)
        self.root_error_rate = float(0.0)
        self.logpage_table = None
    
    def compute_statistic(self):
        err_sum = 0
        group_size = len(self.report_items)
        self.failure_number = int(0)
        self.failure_rate = float(0.0)
        self.recover_number = int(0)
        self.hang_number = int(0)
        self.recover_rate = float(0.0)
        self.error_avg_number = int(0)
        self.internal_error_detected_number = int(0)
        self.trap_types = {}        
        for c in self.report_items:
            if(c.failure): self.failure_number += 1
            if(c.last_solution_correct == "YES"): self.recover_number += 1
            if c.hang: self.hang_number += 1
            err_sum += c.number_of_errors
            if c.internal_error_detected: 
                self.internal_error_detected_number += 1
            if(self.trap_types.has_key(c.trap_type)):
                self.trap_types[c.trap_type] += 1
            else:
                self.trap_types[c.trap_type] = 1
            if c.masked_fault: self.masked_fault_number += 1
            if c.latent_fault: self.latent_fault_number += 1
            if c.signalled_failure: self.signalled_failure_number += 1
            if c.silent_data_corruption: self.silent_data_corruption_number += 1
            if c.latency_fault_to_failure != "-" :
                if(float(c.latency_fault_to_failure) >= self.fault_to_failure_latency_max):
                    self.fault_to_failure_latency_max = float(c.latency_fault_to_failure)
                if(float(c.latency_fault_to_failure) < self.fault_to_failure_latency_min):
                    self.fault_to_failure_latency_min = float(c.latency_fault_to_failure)
                self.fault_to_failure_latency_mean  += float(c.latency_fault_to_failure)
                
        self.fault_to_failure_latency_mean = (self.fault_to_failure_latency_mean / self.failure_number) if self.failure_number > 0 else 0
        self.failure_rate = 100.0*float(self.failure_number) / float(group_size)
        self.internal_error_detected_rate = 100*float(self.internal_error_detected_number) / float(group_size)
        if(self.failure_number != 0):
            self.recover_rate = 100.0*float(self.recover_number) / float(self.failure_number)
        self.error_avg_number = int(err_sum / group_size)
        self.trap_list = self.trap_types.items()
        self.trap_list.sort(key=lambda tup: tup[1], reverse=True)
        
    def trap_list_to_string(self, trap_desc_table=None):
        res = ""
        for c in self.trap_list:
            if(trap_desc_table==None):
                res += "\n" + str(c[0]) + " : " + str(c[1])
            else:
                tt_item = trap_desc_table.get_by_trap_type(c[0])
                if(str(c[0]) == "-"):
                    tt_desc = "No Trap"
                else:
                    tt_desc = "Undefined"
                if(tt_item != None):
                    tt_desc = tt_item.description
                res += "\n" + str("%04d"%c[1]) +" : " + tt_desc + " [" +  str(c[0]) + "]"
        return(res)
            
    
    def statistics_to_string(self):
        res = "\nStatisctics: "
        res += "\nDumps number: " + str(len(self.report_items))
        res += "\n\tfailure_number: " + str(self.failure_number)
        res += "\n\tfailure_rate: " + str("%2.2f" % self.failure_rate) + "%"
        res += "\n\trecover_number: " + str(self.recover_number)
        res += "\n\trecover_rate: " + str("%2.2f" % self.recover_rate) + "%"
        res += "\n\terror_avg_number: " + str(self.error_avg_number)
        res += "\n\tinternal_error_detected_number: " + str(self.internal_error_detected_number)
        res += "\n\tinternal_error_detected_rate: " +  str("%2.2f" % self.internal_error_detected_rate) + "%"    
        res += "\n\tTraps Codes: "
        for c in self.trap_list:
            res += "\n\t\t" + str(c[0]) + " : " + str(c[1])
        return(res)
    
    def to_string(self, detailed = False):
        res = "ReportGroup: " +  self.label
        if(detailed == True):
            for c in self.report_items:
                res += "\n" + c.to_string()
        res += self.statistics_to_string()
        return(res)

    def tree_to_html_table(self):
        res = HtmlTable(0,3, self.label)
        res.rows = self.hroot.tree_to_html_rows()
        res.set_label(0, 'Entity')
        res.set_label(1, 'Errors, Abs.')
        res.set_label(2, 'Error_Rate, Errors/Injections, %')        
        return(res.to_string())
        

    def build_htree(self):
        self.hroot = HierNode('Root')
        self.hroot.root = self
        for label in self.entity_labels:
            #ent_list = label.split('_')
            ent_list = re.split('_|\(|\.', label)
            c_item = self.hroot
            for e_name in ent_list:
                if(e_name.endswith(')')):
                    e_name = '(' + e_name
                x = c_item.find(e_name)
                if(x == None):
                    x = c_item.add_by_name(e_name)
                c_item = x
            self.hleaves.append(c_item) #add leaf to list
        print(self.hroot.tree_to_string())
        print("\n\nLeaves:")
        for c in self.hleaves:
            print("+ " + c.name)
        
    def compute_stat_htree(self):
        for i in self.report_items:
            #1. reset all flags to false
            self.hroot.reset_flags()
            #2. assign flags to leaves[j] from i.check_vector[j]
            for j in range(0, len(self.hleaves), 1):
                self.hleaves[j].pass_flag = i.check_vector[j]
            #3. propagate True flag across the tree from each leaf[j] to the root
            for j in range(0, len(self.hleaves), 1):
                x = self.hleaves[j]
                while x.parent != None:
                    if(x.pass_flag == False):
                        x.parent.pass_flag = False
                    x = x.parent
            #4. from root to leaves: increment error counter if flag set to True
            self.hroot.increment_error_counter()
        self.hroot.compute_error_rate(len(self.report_items))
        self.root_error_rate = self.hroot.error_rate
            
    
    
    
    def internals_check_to_html(self):
        #print "\n\nReportItems: " + str(len(self.report_items))
        #print "Labels: " +  str(len(self.entity_labels))
        logtable = HtmlTable(len(self.report_items)+1, len(self.entity_labels)+6, self.label)
        logtable.set_label(0, 'Index')
        logtable.set_label(1, 'Target')
        logtable.set_label(2, 'Fault Model')
        logtable.set_label(3, 'Forced Value')
        logtable.set_label(4, 'Inject. Time')
        logtable.set_label(5, 'Observ. Time')
        for i in range(0, len(self.entity_labels), 1):
            logtable.set_label(6+i, self.entity_labels[i])
        for k in range(0, len(self.report_items), 1):
            #print "Check vector [" + str(k) + "] :"  + str(len(self.report_items[k].check_vector))
            logtable.put_data(k, 0, str(self.report_items[k].inj_description.index))
            logtable.put_data(k, 1, self.report_items[k].inj_description.target)
            logtable.put_data(k, 2, self.report_items[k].inj_description.fault_model)
            logtable.put_data(k, 3, self.report_items[k].inj_description.forced_value)
            logtable.put_data(k, 4, str(self.report_items[k].inj_description.injection_time))
            logtable.put_data(k, 5, str(self.report_items[k].inj_description.observation_time))
            for i in range(0, len(self.entity_labels), 1):
                logtable.put_data(k, 6+i, self.report_items[k].internal_values_vector[i])
                if(self.report_items[k].check_vector[i] == True):
                    logtable.set_class(k, 6+i, 'pass')
                else:
                    logtable.set_class(k, 6+i, 'fail')
            #self.report_items[k].internal_values_vector = []
        for i in range(0, len(self.entity_labels), 1):
            ecounter = 0
            for k in range(0, len(self.report_items), 1):
                if(self.report_items[k].check_vector[i] == False):
                    ecounter += 1
            logtable.put_data(len(self.report_items), 6+i, str(ecounter))
        return(logtable.to_string())
    
    def clean_items(self):
        for k in range(0, len(self.report_items), 1):
            self.report_items[k].internal_values_vector = None
            self.report_items[k].check_vector = None
        self.hroot = None
        self.hleaves = None
        self.logpage_table = None
            

        
class ConfigReport:
    def __init__(self, label=""):
        self.label = label
        self.group_items = []
        self.hlog_path = ""
        self.report_dir = ""
        self.entity_labels = [] # for items of check_vector
        #items, grouped by injection target
        self.target_group_items = []
        self.hierarchy_content_page_path = ""
        #groups according to both faultmodel and failure mode: (stuck-at-1:latent, stuck-at-1:signalled, stuck-at-1:notsignalled, ....)
        self.failure_mode_group_items = []
        self.config = None
        self.corrupted_dumps = []
        self.dumpfilesnum = int(0)
    
    def target_group_items_to_string(self):
        res = "Target_Group_Items (" + self.label + "):"
        for c in self.target_group_items:
            res += "\n" + c.label + " : " + str(len(c.report_items)) + " [items]"
        return(res)
    
    def add_report_item_by_failure_mode(self, item):
        item.set_group_name_by_fault_model()
        j_name = item.group_name
        if(item.latent_fault):
            j_name += "+Latent"
        elif(item.signalled_failure):
            j_name += "+Signalled"
        elif(item.silent_data_corruption):
            j_name += "+NotSignalled"            
        elif(item.masked_fault):
            j_name += "+Masked"        
        gp = None
        for v in self.failure_mode_group_items:
            if(v.label == j_name):
                gp = v
                break
        if(gp==None):
            gp = ReportGroup(j_name)
            gp.entity_labels = self.entity_labels
            gp.report_items.append(item)
            self.failure_mode_group_items.append(gp)
        else:
            gp.report_items.append(item)
            
    
    def add_report_item_by_target_group(self, item):
        j_name = item.inj_description.target
        j_name = j_name.replace('/O}', '}').replace('{','').replace('}', '').replace('/testbench/','')
        j_name = re.sub('_[0-9]+$', '', j_name)
        e_tree = re.split('/|_', j_name)
        t_name = ""
        for c in e_tree:
            t_name += "/" + c
            gp = None
            for v in self.target_group_items:
                if(v.label == t_name):
                    gp = v
                    break
            if(gp==None):
                 gp = ReportGroup(t_name)
                 gp.entity_labels = self.entity_labels
                 gp.report_items.append(item)
                 self.target_group_items.append(gp)
            else:
                gp.report_items.append(item)
        return(gp)
    
    def add_report_item(self, item):
        item.set_group_name_by_fault_model()
        gp = None
        for v in self.group_items:
            if(v.label == item.group_name):
                gp = v
                break
        if(gp==None):
            gp = ReportGroup(item.group_name)
            gp.entity_labels = self.entity_labels
            gp.report_items.append(item)
            self.group_items.append(gp)
        else:
            gp.report_items.append(item)
        
    def to_string(self, detailed = False):
        res = "ConfigReport: " + self.label
        for c in self.group_items:
            res += "\n" + c.to_string(detailed)
        return(res)
    
    def compute_statisctics(self):
        for c in self.group_items:
            c.compute_statistic()
    
    def get_group_labels(self):
        res = []
        for c in self.group_items:
            res.append(c.label)
        return(res)

    def get_group(self, ilabel):
        for c in self.group_items:
            if(ilabel == c.label):
                return(c)
        return(None)
        
    
    def set_entity_labels(self, raw_labels, normalize = True):
        for lbl in raw_labels:
            c = lbl
            if(normalize):
                c = re.sub('_O$', '', c)
                c = re.sub('_join$', '', c)
            self.entity_labels.append(c)
    
    def save_hierarchy_report(self, folder):
        for c in self.group_items:
            c.hierarchy_report_path = "hierarchy_report_"+c.label + ".html"
            c.hierarchy_tree_path = "design_tree_" + c.label + ".html"
            logpage = HtmlPage(self.label)
            logpage.css_file = "../../markupstyle.css"
            logpage.js_files.append('../../jquery.min.js')
            logpage.js_files.append('../../xscript.js')
            logpage.put_data(c.internals_check_to_html())
            logpage.write_to_file(os.path.join(folder, c.hierarchy_report_path))
            rsize = float(os.path.getsize(os.path.join(folder, c.hierarchy_report_path))) / float(1024*1024) 
            a = HtmlRef('./' + c.hierarchy_report_path, 'Full Report (click to observe); Caution: File is Large - Opening it will take considerable amount of traffic, time and memory, FileSize = ' + str("%2.2f" % rsize) + " Mbyte")

            c.build_htree()
            c.compute_stat_htree()
            tree_page = HtmlPage(self.label)
            tree_page.css_file = "../../markupstyle.css"
            tree_page.js_files.append('../../jquery.min.js')
            tree_page.js_files.append('../../xscript.js')
            tree_page.put_data(a.to_string())
            tree_page.put_data("<hr><br>")
            tree_page.put_data(c.tree_to_html_table())
            tree_page.write_to_file(os.path.join(folder, c.hierarchy_tree_path))
            
    def save_hierarchy_report_by_failure_mode(self, folder):
        for c in self.failure_mode_group_items:
            c.hierarchy_report_path = "FailureMode_hierarchy_report_"+c.label + ".html"
            c.hierarchy_tree_path = "FailureMode_design_tree_" + c.label + ".html"
            logpage = HtmlPage(self.label)
            logpage.css_file = "../../markupstyle.css"
            logpage.js_files.append('../../jquery.min.js')
            logpage.js_files.append('../../xscript.js')
            logpage.put_data(c.internals_check_to_html())           
            logpage.write_to_file(os.path.join(folder, c.hierarchy_report_path))
            rsize = float(os.path.getsize(os.path.join(folder, c.hierarchy_report_path))) / float(1024*1024) 
            a = HtmlRef('./' + c.hierarchy_report_path, 'Full Report (click to observe); Caution: File is Large - Opening it will take considerable amount of traffic, time and memory, FileSize = ' + str("%2.2f" % rsize) + " Mbyte")
            c.build_htree()
            c.compute_stat_htree()
            tree_page = HtmlPage(self.label)
            tree_page.css_file = "../../markupstyle.css"
            tree_page.js_files.append('../../jquery.min.js')
            tree_page.js_files.append('../../xscript.js')
            tree_page.put_data(a.to_string())
            tree_page.put_data("<hr><br>")
            tree_page.put_data(c.tree_to_html_table())
            tree_page.write_to_file(os.path.join(folder, c.hierarchy_tree_path))



    def save_hierarchy_report_by_target(self, tfolder):
        prefix = "./target_tree_report"
        folder = os.path.join(tfolder, prefix)
        if(not os.path.exists(folder)):
            os.mkdir(folder)
            print("Folder created")
        for c in self.target_group_items:
            c.hierarchy_report_path = "hierarchy_report_"+c.label.replace('/','_') + ".html"
            c.hierarchy_tree_path = "design_tree_" + c.label.replace('/','_') + ".html"
            logpage = HtmlPage(self.label)
            logpage.css_file = "../../../markupstyle.css"
            logpage.js_files.append('../../../jquery.min.js')
            logpage.js_files.append('../../../xscript.js')
            logpage.put_data(c.internals_check_to_html())
            logpage.write_to_file(os.path.join(folder, c.hierarchy_report_path))
            rsize = float(os.path.getsize(os.path.join(folder, c.hierarchy_report_path))) / float(1024*1024) 
            a = HtmlRef('./' + c.hierarchy_report_path, 'Full Report (click to observe); Caution: File is Large - Opening it will take considerable amount of traffic, time and memory, FileSize = ' + str("%2.2f" % rsize) + " Mbyte")
            c.build_htree()
            c.compute_stat_htree()
            tree_page = HtmlPage(self.label)
            tree_page.css_file = "../../../markupstyle.css"
            tree_page.js_files.append('../../../jquery.min.js')
            tree_page.js_files.append('../../../xscript.js')
            tree_page.put_data(a.to_string())
            tree_page.put_data("<hr><br>")
            tree_page.put_data(c.tree_to_html_table())
            tree_page.write_to_file(os.path.join(folder, c.hierarchy_tree_path))
        #create title page with table of contents
        self.hierarchy_content_page_path = "HierarchyReport_" + self.label + ".html"
        ct = HtmlTable(len(self.target_group_items), 3, self.label)
        ct.set_label(0, 'Injection Target (Unit/Reg/Bus...), click to observe error propagation across the Design Tree')
        ct.set_label(1, 'Root Errors, Abs.')
        ct.set_label(2, 'Root Error Rate, %')            
        for i in range(0,len(self.target_group_items), 1):
            item_href = HtmlRef(prefix + "/"+self.target_group_items[i].hierarchy_tree_path, self.target_group_items[i].label)
            ct.put_data(i,0,item_href.to_string())
            ct.put_data(i,1,str(self.target_group_items[i].hroot.error_total))
            ct.put_data(i,2,str("%2.2f" % self.target_group_items[i].hroot.error_rate))            
        contents_page = HtmlPage("Hierarchy report: " + self.label)
        contents_page.css_file = "../../markupstyle.css"
        contents_page.js_files.append('../../jquery.min.js')
        contents_page.js_files.append('../../xscript.js')
        contents_page.put_data(ct.to_string())
        contents_page.write_to_file(os.path.join(tfolder, self.hierarchy_content_page_path))
            
    def clean_items(self ):
        for c in self.group_items:
            c.clean_items()
        for c in self.target_group_items:
            c.clean_items()
        for c in self.failure_mode_group_items:
            c.clean_items() 
        gc.collect()
    

class ICOMPARER:
    def __init__(self, label=""):
        self.detect_failures_at_finish_time = True #True: failure - mismatch of the output results at workload finish time (e.g. memory content), False: failure - mismatch on the outputs at any time point (e.g. output port)
        self.finish_flag_signal = ''
        self.error_flag_signal = ''
        self.error_flag_active_value = ''
        self.trap_type_signal = ''
        self.neg_timegap = float(0)
        self.pos_timegap = float(0)
        self.check_duration_factor = float(0)
        self.label = label
        self.report_label = 'NonameReport'
        self.fmlist = []
        self.genconf = None
        self.scale_factor = float(0)
        self.clk_period = float(0)
        self.reference_dump = None
        self.join_group_list = None
        self.initial_internal_labels = []
        self.initial_output_labels = []
        self.res_file_prefix = "dump_"
        self.report_root = ""
        self.report_conf_dir = ""
        self.dump_dir = ""
        self.exp_description_file = ""
        self.trap_desc_table = None
        self.write_html_dumps = "off"
        self.hierarchical_error_analysis = "off"
        self.dynamic_linking = "off"
        #to be computed internally
        self.dump_file_list = []
        self.desctable = None
        self.config_report = None
        self.prec_logtables = []
        self.activity_intervals = []
        self.effective_switches_intervals = []
        self.logic_dict = {}
        self.normalize_factor = float(1.0)
        self.split_by_profiled_value = ''
        self.sql_connection = None
        self.summarypage = None

    def process_results(self):
        all_instance_types = set()
        all_fault_models = set()
        all_inj_cases = set()
        for i in self.desctable.items:
            all_instance_types.add(i.instance_type)
            all_fault_models.add(i.fault_model)
            all_inj_cases.add(i.injection_case)
        for t in all_instance_types:
            for fm in all_fault_models:
                for ic in all_inj_cases:
                    print 'Deleting existing entries from DB: ' +self.label + ' AND ' + t + ' AND ' + fm  + ' AND ' + ic
                self.sql_connection.cursor().execute('DELETE FROM injections WHERE '+ 'model = \"' + self.label + '\" AND instancetype=\"' + t + '\" AND faultmodel=\"' + fm + '\" AND injectioncase=\"' + ic + '\"')
        self.sql_connection.commit() 
        self.config_report = ConfigReport(self.label)
        self.config_report.set_entity_labels(self.initial_internal_labels, True)
        print "\n\nDESC TABLE ITEMS: " + str(len(self.desctable.items)) + "\n\n"
        print "Scale Factor: " + str( self.scale_factor)
        #print self.desctable.get_by_index(1000).to_string()
        report_folder = os.path.normpath(os.path.join(self.report_root, self.report_conf_dir, "./REPORT"))
        if(not os.path.exists(report_folder)):
            os.mkdir(report_folder)
        html_dump_dir = os.path.join(report_folder, "./html_dumps")
        if(not os.path.exists(html_dump_dir)):
            os.mkdir(html_dump_dir)
        self.reference_dump.to_html(os.path.join(html_dump_dir,"join_reference.html"))            
        #1. Get dump list
        os.chdir(os.path.join(self.report_root, self.report_conf_dir, self.dump_dir))
        dumplist = glob.glob('dump_*')
        dumplist.sort()
        self.config_report.dumpfilesnum = len(dumplist)
        #initilialize HTML log table
        logtable = HtmlTable(len(dumplist), 14, self.label)
        logtable.set_label(0, 'Index')
        logtable.set_label(1, 'Target')
        logtable.set_label(2, 'Fault Model')
        logtable.set_label(3, 'Forced Value')
        logtable.set_label(4, 'Inject. Time')
        logtable.set_label(5, 'Observ. Time')
        logtable.set_label(6, 'Failure (Y/N)')
        logtable.set_label(7, 'Failure Mode')
        logtable.set_label(8, 'Last Solution Correct')
        logtable.set_label(9, 'Number Of Errors')
        logtable.set_label(10, 'Error Mode')
        logtable.set_label(11, 'Trap Code')
        logtable.set_label(12, 'Trap Description')
        logtable.set_label(13, 'Latency Fault to Failure')
       
        index = 0
        basetime = self.reference_dump.vectors[0].time
        for dump in dumplist:
            experiment_index = int(re.findall("dump_([0-9]+)", dump)[0])
            sys.stdout.write("\r%s: Processing dump[%6i]" % (self.label, experiment_index) )            
            sys.stdout.flush()
            inj_dump = simDump()
            inj_dump.set_labels_copy(self.initial_internal_labels, self.initial_output_labels)
            if inj_dump.build_vectors_from_file(dump) == None:
                self.config_report.corrupted_dumps.append(dump)
                continue    # bypass empty (corrupted) file 
            
            report_item = ReportItem()
            report_item.inj_description = self.desctable.get_by_index(experiment_index)

            if self.split_by_profiled_value != 'on':
                report_item.inj_description.profiled_value = ''
            for f in self.fmlist:
                if(f.time_start != f.time_end):
                    if(report_item.inj_description.fault_model == f.model and report_item.inj_description.forced_value == f.forced_value ):
                        inj_start_time = int(genconf.std_workload_time * f.time_start * self.scale_factor)
                        inj_stop_time = int(genconf.std_workload_time * f.time_end * self.scale_factor)
                        if(report_item.inj_description.injection_time >= inj_start_time and report_item.inj_description.injection_time <= inj_stop_time):
                            report_item.inj_description.generic_fault_model = f
            
            drel = report_item.inj_description.max_activity_duration / self.normalize_factor
            for f in range(0,len(self.activity_intervals)-1):
                if(drel >= self.activity_intervals[f] and drel < self.activity_intervals[f+1]):
                    report_item.inj_description.max_activity_relative_from = str(self.activity_intervals[f])
                    report_item.inj_description.max_activity_relative_to = str(self.activity_intervals[f+1])
            if(self.activity_intervals != [] and report_item.inj_description.max_activity_relative_from == ''):
                report_item.inj_description.max_activity_relative_from = str(self.activity_intervals[-1])
                report_item.inj_description.max_activity_relative_to = 'Inf'

            drel = report_item.inj_description.effective_switches / self.normalize_factor
            for f in range(0,len(self.effective_switches_intervals)-1):
                if( drel >= self.effective_switches_intervals[f] and drel < self.effective_switches_intervals[f+1]):
                    report_item.inj_description.effective_switches_from = str(self.effective_switches_intervals[f])
                    report_item.inj_description.effective_switches_to = str(self.effective_switches_intervals[f+1])
            if(self.effective_switches_intervals != [] and report_item.inj_description.effective_switches_from == ''):
                report_item.inj_description.effective_switches_from = str(self.effective_switches_intervals[-1])
                report_item.inj_description.effective_switches_to = 'Inf'            

            if(len(self.logic_dict) > 0):
                report_item.inj_description.logic_group = self.logic_dict.get(report_item.inj_description.instance_type, 'OtherLogic')

            if(report_item.inj_description.injection_time > 0):
                inj_dump.remove_vector(0)
            inj_dump.join_output_columns(self.join_group_list.copy())
            current_dump_name = "join_"+dump + ".html"
            current_dump_path = os.path.join(html_dump_dir, current_dump_name)
            if(self.write_html_dumps == "on"):
                inj_dump.compare_to_html(self.reference_dump, current_dump_path)


            #ANALYSIS            
            #Get vector at finish_time for faulty and reference dumps
            if self.finish_flag_signal != '':
                fin_vect_ref = self.reference_dump.get_first_vector_by_key(self.finish_flag_signal, '1')            
                fin_vect_inj = inj_dump.get_first_vector_by_key(self.finish_flag_signal, '1')
            else:   #if finish flag not present - assume vector at workload finish is the last vector in the dump
                fin_vect_ref = self.reference_dump.vectors[-1]
                fin_vect_inj = inj_dump.get_closest_forward(fin_vect_ref.time)

            if self.detect_failures_at_finish_time == True:
                #Check for failures by finish vector and if present, check for recovery
                if(fin_vect_inj == None): #if there is no vector at/after finish time (model hang) - assume failure
                    self.config_report.corrupted_dumps.append(dump)
                    report_item.failure = True
                    report_item.hang = True
                else:
                    for i in range(0, len(fin_vect_inj.outputs), 1):
                        if(fin_vect_inj.outputs[i] != fin_vect_ref.outputs[i]):
                            report_item.failure = "YES"
                            report_item.last_solution_correct = "YES" if fin_vect_inj.outputs[-1] == fin_vect_ref.outputs[-1] else "NO"
                            break   
                failure_vector = reference_dump.get_first_fail_vector(inj_dump, self.neg_timegap, self.pos_timegap, float(0), basetime + float(report_item.inj_description.injection_time))
            else:
                #check for failures by comparing outputs at all timepoint during workload execution
                failure_vector = reference_dump.get_first_fail_vector(inj_dump, self.neg_timegap, self.pos_timegap, self.check_duration_factor, basetime + float(report_item.inj_description.injection_time))
                if failure_vector != None:
                    report_item.failure = True

                            
            if(report_item.failure):
                if(self.error_flag_signal):
                    if inj_dump.get_forward_by_key(basetime + float(report_item.inj_description.injection_time), self.error_flag_signal, self.error_flag_active_value) != None:
                        report_item.internal_error_detected = True
                        report_item.trap_type = inj_dump.get_value_where(self.trap_type_signal, self.error_flag_signal, self.error_flag_active_value)
                #compute fault to failure latency
                if failure_vector != None:
                    latency = failure_vector.time- basetime - float(report_item.inj_description.injection_time)
                else:
                    latency = 0
                report_item.latency_fault_to_failure = str("%.2f" % latency) if latency > 0 else str("%.2f" % float(0))


            #Compute number of errors comparing vector of internals at finish_time inj==ref
            if fin_vect_inj != None:
                report_item.internal_values_vector = fin_vect_inj.internals
                for i in range(0, len(fin_vect_inj.internals), 1):
                    if(fin_vect_inj.internals[i] != fin_vect_ref.internals[i]):
                        report_item.number_of_errors += 1
                        report_item.check_vector.append(False)
                    else:
                        report_item.check_vector.append(True)

            #Determine failure mode                    
            if(not report_item.failure):
                if(report_item.number_of_errors == 0):
                    report_item.masked_fault = True
                    report_item.failure_mode = "Masked_Fault"
                else:
                    report_item.latent_fault = True
                    report_item.failure_mode = "Latent_Fault"
            else:
                if(report_item.internal_error_detected):
                    report_item.signalled_failure = True
                    report_item.failure_mode = "Signalled_Failure"                    
                else:
                    report_item.silent_data_corruption = True
                    report_item.failure_mode = "Silent_Data_Corruption"                    


            report_item.set_group_name_by_fault_model()
            self.config_report.add_report_item(report_item)
            self.config_report.add_report_item_by_target_group(report_item)
            self.config_report.add_report_item_by_failure_mode(report_item)
            
            if(self.dynamic_linking == 'on'):
                href = HtmlRef("../../dumptrace.py?config="+self.report_label + "&dump=" + dump, str(report_item.inj_description.index))
            else:
                href = HtmlRef("./html_dumps/"+current_dump_name, str(report_item.inj_description.index))
            logtable.put_data(index, 0, href.to_string())
            logtable.put_data(index, 1, report_item.inj_description.target)
            logtable.put_data(index, 2, report_item.inj_description.fault_model)
            logtable.put_data(index, 3, report_item.inj_description.forced_value)
            logtable.put_data(index, 4, str(report_item.inj_description.injection_time))
            logtable.put_data(index, 5, str(report_item.inj_description.observation_time))
            logtable.put_data(index, 6, 'Yes' if report_item.failure else 'N')
            logtable.set_class(index, 0, "fail" if report_item.failure else "pass")
            if   report_item.masked_fault: logtable.put_data(index, 7, 'Masked')
            elif report_item.latent_fault: logtable.put_data(index, 7, 'Latent')
            elif report_item.signalled_failure: logtable.put_data(index, 7, 'Signaled Failure')
            elif report_item.silent_data_corruption: logtable.put_data(index, 7, 'Silent Data Corruption')
            logtable.put_data(index, 8, report_item.last_solution_correct)
            logtable.put_data(index, 9, str(report_item.number_of_errors))
            logtable.put_data(index, 10, 'Yes' if report_item.internal_error_detected else '-')
            logtable.put_data(index, 11, report_item.trap_type)
            tt_desc = ""
            if(trap_desc_table != None):
                tt_item = trap_desc_table.get_by_trap_type(report_item.trap_type)
                if(tt_item != None):
                    tt_desc = tt_item.description
                else:
                    tt_desc = "-"
            logtable.put_data(index, 12, tt_desc)
            logtable.put_data(index, 13, report_item.latency_fault_to_failure)                        

            group = self.config_report.get_group(report_item.group_name)
            if(group.logpage_table == None):
                group.logpage_table = HtmlTable(0, 14, self.label+'_'+group.label)
                group.logpage_table.labels = logtable.labels
            group.logpage_table.add_row(logtable.get_row(index))
            #append to SQL DB
            try:
                sql_query = '''INSERT INTO injections (model, eind, target, instancetype, faultmodel, injectioncase, forcedvalue, injectiontime, injectionduration, observationtime, profiledvalue, failuremode, errorcount, trapcode, latencyfaultfailure, dumpfile, reportlabel)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
                self.sql_connection.cursor().execute(sql_query, (self.label, report_item.inj_description.index, report_item.inj_description.target, report_item.inj_description.instance_type, report_item.inj_description.fault_model, report_item.inj_description.injection_case, report_item.inj_description.forced_value, report_item.inj_description.injection_time, report_item.inj_description.duration, report_item.inj_description.observation_time, report_item.inj_description.profiled_value, report_item.failure_mode, report_item.number_of_errors, report_item.trap_type, None if report_item.latency_fault_to_failure =='-' else float(report_item.latency_fault_to_failure), dump, self.report_label ))
            except Exception as err:
                print('SQL query failed: ' + str(err))
            index += 1

        self.sql_connection.commit()    
        self.config_report.compute_statisctics()
        self.config_report.report_dir = self.report_conf_dir + "./REPORT"
        self.config_report.hlog_path = "report_"+self.report_label+".html"
        logpage = HtmlPage(self.label)
        logpage.css_file = "../../markupstyle.css"
        logpage.js_files.append('../../jquery.min.js')
        logpage.js_files.append('../../xscript.js')        
        logpage.put_data(logtable.to_string())
        config_hlog_path = os.path.join(report_folder, self.config_report.hlog_path)
        logpage.write_to_file(config_hlog_path)
        
        for c in self.config_report.group_items:
            c.logpage_link = "report_" + self.report_label +'_'+ c.label + ".html"
            cpage = HtmlPage(self.label +'_'+ c.label)
            cpage.css_file = "../../markupstyle.css"
            cpage.js_files.append('../../jquery.min.js')
            cpage.js_files.append('../../xscript.js')             
            cpage.put_data(c.logpage_table.to_string())
            cpage.write_to_file(os.path.join(report_folder, c.logpage_link))           


        stat_table = HtmlTable(len(self.config_report.group_items), 7, self.label + " : Statistics")
        stat_table.set_label(0, 'Report Group')
        stat_table.set_label(1, 'Failures / Dumps')
        stat_table.set_label(2, 'Masked Rate, %')
        stat_table.set_label(3, 'Latent Rate, %')
        stat_table.set_label(4, 'Signalled Failure Rate, %')
        stat_table.set_label(5, 'SDC Rate, %')
        stat_table.set_label(6, 'Latency (Fault-Fail): mean / clk')  
        for i in range(0, len(self.config_report.group_items), 1):
            c = self.config_report.group_items[i]
            ls = len(c.report_items)
            stat_table.put_data(i, 0, c.label.replace('-',' & '))
            stat_table.put_data(i, 1, str(c.failure_number) + ' / ' + str(ls))
            stat_table.put_data(i, 2, str('%.2f'%(100*float(c.masked_fault_number)/ls)))
            stat_table.put_data(i, 3, str('%.2f'%(100*float(c.latent_fault_number)/ls)))
            stat_table.put_data(i, 4, str('%.2f'%(100*float(c.signalled_failure_number)/ls)))
            stat_table.put_data(i, 5, str('%.2f'%(100*float(c.silent_data_corruption_number)/ls)))
            stat_table.put_data(i, 6, str('%.2f'%(c.fault_to_failure_latency_mean/(float(self.clk_period)) )))
        summarypage.put_data(stat_table.to_string() + "<br><hr><br>")


        if(hierarchical_error_analysis == "on"):
            self.config_report.save_hierarchy_report(report_folder)
            #self.config_report.save_hierarchy_report_by_target(report_folder)
            self.config_report.save_hierarchy_report_by_failure_mode(report_folder)
            print(self.config_report.target_group_items_to_string())
        self.config_report.clean_items()
        

class MatchItem:
    def __init__(self, itemlist=None):
        self.target = ""
        self.failure_mode = []
        self.match = True
        self.index = int(0)
        self.build(itemlist)
    
    def build(self, itemlist):
        if(itemlist != None):
            self.target = itemlist[0].inj_description.target
            self.index = itemlist[0].inj_description.index
            for t in itemlist:
                self.failure_mode.append(t.failure_mode)
            for i in range(0, len(self.failure_mode), 1):
                if(self.failure_mode[0] != self.failure_mode[i]):
                    self.match = False
                    break

class MatchTable:
    def __init__(self):
        self.items = []
        self.labels = []
        
    def add_label(self, label):
        self.labels.append(label)
        
    def put(self, itemlist):
        self.items.append(MatchItem(itemlist))
    
    def get_size(self):
        return(len(self.items))
    
    def get_match_number(self):
        res = 0
        for c in self.items:
            if(c.match == True):
                res += 1
        return(res)
    
    def ToHtml(self):
        res = HtmlTable(len(self.items), len(self.labels)+2, "Behavior match")
        res.set_label(0, "Num (Index)")
        res.set_label(1, "Target")
        for i in range(0, len(self.labels), 1):
            res.set_label(i+2, self.labels[i])
        for row in range(0, len(self.items), 1):
            if(self.items[row].match == False):
                res.set_class(row, 0, "fail")
            else:
                res.set_class(row, 0, "pass")            
            res.put_data(row, 0, str(row) + " (" + str(self.items[row].index) + ")")
            res.put_data(row, 1, self.items[row].target)
            for column in range(0, len(self.labels), 1):
                res.put_data(row, column+2, self.items[row].failure_mode[column])
        return(res)




time_start = datetime.datetime.now().replace(microsecond=0)
timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S')
call_dir = os.getcwd()


config_file_path = os.path.join(os.getcwd(), sys.argv[1])
print "CONFIG PATH: " + config_file_path
#1. Parse configuration file
normconfig = config_file_path.replace('.xml','_normalized.xml')
normalize_xml(config_file_path, normconfig)
xml_conf = ET.parse(normconfig)
tree = xml_conf.getroot()
genconf = GenConfig(tree.findall('Generic')[0])
print genconf.to_string()
#Tool Options are kept by-default if this tag is not present in config.xml
toolconf = ToolOptions()
tool_tags = tree.findall('ToolOptions')
if(len(tool_tags)>0):
    toolconf = ToolOptions(tool_tags[0])
print(toolconf.to_string())


fmlist = []
for c in tree.findall('fault_injection')[0].findall('fault_model'):
    fmlist.append(FaultModelConfig(c))

#task options
tasknode = tree.findall('analysis')[0].findall('task')[0]
unpack_from_dir = tasknode.get('unpack_from_dir','')
report_dir = resolve_path(call_dir, tasknode.get('report_dir'))
if not os.path.exists(report_dir):
    os.makedirs(report_dir)
copy_all_files(os.path.join(call_dir,'interface'), report_dir)

write_html_dumps = tasknode.get('write_html_dumps')
dynamic_linking = tasknode.get('dynamic_linking')
hierarchical_error_analysis = tasknode.get('hierarchical_error_analysis')
trap_types_description_file = tasknode.get('trap_types_description_file','')
split_by_time_intervals = tasknode.get('split_by_time_intervals','')
memory_saving_mode = tasknode.get('memory_saving_mode','')
split_by_activity_duration_interval   = tasknode.get('split_by_activity_duration_interval','')
split_by_effective_switches_intervals = tasknode.get('split_by_effective_switches_intervals','')
split_by_logic_type = tasknode.get('split_by_logic_type','')
normalize_by_workload_duration = tasknode.get('normalize_by_workload_duration','')
split_by_profiled_value = tasknode.get('split_by_profiled_value','')
default_logic_type = tasknode.get('default_logic_type','Other')
model_lable_append_prefix = tasknode.get('model_lable_append_prefix','')
report_lable_append_prefix = tasknode.get('report_lable_append_prefix','')

#options for factorial configurations
parconflist = []
for xnode in tree.findall('config'):
    parconflist.append(ParConfig(xnode))
for c in parconflist:
    c.work_dir = resolve_path(call_dir, c.work_dir)
    c.report_label = report_lable_append_prefix + model_lable_append_prefix + c.label
    c.report_dir = os.path.join(report_dir, c.report_label)
    print c.to_string()      
    
#trap codes descriptors if any
trap_desc_table = None
if(trap_types_description_file != ''):
    trap_desc_table = TrapDescriptionTable()
    trap_desc_table.build_from_file(resolve_path(call_dir, trap_types_description_file))
    print "\n\nExceptions table: " + trap_desc_table.to_string()

#Descriptors for renaming signals in dump file
rename_list = []
renamelistnode = tree.findall('analysis')[0].findall('rename_list')[0]
for c in renamelistnode.findall('item'):
    x = RenameItem(c.get('from'), c.get('to'))
    rename_list.append(x)
for c in rename_list:
    print(c.to_string())

#Descriptors for merging signals in dump file
join_group_list = JoinGroupList()
join_group_list.init_from_tag(tree.findall('analysis')[0].findall('join_groups')[0])
print join_group_list.to_str()


if(dynamic_linking == 'on'):
    shutil.copyfile(os.path.join(call_dir, 'dumptrace.py'),os.path.join(report_dir, 'dumptrace.py'))
    shutil.copyfile(normconfig, os.path.join(report_dir, 'config.xml'))    


#Create sqLite DB
dbpath = os.path.join(report_dir, "Results_SQL.db")
#if os.path.exists(dbpath): os.remove(dbpath)
connection = sqlite3.connect(dbpath)
cursor = connection.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type=\'table\' AND name=\'injections\';')
#if table not exists - create it, otherwise, append to already existing
if len(cursor.fetchall()) == 0:
    sql_command = """
    CREATE TABLE injections (
    model VARCHAR(255), 
    eind INTEGER,
    target VARCHAR(255),
    instancetype VARCHAR(255),
    faultmodel VARCHAR(255),
    injectioncase VARCHAR(255),
    forcedvalue VARCHAR(10),
    injectiontime REAL,
    injectionduration REAL,
    observationtime REAL,
    profiledvalue VARCHAR(20),
    failuremode VARCHAR(100),
    errorcount INTEGER,
    trapcode VARCHAR(255),
    latencyfaultfailure REAL, 
    dumpfile VARCHAR(255),
    reportlabel VARCHAR(255));"""
    cursor.execute(sql_command)
    connection.commit()



REPORTS = []
group_labels = []
stat_tables = dict()
trap_tables = dict()
debug_table = HtmlTable(len(parconflist), 4, " : Debug Info")
debug_table.set_label(0, 'Configuration')
debug_table.set_label(1, 'Corrupted dumps (bypassed)')
debug_table.set_label(2, 'Experiments planned')
debug_table.set_label(3, 'Experiments completed')

summarypage = HtmlPage("index.html")
summarypage.js_files.append('jquery.min.js')
summarypage.js_files.append('xscript.js')  
summarypage.css_file = "markupstyle.css"


index = 0
for conf in parconflist:
    #Unpack results
    print 'Unpacking results'
    if(not os.path.exists(conf.report_dir)):
        os.mkdir(conf.report_dir)
    src_path = ''
    if(unpack_from_dir != ''):
        unpack_list = glob.glob(os.path.join(resolve_path(call_dir, unpack_from_dir),'*.zip'))
    else:
        unpack_list = glob.glob(os.path.join(conf.work_dir,'*.zip'))
    for p in unpack_list:
        if(p.find(conf.label) >= 0):
            src_path = p
            break
    if(src_path == ''):
        print 'Error: No zip file found for: ' + conf.label
        key = raw_input('...')    
    unpack_script = 'unzip -o \"' + src_path + "\" \"" + toolconf.list_init_file.replace('./','') + "\" \"" + toolconf.result_dir.replace('./','') + "/*\" -d \"" + conf.report_dir + "\" > " + os.path.join(conf.report_dir,'unzip_log.txt')
    print 'Unpacking: ' + unpack_script
    proc = subprocess.Popen(unpack_script, shell=True)
    proc.wait()
    conf.label = model_lable_append_prefix + conf.label

    #Update comparator
    mcomp = ICOMPARER(conf.label)
    mcomp.report_label = conf.report_label 
    mcomp.genconf = genconf
    mcomp.scale_factor = float(conf.clk_period) / float(genconf.std_clk_period)
    mcomp.clk_period = float(conf.clk_period)
    mcomp.detect_failures_at_finish_time = True if tasknode.get('detect_failures_at_finish_time','') == 'on' else False
    mcomp.finish_flag_signal = tasknode.get('finish_flag_signal','')
    mcomp.error_flag_signal = tasknode.get('error_flag_signal','')
    mcomp.error_flag_active_value = tasknode.get('error_flag_active_value','')
    mcomp.trap_type_signal = tasknode.get('trap_type_signal','')
    mcomp.neg_timegap = float(tasknode.get('neg_timegap','0'))
    mcomp.pos_timegap = float(tasknode.get('pos_timegap','0'))
    mcomp.check_duration_factor = float(tasknode.get('check_duration_factor','0'))
    mcomp.sql_connection = connection
    mcomp.summarypage = summarypage

    if(split_by_time_intervals == 'on'): mcomp.fmlist = fmlist
    if(split_by_activity_duration_interval != ''):
        if normalize_by_workload_duration == 'on':
            mcomp.normalize_factor = (float(genconf.std_workload_time)*mcomp.scale_factor)
        xint = split_by_activity_duration_interval.split(' ')
        for i in xint:
            mcomp.activity_intervals.append(float(i))
    if(split_by_effective_switches_intervals != ''):
        if normalize_by_workload_duration == 'on':
            mcomp.normalize_factor = (float(genconf.std_workload_time) / float(genconf.std_clk_period))        
        xint = split_by_effective_switches_intervals.split(' ')
        for i in xint:
            mcomp.effective_switches_intervals.append(float(i))
    for i in  mcomp.effective_switches_intervals:
        print 'sw: ' + str(i)
    if(split_by_logic_type != ''):
        for i in split_by_logic_type.split(','):
            xi = i.replace(' ','').split(':')
            mcomp.logic_dict[xi[0]] = xi[1]
            
    mcomp.split_by_profiled_value = split_by_profiled_value

    mcomp.report_root = report_dir
    mcomp.report_conf_dir = './'+conf.report_label
    mcomp.dump_dir = toolconf.result_dir
    mcomp.write_html_dumps = write_html_dumps
    mcomp.dynamic_linking = dynamic_linking
    mcomp.hierarchical_error_analysis = hierarchical_error_analysis    
    #Process results
    reference_dump = simDump()
    reference_dump.build_labels_from_file(os.path.normpath(os.path.join(report_dir, './'+conf.report_label, toolconf.list_init_file)), rename_list)
    reference_dump.build_vectors_from_file(os.path.normpath(os.path.join(report_dir, './'+conf.report_label, toolconf.result_dir, toolconf.reference_file)))
    mcomp.trap_desc_table = trap_desc_table
    mcomp.reference_dump = reference_dump
    mcomp.join_group_list = join_group_list.copy()
    mcomp.initial_internal_labels, mcomp.initial_output_labels = reference_dump.get_labels_copy()
    mcomp.reference_dump.join_output_columns(join_group_list)
    mcomp.desctable = ExpDescTable(conf.label)
    mcomp.desctable.build_from_csv_file(os.path.join(mcomp.report_root, mcomp.report_conf_dir, mcomp.dump_dir, "_summary.csv"), default_logic_type)
    mcomp.desctable.normalize_targets()
    
    
    #mcomp.desctable.filter('profiled_value',filter_by_profiled_value)
    
    
    mcomp.process_results()
    c = mcomp.config_report
    c.config = conf

    if(memory_saving_mode != 'on'):
        REPORTS.append(c)

    logpage = HtmlPage("main_index.html")
    logpage.css_file = "markupstyle.css"
    debug_table.put_data(index, 0, conf.label)
    debug_table.put_data(index, 1, str(len(c.corrupted_dumps)))
    debug_table.put_data(index, 2, str(len(mcomp.desctable.items)))
    debug_table.put_data(index, 3, str(c.dumpfilesnum))

    if(group_labels == [] ):
        group_labels = c.get_group_labels()
        for gl in group_labels:
            stat_table = HtmlTable(len(parconflist), 21, gl + " : Statistics")
            trap_table = HtmlTable(1, len(parconflist), gl + " : Sorted Trap List")
            stat_tables[gl] = stat_table
            trap_tables[gl] = trap_table
            stat_table.set_label(0, 'Configuration')
            stat_table.set_label(1, 'Error Rate (Root)')
            stat_table.set_label(2, 'Failures / Dumps')
            stat_table.set_label(3, 'Model Hang')
            stat_table.set_label(4, 'IU Error Mode Detected')
            stat_table.set_label(5, 'Masked Faults')
            stat_table.set_label(6, 'Latent Faults')
            stat_table.set_label(7, 'Signalled Failures')
            stat_table.set_label(8, 'Silent Data Corruption')
            stat_table.set_label(9, 'Error Asserted, %')
            stat_table.set_label(10, 'Failure Rate, %')
            stat_table.set_label(11, 'Masked Rate, %')
            stat_table.set_label(12, 'Latent Rate, %')
            stat_table.set_label(13, 'Signalled Failure Rate, %')
            stat_table.set_label(14, 'SDC Rate, %')
            stat_table.set_label(15, 'Design tree, Masked')
            stat_table.set_label(16, 'Design tree, Latent')
            stat_table.set_label(17, 'Design tree, Signalled')
            stat_table.set_label(18, 'Design tree, SDC')
            stat_table.set_label(19, 'Latency (Fault-Fail): mean : min : max')
            stat_table.set_label(20, 'Latency (Fault-Fail): mean / clk')  
    for gl in group_labels:
        stat_table = stat_tables[gl]
        trap_table = trap_tables[gl]
        d = c.get_group(gl)
        silent_group = None
        latent_group = None
        signalled_group = None
        not_signalled_group = None
        for x in c.failure_mode_group_items:
            clbl = x.label.split('+')
            if((clbl[0] == d.label) and (clbl[1] == "Masked") ):
                silent_group = x
            elif((clbl[0] == d.label) and (clbl[1] == "Latent") ):
                latent_group = x
            elif((clbl[0] == d.label) and (clbl[1] == "Signalled") ):
                signalled_group = x
            elif((clbl[0] == d.label) and (clbl[1] == "NotSignalled") ):
                not_signalled_group = x

        silent_tree_href = None
        latent_tree_href = None
        signalled_tree_href = None
        not_signalled_tree_href = None                
        if(hierarchical_error_analysis == "on"):
            if(silent_group != None): silent_tree_href = HtmlRef(c.report_dir + "/"+ silent_group.hierarchy_tree_path, str("%2.2f" % silent_group.root_error_rate) + "%")
            if(latent_group != None): latent_tree_href = HtmlRef(c.report_dir + "/"+ latent_group.hierarchy_tree_path, str("%2.2f" % latent_group.root_error_rate) + "%")
            if(signalled_group != None): signalled_tree_href = HtmlRef(c.report_dir + "/"+ signalled_group.hierarchy_tree_path, str("%2.2f" % signalled_group.root_error_rate) + "%")
            if(not_signalled_group != None): not_signalled_tree_href = HtmlRef(c.report_dir + "/"+ not_signalled_group.hierarchy_tree_path, str("%2.2f" % not_signalled_group.root_error_rate) + "%")

        href = HtmlRef( c.report_dir + "/"+d.logpage_link, c.label)
        stat_table.put_data(index, 0, href.to_string())
        htree_href = HtmlRef(c.report_dir + "/" + d.hierarchy_tree_path, str("%2.2f" % d.root_error_rate) + "%")
        if(hierarchical_error_analysis == "on"):
            stat_table.put_data(index, 1, htree_href.to_string())
        else:
            stat_table.put_data(index, 1, "disabled")            
        stat_table.put_data(index, 2, str(d.failure_number) + " / " + str(len(d.report_items)))
        stat_table.put_data(index, 3, str(d.hang_number))
        stat_table.put_data(index, 4, str(d.internal_error_detected_number))
        stat_table.put_data(index, 5, str(d.masked_fault_number))
        stat_table.put_data(index, 6, str(d.latent_fault_number))
        stat_table.put_data(index, 7, str(d.signalled_failure_number))
        stat_table.put_data(index, 8, str(d.silent_data_corruption_number))
        stat_table.put_data(index, 9, str("%2.2f" % d.internal_error_detected_rate) + "%")
        stat_table.put_data(index, 10, str("%2.2f" % d.failure_rate) + "%")
        group_size = len(d.report_items)
        stat_table.put_data(index, 11, str(str("%2.2f" % (100.0* float(d.masked_fault_number) / float(group_size)))) + "%")        
        stat_table.put_data(index, 12, str(str("%2.2f" % (100.0* float(d.latent_fault_number) / float(group_size)))) + "%")           
        stat_table.put_data(index, 13, str(str("%2.2f" % (100.0* float(d.signalled_failure_number) / float(group_size)))) + "%")        
        stat_table.put_data(index, 14, str(str("%2.2f" % (100.0* float(d.silent_data_corruption_number) / float(group_size)))) + "%")        
        if(hierarchical_error_analysis == "on"):
            if(silent_tree_href != None):
                stat_table.put_data(index, 15, silent_tree_href.to_string())
            if(latent_tree_href != None):
                stat_table.put_data(index, 16, latent_tree_href.to_string())
            if(signalled_tree_href != None):
                stat_table.put_data(index, 17, signalled_tree_href.to_string())        
            if(not_signalled_tree_href != None):
                stat_table.put_data(index, 18, not_signalled_tree_href.to_string())
        else:
            stat_table.put_data(index, 15, "disabled")        
            stat_table.put_data(index, 16, "disabled")        
            stat_table.put_data(index, 17, "disabled")        
            stat_table.put_data(index, 18, "disabled")            
        stat_table.put_data(index, 19,  str("%.2f" %(d.fault_to_failure_latency_mean)) + " (" + str("%.2f" %(d.fault_to_failure_latency_min)) + " : " + str("%.2f" %(d.fault_to_failure_latency_max)) + ")" )
        stat_table.put_data(index, 20,  str("%.2f" %(d.fault_to_failure_latency_mean / (float(c.config.clk_period)))  ))        
        print c.config.label + " - Latency: " + str("%.2f" %d.fault_to_failure_latency_mean) + " / " + str("%.2f" % (float(c.config.clk_period)))
        trap_table.set_label(index, href.to_string())
        trap_table.put_data(0, index, d.trap_list_to_string(trap_desc_table))
        
        logpage.put_data(stat_table.to_string() + "<br>")
        logpage.put_data(trap_table.to_string() + "<br>")
        logpage.put_data("<hr><br>")
    logpage.put_data(debug_table.to_string() + "<br>")
    os.chdir(report_dir)
    logpage.js_files.append('jquery.min.js')
    logpage.js_files.append('xscript.js')  
    logpage.write_to_file("main_index.html")
    index += 1
    #pack /iresults folder to zip and remove it
    zip_folder(os.path.join(mcomp.report_root, mcomp.report_conf_dir), toolconf.result_dir)
    shutil.rmtree(os.path.join(mcomp.report_root, mcomp.report_conf_dir, toolconf.result_dir))
    summarypage.write_to_file("index.html")

#Make query interface
with open(os.path.join(report_dir,'query.html'),'r+') as f:
    content = f.read()
    f.seek(0)
    buf = ''
    cursor.execute('SELECT DISTINCT model from injections')
    for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    content = content.replace('_#qmodel', buf + '\n\t<option value=\"\">ANY</option>')

    buf = ''
    cursor.execute('SELECT DISTINCT faultmodel from injections')
    for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    content = content.replace('_#qfaultmodel', buf + '\n\t<option value=\"\">ANY</option>')

    buf = ''
    cursor.execute('SELECT DISTINCT injectioncase from injections')
    for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    content = content.replace('_#qinjectioncase', buf + '\n\t<option value=\"\">ANY</option>')

    buf = ''
    cursor.execute('SELECT DISTINCT forcedvalue from injections')
    for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    content = content.replace('_#qforcedvalue', buf + '\n\t<option value=\"\">ANY</option>')

    buf = '\n\t<option value=\"\">ANY</option>'
    #cursor.execute('SELECT DISTINCT failuremode from injections')
    #for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    for c in ['Masked_Fault', 'Latent_Fault', 'Signalled_Failure', 'Silent_Data_Corruption']: buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
    content = content.replace('_#qfailuremode', buf)

    buf = ''
    cursor.execute('SELECT DISTINCT instancetype from injections')
    for c in cursor.fetchall(): buf += '\n\t<option value=\"' + str(c[0]) + '\">'+ str(c[0]) + '</option>'
    content = content.replace('_#qinstancetype', buf + '\n\t<option value=\"\">ANY</option>')

    cursor.execute('SELECT DISTINCT eind from injections ORDER BY eind')
    res = cursor.fetchall()
    content = content.replace('_#qeind', str(res[0][0]) + ' : ' + str(res[-1][0]))
    f.write(content)
    f.truncate()

connection.close()
time_stop = datetime.datetime.now().replace(microsecond=0)
time_taken = time_stop - time_start
print "\tTIME TAKEN: " + str(time_taken)