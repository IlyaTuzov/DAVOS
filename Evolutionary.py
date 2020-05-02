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
import random
import multiprocessing
import copy
from subprocess import call
from sys import platform
from Datamanager import *
import ImplementationTool
from EvalEngine import *
from itertools import combinations
import math
from FactorialDesignBuilder import *
import ImplementationTool
import DecisionSupport


POPULATION_SIZE = int(18)
SELECTION_SIZE  = int(9)
SAMPLE_INCREMENT = 10000

def get_random_individual(datamodel, config):
    c = []
    for factor in config.factorial_config.factors:
        a = FactorSetting()
        a.FactorName = factor.factor_name
        a.OptionName = factor.option_name
        a.Phase = factor.phase_name
        a.FactorVal = random.choice(list(factor.setting.keys()))
        a.OptionVal = factor.setting[a.FactorVal]
        c.append(a)
    m = datamodel.GetOrCreateHDLModel(c)
    if m.Label == '': m.Label = '{0}{1:03d}'.format(config.design_genconf.design_label, m.ID)
    if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label))
    return(m)



#Read some random configurations from file
def init_from_file(datamodel, config):
    existing_configs, new_configs = [], []
    if config.factorial_config.table_of_factors != '' and os.path.exists(os.path.normpath(os.path.join(config.call_dir, config.factorial_config.table_of_factors))):    
        T = Table('FactorialDesign')        
        T.build_from_csv(os.path.normpath(os.path.join(config.call_dir, config.factorial_config.table_of_factors)))
    else:
        return([])
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
    return(new_configs+existing_configs)








def filter(P):
    res, filtered_out  = [], []
    for i in P:
        if i.Metrics['Implprop']['FREQUENCY'] >= 2.0 and (i.Metrics['Error']=='' or i.Metrics['Error']==0):
            res.append(i)
        else:
            #print('\nFilter: {0} filtered out by frequency = {1}'.format(i.Label, str(i.Metrics['Implprop']['FREQUENCY'])))
            filtered_out.append(i)
    return(res, filtered_out)






#return the new population maintaining N/2 best indivuduals
def selection_simple(individuals):
    selected = []
    rest = []
    individuals.sort(key = lambda x: x.Metrics['Score'], reverse = True)    
    for i in individuals:
        if i.Metrics['Score'] > 0.0 and len(selected) < len(individuals)/2:
            selected.append(i)
        else:
            rest.append(i)
    return(selected, rest)
    #return(individuals[0:len(individuals)/2], individuals[len(individuals)/2:])

#create and M new chromosomes from M invidividuals, append to population
class CrossoverTypes:
    SinglePoint, MultiPoint, Uniform = list(range(3))




def crossover_simple(individuals, CrossType):
    res = []
    if len(individuals) < 2: return(res)
    for i in range(len(individuals)/2):
        parent_a = individuals[i*2 + 0]
        parent_b = individuals[i*2 + 1]
        chromosoma_1, chromosoma_2  = [], []
        if CrossType == CrossoverTypes.Uniform:
            for i in range(len(parent_a.Factors)):
                point = random.choice([0,1])
                gene_1 = parent_a.Factors[i] if point==0 else parent_b.Factors[i]
                gene_2 = parent_a.Factors[i] if point==1 else parent_b.Factors[i]
                chromosoma_1.append(copy.copy(gene_1))
                chromosoma_2.append(copy.copy(gene_2))
        res.append(chromosoma_1)
        res.append(chromosoma_2)
    return(res)


def crossover_elitist(individuals, CrossType, ind_cnt):
    res = []
    if len(individuals) < 2: return(res)
    while len(res) < ind_cnt:
        parent_a = individuals[0]
        for parent_b in individuals[1:]:
            chromosoma_1, chromosoma_2  = [], []
            if CrossType == CrossoverTypes.Uniform:
                for i in range(len(parent_a.Factors)):
                    point = random.choice([0,1])
                    gene_1 = parent_a.Factors[i] if point==0 else parent_b.Factors[i]
                    gene_2 = parent_a.Factors[i] if point==1 else parent_b.Factors[i]
                    chromosoma_1.append(copy.copy(gene_1))
                    chromosoma_2.append(copy.copy(gene_2))
            res.append(chromosoma_1)
            res.append(chromosoma_2)
    return(res[:ind_cnt])


