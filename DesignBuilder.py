# Builds the datastructures and files for experimental flow:
# 1. Infers balanced and oprthogonal fractional factorial design
# 2. Builds internal data model and database descriptors for HDL models to be implemented (if any)
# 3. Exports the template configuration for fault injection tool
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
import glob
from subprocess import call
from sys import platform
from Datamanager import *
import string
import ImplementationTool



def create_factorial_configurations(datamodel, config):
    existing_configs, new_configs = ([], [])
    if config.factorial_config.table_of_factors != '' or config.factorial_config.resolution > 0:
        T = Table('FactorialDesign')
        #obtain fatorial design (table)
        if config.factorial_config.table_of_factors != '':            
            T.build_from_csv(os.path.normpath(os.path.join(config.call_dir, config.factorial_config.table_of_factors)))
        else:
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
            script_fname = os.path.abspath(os.path.join(config.design_genconf.design_dir, 'ParConfGen.m'))            
            with open(script_fname, 'w') as file:
                file.write(matlabscript)            
            shellcmd = 'matlab.exe -nosplash -nodesktop -minimize -r \"cd {0}; run (\'{1}\'); quit\"'.format( os.path.normpath(os.path.join(config.call_dir, config.design_genconf.design_dir)), 'ParConfGen.m' )
            if os.path.exists(generated_table_of_factors): os.remove(generated_table_of_factors)
            proc = subprocess.Popen(shellcmd, shell=True)
            proc.wait()
            while not os.path.exists(generated_table_of_factors):
                time.sleep(1)
            with open(generated_table_of_factors,'r') as file: 
                content = file.read()                
                content = content.replace('-1','0')
            with open(generated_table_of_factors,'w') as file: 
                file.write(content)                
            T.build_from_csv(generated_table_of_factors)
        flist = T.labels
        flist.sort()
        for i in range(T.rownum()):
            c = []
            for f in flist:
                a = FactorSetting()
                a.FactorName = f
                a.FactorVal = T.getByLabel(f, i)
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
            if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label))
            if 'Implprop' in m.Metrics:
                #config exist/already has been implemented previosuly - re-implement or omit
                if (m.Metrics['Implprop'] != None) and (not config.overwrite_existing):
                    existing_configs.append(m)   
                else:
                    new_configs.append(m)
            else:
                new_configs.append(m)
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
    existing_models, new_models  = create_factorial_configurations(datamodel, config)
    console_message('Already implemented (from database): {0}, To be implemented (new): {1}'.format(len(existing_models), len(new_models)), ConsoleColors.Green)
    if davosconf.platform == Platforms.Multicore:
        ImplementationTool.implement_models_multicore(config, new_models)
    else:
        ImplementationTool.implement_models_Grid(config, new_models)

    with open(os.path.join(config.design_genconf.tool_log_dir, 'SUMMARY.xml'), 'w') as f: 
        f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in (existing_models + new_models) ])))

    datamodel.SaveHdlModels()
