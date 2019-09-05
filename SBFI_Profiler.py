# Pre-injection Profiling
# Measures switching activity on the inputs of macrocells
# Identifies the used/unused memory cells
# Any other metric that can improve the fault injection in any way
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


class ProfilingType:
    actime, value = range(2)



#----------------------------------------------
#        Profiling logic 
#----------------------------------------------

class ProfilingAddressDescriptor:
    def __init__(self, Iaddress):
        self.address = Iaddress
        self.rate = float(0)
        self.time_from = float(0)
        self.time_to = float(0)
        self.total_time = float(0)
        self.entries = int(0)
        self.effective_switches = int(0)
        self.profiled_value = ''
        
    def to_xml(self):
        return '<address val = \"{0:s}\" rate = \"{1:.4f}\" time_from = \"{2:.2f}\" time_to = \"{3:.2f}\" total_time = \"{4:.1f}\" entries = \"{5:d}\" effective_switches = \"{6:d}\"/>'.format(self.address, self.rate, self.time_from, self.time_to, self.total_time, self.entries, self.effective_switches)


class ProfilingDescriptor:
    def __init__(self, Iprim_type, Iprim_name, Icase):
        self.prim_type = Iprim_type
        self.prim_name = Iprim_name
        self.inj_case = Icase           #object from dictionary->injection_rule(prim_type, fault_model)->injection_case
        self.trace_descriptor = None
        self.address_descriptors = []
        self.indetermination = False
        self.indetermination_time = float(0)
        self.profiled_value = ''

    def to_xml(self):
        res = '\n\t<simdesc prim_type = \"' + self.prim_type + '\" prim_name = \"'+ self.prim_name + '\" inj_case = \"' + self.inj_case.label + '\" >'
        for i in self.address_descriptors:
            res += '\n\t\t' + i.to_xml()
        return(res + '\n\t</simdesc>')
    
    def get_by_adr(self, iadr):
        for i in self.address_descriptors:
            if i.address == str(iadr):
                return(i)
        return(None)

class ProfilingResult:
    def __init__(self, Iconfig, Ifaultmodel):
        self.config = Iconfig
        self.faultmodel = Ifaultmodel
        self.items = []
    
    def append(self, Iprim_type, Iprim_name, Icase):
        self.items.append(ProfilingDescriptor(Iprim_type, Iprim_name, Icase))

    def get(self, prim_type, prim_name, inj_case_label):
        for i in self.items:
            if(i.prim_type == prim_type and i.prim_name == prim_name and i.inj_case.label == inj_case_label):
                return(i)



#returns list of possible addresses by replacing X with 1/0
def resolve_indetermination(addr):
	res = []
	res.append(addr)
	cnt = 1
	while cnt > 0:
		cnt = 0
		for i in range(0, len(res), 1):
			if res[i].count('X') > 0:
				a = res[i]
				res.remove(a)
				res.append(a.replace('X','1',1))
				res.append(a.replace('X','0',1))
				cnt+=1
				break
	return(res)



def ProfileHdlModels(config, toolconf, datamodel):
    for p in ProfilingConfig.items:
        if p.type == ProfilingType.actime:
            if len(p.indexes) > 1:
                for i1 in range(p.indexes[0].low, p.indexes[0].high+1):
                    for i2 in range:
                        pass
            else:
                pass
        else:
            pass
