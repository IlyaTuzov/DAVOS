# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Automation of multicriteria decision making:
#           1. Computation of custom benchmarking metric (derived in the basis of raw PPA and Dependability attributes)
#           2. Ranking of configurations under study by weighted sum method (Dependability benchmarking)
#           3. Inference of regression models
#           4. Dependability-driven optimization (Design space exploration)
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------


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
import math
from Davos_Generic import *
from Datamanager import *
import DerivedMetrics
from RegressionModel_Manager import *
from EvalEngine import *
from FactorialDesignBuilder import *
import FFI.Host_Zynq
import EvalEngine
import ImplementationTool
import MCDM
import statistics

RmodelStdFolder = 'RegressionModels'
ModelSummary = 'Summary.xml'

VERIFY_CONFIGURATIONS = True


def infer_regression_models(davosconf, configurations, resdir, varlist = [] , vartype = {}):
    summaryfile = os.path.normpath(os.path.join(resdir, ModelSummary))
    if os.path.exists(summaryfile): os.remove(summaryfile)
    if not os.path.exists(resdir): os.makedirs(resdir)
    #1. Export Table of Samples (.csv)
    T = Table('Samples')
    if len(configurations) == 0:
        return
    FactorLabels = []
    ResponceVariableLabels = []
    ResponceVariableTypes = []
    valid_individuals = []
    for i in configurations:
        if isinstance(i.Metrics['Implprop'], dict) and i.Metrics['Implprop']['VerificationSuccess'] > 0:
            valid_individuals.append(i)
        else:
            print 'WARNING: infer_regression_models: skipping {}'.format(i.Label)
    #append factors
    for c in valid_individuals[-1].Factors:
        FactorLabels.append(c.FactorName)
        T.add_column(c.FactorName)
    for row in range(len(valid_individuals)):        
        T.add_row()
        for col in range(len(T.labels)):
            x = valid_individuals[row].get_factor_by_name(T.labels[col])
            T.put(row,col, x.FactorVal)
    #append responce variables
    metrics = valid_individuals[-1].get_flattened_metric_dict()
    for k, v in metrics.iteritems():
        if (len(varlist) > 0 and k in varlist) or varlist == []:
            if k in vartype.keys():
                ResponceVariableLabels.append(k)
                ResponceVariableTypes.append(vartype[k])
            elif isinstance(v, int):
                ResponceVariableLabels.append(k)
                ResponceVariableTypes.append('discrete')
            elif isinstance(v, float):
                ResponceVariableLabels.append(k)
                ResponceVariableTypes.append('continuous')
    for respvar_ind in range(len(ResponceVariableLabels)):
        lbl = ResponceVariableLabels[respvar_ind]
        T.add_column(lbl)   
        for row in range(len(valid_individuals)):
            if valid_individuals[row].Metrics['Implprop']['VerificationSuccess'] > 0:
                metrics = valid_individuals[row].get_flattened_metric_dict()
                T.put(row, len(FactorLabels)+respvar_ind, metrics[lbl])

    matlab_input_file = os.path.join(resdir, 'RegressionAnalysisInput.csv') 
    with open(matlab_input_file, 'w') as f:
        f.write(T.to_csv(',', False))
    with open(os.path.join(davosconf.call_dir, 'SupportScripts', 'AnovaRegression.m'), 'r') as f:
        matlabscript = f.read()
    matlabscript = matlabscript.replace('#INPFILE', '\'{0}\''.format(matlab_input_file)).replace('#RESFOLDER', '\'{0}/\''.format(unixstyle_path(resdir)))
    matlabscript = matlabscript.replace('#FACTORLABELS', '{{{0}}}'.format(", ".join(["'{0}'".format(c) for c in FactorLabels])))
    matlabscript = matlabscript.replace('#RESPONSEVARIABLELABELS', '{{ {0} }}'.format(", ".join(["'{0}'".format(c) for c in ResponceVariableLabels])))
    matlabscript = matlabscript.replace('#RESPONSEVARIABLETYPES', '{{{0}}}'.format(", ".join(["'{0}'".format(c) for c in ResponceVariableTypes])))
    with open(os.path.join(davosconf.report_dir, 'AnovaRegression.m'), 'w') as f:
        f.write(matlabscript)
    shellcmd = 'matlab.exe -nosplash -nodesktop -minimize -r \"cd {0}; run (\'{1}\'); quit\"'.format( davosconf.report_dir, 'AnovaRegression.m' )
    proc = subprocess.Popen(shellcmd, shell=True)
    proc.wait()
    while not os.path.exists(summaryfile):
        time.sleep(1)
    return((FactorLabels, ResponceVariableLabels))


