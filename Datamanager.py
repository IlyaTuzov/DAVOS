# Library defining data structes/classes and related logic, used by DAVOS modules
# Covers:
# 1. Configuration management (parsing/exporting of XML formatted confgirations),
# 2. Observation dumps (pasring, tracing, etc.)
# 3. Internal Data Model to manage fault injection and derived analysys metrics (SQLite reflection provided)
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
import sqlite3
import copy
import threading
import ast
from Davos_Generic import *
__metaclass__ = type

#---------------------------------------
# classes for analysis of simulation dumps
#---------------------------------------
    
class RenameItem:
    def __init__(self, ifrom="", ito=""):
        self.ifrom = ifrom
        self.ito = ito
    def to_string(self):
        return('From: ' + self.ifrom + ", To: " + self.ito)


val_pattern = re.compile("[0-9a-zA-Z\.\+\-\*]+")

def find_between( s, first, last ):
    try:
        start = s.index( first ) + len( first )
        end = s.index( last, start )
        return s[start:end]
    except ValueError:
        return ""

class VectorField:
    internal, output = range(2)

class SimVector:
    def __init__(self, time=0.0, delta = 0):
       #time is supposed to be float %.2
       self.time = 0.0
       self.delta = 0
       self.internals = []
       self.outputs = []

    #field: VectorField.internal or VectorField.output
    def equals(self, v_cmp, field):
        if field == VectorField.internal:
            if len(self.internals) != len(v_cmp.internals):
                return(False)
            for i in range(0, len(self.internals), 1):
                if self.internals[i] != v_cmp.internals[i]:
                    return(False)
        elif field == VectorField.output:
            if len(self.outputs) != len(v_cmp.outputs):
                return(False)
            for i in range(0, len(self.outputs), 1):
                if self.outputs[i] != v_cmp.outputs[i]:
                    return(False)
        else:
            raw_input('Undefined Field specificator: ' + str(field))
        return(True)


    def build_from_string(self, intern_num, output_num, str_data):
        clm = re.findall(val_pattern, str_data)
        if(len(clm) < intern_num + output_num + 2):
            print "build_from_string err: line is not complete"
            return(None)
        self.time = float(clm[0])
        self.delta = int(clm[1])

        for ind in range(2, 2+intern_num, 1):
            self.internals.append(clm[ind]) 
        for ind in range(2+intern_num, 2+intern_num+output_num, 1):
            self.outputs.append(clm[ind])   
        return(self)       
    
    def to_csv(self):
        res = str(self.time) + ";" + str(self.delta) + ";"
        for c in self.internals:
            res += c + ";"
        for c in self.outputs:
            res += c + ";"
        return(res)
    
    def to_html(self):
        res = "<tr>" + "<td>" + str(self.time) + "</td><td>" + str(self.delta) + "</td>"
        for c in self.internals:
            res += "<td>" + c + "</td>"
        for c in self.outputs:
            res += "<td>" + c + "</td>"
        res +="</tr>"
        return(res)
        

        
    
