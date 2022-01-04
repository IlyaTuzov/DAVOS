# Miscellaneous procedures to generate factorial designs for design space exploration
# 1. Infers balanced and orthogonal fractional factorial design
# 2. Builds internal data model and database descriptors for HDL models to be implemented
# 3. Exports template configurations for fault injection tool
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

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
import glob
from subprocess import call
from sys import platform
from Datamanager import *
import string
import ImplementationTool


class ExperimentalDesignTypes:
    Fractional, Doptimal = list(range(2))

def Build_ConfigTable_Matlab(config, DesignType = ExperimentalDesignTypes.Doptimal):
    T = Table('FactorialDesign')
    if DesignType == ExperimentalDesignTypes.Fractional:
        with open(os.path.join(config.call_dir,'SupportScripts','factorial.m'), 'r') as file:
            matlabscript = file.read()
        aliases = [c.factor_name for c in config.factorial_config.factors]
        terms  = []
        l=len(aliases)
        if l <= 26: u =0
        else:
            l = 26
            u = len(aliases) - l
        for i in range(l): terms.append(string.ascii_lowercase[i])
        for i in range(u): terms.append(string.ascii_uppercase[i])
        matlabscript = matlabscript.replace('#FACTORS', '\'' + ' '.join(terms) + '\'')
        matlabscript = matlabscript.replace('#ALIASES', '{' + ' '.join(['\''+c+'\'' for c in aliases]) + '}')
        matlabscript = matlabscript.replace('#RESOLUTION', str(config.factorial_config.resolution))
        generated_table_of_factors = os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir, 'FactorConfig_{0}.csv'.format(config.design_genconf.design_label)))
        matlabscript = matlabscript.replace('#FILENAME', '\''+generated_table_of_factors+'\'')

    elif DesignType == ExperimentalDesignTypes.Doptimal:
        with open(os.path.join(config.call_dir,'SupportScripts','doptimal.m'), 'r') as file:
            matlabscript = file.read()
        factors = [c.factor_name for c in config.factorial_config.factors]
        categorical_indexes = list(range(1, len(factors)+1)) #assume all factors are categorical
        levels = [len(c.setting) for c in config.factorial_config.factors]
        generated_table_of_factors = os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir, 'FactorConfig_{0}.csv'.format(config.design_genconf.design_label)))
        matlabscript = matlabscript.replace('#FACTORS', '{' + ', '.join(['\'{}\''.format(i) for i in factors]) + '}')
        matlabscript = matlabscript.replace('#CATEGORICAL_INDEXES', '[' + ', '.join('{}'.format(i) for i in categorical_indexes) + ']')
        matlabscript = matlabscript.replace('#LEVELS', '[' + ', '.join('{}'.format(i) for i in levels) + ']')
        matlabscript = matlabscript.replace('#FILENAME', '\''+generated_table_of_factors+'\'')

    script_fname = os.path.abspath(os.path.join(config.design_genconf.design_dir, 'ParConfGen.m'))            
    with open(script_fname, 'w') as file:
        file.write(matlabscript)            
    shellcmd = 'matlab.exe -nosplash -nodesktop -minimize -r \"cd {0}; run (\'{1}\'); quit\"'.format( os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir)), 'ParConfGen.m' )
    if os.path.exists(generated_table_of_factors): os.remove(generated_table_of_factors)
    proc = subprocess.Popen(shellcmd, shell=True)
    proc.wait()
    while not os.path.exists(generated_table_of_factors):
        time.sleep(1)
    if DesignType == ExperimentalDesignTypes.Fractional:
        with open(generated_table_of_factors,'r') as file: 
            content = file.read()                        
            content = content.replace('-1','0')
        with open(generated_table_of_factors,'w') as file: 
            file.write(content)                
    T.build_from_csv(generated_table_of_factors)
    return(T)



def AppendModelsFromTable(T, datamodel, config):
    existing_configs, new_configs = ([], [])
    flist = T.labels
    flist.sort()
    for i in range(T.rownum()):
        c = []
        for f in flist:
            a = FactorSetting()
            a.FactorName = f
            a.FactorVal = int(T.getByLabel(f, i))
            cfg = config.factorial_config.GetFactorByName(f)
            a.OptionName = cfg.option_name
            a.Phase = cfg.phase_name
            for k, v in cfg.setting.iteritems():
                if k == a.FactorVal:
                    a.OptionVal = v
                    break
            c.append(a)
        m = datamodel.GetOrCreateHDLModel(c)
        m.TabIndex = i
        if m.Label == '': m.Label = '{0}{1:03d}'.format(config.design_genconf.design_label, m.ID)
        if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label).replace('\\','/'))
        if 'Implprop' in m.Metrics:
            #config exist/already has been implemented previosuly - re-implement or omit
            if (m.Metrics['Implprop'] != None) and (not config.overwrite_existing):
                existing_configs.append(m)   
            else:
                new_configs.append(m)
        else:
            new_configs.append(m)
    return((existing_configs, new_configs))



