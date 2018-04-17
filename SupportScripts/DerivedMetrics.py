# An example implementation of custom benchmarking metrics 
# derived from raw PPA and dependability attrubutes stored in database
# invoked by DesicionSupport module, linked DerivedMetric tag in config.xml 
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import shutil
import time
import glob
import cgi
import cgitb
import sqlite3
import subprocess
import random
from ast import literal_eval as make_tuple


#definition of custom optimization metric for each item from database.models
#derived from SBFI statistic {injectionstat}, other metrics existing in database {implprop}
#and custom external argument - dictionary-formatted {custom_arg}


def DeriveMTTF(injectionstat, implprop, custom_arg):
    if injectionstat == None or implprop == None:
        return(0)
    sdc = dict()    
    for cell, cell_stat in injectionstat.iteritems():
        sdc[cell]= float(0)
        total = float(0)
        for f, stat in cell_stat.iteritems():
            sdc[cell] += stat['Abs_C']
            total += (stat['Abs_M']+stat['Abs_L']+stat['Abs_S']+stat['Abs_C'])
        sdc[cell] = sdc[cell]/total
    L = float(0)
    for cell, val in sdc.iteritems():
        if (cell not in implprop) or ('fit.'+cell not in custom_arg): continue
        L += custom_arg['k']*custom_arg['fit.'+cell]*implprop[cell]*val
    return ( 0 if L == float(0) else (1/L) )




def DeriveSdcIndex(injectionstat, implprop, custom_arg):
    if injectionstat == None or implprop == None:
        return(0)
    sdc = dict()    
    for cell, cell_stat in injectionstat.iteritems():
        sdc[cell]= float(0)
        total = float(0)
        for f, stat in cell_stat.iteritems():
            sdc[cell] += stat['Abs_C']
            total += (stat['Abs_M']+stat['Abs_L']+stat['Abs_S']+stat['Abs_C'])
        sdc[cell] = sdc[cell]/total
    total_cells= 0
    total_sdc = float(0)
    for cell, val in sdc.iteritems():
        total_cells += implprop[cell]
        total_sdc += implprop[cell] * val
    return(100*total_sdc/total_cells)
        
         