class simDump:
    def __init__(self, fname=""):
        self.vectors = []
        self.internal_labels = []
        self.output_labels = []
        self.caption = ""
        #subset of vectors where only inputs/outputs change their value
        self.v_out_filtered = []
        self.v_int_filtered = []
    
    #input - simInitModel.do
    #result - self.internal_labels, self.output_labels
    def build_labels_from_file(self, fname="", rename_list=None):
        initfile = open(fname,'r')
        fcontent = initfile.read()
        initfile.close()
        internals_content = find_between(fcontent, "#<INTERNALS>","#</INTERNALS>")
        outputs_content = find_between(fcontent, "#<OUTPUTS>","#</OUTPUTS>")
        self.internal_labels = re.findall("-label\s+?(.+?)\s+?", internals_content)
        self.output_labels = re.findall("-label\s+?(.+?)\s+?", outputs_content)
        if(rename_list != None):
            for c in rename_list:
                for i in range(0, len(self.internal_labels), 1):
                    if( self.internal_labels[i] == c.ifrom):
                        self.internal_labels[i] = c.ito
        return(0)
    
    def get_labels_copy(self):
        il = []
        ol = []
        for c in self.internal_labels:
            il.append(c)
        for c in self.output_labels:
            ol.append(c)
        return( (il, ol) )
        
    def set_labels_copy(self, il, ol):
        for c in il:
            self.internal_labels.append(c)
        for c in ol:
            self.output_labels.append(c)
        return(0)        
        

    def normalize_array_labels(self, dumpfilename):
        if not os.path.exists(dumpfilename):
            return(None)
        with open(dumpfilename, 'r') as dumpfile:
            lines = dumpfile.readlines()
        for l in lines:
            if re.match('^\s*?[0-9]+', l):
                clm = re.findall("[0-9a-zA-Z\.\+\-\*{}]+", l)
                data_ind = 2
                normalized_internal_labels = []
                for label_i in range(len(self.internal_labels)):
                    if (clm[data_ind]).find('{') >= 0 :
                        arr_max_ind = 0
                        while (clm[data_ind + arr_max_ind]).find('}') < 0:
                            arr_max_ind += 1
                        for c in range(0,arr_max_ind+1, 1):
                            normalized_internal_labels.append('{0}[{1}]'.format(self.internal_labels[label_i], str(c)))
                            data_ind += 1
                    else:
                        normalized_internal_labels.append(self.internal_labels[label_i])
                        data_ind += 1
                normalized_output_labels = []
                for label_i in range(len(self.output_labels)):
                    if (clm[data_ind]).find('{') >= 0 :
                        arr_max_ind = 0
                        while (clm[data_ind + arr_max_ind]).find('}') < 0:
                            arr_max_ind += 1
                        for c in range(0,arr_max_ind+1, 1):
                            normalized_output_labels.append('{0}.format({1})'.format(self.output_labels[label_i], str(c)))
                            data_ind += 1
                    else:
                        normalized_output_labels.append(self.output_labels[label_i])
                        data_ind += 1
                self.internal_labels = normalized_internal_labels
                self.output_labels = normalized_output_labels
                return     
            
             
    #input - dump file *.lst
    #result - self.vectors
    def build_vectors_from_file(self, fname):
        if not os.path.exists(fname):
            return(None)
        self.caption = fname
        with open(fname, 'r') as dumpfile:
            lines = dumpfile.readlines()
        for l in lines:
            if re.match('^\s*?[0-9]+', l.replace('{','').replace('}','')):
                v = SimVector()
                v.build_from_string(len(self.internal_labels), len(self.output_labels), l)
                self.vectors.append(v)
        if(len(self.vectors) == 0):
            with open('error_log.txt','a') as err_log:
                err_log.write('\nEmpty list file: '+ fname)
            return(None)
        else:
            self.normalize(True)            
            return(self)
    
    def remove_vector(self, index):
        del self.vectors[index]
    
    #For each vector remove all preceding vectors with the same timestamp (keep only last vector for each time instance)
    def normalize(self, RemoveDelta = True):
        vset = []
        vbuf = self.vectors[-1]
        vset.append(vbuf)
        for i in range(len(self.vectors)-1, -1, -1):
            v = self.vectors[i]
            if (v.time == vbuf.time) and (v.delta == vbuf.delta):
                continue
            elif RemoveDelta and (v.time == vbuf.time):
                continue
            else:
                vbuf = v
                vset.append(vbuf)
        vset.reverse()
        self.vectors = vset

    #Select two sequences of vectors: where inputs/outputs change their values
    def filter_vectors(self):
        if len(self.vectors) > 0:
            self.v_int_filtered.append(self.vectors[0])
            for v in self.vectors:
                if not (v.equals(self.v_int_filtered[-1], VectorField.internal)):
                    self.v_int_filtered.append(v)
            self.v_out_filtered.append(self.vectors[0])
            for v in self.vectors:
                if not (v.equals(self.v_out_filtered[-1], VectorField.output)):
                    self.v_out_filtered.append(v)
        
    
    def to_html(self, fname):
        content = "<!DOCTYPE HTML>\n<html><head>\n<meta charset=\"utf-8\"></head>\n<body>"
        table = "<table border=\"1\"><caption>" + self.caption + "</caption>"
        table += "\n<tr><th>TIME</th>"+"\n<th>DELTA</th>"
        for label in self.internal_labels:
            table += "<th>"+label+"</th>"
        for label in self.output_labels:
            table += "<th>"+label+"</th>"
        table+="</tr>"
        for v in self.vectors:
            table+=v.to_html()
        table += "</table>"
        content += table
        content += "</body></html>"
        hdump = open(fname, "w")
        hdump.write(content)
        hdump.close()
        
    def get_vector_by_time(self, itime, idelta=None):
        if idelta != None:
            for v in self.vectors:
                if((v.time == itime) and (v.delta == idelta)):
                    return(v)
        else:
            for v in self.vectors:
                if (v.time == itime):
                    return(v)
        return(None)
    
    def compare_to_html(self, refdump, fname):
        nrows = len(self.vectors)
        ncols = 2 + len(self.internal_labels) + len(self.output_labels)
        htable = HtmlTable(nrows, ncols, self.caption)
        htable.set_label(0, "Time")
        htable.set_label(1, "Delta")
        
        len_int = len(self.internal_labels)
        len_out = len(self.output_labels)
        for i in range(0, len_int, 1):
            htable.set_label(2+i, self.internal_labels[i])
        for i in range(0, len_out , 1):
            htable.set_label(2+len_int + i, self.output_labels[i])
        for i in range(0, len(self.vectors), 1):
            itime = self.vectors[i].time
            idelta = self.vectors[i].delta
            htable.put_data(i, 0, str(itime))
            htable.put_data(i, 1, str(idelta))            
            refvector = refdump.get_vector_by_time(itime, idelta)
            for j in range(0, len_int, 1):
                htable.put_data(i,2+j, self.vectors[i].internals[j])
                htable.set_class(i,2+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].internals[j] == refvector.internals[j]):
                        htable.set_class(i,2+j,"pass")
                    else:
                        htable.set_class(i,2+j,"fail")
            for j in range(0, len_out, 1):
                htable.put_data(i,2+len_int+j, self.vectors[i].outputs[j])
                htable.set_class(i,2+len_int+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].outputs[j] == refvector.outputs[j]):
                        htable.set_class(i,2+len_int+j,"pass")
                    else:
                        htable.set_class(i,2+len_int+j,"fail")                        
        hpage = HtmlPage(self.caption)
        hpage.css_file = "../../../../teststyle.css"
        hpage.js_files.append('../../../../jquery-1.12.1.min.js')
        hpage.js_files.append('../../../../myscript.js')        
        hpage.put_data(htable.to_string())
        hpage.put_data(self.get_highlight_comment())    
        hpage.write_to_file(fname)
    
    def get_highlight_comment(self):
        res = HtmlTable(1, 3, "Highlighting Options")
        res.put_data(0,0,"Match")
        res.set_class(0,0,"pass")
        res.put_data(0,1,"Mismatch (error/failure)")
        res.set_class(0,1,"fail")
        res.put_data(0,2,"Unexpected transition (time point not in reference)")
        res.set_class(0,2,"nomatch")
        return("<br><hr>"+res.to_string_no_header())
        



    # select next-time vector after ivect.time, field == None - from complete dump, VectorField.internal - from v_int_filtered, VectorField.output - from v_out_filtered,
    def get_closest_forward(self, itime, field = None):
        if field == None:
            vectlist = self.vectors
        elif field == VectorField.internal:
            vectlist =  self.v_int_filtered
        elif field == VectorField.output:
            vectlist = self.v_out_filtered
        for v in vectlist:
            if v.time >= itime:
                return(v)
        return(None)
    
    # select prev-time vector after ivect.time, field == None - from complete dump, VectorField.internal - from v_int_filtered, VectorField.output - from v_out_filtered,
    def get_closest_backward(self, itime, field = None):
        if field == None:
            vectlist = self.vectors[::-1]
        elif field == VectorField.internal:
            vectlist =  self.v_int_filtered[::-1]
        elif field == VectorField.output:
            vectlist = self.v_out_filtered[::-1]
        for v in vectlist:
            if v.time <= itime:
                return(v)
        return(None)




    #returns first vector in self which does not match some vector from cmpdump
    #if mathing rules for all vectors in self are satisfied - returns None (no failures)
    def get_first_fail_vector(self, cmpdump, neg_timegap=float(0), pos_timegap=float(0), check_duration_factor=float(0), start_time = float(0)):
        if self.v_out_filtered == []:    self.filter_vectors()
        if cmpdump.v_out_filtered == []: cmpdump.filter_vectors()
        if len(cmpdump.v_out_filtered) == 0:
            return(self.v_out_filtered[0])
        #Find match for each interval v[i] - v[i+1]
        for v in range(0, len(self.v_out_filtered), 1):
            if self.v_out_filtered[v].time < start_time:
                continue
            checkvalue = ','.join(self.v_out_filtered[v].outputs)
            match = False
            if check_duration_factor > float(0) and v < len(self.v_out_filtered)-1:
                for c in range(0, len(cmpdump.v_out_filtered)-1, 1):
                    #1st condition: CMP vector inside the timegap around SELF vector
                    if (cmpdump.v_out_filtered[c].time >= self.v_out_filtered[v].time - neg_timegap) and (cmpdump.v_out_filtered[c].time <= self.v_out_filtered[v].time + pos_timegap):
                        #2nd condition: outputs of CMP vector match outputs of SELF vector
                        if ','.join(cmpdump.v_out_filtered[c].outputs) == checkvalue:
                            #3rd condition: duration (stability interval) is not less than in reference (SELF) * check_duration_factor
                            if (cmpdump.v_out_filtered[c+1].time - cmpdump.v_out_filtered[c].time) >= (self.v_out_filtered[v+1].time - self.v_out_filtered[v].time)*check_duration_factor:
                                match = True
                                break
            else: #duration check disabled OR last vector in self.v_out_filtered
                for c in range(0, len(cmpdump.v_out_filtered), 1):
                    if (cmpdump.v_out_filtered[c].time >= self.v_out_filtered[v].time - neg_timegap) and (cmpdump.v_out_filtered[c].time <= self.v_out_filtered[v].time + pos_timegap):
                        if ','.join(cmpdump.v_out_filtered[c].outputs) == checkvalue:
                            match = True
                            break
            if not match: #return this vector because no match found in cmpdump
                return(self.v_out_filtered[v])
        return(None) #all vectors in SELF match some vectors in cmpdump

    
    def get_forward_by_key(self, itime, ikey, ival):
        vname, c_index = self.get_index_by_label(ikey)
        for v in self.vectors:
            if v.time  >= itime:
                if(v.internals[c_index] == ival):
                    return(v)
        return(None)
    
    
    def get_first_mismatch(self, idump, inj_time):
        for v in self.vectors:
            if(v.time < inj_time):
                continue
            c = idump.get_vector_by_time(v.time, None)
            if(c==None):
                return(v)
            else:
                for i in range(0, len(v.outputs), 1):
                    if(v.outputs[i] != c.outputs[i]):
                        return(v)
        return(None)
    
    def join_output_columns(self, join_group_list):
        if(len(join_group_list.group_list) == 0):
            return(1)
        new_output_label_list = []
        for jn in join_group_list.group_list:
            jn.src_indexes = []
            for i in jn.src_labels:
                #print "LABEL: " + i
                jn.src_indexes.append(self.output_labels.index(i))
            if(jn.join_label != '-'):
                new_output_label_list.append(jn.join_label)
            
        for v in self.vectors:
            new_outputs = []
            for jn in join_group_list.group_list:
                if(jn.join_label != '-'):
                    val = ""
                    for i in jn.src_indexes:
                        val += v.outputs[i]
                    new_outputs.append(val)
            v.outputs = new_outputs
        self.output_labels = new_output_label_list
        return(0)

    #returns tuple: (vector_name, index) for specified label
    def get_index_by_label(self, label):
        for ind in range(0, len(self.internal_labels), 1):
            if(label == self.internal_labels[ind]):
                return(('internals',ind))
        for ind in range(0, len(self.output_labels), 1):
            if(label == self.output_labels[ind]):
                return(('outputs',ind))
        return(('not_found', 0))

    def get_first_vector_by_key (self, key = "FinishFlag", val = "1"):
        vname, c_index = self.get_index_by_label(key)
        if(vname == 'internals'):
            try:
                for i in range(0, len(self.vectors), 1):
                    if(self.vectors[i].internals[c_index] == val):
                        return(self.vectors[i])
            except IndexError:
                print str(IndexError)
                return(None)
        if(vname == 'outputs'):
            try:
                for i in range(0, len(self.vectors), 1):
                    if(self.vectors[i].outputs[c_index] == val):
                        return(self.vectors[i])     
            except IndexError:
                print str(IndexError)
                return(None)                       
        return(None)
        
    def get_value_where(self, column_label = "", where_key = "", where_value = ""):
        vname, c_index = self.get_index_by_label(column_label)
        vect = self.get_first_vector_by_key(where_key, where_value)
        if(vname == 'internals'):
            return(vect.internals[c_index])
        elif(vname == 'outputs'):
            return(vect.outputs[c_index])
        else:
            return ""





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



