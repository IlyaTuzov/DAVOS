import os
import sys
from serial import Serial
import subprocess
import serial.tools.list_ports
import re
import shutil
import glob
import struct
import datetime
import random
import time
from Davos_Generic import Table
from BitstreamParser import *
from Datamanager import *
from FFI.Host_Zynq import *
from Reportbuilder import *
#                                   Exp_Index   FAR        word       bit       Inj_Time      FailureMode        ActivityTime  
injlog_item_ptn = re.compile('>>.*?([0-9]+).*?([0-9]+).*?([0-9]+).*?([0-9]+).*?([0-9\.]+).*?:([a-zA-Z]+)([:\s]+([0-9\.]+))?')


def build_lut_coord_dict(LutMapList, SimResFile=''):
    simresdict={}
    if SimResFile != '':
        print('Processing simulation results: {0}'.format(SimResFile))
        SimRes = Table('SimRes')
        SimRes.build_from_csv(SimResFile)
        node_ind, case_ind, res_ind = SimRes.labels.index('Node'), SimRes.labels.index('InjCase'),  SimRes.labels.index('FailureMode')
        for i in range(SimRes.rownum()):
            node = SimRes.get(i, node_ind)
            case = int(re.findall('[0-9]+', SimRes.get(i, case_ind))[0])
            simresdict[(node, case)] = SimRes.get(i, res_ind).upper()

    coord_dict = {}
    for lut in LutMapList:
        if 'Multiplicity' not in lut: lut['Multiplicity'] = len(lut['globalmap'][0])
        if ('FailureModeEmul' not in lut) or (lut['FailureModeEmul']==[]): lut['FailureModeEmul'] = [[-1]*lut['Multiplicity'] for i in range(len(lut['globalmap']))]
        for i in range(len(lut['globalmap'])):
            if (lut['simnode'], i) in simresdict:
                lut['FailureModeSim'].append(simresdict[(lut['simnode'], i)])
            for j in range(len(lut['globalmap'][i])):
                #several logic luts can use the same memory cell (LUT6_2 bell = LUT6 cell + LUT5 cell )
                if not lut['globalmap'][i][j] in coord_dict: coord_dict[lut['globalmap'][i][j]] = []
                coord_dict[lut['globalmap'][i][j]].append((lut, i, j))
    return(coord_dict)


def build_regmem_coord_dict(LLfname, Beldescfname):
    ff_coord_dict, ram_coord_dict = {}, {}
    ramblocation_dict = {}
    T = Table('Bels')
    T.build_from_csv(Beldescfname)
    for i in T.query({'BellType':'RAMB'}):
        ramblocation_dict[i['CellLocation']] = i['Node']
    with open(LLfname, 'r') as f:
        for line in f:
            matchDesc , t = re.search(ram_search_ptn,line), 1
            if not matchDesc: 
                matchDesc, t = re.search(ff_search_ptn,line), 2
            if matchDesc:
                FAR = int(matchDesc.group(1), 16)
                offset = int(matchDesc.group(2))
                block = matchDesc.group(3)
                word, bit =offset/32, offset%32
                if t==1:
                    ram_coord_dict[(FAR, word, bit)] = {'node': ramblocation_dict[matchDesc.group(3)], 'case': '{}/{}'.format(matchDesc.group(4), matchDesc.group(5))}
                elif t==2:
                    ff_coord_dict[(FAR, word, bit)]  = {'node' : matchDesc.group(5), 'case' : ''} 
    return(ff_coord_dict, ram_coord_dict)



def load_Map_dict(fname):
    res = {}
    if os.path.exists(fname):
        Tab = Table('MapList')
        Tab.build_from_csv(fname)
        for i in range(Tab.rownum()):
            res[(int(Tab.getByLabel('FAR', i)), int(Tab.getByLabel('word', i)), int(Tab.getByLabel('bit', i)))] = {'node': Tab.getByLabel('Node', i), 'case': Tab.getByLabel('Case', i)}
    return(res)




