#!python
# Produces the set of factorial implementations (defined by models argument) from input RT-level model
# for given configuration of implementation flow (config.flow in the input configuration argument)
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import sys
import xml.etree.ElementTree as ET
import re
import os
import subprocess
import string
import copy
import glob
import shutil
import datetime
import time
from sys import platform
from multiprocessing import Process, Manager
from multiprocessing.managers import BaseManager
from subprocess import call
from Datamanager import *
sys.path.insert(0, os.path.join(os.getcwd(), './SupportScripts'))
import VendorSpecific

TIMEOUT_IMPL_PHASE = 1000


def implement_model(config, model, adjust_constraints, stat, ForceReimplement = False):
    os.chdir(config.design_genconf.design_dir)    
    if (not ForceReimplement) and (update_metrics(model) != None): return
    if not os.path.exists(config.design_genconf.tool_log_dir):
        os.makedirs(config.design_genconf.tool_log_dir)            
    log = open(os.path.join(config.design_genconf.tool_log_dir, model.Label+".log"), 'w')
    log.write("\nImplementing: " + model.Label + ', started: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if stat == None: stat = ProcStatus('Config')
    if not 'EvalTime' in model.Metrics: model.Metrics['EvalTime'] = dict()
    if not isinstance(model.Metrics['EvalTime'], dict): model.Metrics['EvalTime'] = dict()
    for k,v in model.Metrics['EvalTime'].iteritems():
        stat.update(str(k), '{} sec'.format(v), 'ok')

    #If this configuration has not been implemented previously - implement it, retrieve the results, update statistics for monitoring interface
    if ForceReimplement:
        if os.path.exists(model.ModelPath):
            try:
        #        #backup_script = 'zip -r {0}_BACKUP {1} > {2}/ziplog_{3}.log'.format(model.Label, cleanup_path(get_relative_path(os.getcwd(), model.ModelPath)), config.design_genconf.tool_log_dir, model.Label)
        #        #proc = subprocess.Popen(backup_script, shell=True)
        #        #print('Running backup of previous results: {0}'.format(backup_script))
        #        #proc.wait()
                shutil.rmtree(model.ModelPath)
            except e:
                print(str(e))
    if not os.path.exists(model.ModelPath):
        shutil.copytree(os.path.join(config.design_genconf.design_dir, config.design_genconf.template_dir), model.ModelPath)
    os.chdir(model.ModelPath)
    print("Started Process [" + model.Label + "], workdir: " + os.getcwd())
    if not os.path.exists(config.design_genconf.log_dir):
        os.makedirs(config.design_genconf.log_dir)

    constraint_template = ''
    all_constraints = [p.constraint_to_adjust for p in config.flow.get_phase_chain() if p.constraint_to_adjust!=None]
    for c in all_constraints:
        c.current_value = c.start_value
    if os.path.exists(config.design_genconf.constraint_file):
        with open(config.design_genconf.constraint_file, 'r') as f:
            constraint_template = f.read()
    
    implentability_checked, impl_test = False, False
    phase = config.flow.entry_phase
    while phase != None:
        stat.update('Progress', phase.name, 'wait')
        stat.update(phase.name, 'In progress', 'wait')
        #update constraint file if any contraint defined
        if len(phase.constraints_to_export) > 0:
            constraint_content = constraint_template
            for ce in all_constraints:
                constraint_content = constraint_content.replace(ce.placeholder, str(ce.current_value))
                stat.update('Iteration', ce.iteration, 'ok')
                ce.iteration += 1
            if os.path.exists(config.design_genconf.constraint_file):
                with open(config.design_genconf.constraint_file, 'w') as f:
                    f.write(constraint_content)

        completed = False
        attempt = 0
        while not completed:
            attempt+=1
            script = getattr(VendorSpecific, phase.script_builder)(phase, config, model)
            timestart = datetime.datetime.now().replace(microsecond=0)
            start_t = time.time()
            log.write('\n{0}\tStarting: {1}, attempt: {2}, script: {{{3}}}'.format(str(timestart), phase.name, attempt, script))
            log.flush()
            proc = subprocess.Popen(script, shell=True)
            time.sleep(1)
            while (proc.poll() == None) and (time.time() - start_t < TIMEOUT_IMPL_PHASE):
                time.sleep(1)
            if proc.poll() == None:
                log.write('\n{0}\tTimeout: {1}, attempt: {2}, script: {{{3}}}'.format(str(datetime.datetime.now().replace(microsecond=0)), phase.name, attempt, script))
                log.flush()
                proc.kill()
                success = False             
            else:
                success = getattr(VendorSpecific, phase.postcondition_handler)(phase, config, model)
            timetaken = datetime.datetime.now().replace(microsecond=0) - timestart
            if success:                
                if not phase.name in model.Metrics['EvalTime']: 
                    model.Metrics['EvalTime'][phase.name] = int(time_to_seconds(timetaken))
                else: 
                    model.Metrics['EvalTime'][phase.name] += int(time_to_seconds(timetaken))
                stat.update(phase.name, '{} sec'.format(model.Metrics['EvalTime'][phase.name]), 'ok')
                completed = True
            else:
                if attempt > config.retry_attempts:
                    #report an error and stop
                    stat.update(phase.name, 'Error', 'err')
                    log.write("\nPostcondition/Timeout error at {0}: , exiting".format(phase.name) )
                    log.close()
                    return      

        res = getattr(VendorSpecific, phase.result_handler)(phase, config, model)
        if not 'Implprop' in model.Metrics: model.Metrics['Implprop'] = dict()
        if not isinstance(model.Metrics['Implprop'], dict): model.Metrics['Implprop'] = dict()
        for k, v in res.iteritems():
            model.Metrics['Implprop'][k] = v
            stat.update(k, str(v), 'res')

        if adjust_constraints and phase.constraint_to_adjust != None:
            satisfied = getattr(VendorSpecific, phase.constraint_to_adjust.check_handler)(phase, config, model)
            
            if satisfied:
                implentability_checked = True
                if impl_test:
                    impl_test == False
                    phase.constraint_to_adjust.current_value = saved_constraint
                    log.write('\n{0}\tImplementation test passed'.format(str(timestart)))
                if phase.constraint_to_adjust.converged:
                    phase = phase.next
                else:
                    #strengthen the constraint until not satisfied
                    if phase.constraint_to_adjust.goal == AdjustGoal.min:
                        phase.constraint_to_adjust.current_value -= phase.constraint_to_adjust.adjust_step
                    elif phase.constraint_to_adjust.goal == AdjustGoal.max:
                        phase.constraint_to_adjust.current_value += phase.constraint_to_adjust.adjust_step
                    log.write('\n{0}\tConstraint adjusted: {1} = {2}'.format(str(timestart), phase.constraint_to_adjust.placeholder, phase.constraint_to_adjust.current_value))
                    if phase.constraint_to_adjust.current_value <= 0:
                         #mask config as non implementable and exit
                         model.Metrics['Implprop']['Error'] = 'ImplError'
                         completed = True
                         phase = None
                         break
                    phase = phase.constraint_to_adjust.return_to_phase
            else:
                if (not implentability_checked) and phase.constraint_to_adjust.goal == AdjustGoal.max:
                    if impl_test:
                        model.Metrics['Implprop']['Error'] = 'ImplError'
                        completed = True
                        phase = None
                        log.write('\n{0}\tImplementation test failed'.format(str(timestart)))
                        break
                    else:    
                        saved_constraint = phase.constraint_to_adjust.current_value - phase.constraint_to_adjust.adjust_step           
                        phase.constraint_to_adjust.current_value = 15.0
                        impl_test = True
                        phase = phase.constraint_to_adjust.return_to_phase
                        log.write('\n{0}\tImplementation test started'.format(str(timestart)))
                else:
                    #once not satisfied - converged
                    phase.constraint_to_adjust.converged = True
                    #relax the constraint until satisfied
                    if phase.constraint_to_adjust.goal == AdjustGoal.min:
                        phase.constraint_to_adjust.current_value += phase.constraint_to_adjust.adjust_step
                    elif phase.constraint_to_adjust.goal == AdjustGoal.max:
                        phase.constraint_to_adjust.current_value -= phase.constraint_to_adjust.adjust_step
                    if phase.constraint_to_adjust.current_value <= 0:
                         #mask config as non implementable and exit
                         model.Metrics['Implprop']['Error'] = 'ImplError'
                         completed = True
                         phase = None
                         break
                    log.write('\n{0}\tConstraint adjusted: {1} = {2}'.format(str(timestart), phase.constraint_to_adjust.placeholder, phase.constraint_to_adjust.current_value))
                    phase = phase.constraint_to_adjust.return_to_phase
        else:
            phase = phase.next

    model.serialize(SerializationFormats.XML, model.std_dumpfile_name)
    stat.update('Progress', 'Completed', 'ok')
    log.close()



#returns dictionary dict[config_label] = (process_id=None, model_descriptor, statistic_descriptor)
#read from file statfile (xml)
def recover_statistics(model_list, statfile, recover_state = True):
    procdict = dict()
    recover_stat_tree = None
    if recover_state and os.path.exists(statfile):
        recover_stat_tree = ET.parse(statfile).getroot()
    for i in model_list:
        stat = ProcStatus('Config')
        if(recover_stat_tree is not None): 
            stat.from_xml(recover_stat_tree, 'Config', 'Label', i.Label)
        procdict[i.Label] = (None, i, stat)
        stat.update('Label', i.Label,'')
    return(procdict)


def proclist_stat(proclist):
    active_proc = 0
    finished_proc = 0
    for p in proclist:
        if p[0] != None:
            if(p[0].is_alive()):
                active_proc += 1
            else:
                finished_proc += 1
    return(active_proc, finished_proc)


def allocate_gui_local(config):
    os.chdir(config.design_genconf.design_dir)
    copy_all_files(os.path.join(config.call_dir,'UserInterface/IMPL'), config.design_genconf.design_dir)
    copy_all_files(os.path.join(config.call_dir,'UserInterface/libs'), os.path.join(config.design_genconf.design_dir, 'libs'))
    with open(os.path.join(config.design_genconf.design_dir, 'Monitoring.js'), 'r') as f:
        content = f.read()
    content = content.replace('#FULLSTAT', '\'{0}\''.format(config.statfile)).replace('#MINSTAT', '\'{0}\''.format(config.statfile.replace('.xml','_min.xml')))
    theaders = ['Label']
    tlogdesc = ['./Logs/@.log']
    for c in VendorSpecific.GetResultLabels():
        theaders.append(c)
        tlogdesc.append('./Logs/@.log')
    theaders.append('Progress')
    tlogdesc.append('./Logs/@.log')
    theaders.append('Iteration')
    tlogdesc.append('./Logs/@.log')
    for p in config.flow.get_phase_chain():
        theaders.append(p.name)
        tlogdesc.append('./@/{0}/{1}'.format(config.design_genconf.log_dir, p.logfile))
    content = content.replace('#THEADERS', '[{0}]'.format(', '.join(['\'{0}\''.format(c) for c in theaders])))
    content = content.replace('#LOGDESC', '[{0}]'.format(', '.join(['\'{0}\''.format(c)  for c in tlogdesc])))
    content = content.replace('#GLOBALHEADERS', "['Phase', 'Progress', 'Time_Taken', 'Report']")
    with open(os.path.join(config.design_genconf.design_dir, 'Monitoring.js'), 'w') as f:
        f.write(content)
    #Launch monitoring interface
    try:
        if platform == 'linux' or platform == 'linux2':
             subprocess.check_output('xdg-open ' + os.path.join(config.call_dir, config.design_genconf.design_dir, 'Monitoring.html > ./dummylog.txt'), shell=True)
        elif platform == 'cygwin': 
            subprocess.check_output('cygstart ' + os.path.join(config.call_dir, config.design_genconf.design_dir, 'Monitoring.html > ./dummylog.txt'), shell=True)
        elif platform == 'win32' or  platform == 'win64':
            subprocess.check_output('start ' + os.path.join(config.call_dir, config.design_genconf.design_dir, 'Monitoring.html > ./dummylog.txt'), shell=True)
    except subprocess.CalledProcessError as e:
        print e.output


def update_metrics(m):


    if os.path.isfile(os.path.join(m.ModelPath, HDLModelDescriptor.std_dumpfile_name)):
        tag = ET.parse(os.path.join(m.ModelPath, HDLModelDescriptor.std_dumpfile_name)).getroot()
        res = HDLModelDescriptor.deserialize(SerializationFormats.XML, tag).Metrics
        for k, v in res.iteritems():
            m.Metrics[k] = v
        return(m.Metrics)
    else:
        return(None)


def export_results(models, dir):
    with open(os.path.join(dir, 'IMPLEMENTATION_RESULTS.xml'), 'w') as f: 
        f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.serialize(SerializationFormats.XML) for m in models])))
    with open(os.path.join(dir, 'IMPLEMENTATION_SUMMARY.xml'), 'w') as f: 
        f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in models])))


