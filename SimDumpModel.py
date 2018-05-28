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