def CreateDefaultConfig(datamodel, config):
    c = []
    for factor in config.factorial_config.factors:
        a = FactorSetting()
        a.FactorName = factor.factor_name
        a.OptionName = factor.option_name
        a.Phase = factor.phase_name
        p = config.flow.get_phase(factor.phase_name)
        if p != None:
            a.OptionVal = p.get_option(factor.option_name).default
        else:
            print 'Error: CreateDefaultConfig: option {} not found in phase {}'.format(factor.option_name, factor.phase_name)            
        c.append(a)
        a.FactorVal = -1
        x = config.factorial_config.GetFactorByName(a.FactorName)
        for k,v in x.setting.iteritems():
            if v == a.OptionVal:
                a.FactorVal = k
                break
    m = datamodel.GetOrCreateHDLModel(c)
    if m.Label == '': m.Label = '{0}Default'.format(config.design_genconf.design_label)
    if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label))
    return(m)


def CreateConfigForSetting(datamodel, config, setting):
    if len(config.factorial_config.factors) != len(setting):
        print('Error in CreateConfigForSetting: mismatch {} factors <> {} items in setting'.format(str(v), str(len(setting))))
        return(None)
    c = []
    factors = sorted(config.factorial_config.factors, key=lambda x: x.factor_name, reverse = False)
    for i in range(len(factors)):
        a = FactorSetting()
        a.FactorName = factors[i].factor_name
        a.OptionName = factors[i].option_name
        a.Phase = factors[i].phase_name
        a.FactorVal = setting[i]
        x = config.factorial_config.GetFactorByName(a.FactorName)
        for k,v in x.setting.iteritems():
            if k == a.FactorVal:
                a.OptionVal = v
                break
        c.append(a)        
    m = datamodel.GetOrCreateHDLModel(c)
    if m.Label == '': m.Label = '{0}_{1}'.format(config.design_genconf.design_label, m.ID)
    if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label))
    return(m)


def Build_ExperimentalDesign(datamodel, config):
    """Creates a list of factorial configurations to be evaluated

    Args:
        datamodel (DataModel): contains all configurations under study (may be empty if nothing present before)
        config (ExperiementalDesignConfiguration): parameters of experimental design under study

    Returns:
        (tuple of lists): configurations available, configurations to be implemented    
    """

    if config.factorial_config.table_of_factors != '':    
        T = Table('FactorialDesign')        
        T.build_from_csv(os.path.normpath(os.path.join(config.call_dir, config.factorial_config.table_of_factors)))
    elif config.factorial_config.design_type != '':
        if config.factorial_config.design_type == 'Fractional' and config.factorial_config.resolution > 0:
            T = Build_ConfigTable_Matlab(config, ExperimentalDesignTypes.Fractional)
        elif config.factorial_config.design_type == 'Doptimal':
            T = Build_ConfigTable_Matlab(config, ExperimentalDesignTypes.Doptimal)
    existing_configs, new_configs = AppendModelsFromTable(T, datamodel, config)
    return((existing_configs, new_configs))




def configs_to_table(configs, varlist=[]):
    T = Table('Samples')
    FactorLabels = []
    ResponceVariableLabels = []
    #append factors
    for c in configs[0].Factors:
        FactorLabels.append(c.FactorName)
        T.add_column(c.FactorName)
    for row in range(len(configs)):        
        T.add_row()
        for col in range(len(T.labels)):
            x = configs[row].get_factor_by_name(T.labels[col])
            T.put(row,col, x.FactorVal)
    #append responce variables
    for c in configs:
        if c.Metrics['Error'] == '' or c.Metrics['Error'] == 0:
            metrics = c.get_flattened_metric_dict()
            break
    for k, v in metrics.iteritems():
        if len(varlist) > 0 and k in varlist: ResponceVariableLabels.append(k)
    print('ResponceVariableLabels: {0}'.format(str(ResponceVariableLabels)))
    ResponceVariableLabels.sort()
    for respvar_ind in range(len(ResponceVariableLabels)):
        if respvar_ind in['BestConf']: 
            continue
        lbl = ResponceVariableLabels[respvar_ind]
        T.add_column(lbl)   
        for row in range(len(configs)):
            #if configs[row].Metrics['Implprop']['VerificationSuccess'] > 0:
            metrics = configs[row].get_flattened_metric_dict()
            T.put(row, len(FactorLabels)+respvar_ind, metrics[lbl] if lbl in metrics else '-')
    return(T)