#1.1 HDL Model Configuration parameters: generics
class HDLModelConfigGeneric:
    def __init__(self, xnode):
        if xnode is None:
            self.design_type = ""
            self.library_specification = ""
            self.compile_script = ""
            self.run_script = ""
            self.std_clk_period = float(0)
            self.std_rst_delay = int(0)
            self.std_init_time = int(0)
            self.std_workload_time = int(0)  
            self.finish_flag = ""
            self.clk_signal = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.design_type = xnode.get('design_type').lower()
        self.library_specification = xnode.get('library_specification')
        self.compile_script = xnode.get('compile_script')
        self.run_script = xnode.get('run_script')
        self.std_clk_period = float(xnode.get('std_clk_period'))
        self.std_rst_delay = int(xnode.get('std_rst_delay', '0'))
        self.std_init_time = int(xnode.get('std_init_time'))
        self.std_workload_time = int(xnode.get('std_workload_time'))    
        self.finish_flag = xnode.get('finish_flag', '')        
        self.clk_signal  = xnode.get('clk_signal', '')        
        return(0)

    def to_string(self, msg):
        res = msg
        for key, val in self.__dict__.items():
            res += str("\n\t%s = %s" % (key, str(val)))
        return(res)
 


# 1.2 Configuration parameters: used by initializer module 
class ObservationScope:
    def __init__(self, xnode):
        if xnode is None:
            self.node_prefix = ""
            self.unit_path = ""
            self.label_prefix = ""
            self.sampling_options = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
            self.node_prefix = xnode.get('node_prefix')
            self.unit_path = xnode.get('unit_path')
            self.label_prefix = xnode.get('label_prefix')
            self.sampling_options = xnode.get('sampling_options')


