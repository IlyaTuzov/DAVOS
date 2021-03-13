# Runs fault injection scripts either on GRID (SGE) or Multicore PC
# Monitoring implemented
# TODO: Connect to generator via queue of injection descriptors
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import sys
import xml.etree.ElementTree as ET
import re
import os
import stat
import subprocess
import shutil
import datetime
import time
import random
import glob
from Davos_Generic import *
from Datamanager import *


def execute_injection_scripts(config, toolconf, conf):
    if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        execute_injection_scripts_sge(config, toolconf, conf)
    elif config.platform == Platforms.Multicore:
        execute_injection_scripts_Multicore(config, toolconf, conf)


def execute_injection_scripts_sge(config, toolconf, conf):
    # raw_input("RUNNING execute_injection_scripts_SGE....any key to continue...")
    task_run_at = 0
    time_start = datetime.datetime.now().replace(microsecond=0)
    remaining_jobs = True
    while remaining_jobs:
        task_run_at += 1
        work_label = conf.label + '_sm_atmpt_' + str(task_run_at) + '_'
        # Get the list of injection script files in ./iscripts directory
        fscriptlist = []
        print "\n\nReading the list of fault injection scripts: " + conf.work_dir
        os.chdir(os.path.join(conf.work_dir, toolconf.script_dir))
        dolist = glob.glob('*.do')
        for i in dolist:
            if i.startswith('fault_') or i.startswith('areference_'):
                fscriptlist.append(i)
        fscriptlist.sort()
        compl_simdumps = os.listdir(os.path.join(conf.work_dir, toolconf.result_dir))
        print "Init scripts: {0}, Existing ResFiles: {1}".format(str(len(fscriptlist)), str(len(compl_simdumps)))
        checked_list = []
        if len(compl_simdumps) < 3:
            checked_list.extend(fscriptlist)
        else:
            for s in fscriptlist:
                for i in range(0, 100):
                    try:
                        with open(s, 'r') as ds:
                            sr = ds.read()
                    except Exception as e:
                        print 'read injection scripts exception [' + str(e) + '] on file write: ' + s + ', retrying [attempt ' + str(i) + ']'
                        time.sleep(0.001)
                        continue
                    break
                dumpname = re.findall('[a-zA-Z0-9_]+\.lst', sr)[0]
                # if not os.path.exists(os.path.join(conf.work_dir, toolconf.result_dir, dumpname)):
                if dumpname not in compl_simdumps:
                    checked_list.append(s)
                    sys.stdout.write('Appending to run queue [{0}]: {1}\r'.format(str(len(checked_list)), s))
                    sys.stdout.flush()
                elif config.injector.reference_check_pattern != '':
                    with open(os.path.join(conf.work_dir, toolconf.result_dir, dumpname), 'r') as dmpfile:
                        buf = dmpfile.read()
                        if buf.find(config.injector.reference_check_pattern) < 0:
                            checked_list.append(s)
        # if grid IO error occur (no dump file after script completion) - let 0.1% of scripts to be bypassed (0.1% error margin)
        if len(checked_list) < int(0.001 * len(fscriptlist)):
            break

        print "Scripts to Execute [" + str(len(checked_list)) + "] "
        # for i in checked_list: print i
        # Build the list of shell scripts
        os.chdir(conf.work_dir)
        tasksize = len(checked_list)
        if (tasksize > 0):
            taskproc = config.injector.maxproc
            if (tasksize < config.injector.maxproc):
                taskproc = tasksize
            print "TASKPROC = " + str(taskproc)
            shell_script_list = []
            if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
                checkpoint_set = []
                for ind in range(0, taskproc, 1):
                    shell_script_list.append("")
                    checkpoint_set.append(set())
                for ibase in range(conf.start_from, tasksize, taskproc):
                    for ind in range(ibase, ibase + taskproc, 1):
                        if (ind < tasksize):
                            sim_script = ""
                            checkpoint = re.findall("checkpoint_[0-9]+", checked_list[ind])[0] + ".sim"
                            if not checkpoint in checkpoint_set[ind - ibase]:
                                sim_script += "\ncp {0}/{1} $TMP/{2}".format(toolconf.checkpoint_dir, checkpoint, checkpoint)
                                checkpoint_set[ind - ibase].add(checkpoint)
                            sim_script += "\nvsim -c -restore $TMP/{0}".format(checkpoint)
                            sim_script += " -do \"do " + toolconf.script_dir + "/" + checked_list[ind] + "\""
                            sim_script += " > " + toolconf.log_dir + '/log_' + checked_list[ind].replace('.do', '.log')
                            # sim_script += " > $TMP/log_{0}".format(checked_list[ind].replace('.do', '.log'))
                            # sim_script += "\nrm " + './idatasets/WLFSET_{0}.wlf'.format(re.findall('[0-9]+',checked_list[ind])[0])
                            shell_script_list[ind - ibase] += sim_script
            elif config.injector.checkpont_mode == CheckpointModes.WarmRestore:
                checkpoint_dict = []
                for ind in range(0, taskproc, 1):
                    shell_script_list.append("")
                    checkpoint_dict.append(dict())
                for ibase in range(conf.start_from, tasksize, taskproc):
                    for ind in range(ibase, ibase + taskproc, 1):
                        if (ind < tasksize):
                            checkpoint = re.findall("checkpoint_[0-9]+", checked_list[ind])[0] + ".sim"
                            if checkpoint in checkpoint_dict[ind - ibase]:
                                lst = checkpoint_dict[ind - ibase][checkpoint]
                            else:
                                lst = []
                                checkpoint_dict[ind - ibase][checkpoint] = lst
                            lst.append(checked_list[ind])
                for ind in range(0, taskproc, 1):
                    for cp, lst in checkpoint_dict[ind].iteritems():
                        globaldofile = toolconf.script_dir + '/sim_' + str(ind) + '_' + cp.replace('.sim', '.do')
                        with open(globaldofile, 'w') as dofile:
                            dofile.write("set PTH $::env(TMP)\nset WLFFilename ${{PTH}}/WLFSET_{0}.wlf\nset WLFDeleteOnQuit 1".format(ind))
                            dofile.write("\ntranscript file ${{PTH}}/log_{0}_nodename.txt".format(ind))
                            dofile.write("\ndo " + toolconf.list_init_file)
                            dofile.write("\ncheckpoint ${{PTH}}/cpoint_{0}.sim".format(str(ind)))
                            for l in lst:
                                dofile.write("\n\nrestore $::env(TMP)/cpoint_{0}.sim".format(str(ind)))
                                dofile.write("\nif { [catch {nowhen *} err] } {}")
                                dofile.write("\ndo " + toolconf.script_dir + "/" + l)
                            dofile.write("\nquit\n")
                        shell_script_list[ind] += "\nvsim -c -restore {0}/{1} -do \"do {2}\" > {3}/log_{4}.log".format(toolconf.checkpoint_dir, cp, globaldofile, toolconf.log_dir, str(ind))

            # Run the simulation (Submit the jobs)
            create_restricted_file('vsim.wlf')
            for ind in range(0, taskproc, 1):
                # normalize the script
                shell_script_list[ind] = shell_script_list[ind][1:]
                robust_file_write("./ilogs/shfile_" + str(ind) + ".sh", shell_script_list[ind])
                # Push to the queue - qsub
                run_qsub(work_label + str("%03d" % ind), shell_script_list[ind], conf.work_dir, config.injector.sim_time_injections, "4g", os.path.join(conf.work_dir, toolconf.log_dir))
        time.sleep(15)
        jstat = get_queue_state_by_job_prefix(work_label)
        print "\n\tRunning processes:"
        for job in jstat.running:
            print job.name
        print "\n\tPending processes:"
        for job in jstat.pending:
            print job.name
        print "STARTED MONITORING"
        # Wait for work finish, delete unused temporary wlf files
        remaining_jobs = False
        simtime_max = time.strptime(config.injector.sim_time_injections, '%H:%M:%S')
        simtime_max_sec = simtime_max.tm_hour * 3600 + simtime_max.tm_min * 60 + simtime_max.tm_sec
        joblst = get_queue_state_by_job_prefix(work_label)
        if (config.injector.cancel_pending_tasks == 'on' and len(joblst.pending) > 0 and len(joblst.pending) <= (len(joblst.running) / 2) and (tasksize / config.injector.maxproc) > 10):
            print "Removing pending jobs"
            cancel_pending_jobs(joblst)
            joblst = get_queue_state_by_job_prefix(work_label)
            remaining_jobs = True
        joblst_prev = joblst
        resdir = os.path.join(conf.work_dir, toolconf.result_dir)
        prev_resdirstate = Dirstate(resdir)
        full_jobset_size = len(fscriptlist)

        while joblst.total_len() > 0:
            time.sleep(30)
            joblst = get_queue_state_by_job_prefix(work_label)
            if (len(joblst.running) != len(joblst_prev.running) or len(joblst.pending) != len(joblst_prev.pending)):
                joblst_prev = joblst
            t_queue_not_changed = joblst.time_difference_to_sec(joblst_prev)
            current_resdirstate = Dirstate(resdir)
            if current_resdirstate.nfiles >= full_jobset_size + 1:
                if (len(joblst.running) > 0) or (len(joblst.pending) > 0):
                    print commands.getoutput('qdel -f -u tuil')
                remaining_jobs = True
                break

            if (current_resdirstate.nfiles > prev_resdirstate.nfiles):
                prev_resdirstate = current_resdirstate
            t_resdir_not_changed = current_resdirstate.time_difference_to_sec(prev_resdirstate)
            print "Running: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending)) + ", \tQueue not changed since: " + str(t_queue_not_changed) + " [sec] / Max: " + str(simtime_max_sec) + ", \tRes_Files: " + str(current_resdirstate.nfiles) + " / " + str(full_jobset_size) + " not changed since: " + str(t_resdir_not_changed) + " [sec]"
            if (config.injector.monitoring_mode != 'on') and (t_resdir_not_changed > config.injector.wlf_remove_time):  # queue hang - remove remaining jobs and restart
                print 'Clearing the Queue...'
                res = commands.getoutput('qdel -f -u tuil')
                print res
                joblst = get_queue_state_by_job_prefix(work_label)
                ## while joblst.total_len() > 0:
                #    print "Running: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending))
                #     time.sleep(5)
                #     joblst = get_queue_state_by_job_prefix(work_label)
                remaining_jobs = True
                break
            # Remove intermediate files: wlfs
            # wlflist = glob.glob('wlft*')
            # otd_wlf_cnt = 0
            # otd_wlf_mod_time_min = 1000000
            # for w in wlflist:
            #    tmodif = how_old_file(w)
            #    if(tmodif > config.injector.wlf_remove_time):
            #        os.remove(w)
            #        otd_wlf_cnt += 1
            #        if(tmodif < otd_wlf_mod_time_min): otd_wlf_mod_time_min = tmodif
            # print "Removed " + str(otd_wlf_cnt) + " *wlft files, not modified since: " + str(otd_wlf_mod_time_min)
        current_resdirstate = Dirstate(resdir)
        if (current_resdirstate.nfiles < full_jobset_size):
            remaining_jobs = True
        if (remaining_jobs == False):
            print "FINISHED SIMULATION FOR: " + conf.work_dir
            time_stop = datetime.datetime.now().replace(microsecond=0)
            time_taken = time_stop - time_start
            print "\tTIME TAKEN: " + str(time_taken)
            with open(os.path.join(config.call_dir, 'sim_log_' + config.injector.campaign_label + '.txt'), 'a') as simlog:
                simlog.write("\nConfig: " + conf.label + ": Sim Time = " + str(time_taken))

            # Remove temporary files at working dir, produced by both modelsim and cluster engine
            os.chdir(conf.work_dir)
            tmpf_list = glob.glob(conf.label + '_sm_atmpt_' + "*")
            print "Removing temp files: " + str(len(tmpf_list))
            for w in tmpf_list:
                os.remove(w)
            # Remove intermediate dataset files: wlfs
            wlflist = glob.glob('WLFSET*')
            for w in wlflist:
                os.remove(w)
            wlflist = glob.glob('wlft*')
            for w in wlflist:
                os.remove(w)
                # Check whether termination requested
            # if(check_termination(config_file_path)):
            #    print "TERMINATION REQUESTED by user at config file: " + str(config_file_path)
            #    sys.exit()


