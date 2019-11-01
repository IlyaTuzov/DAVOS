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
from SBFI_Initializer import *
from BitstreamParser import *
import multiprocessing

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



def process_activity_dumps(procid, LutMapList, DAVOS_Config, resdict):
    stat = 0
    ProfileRes=[]
    workload_t = float(DAVOS_Config.SBFIConfig.genconf.std_workload_time)
    print('Starting thread: {0} to {1}'.format(LutMapList[0]['Label'],LutMapList[-1]['Label']))
    for lut in LutMapList:
        if lut['node_main'] == None:
            continue
        inj_dump = simDump()
        combining = (lut['node_compl'] != None and len(lut['cbelinputs']) > 0)
        dual_output = (lut['celltype']=='LUT6' and lut['node_compl'] != None and len(lut['cbelinputs']) == 0)
        paired_shadow_cell = len(lut['cbelinputs']) > 0 and lut['node_compl']==None
        inj_dump.internal_labels = ['Item', 'Compl'] if combining else ['Item']
        inj_dump.build_vectors_from_file("./Traces/{0}.lst".format(lut['Label']))
        #inj_dump.normalize(True)
        (lut['actime'], lut['switchcount']) = inj_dump.get_activity_time(0, workload_t, 1 if combining else None)
        if dual_output:
            print('info: replicating DUAL OUTPUT LUT6 activity for O5: {0}'.format(lut['name']))
            for k,v in lut['actime'].items():
                if k&0x1F not in lut['actime']:
                    lut['actime'][k&0x1F]=v
                    lut['switchcount'][k&0x1F] = lut['switchcount'][k]

        for i in range(2**len(lut['connections'])):
            if not combining:
                if i not in lut['actime']:  
                    lut['actime'][i]=0.0
                    lut['switchcount'][i] = 0
                elif lut['actime'][i]==0.0:
                    lut['actime'][i] = 1.0
            else:
                for j in range(2**len(lut['cbelinputs'])):
                    if (i,j) not in lut['actime']: 
                        lut['actime'][(i,j)] = 0.0
                        lut['switchcount'][(i,j)] = 0
                    elif lut['actime'][(i,j)] == 0.0: lut['actime'][(i,j)] = 1.0

        #Paired cell not represented in the simulation netist (Pathhrough, constant, etc)
        if paired_shadow_cell:
            for i in range(2**len(lut['connections'])):
                v, c = lut['actime'][i], lut['switchcount'][i]
                del lut['actime'][i]
                del lut['switchcount'][i]
                lut['actime'][(i,0)] = v
                lut['switchcount'][(i,0)] = c
                for j in range(1, 2**len(lut['cbelinputs'])):
                    lut['actime'][(i,j)] = v if v > 0 else 1.0 #assume that paired cmem cell has non-zero activity time  
                    lut['switchcount'][(i,j)] = c if c > 0 else 1



        for i in range(2**len(lut['connections'])):
            for j in range(2**len(lut['cbelinputs'])) if (combining or paired_shadow_cell) else range(1):
                x= {    'Label'    : lut['Label'], 
                        'LutBit'   : i,
                        'ComplBit' : j,
                        'BitstreamCoordinates' : lut['globalmap'][i][j],
                        'Actime' : 100.0*float(lut['actime'][(i,j)])/workload_t if (combining or paired_shadow_cell) else 100.0*float(lut['actime'][i])/workload_t,
                        'SwitchCount' :  lut['switchcount'][(i,j)] if (combining or paired_shadow_cell) else lut['switchcount'][i]}
                ProfileRes.append(x)
                #print(str(x))
        stat += 1
        if stat % 100 == 0:
            print('Profiling: processed {0} items'.format(lut['Label']))
    resdict[procid]=ProfileRes