class InjectionScope:
    def __init__(self, xnode):
        if xnode is None:
            self.node_prefix = ""
            self.unit_path = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
            self.node_prefix = xnode.get('node_prefix')
            self.unit_path = xnode.get('unit_path')


class ObservationNodeConf(object):
    def __init__(self, xnode):
        if xnode is None:
            self.location = ""
            self.options = ""
            self.label = ""
            self.path = ""
            self.comment = ""
        else:
            self.location = xnode.get('location')
            self.options = xnode.get('options','')
            self.label = xnode.get('label')
            self.path = xnode.get('path','')
            self.comment = xnode.get('comment','')




class VirtualSignalConf(ObservationNodeConf):
    def __init__(self, xnode):
        super(VirtualSignalConf, self).__init__(xnode)
        self.env = ""
        self.expression = ""
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.env = xnode.get('env', '')
        self.expression = xnode.get('expression')


class MemarrayConf(ObservationNodeConf):
    def __init__(self, xnode):
        super(MemarrayConf, self).__init__(xnode)
        self.low_address = int(0)
        self.high_address = int(0)
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.low_address = int(xnode.get('low_address', '0'))
        self.high_address = int(xnode.get('high_address', '0'))


class GenericObservationNodes:
    def __init__(self, xnode):
        self.signals = []
        self.virtual_signals = []
        self.memarrays = []
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        for i in xnode.findall('signal'):
            self.signals.append(ObservationNodeConf(i))
        for i in xnode.findall('virtual_signal'):
            self.virtual_signals.append(VirtualSignalConf(i))
        for i in xnode.findall('memarray'):
            self.memarrays.append(MemarrayConf(i))


class SBFIConfigInitializer:
    def __init__(self, xnode):
        self.virtual_register_reconstruction = False
        self.observe_outputs = ""
        self.build_injection_list = False
        self.build_dump_init_script = False
        self.match_pattern_file = ""
        self.injection_scopes = [] #InjectionScope
        self.observation_scopes = [] #ObservationScope
        self.generic_observation_nodes = None
        if xnode != None:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.virtual_register_reconstruction = True if xnode.get('virtual_register_reconstruction').lower() == "on" else False
        self.observe_outputs = xnode.get('observe_outputs')
        self.build_injection_list = True if  xnode.get('build_injection_list', '') == 'on' else False
        self.build_dump_init_script = True if  xnode.get('build_dump_init_script', '') == 'on' else False
        self.match_pattern_file = xnode.get('match_pattern_file', '')
        for i in xnode.findall('InjectionScope'):
            self.injection_scopes.append(InjectionScope(i))   
        for i in xnode.findall('ObservationScope'):
            self.observation_scopes.append(ObservationScope(i))   
        self.generic_observation_nodes = GenericObservationNodes(xnode.findall('GenericObservationNodes')[0])


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
            self.injections_per_experiment = int(0)
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
            self.duration = float(0)
            self.modifier = ''
            self.trigger_expression = ''
        else:
            self.build_from_xml(xnode)
                 
    def build_from_xml(self, xnode):
        self.model = xnode.get('model')
        self.target_logic = re.findall('[a-zA-Z0-9_]+', xnode.get('target_logic').lower())
        self.profiling = xnode.get('profiling', '')
        self.experiments_per_target = int(xnode.get('experiments_per_target', '1'))
        self.injections_per_experiment = int(xnode.get('injections_per_experiment', '1'))
        if xnode.get('time_mode', '').lower() == 'clockcycle': self.time_mode = TimeModes.ClockCycle
        elif xnode.get('time_mode', '').lower() == 'absolute': self.time_mode = TimeModes.Absolute
        else:  self.time_mode = TimeModes.Relative
        self.rand_seed = int(xnode.get('rand_seed', '1'))
        self.sample_size = int(xnode.get('sample_size', '0'))        
        self.forced_value = xnode.get('forced_value', '')
        self.duration = float(xnode.get('duration', '0'))
        self.modifier = xnode.get('modifier', '')
        self.trigger_expression = xnode.get('trigger_expression', '')
        self.time_start = float(xnode.get('injection_time_start', '0'))
        self.increment_time_step = float(xnode.get('increment_time_step', '0'))
        self.time_end = float(xnode.get('injection_time_end', '0'))
        self.activity_time_start = float(xnode.get('activity_time_start', '0'))
        self.activity_time_end = float(xnode.get('activity_time_end', '0'))
        self.inactivity_time_start = float(xnode.get('inactivity_time_start', '0'))
        self.inactivity_time_end = float(xnode.get('inactivity_time_end', '0'))
        return(0)

