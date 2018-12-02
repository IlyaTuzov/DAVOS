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
import random
import multiprocessing
import copy

POPULATION_SIZE = int(12)
FIT_ZYNQ = (75.0/float(1024*1024))
ZynqDevices = {0: [ '2', '2' ], 1: [ '6', '0' ]}
requires_properties_implement = ['FREQUENCY']
require_properties_faultinject = ['VerifcationSuccess', 'Injections', 'Failures', 'FailureRate', 'FIT', 'Lambda', 'MTTF']
require_properties = requires_properties_implement + require_properties_faultinject

def estimate_robustness(model, Zynq_id, stat):
        os.chdir(model.ModelPath)
        if stat == None: stat = ProcStatus('Config')
        stat.update('Progress', 'Faulteval', '0%')
        stat.update('Faulteval', 'In progress', 'wait')
        resfile = 'InjResult.txt'
        script = 'python SEUInjector.py {0} {1} {2} {3} > {4}'.format(ZynqDevices[Zynq_id][0], ZynqDevices[Zynq_id][1], 1, resfile, 'InjLog.log')
        timestart = datetime.datetime.now().replace(microsecond=0)
        if not os.path.exists(resfile): 
            proc = subprocess.Popen(script, shell=True)
            proc.wait()
        with open(resfile, 'r') as f:
            content = f.read()
        matchDesc = re.match('Status\s*=\s*(.*?),\s*Injections\s*=\s*([0-9]+),\s*Failures\s*=\s*([0-9]+),\s*Failure\s*Rate\s*=\s*([0-9\.]+)', content)
        if not 'Implprop' in model.Metrics: model.Metrics['Implprop'] = dict()
        if matchDesc:
            model.Metrics['Implprop']['VerifcationSuccess'] = int(0) if matchDesc.group(1).find('Error')>=0 else int(1)
            model.Metrics['Implprop']['Injections'] = int(matchDesc.group(2))
            model.Metrics['Implprop']['Failures'] = int(matchDesc.group(3))
            model.Metrics['Implprop']['FailureRate'] = float(matchDesc.group(4))
            model.Metrics['Implprop']['FIT'] = FIT_ZYNQ * model.Metrics['Implprop']['Injections'] * (model.Metrics['Implprop']['FailureRate'] / 100.0)
            model.Metrics['Implprop']['Lambda'] = model.Metrics['Implprop']['FIT']/float(1000000000)
            model.Metrics['Implprop']['MTTF'] = 1.0 / model.Metrics['Implprop']['Lambda']
        timetaken = str(datetime.datetime.now().replace(microsecond=0) - timestart)        
        for k, v in model.Metrics['Implprop'].iteritems():
            stat.update(k, str(v), 'res')
        stat.update('Faulteval', 'Completed', 'ok')



def dummy_implement(conf, stat):
    stat.update('Progress', 'Implement', '0%')
    stat.update('Implement', 'In progress', 'wait')
    time.sleep(1) # simulate a "long" operation
    if not 'Implprop' in conf.Metrics: conf.Metrics['Implprop'] = dict()
    res = dict()
    d = conf.get_setting_dict()
    res['FREQUENCY'] = (5+d['X01'])*1.5 + (40-d['X23'])*1.1  #int(conf.ID)*10
    res['LUT' ] = (1000 if d['X01']==1 else 2000) + (500 if d['X02']==2 else 1000) #int(conf.ID)*20
    for k, v in res.iteritems():
        conf.Metrics['Implprop'][k] = v
        stat.update(k, str(v), 'res')
    stat.update('Implement', 'Completed', 'ok')

def dummy_estimate_robustness():
    time.sleep(1) # simulate a "long" operation
    d = conf.get_setting_dict()
    res['Failures'] = (500 if d['X08']==1 else 1000) + (d['X15']*100) + (500 if d['X10']==1 else 1000) #int(conf.ID)*1000
    res['Injections'] = 12345
    res['FailureRate'] = float( res['Failures'] )/float(res['Injections'])
        


def worker_Implement(idx, queue_i, queue_o, lock):
    id_proc = idx.get()
    while True:
        item = queue_i.get(True)
        model = item[0]
        stat = item[1]
        config = item[2]
        with lock: print('worker_Implement {0} :: Implementing {1}'.format(id_proc, model.Label))     
        ImplementationTool.implement_model(config, model, True, stat)
        model.Metrics['Error'] = ''
        for i in requires_properties_implement:
            if not i in model.Metrics['Implprop']:
                model.Metrics['Implprop'][i] = 0
                model.Metrics['Error'] = 'ImplementError'
        queue_o.put(item)


def worker_Faulteval(idx, queue_i, queue_o, lock):
    id_proc = idx.get()
    while True:
        item = queue_i.get(True)
        model = item[0]
        stat = item[1]
        config = item[2]
        if model.Metrics['Error'] != '':
            with lock: print('worker_Faulteval {0} :: Passing {1} due to error flag'.format(id_proc, model.Label))     
        else:
            with lock: print('worker_Faulteval {0} :: Estimating Robustness {1}'.format(id_proc, model.Label))     
            estimate_robustness(model, id_proc, stat)
        for i in require_properties_faultinject:
            if not i in model.Metrics['Implprop']:
                model.Metrics['Implprop'][i] = 0
                if model.Metrics['Error'] == '':
                    model.Metrics['Error'] = 'InjError'
        queue_o.put(item)