def AggregateLutResults(LutMapList, EmulResFile, SimResFile=''):
    coord_dict = build_lut_coord_dict(LutMapList, SimResFile)
    with open(EmulResFile, 'rU') as f:
        content = f.readlines()
    for l in content:
        match = re.search(injlog_item_ptn, l)
        if match:
            index = int(match.group(1))
            coord = (int(match.group(2)), int(match.group(3)), int(match.group(4)))
            injtime = float(match.group(5))
            fmode = match.group(6).lower()
            failuremode = 'M' if fmode.find('masked') >= 0 else 'L' if fmode.find('latent') >= 0 else 'C' if  fmode.find('sdc') >= 0 else 'S' if  fmode.find('signaled') >= 0 else 'X'
            if coord in coord_dict:
                for (lut, i, j) in coord_dict[coord]:
                    lut['FailureModeEmul'][i][j] = failuremode 
    for lut in LutMapList:
        lut['Emul_vs_Sim']=['']*len(lut['FailureModeEmul'])
        for i in range(len(lut['FailureModeSim'])):
            fm_sim  = lut['FailureModeSim'][i]
            fm_emul = list(set(lut['FailureModeEmul'][i]))
            if -1 in fm_emul: fm_emul.remove(-1)
            if len(fm_emul)==1:
                lut['Emul_vs_Sim'][i] = 'eq_s' if fm_sim==fm_emul[0] else 'un' if fm_sim==0 else 'ov'
            elif len(fm_emul) > 0:
                lut['Emul_vs_Sim'][i] = 'eq_w' if fm_sim==1 else 'un'
             




def ExportProfilingStatistics(LutMapList, fname):
    #Per frame: FAR;MeanActivityTime;FailureRate
    print('creating perframe dict')
    perframe_experiments = dict()
    for lut in LutMapList:
        for i in range(len(lut['FailureModeEmul'])):
            if len(lut['FailureModeEmul'][i]) > 0:
                for j in range(len(lut['FailureModeEmul'][i])):
                    if len(lut['Actime']) > 0 and j< len(lut['Actime'][i]) and lut['Actime'][i][j] >= 0 and lut['FailureModeEmul'][i][j] >= 0:
                        FAR = lut['globalmap'][i][j][0]
                        if FAR not in perframe_experiments: perframe_experiments[FAR]  = []
                        perframe_experiments[ FAR ].append((lut['Actime'][i][j], lut['FailureModeEmul'][i][j]))
    res = []
    for k,v in perframe_experiments.items():
        actime=[i[0] for i in v]
        failures = [i[1] for i in v]
        #res.append( (k, sum(actime)/len(actime), 100.0*float(sum(failures))/len(failures), len(actime)) )
        res.append( (k, sum(actime)/(101*32), 100.0*float(sum(failures))/(101*32), len(actime)) )
    T = Table('PerFrameRes', ['FAR', 'MeanActime', 'FailureRate', 'items'])
    for i in res:
        T.add_row(map(str, [i[0], i[1], i[2], i[3]]))
    with open(fname,'w') as f:
        f.write(T.to_csv())