#do not touch the best individual
def mutate(chromosomes, config, probability, factor_diversity = False):
    #weights vector - probability to select the given gene for mutation
    w, wp = [], []
    #for i in config.factorial_config.factors: w.append(len(i.setting))
    for i in config.factorial_config.factors: w.append(int(math.ceil(math.log(len(i.setting),2))))
    for i in range(len(w)): wp.append(float(w[i])/float(sum(w)))
    #print 'Probability vector check: {0:.3f}'.format(sum(wp))
    for i in chromosomes:
        #chek whether mutation will be applied
        if random.randint(0,100) < probability:
            #select random gene with it's weight as probability
            t = random.uniform(0, 1)
            index = 0; t -= wp[index]
            while t > 0:
                index +=1
                t -= wp[index]
            #mutate gene[index]
            f = config.factorial_config.factors[index]
            i[index].FactorVal = random.choice(list( set(f.setting.keys()) - set([i[index].FactorVal]) ))
            i[index].OptionVal = f.setting[i[index].FactorVal]
            print('Mutated factor {} = {}'.format(str(index), str(i[index].FactorVal)))
    if factor_diversity:
        for index in range(len(config.factorial_config.factors)):
            #print(str(index)+ ": "+ ", ".join([str(x[index].FactorVal) for x in chromosomes]))
            diverse_levels = set()
            for c in chromosomes:
                diverse_levels.add(c[index].FactorVal)
            if len(diverse_levels) < 2:
                #select random chromosome and change the gene [index]
                c = random.choice(chromosomes)
                f = config.factorial_config.factors[index]
                z = set(f.setting.keys()) - diverse_levels
                if len(z) > 0:                
                    c[index].FactorVal = random.choice(list(z))
                    c[index].OptionVal = f.setting[c[index].FactorVal]
                    print('Mutation: Force mutation of factor {}:  {} = {}'.format(str(index), str(c[index].FactorVal), str(c[index].OptionVal)))
    return(chromosomes)


def create_individuals(davosconf, chromosomes, datamodel):
    res = []
    for i in chromosomes:
        m = datamodel.GetOrCreateHDLModel(i)
        if m.Label == '': m.Label = '{0}{1:03d}'.format(davosconf.ExperimentalDesignConfig.design_genconf.design_label, m.ID)
        if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(davosconf.ExperimentalDesignConfig.design_genconf.design_dir, m.Label))
        res.append(m)
    return(res)


def create_individual(davosconf, chromosome, datamodel):
    m = datamodel.GetOrCreateHDLModel(chromosome)
    if m.Label == '': m.Label = '{0}{1:03d}'.format(davosconf.ExperimentalDesignConfig.design_genconf.design_label, m.ID)
    if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(davosconf.ExperimentalDesignConfig.design_genconf.design_dir, m.Label))
    return(m)



