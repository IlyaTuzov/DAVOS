# A tool implementing full/fractional factorial design for Xilinx ISE design Suite
# Launch format: python Implement_Xil.py config.xml
# where config.xml - custom configuration of DSE flow
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import subprocess
import shutil
import string
import copy
import time
from multiprocessing import Process, Manager
from multiprocessing.managers import BaseManager
import glob
from subprocess import call
from sys import platform

class Table:
    def __init__(self, name):
        self.name = name
        self.columns = []
        self.labels = []
  
    def rownum(self):
        if(len(self.columns) > 0):
            return(len(self.columns[0]))
        else:
            return(0)
    
    def colnum(self):
        return(len(self.columns))
    
    
    def add_column(self, lbl):
        self.columns.append([])
        self.labels.append(lbl)
        

    def add_row(self, idata=None):
        if(idata!=None):
            if(len(idata) == self.colnum()):
                for c in range(0, len(self.columns), 1):
                    self.columns[c].append(idata[c])
            else:
                print "Warning: Building Table - line size mismatch at add_row(): " + str(len(idata)) + " <> " + str(self.colnum())
        else:
            for c in self.columns:
                c.append("")
            
                        
    def put(self, row, col, data):
        if( col < len(self.columns) ):
            if( row < len(self.columns[0]) ):
                self.columns[col][row] = data
            else:
                print("Table: "+self.name + " : put data: " + str(data) + " : Row index " + str(row) + " not defined")
        else:
            print("Table: "+self.name + " : put data: " + str(data) + " : Column index " + str(col) + " not defined")
            
    def get(self, row, col):
        if( col < len(self.columns) ):
            if( row < len(self.columns[col]) ):
                return(self.columns[col][row])
            else:
                print("Table: "+self.name + " : put data: " + str(data) + " : Row index " + str(row) + " not defined")
        else:
            print("Table: "+self.name + " : put data: " + str(data) + " : Column index " + str(col) + " not defined")
        return("")
    
    def to_csv(self):
        res = "sep=;\n"
        for l in self.labels:
            res += l+";"
        nc = len(self.columns)
        nr = len(self.columns[0])
        for r in range(0, nr, 1):
            res+="\n"
            for c in range(0, nc, 1):
                res+=str(self.get(r,c))+";"
        return(res)

    def to_xml(self, tagname = 'Item'):
        res = "<?xml version=\"1.0\"?>\n<data>\n"
        for r in range(0, self.rownum(), 1):
            res += '\n\n<' + tagname
            for c in range(0, self.colnum(), 1):
                res += '\n\t' + self.labels[c] + '=\"' + self.get(r, c) + '\"'
            res += '/>'
        res += "\n</data>"
        return(res)
    
    def snormalize(self, ist):
        if(ist[-1]=="\r" or ist[-1]=="\n"):
            del ist[-1]
        return ist
    
    def build_from_csv(self, fname):
        fdesc = open(fname, 'r')
        content = fdesc.read()
        fdesc.close()
        lines = string.split(content,'\n')
        itemsep = re.findall("sep\s*?=\s*?([;,]+)", lines[0])[0]
        labels = self.snormalize(lines[1].rstrip(itemsep).split(itemsep))
        for l in labels:
            self.add_column(l)
        for i in range(2, len(lines), 1):
            c = self.snormalize(lines[i].rstrip(itemsep).split(itemsep))
            self.add_row(c)
        
#------------------------------------------------------------------------------------
class IOption:
    def __init__(self, name, value = ""):
        self.name = name    #power, opt_mode....
        self.value = value  #No/Yes, Speed/Area...

class IFactor:
    def __init__(self, ifactor_name, ioption_name="", iphase = ""):
        self.factor_name = ifactor_name #X1....X31
        self.option_name = ioption_name #power, opt_mode
        self.phase = iphase #synthesis/translate/map/par
        self.option_values = dict()   #option_value[X.value]=Speed
    
    def add_setting(self, ifactor_value, ioption_value):
        self.option_values[ifactor_value] = ioption_value
    
    def to_string(self):
        res = "Factor: " + self.factor_name + "\tOption: " + self.option_name + "\tPhase: " + self.phase
        for k, v in self.option_values.items():
            res += "\n\t"+str(k) + " : " + str(v)
        return(res)

class IFactorialConfiguration:
    def __init__(self, ilabel):
        self.label = ilabel
        self.synthesis = [] #Ioption
        self.translate = []
        self.map = []
        self.par = []
        self.genconf = None
        #-------------------
        self.factor_setting = []
        self.table_index  = int(-1)
        self.synthesis_log = None
        self.translate_log = None
        self.map_log = None
        self.par_log = None
        self.synthesis_netlist_log = None
        self.map_netlist_log = None
        self.par_netlist_log = None        
        self.trace_report = None
        self.es_power_report = None
        self.saif_power_report = None
        
        
    def to_string(self):
        res = "Options Confugiration: " + self.label
        res += "\n\tSynthesis:"
        for c in self.synthesis:
            res += "\n\t\t"+ c.name + " = " + c.value
        res += "\n\tTranslate:"
        for c in self.translate:
            res += "\n\t\t"+ c.name + " = " + c.value
        res += "\n\tMAP:"
        for c in self.map:
            res += "\n\t\t"+ c.name + " = " + c.value
        res += "\n\tPAR:"
        for c in self.par:
            res += "\n\t\t"+ c.name + " = " + c.value
        return(res)
    
    def mcopy(self, ilabel):
        res = IFactorialConfiguration(ilabel)
        res.synthesis = copy.deepcopy(self.synthesis)
        res.translate = copy.deepcopy(self.translate)
        res.map = copy.deepcopy(self.map)
        res.par = copy.deepcopy(self.par)
        res.genconf = self.genconf
        res.build_log_desc()
        return(res)

    def build_log_desc(self):
        self.synthesis_log = self.genconf.log_dir + "/_synthesis.log"
        self.translate_log = self.genconf.log_dir + "/_translate.log"
        self.map_log = self.genconf.log_dir + "/_map.log"
        self.par_log = self.genconf.log_dir + "/_par.log"
        self.synthesis_netlist_log = self.genconf.log_dir + "/_post_synt_netlist.log"
        self.map_netlist_log = self.genconf.log_dir + "/_map_netlist_log.log"
        self.par_netlist_log = self.genconf.log_dir + "/_par_netlist_log.log"        
        self.fuse_log = self.genconf.log_dir + "/" + "fuse_log.log"
        self.isim_log = self.genconf.log_dir + "/" + "isim_log.log"
        self.trace_report = self.genconf.log_dir + "/" + "timing.twr"
        self.es_power_report = self.genconf.log_dir + "/estimated_power_" + self.genconf.top_design_unit + ".pwr"
        self.saif_power_report = self.genconf.log_dir + "/SAIF_" + self.genconf.top_design_unit + ".pwr"

    
    def get_option_by_name(self, iname, iphase):
        if(iphase == "synthesis"):
            for c in self.synthesis:
                if(c.name == iname):
                    return(c)
        elif(iphase == "translate"):
            for c in self.translate:
                if(c.name == iname):
                    return(c)
        elif(iphase == "map"):
            for c in self.map:
                if(c.name == iname):
                    return(c)
        elif(iphase == "par"):
            for c in self.par:
                if(c.name == iname):
                    return(c)
        else:
            print "Error: get_option_by_name: \"" + iphase +"\" phase not found"
            sys.exit(0)
        return(None)
    
    def get_xst_file_name(self):
        return(self.genconf.top_design_unit + ".xst")
    
    def get_xst_file_content(self):
        res = "\nrun"
        for c in self.synthesis:
            res += "\n-"+c.name + " " + c.value
        return(res + "\n")
    
    def get_synthesis_script(self):
        #self.synthesis_log = self.genconf.log_dir + "/_synthesis.log"
        res = "xst -intstyle " + self.genconf.intstyle + " -ifn \"./" + self.get_xst_file_name() + "\" -ofn \"" +self.genconf.log_dir + "/"+self.genconf.top_design_unit+".syr\" > " + self.synthesis_log
        return(res)
    
    def get_translate_script(self):
        #self.translate_log = self.genconf.log_dir + "/_translate.log"
        res = "ngdbuild "
        for c in self.translate:
            if(c.value.find('!-') < 0):
                if(c.name.replace(' ', '').replace('\t','') != ""):
                    res += " -" + c.name
                    if(c.value.find('!+') < 0): res += " " + c.value
                else:
                    res += " " + c.value
        res += " > " + self.translate_log
        return(res)

    def get_map_script(self):
        #self.map_log = self.genconf.log_dir + "/_map.log"
        res = "map "
        for c in self.map:
            if(c.value.find('!-') < 0):
                if (c.name.replace(' ', '').replace('\t','') != ""):
                    res += " -" + c.name
                    if(c.value.find('!+') < 0): res += " " + c.value
                else:
                    res += " " + c.value
        res += " > " + self.map_log
        return(res)       
    
    def get_par_script(self):
        #self.par_log = self.genconf.log_dir + "/_par.log"
        if self.genconf.ise_path != "":
            res = os.path.join(self.genconf.ise_path, 'ISE/bin/nt64/par.exe' ) + " -w "
        else:
            res = "par -w "
        for c in self.par:
            if(c.value.find('!-') < 0):
                if(c.name.replace(' ', '').replace('\t','') != ""):
                    res += " -" + c.name
                    if(c.value.find('!+') < 0): res += " " + c.value
                else:
                    res += " " + c.value
        res += " > " + self.par_log
        return(res)
    
    #phase = synthesis / map / par
    def get_netgen_script(self, phase):
        res = "netgen -intstyle " + self.genconf.intstyle + " " + self.genconf.basic_netgen_options
        if(phase == "synthesis"):
            res += "-dir " + self.genconf.netlist_dir + "/synthesis " + "-sim " + self.genconf.top_design_unit + ".ngc " + "_synthesis.vhd > " + self.synthesis_netlist_log
