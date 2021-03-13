# Fault injector top-level script: launches and monitors all SBFI phases)
# Launch format: python SBFI_Tool.py config.xml
# Where config.xml - configuration of fault injection campaign (XML-formatted)
# Refer to documentation for more information
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
import copy
from Davos_Generic import *
from Datamanager import *
from SBFI.SBFI_Initializer import *
from SBFI.SBFI_Profiler import *
from SBFI.SBFI_FaultloadGenerator import *
from SBFI.SBFI_Injector import *
from SBFI.SBFI_Analyzer import *
from Reportbuilder import *


def cleanup(config, toolconfig):
    timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S')
    for c in config.parconf:
        remove_dir(os.path.join(c.work_dir, toolconfig.script_dir))
        remove_dir(os.path.join(c.work_dir, toolconfig.log_dir))
        remove_dir(os.path.join(c.work_dir, toolconfig.dataset_dir))

        create_folder(c.work_dir, toolconfig.script_dir, timestamp)
        create_folder(c.work_dir, toolconfig.log_dir, timestamp)
        create_folder(c.work_dir, toolconfig.dataset_dir, timestamp)

    for c in config.parconf:
        if config.injector.create_scripts:
            remove_dir(os.path.join(c.work_dir, toolconfig.result_dir))
            create_folder(c.work_dir, toolconfig.result_dir, timestamp)
        else:
            for c in glob.glob(os.path.join(c.work_dir, toolconfig.result_dir, '*.*')):
                if not c.endswith(toolconfig.reference_file):
                    os.remove(c)
    for c in config.parconf:
        if config.injector.create_checkpoints:
            remove_dir(os.path.join(c.work_dir, toolconfig.checkpoint_dir))
            create_folder(c.work_dir, toolconfig.checkpoint_dir, timestamp)


def compile_project(config, toolconfig):
    if len(config.genconf.compile_script) == 0:
        return
    # When using Sun Grid Engine
    if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        for c in config.parconf:
            run_qsub(config.injector.work_label + '_compile_' + c.label,
                     "vsim -c -do \"do " + config.genconf.compile_script + " " + c.compile_options + " ;quit\" > ./ilogs/compile_log.txt",
                     c.work_dir, config.injector.sim_time_checkpoints, "2g", os.path.join(c.work_dir, toolconf.log_dir))
        joblst = get_queue_state_by_job_prefix(config.injector.work_label + '_compile_')
        while joblst.total_len() > 0:
            print "[Compile] Running: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending))
            time.sleep(15)
            joblst = get_queue_state_by_job_prefix(config.injector.work_label + '_compile_')
        time.sleep(30)
    # When using Multicore PC
    elif config.platform == Platforms.Multicore:
        for c in config.parconf:
            os.chdir(c.work_dir)
            compile_script = "vsim -c -do \"do " + config.genconf.compile_script + " " + c.compile_options + " ;quit\" > ./ilogs/compile_log.txt"
            proc = subprocess.Popen(compile_script, shell=True)
            print "RUN: " + compile_script
            proc.wait()


def generate_reference_script(config, toolconfig):
    for c in config.parconf:
        scale_factor = float(c.clk_period) / float(config.genconf.std_clk_period)
        init_time = int(config.genconf.std_init_time * scale_factor)
        workload_time = int(config.genconf.std_workload_time * scale_factor)
        print "Scale factor: " + str(scale_factor)
        reference_script = "do " + config.genconf.run_script + " " + c.run_options
        reference_script += "\nrun " + str(init_time) + "ns"
        reference_script += "\ncheckpoint " + toolconfig.checkpoint_dir + "/" + toolconfig.std_start_checkpoint
        reference_script += "\ncheckpoint " + toolconfig.checkpoint_dir + "/checkpoint_0.sim"
        reference_script += "\nquit\n"
        os.chdir(c.work_dir)
        with open(toolconfig.script_dir + "/checkpointsim.do", "w") as reference_script_file:
            reference_script_file.write(reference_script)
        reference_script = ""
        if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
            reference_script += 'set WLFFilename ./idatasets/WLFSET_REFERENCE.wlf\nset WLFFileLock 0\nset WLFDeleteOnQuit 1'
            reference_script += "\ntranscript file " + toolconfig.log_dir + "/log_reference.txt"
        reference_script += "\nset ExecTime " + str(workload_time) + "ns"
        reference_script += ("\nwhen \"\$now >= $ExecTime && {0}'event && {1} == 1\"".format(config.genconf.clk_signal,
                                                                                             config.genconf.clk_signal) if config.genconf.clk_signal != '' else "\nwhen \"\$now >= $ExecTime\"") + " { force -freeze " + (
                                toolconf.finish_flag if config.genconf.finish_flag == '' else config.genconf.finish_flag) + " 1 }"
        if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
            reference_script += "\ndo " + toolconfig.list_init_file
        reference_script += "\nrun [scaleTime $ExecTime 1.01]"
        reference_script += "\nwrite list " + toolconfig.result_dir + "/" + toolconfig.reference_file
        if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
            reference_script += "\nquit\n"
        with open(toolconfig.script_dir + "/areference__checkpoint_0.do", "w") as simple_reference_file:
            simple_reference_file.write(reference_script)


