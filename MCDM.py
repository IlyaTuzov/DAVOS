# Implements multicriteria decision making procedures, used in DSE experiments
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------

import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), './SupportScripts'))
import xml.etree.ElementTree as ET
import shutil
import random
import glob
import copy
import ast
import math
from Davos_Generic import *
from Datamanager import *
import DerivedMetrics
from RegressionModel_Manager import *



#filter-out invalid configurations
def filter_population(population):
    valid, excluded = [], []
    for i in population:
        if ('Error' in i.Metrics) and ('Implprop' in i.Metrics) and isinstance(i.Metrics['Implprop'], dict) and ('VerificationSuccess' in i.Metrics['Implprop']) and ('FIT' in i.Metrics['Implprop']) and (i.Metrics['Error'] in ['', 0]) and (i.Metrics['Implprop']['VerificationSuccess'] > 0) and (i.Metrics['Implprop']['FIT'] > 0):
            valid.append(i)
        else:
            excluded.append(i)
    return((valid, excluded))



def derive_metrics(davosconf, datamodel):
    for d in davosconf.DecisionSupportConfig.DerivedMetrics:        
        for m in datamodel.HdlModel_lst:
            impl = None if 'Implprop' not in m.Metrics else m.Metrics['Implprop']
            inj =  None if 'Injectionstat' not in m.Metrics else m.Metrics['Injectionstat']
            v = getattr(DerivedMetrics, d.handler)(inj, impl, d.custom_arg)
            if v != None:
                m.Metrics[d.name] = v


def compute_score(configurations, davosconf):
    valid, excluded = filter_population(configurations)     
    for scenario in davosconf.DecisionSupportConfig.MCDM:
        minmax = dict()
        for k,v in scenario.variables.iteritems():
            minmax[k] = (min(c.Metrics['Implprop'][k] for c in valid), max(c.Metrics['Implprop'][k] for c in valid))
        for c in valid:
            c.Metrics['Implprop'][scenario.name] = float(0)
            for k,v in scenario.variables.iteritems():
                c.Metrics['Implprop'][scenario.name] += (v['weight']*c.Metrics['Implprop'][k]/minmax[k][1]) if v['goal']==AdjustGoal.max else (v['weight']*minmax[k][0]/c.Metrics['Implprop'][k])
        for c in excluded:
            if ('Implprop' not in c.Metrics) or (not isinstance(c.Metrics['Implprop'], dict)): c.Metrics['Implprop'] = dict()
            c.Metrics['Implprop'][scenario.name] = float(0)



    #valid, excluded = filter_population(configurations) 
    #max_freq = max(c.Metrics['Implprop']['FREQUENCY'] for c in valid)
    #min_fit  = min(c.Metrics['Implprop']['FIT'] for c in valid)
    #for c in valid:
    #    c.Metrics['Implprop']['Score_Balanced'] = (0.3*c.Metrics['Implprop']['FREQUENCY']/max_freq) + (0.7*min_fit/c.Metrics['Implprop']['FIT'])
    #for c in excluded:
    #    c.Metrics['Implprop']['Score_Balanced'] = 0.0



def is_dominated(candidate, individuals, properties):
    for i in individuals:
        flags = [i.Metrics['Implprop'][p] >= candidate.Metrics['Implprop'][p] for p in properties]
        if not False in flags:
            #print('{0} dominated by {1}'.format(candidate.Label, i.Label))
            return(True)
    return(False)




def pareto_sort(population, properties):
    pool = population[:]
    pool = sorted(pool, key = lambda x: (x.Metrics['Implprop'][properties[0]], x.Metrics['Implprop'][properties[1]]), reverse=True)
    pareto_fronts = []
    
    while len(pool)>0:
        #add best individuals for each metric to pareto set 
        pareto=[]
        for p in properties:
            item = sorted(pool, key = lambda x: (x.Metrics['Implprop'][p]), reverse=True)[0]
            if not item in pareto: pareto.append( item )
        for item in pool:
            if not is_dominated(item, pareto, properties):
                if not item in pareto:
                    pareto.append(item)
        pareto_fronts.append(pareto)
        for item in pareto:
            if item in pool:
                pool.remove(item)
    for rank in range(len(pareto_fronts)):
        for i in pareto_fronts[rank]: i.Metrics['ParetoRank']=rank
    for i in population:
        i.Metrics['CrowdingDistance']=0.0
    for pareto in pareto_fronts:
        for p in properties:
            pmax = sorted(population, key = lambda x: x.Metrics['Implprop'][p], reverse=True)[0].Metrics['Implprop'][p]
            pmin = sorted(population, key = lambda x: x.Metrics['Implprop'][p], reverse=False)[0].Metrics['Implprop'][p]

            pareto.sort(key = lambda x: (x.Metrics['Implprop'][p]), reverse=False)
            pareto[0].Metrics['CrowdingDistance'], pareto[-1].Metrics['CrowdingDistance'] = 1000.0, 1000.0
            if len(pareto)>2:
                for i in range(1,len(pareto)-1):
                    if not 'CrowdingDistance' in pareto[i].Metrics: pareto[i].Metrics['CrowdingDistance']=0.0
                    pareto[i].Metrics['CrowdingDistance'] = pareto[i].Metrics['CrowdingDistance'] + (pareto[i+1].Metrics['Implprop'][p]-pareto[i-1].Metrics['Implprop'][p])/(pmax-pmin)
        print('\n'.join(['{0}\t{1}\t{2}\t{3}\t{4}'.format(i.Label, i.Metrics['Implprop'][properties[0]], i.Metrics['Implprop'][properties[1]], i.Metrics['ParetoRank'], i.Metrics['CrowdingDistance']) for i in pareto]) + '\n-\n')
    for i in population: 
        i.Metrics['CrowdingDistanceInv']=1.0/i.Metrics['CrowdingDistance']
    return(pareto_fronts, sorted(population, key=lambda x: (x.Metrics['ParetoRank'], x.Metrics['CrowdingDistanceInv']), reverse=False))

        