def log_results(config, iteration, timemark, selected, rest):
    labels = sorted([x.FactorName for x in selected[0].Factors])
    with open(os.path.join(config.design_genconf.tool_log_dir, 'Iteration_{0}.csv').format(str(iteration)), 'w') as f:
        f.write('sep = ;\nIteration;Time;Label;Status;ParetoRank;CrowdingDistance;Frequency;EssentialBits;Injection;Failures;FailureRate;FailureRateMargin;FIT;FITMargin;MTTF;Error;SynthesisTime;ImplementationTime;RobustnessAssessmentTime;'+ ';'.join(labels))    
        for i in selected:
            f.write('\n{0};{1};{2};{3};{4:d};{5:.4f};{6:.4f};{7:d};{8:d};{9:d};{10:.4f};{11:.4f};{12:.4f};{13:.4f};{14:.4f};{15};{16};{17};{18}'.format(
                iteration, str(int(timemark)), i.Label, 'Selected', i.Metrics['ParetoRank'] if 'ParetoRank' in i.Metrics else '-', i.Metrics['CrowdingDistance'] if 'CrowdingDistance' in i.Metrics else '-',
                i.Metrics['Implprop']['FREQUENCY'], i.Metrics['Implprop']['EssentialBits'], i.Metrics['Implprop']['Injections'], i.Metrics['Implprop']['Failures'], i.Metrics['Implprop']['FailureRate'], i.Metrics['Implprop']['FailureRateMargin'], i.Metrics['Implprop']['FIT'], i.Metrics['Implprop']['FITMargin'], i.Metrics['Implprop']['MTTF'], i.Metrics['Error'], str(i.Metrics['EvalTime']['Synthesis']), str(i.Metrics['EvalTime']['Implementation']), str(i.Metrics['EvalTime']['RobustnessAssessment']) ) )
            for l in labels: f.write(';{0:d}'.format(i.get_factor_by_name(l).FactorVal))
        for i in rest:
            if not 'RobustnessAssessment' in i.Metrics['EvalTime']: i.Metrics['EvalTime']['RobustnessAssessment']=int(0)
            f.write('\n{0};{1};{2};{3};{4};{5:.4f};{6:.4f};{7:d};{8:d};{9:d};{10:.4f};{11:.4f};{12:.4f};{13:.4f};{14:.4f};{15};{16};{17};{18}'.format(
                iteration, str(int(timemark)), i.Label, '-', 
                i.Metrics['ParetoRank'] if 'ParetoRank' in i.Metrics else '-', 
                i.Metrics['CrowdingDistance'] if 'CrowdingDistance' in i.Metrics else 0.0,
                i.Metrics['Implprop']['FREQUENCY'] if 'FREQUENCY' in i.Metrics['Implprop'] else 0.0, 
                i.Metrics['Implprop']['EssentialBits'] if 'EssentialBits' in i.Metrics['Implprop'] else 0, 
                i.Metrics['Implprop']['Injections'] if 'Injections' in i.Metrics['Implprop'] else 0,
                i.Metrics['Implprop']['Failures'] if 'Failures' in i.Metrics['Implprop'] else 0, 
                i.Metrics['Implprop']['FailureRate'] if 'FailureRate' in i.Metrics['Implprop'] else 0.0,
                i.Metrics['Implprop']['FailureRateMargin'] if 'FailureRateMargin' in i.Metrics['Implprop'] else 0.0, 
                i.Metrics['Implprop']['FIT'] if 'FIT' in i.Metrics['Implprop'] else 0.0, 
                i.Metrics['Implprop']['FITMargin'] if 'FITMargin' in i.Metrics['Implprop'] else 0.0, 
                i.Metrics['Implprop']['MTTF'] if 'MTTF' in i.Metrics['Implprop'] else 0.0, 
                i.Metrics['Error'], 
                str(i.Metrics['EvalTime']['Synthesis']) if 'Synthesis' in i.Metrics['EvalTime'] else '0', 
                str(i.Metrics['EvalTime']['Implementation']) if 'Implementation' in i.Metrics['EvalTime'] else '0',
                str(i.Metrics['EvalTime']['RobustnessAssessment']) if 'RobustnessAssessment' in  i.Metrics['EvalTime'] else '0') )
            for l in labels: f.write(';{0:d}'.format(i.get_factor_by_name(l).FactorVal))
        with open(os.path.join(config.design_genconf.tool_log_dir, 'MODELS.xml'), 'w') as f: 
            f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in (datamodel.HdlModel_lst) ])))




def GeneticSearch_PresiceRanking(config, JM, datamodel):
    iteration = 0
    population = []
    #Build initial random population    
    for i in range(POPULATION_SIZE):
        population.append(get_random_individual(datamodel, config))
    timestart = time.time()
    while(True):
        iteration+=1
        population = evaluate(population, config, JM, datamodel)
        datamodel.SaveHdlModels()
        parents, rest    = selection_simple(population)
        log_results(config, iteration, time.time()-timestart, parents, rest)
        print 'Iteration: {0:d}, Selected: {1}\n\n'.format(iteration, ', '.join([str(x.Metrics['Implprop']['Failures']) for x in parents]))       
        new_ind_cnt = POPULATION_SIZE - len(parents)
        if len(parents) > 1:
            chromosomes = crossover_elitist(parents, CrossoverTypes.Uniform, new_ind_cnt)              
            chromosomes = mutate(chromosomes, config, 50)
            children = create_individuals(chromosomes, datamodel)    #select inviduals with matching chromosomes from DB, otherwise create new ones to be evaluated(implemented)
        else:
            for i in range(new_ind_cnt):
                children.append(get_random_individual(datamodel, config))
        population = parents + children
















