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
DAVOSPATH = os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../..'))
sys.path.insert(1, DAVOSPATH)
from Davos_Generic import *

resfolder = "/home2/tuil/UC7/analysis/"

nodes = [
    'core/u0/iu0/syncrregs.r[f]', 
    'core/u0/iu0/syncrregs.r[d]',
    'core/u0/iu0/syncrregs.r[a]',
    'core/u0/iu0/syncrregs.r[e]',
    'core/u0/iu0/syncrregs.r[x]',
    'core/u0/iu0/syncrregs.r[wb]',
    'core/u0/iu0/syncrregs.r[m]',
    'core/u0/iu0/syncrregs.r[csr]',
    'core/u0/iu0/fpui'          ,   
    'core/u0/iu0/ici'           ,
    'core/u0/iu0/tbi'           ,
    'core/u0/iu0/dci'           ,
    'core/u0/iu0/rfi'           ,
    'core/u0/iu0/dbg'           ,
    'core/u0/ramrf'             ,
    'core/u0/mmu0/srstregs'     ,
    'core/u0/mmu0/crami'        ,
    'core/u0/mmu0/dco'          ,
    'core/u0/mmu0/ico'          ,
    'core/u0/fpu_gen'           ,
    'core/u0/bht0'              ,
    'core/u0/mgen.div'          ,
    'core/u0/mgen.mul'          ,
    'core/u0/btb0'              ,
    'core/u0/cmem'              ,
    'core/u0/rst'
]





def hierarchical_average(report_files):
    fdist = {x: {} for x in nodes}
    fmodes = set()

    for fname in report_files:
        T = Table('FFI_result', [])
        T.build_from_csv(fname)
        for node in nodes:
            S = T.filter_copy('DesignNode', node)
            #print('Processing File: {0:s}, Node: {1:s}, Items: {2:d}'.format(fname, node, S.rownum()))
            for row in range(S.rownum()):
                fmode = S.getByLabel('FailureMode', row)
                if fmode in fdist[node]:
                    fdist[node][fmode] += 1
                else:
                    fdist[node][fmode] = 1
                    fmodes.add(fmode)
                    
    labels = sorted(list(fmodes))
    res = Table('Result', ['DesignNode'] + labels)
    for node in nodes:
        d_item = [fdist[node][label] if label in fdist[node] else '0' for label in labels]
        res.add_row( [node] + d_item)
    resfilename = os.path.join(resfolder, 'res_core_1_dist.csv')
    res.to_csv(";", True, resfilename)
    print("Result exported to: {0:s}".format(resfilename))


def aggregate_grmon_trace(input_log, grmon_trace, resfile):
    T = Table('FFI_result', [])
    T.build_from_csv(input_log)
    with open(grmon_trace,'r') as f:
        content = f.read()
    #items = content.split('2023:')[1:-1]
    #for i in range(len(T.rownum())):
    items = []    
    for i in re.findall('2023:(.*?)FMODE', content, re.DOTALL):
        #items.append(i.splitlines()[0])    
        items.append(i.replace(';','.').replace('\n',' ').replace('\r', ''))
    T.add_column('grmon_message', items)
    with open(resfile, 'w') as f:
        f.write(T.to_csv())


if __name__ == "__main__":

    resfiles = [
            '/home2/tuil/UC7/analysis/Core_1_permament_LOG_2023-06-29_22-49-32.csv',
            '/home2/tuil/UC7/analysis/Core_1_100us_LOG_2023-06-29_11-44-37.csv',
            '/home2/tuil/UC7/analysis/Core_1_001us_LOG_2023-06-30_15-26-15.csv',
        #   '/home2/tuil/UC7/analysis/Core_2_permanent_LOG_2023-06-28_17-00-42.csv',
        #   '/home2/tuil/UC7/analysis/Core_2_100us_LOG_2023-06-28_00-47-29.csv',
        #   '/home2/tuil/UC7/analysis/Core_2_001us_.csv' 
        ]

    #hierarchical_average(resfiles)
    aggregate_grmon_trace('/home2/tuil/UC7/dataset_v2/LOG_Core1_permanent_v2.csv', 
                          '/home2/tuil/UC7/dataset_v2/grmon_log.txt',
                          '/home2/tuil/UC7/dataset_v2/LOG_Core1_permanent_v2_Ext.csv')