def augment_design(configurations, excluded, datamodel, config, sample_size):
    #export factorial design
    excl_file  = os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir, 'Excluded_{0}.csv'.format(config.design_genconf.design_label))) 
    input_file = os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir, 'InputSample{0}.csv'.format(config.design_genconf.design_label)))     
    output_file = os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir, 'Augmented_{0}.csv'.format(config.design_genconf.design_label)))

    if len(excluded) > 0:
        Excl = configs_to_table(excluded, [])
        with open(excl_file, 'w') as f:
            f.write(Excl.to_csv(',', False))
    with open(os.path.join(config.call_dir,'SupportScripts','excludeitems.m'), 'r') as file:
        matlabscript = file.read()
    matlabscript = matlabscript.replace('#INPFILENAME', '\''+excl_file+'\'')
    with open(os.path.join(config.design_genconf.design_dir, 'excludeitems.m'), 'w') as file:
        file.write(matlabscript) 
    T = configs_to_table(configurations, [])
    with open(input_file, 'w') as f:
        f.write(T.to_csv(',', False))

    with open(os.path.join(config.call_dir,'SupportScripts','AugmentDesign.m'), 'r') as file:
        matlabscript = file.read()
    factors = [c.factor_name for c in config.factorial_config.factors]
    categorical_indexes = list(range(1, len(factors)+1)) #assume all factors are categorical
    levels = [len(c.setting) for c in config.factorial_config.factors]    
    matlabscript = matlabscript.replace('#FACTORS', '{' + ', '.join(['\'{}\''.format(i) for i in factors]) + '}')
    matlabscript = matlabscript.replace('#CATEGORICAL_INDEXES', '[' + ', '.join('{}'.format(i) for i in categorical_indexes) + ']')
    matlabscript = matlabscript.replace('#LEVELS', '[' + ', '.join('{}'.format(i) for i in levels) + ']')
    matlabscript = matlabscript.replace('#INPFILENAME', '\''+input_file+'\'')
    matlabscript = matlabscript.replace('#RESFILENAME', '\''+output_file+'\'')
    matlabscript = matlabscript.replace('#TARGETDESIGNSIZE', str(sample_size))
    script_fname = os.path.abspath(os.path.join(config.design_genconf.design_dir, 'Augment.m'))            
    with open(script_fname, 'w') as file:
        file.write(matlabscript)            
    shellcmd = 'matlab.exe -nosplash -nodesktop -minimize -r \"cd {0}; run (\'{1}\'); quit\"'.format( os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir)), 'Augment.m' )
    if os.path.exists(output_file): os.remove(output_file)
    proc = subprocess.Popen(shellcmd, shell=True)
    proc.wait()
    while not os.path.exists(output_file): time.sleep(1)
    T = Table('AugmentedDesign')
    T.build_from_csv(output_file)
    existing_configs, new_configs = AppendModelsFromTable(T, datamodel, config)
    return((existing_configs, new_configs))




#Entry point for the parent process
if __name__ == '__main__':           
    call_dir = os.getcwd()
    normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
    normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
    tree = xml_conf.getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    config = davosconf.ExperimentalDesignConfig
    config.ConfigFile = normconfig
    datamodel = DataModel()
    datamodel.ConnectDatabase( davosconf.get_DBfilepath(False), davosconf.get_DBfilepath(True) )
    datamodel.RestoreHDLModels(None)

    #1. Build or Read factorial configurations
    #existing_models, new_models  = Create_FactorialDesign_Matlab(datamodel, config)
    #console_message('Already implemented (from database): {0}, To be implemented (new): {1}'.format(len(existing_models), len(new_models)), ConsoleColors.Green)
    #if davosconf.platform == Platforms.Multicore:
    #    ImplementationTool.implement_models_multicore(config, new_models)
    #else:
    #    ImplementationTool.implement_models_Grid(config, new_models)

    #with open(os.path.join(config.design_genconf.tool_log_dir, 'SUMMARY.xml'), 'w') as f: 
    #    f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in (existing_models + new_models) ])))

    #datamodel.SaveHdlModels()

    existing_models, new_models  = Build_ExperimentalDesign(datamodel, config)
