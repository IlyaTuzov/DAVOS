# Automation of multicriteria decision making (module under active refactoring - functionality from previous version in ./DesicionSupport folder)
# 1. Computation of custom benchmarking metric (derived in the basis of raw PPA and Dependability attributes)
# 2. Ranking of configurations under study by weighted sum method (Dependability benchmarking)
# 3. Inference of regression models - currently requries matlab
# 4. Optimization (Design space exploration) - WSM and Pareto,
#    uses embedded logic under small set of significant factors, otherwise CUDA-based tool to accelerate the process
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), './SupportScripts'))
import xml.etree.ElementTree as ET
import re
import stat
import subprocess
import shutil
import datetime
import time
import random
import glob
import copy
import ast
from Davos_Generic import *
from Datamanager import *
import DerivedMetrics
from RegressionModel_Manager import *

RmodelStdFolder = 'RegressionModels'

def derive_metrics(davosconf, datamodel):
    for d in davosconf.DecisionSupportConfig.DerivedMetrics:        
        for m in datamodel.HdlModel_lst:
            impl = None if 'Implprop' not in m.Metrics else m.Metrics['Implprop']
            inj =  None if 'Injectionstat' not in m.Metrics else m.Metrics['Injectionstat']
            v = getattr(DerivedMetrics, d.handler)(inj, impl, d.custom_arg)
            if v != None:
                m.Metrics[d.name] = v



def infer_regression_models(davosconf, datamodel):
    resdir = os.path.join(config.report_dir, RmodelStdFolder)
    summaryfile = os.path.normpath(os.path.join(resdir, 'MatlabSummary.xml'))
    if os.path.exists(summaryfile): os.remove(summaryfile)
    if not os.path.exists(resdir): os.makedirs(resdir)
    #1. Export Table of Samples (.csv)
    T = Table('Samples')
    if len(datamodel.HdlModel_lst) == 0:
        return
    FactorLabels = []
    ResponceVariableLabels = []
    ResponceVariableTypes = []
    #append factors
    for c in datamodel.HdlModel_lst[-1].Factors:
        FactorLabels.append(c.FactorName)
        T.add_column(c.FactorName)
    for row in range(len(datamodel.HdlModel_lst)):
        T.add_row()
        for col in range(len(T.labels)):
            x = datamodel.HdlModel_lst[row].get_factor_by_name(T.labels[col])
            T.put(row,col, x.FactorVal)
    #append responce variables
    metrics = datamodel.HdlModel_lst[-1].get_flattened_metric_dict()
    for k, v in metrics.iteritems():
        if isinstance(v, int):
            ResponceVariableLabels.append(k)
            ResponceVariableTypes.append('discrete')
        if isinstance(v, float):
            ResponceVariableLabels.append(k)
            ResponceVariableTypes.append('continuous')
    for respvar_ind in range(len(ResponceVariableLabels)):
        lbl = ResponceVariableLabels[respvar_ind]
        T.add_column(lbl)   
        for row in range(len(datamodel.HdlModel_lst)):
            metrics = datamodel.HdlModel_lst[row].get_flattened_metric_dict()
            T.put(row, len(FactorLabels)+respvar_ind, metrics[lbl])

    matlab_input_file = 'RegressionAnalysisInput.csv'
    with open(os.path.join(config.report_dir, matlab_input_file), 'w') as f:
        f.write(T.to_csv(',', False))
    with open(os.path.join(config.call_dir, 'SupportScripts', 'AnovaRegression.m'), 'r') as f:
        matlabscript = f.read()
    matlabscript = matlabscript.replace('#INPFILE', '\'{0}\''.format(matlab_input_file)).replace('#RESFOLDER', '\'{0}/\''.format(unixstyle_path(resdir)))
    matlabscript = matlabscript.replace('#FACTORLABELS', '{{{0}}}'.format(", ".join(["'{0}'".format(c) for c in FactorLabels])))
    matlabscript = matlabscript.replace('#RESPONSEVARIABLELABELS', '{{ {0} }}'.format(", ".join(["'{0}'".format(c) for c in ResponceVariableLabels])))
    matlabscript = matlabscript.replace('#RESPONSEVARIABLETYPES', '{{{0}}}'.format(", ".join(["'{0}'".format(c) for c in ResponceVariableTypes])))
    with open(os.path.join(config.report_dir, 'AnovaRegression.m'), 'w') as f:
        f.write(matlabscript)
    shellcmd = 'matlab.exe -nosplash -nodesktop -minimize -r \"cd {0}; run (\'{1}\'); quit\"'.format( config.report_dir, 'AnovaRegression.m' )
    proc = subprocess.Popen(shellcmd, shell=True)
    proc.wait()
    while not os.path.exists(summaryfile):
        time.sleep(1)
    return((FactorLabels, ResponceVariableLabels))


    


if __name__ == "__main__": 
    normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
    normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
    tree = xml_conf.getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    print (to_string(config, "Configuration: "))
    datamodel = DataModel()
    datamodel.ConnectDatabase( config.get_DBfilepath(False), config.get_DBfilepath(True) )
    datamodel.RestoreHDLModels(None)

    if config.DecisionSupport:
        #1. Derive custom metrics
        derive_metrics(config, datamodel)
        #2. Regression analysis (DSE case): infer regression models for each metric as function of input factors: Metric = f(Xi)
        FactorLabels, ResponceVariableLabels = infer_regression_models(config, datamodel)



        #3. Multicriteria Decision Analysis (both benchmarking and DSE)                
        RM = RegressionModelManager(FactorLabels)
        RM.load_all(os.path.join(config.report_dir, RmodelStdFolder))
        RM.compile_estimator_script(os.path.join(config.report_dir, RmodelStdFolder))
        
        #res = RM.evaluate_python([0,1, 0,   1,0,    0, 0,0,0,0,0,0,0,0,0,0,0,0,1,0,1,1,   0, 0, 0, 1, 0,1, 0,0,0])        
        #for i in range(1000):
        #    res = RM.evaluate_python([random.randint(0,1),random.randint(0,1),random.randint(0,1),random.randint(0,1),1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,0,0,1,1,random.randint(0,1)])
        #    print(str(res))

    datamodel.SaveHdlModels()