def create_checkpoints(config, toolconfig):
    # When using Sun Grid Engine
    if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        for c in config.parconf:
            # qsub_wait_threads(maxproc-1)
            run_qsub(config.injector.work_label + c.label,
                     "vsim -c -do \"do ./iscripts/checkpointsim.do \" > ./iresults/checkpoint_sim_log.txt", c.work_dir,
                     config.injector.sim_time_checkpoints, "4g", os.path.join(c.work_dir, toolconf.log_dir))
            print "STARTED CHECKPOINT SIM: " + c.label + " MAX TIME REQUESTED: " + config.injector.sim_time_checkpoints
        joblst = get_queue_state_by_job_prefix(config.injector.work_label)
        while joblst.total_len() > 0:
            print "Running: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending))
            time.sleep(15)
            joblst = get_queue_state_by_job_prefix(config.injector.work_label)
    # When using Multicore PC
    elif config.platform == Platforms.Multicore:
        tasksize = len(config.parconf)
        print "TASKSIZE = " + str(tasksize)
        for ibase in range(0, tasksize, config.injector.maxproc):
            proclist = []
            print "ibase:" + str(ibase)
            for ind in range(ibase, ibase + config.injector.maxproc, 1):
                if (ind < tasksize):
                    os.chdir(config.parconf[ind].work_dir)
                    sim_script = "vsim -c -do \"do ./iscripts/checkpointsim.do \"> ./iresults/checkpoint_sim_log.txt"
                    proc = subprocess.Popen(sim_script, shell=True)
                    print "\trunned ind:" + str(ind) + " : " + sim_script
                    proclist.append(proc)
            for c in proclist:
                c.wait()


def generate_precise_checkpoints(config, toolconf, conf):
    scale_factor = float(conf.clk_period) / float(config.genconf.std_clk_period)
    delta = int(config.genconf.std_workload_time * scale_factor / config.injector.workload_split_factor)
    print "Checkpoints Delta: " + str(delta)
    ct_script = "transcript file " + toolconf.log_dir + "/log_multiple_checkpoints.txt"
    c_time_point = int(0)
    for ind in range(0, config.injector.workload_split_factor, 1):
        ct_script += "\ncheckpoint " + toolconf.checkpoint_dir + "/checkpoint_" + str(c_time_point) + ".sim"
        ct_script += "\nrun " + str(delta) + "ns"
        c_time_point += delta
    ct_script += "\nquit\n"
    os.chdir(conf.work_dir)
    with open(toolconf.script_dir + "/checkpoints_split.do", "w") as ct_script_file:
        ct_script_file.write(ct_script)
    sim_script = "vsim -c -restore " + toolconf.checkpoint_dir + "/" + toolconf.std_start_checkpoint
    sim_script += " -do \"do " + toolconf.script_dir + "/checkpoints_split.do \""
    sim_script += " > " + toolconf.log_dir + "/log_checkpoints_split.log"
    print "Saving clustering checkpoints: " + sim_script

    # Running chekpoints script
    if config.platform == Platforms.Multicore:
        proc = subprocess.Popen(sim_script, shell=True)
        proc.wait()
        print "Finished, Checkpoints stored"
    elif config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        remaining_jobs = True
        task_run_at = 0
        while (remaining_jobs):
            task_run_at += 1
            cpdir = os.path.join(conf.work_dir, toolconf.checkpoint_dir)
            if Dirstate(cpdir).nfiles >= config.injector.workload_split_factor: break
            work_label = config.injector.work_label + 'cp_' + str(task_run_at) + '_'
            run_qsub(work_label + conf.label, sim_script, conf.work_dir, config.injector.sim_time_checkpoints, "4g",
                     os.path.join(conf.work_dir, toolconf.log_dir))
            time.sleep(20)
            joblst = get_queue_state_by_job_prefix(work_label + conf.label)
            while joblst.total_len() > 0:
                if (Dirstate(cpdir).nfiles >= config.injector.workload_split_factor): break
                print "Running: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending))
                time.sleep(15)
                joblst = get_queue_state_by_job_prefix(work_label + conf.label)
            # time.sleep(wlf_remove_time)
            cpdirstate = Dirstate(cpdir)
            if (cpdirstate.nfiles >= config.injector.workload_split_factor):
                remaining_jobs = False
    print "Finished, Checkpoints stored"