def build_summary_page(models, fname):
    spage = HtmlPage('Summary')
    spage.css_file = 'markupstyle.css'
    T = Table('Summary')
    T.add_column('Label')
    factors = []
    for f in models[0].Factors: 
        factors.append(f.FactorName)
        T.add_column(f.FactorName)
    for i in range(len(models)):
        T.add_row()
        T.put(i,0, str(models[i].Label))
        for f in range(len(factors)):
            T.put(i,1+f, str((models[i].get_factor_by_name(factors[f])).FactorVal))
    implprop = set()
    for m in models:
        update_metrics(m)
        if 'Implprop' in m.Metrics:
            for k, v in m.Metrics['Implprop'].iteritems():
                implprop.add(k)
    implprop = list(implprop)
    x = T.colnum()
    for p in implprop: T.add_column(p)
    for i in range(len(models)):
        m = models[i]
        for p in range(len(implprop)):
            data = '-'
            if 'Implprop' in m.Metrics:
                if implprop[p] in m.Metrics['Implprop']:
                    data = str(m.Metrics['Implprop'][implprop[p]])
            T.put(i, x+p, data)          
    spage.put_data(T.to_html_table('Factorial Design: Summary').to_string())
    spage.write_to_file(fname)


#For multicore systems (PC)
def implement_models_multicore(config, models, recover_state = True):
    #Prepare the implementation process
    #Register shared object type - to obtain the statistics from launched processes
    BaseManager.register('ProcStatus', ProcStatus)
    manager = BaseManager()
    manager.start()
    #Allocate User Interface and launch it - monitoring page (no web-server required)
    allocate_gui_local(config)
    if not os.path.exists(config.design_genconf.tool_log_dir):
        os.makedirs(config.design_genconf.tool_log_dir)            

    procdict = recover_statistics(models, os.path.join(config.design_genconf.design_dir, config.statfile), recover_state)
    globalstatdict = dict()
    stat = ProcStatus('Global')
    stat.update('Phase', 'Implementation','')
    stat.update('Progress', '0%','')
    stat.update('Report', 'wait','')
    globalstatdict['Implementation'] = stat

    if recover_state:
        models_to_implement = []
        for m in models:
            if m.Label in procdict:
                stat = procdict[m.Label][2]
                if stat.get('Progress') == ('Completed', 'ok'):
                    #if not 'Implprop' in m.Metrics: m.Metrics['Implprop'] = dict()
                    #for k, v in (stat.get_message_dict_by_descriptor('res')).iteritems():
                    #    m.Metrics['Implprop'][k] = float(v)      
                    update_metrics(m)
                    if 'Implprop' in m.Metrics:
                        continue
            models_to_implement.append(m)
    else:
        models_to_implement = models
    

    if len(models_to_implement) > 0:
        timestart = datetime.datetime.now().replace(microsecond=0)
        for i in range(len(models_to_implement)):
            m = models_to_implement[i]
            stat = manager.ProcStatus('Config')   #shared proxy-object for process status monitoring
            stat.update('Label', m.Label,'')
            #wait for resources for new process and update statistics
            while True:
                (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
                globalstatdict['Implementation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(len(models_to_implement))))+'%', '')
                globalstatdict['Implementation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart), 'ok')
                save_statistics( [val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]], os.path.join(config.design_genconf.design_dir, config.statfile) ) 
                print('Finished: {0}, Running: {1}'.format(finished_proc_num, active_proc_num))
                if active_proc_num < config.max_proc:
                    break
                time.sleep(5)            
            build_summary_page(models, 'summary.html')
            p = Process(target = implement_model, args = (config, m, True, stat))
            p.start()
            procdict[m.Label] = (p, m.Label, stat)
        while True:
            (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
            globalstatdict['Implementation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(len(models_to_implement))))+'%', '')
            globalstatdict['Implementation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart), 'ok')
            save_statistics( [val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]], os.path.join(config.design_genconf.design_dir, config.statfile) ) 
            print('Finished: {0}, Running: {1}'.format(finished_proc_num, active_proc_num))
            if active_proc_num < 1:
                break
            time.sleep(5)
    build_summary_page(models, 'summary.html')
    for m in models:
        update_metrics(m)
    export_results(models, config.design_genconf.tool_log_dir)




def ImplementConfigurationsManaged(configlist_implement, configlist_inject, config, JM, callback_func = None, callback_period = 0):
    BaseManager.register('ProcStatus', ProcStatus)
    manager = BaseManager()
    manager.start()
    globalstatdict = dict()
    configstat = []
    stat = ProcStatus('Global')
    stat.update('Phase', 'Implementation','')
    stat.update('Progress', '0%','')
    stat.update('Report', 'wait','')
    globalstatdict['Implementation'] = stat
    conf_count = len(configlist_implement) + len(configlist_inject)

    for i in configlist_inject:
        stat = manager.ProcStatus('Config')   #shared proxy-object for process status monitoring
        stat.update('Label', i.Label,'')
        configstat.append(stat)
        JM.queue_faulteval.put([i, stat, config])
    for i in configlist_implement:
        stat = manager.ProcStatus('Config')   #shared proxy-object for process status monitoring
        stat.update('Label', i.Label,'')
        configstat.append(stat)
        JM.queue_implement.put([i, stat, config])
    tmark = time.time()
    while(JM.queue_result.qsize() < conf_count):
        with JM.console_lock: 
            console_message('Implementation_Queue = {0:d}, SeuInjection_Queue = {1:d}, Result_Queue = {2:d} / {3:d}\r'.format(JM.queue_implement.qsize(), JM.queue_faulteval.qsize(), JM.queue_result.qsize(),  conf_count), ConsoleColors.Green, True)
        save_statistics( [val for key, val in sorted(globalstatdict.items())] + configstat, os.path.join(config.design_genconf.design_dir, config.statfile) )
        time.sleep(1)
        if callback_func != None and int(time.time()-tmark) >= callback_period:
            callback_func()
            tmark = time.time()
    save_statistics( [val for key, val in sorted(globalstatdict.items())] + configstat, os.path.join(config.design_genconf.design_dir, config.statfile) )
    impl_results = []
    for i in range(conf_count):
        c = JM.queue_result.get()[0]
        with JM.console_lock: print 'Appending Result: {0}:{1}'.format(str(c.Label), str(c.Metrics))
        impl_results.append(c)
    return(impl_results)




















def check_modelst_completed(modelst):
    for m in modelst:
        if not os.path.exists(os.path.join(m.ModelPath, m.std_dumpfile_name)):
            return False
    return True


#For SGE systems (Grid)
def implement_models_Grid(config, models, recover_state = True):    
    job_prefix = 'IMPL_'
    timestart = datetime.datetime.now().replace(microsecond=0)
    for m in models:
        #serialize model to XML
        j = os.path.join(config.design_genconf.design_dir, m.Label+'.XML')
        m.serialize(SerializationFormats.XML, j)
        #create grid job for serialized model
        shell_script = 'python ImplementationTool.py {0} {1}'.format(config.ConfigFile, j)
        run_qsub(job_prefix + m.Label, shell_script, config.call_dir, "20:00:00", "4g", os.path.join(config.call_dir, 'GridLogs'))
    #monitoring        
    joblst = get_queue_state_by_job_prefix(job_prefix)
    print "\n\tRunning processes: " + ''.join(['\n\t{0}'.format(job.name) for job in joblst.running])
    print "\n\tPending processes:"  + ''.join(['\n\t{0}'.format(job.name) for job in joblst.pending])
    print "STARTED MONITORING"   
    while joblst.total_len() > 0:
        if check_modelst_completed(models):
            print(commands.getoutput('qdel -u $USER'))
            break
        timetaken = str(datetime.datetime.now().replace(microsecond=0) - timestart)
        console_complex_message(['{0} : Pending: {1} \tRunning: {2} \tFinished: {3} \tTime taken: {4}'.format(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), len(joblst.pending), len(joblst.running), len(models)-len(joblst.pending)-len(joblst.running), timetaken)], [ConsoleColors.Green], True)
        time.sleep(10)
        joblst = get_queue_state_by_job_prefix(job_prefix)
    #export results
    for m in models:
        update_metrics(m)
    export_results(models, config.design_genconf.tool_log_dir)



#Entry point for the parent process
if __name__ == '__main__':           
    call_dir = os.getcwd()
    if sys.argv[1].find('_normalized.xml') > 0:
        normconfig = (sys.argv[1])
    else:
        normconfig = (sys.argv[1]).replace('.xml','_normalized.xml')
        normalize_xml(os.path.join(os.getcwd(), sys.argv[1]), os.path.join(os.getcwd(), normconfig))                
    xml_conf = ET.parse(os.path.join(os.getcwd(), normconfig))
    tree = xml_conf.getroot()

    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    config = davosconf.ExperimentalDesignConfig
    if len(sys.argv) > 2: #implement this given configuration
        #deserialize model
        model = HDLModelDescriptor.deserialize(SerializationFormats.XML, (ET.parse(sys.argv[2])).getroot())
        if config.platform == Platforms.GridLight: #work with local storage on each node
            itemstocopy = []
            for i in os.listdir(config.design_genconf.design_dir):
                if i.find(config.design_genconf.design_label) < 0:
                    itemstocopy.append(i)
            dst = os.path.join(os.environ['TMP'], 'DAVOS')
            if os.path.exists(dst): 
                shutil.rmtree(dst)
            if not os.path.exists(dst): 
                os.makedirs(dst)                
            for i in itemstocopy:
                a = os.path.join(config.design_genconf.design_dir, i)
                if os.path.isdir(a):
                    shutil.copytree(a, os.path.join(dst, i))
                else:
                    shutil.copyfile(a, os.path.join(dst, i))
            src_path = model.ModelPath
            model.ModelPath = os.path.join(dst, model.Label)           
            try:
                implement_model(config, model, True, None)
            except:
                print 'Something went wrong in implement_model'
            #copy results back to main folder
            if os.path.exists(src_path): shutil.rmtree(src_path)
            if not os.path.exists(src_path): shutil.copytree(os.path.join(config.design_genconf.design_dir, config.design_genconf.template_dir), src_path)
            try:
                shutil.copytree(os.path.join(model.ModelPath, config.design_genconf.netlist_dir),    os.path.join(src_path, config.design_genconf.netlist_dir))
                shutil.copyfile(os.path.join(model.ModelPath, config.design_genconf.testbench_file), os.path.join(src_path, config.design_genconf.testbench_file))
                shutil.copyfile(os.path.join(model.ModelPath, model.std_dumpfile_name), os.path.join(src_path, model.std_dumpfile_name))
            except:
                print 'Some result files are missing'
            os.chdir(src_path)
            shutil.rmtree(model.ModelPath, ignore_errors=True)
    else: #implement everything from database
        pass