#update LutMapList records with switching_activity [Address/ComplementaryAddress:AcTime] 
def Estimate_LUT_switching_activity(LutMapList, DAVOS_Config):
        
    #InitializeHDLModels(DAVOS_Config.SBFIConfig, DAVOS_Config.toolconf)
    CellTypes = list(set([i['celltype'].lower() for i in LutMapList]))
    nodetree = ET.parse(os.path.join(DAVOS_Config.SBFIConfig.parconf[0].work_dir, DAVOS_Config.toolconf.injnode_list)).getroot()
    inj_nodes = ConfigNodes(DAVOS_Config.SBFIConfig.parconf[0].label, nodetree)        
    nodelist = inj_nodes.get_all_by_typelist(CellTypes)

    #f = open('Log.txt','w')

    trace_script = "#Profiling script\ndo {}".format(DAVOS_Config.SBFIConfig.genconf.run_script)
    index = 0
    stdenv = DAVOS_Config.ExperimentalDesignConfig.design_genconf.uut_root
    if not stdenv.endswith('/'): stdenv += '/'
    for lut in LutMapList:
        index+=1
        lut['Label'] = 'CELL_{0:05d}'.format(index)
        for node in nodelist:
            if lut['name'].endswith(node.name.replace(' ','').replace(stdenv,'').replace('\\','')):
                lut['node_main'] = node
                break
        if lut['combcell']!=None:
            for node in nodelist:
                if lut['combcell']['name'].endswith(node.name.replace(' ','').replace(stdenv,'').replace('\\','')):
                    lut['node_compl'] = node
                    break
        #f.write('{0} : {1} : {2}\n'.format(lut['name'], '' if node_main == None else node_main.name, '==' if node_compl==None else node_compl.name))  
        if lut['node_main'] != None:
            trace_script += "\nquietly virtual signal -env {0} -install {0} {{ ((concat_range ({1:d} downto 0)) ({2}) )}} {3}".format(stdenv, 
                                                                                                                                    len(lut['connections'])-1, 
                                                                                                                                    ' & '.join(['{0}/{1}'.format(lut['node_main'].name.replace(stdenv,''), port) for port in sorted(lut['connections'].keys(), reverse=True)]),
                                                                                                                                    lut['Label'])
            if lut['node_compl'] != None and len(lut['cbelinputs']) > 0:
                combcell_I = []
                for a in lut['cbelinputs']:
                    for k, v in lut['combcell']['connections'].iteritems():
                        if a==v:
                             combcell_I.append(k)
                trace_script += "\nquietly virtual signal -env {0} -install {0} {{ ((concat_range ({1:d} downto 0)) ({2}) )}} {3}_Compl".format(stdenv, 
                                                                                                                                        len(combcell_I)-1, 
                                                                                                                                        ' & '.join(['{0}/{1}'.format(lut['node_compl'].name.replace(stdenv,''), port) for port in combcell_I[::-1]]),
                                                                                                                                        lut['Label'])

            trace_script += "\nset {0} [view list -new -title {0}]".format(lut['Label'])
            trace_script += "\nradix bin"
            trace_script += "\nadd list {0}/{1} -window ${2}".format(stdenv, lut['Label'], lut['Label'])
            if lut['node_compl'] != None and len(lut['cbelinputs']) > 0:
                trace_script += "\nadd list {0}/{1}_Compl -window ${2}".format(stdenv, lut['Label'], lut['Label'])

        else:
            print('No mathing simulation node for {0}'.format(lut['name']))

    trace_script += "\n\n\nrun {0:d} ns\n".format(DAVOS_Config.SBFIConfig.genconf.std_workload_time)

    for lut in LutMapList:
        if lut['node_main'] != None:
            trace_script += "\nview list -window ${0}".format(lut['Label'])
            trace_script += "\nwrite list -window ${0} ./Traces/{0}.lst".format(lut['Label'])
    trace_script += "\nquit\n"

    os.chdir(DAVOS_Config.SBFIConfig.parconf[0].work_dir)
    with open('Profiling.do', 'w') as f:
        f.write(trace_script)


    #proc = subprocess.Popen("vsim -c -do \"Profiling.do\" > Profiling.log", shell=True)
    #print "Profiling... "
    #proc.wait()
    
    proclist = []
    procnum = DAVOS_Config.ExperimentalDesignConfig.max_proc
    step = len(LutMapList)/procnum
    res = [[] for i in range(procnum)]
    manager=multiprocessing.Manager()
    return_dict = manager.dict()

    for i in range(procnum):
        t = multiprocessing.Process(target = process_activity_dumps, args = (i, LutMapList[i*step:(i+1)*step], DAVOS_Config, return_dict))
        proclist.append(t)
    for t in proclist:
        t.start()
    for t in proclist:
        t.join()


    print('Aggregating ')
    NonfilteredRes = []
    for k,v in return_dict.items(): NonfilteredRes+=v
    unique_res = dict()
    for item in NonfilteredRes:
        if not item['BitstreamCoordinates'] in unique_res:
            unique_res[item['BitstreamCoordinates']] = item
        elif unique_res[item['BitstreamCoordinates']]['Actime'] < item['Actime']:
            unique_res[item['BitstreamCoordinates']] = item
    ProfileRes =  [unique_res[k] for k in sorted(unique_res.keys(), reverse=False)]
    
    res = Table('Actime')
    for lbl in ['Label', 'LutBit', 'BitstreamCoordinates', 'Actime', 'SwitchCount']:
        res.add_column(lbl, map(str, [ProfileRes[i][lbl] for i in range(len(ProfileRes))]))

    for lut in LutMapList:
        combining =             len(lut['cbelinputs']) > 0 and lut['node_compl'] != None  
        paired_shadow_cell =    len(lut['cbelinputs']) > 0 and lut['node_compl'] == None
        lut['Actime'] = []
        lut['SwitchCount'] = []
        for i in range(len(lut['globalmap'])):
            lut['Actime'].append([])
            lut['SwitchCount'].append([])
            for j in range(len(lut['globalmap'][i])):
                lut['Actime'][i].append( unique_res[ lut['globalmap'][i][j] ]['Actime'] if lut['globalmap'][i][j] in unique_res else  float(-1.0))
                lut['SwitchCount'][i].append( unique_res[ lut['globalmap'][i][j] ]['SwitchCount'] if lut['globalmap'][i][j] in unique_res else  int(0))


    #for lut in LutMapList:
    #    x = [i for i in ProfileRes if lut['Label'] == i['Label']]
    #    combining =             len(lut['cbelinputs']) > 0 and lut['node_compl'] != None  
    #    paired_shadow_cell =    len(lut['cbelinputs']) > 0 and lut['node_compl'] == None
    #    buf = [y['Actime'] for y in sorted(x, key=lambda i: (i['LutBit'], i['ComplBit']))]
    #    chunksize = (2**len(lut['cbelinputs'])) if (combining or paired_shadow_cell) else 1 
    #    lut['Actime'] = [buf[i:i+chunksize] for i in range(0, len(buf), chunksize)]
    with open('Profiled.csv','w') as f:
        f.write(res.to_csv())


    #with open('Temp1.txt','w') as f:
    #    f.write( '\n'.join(i.type + ' : ' + i.name.replace(DAVOS_Config.ExperimentalDesignConfig.design_genconf.uut_root,'').replace('\\','') for i in nodelist))
    #Build Trace/List script for ModelSim
    return(ProfileRes)