class SBFIConfigInjector:
    def __init__(self, xnode):
        self.fault_model = []
        if xnode is None:
            self.checkpont_mode = CheckpointModes.ColdRestore
            self.reference_check_pattern = ''
            self.maxproc = int(1)
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
        for i in xnode.findall('fault_model'):
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

class SBFIConfigAnalyzer:
   def __init__(self, xnode):
       self.join_group_list = JoinGroupList()
       self.rename_list = []
       if xnode is None:
           self.unpack_from_dir = ""
           self.detect_failures_at_finish_time = True
           self.error_flag_signal = ""
           self.error_flag_active_value = ""
           self.trap_type_signal = ""
           self.neg_timegap = float(0)
           self.pos_timegap = float(0)
           self.check_duration_factor = float(0)
           self.report_dir = ''
           self.threads = int(1)
       else:
            self.build_from_xml(xnode)
           
   def build_from_xml(self, xnode):
       self.unpack_from_dir = xnode.get('unpack_from_dir','')
       self.detect_failures_at_finish_time = True if xnode.get('detect_failures_at_finish_time','').lower() == "on" else False
       self.error_flag_signal = xnode.get('error_flag_signal','')
       self.error_flag_active_value = xnode.get('error_flag_active_value','')
       self.trap_type_signal = xnode.get('trap_type_signal','')
       self.neg_timegap = float(xnode.get('neg_timegap','0'))
       self.pos_timegap = float(xnode.get('pos_timegap','0'))
       self.check_duration_factor = float(xnode.get('check_duration_factor',''))
       self.report_dir = xnode.get('report_dir','')
       self.threads = int(xnode.get('threads','1'))
       tag = xnode.findall('join_groups')
       if len(tag) > 0: self.join_group_list.init_from_tag(tag[0])
       tag = xnode.findall('rename_list')
       if len(tag) > 0:
           for c in tag[0].findall('item'):
               self.rename_list.append(RenameItem(c.get('from'), c.get('to')))


#1.5 Configuration Items for HDL models under test (annex for genconfig)
class ParConfig:
    def __init__(self, xnode):
        self.report_dir = ""
        if xnode is None:
            self.relative_path = ""
            self.work_dir = ""
            self.label = ""
            self.compile_options = ""
            self.run_options = ""
            self.clk_period = float(0)
            self.start_from = int(0)
            self.stop_at = int(0)
            self.report_label = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.relative_path = xnode.get('relative_path','on')            
        self.work_dir = xnode.get('work_dir')     
        self.label = xnode.get('label')
        self.compile_options = xnode.get('compile_options', '')
        self.run_options = xnode.get('run_options', '')
        self.clk_period = float(xnode.get('clk_period'))
        buf = xnode.get('start_from', '')
        self.start_from = 0 if buf=='' else int(buf)
        buf = xnode.get('stop_at', '')        
        self.stop_at = 0 if buf=='' else int(buf)
        self.report_label = self.label
        

class Platforms:
    Multicore, Grid, GridLight = range(3)

#1.6 Root SBFI Configuration Object
class SBFIConfiguration:
    def __init__(self, xnode):
        self.call_dir = os.getcwd()
        self.file = ''
        self.platform = Platforms.Multicore
        self.report_dir = ''
        self.dbfile = ''
        self.initializer_phase = False
        self.profiler_phase = False
        self.injector_phase = False
        self.reportbuilder_phase = False
        self.genconf = None
        self.parconf = []
        self.initializer = None
        self.injector = None
        self.analyzer = None
        self.reportbuilder = None
        if xnode != None:
            self.build_from_xml(xnode)
        for c in self.parconf:
            if(c.relative_path =="on"):
                c.work_dir = os.path.normpath(os.path.join(self.call_dir, c.work_dir))
        if self.initializer.match_pattern_file.find('#RUNDIR') >= 0:
            self.initializer.match_pattern_file = os.path.normpath(self.initializer.match_pattern_file.replace('#RUNDIR', self.call_dir))

                
    def get_DBfilepath(self, backup_path = False):
        if not backup_path:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile)) )
        else:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile.replace('.db', '_Backup.db')) )  )           
        


    def build_from_xml(self, xnode):
        v = xnode.get('platform', 'multicore').lower()
        if v == 'multicore': self.platform = Platforms.Multicore
        elif v == 'grid': self.platform = Platforms.Grid
        elif v == 'gridlight': self.platform = Platforms.GridLight
        self.initializer_phase = True if xnode.get('initializer_phase', '') == 'on' else False
        self.profiler_phase = True if xnode.get('profiler_phase', '') == 'on' else False
        self.injector_phase = True if xnode.get('injector_phase', '') == 'on' else False
        self.reportbuilder_phase = True if xnode.get('reportbuilder_phase', '') == 'on' else False
        self.report_dir = os.path.normpath(xnode.get('report_dir', '').replace('#RUNDIR', self.call_dir))
        self.dbfile = xnode.get('dbfile', 'Results.db')
        tag = xnode.findall('Generic')
        if len(tag) > 0: self.genconf = HDLModelConfigGeneric(tag[0])
        tag = xnode.findall('Initializer')
        if len(tag) > 0: self.initializer = SBFIConfigInitializer(tag[0])
        tag = xnode.findall('Injector')
        if len(tag) > 0: self.injector = SBFIConfigInjector(tag[0])
        tag = xnode.findall('Analyzer')
        if len(tag) > 0: self.analyzer = SBFIConfigAnalyzer(tag[0])
        for c in xnode.findall('config'):
            self.parconf.append(ParConfig(c))
        self.parconf.sort(key=lambda x: x.label, reverse = False)