#select M best individuals by iteratively refining the confidence intervals for their metrics
def selection_adaptive(Input_Population, M, davosconf, JM, datamodel, rank_selected=False):
    T, P = Input_Population[:], Input_Population[:]
    while len(T) > 0:
        for i in T:
            if not 'SampleSizeGoal'  in i.Metrics: i.Metrics['SampleSizeGoal']  = int(SAMPLE_INCREMENT)
            if not 'ErrorMarginGoal' in i.Metrics: i.Metrics['ErrorMarginGoal'] = float(0)           
        T = evaluate(T, davosconf, JM, datamodel)
        datamodel.SaveHdlModels()
        #filter by Frequency
        P, fc = filter(P)
        P.sort(key = lambda x: x.Metrics['ScoreMean'], reverse = True)
        T = []
        #check intersection of confidence intervals of top M individuals with the rest of population 
        for top in P[:M]:
            for bottom in P[M:]:
                overlap, l = intersect_intervals(top.Metrics['ScoreLow'], top.Metrics['ScoreHigh'], bottom.Metrics['ScoreLow'], bottom.Metrics['ScoreHigh'])
                if overlap:
                    print "\t{0}:{1:.4f}->{2:.4f} overlaps {3}:{4:.4f}->{5:.4f}".format(top.Label,top.Metrics['ScoreLow'], top.Metrics['ScoreHigh'], bottom.Label, bottom.Metrics['ScoreLow'], bottom.Metrics['ScoreHigh'])
                    if top.Metrics['Implprop']['FailureRateMargin'] >= 0.1 and (not top in T):
                         top.Metrics['SampleSizeGoal'] += int(SAMPLE_INCREMENT)
                         T.append(top)
                    if bottom.Metrics['Implprop']['FailureRateMargin'] >= 0.1 and (not bottom in T):
                         bottom.Metrics['SampleSizeGoal'] += int(SAMPLE_INCREMENT)
                         T.append(bottom) 
        #check intersection of confidence intervals of top M individuals amont themselves
        if rank_selected:
            for a in P[:M]:
                for b in P[:M]:
                    if a != b:
                        overlap, l = intersect_intervals(a.Metrics['ScoreLow'], a.Metrics['ScoreHigh'], b.Metrics['ScoreLow'], b.Metrics['ScoreHigh'])
                        if overlap:
                            print "\tRank Selected {0}:{1:.4f}->{2:.4f} overlaps {3}:{4:.4f}->{5:.4f}".format(a.Label, a.Metrics['ScoreLow'], a.Metrics['ScoreHigh'], b.Label, b.Metrics['ScoreLow'], b.Metrics['ScoreHigh'])
                            if a.Metrics['Implprop']['FailureRateMargin'] >= 0.1 and (not a in T):
                                 a.Metrics['SampleSizeGoal'] += int(SAMPLE_INCREMENT)
                                 T.append(a)
                            if b.Metrics['Implprop']['FailureRateMargin'] >= 0.1 and (not b in T):
                                 b.Metrics['SampleSizeGoal'] += int(SAMPLE_INCREMENT)
                                 T.append(b)             
        T.sort(key = lambda x: x.ID, reverse = False)
        print("Individuals to refine: \n\t{}".format("\n\t".join(["{0:3d} ({1:6d})".format(x.ID, x.Metrics['SampleSizeGoal']) for x in T])))
    selected = P[0:M]
    rest = []
    for i in Input_Population:
        if not i in selected:
            rest.append(i)
    rest.sort(key = lambda x: x.Metrics['ScoreMean'], reverse = True)
    return (selected, rest)


def crossover_exhaustive(individuals, CrossType):
    res = []
    if len(individuals) < 2: return(res)
    indexes = range(0,len(individuals))
    pairs = list(combinations(indexes, 2))
    for p in pairs:
        parent_a = individuals[p[0]]
        parent_b = individuals[p[1]]
        chromosoma_1, chromosoma_2  = [], []
        if CrossType == CrossoverTypes.Uniform:
            for i in range(len(parent_a.Factors)):
                point = random.choice([0,1])
                gene_1 = parent_a.Factors[i] if point==0 else parent_b.Factors[i]
                gene_2 = parent_a.Factors[i] if point==1 else parent_b.Factors[i]
                chromosoma_1.append(copy.copy(gene_1))
                chromosoma_2.append(copy.copy(gene_2))
        res.append(chromosoma_1)
        res.append(chromosoma_2)
    return(res)