def launch_analysis(config, toolconf, conf, datamodel):
    if config.platform == Platforms.Multicore or config.platform == Platforms.Grid:
        if datamodel == None: raw_input('Err 01: datamodel not initialized')
        datamodel.dbhelper.BackupDB(False)
        process_dumps(config, toolconf, conf, datamodel)
    elif config.platform == Platforms.GridLight:
        work_label = config.injector.work_label + 'Analysis_'
        run_qsub(work_label, 'python Analyzer_Iso_Grid.py ' + config.file + ' ' + conf.label + ' > ' + 'Analyzer.log',
                 config.call_dir, config.injector.sim_time_injections, "4g",
                 os.path.join(conf.work_dir, toolconf.log_dir))
        joblst_prev = get_queue_state_by_job_prefix(work_label)
        remaining_jobs = True
        while remaining_jobs:
            time.sleep(5)
            joblst = get_queue_state_by_job_prefix(work_label)
            if (len(joblst.running) != len(joblst_prev.running) or len(joblst.pending) != len(joblst_prev.pending)):
                joblst_prev = joblst
            t_queue_not_changed = joblst.time_difference_to_sec(joblst_prev)
            if joblst.total_len() == 0:
                remaining_jobs = False
                # Check for job hang
            elif t_queue_not_changed > 500 and how_old_file(
                    os.path.normpath(os.path.join(config.call_dir, 'Analyzer.log'))) > 200:
                res = commands.getoutput('qdel -f -u tuil')
                print res
                time.sleep(5)
                try:
                    # one more copy just in case
                    # shutil.copy(config.get_DBfilepath(False), config.get_DBfilepath(False).replace('.db', datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S') + '.db'))
                    # Recover DB
                    shutil.copy(config.get_DBfilepath(True), config.get_DBfilepath(False))
                except Exception as e:
                    pass
                # Re-run analysis
                run_qsub(work_label,
                         'python Analyzer_Iso_Grid.py ' + config.file + ' ' + conf.label + ' > ' + 'Analyzer.log',
                         config.call_dir, config.injector.sim_time_injections, "4g",
                         os.path.join(conf.work_dir, toolconf.log_dir))
                remaining_jobs = True
            print "Analysis: " + str(len(joblst.running)) + ",\tPending: " + str(len(joblst.pending))
        shutil.copy(config.get_DBfilepath(False), config.get_DBfilepath(True))
    print 'Analysis completed'


# True - terminate, False - continue with modified configuration
def tweak_config_and_check_termination(config):
    for f in config.injector.fault_model:
        if f.increment_time_step == 0:
            return True
        f.time_start += f.increment_time_step * f.experiments_per_target
        f.time_end += f.increment_time_step * f.experiments_per_target
    tlim = (
            config.genconf.std_workload_time / config.genconf.std_clk_period) if f.time_mode == TimeModes.ClockCycle else config.genconf.std_workload_time
    return (f.time_start > tlim)