def execute_injection_scripts_Multicore(config, toolconf, conf):
    fscriptlist = []
    print "\n\nStarting fault injection: " + conf.work_dir
    os.chdir(os.path.join(conf.work_dir, toolconf.script_dir))
    dolist = glob.glob('*.do')
    for i in dolist:
        if i.startswith('fault_') or i.startswith('areference_'):
            fscriptlist.append(i)
    fscriptlist.sort()
    print "Init scripts: " + str(len(fscriptlist))
    checked_list = []
    for s in fscriptlist:
        with open(s, 'r') as ds:
            dumpname = re.findall('[a-zA-Z0-9_]+\.lst', ds.read())[0]
            if not os.path.exists(os.path.join(conf.work_dir, toolconf.result_dir, dumpname)):
                checked_list.append(s)
    print("Scripts to Execute: {0}".format(len(checked_list)))

    tasksize = len(checked_list)
    if conf.stop_at > 0 and conf.stop_at < tasksize:
        tasksize = conf.stop_at
    os.chdir(conf.work_dir)
    create_restricted_file('vsim.wlf')
    proclist = []
    time_start = datetime.datetime.now().replace(microsecond=0)

    TME_Start = time.time()
    if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
        for ind in range(conf.start_from, tasksize, 1):
            checkpoint = re.findall("checkpoint_[0-9]+", checked_list[ind])[0] + ".sim"
            sim_script = "vsim -c -restore " + toolconf.checkpoint_dir + "/" + checkpoint
            sim_script += " -do \"do " + toolconf.script_dir + "/" + checked_list[ind] + "\""
            sim_script += " > " + toolconf.log_dir + "/log_" + str("%06d" % ind) + ".log"
            while get_active_proc_number(proclist) >= config.injector.maxproc:
                time.sleep(0.2)
            proc = subprocess.Popen(sim_script, shell=True)
            proclist.append(proc)
            console_message("Progress: {0:5d}/{1:5d}, Running proc: {2:5d}, Remaining time: {3:.2f} minutes".format(
                ind, tasksize, get_active_proc_number(proclist),
                (float(time.time()) - float(TME_Start)) * (float(tasksize - ind) / float(ind + 1)) / float(60)), ConsoleColors.Green, True)
            wlflist = glob.glob('wlft*')
            otd_wlf_cnt = 0
            otd_wlf_mod_time_min = 1000000
            for w in wlflist:
                tmodif = how_old_file(w)
                if tmodif > config.injector.wlf_remove_time:
                    try:
                        os.remove(w)
                        otd_wlf_cnt += 1
                        if tmodif < otd_wlf_mod_time_min: otd_wlf_mod_time_min = tmodif
                    except Exception as e:
                        print "Exception [" + str(e) + "] on file remove: " + w

    elif config.injector.checkpont_mode == CheckpointModes.WarmRestore:
        shell_script_list = []
        checkpoint_dict = []
        taskproc = config.injector.maxproc
        for ind in range(0, taskproc, 1):
            shell_script_list.append("")
            checkpoint_dict.append(dict())
        for ibase in range(conf.start_from, tasksize, taskproc):
            for ind in range(ibase, ibase + taskproc, 1):
                if (ind < tasksize):
                    checkpoint = re.findall("checkpoint_[0-9]+", checked_list[ind])[0] + ".sim"
                    if checkpoint in checkpoint_dict[ind - ibase]:
                        lst = checkpoint_dict[ind - ibase][checkpoint]
                    else:
                        lst = []
                        checkpoint_dict[ind - ibase][checkpoint] = lst
                    lst.append(checked_list[ind])
        for ind in range(0, taskproc, 1):
            for cp, lst in checkpoint_dict[ind].iteritems():
                globaldofile = toolconf.script_dir + '/sim_' + str(ind) + '_' + cp.replace('.sim', '.do')
                with open(globaldofile, 'w') as dofile:
                    dofile.write("set WLFFilename {0}/WLFSET_{1}.wlf\nset WLFDeleteOnQuit 1".format(toolconf.dataset_dir, ind))
                    dofile.write("\ntranscript file {0}/transcript_{1}.txt".format(toolconf.script_dir, ind))
                    dofile.write("\ndo " + toolconf.list_init_file)
                    dofile.write("\ncheckpoint {0}/cpoint_{1}.sim".format(toolconf.dataset_dir, str(ind)))
                    for l in lst:
                        dofile.write("\n\nrestore {0}/cpoint_{1}.sim".format(toolconf.dataset_dir, str(ind)))
                        dofile.write("\nif { [catch {nowhen *} err] } {}")
                        dofile.write("\ndo " + toolconf.script_dir + "/" + l)
                    dofile.write("\nquit\n")
                shell_script_list[ind] += "\nvsim -c -restore {0}/{1} -do \"do {2}\" > {3}/log_{4}.log".format(toolconf.checkpoint_dir, cp, globaldofile, toolconf.log_dir, str(ind))
        for ind in range(len(shell_script_list)):
            script_file = "{0}/shfile_{1}.sh".format(toolconf.script_dir, str(ind))
            robust_file_write(script_file, shell_script_list[ind][1:])
            if not script_file.startswith('./'): script_file = './' + script_file
            proc = subprocess.Popen(script_file, shell=True)
            proclist.append(proc)
            print 'Runned: ' + script_file
    while get_active_proc_number(proclist) > 0:
        tracenum = len(os.listdir(os.path.join(conf.work_dir, toolconf.result_dir))) - 2
        try:
            console_message("Running Processes: {0}, Traces stored: {1}/{2}, Remaining time: {3:.2f} minutes\r".format(len(get_active_proc_indexes(proclist)), tracenum, tasksize, (float(time.time()) - float(TME_Start)) * (float(tasksize - tracenum) / float(tracenum + 1)) / float(60)), ConsoleColors.Green, True)
        except:
            pass
        time.sleep(5)
    time_stop = datetime.datetime.now().replace(microsecond=0)
    time_taken = time_stop - time_start
    print "\n\tTotal Simulation Time: " + str(time_taken)
    os.chdir(conf.work_dir)
    for w in glob.glob('wlft*'):
        try:
            os.remove(w)
        except:
            pass