class JobManager:
    def __init__(self, imp_proc_num, inj_proc_num):
        self.imp_proc_num = imp_proc_num
        self.inj_proc_num = inj_proc_num
        self.manager = multiprocessing.Manager()
        self.console_lock = self.manager.Lock()
        self.queue_implement = self.manager.Queue()
        self.queue_faulteval = self.manager.Queue()
        self.queue_result = self.manager.Queue()
        self.ids_imp = self.manager.Queue()
        for i in range(imp_proc_num): self.ids_imp.put(i)
        self.ids_inj = self.manager.Queue()
        for i in range(inj_proc_num): self.ids_inj.put(i)        
        implement_Pool = multiprocessing.Pool(imp_proc_num, worker_Implement,(self.ids_imp, self.queue_implement, self.queue_faulteval, self.console_lock))
        faulteval_Pool = multiprocessing.Pool(inj_proc_num, worker_Faulteval,(self.ids_inj, self.queue_faulteval, self.queue_result, self.console_lock))    
        




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






def evaluate(population, config, JM, datamodel):
    configurations_to_implement = []   
    configurations_implemented = []
    for individual in population:
        #Check availability of all metrics, required for score computation
        complete = True
        if not 'Implprop' in individual.Metrics:
            complete = False
        else:
            for p in require_properties:
                if not p in individual.Metrics['Implprop']:
                    complete = False
                    break
        if complete:
            configurations_implemented.append(individual)
        else:
            configurations_to_implement.append(individual)
        #Implement all inviduals with missing metrics
    buf = ImplementationTool.ImplementConfigurationsManaged(configurations_to_implement, config, JM)
    res = []
    for i in buf:
        m = datamodel.GetHdlModel(i.Label)
        m.Metrics = i.Metrics
        res.append(m)
    individuals = configurations_implemented + res
    #compute the fitness of each individual and rank them (sort descending - first are better)
    #example - minimize failures
    for i in individuals: 
        if i.Metrics['Error'] == '' and i.Metrics['Implprop']['VerifcationSuccess'] > 0:
            if float(i.Metrics['Implprop']['FREQUENCY']) >= 20.0 and i.Metrics['Implprop']['FIT'] > 0:
                i.Metrics['Score'] = 1.0/float(i.Metrics['Implprop']['FIT'])
            else:
                i.Metrics['Score'] = 0.0
        else:
            i.Metrics['Score'] = 0.0
    return(individuals)






#return the new population maintaining N/2 best indivuduals
def selection(individuals):
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
    SinglePoint, MultiPoint, Uniform = range(3)

def crossover(individuals, CrossType):
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
def mutate(chromosomes, config, probability):
    #weights vector - probability to select the given gene for mutation
    w, wp = [], []
    for i in config.factorial_config.factors: w.append(len(i.setting))
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
            i[index].FactorVal = random.choice(list(f.setting.keys()))
            i[index].OptionVal = f.setting[i[index].FactorVal]
    return(chromosomes)


def create_individuals(chromosomes, datamodel):
    res = []
    for i in chromosomes:
        m = datamodel.GetOrCreateHDLModel(i)
        if m.Label == '': m.Label = '{0}{1:03d}'.format(config.design_genconf.design_label, m.ID)
        if m.ModelPath == '': m.ModelPath = os.path.abspath(os.path.join(config.design_genconf.design_dir, m.Label))
        res.append(m)
    return(res)

def log_results(iteration, selected, rest):
    labels = sorted([x.FactorName for x in selected[0].Factors])
    if iteration == 1:
        with open(os.path.join(config.design_genconf.tool_log_dir, 'Log.csv'), 'w') as f:
            f.write('sep = ;\nIteration;Label;Status;Frequency;EssentialBits;Failures;FailureRate;FIT;MTTF;Error'+ ';'.join(labels))    
    with open(os.path.join(config.design_genconf.tool_log_dir, 'Log.csv'), 'a') as f:
        for i in selected:
            f.write('\n{0};{1};{2};{3:.4f};{4:d};{5:d};{6:.4f};{7:.4f};{8:.4f};{9}'.format(iteration, i.Label, 'Selected', i.Metrics['Implprop']['FREQUENCY'], i.Metrics['Implprop']['Injections'], i.Metrics['Implprop']['Failures'], i.Metrics['Implprop']['FailureRate'], i.Metrics['Implprop']['FIT'], i.Metrics['Implprop']['MTTF'], i.Metrics['Error']) )
            for l in labels: f.write(';{0:d}'.format(i.get_factor_by_name(l).FactorVal))
        for i in rest:
            f.write('\n{0};{1};{2};{3:.4f};{4:d};{5:d};{6:.4f};{7:.4f};{8:.4f};{9}'.format(iteration, i.Label, '-', i.Metrics['Implprop']['FREQUENCY'], i.Metrics['Implprop']['Injections'], i.Metrics['Implprop']['Failures'], i.Metrics['Implprop']['FailureRate'], i.Metrics['Implprop']['FIT'], i.Metrics['Implprop']['MTTF'], i.Metrics['Error']) )
            for l in labels: f.write(';{0:d}'.format(i.get_factor_by_name(l).FactorVal))
        with open(os.path.join(config.design_genconf.tool_log_dir, 'MODELS.xml'), 'w') as f: 
            f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in (datamodel.HdlModel_lst) ])))





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
    if not os.path.exists(config.design_genconf.tool_log_dir):
        os.makedirs(config.design_genconf.tool_log_dir)

    #Build Worker processes
    JM = JobManager(6,2)
    random.seed(1)

    iteration = 0
    population = []
    #1. Build initial random population    
    for i in range(POPULATION_SIZE):
        population.append(get_random_individual(datamodel, config))

    #ImplementationTool.implement_model(config, population[0], True, None)
    #estimate_robustness(population[0], 1, None)


    while(True):
        iteration+=1
        population = evaluate(population, config, JM, datamodel)
        datamodel.SaveHdlModels()
        parents, rest    = selection(population)

        log_results(iteration, parents, rest)
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



    #datamodel.SaveHdlModels()