def RunSBFI(datamodel, config, toolconf):
    # Cleanup
    if config.injector.cleanup_folders:
        cleanup(config, toolconf)
        print "Cleanup Completed"

    # Initialize HDL models for simulation: creates simNodes.xml and SimInitModel.do for each HDLmodel
    if config.initializer_phase:
        InitializeHDLModels(config, toolconf)

    # Compile project
    if config.injector.compile_project:
        compile_project(config, toolconf)
        print "Compilation Completed"
        config.injector.compile_project = False

    # Reference simulation script
    if config.injector.create_scripts:
        generate_reference_script(config, toolconf)
        print "Reference Created"
        config.injector.create_scripts = False
    # Library can be removed because checkpoint encapsulates everything required for simulation
    if config.injector.remove_par_lib_after_checkpoint_stored:
        for c in config.parconf:
            rm_dir = os.path.join(c.work_dir, toolconf.par_lib_path)
            if (os.path.exists(rm_dir)):
                print 'Removing par_lib: ' + rm_dir
                shutil.rmtree(rm_dir)
    # Generate checkpoints
    if config.injector.create_checkpoints:
        create_checkpoints(config, toolconf)
        print "Checkpoints Created"
        config.injector.create_checkpoints = False

    # Profiling: fills the table Profiling and appends related data into table Targets
    if config.profiler_phase and datamodel != None:
        ProfileHdlModels(config, toolconf, datamodel)

    # Run fault injection experiments
    if config.injector_phase:
        iteration = int(0)
        S = len(config.parconf)
        config_bcp = copy.deepcopy(config)
        # Now each HDL model is processes one by one
        for conf in config.parconf:
            config = copy.deepcopy(config_bcp)
            # 3.6. Run simulation to obtain clustering checkpoints
            if config.injector.create_precise_checkpoints:
                generate_precise_checkpoints(config, toolconf, conf)

            # You may tweak the configuration just before launching the Generator-Simulator-Analyzer threads
            Finish_Flag = False
            while not Finish_Flag:
                iteration += 1
                with open(os.path.join(config.call_dir, config.injector.campaign_label + '_log.log'), 'a') as logfile:
                    logfile.write('\n\n\n\n' + datetime.datetime.strftime(datetime.datetime.now(),
                                                                          '%Y-%m-%d_%H-%M-%S') + ' : ' + to_string(
                        config.injector.fault_model[0]) + ' : \n\t\tITERATION ' + str(iteration))

                # Export injection scripts for the given model and faultload configuration
                if config.injector.create_injection_scripts:
                    generate_faultload(FaultloadModes.Sampling, config, conf, toolconf, fault_dict)

                # Execute injection scripts (simulate - on Selected platform)
                if config.injector.run_faultinjection:
                    execute_injection_scripts(config, toolconf, conf)

                # Analyze observation traces and save the results to the database
                launch_analysis(config, toolconf, conf, datamodel)

                # Adjust the configuration for next iteration of long injection campaign (legacy feature to be removed)
                Finish_Flag = tweak_config_and_check_termination(config)
                if not Finish_Flag:
                    cleanup(config, toolconf)

    # Build SBFI report on the basis of results collected in the database
    if config.reportbuilder_phase:
        build_report(config, toolconf, datamodel)
    if datamodel is not None:
        datamodel.SyncAndDisconnectDB()


# Script entry point when launched directly
if __name__ == "__main__":
    sys.stdin = open('/dev/tty')
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    # extract SBFI configuration from input XML
    tree = parse_xml_config(sys.argv[1]).getroot()
    davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
    config = davosconf.SBFIConfig
    config.parconf = davosconf.parconf
    config.file = sys.argv[1]
    print (to_string(config, "Configuration: "))
    fault_dict = FaultDict(config.genconf.library_specification)
    # Prepare data model
    datamodel = None
    if config.platform == Platforms.Multicore or config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        if not os.path.exists(davosconf.report_dir):
            os.makedirs(davosconf.report_dir)
        datamodel = DataModel()
        datamodel.ConnectDatabase(config.get_DBfilepath(False), config.get_DBfilepath(True))
        datamodel.RestoreHDLModels(config.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
        datamodel.SaveHdlModels()
    # Launch fault injection experiment
    RunSBFI(datamodel, config, toolconf)
    try:
        set_permissions(davosconf.report_dir, 0o777)
    except OSError as e:
        print("Warning: Unable to set 777 permissions on {0}".format(davosconf.report_dir))
    print("Experiment Completed, check SBFI report at: {0}".format(davosconf.report_dir))
# user_dict = ast.literal_eval(tree.findall('DAVOS')[0].findall('ExperimentalDesign')[0].findall('generic')[0].get('custom_parameters'))