class ExperiementalDesignConfiguration:
    def __init__(self, xnode):
        pass



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



class DecisionSupportConfiguration:
    def __init__(self, xnode):
        self.DerivedMetrics = []
        if xnode != None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        a = xnode.findall('DerivedMetrics')
        if len(a) > 0:
            for x in a[0].findall('DerivedMetric'):
                self.DerivedMetrics.append(DerivedMetric(x))


class DavosConfiguration:
    def __init__(self, xnode):
        self.call_dir = os.getcwd()
        self.DesignBuilder = False
        self.FaultInjection = False
        self.DecisionSupport = False
        self.ExperimentalDesignConfig = None
        self.FaultInjectionConfig = None
        self.DecisionSupportConfig = None
        self.report_dir = ''
        self.dbfile = ''
        if xnode != None:
            self.build_from_xml(xnode)
        self.FaultInjectionConfig.report_dir = self.report_dir
        self.FaultInjectionConfig.dbfile = self.dbfile

    def build_from_xml(self, xnode):
        self.DesignBuilder = True if xnode.get('DesignBuilder', '') == 'on' else False
        self.FaultInjection = True if xnode.get('FaultInjection', '') == 'on' else False
        self.DecisionSupport = True if xnode.get('DecisionSupport', '') == 'on' else False
        self.report_dir = os.path.normpath(xnode.get('report_dir', '').replace('#RUNDIR', self.call_dir))
        self.dbfile = xnode.get('dbfile', 'Results.db')
        tag = xnode.findall('ExperimentalDesign')
        if len(tag) > 0: self.ExperimentalDesignConfig = ExperiementalDesignConfiguration(tag[0])
        tag = xnode.findall('FaultInjection')
        if len(tag) > 0: self.FaultInjectionConfig = SBFIConfiguration(tag[0])
        tag = xnode.findall('DecisionSupport')
        if len(tag) > 0: self.DecisionSupportConfig = DecisionSupportConfiguration(tag[0])


    def get_DBfilepath(self, backup_path = False):
        if not backup_path:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile)) )
        else:
            return( os.path.normpath(os.path.join(self.report_dir, self.dbfile.replace('.db', '_Backup.db')) )  )   


#-------------------------------------------------------------#
# Internal datamodel reflected onto the database
#-------------------------------------------------------------#

class AnalyzerReferenceDesc:
    def __init__(self):
        self.reference_dump = None
        self.JnGrLst = None
        self.initial_internal_labels = None
        self.initial_output_labels = None


class DataDescriptors:
    HdlModel, InjTarget, Profiling, InjectionExp = range(4)