if __name__ == "__main__":
    path = "C:/Projects/Profiling/Models/MC8051_ZC"
    T=Table('ProflingResult')
    T.build_from_csv(os.path.join(path, 'LutMapList_Upd_ext.csv'))
    items = []
    Actime_ind, SWcount, Fmode_ind = T.labels.index('Actime'), T.labels.index('SwitchCount'), T.labels.index('FailureModeEmul')
    for row in range(T.rownum()):
        item = (float(T.get(row, Actime_ind)), int(T.get(row, SWcount)), int(T.get(row, Fmode_ind)), float(T.get(row, Actime_ind))*int(T.get(row, SWcount)))
        if item[0] > 0 and item[1] > 0 and item[2] >= 0:
            items.append(item)

    items.sort(key=lambda i: i[3])
    N = 20
    S = len(items)/N
    for i in range(N):
        actime =  [items[j][0] for j in range(S*i, S*(i+1))]
        swcount = map(float, [items[j][1] for j in range(S*i, S*(i+1))])
        fmode  =  map(float, [items[j][2] for j in range(S*i, S*(i+1))])
        sortfunc = map(float, [items[j][3] for j in range(S*i, S*(i+1))])

        print('Group {0:3d} : Mean_Actime {1:10.5f} : Mean_SwitchCount: {2:10.0f} : FailureRate : {3:6.2f} : SortFunc : {4:10.0f}'.format(i, sum(actime)/len(actime), sum(swcount)/len(swcount), 100*sum(fmode)/len(fmode), sum(sortfunc)/len(sortfunc) ))