#            res += "-dir " + self.genconf.netlist_dir + "/synthesis " + "-sim " + self.genconf.top_design_unit + ".ngc " + "_synthesis.v > " + self.synthesis_netlist_log

        elif(phase == "map"):
            res += "-dir " + self.genconf.netlist_dir + "/map " + "-pcf " + self.genconf.top_design_unit + ".pcf " + "-sim " + self.genconf.top_design_unit + "_map.ncd " + "_map.vhd > " + self.map_netlist_log
#            res += "-dir " + self.genconf.netlist_dir + "/map " + "-pcf " + self.genconf.top_design_unit + ".pcf " + "-sim " + self.genconf.top_design_unit + "_map.ncd " + "_map.v > " + self.map_netlist_log
        elif(phase == "par"):
            res += "-dir " + self.genconf.netlist_dir + "/par " + "-pcf " + self.genconf.top_design_unit + ".pcf" + " -tb" + " -insert_pp_buffers true " + "-sim " + self.genconf.top_design_unit + ".ncd " + "_timesim.vhd > " + self.par_netlist_log
#            res += "-dir " + self.genconf.netlist_dir + "/par " + "-pcf " + self.genconf.top_design_unit + ".pcf" + " -tb" + " -insert_pp_buffers true " + "-sim " + self.genconf.top_design_unit + ".ncd " + "_timesim.v > " + self.par_netlist_log
        else:
            print "get_netgen_script: undefined phase " + phase
        return(res)
            
    def get_trace_script(self):
        res = "trce -intstyle " + self.genconf.intstyle + " -v 3 -n 3 -s " + self.genconf.speed_grade + " -fastpaths -xml " + self.genconf.top_design_unit + ".twx " + self.genconf.top_design_unit + ".ncd -o " + self.trace_report + " " + self.genconf.top_design_unit + ".pcf" + " -ucf " + self.genconf.constraint_file + " > " + self.genconf.log_dir + "/trace.log"
        return(res)
    
    def get_es_power_script(self):
        res = "xpwr -intstyle " + self.genconf.intstyle + " " + self.genconf.top_design_unit + ".ncd " + self.genconf.top_design_unit + ".pcf" + " -o " + self.es_power_report + " > " + self.genconf.log_dir + "/xpower_log.log"
        return(res)
    
class IFactorialDesign:
    def __init__(self):
        self.configurations = [] #IFactorialConfiguration
        
    def append_configuration(self, config):
        self.configurations.append(config)

    def get_by_label(self, label):
        for c in self.configurations:
            if c.label == label:
                return(c)
        return(None)
    
    def to_string(self):
        res = "\n\t\t\tCONFIGURATIONS"
        for c in self.configurations:
            res += "\n\n\n\tLABEL: " + c.label
            res += "\n" + c.get_xst_file_content()
            res += "\nSynthesis_script: " + c.get_synthesis_script()
            res += "\nTranslate_script: " + c.get_translate_script()
            res += "\nMap_script: " + c.get_map_script()
            res += "\nPar_script: " + c.get_par_script()
            res += "\nNetgen_Synt_script: " + c.get_netgen_script("synthesis")
            res += "\nNetgen_Map_script: " + c.get_netgen_script("map")
            res += "\nNetgen_Par_script: " + c.get_netgen_script("par")
            res += "\nTrace_script: " + c.get_trace_script()            
        return(res)
            
    
class GenericConfig:
    def __init__(self, itag=None):
        self.ise_path = ""
        self.device = ""
        self.speed_grade = ""
        self.top_design_unit = ""
        self.intstyle = ""
        self.ifn = ""
        self.constraint_file = ""
        self.clk_net = ""
        self.rst_net = ""
        self.clk_initial_period = 0.0
        self.clk_adjustment_delta = 0.0
        self.design_label = ""
        self.relative_path = ""
        self.design_dir = ""
        self.template_dir = ""
        self.log_dir = ""
        self.netlist_dir = ""
        self.basic_netgen_options = ""
        self.rpw_tpw = ""
        self.generic_constraint_file = ""
        self.generic_constraint_content = ""
        self.tool_log_dir = ""
        self.testbench_template_file = ""
        self.sim_project_file = ""
        self.testbench_file = ""
        self.testbench_top_unit = ""
        self.clk_constant = ""
        self.uut_root = ""
        self.std_start_time = float(0.0)
        self.std_observation_time = float(0.0)
        self.std_clock_period = float(0.0)
        self.isim_gui = ""
        self.waveform_file = ""
        self.statfile = "XIStat.xml"
        if(itag!=None):
            self.build_from_xml(itag)
    
    def build_from_xml(self, itag):
        self.ise_path = itag.get('ise_path')        
        self.device = itag.get('device')
        self.speed_grade = itag.get('speed_grade')
        self.top_design_unit = itag.get('top_design_unit')
        self.intstyle = itag.get('intstyle')
        self.ifn = itag.get('ifn')
        self.constraint_file = self.top_design_unit + ".ucf"
        self.clk_net = itag.get('clk_net')
        self.rst_net = itag.get('rst_net')
        self.clk_initial_period = float(itag.get('clk_initial_period'))
        self.clk_adjustment_delta = float(itag.get('clk_adjustment_delta'))        
        self.design_label = itag.get('design_label')
        self.relative_path = itag.get('relative_path')
        self.design_dir = itag.get('design_dir')
        self.template_dir = itag.get('template_dir')
        self.log_dir = itag.get('log_dir')
        self.netlist_dir = itag.get('netlist_dir')
        self.basic_netgen_options = itag.get('basic_netgen_options')
        self.rpw_tpw = itag.get('rpw_tpw')
        self.generic_constraint_file = itag.get('generic_constraint_file')
        self.testbench_template_file = itag.get('testbench_template_file')
        self.sim_project_file = itag.get('sim_project_file')
        self.testbench_file = itag.get('testbench_file')        
        self.testbench_top_unit = itag.get('testbench_top_unit')
        self.clk_constant = itag.get('clk_constant')
        self.uut_root = itag.get('uut_root')
        self.std_start_time = float(itag.get('std_start_time'))
        self.std_observation_time = float(itag.get('std_observation_time'))
        self.std_clock_period = float(itag.get('std_clock_period'))
        self.isim_gui = itag.get('isim_gui')
        self.waveform_file = itag.get('waveform_file')
        
        
    
    def to_string(self):
        res = "Generic Configuration: "
        res += "\n\tise_path: " + self.ise_path
        res += "\n\tdevice: " + self.device
        res += "\n\tspeed_grade: " + self.speed_grade
        res += "\n\ttop_design_unit: " + self.top_design_unit
        res += "\n\tintstyle: " + self.intstyle
        res += "\n\tifn: " + self.ifn
        res += "\n\tconstraint_file: " + self.constraint_file
        res += "\n\tclk_net: " + self.clk_net
        res += "\n\trst_net: " + self.rst_net        
        res += "\n\tclk_initial_period: " + str(self.clk_initial_period)
        res += "\n\tclk_adjustment_delta: " + str(self.clk_adjustment_delta)        
        res += "\n\tdesign_label: " + self.design_label
        res += "\n\trelative_path: " + self.relative_path
        res += "\n\tdesign_dir: " + self.design_dir
        res += "\n\ttemplate_dir: " + self.template_dir    
        res += "\n\tlog_dir: " + self.log_dir
        res += "\n\tnetlist_dir: " + self.netlist_dir
        res += "\n\tbasic_netgen_options: " + self.basic_netgen_options
        res += "\n\trpw_tpw: " + self.rpw_tpw
        res += "\n\tgeneric_constraint_file: " + self.generic_constraint_file
        res += "\n\ttestbench_template_file: " + self.testbench_template_file
        res += "\n\tsim_project_file: " + self.sim_project_file
        res += "\n\tgeneric_constraint_file: " + self.generic_constraint_file
        res += "\n\ttestbench_top_unit: " + self.testbench_top_unit
        res += "\n\tclk_constant: " + self.clk_constant
        res += "\n\tuut_root: " + self.uut_root
        res += "\n\tstd_start_time: " + str(self.std_start_time)
        res += "\n\tstd_observation_time: " + str(self.std_observation_time)
        res += "\n\tstd_clock_period: " + str(self.std_clock_period)
        res += "\nisim_gui: " +str(self.isim_gui)
        res += "\nwaveform_file: " +str(self.waveform_file)
        return(res)
        
    
    