#1 for main effects, 2 for 2-factor interactions, etc.
def compute_degrees_of_freedom(config, order_or_effects = 1):
    df = []
    for f in config.factorial_config.factors:
        df.append(len(f.setting) - 1)
    if order_or_effects == 1:
        return( sum(df) + 1)





if __name__ == "__main__": 
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
    random.seed(1)   
    mcdm_vars = [c.name for c in davosconf.DecisionSupportConfig.MCDM]
    
    eval_time_impl, eval_time_ffi = [], []
    for c in datamodel.HdlModel_lst:
        c.Metrics['Predicted'] = dict()
        if not 'EvalTime' in c.Metrics:
            continue
        if isinstance(c.Metrics['EvalTime'], dict):
            if 'Implementation' in c.Metrics['EvalTime'] and 'Synthesis' in c.Metrics['EvalTime']  and 'RobustnessAssessment' in c.Metrics['EvalTime']:
                eval_time_impl.append( (float(c.Metrics['EvalTime']['Synthesis']) + float(c.Metrics['EvalTime']['Implementation']))/3600.0 )
                eval_time_ffi.append( float(c.Metrics['EvalTime']['RobustnessAssessment']) / 3600.0)
    DefConf = CreateDefaultConfig(datamodel, config)
    for m in datamodel.HdlModel_lst:        
        if ('Error' in m.Metrics) and (not isinstance(m.Metrics['Error'], str)):
            m.Metrics['Error']  = ''


    print('Mean Impl Time: {0:.2f} ({1:.2f}) \nMean FFI time: {2:.2f} ({3:.2f})\nTotal Conf: {4:d}'.format(statistics.mean(eval_time_impl), statistics.stdev(eval_time_impl), statistics.mean(eval_time_ffi),statistics.stdev(eval_time_ffi), len(eval_time_ffi)))
    print('Total Impl time: {0:.1f}\nTotal FFI time: {1:.1f}'.format(sum(eval_time_impl)/6, sum(eval_time_ffi)/2))
    raw_input('any key to continue...')


    MCDM.compute_score(datamodel.HdlModel_lst, davosconf) 
     


    #print('\n'.join(['{0} = {1}'.format(k, str(v)) for k,v in DefConf.Metrics['Implprop'].iteritems()]))
    #raw_input('...')

    #resdir = os.path.join(davosconf.report_dir, '{}_sample_{}'.format(RmodelStdFolder, str(168)))
    #FactorLabels = [f.factor_name for f in davosconf.ExperimentalDesignConfig.factorial_config.factors]
    #RM = RegressionModelManager(FactorLabels)
    #RM.load_significant(os.path.join(davosconf.report_dir, resdir), 1.0)
    #RM.compile_estimator_script_multilevel(resdir)
    #stat = RM.get_min_max_terms()
    #DefSettingDict = DefConf.get_setting_dict()
    
    #RM.export_summary(davosconf, os.path.join(resdir,'summary_models.csv'), [DefSettingDict[key] for key in sorted(DefSettingDict.keys())])
    #raw_input('Custom script success')

    
    #FactorLabels = ['X01', 'X02', 'X03', 'X04', 'X05', 'X06', 'X07', 'X08', 'X09', 'X10', 'X11', 'X12', 'X13', 'X14', 'X15', 'X16', 'X17', 'X18', 'X19', 'X20', 'X21', 'X22', 'X23', 'X24', 'X25', 'X26', 'X27', 'X28', 'X29', 'X30']
    #resdir = 'C:\Projects\Controllers\Doptimal\RegressionModels_sample_196'
    #RM = RegressionModelManager(FactorLabels)
    #RM.load_significant(os.path.join(davosconf.report_dir, resdir), 1.0)
    #RM.compile_estimator_script_multilevel(resdir)
    #defres = RM.evaluate_python([0,2,0,3,3,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,1,7,0,17,0,0,0,5,0,3])
    #print(str(defres))
    #stat = RM.get_min_max_terms()
    #with open(os.path.join(resdir, 'Stat_v1.txt'), 'w') as file:
    #    for k, v in stat.iteritems():
    #        file.write('\n\nModel: {}'.format(str(k)))
    #        for term in v:
    #            file.write('\n{0}\t\t{1:.3f} : {2:.3f}'.format(str(term[0]), term[1], term[2]))

    existing_models=[]
    for c in datamodel.HdlModel_lst:
        if c.ID == 344:
            existing_models.append(c)
            c.Metrics['Implprop']=dict()
            break



    

    if davosconf.DecisionSupport:
        if davosconf.DecisionSupportConfig.task == 'DSE':
            if davosconf.DecisionSupportConfig.method == 'Statistical':
                #build a list of configurations to implement and evaluate
                existing_models, new_models  = Build_ExperimentalDesign(datamodel, config)   
                new_models.append(DefConf)                                                                                                                           
                os.chdir(config.call_dir)
                #Instantiate evaluation engine and initialize it
                JM = JobManager(davosconf)

                if config.factorial_config.design_type == 'Doptimal':
                    sample_size = compute_degrees_of_freedom(config, 1)   
                    excluded = []                 
                    for i in range(5):
                        print '\nAdjusted sample size {0:d}\n'.format(sample_size)
                        valid_sample = False
                        while not valid_sample:
                            for c in existing_models + new_models:
                                c.Metrics['SampleSizeGoal'] = int(0)
                                c.Metrics['ErrorMarginGoal'] = float(0.10)
                            #supply configurations to the evaluation engine
                            configurations = evaluate(existing_models + new_models, davosconf, JM, datamodel, False)
                            #for dut in configurations:
                            #    try:
                            #        if ('Implprop' in dut.Metrics) and ('Error' in dut.Metrics) and (dut.Metrics['Error'] == '' or dut.Metrics['Error'] == 0):
                            #            ImplementationTool.power_simulation(dut, davosconf)
                            #            datamodel.SaveHdlModels()
                            #    except:
                            #        print('Exception in power_simulation: {0}'.format(str(sys.exc_info()[0])))
                            #datamodel.SaveHdlModels()
                            MCDM.compute_score(configurations, davosconf)

                            configurations = [item for item in configurations if item.Label != DefConf.Label]
                            datamodel.SaveHdlModels()
                            export_DatamodelStatistics(datamodel, os.path.join(config.design_genconf.design_dir, config.statfile))
                            configurations, buf = MCDM.filter_population(configurations)
                            if len(configurations) == 0:
                                print 'Warning: all configurations filtered-out'
                            excluded = excluded + buf
                            #excluded = datamodel.HdlModel_lst
                            if len(configurations) < sample_size:
                                existing_models, new_models = augment_design(configurations, excluded + configurations, datamodel, config, sample_size)
                                valid_sample = False
                            else:
                                valid_sample = True

                        MCDM.compute_score(configurations, davosconf)
                        resdir = os.path.join(davosconf.report_dir, '{}_sample_{}'.format(RmodelStdFolder, str(sample_size)))
                        FactorLabels, ResponceVariableLabels = infer_regression_models(davosconf, configurations, resdir,  ['FREQUENCY', 'FIT', 'CriticalBits', 'FailureRate', 'POWER_PL', 'UTIL_LUT', 'UTIL_FF']+mcdm_vars, {'CriticalBits':'continuous', 'UTIL_DSP':'discrete', 'UTIL_BRAM':'discrete'})
                        RM = RegressionModelManager(FactorLabels)
                        RM.load_significant(os.path.join(davosconf.report_dir, resdir), 1.0)
                        RM.compile_estimator_script_multilevel(resdir)
                        stat = RM.get_min_max_terms()
                        with open(os.path.join(resdir, 'Stat_v1.txt'), 'w') as file:
                            for k, v in stat.iteritems():
                                file.write('\n\nModel: {}'.format(str(k)))
                                for term in v:
                                    file.write('\n{0}\t\t{1:.3f} : {2:.3f}'.format(str(term[0]), term[1]*1000, term[2]*1000))



                        if VERIFY_CONFIGURATIONS and (sample_size in [168, 224]):
                            predicted = RM.get_min_max_linear(DefConf.get_setting_dict())
                            bestconflist = []
                            if predicted != None:
                                for varname, prop in predicted.iteritems():
                                    if varname in ['FREQUENCY']+mcdm_vars:
                                        best_val = prop[1]
                                        best_conf = prop[3]
                                    else:
                                        best_val = prop[0]
                                        best_conf = prop[2]
                                    bestconf = CreateConfigForSetting(datamodel, config, best_conf)
                                    if bestconf != None:
                                        if ('Predicted' in bestconf.Metrics) and len(bestconf.Metrics['Predicted']) > 0:
                                            #best config for this response var coincides with the best config for some other var
                                            bestconf.Metrics['Predicted']['BestVar'] += '+{0}'.format(varname)
                                        else: 
                                            bestconf.Metrics['Predicted'] = dict()
                                            for k,v in RM.evaluate_python(best_conf).iteritems():
                                                bestconf.Metrics['Predicted'][k+'_Predicted'] = v
                                            bestconf.Metrics['Predicted']['BestVar'] = varname
                                            bestconf.Metrics['Predicted']['BestVal'] = best_val
                                            bestconf.Metrics['Predicted']['BestConf'] = ','.join(map(str, best_conf))
                                            bestconf.Metrics['Predicted']['SampleSize'] = sample_size
                                            bestconflist.append(bestconf)

                            datamodel.SaveHdlModels()
                            #print(str(bestconflist))
                            if len(bestconflist) > 0:
                                print 'Evaluating Predicted Configurations at {} sample size'.format(str(sample_size))
                                for c in bestconflist:
                                    c.Metrics['SampleSizeGoal'] = int(0)
                                    c.Metrics['ErrorMarginGoal'] = float(0.10)
                                bestconflist = evaluate(bestconflist, davosconf, JM, datamodel, False)
                                datamodel.SaveHdlModels()


                                #if some best configurations are invalid - check suboptimal configurations
                                altconfigs = []
                                for c in bestconflist:
                                    if c.Metrics['Error'] != '':
                                        bestvar = c.Metrics['Predicted']['BestVar']
                                        goal = OptimizationGoals.min if c.Metrics['Predicted']['BestVar'] in ['EssentialBits', 'CriticalBits', 'FailureRate', 'FIT', 'POWER_PL', 'UTIL_LUT', 'UTIL_FF', 'UTIL_BRAM', 'UTIL_DSP'] else OptimizationGoals.max
                                        altern_settings = RM.get_alternative_configurations(bestvar.split('+')[0], c.get_setting_dict(), goal)
                                        for s in altern_settings:
                                            AltConf = CreateConfigForSetting(datamodel, config, s)
                                            if AltConf!= None:
                                                AltConf.Metrics['Predicted'] = dict()
                                                for k,v in RM.evaluate_python(s).iteritems():
                                                    AltConf.Metrics['Predicted'][k+'_Predicted'] = v
                                                AltConf.Metrics['Predicted']['BestVar'] = bestvar 
                                                AltConf.Metrics['Predicted']['BestVal'] = AltConf.Metrics['Predicted'][bestvar.split('+')[0]+'_Predicted']
                                                AltConf.Metrics['Predicted']['BestConf'] = ','.join(map(str, s))
                                                AltConf.Metrics['Predicted']['SampleSize'] = sample_size
                                                AltConf.Metrics['SampleSizeGoal'], AltConf.Metrics['ErrorMarginGoal'] = int(0), float(0.10)
                                                altconfigs.append(AltConf)
                                bestconflist = evaluate(bestconflist+altconfigs, davosconf, JM, datamodel, False)

                                #for dut in bestconflist+altconfigs:
                                #    ImplementationTool.power_simulation(dut, davosconf)
                                #    datamodel.SaveHdlModels()

                                MCDM.compute_score(bestconflist, davosconf)                                    
                                varlist =  ['FREQUENCY', 'FIT', 'CriticalBits', 'FailureRate', 'POWER_PL', 'UTIL_LUT', 'UTIL_FF'] +mcdm_vars + bestconflist[0].Metrics['Predicted'].keys()
                                #varlist =  bestconflist[0].Metrics['Implprop'] + bestconflist[0].Metrics['Predicted'].keys()
                                T = configs_to_table(bestconflist, varlist)
                                with open(os.path.join(resdir,'Predicted.csv'), 'w') as f:
                                    f.write(T.to_csv(';', False))                            
                                raw_input('Predicted config evaluated for sample size {0}, press any key to continue...'.format(str(sample_size)))
                            datamodel.SaveHdlModels()







                        sample_size+=int(math.ceil(0.5*compute_degrees_of_freedom(config, 1)))
                

                #Derive custom metrics
#                derive_metrics(config, datamodel)

                

                #Multicriteria Decision Analysis
#                RM = RegressionModelManager(FactorLabels)
#                RM.load_all(os.path.join(config.report_dir, RmodelStdFolder))
#                RM.compile_estimator_script(os.path.join(config.report_dir, RmodelStdFolder))
        


        #res = RM.evaluate_python([0,1, 0,   1,0,    0, 0,0,0,0,0,0,0,0,0,0,0,0,1,0,1,1,   0, 0, 0, 1, 0,1, 0,0,0])        
        #for i in range(1000):
        #    res = RM.evaluate_python([random.randint(0,1),random.randint(0,1),random.randint(0,1),random.randint(0,1),1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1,1,0,0,1,1,random.randint(0,1)])
        #    print(str(res))

    datamodel.SaveHdlModels()