def build_FFI_report(DavosConfig, ExportLutCsv=False):
    datamodel = DataModel()
    if not os.path.exists(DavosConfig.report_dir):
        os.makedirs(DavosConfig.report_dir)
    datamodel.ConnectDatabase( DavosConfig.get_DBfilepath(False), DavosConfig.get_DBfilepath(True) )
    datamodel.RestoreHDLModels(DavosConfig.parconf)
    datamodel.RestoreEntity(DataDescriptors.InjTarget)
    datamodel.SaveHdlModels()

    for conf in DavosConfig.parconf:
        model = datamodel.GetHdlModel(conf.label)

        Tab = Table('LutMapList')
        Tab.build_from_csv(os.path.join(conf.work_dir, 'LutMapList.csv'))
        LutMapList = TableToLutList(Tab)  

        if ExportLutCsv:
            AggregateLutResults(LutMapList, os.path.join(conf.work_dir,'./log/Injector.log'))
            with open(os.path.join(conf.work_dir,'LutResult.csv'),'w') as f:
                zTab = LutListToTable(LutMapList, True, False)
                f.write(zTab.to_csv())
            if DavosConfig.FFIConfig.profiling:
                ExportProfilingStatistics(LutMapList, os.path.join(conf.work_dir,'PerFrame.csv'))

        SummaryTable = Table(model.Label, ['ID', 'Target', 'FAR', 'word', 'bit', 'Actime', 'FailureMode'])

        lut_dict = build_lut_coord_dict(LutMapList, '')
        ff_dict = load_Map_dict(os.path.join(conf.work_dir, 'FFMapList.csv'))
        ram_dict = load_Map_dict(os.path.join(conf.work_dir, 'BramMapList.csv'))
        lutram_dict = load_Map_dict(os.path.join(conf.work_dir, 'LutramMapList.csv'))

        #ff_dict, ram_dict = build_regmem_coord_dict(os.path.join(conf.work_dir, 'Bitstream.ll'), os.path.join(conf.work_dir, 'Bels.csv'))

        ExpDescIdCnt=datamodel.GetMaxKey(DataDescriptors.InjectionExp) + 1
        with open(os.path.join(conf.work_dir,'./log/Injector.log'), 'rU') as f:
            content = f.readlines()
        for l in content:
            match = re.search(injlog_item_ptn, l)
            if match:
                coord = (int(match.group(2)), int(match.group(3)), int(match.group(4)))
                if coord in lut_dict:
                    target = datamodel.GetOrAppendTarget(lut_dict[coord][0][0]['name'], 'LUT', '{}/{}'.format(lut_dict[coord][0][1], lut_dict[coord][0][2]))
                elif coord in ff_dict:
                    target = datamodel.GetOrAppendTarget(ff_dict[coord]['node'], 'FF', ff_dict[coord]['case'])
                elif coord in ram_dict:
                    target = datamodel.GetOrAppendTarget(ram_dict[coord]['node'], 'BRAM', ram_dict[coord]['case'])
                elif coord in lutram_dict:
                    target = datamodel.GetOrAppendTarget(lutram_dict[coord]['node'], 'LUTRAM', lutram_dict[coord]['case'])
                else:
                    target = datamodel.GetOrAppendTarget('U:{0:08x}:{1:03d}:{2:02d}'.format(int(match.group(2)), int(match.group(3)), int(match.group(4))), 'TYPE0', '')

                InjDesc = InjectionDescriptor()
                InjDesc.InjectionTime = float(match.group(5))
                fmode = match.group(6).lower()
                InjDesc.FailureMode = 'M' if fmode.find('masked') >= 0 else 'L' if fmode.find('latent') >= 0 else 'C' if  fmode.find('sdc') >= 0 else 'S' if  fmode.find('signaled') >= 0 else 'X'
                InjDesc.ID = ExpDescIdCnt
                InjDesc.ModelID = model.ID
                InjDesc.TargetID = target.ID
                InjDesc.FaultModel = 'BitFlip'
                InjDesc.ForcedValue = ''
                InjDesc.InjectionDuration = float(0)
                InjDesc.ObservationTime = float(0)
                InjDesc.Node = target.NodeFullPath
                InjDesc.InjCase = target.InjectionCase
                InjDesc.Status = 'F'
                InjDesc.FaultToFailureLatency = float(0)
                InjDesc.ErrorCount = 0
                InjDesc.Dumpfile = ''
                datamodel.LaunchedInjExp_dict[InjDesc.ID] = InjDesc
                actime = float(-1.0) if match.group(8)==None else float(match.group(8))
                SummaryTable.add_row(map(str, [int(match.group(1)), target.NodeFullPath, coord[0], coord[1], coord[2], actime, InjDesc.FailureMode]))
                ExpDescIdCnt+=1
                if ExpDescIdCnt%100==0: sys.stdout.write('Processed report lines: {0}\r'.format(str(ExpDescIdCnt)))
        SummaryTable.to_csv(';',True,os.path.join(DavosConfig.report_dir, '{0}.csv'.format(model.Label)))
        T = SummaryTable.to_html_table('SEU_LUT_Details')
        T.to_file(os.path.join(DavosConfig.report_dir, '{0}.html'.format(model.Label)))


    datamodel.SaveHdlModels()
    datamodel.SaveTargets()
    datamodel.SaveInjections()

    build_report(DavosConfig, DavosConfig.toolconf, datamodel)

    datamodel.SyncAndDisconnectDB()  


#if __name__ == "__main__":
#    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
#    normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
#    normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
#    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
#    tree = xml_conf.getroot()
#    config = DavosConfiguration(tree.findall('DAVOS')[0])
#    config.toolconf = toolconf
#    config.file = normconfig




#    build_FFI_report(config, datamodel)
       
    
    