class DataModel:
    def __init__(self):
        self.HdlModel_lst = []
        #self.HdlModel_dict = dict() #key = label
        self.Target_lst = []
        self.Target_dict = dict() #key = {NodeFullPath,Macrocell,InjectionCase}
        self.Profiling_lst = []
        self.LaunchedInjExp_dict = dict()
        self.dbhelper = None
        self.lock = threading.RLock()
        self.reference = AnalyzerReferenceDesc()



    def ConnectDatabase(self, dbfile, backupfile):
        self.dbhelper = SqlHelper(dbfile, backupfile)

    def GetHdlModel(self, label):
        for m in self.HdlModel_lst:
            if m.Label == label:
                return(m)
        return(None)

    def RestoreHDLModels(self, externaldescriptor_lst):
        id_cnt = self.GetMaxKey(DataDescriptors.HdlModel) + 1
        self.HdlModel_lst = self.dbhelper.HdlModels_load()
        #self.HdlModel_dict = list_to_dict(self.HdlModel_lst, 'Label')
        if externaldescriptor_lst != None:
            for c in externaldescriptor_lst:
                if self.GetHdlModel(c.label) == None:
                    a = HDLModelDescriptor()
                    a.from_config_file(c)
                    a.ID = id_cnt
                    self.HdlModel_lst.append(a)
                    id_cnt += 1
            #self.HdlModel_dict = list_to_dict(self.HdlModel_lst, 'Label')

    def RestoreEntity(self, EntityName):
        if EntityName == DataDescriptors.HdlModel:
            self.RestoreHDLModels(None)
        elif EntityName == DataDescriptors.InjTarget:
            self.Target_lst = self.dbhelper.Targets_load()
            for i in self.Target_lst:
                key = i.NodeFullPath + ',' + i.Macrocell + ',' + i.InjectionCase
                self.Target_dict[key] = i
        elif EntityName == DataDescriptors.Profiling:
            pass
        elif EntityName == DataDescriptors.InjectionExp:
            pass


    def GetOrAppendTarget(self, NodeFullPath, Macrocell, InjectionCase):
        with self.lock:
            res = None
            key = NodeFullPath + ',' + Macrocell + ',' + InjectionCase
            if key in self.Target_dict:
                res = self.Target_dict[key]
            else:
                res = InjectionTargetDescriptor()
                res.NodeFullPath = NodeFullPath
                res.Macrocell = Macrocell
                res.InjectionCase = InjectionCase
                if len(self.Target_lst) > 0: res.ID = max(node.ID for node in self.Target_lst) + 1
                else: res.ID = 0
                self.Target_lst.append(res)
                self.Target_dict[key] = res
        return(res)


    def AppendInjExpDesc(self, InjExpDesc):
        self.LaunchedInjExp_dict[InjExpDesc.ID] = InjExpDesc

    def SaveHdlModels(self):
        self.dbhelper.HdlModels_save(self.HdlModel_lst)

    def SaveTargets(self):
        self.dbhelper.Targets_save(self.Target_lst)

    def SaveInjections(self):
        injDesc_lst = self.LaunchedInjExp_dict.values()
        injDesc_lst.sort(key=lambda x: x.ID, reverse = False)
        self.dbhelper.InjectionDesc_save(injDesc_lst)

    def SyncAndDisconnectDB(self):
        self.dbhelper.connection.commit()
        self.dbhelper.connection.close()


    def GetMaxKey(self, EntityName):
        if EntityName == DataDescriptors.HdlModel:
            lst = self.dbhelper.get_primarykey_list('Models', True)
        elif EntityName == DataDescriptors.InjTarget:
            lst =self.dbhelper.get_primarykey_list('Targets', True)
        elif EntityName == DataDescriptors.Profiling:
            lst =self.dbhelper.get_primarykey_list('Profiling', True)
        elif EntityName == DataDescriptors.InjectionExp:
            lst = self.dbhelper.get_primarykey_list('Injections', True)
        if len(lst) > 0:
            return(lst[-1])
        else:
            return(0)






class HDLModelDescriptor:
    def __init__(self):
        self.ID = int(0)
        self.Label = ""
        self.ReportPath = ""
        self.Metrics = dict()

    def from_config_file(self, simconfig):
        self.Label = simconfig.label
        self.ReportPath = './'+simconfig.label
        self.Metrics['ClockPeriod'] = simconfig.clk_period
        self.Metrics['Frequency'] = float(1000000000)/float(simconfig.clk_period)


class InjectionTargetDescriptor:
    def __init__(self):
        self.ID = None
        self.NodeFullPath = ""
        self.Macrocell = ""
        self.InjectionCase = ""

class ProfilingResultDescriptor:
    def __init__(self):
        self.ID = None
        self.TargetID = None
        self.ModelID = None
        self.TotalAcTime = float(0)
        self.lastAcTime = float(0)
        self.ValueTime = dict() #saved as string in DB ( str() <--> eval() )

class InjectionDescriptor:
    def __init__(self):
        self.ID = None
        self.ModelID = None
        self.TargetID = None
        self.FaultModel = ""
        self.ForcedValue = ""
        self.InjectionTime = float(0)
        self.InjectionDuration = float(0)
        self.ObservationTime = float(0)
        self.Status = ""    #S - successfully simulated and analyzed, P - profiled, H - no finish vector (hang), E - analysis error (no sim dump, etc.)
        self.FailureMode = ""   #M - masked, L - latent, S - signalled failure, C  - silent data corruption
        self.ErrorCount = int(0)
        self.TrapCode = ""
        self.FaultToFailureLatency = float(0)
        self.Dumpfile = ""


#SqlHelper manages database operations : SQlite.db <--> datamodel
CreateDBquery = {
    "Injections" : """ 
        CREATE TABLE Injections (
            ID INTEGER PRIMARY KEY,
            ModelID  INTEGER,
            TargetID  INTEGER,
            FaultModel VARCHAR(32),
            ForcedValue  VARCHAR(64),
            InjectionTime  REAL,
            InjectionDuration REAL,
            ObservationTime REAL,
            Status CHARACTER(1),
            FailureMode CHARACTER(1),
            ErrorCount INTEGER,
            TrapCode VARCHAR(16),
            FaultToFailureLatency REAL,
            Dumpfile VARCHAR(128),
            FOREIGN KEY(ModelID) REFERENCES Models(ID),           
            FOREIGN KEY(TargetID) REFERENCES Targets(ID)
            ); """,

    "Targets" : """
        CREATE TABLE Targets (
            ID INTEGER PRIMARY KEY,
            NodeFullPath VARCHAR(1024),
            Macrocell VARCHAR(256),
            InjectionCase VARCHAR(256)
            );""",


    "Profiling" : """
        CREATE TABLE Profiling (
            ID INTEGER PRIMARY KEY,
            TargetID INTEGER,
            ModelID INTEGER,
            TotalAcTime REAL,
            lastAcTime REAL,
            ValueTime VARCHAR(128),
            FOREIGN KEY(TargetID) REFERENCES Targets(ID),
            FOREIGN KEY(ModelID) REFERENCES Models(ID) 
                            
            ); """,

    "Models" : """
        CREATE TABLE Models (
            ID INTEGER PRIMARY KEY,
            Label VARCHAR(255),
            ReportPath VARCHAR(255),
            Frequency REAL,
            ClockPeriod REAL
        ); """


    }


