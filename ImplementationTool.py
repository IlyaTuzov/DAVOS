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




def implement_model(config, model, adjust_constraints = True, stat=None):
    os.chdir(config.design_genconf.design_dir)    
    log = open(os.path.join(config.design_genconf.tool_log_dir, model.Label+".log"), 'w')
    log.write("\nImplementing: " + model.Label + ', started: ' + datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    if stat == None:
        stat = ProcStatus('Config')

    #If this configuration has not been implemented previously - implement it, retrieve the results, update statistics for monitoring interface
    if os.path.exists(model.ModelPath):
        try:
            backup_script = 'zip -r {0}_BACKUP {1} > {2}/ziplog_{3}.log'.format(model.Label, cleanup_path(get_relative_path(os.getcwd(), model.ModelPath)), config.design_genconf.tool_log_dir, model.Label)
            proc = subprocess.Popen(backup_script, shell=True)
            print('Running backup of previous results: {0}'.format(backup_script))
            proc.wait()
            shutil.rmtree(model.ModelPath)
        except e:
            print(str(e))
    if not os.path.exists(model.ModelPath):
        shutil.copytree(config.design_genconf.template_dir, model.ModelPath)
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
            with open(config.design_genconf.constraint_file, 'w') as f:
                f.write(constraint_content)

        completed = False
        attempt = 0
        while not completed:
            attempt+=1
            script = getattr(VendorSpecific, phase.script_builder)(phase, config, model)
            timestart = datetime.datetime.now().replace(microsecond=0)
            log.write('\n{0}\tStarting: {1}, attempt: {2}, script: {{{3}}}'.format(str(timestart), phase.name, attempt, script))
            log.flush()
            proc = subprocess.Popen(script, shell=True)
            proc.wait()
            timetaken = str(datetime.datetime.now().replace(microsecond=0) - timestart)
            success = getattr(VendorSpecific, phase.postcondition_handler)(phase, config, model)
            if success:
                stat.update(phase.name, '100%: '+ timetaken, 'ok')
                completed = True
            else:
                if attempt > config.retry_attempts:
                    #report an error and stop
                    stat.update(phase.name, 'Error', 'err')
                    log.write("\nError reported {0}: , exiting".format(phase.name) )
                    log.close()
                    return      

        res = getattr(VendorSpecific, phase.result_handler)(phase, config, model)
        if not 'Implprop' in model.Metrics: 
            model.Metrics['Implprop'] = dict()
        for k, v in res.iteritems():
            model.Metrics['Implprop'][k] = v
            stat.update(k, str(v), 'res')

        if adjust_constraints and phase.constraint_to_adjust != None:
            satisfied = getattr(VendorSpecific, phase.constraint_to_adjust.check_handler)(phase, config, model)
            if satisfied:
                if phase.constraint_to_adjust.converged:
                    phase = phase.next
                else:
                    #strengthen the constraint until not satisfied
                    if phase.constraint_to_adjust.goal == AdjustGoal.min:
                        phase.constraint_to_adjust.current_value -= phase.constraint_to_adjust.adjust_step
                    elif phase.constraint_to_adjust.goal == AdjustGoal.max:
                        phase.constraint_to_adjust.current_value += phase.constraint_to_adjust.adjust_step
                    log.write('\n{0}\tConstraint adjusted: {1} = {2}'.format(str(timestart), phase.constraint_to_adjust.placeholder, phase.constraint_to_adjust.current_value))
                    phase = phase.constraint_to_adjust.return_to_phase
            else:
                #once not satisfied - converged
                phase.constraint_to_adjust.converged = True
                #relax the constraint until satisfied
                if phase.constraint_to_adjust.goal == AdjustGoal.min:
                    phase.constraint_to_adjust.current_value += phase.constraint_to_adjust.adjust_step
                elif phase.constraint_to_adjust.goal == AdjustGoal.max:
                    phase.constraint_to_adjust.current_value -= phase.constraint_to_adjust.adjust_step
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


def allocate_user_interface(config):
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


def export_results(models, dir):
    with open(os.path.join(dir, 'IMPLEMENTATION_RESULTS.xml'), 'w') as f: 
        f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.serialize(SerializationFormats.XML) for m in models])))
    with open(os.path.join(dir, 'IMPLEMENTATION_SUMMARY.xml'), 'w') as f: 
        f.write('<?xml version="1.0"?>\n<data>\n{0}\n</data>'.format('\n\n'.join([m.log_xml() for m in models])))


#For multicore systems (PC)
def implement_models_multicore(config, models, recover_state = True):
    #Prepare the implementation process
    #Register shared object type - to obtain the statistics from launched processes
    BaseManager.register('ProcStatus', ProcStatus)
    manager = BaseManager()
    manager.start()
    #Allocate User Interface and launch it - monitoring page (no web-server required)
    allocate_user_interface(config)
    if not os.path.exists(config.design_genconf.tool_log_dir):
        os.makedirs(config.design_genconf.tool_log_dir)            

    procdict = recover_statistics(models, config.statfile, recover_state)
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
                save_statistics( [val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]], config.statfile ) 
                print('Finished: {0}, Running: {1}'.format(finished_proc_num, active_proc_num))
                if active_proc_num < config.max_proc:
                    break
                time.sleep(5)            
            p = Process(target = implement_model, args = (config, m, True, stat))
            p.start()
            procdict[m.Label] = (p, m.Label, stat)
        while True:
            (active_proc_num, finished_proc_num) = proclist_stat(list(procdict.values()))
            globalstatdict['Implementation'].update('Progress', str('%.2f' % (100*float(finished_proc_num)/float(len(models_to_implement))))+'%', '')
            globalstatdict['Implementation'].update('Time_Taken', str(datetime.datetime.now().replace(microsecond=0) - timestart), 'ok')
            save_statistics( [val for key, val in sorted(globalstatdict.items())] + [item[2] for item in [val for key, val in sorted(procdict.items())]], config.statfile ) 
            print('Finished: {0}, Running: {1}'.format(finished_proc_num, active_proc_num))
            if active_proc_num < 1:
                break
            time.sleep(5)

    for m in models:
        update_metrics(m)
    export_results(models, config.design_genconf.tool_log_dir)


        