def GeneticSearch_AdaptiveRanking(davosconf, JM, datamodel, starting_population, continue_iteration):
    #population = []
    #timestart = time.time()    
    #for i in datamodel.HdlModel_lst:
    #    if i.Label in ['AVR042','AVR047','AVR046','AVR054','AVR049','AVR032','AVR048','AVR053','AVR043','AVR055','AVR056','AVR057','AVR058','AVR059','AVR060','AVR061','AVR062','AVR063']:
    #        population.append(i)

    #population.sort(key=lambda x: x.Label, reverse=False)
    #iteration = 0
    
    population = []
    timestart = time.time()    
    iteration = continue_iteration if continue_iteration > 0 else 0        
    if len(starting_population) > 0:
        for i in starting_population:
            population.append(i)
    else:
        #Build initial random population    
        population = init_from_file(datamodel, davosconf.ExperimentalDesignConfig)
    while len(population) < POPULATION_SIZE:
        print 'Generating initial random population'
        ind = get_random_individual(datamodel, davosconf.ExperimentalDesignConfig)
        population.append(ind)
    for ind in population:
        ind.Metrics['CreatedAtIteration'] = iteration
    print('INIT population: \n{0}'.format('\n\n\n'.join([', '.join(['{0}={1}'.format(j.FactorName, j.FactorVal) for j in i.Factors]) for i in population])))
    raw_input('Any key to proceed...')    

    while(True):
        parents, rest = selection_adaptive(population, SELECTION_SIZE, davosconf, JM, datamodel)
        log_results(davosconf.ExperimentalDesignConfig, iteration, time.time()-timestart, parents, rest)
        datamodel.SaveHdlModels()
        print 'Iteration: {0:d}, Selected: {1}\n\n'.format(iteration, ', \n\n'.join([str(x.Metrics['Implprop']) for x in parents]))       
        new_ind_cnt = POPULATION_SIZE - len(parents)
        iteration+=1
        children = []
        while len(children) < new_ind_cnt:            
            if len(parents) > 1:
                chromosomes = crossover_exhaustive(parents, CrossoverTypes.Uniform)              
                chromosomes = mutate(chromosomes, davosconf.ExperimentalDesignConfig, 50, False)
                for ch in chromosomes:
                    if len(children) < new_ind_cnt:
                        child = create_individual(davosconf, ch, datamodel)    #select inviduals with matching chromosomes from DB, otherwise create new ones to be evaluated(implemented)
                        if (not 'ScoreMean' in child.Metrics) or ('CreatedAtIteration' in  child.Metrics and child.Metrics['CreatedAtIteration'] == iteration):        #new individual
                            child.Metrics['CreatedAtIteration'] = iteration
                            children.append(child)
            else:
                child = get_random_individual(datamodel, davosconf.ExperimentalDesignConfig)
                if (not 'ScoreMean' in child.Metrics) or ('CreatedAtIteration' in  child.Metrics and child.Metrics['CreatedAtIteration'] == iteration):
                    child.Metrics['CreatedAtIteration'] = iteration
                    children.append(child)
        population = parents + children
        




def binary_tournament_selection(individuals):
    a, b = random.choice(individuals), random.choice(individuals)
    if a.Metrics['ParetoRank'] < b.Metrics['ParetoRank']:
        return(a)
    elif a.Metrics['ParetoRank'] > b.Metrics['ParetoRank']:
        return(b)
    else:   #if both pertain to the same Pareto frontier - check 
        if a.Metrics['CrowdingDistance'] > b.Metrics['CrowdingDistance']:
            return(a)
        elif a.Metrics['CrowdingDistance'] < b.Metrics['CrowdingDistance']:
            return(b)
        else: 
            return(a)


def crossover_couples(couples, CrossType):
    res = []
    for c in couples:
        chromosoma_1, chromosoma_2  = [], []
        if CrossType == CrossoverTypes.Uniform:
            for i in range(len(c[0].Factors)):
                point = random.choice([0,1])
                gene_1 = c[0].Factors[i] if point==0 else c[1].Factors[i]
                gene_2 = c[0].Factors[i] if point==1 else c[1].Factors[i]
                chromosoma_1.append(copy.copy(gene_1))
                chromosoma_2.append(copy.copy(gene_2))
        res.append(chromosoma_1)
        res.append(chromosoma_2)
    return(res)