class SqlHelper:
    def __init__(self, dbfile, dbbackup):
        self.dbfile = dbfile
        self.dbbackup = dbbackup
        self.connection = None
        self.cursor = None
        self.createdb()
        self.last_backup_time = datetime.datetime.now().replace(microsecond=0)


    def robust_db_exec(self, query, datatuple, immediate_commit = False):
        for i in range(0, 5):
            try:
                if datatuple == None:
                    self.cursor.execute(query)
                else:
                    self.cursor.execute(query, datatuple)
                if immediate_commit:
                    self.connection.commit()
            except Exception as e:                
                print 'DB execute error: ' + str(e)
                #time.sleep(0.1)
                continue
            break
    
    def execute_for_result(self, query, datatuple):
        self.robust_db_exec(query, datatuple, False)
        return self.cursor.fetchall()

    def createdb(self):
        self.connection = sqlite3.connect(self.dbfile)
        self.cursor = self.connection.cursor()
        for tablename, sqlcode in CreateDBquery.items():
            query = 'SELECT name FROM sqlite_master WHERE type=\'table\' AND name=\'{0}\';'.format(tablename)
            self.robust_db_exec(query, None)
            if len(self.cursor.fetchall()) == 0:
                self.robust_db_exec(sqlcode, None, True)


    def BackupDB(self, Immediate = True):
        timestamp = datetime.datetime.now().replace(microsecond=0)
        if Immediate or (time_to_seconds(timestamp - self.last_backup_time) > 3600):
            print('....Doing database backup....')
            self.connection.commit()
            self.connection.close()
            shutil.copy(self.dbfile, self.dbbackup)
            self.connection = sqlite3.connect(self.dbfile)
            self.cursor = self.connection.cursor()
            self.last_backup_time = timestamp


    def close(self):
        self.connection.close()

    def HdlModels_load(self):
        model_lst = []
        self.robust_db_exec('SELECT * FROM Models', None)
        rows = self.cursor.fetchall()
        for c in rows:
            a = HDLModelDescriptor()
            names = [description[0] for description in self.cursor.description]
            a.Metrics = dict(zip(names, c))
            a.ID = a.Metrics['ID']
            del a.Metrics['ID']
            a.Label = a.Metrics['Label']
            del a.Metrics['Label']
            a.ReportPath = a.Metrics['ReportPath']
            del a.Metrics['ReportPath']
            model_lst.append(a)
            for k, v in a.Metrics.items():
                if v==None: a.Metrics[k] = 0
                elif type(v) is float: a.Metrics[k] = v
                else: a.Metrics[k] = ast.literal_eval(str(v))
        return(model_lst)


    def get_columnsintable(self, Tablename):
        columndesc = self.execute_for_result('PRAGMA table_info({0})'.format(Tablename), None)
        res = []
        for c in columndesc:
            res.append(str(c[1]))
        return(res)

    def HdlModels_save(self, HdlModel_lst):        
        for m in HdlModel_lst:
            coldesc = self.get_columnsintable('Models')
            for k,v in m.Metrics.iteritems():
                if not k in coldesc:
                    T = 'REAL' if type(v) is float else 'VARCHAR(10000)'
                    self.robust_db_exec('ALTER TABLE Models ADD COLUMN {0} {1}'.format(k, T), None, True)
            query = "\nINSERT OR REPLACE INTO Models (ID, Label, ReportPath, {0}) VALUES ({1}, \"{2}\", \"{3}\", {4})".format(', '.join(m.Metrics.keys()), m.ID, m.Label, m.ReportPath, ','.join(format(x, ".4f") if type(x) is float else '\"{0}\"'.format(str(x)) for x in m.Metrics.values()))
            self.robust_db_exec(query, None)
        self.connection.commit()


    def Targets_load(self):
        target_lst = []
        self.robust_db_exec('SELECT ID, NodeFullPath, Macrocell, InjectionCase FROM Targets', None)
        rows = self.cursor.fetchall()
        for c in rows:
            a = InjectionTargetDescriptor()
            a.ID = int(c[0])
            a.NodeFullPath = str(c[1])
            a.Macrocell = str(c[2])
            a.InjectionCase = str(c[3])
            target_lst.append(a)
        return(target_lst)


    def Targets_save(self, Target_lst):
        for t in Target_lst:
            query = "\nINSERT OR REPLACE INTO Targets (ID, NodeFullPath, Macrocell, InjectionCase) VALUES(?,?,?,?)"
            self.robust_db_exec(query, (t.ID, t.NodeFullPath, t.Macrocell, t.InjectionCase))
        self.connection.commit()

    def InjectionDesc_save(self, InjDesc_lst):
        for i in InjDesc_lst:
            query = "\nINSERT INTO Injections (ID, ModelID, TargetID, FaultModel, ForcedValue, InjectionTime, InjectionDuration, ObservationTime, Status, FailureMode, ErrorCount, TrapCode, FaultToFailureLatency, Dumpfile) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            self.robust_db_exec(query, (i.ID, i.ModelID, i.TargetID, i.FaultModel, i.ForcedValue, i.InjectionTime, i.InjectionDuration, i.ObservationTime, i.Status, i.FailureMode, i.ErrorCount, i.TrapCode, i.FaultToFailureLatency, i.Dumpfile))
        self.connection.commit()


    def get_distinct(self, field, table, sortflag = False):
        res = []
        self.robust_db_exec('SELECT DISTINCT {0} FROM {1}'.format(field, table), None)
        for c in self.cursor.fetchall():
            res.append(c[0])
        if sortflag == True: res.sort()
        return(res)


    def get_primarykey_list(self, table, sortflag):
        return self.get_distinct('ID', table, sortflag)

