class IoptionConfigurator:
    def __init__(self):
        self.config_table = None    #Table
        self.factors = [] #IFactor
        self.res_design = None
        self.genconf = None
    
    def get_factor_by_name(self, fc_name):
        for c in self.factors:
            if(c.factor_name == fc_name):
                return(c)
        return(None)
                
    
    def create_design(self, croot):
        self.genconf = GenericConfig(croot.findall('generic')[0])
        print self.genconf.to_string()
        if(self.genconf.generic_constraint_file != ""):
            f = open(os.path.join(self.genconf.design_dir, self.genconf.template_dir, self.genconf.generic_constraint_file), 'r')
            self.genconf.generic_constraint_content = f.read()
            f.close()
            print "Generic Constraints: " + self.genconf.generic_constraint_content
        self.genconf.tool_log_dir = os.path.join(os.getcwd(), self.genconf.design_dir, "Logs")
        self.genconf.statfile = os.path.join(os.getcwd(), self.genconf.design_dir, self.genconf.statfile)
        if(not os.path.exists(self.genconf.tool_log_dir)):
            os.mkdir(self.genconf.tool_log_dir)
        mlog = open(os.path.join(self.genconf.tool_log_dir, "_Configurations.log"),'w')
        
        #read the defaults
        default_configuration = IFactorialConfiguration(self.genconf.design_label+"Default")
        default_configuration.genconf = self.genconf
        o_synthesis = croot.findall('default_synthesis_options')[0].findall('option')
        o_translate = croot.findall('default_translate_options')[0].findall('option')
        o_map = croot.findall('default_map_options')[0].findall('option')
        o_par = croot.findall('default_par_options')[0].findall('option')
        for opt in o_synthesis:
            default_configuration.synthesis.append(IOption(opt.get('name'), opt.get('value')))
        for opt in o_translate:
            default_configuration.translate.append(IOption(opt.get('name'), opt.get('value')))
        for opt in o_map:
            default_configuration.map.append(IOption(opt.get('name'), opt.get('value')))
        for opt in o_par:
            default_configuration.par.append(IOption(opt.get('name'), opt.get('value')))
        
        o_device = IOption('p', self.genconf.device)
        default_configuration.synthesis.append(o_device)
        default_configuration.synthesis.append(IOption('ifn', self.genconf.ifn))
        default_configuration.synthesis.append(IOption('ofn', self.genconf.top_design_unit))
        default_configuration.synthesis.append(IOption('top', self.genconf.top_design_unit))
        default_configuration.translate.insert(0,IOption('intstyle', self.genconf.intstyle))        
        default_configuration.translate.append(IOption('uc', self.genconf.constraint_file))
        default_configuration.translate.append(o_device)
        default_configuration.translate.append(IOption(' ', self.genconf.top_design_unit + ".ngc " + self.genconf.top_design_unit + ".ngd"))
        default_configuration.map.insert(0,IOption('intstyle', self.genconf.intstyle))        
        default_configuration.map.append(o_device)
        default_configuration.map.append(IOption('o', self.genconf.top_design_unit + "_map.ncd " + self.genconf.top_design_unit + ".ngd " + self.genconf.top_design_unit + ".pcf"))
        default_configuration.par.insert(0,IOption('intstyle', self.genconf.intstyle))                
        default_configuration.par.append(IOption(' ', self.genconf.top_design_unit + "_map.ncd " + self.genconf.top_design_unit + ".ncd " + self.genconf.top_design_unit + ".pcf"))        
        default_configuration.build_log_desc()
        print default_configuration.to_string()
        
        factor_setting = croot.findall('factorial_design')[0]
        #read the Table of factors setting
        self.config_table = Table("Partial Factorial Design/Configurations")
        self.config_table.build_from_csv(factor_setting.get('table_of_factors'))
        print self.config_table.to_csv()
        #read factors assignment
        fset = factor_setting.findall('factor')
        for tag in fset:
            fc = IFactor(tag.get('name'), tag.get('option'), tag.get('phase'))
            set_tag = tag.findall('setting')
            for x in set_tag:
                fc.add_setting(x.get('factor_value'), x.get('option_value'))
            self.factors.append(fc)
        for i in self.factors:
            print i.to_string()
        
        #Build configurations
        self.res_design = IFactorialDesign()
        self.res_design.append_configuration(default_configuration)
        for i in range(0, self.config_table.rownum(), 1):
            conf = default_configuration.mcopy(self.genconf.design_label + str("%03d" % i))
            conf.table_index = i
            conf.factor_setting = []
            for c in range(0, self.config_table.colnum(), 1):
                x_name =  self.config_table.labels[c]
                x_value = self.config_table.get(i, c)
                x_factor = self.get_factor_by_name(x_name)
                conf.factor_setting.append(x_value)
                if(x_factor == None):
                    print "Error: not found in the configuration file *.xml: Factor " + x_name
                    sys.exit(0)
                x_option = conf.get_option_by_name(x_factor.option_name, x_factor.phase)
                x_option.value = x_factor.option_values[x_value]
            self.res_design.append_configuration(conf)
        mlog.write(self.res_design.to_string())
        mlog.close()
        
        return(self.res_design)
        




