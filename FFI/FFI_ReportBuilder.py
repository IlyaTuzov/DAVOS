

def AggregateInjectionResults(LutMapList, EmulResFile, SimResFile=''):
    simresdict={}
    if SimResFile != '':
        print('Processing simulation results: {0}'.format(SimResFile))
        SimRes = Table('SimRes')
        SimRes.build_from_csv(SimResFile)
        node_ind, case_ind, res_ind = SimRes.labels.index('Node'), SimRes.labels.index('InjCase'),  SimRes.labels.index('FailureMode')
        for i in range(SimRes.rownum()):
            node = SimRes.get(i, node_ind)
            case = int(re.findall('[0-9]+', SimRes.get(i, case_ind))[0])
            injres = 1 if SimRes.get(i, res_ind).lower() == 'c' else 0 if SimRes.get(i, res_ind).lower() == 'm' else -1
            simresdict[(node, case)] = injres

    item_ptn = re.compile('>>.*?\|\|.*?([0-9]+).*?([0-9]+).*?([0-9]+).*?([0-9]+).*?([0-9\.]+).*?([0-9]+)$')
    with open(EmulResFile, 'rU') as f:
        content = f.readlines()
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
    for l in content:
        match = re.search(item_ptn, l)
        if match:
            index = int(match.group(1))
            coord = (int(match.group(2)), int(match.group(3)), int(match.group(4)))
            actime = float(match.group(5))
            failuremode = int(match.group(6))
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





def build_FFI_report(DavosConfig, datamodel):
    for conf in DavosConfig.SBFIConfig.parconf:
        Tab = Table('LutMapList')
        Tab.build_from_csv(os.path.join(conf.work_dir, 'LutMapList.csv'))
        LutMapList = TableToLutList(Tab)  
        AggregateInjectionResults(LutMapList, os.path.join(conf.work_dir,'./log/ProfilingResult.log'))
        with open(os.path.join(conf.work_dir,'LutMapList_Upd_ext.csv'),'w') as f:
            zTab = LutListToTable(LutMapList, True, False)
            f.write(zTab.to_csv())
        ExportProfilingStatistics(LutMapList, os.path.join(conf.work_dir,'PerFrame.csv'))





if __name__ == "__main__":
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
    normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
    tree = xml_conf.getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    config.toolconf = toolconf
    config.file = normconfig

    if config.platform == Platforms.Multicore or config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        datamodel = DataModel()
        datamodel.ConnectDatabase( config.get_DBfilepath(False), config.get_DBfilepath(True) )
        datamodel.RestoreHDLModels(config.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
        datamodel.SaveHdlModels()


    build_FFI_report(config, datamodel)
         
    
    

