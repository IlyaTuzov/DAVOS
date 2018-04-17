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

def derive_metrics(davosconf, datamodel):
    for d in davosconf.DecisionSupportConfig.DerivedMetrics:        
        for m in datamodel.HdlModel_lst:
            impl = None if 'Implprop' not in m.Metrics else m.Metrics['Implprop']
            inj =  None if 'Injectionstat' not in m.Metrics else m.Metrics['Injectionstat']
            m.Metrics[d.name] = getattr(DerivedMetrics, d.handler)(inj, impl, d.custom_arg)
        



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

        #3. Multicriteria Decision Analysis (both benchmarking and DSE)

    datamodel.SaveHdlModels()