def execute_impl_script(script, res_logfile, retry_attempts, comment, ilog, check_file = ""):
    attempt = 0
    res_ok = 0
    cfile_ok = 1
    timestart = datetime.datetime.now().replace(microsecond=0)
    while(((res_ok==0) or (cfile_ok==0)) and (attempt <= retry_attempts)):
        ilog.write("\n" + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\tStarting: " + comment + ", attempt " + str(attempt) +" : {"+ script+"}")
        ilog.flush()
        proc = subprocess.Popen(script, shell=True)
        proc.wait()

        if os.path.exists(res_logfile):
            with open(res_logfile, 'r') as f:
                content = f.read()
        else:
            ilog.write("\n"+ datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')+ "\tResult file not found: "+res_logfile)
            return(-1, str(datetime.datetime.now().replace(microsecond=0) - timestart))
        cfile_ok = 1
        if(check_file != ""):
            if(not os.path.isfile(check_file)):
                ilog.write("\n"+ check_file + " Not found after " + comment)
                cfile_ok = 0
        if((content.find('ERROR:') >= 0) or (cfile_ok == 0)):
            attempt += 1
            ilog.write("\n" + comment +": Error reported, retrying...")
        else:
            res_ok = 1
            cfile_ok = 1
    if(res_ok == 0):
        ilog.write("\n"+comment+" Unsuccessfull")
        ilog.flush
        return(-1, str(datetime.datetime.now().replace(microsecond=0) - timestart))
    else:
        ilog.write("\n"+comment + " Finished Successfully")
        return(1, str(datetime.datetime.now().replace(microsecond=0) - timestart))
            


def implement_configuration(config, target_dir, retry_attempts, overwrite_flag, stat):
    print "STARTED : " + config.label
    log = open(os.path.join(config.genconf.tool_log_dir, config.label+".log"), 'w')
    log.write("\n\t\tImplementing: " + config.label+"\n")
    
    #create directories    
    if os.path.exists(config.label):
        if not overwrite_flag: return
        else:
            shutil.rmtree(config.label)
    shutil.copytree(config.genconf.template_dir, config.label)
    
    os.chdir(os.path.join(target_dir, config.label))
    print "Process [" + config.label + "], working dir: " + os.getcwd()
    if(not os.path.exists(config.genconf.log_dir)):
        os.makedirs(config.genconf.log_dir)
    
    #create *.xst file (synthesis options)
    f = open(config.get_xst_file_name(), "w")
    f.write(config.get_xst_file_content())
    f.close()
       
    #1.1 Synthesis
    stat.update('Progress', 'Synthesis$wait')
    stat.update('Synthesis', 'In progress$wait')
    (status, timetaken) = execute_impl_script(config.get_synthesis_script(), config.synthesis_log, retry_attempts, "SYNTHESIS", log, os.path.join(target_dir, config.label, config.genconf.top_design_unit + ".ngc"))
    if(status < 0): 
        stat.update('Synthesis', 'Error$err')
        return(status)
    stat.update('Synthesis', 'Building Post-Synt netlist$wait')
    (status, timetaken) = execute_impl_script(config.get_netgen_script('synthesis'), config.synthesis_netlist_log, retry_attempts, "Building Netlist", log)
    if(status < 0): 
        stat.update('Synthesis', 'Error$err')
        return(status)
    #check .ngc file
    stat.update('Synthesis', '100%: ' + timetaken + '$ok')
        

    #2. Implementation
    iteration = 0
    finish = 0
    clk_period = config.genconf.clk_initial_period
    #clock adjustment iterations
    inf = 1
    log.write("\n\nStarting Implementation")
    stat.update('Converged', 'No$wait')

    while (inf == 1):
        ucf_content = "NET \""+ config.genconf.clk_net +"\" TNM_NET =" + config.genconf.clk_net +"; \nTIMESPEC TS_clock = PERIOD \""+ config.genconf.clk_net +"\" " + str(clk_period) + " ns HIGH 50%;\n" + config.genconf.generic_constraint_content
        log.write("\n\n*.ucf content [Phase = %d, Finish_flag = %d]: \n%s" % (iteration, finish, ucf_content))
        log.flush()
        ucf_file = open(config.genconf.constraint_file,'w')
        ucf_file.write(ucf_content)
        ucf_file.close()
        stat.update('Iteration', str(iteration)+'$ok')
        stat.update('Clock', str(clk_period)+'$ok')
        
        #2.1 Translate
        stat.update('Progress', 'Translate$wait')
        stat.update('Translate', 'In progress$wait')
        (status, timetaken) = execute_impl_script(config.get_translate_script(), config.translate_log, retry_attempts, "TRANSLATE", log)
        if(status < 0): 
            stat.update('Translate', 'Error$err')
            return(status)
        stat.update('Translate', '100%: ' + timetaken + '$ok')
        #2.2 MAP
        stat.update('Progress', 'MAP$wait')
        stat.update('Map', 'In progress$wait')
        (status, timetaken) = execute_impl_script(config.get_map_script(), config.map_log, retry_attempts, "MAP", log)
        if(status < 0): 
            stat.update('Map', 'Error$err')
            return(status)
        stat.update('Map', '100%: ' + timetaken + '$ok')
        #2.3 PAR
        stat.update('Progress', 'PlaceRoute$wait')
        stat.update('PlaceRoute', 'In progress$wait')
        (status, timetaken) = execute_impl_script(config.get_par_script(), config.par_log, retry_attempts, "PAR", log)
        if(status < 0): 
            stat.update('PlaceRoute', 'Error$err')
            return(status)
        stat.update('PlaceRoute', '100%: ' + timetaken + '$ok')
        #2.4 ANALYZE TIMING
        stat.update('Progress', 'Timing Analysis$wait')
        stat.update('TimingAnalysis', 'In progress$wait')
        (status, timetaken) = execute_impl_script(config.get_trace_script(), config.trace_report, retry_attempts, "TRACE/Timing Analysis", log)
        if(status < 0): 
            stat.update('TimingAnalysis', 'Error$err')
            return(status)       
        timing_report_file = open(config.trace_report,"r")
        timing_report = timing_report_file.read()
        timing_report_file.close()        
        stat.update('TimingAnalysis', '100%: ' + timetaken + '$ok')

        if(timing_report.find("All constraints were met") < 0):
            if(timing_report.find("not met") < 0): 
                log.write("\nERROR WHILE ANALYZING TIMING REPORT")
                return(-1)
            else:   #not met: stop decreasing the clock period, but now increase it until met
                finish = 1
                stat.update('Converged', 'Yes$ok')
                clk_period += config.genconf.clk_adjustment_delta
        else:
            if (finish == 1):   #if met after increasing the clock period - minimum period found (stop iterating)
                break
            else:       #if met, but minimun period yet not found
               clk_period -= config.genconf.clk_adjustment_delta
        iteration +=1

    stat.update('Progress', 'Building Netlist$wait')
    stat.update('NetlistBuilder', 'In process$wait')
    (status, timetaken) = execute_impl_script(config.get_netgen_script('par'), config.par_netlist_log, retry_attempts, "Building Post-PAR Netlist", log)
    if(status < 0): return(status)
    (status, timetaken) = execute_impl_script(config.get_netgen_script('map'), config.map_netlist_log, retry_attempts, "Building Post-MAP Netlist", log)
    if(status < 0): return(status)   
    stat.update('NetlistBuilder', '100%: ' + timetaken + '$ok')
    stat.update('Progress', 'Power Analysis$wait')
    stat.update('PowerAnalysis', 'Inprogress$wait')
    (status, timetaken) = execute_impl_script(config.get_es_power_script(), config.es_power_report, retry_attempts, "Power Analysis", log)
    if(status < 0): 
        stat.update('PowerAnalysis', 'Error$err')
        return(status)       
    stat.update('PowerAnalysis', '100%: ' + timetaken + '$ok')

    stat.update('Progress', 'Completed: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '$ok')
    log.write("\n\n\t\tImplementation Finished")    
    impl_prop = get_implementation_properties(config.par_log, config.trace_report, config.es_power_report)
    stat.update('FREQ', str("%.2f" %impl_prop.maximum_frequency) + '$res')
    stat.update('POWER_DYN', str("%.2f" %impl_prop.dynamic_power) + '$res')
    stat.update('SLICE', str(impl_prop.slices) + '$res')
    stat.update('REG', str(impl_prop.ffs) + '$res')
    stat.update('LUT', str(impl_prop.luts) + '$res')
    stat.update('DSP', str(impl_prop.dsps) + '$res')
    stat.update('RAMB', str(impl_prop.rambs) + '$res')
    log.write("\n\n" + impl_prop.to_string())
    log.close()
    

class ImplementationProperties:
    def __init__(self):
        #value == -1 means that tag was not found in the report file, it should be denoted as ? in the resulting table
        self.luts = int(0)
        self.ffs = int(0)
        self.slices = int(0)
        self.rambs = int(0)
        self.dsps = int(0)
        self.minimum_period = float(0.0)
        self.maximum_frequency = float(0.0)
        self.dynamic_power = float(0.0)
        self.static_power = float(0.0)

    def to_string(self):
        res = "\t\tImplementation Properties: "
        res += "\nLUTs:\t" + str(self.luts)
        res += "\nFFs:\t" + str(self.ffs)
        res += "\nSlices:\t" + str(self.slices)
        res += "\nRAMBs:\t" + str(self.rambs)
        res += "\nDSPs:\t" + str(self.dsps)
        res += "\nMin Clk Period:\t" + str("%.3f" % self.minimum_period)
        res += "\nMax Frequency:\t" + str("%.3f" % self.maximum_frequency)
        res += "\nDynamic Power:\t" + str("%.3f" % self.dynamic_power)
        res += "\nStatic Power:\t" + str("%.3f" % self.static_power)
        return(res)
        
        
def get_implementation_properties(par_file, trace_file, power_file):
    num_point_pattern = "[0-9]+\.?[0-9]*"
    num_comma_pattern = "[0-9]+\,?[0-9]*"    
    res = ImplementationProperties()
    #1. Retrieve Power data from power_file
    if(os.path.isfile(power_file)):
        with open(power_file, 'r') as f:
            content = f.read()
        match = re.findall("Supply Power \(mW\).+", content)[0]
        power_list = re.findall(num_point_pattern, match)
        res.dynamic_power = float(power_list[1])
        res.static_power = float(power_list[2])
    #2. Retrieve timing data from trace_file
    if(os.path.isfile(trace_file)):
        with open(trace_file, 'r') as f:
            content = f.read()
        match = re.findall("Minimum period:.*?\{", content)[0]
        res.minimum_period = float(re.findall(num_point_pattern, match)[0])
        match = re.findall("\(Maximum frequency:.*?\)", content)[0]
        res.maximum_frequency = float(re.findall(num_point_pattern, match)[0])
    #3. Retrieve Utilization data from par_file
    if(os.path.isfile(par_file)):
        with open(par_file, 'r') as f:
            content = f.read()
        try:
            match = re.findall("Number of Slice LUTs:.*?%", content)[0]
            res.luts = int(re.findall(num_comma_pattern, match)[0].replace(',',''))
            match = re.findall("Number of Slice Registers:.*?%", content)[0]
            res.ffs = int(re.findall(num_comma_pattern, match)[0].replace(',',''))
            match = re.findall("Number of occupied Slices:.*?%", content)[0]
            res.slices = int(re.findall(num_comma_pattern, match)[0].replace(',',''))    
            match = re.findall("Number of RAMB.*?:(.*?)%", content)
            for c in match:
                res.rambs += int(re.findall(num_comma_pattern, c)[0].replace(',',''))
            match = re.findall("Number of DSP.*?:(.*?)%", content)
            for c in match:
                res.dsps += int(re.findall(num_comma_pattern, c)[0].replace(',',''))
        except IndexError:
            print 'File Parse Error (file incomplete): get_implementation_properties: ' + par_file
            return(res)
    return(res)



def get_report_summary(par_report, trace_report, power_report, factorial_design = None, IncludeDefaultConfig=False):
    t = Table("RESULTS")
    t.add_column("CONFIGURATION")        
    t.add_column("CLK_PERIOD")
    t.add_column("MAX_FREQUENCY")
    t.add_column("POWER_DYNAMIC")
    t.add_column("POWER_STATIC")
    t.add_column("UTIL_REG")
    t.add_column("UTIL_LUT")
    t.add_column("UTIL_SLICE")        
    t.add_column("UTIL_RAMB")
    t.add_column("UTIL_DSP")
    t.add_column("CONFIG_TABLE_INDEX")
    t.add_column("FACTOR_SETTING")
    
    os.chdir(target_dir)
    dirlist = []
    if factorial_design != None:
        indset = range(0, len(factorial_design.configurations), 1) if IncludeDefaultConfig else range(1, len(factorial_design.configurations), 1)
        for i in indset:
            dirlist.append(factorial_design.configurations[i].label)
    else:
        for c in sorted(glob.glob(genconf.design_label + "*")):
            if(os.path.isdir(c)):
                dirlist.append(c)
        dirlist.sort()
    for i in range(0, len(dirlist), 1):
        #print "\n\nSummarizing Report Data, Configuration directory: " + dirlist[i]
        os.chdir(os.path.join(target_dir, dirlist[i]))
        res = get_implementation_properties(par_report, trace_report, power_report)
        #print res.to_string()
        t.add_row()
        t.put(i, 0, dirlist[i])
        t.put(i, 1, str("%.3f" % res.minimum_period))
        t.put(i, 2, str("%.3f" % res.maximum_frequency))
        t.put(i, 3, str("%.3f" % res.dynamic_power))
        t.put(i, 4, str("%.3f" % res.static_power))
        t.put(i, 5, str(res.ffs))
        t.put(i, 6, str(res.luts))
        t.put(i, 7, str(res.slices))
        t.put(i, 8, str(res.rambs))
        t.put(i, 9, str(res.dsps))     
        if factorial_design != None:
            c = factorial_design.get_by_label(dirlist[i])
            t.put(i, 10, str(c.table_index))
            t.put(i, 11, str(' '.join(c.factor_setting)))
        else:
            t.put(i, 10, '')
            t.put(i, 11, '')
    return(t)

    
def norm_clk_period(c):
    base = int(c)
    r = float(c) - float(base)
    if(r>0.5):
        return(float(base) + 1.0)
    elif(r>0):
        return(float(base) + 0.5)
    else:
        return(float(c))
    
def simulate_estimate_consumption(config, target_dir, retry_attempts, only_update_testbench, stat):
    if(not os.path.exists(config.genconf.tool_log_dir)):
        os.mkdir(config.genconf.tool_log_dir)    
    #remove old simulation log (if existed)
    if(os.path.exists(os.path.join(config.genconf.tool_log_dir, config.label+".log"))):
        with open(os.path.join(config.genconf.tool_log_dir, config.label+".log"), 'r+') as f:
            c = f.read()
            ind = c.find("Simulating: " + config.label)
            if ind > 0:
                f.seek(0)
                f.write(c[:ind])
                f.truncate()
    log = open(os.path.join(config.genconf.tool_log_dir, config.label+".log"), 'a')
    log.write("\n\t\tSimulating: " + config.label+"\n")
    if not os.path.exists(os.path.join(target_dir, config.label)):
        log.write('\nNo implementation found, nothing to simulate, exiting')
        return
    os.chdir(os.path.join(target_dir, config.label)) 
    with open(config.trace_report, 'r') as f:
        content = f.read()
    match = re.findall("Minimum period:.*?\{", content)[0]
    minimum_period = float(re.findall("[0-9]+\.?[0-9]*", match)[0])
    period = norm_clk_period(minimum_period)
    scale_factor = period / config.genconf.std_clock_period 
    #1. Modify Testbench: clock period constant
    with open(config.genconf.testbench_file, 'r') as f:
        content = f.read()
    content = re.sub(config.genconf.clk_constant + ".*:=\s*[0-9]+\.?[0-9]*\s*?", config.genconf.clk_constant + " : real := " + str("%.1f" % period), content)
    with open(config.genconf.testbench_file, 'w') as f:
        f.write(content)
    print('Testbench Updated: ' + config.label)
    if(only_update_testbench):
        return
    #2. Create/Modify sim_project_file
    content = ""
    if(config.genconf.sim_project_file != ""):
        f = open(config.genconf.sim_project_file, 'r')
        content = f.read()
        f.close()
    sim_prj_file = "par_sim.prj"
    netlist_files = glob.glob(config.genconf.netlist_dir + "/par/" + "*.vhd")
#    netlist_files = glob.glob(config.genconf.netlist_dir + "/par/" + "*.v")

    for c in netlist_files:
        content = "vhdl work \"" + c + "\"\n" + content
#        content = "verilog work \"" + c + "\"\n" + content

    content += "vhdl work \"" + config.genconf.testbench_file + "\"\n"
#    content += "verilog work \"" + config.genconf.testbench_file + "\"\n"
    f = open(sim_prj_file, 'w')
    f.write(content)
    f.close()
    #3. Check netlist for invalid identifiers, rename them
    rx_ptn = re.compile(r"\\.*\)\\")
    repl_ptn = re.compile("[a-zA-Z0-9_]+")
    for c in netlist_files:
        ndesc = open(c,'r')
        ncontent = ndesc.read()
        ndesc.close()
        sdf = c.replace(".vhd", ".sdf")
#        sdf = c.replace(".v", ".sdf")
        if(os.path.exists(sdf)):
            sdf_desc = open(sdf,'r')
            sdf_content = sdf_desc.read()
            sdf_desc.close()
        nlines = ncontent.split('\n')
        log.write("Netlist file " + c + ", lines: " + str(len(nlines)))
        ident_list = set()
        for l in nlines:
            match = re.findall(rx_ptn, l)
            if(len(match)>0):
                ident_list.add(match[0])
        cnt = 0
        for ident in ident_list:
            tx = re.findall(repl_ptn, ident)
            if(len(tx) > 0):
                repl_id = tx[0] + "_FixSyntax_" + str(cnt)
            else:
                repl_id = "Identifier_FixSyntax_" + str(cnt)
            ncontent = ncontent.replace(ident, repl_id)
            x = ident.replace("\\","",1).replace(")\\","\\)")
            sdf_content = sdf_content.replace(x, repl_id)
            log.write("\n\t\tFixed Identifier Syntax: " + ident + " -> " + repl_id + " [" + x + "] -> " + repl_id)
            cnt += 1
        if(cnt > 0):
            log.write("\n\t\tREWRITING NETLIST: " + c)
            ndesc = open(c,'w')
            ncontent = ndesc.write(ncontent)
            ndesc.close()
            if(os.path.exists(sdf)):
                log.write("\n\t\tREWRITING SDF: " + sdf)
                sdf_desc = open(sdf,'w')
                sdf_desc.write(sdf_content)
                sdf_desc.close()
    #4. Compile: fuse... [subprocess]
    stat.update('Progress', 'Fuse Compile$wait')
    stat.update('Fuse_Compile', 'In progress$wait')
    print "Fuse Compiling: " + config.label
    sim_exec = "testbench_isim_par.exe"
    fuse_script = "fuse -intstyle ise -mt off -incremental -lib simprims_ver -lib unisims_ver -lib unimacro_ver -lib xilinxcorelib_ver -lib secureip -o ./" + sim_exec + " -prj ./" +  sim_prj_file + " work." + config.genconf.testbench_top_unit + " > " + config.fuse_log
#    fuse_script = "fuse -intstyle ise -mt off -incremental -lib simprims_ver -lib unisims_ver -lib unimacro_ver -lib xilinxcorelib_ver -lib secureip -o ./" + sim_exec + " -prj ./" +  sim_prj_file + " work." + config.genconf.testbench_top_unit + " work.glbl > " + config.fuse_log

    (status, timetaken) = execute_impl_script(fuse_script, config.fuse_log , retry_attempts, "FUSE compile", log, sim_exec)
    if(status < 0): 
        stat.update('Fuse_Compile', 'Error$err')
        return(status)   
    stat.update('Fuse_Compile', '100%: ' + timetaken + '$ok')
    #5. Create *.cmd file
    saif_file = "xpower_isim.saif"
    cmd_content =  "sdfanno -min " +  config.genconf.netlist_dir + "/par/_timesim.sdf" + " -root /" + config.genconf.testbench_top_unit + "/" + config.genconf.uut_root
    cmd_content += "\nonerror {resume}"
    cmd_content += "\nrun 0 ns"
    cmd_content += "\nrestart"
    cmd_content += "\nrun " + str(int(scale_factor * config.genconf.std_start_time)) + " ns"
    cmd_content += "\nsaif open -scope /" + config.genconf.testbench_top_unit + "/" +  config.genconf.uut_root + " -file " + saif_file + " -allnets"
    cmd_content += "\nrun " + str(int(scale_factor * config.genconf.std_observation_time)) + " ns"
    cmd_content += "\nsaif close;\nexit\n"
    batch_file = "isim_workload.cmd"
    with open(batch_file, "w") as f:
        f.write(cmd_content)
    #6. Simulate *.exe... *.cmd... [subprocess]
    stat.update('Progress', 'Simulation$wait')
    stat.update('Simulation_ISIM', 'In progress$wait')
    if platform == 'win32' or platform == 'win64':
        isim_script = os.path.join(config.genconf.ise_path, 'settings64.bat') + ' && ' + sim_exec + " -intstyle " + config.genconf.intstyle
    else:
        isim_script = "./"+sim_exec+" -intstyle " + config.genconf.intstyle
    if(config.genconf.isim_gui == "on"):
        isim_script += " -gui"
        if(config.genconf.waveform_file != ""):
            isim_script += " -view " + config.genconf.waveform_file
    isim_script += " -tclbatch ./" + batch_file
    isim_script += " -wdb ./testbench_isim_par.wdb"
    isim_script += " > " +  config.isim_log

    (status, timetaken) = execute_impl_script(isim_script, config.isim_log, retry_attempts, "Simulation swithing activity", log, saif_file)
    if(status < 0): 
        stat.update('Simulation_ISIM', 'Error$err')
        return(status)   
    stat.update('Simulation_ISIM', '100%: ' + timetaken + '$ok')

    #7. Xpower [subprocess]
    stat.update('Progress', 'Power Analysis$wait')
    stat.update('PowerAnalysis', 'In progress$wait')
    #config.saif_power_report = config.genconf.log_dir + "/SAIF_" + config.genconf.top_design_unit + ".pwr"
    xpower_script = "xpwr -v -intstyle " + config.genconf.intstyle + " -ol std " + config.genconf.top_design_unit + ".ncd " + config.genconf.top_design_unit + ".pcf" + " -s " + saif_file +" -o " + config.saif_power_report
    xpower_script += " > " + config.genconf.log_dir + "/xpower_log.log"
    (status, timetaken) = execute_impl_script(xpower_script, config.saif_power_report, retry_attempts, "Xpower Power Estimation (+ SAIF)", log)
    if(os.path.exists(os.path.join(target_dir, config.label, './isim'))):
        print config.label + ' cleanup: Removing isim folder'
        shutil.rmtree(os.path.join(target_dir, config.label, './isim'))
    if(status < 0): 
        stat.update('PowerAnalysis', 'Error$err')
        return(status)
    stat.update('PowerAnalysis', '100%: ' + timetaken + '$ok')
    stat.update('Progress', 'Completed: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '$ok')
    impl_prop = get_implementation_properties(config.par_log, config.trace_report, config.saif_power_report)
    stat.update('FREQ', str("%.2f" %impl_prop.maximum_frequency) + '$res')
    stat.update('POWER_DYN', str("%.2f" %impl_prop.dynamic_power) + '$res')
    stat.update('SLICE', str(impl_prop.slices) + '$res')
    stat.update('REG', str(impl_prop.ffs) + '$res')
    stat.update('LUT', str(impl_prop.luts) + '$res')
    stat.update('DSP', str(impl_prop.dsps) + '$res')
    stat.update('RAMB', str(impl_prop.rambs) + '$res')
    log.write("\n\n" + impl_prop.to_string())
    log.close()
    


#----------------------------------------------
class SignalDim:
    def __init__(self, LeftD=int(0), RightD=int(0), Dir='downto'):
        self.LeftD=LeftD
        self.RightD=RightD
        self.Dir=Dir
    def to_string(self):
        return(str(self.LeftD) + "  " + self.Dir + "  " + str(self.RightD))      
    def get_width(self):
        return(abs(int(self.LeftD)-int(self.RightD) + 1))
    def get_max(self):
        if(int(self.LeftD) > int(self.RightD)):
            return(int(self.LeftD))
        else:
            return(int(self.RightD))
    def get_min(self):
        if(int(self.LeftD) < int(self.RightD)):
            return(int(self.LeftD))
        else:
            return(int(self.RightD))        

class PortT:
    def __init__(self, name='', direction='', basetype=''):
        self.name=name
        self.wire=None
        self.direction=direction
        self.basetype=basetype
        self.dimensions=[]
        self.used = 0
    def to_string(self):
        line = self.name + " " + self.direction + " " + self.basetype
        #line = line + "dim: " + str(len(self.dimensions))
        if len(self.dimensions) > 0:
            line += " ("
            for d in self.dimensions:
                if d != self.dimensions[-1]:
                    line = line + d.to_string() + ", "
                else:
                    line = line + d.to_string() + ")"
        return (line)

    def get_wire_definition(self, prefix = "tb_"):
        self.wire = prefix+self.name
        res = 'signal ' + self.wire + ' : ' + self.basetype
        if len(self.dimensions) > 0:
            res += " ("
            for d in self.dimensions:
                if d != self.dimensions[-1]:
                    res += d.to_string() + ", "
                else:
                    res += d.to_string() + ")"
        return(res)
    def get_width(self):
        res = int(1)
        for dim in self.dimensions:
            res = res*dim.get_width()
        return(res)
            
        
        
class EntityT:
    def __init__(self, name='none', file_content = ''):
        self.name = name
        self.file_content=file_content
        self.arch_name=''
        self.port_list_def=[]
        self.entity_definition=''
        self.port_list=[]
        self.architecture=''
        self.body=''
        self.port_map=[]
        self.expressions=[]
    def get_port_by_name(self, portname, match_case = "off"):
        for p in self.port_list:
            if(match_case == "off"):
                if(p.name.lower() == portname.lower()):
                    return(p)
            else:
                if(p.name == portname):
                    return(p)                
        return(None)
    
def build_testbench(config, target_dir, testbench_template_content):
    result = testbench_template_content
    pure_port_name = "[a-zA-Z0-9_.]+"
    port_par_pattern = re.compile(pure_port_name)
    port_def_pattern = re.compile(pure_port_name+'.+?;')
    dimensions_def_pattern=re.compile("\(.+?\)")
    number_pattern = re.compile("[0-9]+")
    word_pattern = re.compile("[a-zA-Z]+")

    os.chdir(os.path.join(target_dir, config.label))
    print("\n Target dir: " + os.getcwd())
    netlist_files = glob.glob(config.genconf.netlist_dir + "/par/" + "*.vhd")
    ent = None
    for ntf in netlist_files:
        f = open(ntf)
        content = f.read()
        f.close()
        match = re.findall("entity\s+"+ config.genconf.top_design_unit +"\s+is",content,re.DOTALL)
        if(len(match)>0):
            ent = EntityT(config.genconf.top_design_unit, content)
            break
    match = re.findall('entity\s+'+ent.name+'\s+is.+?end\s'+ent.name,content,re.DOTALL)
    ent.entity_definition = match[0]
    t = re.sub('\s*\)\s*;\s*end', ';\nend', ent.entity_definition)
    ent.port_list_def = port_def_pattern.findall(t)
    #parse port list -> list of PortT objects
    for p in ent.port_list_def:
        t = port_par_pattern.findall(p)
        port = PortT(t[0],t[1],t[2])
        dim = dimensions_def_pattern.findall(p)
        if len(dim) > 0:
            m=dim[0].split(',')
            for x in m:
                nm = number_pattern.findall(x)
                wd = word_pattern.findall(x)
                sdim = SignalDim(nm[0], nm[1], wd[0])
                port.dimensions.append(sdim)
        ent.port_list.append(port)
    
    #Signal definitions to use in port map
    sdef = "" 
    for p in ent.port_list:
        sdef += "\n\t" + p.get_wire_definition()
        assignment = ''
        if(p.direction =="in" and len(p.dimensions) == 0):
            assignment = " := \'0\'"
        if(p.name.lower() == config.genconf.rst_net.lower()):
            assignment = " := \'1\'"
        sdef += assignment + ";"
    result = result.replace('--#Signals', sdef)
    #UUT Instance port map
    uut_map = config.genconf.uut_root + " : entity work." + config.genconf.top_design_unit + " port map ("
    for i in range(0, len(ent.port_list), 1):
        uut_map += "\n\t" + ent.port_list[i].name + "\t=>\t" + ent.port_list[i].wire
        if(i != len(ent.port_list)-1):
            uut_map += ","
    uut_map +="\n\t);"
    result = result.replace('--#Instance', uut_map)
    #Clock
    clock_port = ent.get_port_by_name(config.genconf.clk_net)
    if(clock_port == None):
        print "clock signal [" + config.genconf.clk_net +"] not found in the netlist code"
    else:
        clk_proc = "\t\twait for 1 ns * " + config.genconf.clk_constant + "/2;\n\t\t" + clock_port.wire + " <= not " + clock_port.wire + ";"
        result = result.replace('--#Clock', clk_proc)
    #Reset
    reset_port = ent.get_port_by_name(config.genconf.rst_net)
    if(reset_port == None):
        print "Reset signal [" + config.genconf.rst_net +"] not found in the netlist code"
    else:
        rst_proc = "\t\twait for 10*" + config.genconf.clk_constant + ";\n\t\t" + reset_port.wire + " <= \'0\';"
        result = result.replace('--#Reset', rst_proc)
    #Random_vector
    inputs = []
    in_wid = 0
    for p in ent.port_list:
        if(p.direction == "in" and p.name.lower() != config.genconf.clk_net.lower() and p.name.lower() != config.genconf.rst_net.lower()):
            inputs.append(p)
            in_wid += p.get_width()
    if(in_wid < 16): in_wid = 16;
    vect = 'rand_input_vect'
    vect_def = "\t\tconstant RWID : integer := " +str(in_wid) + ";"
    vect_def += "\n\t\tvariable " + vect + " : std_logic_vector(RWID-1 downto 0);"
    result = result.replace('--#Random_vector', vect_def)        
    #Process
    v_i = in_wid-1
    proc = "\t\t\tset_random_value(" + vect + ");"
    for p in inputs:
        if len(p.dimensions) > 0:
            dmin = p.dimensions[0].get_min()
            dmax = p.dimensions[0].get_max()
            for i in range(dmax, dmin-1, -1):
                proc += "\n\t\t\t" + p.wire + "(" + str(i) + ")" + " <= " + vect + "(" + str(v_i) + ");"
                v_i -=1
        else:
            proc += "\n\t\t\t" + p.wire + " <= " + vect + "(" + str(v_i) + ");"
            v_i -= 1
    proc+="\n\t\t\twait until rising_edge(" + clock_port.wire + ");"
    result = result.replace('--#Process', proc) 
    print(result)
    f = open(config.genconf.testbench_file,'w')
    f.write(result)
    f.close()
    


def get_active_proc_number(proclist):
    res = 0
    for p in proclist:
        if p[0] != None:
            if(p[0].is_alive()):
                res += 1
    return(res)

def proclist_stat(proclist):
    active_proc = 0
    finished_proc = 0
    for p in proclist:
        if p[0] != None:
            if(p[0].is_alive()):
                active_proc += 1
            else:
                finished_proc += 1
    return(active_proc, finished_proc)



class ProcStatus(object):
    def __init__(self, tag = 'Noname'):
        self.data = dict()
        self.tag = tag
        self.changed = True

    def copy(self, src):
        for key, value in list(src.data.items()):
             self.data[key] = value
        self.tag = src.tag
        self.changed = src.changed

    def update(self, key, val):
        self.data[key] = val
        self.changed = True

    def set_mark(self, inmark):
        self.changed = inmark

    def get_mark(self):
        return(self.changed)


    def clear(self, keylist, initval='-'):
        for key in keylist:
            self.data[key] = initval
        self.changed = True


                
    def to_str(self):
        res = ""
        for key, value in list(self.data.items()):
            res += str(key) + ' : ' + str(value) + ', '
        return(res)
    
    def to_xml(self):
        res = '<' + self.tag + ' '
        for key, value in list(self.data.items()):
            res += '\n\t' +str(key) + ' = \"' + str(value) + '\" '
        res += ' >'
        res += '\n</' + self.tag + '>'
        return(res)
    
    def from_xml(self, xmlroot, tag, key, val):
        for i in xmlroot.findall(tag):
            if i.get(key, '') == val:
                for aname, avalue in i.attrib.items():
                    self.data[aname] = avalue
                self.tag = tag
                break



def save_statistics(statlist, statfile):
    res = '<?xml version=\"1.0\"?>\n<data>'
    for i in statlist:
        res += '\n\n' + i.to_xml()
    res += '\n</data>'
    with open(statfile, 'w') as f:
        f.write(res)
    #minimized stat file - export only changed items
    res = '<?xml version=\"1.0\"?>\n<data>'
    for i in statlist:
        if i.get_mark():
            res += '\n\n' + i.to_xml()
            i.set_mark(False)
    res += '\n</data>'
    with open(statfile.replace('.xml','_min.xml'), 'w') as f:
        f.write(res)





#returns dictionary dict[config_label] = (process_id=None, config_descriptor, statistic_descriptor)
#read from file statfile (xml)
def recover_statistics(config_list, statfile, clear = False):
    procdict = dict()
    recover_stat_tree = None
    if (not clear) and os.path.exists(statfile):
        recover_stat_tree = ET.parse(statfile).getroot()
    for i in config_list:
        stat = ProcStatus('Config')
        if(recover_stat_tree is not None): stat.from_xml(recover_stat_tree, 'Config', 'Label', i.label)
        procdict[i.label] = (None, i, stat)
        stat.update('Label', i.label)
    return(procdict)
    
    
        


def copy_all_files(src, dst):
    src_files = os.listdir(src)
    for file_name in src_files:
         full_file_name = os.path.join(src, file_name)
         if (os.path.isfile(full_file_name)):
              shutil.copy(full_file_name, dst)

    
#Entry point for the parent process
if __name__ == '__main__':           
    call_dir = os.getcwd()
    config_file_path = os.path.join(os.getcwd(), sys.argv[1])
    print "CONFIG PATH: " + config_file_path
    #1. Parse configuration file
    iconfig = sys.argv[1]
    tree = ET.parse(iconfig).getroot()
    tasktag = tree.findall('task')[0]

    maxproc = int(tasktag.get('max_proc'))
    retry_attempts = int(tasktag.get('retry_attempts','0'))
    overwrite_flag = True if tasktag.get('overwrite_existing','') == 'on' else False
    implement_design = tasktag.get('implement_design','on')
    implement_default_config = True if tasktag.get('implement_default_config', 'on') == 'on' else False
    simulate_switching_activity = tasktag.get('simulate_switching_activity','on')
    only_update_testbench = tasktag.get('only_update_testbench','off')
    build_testbench_random_inputs = tasktag.get('build_testbench_random_inputs','off')
    first_index = tasktag.get('first_index','')
    last_index = tasktag.get('last_index','')
    print "Max Proc: " + str(maxproc)
        
    configurator = IoptionConfigurator()
    factorial_design = configurator.create_design(tree)
    genconf = configurator.genconf
    target_dir = os.path.join(call_dir, genconf.design_dir)

    globalstatdict = dict()
    stat = ProcStatus('Global')
    stat.update('Phase', 'Implementation')
    if implement_design == 'on': 
        stat.update('Progress', '0%')
        stat.update('Report', 'wait')
    else: 
        stat.update('Progress', 'Not selected')
        stat.update('Report', '@[CSV@?./Logs/summary_power_estimated.csv]@, @[XML@?./Logs/summary_power_estimated.xml]@')
    globalstatdict['Implementation'] = stat
    stat = ProcStatus('Global')
    stat.update('Phase', 'Power Simulation')
    if simulate_switching_activity == "on": 
        stat.update('Progress', '0%')
        stat.update('Report', 'wait')
    else: 
        stat.update('Progress', 'Not selected')
        stat.update('Report', '@[CSV@?./Logs/summary_power_simulated.csv]@, @[XML@?./Logs/summary_power_simulated.xml]@')
    globalstatdict['Simulation'] = stat


    BaseManager.register('ProcStatus', ProcStatus)
    manager = BaseManager()
    manager.start()
    
    #allocate User Interface and launch it - statistics page (web)
    copy_all_files(os.path.join(call_dir,'interface'), genconf.design_dir)
    try:
        if platform == 'linux' or platform == 'linux2':
             subprocess.check_output('xdg-open ' + os.path.join(call_dir, genconf.design_dir, 'index.html > ./dummylog.txt'), shell=True)
        elif platform == 'cygwin': 
            subprocess.check_output('cygstart ' + os.path.join(call_dir, genconf.design_dir, 'index.html > ./dummylog.txt'), shell=True)
        elif platform == 'win32' or  platform == 'win64':
            subprocess.check_output('start ' + os.path.join(call_dir, genconf.design_dir, 'index.html > ./dummylog.txt'), shell=True)
    except subprocess.CalledProcessError as e:
        print e.output

    #Determine range of configurations to work with
    if implement_default_config:
        ind_start = 0
    elif first_index != '':
        ind_start = int(first_index)
    else:
        ind_start = 1
    ind_end   = int(last_index)+1  if last_index  != '' else len(factorial_design.configurations)


    #Implement selected configurations
    procdict = recover_statistics(factorial_design.configurations, genconf.statfile, True)
    clk_adjusted_flag = False
    if implement_design == "on":
        timestart = datetime.datetime.now().replace(microsecond=0)
        for i in range(ind_start, ind_end, 1):
            procdict[factorial_design.configurations[i].label][2].update('Progress', 'Scheduled')
            procdict[factorial_design.configurations[i].label][2].clear(['Iteration', 'Clock', 'Converged', 'Synthesis', 'Translate', 'Map', 'PlaceRoute', 'TimingAnalysis', 'NetlistBuilder', 'PowerAnalysis'])
        for i in range(ind_start, ind_end, 1):
            stat = manager.ProcStatus('Config')   #shared proxy-object for process status monitoring
            stat.update('Label', factorial_design.configurations[i].label)
            #wait for resources for new process and update statistics
            while True:
                (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
                globalstatdict['Implementation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(ind_end-ind_start)))+'%')
                save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile) 
                if active_proc_num < maxproc:
                    break
                time.sleep(5)
                globalstatdict['Implementation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart)+'$ok')
            # adjust initial clock period for future processes
            if not clk_adjusted_flag: #do it just once
                buf_clk = float(0)
                buf_cnt = int(0)
                for x in list(procdict.values()):
                    if x[0] != None:    #if process has been launched
                        if x[0].exitcode != None: #and terminated, then we can retrieve the resulted clock period
                            if os.path.exists(os.path.join(target_dir, x[1].label, x[1].trace_report )):
                                with open(os.path.join(target_dir, x[1].label, x[1].trace_report), 'r') as f:
                                    content = f.read()
                                buf_clk += float(re.findall("Minimum period:\s*([0-9]+\.?[0-9]*)", content)[0])
                                buf_cnt += 1
                if buf_cnt > 0: #compute the mean clock period
                    genconf.clk_initial_period = norm_clk_period(buf_clk/float(buf_cnt)) 
                    print "CLK INITIAL PERIOD ADJUSTED: " + str(genconf.clk_initial_period)
                    if(buf_cnt > (ind_end - ind_start)/5): clk_adjusted_flag = True
            p = Process(target = implement_configuration, args = (factorial_design.configurations[i], target_dir, retry_attempts, overwrite_flag, stat))
            p.start()
            procdict[factorial_design.configurations[i].label] = (p, factorial_design.configurations[i], stat)
            #wait for completion and update statistics
        while True:
            (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
            globalstatdict['Implementation'].update('Progress', str('%.2f'% (100*float(finished_proc_num)/float(ind_end-ind_start)))+'%')
            save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile) 
            if active_proc_num < 1:
                break
            time.sleep(5)
            globalstatdict['Implementation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart)+'$ok')
    if(not os.path.exists(genconf.tool_log_dir)):
        os.mkdir(config.genconf.tool_log_dir)            
    summary = get_report_summary(genconf.log_dir + "/_par.log", factorial_design.configurations[0].trace_report, factorial_design.configurations[0].es_power_report, factorial_design, implement_default_config)
    with  open(os.path.join(genconf.tool_log_dir, "summary_power_estimated.csv"), 'w') as summary_file:
        summary_file.write(summary.to_csv())
    with  open(os.path.join(genconf.tool_log_dir, "summary_power_estimated.xml"), 'w') as summary_file:
        summary_file.write(summary.to_xml('Configuration'))
    globalstatdict['Implementation'].update('Report', '@[CSV@?./Logs/summary_power_estimated.csv]@, @[XML@?./Logs/summary_power_estimated.xml]@$ok')
    save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile) 



    #Build testbench with random stimuli - if no no functional testbench is provided
    if(build_testbench_random_inputs == "on"): 
        if(os.path.isfile(os.path.join(call_dir, genconf.testbench_template_file))):
            tbfile = open(os.path.join(call_dir, genconf.testbench_template_file),'r')
            tb_template_content = tbfile.read()
            tbfile.close()
            print("Tesbench content: \n"+tb_template_content)
            for c in factorial_design.configurations:
                build_testbench(c, target_dir, tb_template_content)
        else:
            print("Testbench template file not found: " + os.path.join(call_dir, genconf.testbench_template_file))


    #Simulate switching activity (Isim) for workload-dependent (accurate) estimation of power consumption
    if(simulate_switching_activity == "on" or only_update_testbench == "on"):
        timestart = datetime.datetime.now().replace(microsecond=0)
        procdict = recover_statistics(factorial_design.configurations, genconf.statfile)
        for i in range(ind_start, ind_end, 1):
            procdict[factorial_design.configurations[i].label][2].update('Progress', 'Scheduled')
            procdict[factorial_design.configurations[i].label][2].clear(['Fuse_Compile', 'Simulation_ISIM', 'PowerAnalysis'])
        upf = True if only_update_testbench == "on" else False            
        for i in range(ind_start, ind_end, 1):
            stat = manager.ProcStatus('Config')   #shared proxy-object for process status monitoring
            stat.copy(procdict[factorial_design.configurations[i].label][2])
            #wait for resources for new process and update statistics
            while True:
                (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
                globalstatdict['Simulation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(ind_end-ind_start)))+'%')
                save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile) 
                if active_proc_num < maxproc:
                    break
                time.sleep(5)
                globalstatdict['Simulation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart)+'$ok')
            p = Process(target = simulate_estimate_consumption, args = (factorial_design.configurations[i], target_dir, retry_attempts, upf, stat))
            p.start()
            procdict[factorial_design.configurations[i].label] = (p, factorial_design.configurations[i], stat)
        while True:
            (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
            globalstatdict['Simulation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(ind_end-ind_start)))+'%')
            save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile) 
            if active_proc_num < 1:
                break
            time.sleep(5)
            globalstatdict['Simulation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart)+'$ok')
    summary = get_report_summary(genconf.log_dir + "/_par.log", factorial_design.configurations[0].trace_report, factorial_design.configurations[0].saif_power_report, factorial_design, implement_default_config)
    with open(os.path.join(genconf.tool_log_dir, "summary_power_simulated.csv"), 'w') as summary_file:
        summary_file.write(summary.to_csv())
    with  open(os.path.join(genconf.tool_log_dir, "summary_power_simulated.xml"), 'w') as summary_file:
        summary_file.write(summary.to_xml('Configuration'))
    globalstatdict['Simulation'].update('Report', '@[CSV@?./Logs/summary_power_simulated.csv]@, @[XML@?./Logs/summary_power_simulated.xml]@$ok')
    save_statistics([val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]] , genconf.statfile)   

    #build template for SBFI tool
    os.chdir(call_dir)
    config_content = "<data>"
    for c in factorial_design.configurations:
        cpi = get_implementation_properties(os.path.join(genconf.design_dir, c.label ,genconf.log_dir + "/_par.log"), os.path.join(genconf.design_dir, c.label , factorial_design.configurations[0].trace_report), os.path.join(genconf.design_dir, c.label , genconf.log_dir + "/estimated_power_" + genconf.top_design_unit + ".pwr"))
        config_content += "\n\n\t<config\n\t\twork_dir = \"" + genconf.design_dir + "/"+c.label + "\""
        config_content += "\n\t\tlabel = \"" + c.label + "\""
        config_content += "\n\t\tcompile_options = \"lib_on kh_off\""
        config_content += "\n\t\trun_options = \"kh_off\""
        config_content += "\n\t\tclk_period = \"" + str("%.1f" % norm_clk_period(cpi.minimum_period)) + "\""
        config_content += "\n\t\tstart_from = \"\""            
        config_content += "\n\t\tstop_at = \"\""
        config_content += "\n\t/>"
    config_content += "</data>"
    config_pattern_file = open(os.path.join(genconf.tool_log_dir, "config_pattern.xml"), 'w')
    config_pattern_file.write(config_content)
    config_pattern_file.close()
    
    print("Completed")

    
    