def NGSA(davosconf, JM, datamodel):
    population = []
    timestart = time.time()
    iteration=0   


    for i in datamodel.HdlModel_lst:
        if i.Label in ['Microblaze_030']:
            i.Metrics['Implprop']= dict()
    

    #Build initial random population    
    population = init_from_file(datamodel, davosconf.ExperimentalDesignConfig)
    while len(population) < POPULATION_SIZE:
        print 'Generating initial random population'
        ind = get_random_individual(datamodel, davosconf.ExperimentalDesignConfig)
        population.append(ind)
    for ind in population:
        ind.Metrics['CreatedAtIteration'] = iteration
    print('INIT population: \n{0}'.format('\n\n\n'.join([', '.join(['{0}={1}'.format(j.FactorName, j.FactorVal) for j in i.Factors]) for i in population])))
    raw_input('Any key to proceed...')    

    while(True):
        population, rest = selection_adaptive(population, len(population), davosconf, JM, datamodel, True)
        pareto_fronts, sorted_population = DecisionSupport.pareto_sort(population, ['MTTF', 'FREQUENCY'])
        parents, rejected = sorted_population[:SELECTION_SIZE], sorted_population[SELECTION_SIZE:]
        log_results(davosconf.ExperimentalDesignConfig, iteration, time.time()-timestart, parents, rejected+rest)
        datamodel.SaveHdlModels()

        new_ind_cnt = POPULATION_SIZE - len(parents)
        iteration+=1
        children = []

        while len(children) < new_ind_cnt:
            if len(parents) > 1:
                couples = []
                for i in range(int(math.ceil(POPULATION_SIZE/2.0))):
                    a, b = binary_tournament_selection(parents), binary_tournament_selection(parents)
                    while (a==b): b = binary_tournament_selection(parents)
                    couples.append((a,b))
                chromosomes = crossover_couples(couples, CrossoverTypes.Uniform)              
                chromosomes = mutate(chromosomes, davosconf.ExperimentalDesignConfig, 50, False)
                for ch in chromosomes:
                    if len(children) < new_ind_cnt:
                        child = create_individual(davosconf, ch, datamodel)    #select inviduals with matching chromosomes from DB, otherwise create new ones to be evaluated(implemented)
                        if (not 'ScoreMean' in child.Metrics) or ('CreatedAtIteration' in  child.Metrics and child.Metrics['CreatedAtIteration'] == iteration):        #new individual
                            child.Metrics['CreatedAtIteration'] = iteration
                            children.append(child)
            else:
                child = get_random_individual(datamodel, davosconf.ExperimentalDesignConfig)
                if (not 'ScoreMean' in child.Metrics) or ('CreatedAtIteration' in  child.Metrics and child.Metrics['CreatedAtIteration'] == iteration):
                    child.Metrics['CreatedAtIteration'] = iteration
                    children.append(child)
        population = parents + children





#Entry point for the parent process
if __name__ == '__main__':           
    call_dir = os.getcwd()
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
    normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))
    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
    tree = xml_conf.getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    davosconf.toolconf = toolconf
    davosconf.file = normconfig

    datamodel = DataModel()
    datamodel.ConnectDatabase( davosconf.get_DBfilepath(False), davosconf.get_DBfilepath(True) )
    datamodel.RestoreHDLModels(None)
    for i in datamodel.HdlModel_lst: i.ModelPath = os.path.join(davosconf.ExperimentalDesignConfig.design_genconf.design_dir, i.Label)

    if not os.path.exists(davosconf.ExperimentalDesignConfig.design_genconf.tool_log_dir):
        os.makedirs(davosconf.ExperimentalDesignConfig.design_genconf.tool_log_dir)

    #Build Worker processes
    JM = JobManager(davosconf)
    random.seed(130)
    #GeneticSearch_PresiceRanking(config, JM, datamodel)

    NGSA(davosconf, JM, datamodel)


    #DefConf = CreateDefaultConfig(datamodel, davosconf.ExperimentalDesignConfig)
    #DefConf.Metrics['SampleSizeGoal']=300000
    #DefConf.Metrics['ErrorMarginGoal']=float(0.001)
    #evaluate([DefConf], davosconf, JM, datamodel, False)
    
    GeneticSearch_AdaptiveRanking(davosconf, JM, datamodel, [], 0)

    datamodel.SaveHdlModels()
