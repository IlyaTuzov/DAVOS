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
        if config.SBFI.clean_run:
            dumppack = "Backup_{0}.zip".format(timestamp)
            os.chdir(c.work_dir)
            for d in [toolconfig.result_dir, toolconfig.script_dir, toolconfig.checkpoint_dir, toolconfig.code_dir]:
                zip_folder(d, dumppack)
            for d in [toolconfig.result_dir, toolconfig.script_dir, toolconfig.checkpoint_dir, toolconfig.log_dir, toolconfig.dataset_dir, toolconfig.code_dir]:
                remove_dir(os.path.join(c.work_dir, d))
        for d in [toolconfig.result_dir, toolconfig.script_dir, toolconfig.checkpoint_dir, toolconfig.log_dir, toolconfig.dataset_dir, toolconfig.code_dir]:
            if not os.path.exists(os.path.join(c.work_dir, d)):
                os.mkdir(os.path.join(c.work_dir, d))


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


def generate_clustering_checkpoints(config, toolconf, conf):
    """ Generates simulator checkpoints evenly distributed along the workload interval
    Args:
        config ():
        toolconf ():
        conf ():

    Returns:
    """
    delta = int(conf.workload_time / config.SBFI.workload_split_factor)
    checkpoints = ['{0}/checkpoint_{1}.sim'.format(toolconf.checkpoint_dir, i) for i in range(0, conf.workload_time, delta)]
    os.chdir(conf.work_dir)
    if not all([os.path.exists(i) for i in checkpoints]):
        ct_script = "transcript file {0}/log_clustering_checkpoints.txt".format(toolconf.log_dir)
        for cpt in checkpoints:
            ct_script += "\ncheckpoint {0}\nrun {1} ns".format(cpt, str(delta))
        ct_script += "\nquit\n"
        os.chdir(conf.work_dir)
        fscript = os.path.join(toolconf.script_dir, "clustering_checkpoints.do")
        with open(fscript, "w") as f:
            f.write(ct_script)

        sim_script = "vsim -c -restore {0} -do \"do {1}\" > ./{2}/log_checkpoints_split.log".format(os.path.join(conf.work_dir, conf.checkpoint),
                                                                                                    fscript, toolconf.log_dir)
        print "Generating clustering checkpoints, running: {0}".format(sim_script)
        if config.platform == Platforms.Multicore:
            proc = subprocess.Popen(sim_script, shell=True)
            proc.wait()
        elif config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
            run_qsub(config.experiment_label, sim_script, conf.work_dir, config.SBFI.time_quota, "4g",
                     os.path.join(conf.work_dir, toolconf.log_dir))
            monitor_sge_job(config.experiment_label, 15)
        print("{0}: Clustering checkpoints stored".format(conf.label))
    else:
        print('{0}: Using existing checkpoints'.format(conf.label))


def golden_run(config, toolconfig, c):
    """ Runs simulation without faults, generates reference trace
    Args:
        toolconfig:
        config:
        c (object):
    """
    os.chdir(c.work_dir)
    fscript = os.path.join(c.work_dir, toolconfig.script_dir, "areference__checkpoint_0.do")
    if not os.path.exists(os.path.join(c.work_dir, toolconfig.result_dir, toolconfig.reference_file)):
        reference_script = """
        catch {{set WLFFilename ./idatasets/WLFSET_REFERENCE.wlf}}
        set WLFFileLock 0
        set WLFDeleteOnQuit 1
        transcript file {0}/log_reference.txt
        set ExecTime {1}ns
        do {2}
        run $ExecTime
        write list {3}/{4}
        quit
        """.format(toolconfig.log_dir, c.workload_time, toolconfig.list_init_file, toolconfig.result_dir, toolconfig.reference_file)
        with open(fscript, "w") as f:
            f.write(reference_script)
        runscript = "vsim -c -restore {0} -do \"do {1}\" > ./{2}/golden_run.txt".format(os.path.join(c.work_dir, c.checkpoint),
                                                                                        fscript, toolconfig.log_dir)
        print('Running: {0}'.format(runscript))
        # Run on SGE cluster
        if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
            run_qsub(config.experiment_label, runscript, c.work_dir,
                     config.SBFI.time_quota, "4g", os.path.join(c.work_dir, toolconf.log_dir))
            monitor_sge_job(config.experiment_label, 15)
        # Run on Multicore PC
        elif config.platform == Platforms.Multicore:
            proc = subprocess.Popen(runscript, shell=True)
            proc.wait()
        print('{0}: Golden Run completed'.format(c.label))
    else:
        print('{0}: Using existing golden run results'.format(c.label))



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
    cleanup(config, toolconf)
    # Prepare models for SBFI experiments: locate fault targets, and generate trace scripts
    InitializeHDLModels(config, toolconf)

    for conf in config.parconf:
        generate_clustering_checkpoints(config, toolconf, conf)
        golden_run(config, toolconf, conf)

        # Generate SBFI scripts for the given model and faultload configuration
        generate_faultload(FaultloadModes.Sampling, config, conf, toolconf)

        # Execute injection scripts (simulate - on Selected platform)
        execute_injection_scripts(config, toolconf, conf)

        # Analyze observation traces and save the results to the database
        launch_analysis(config, toolconf, conf, datamodel)

    # Build SBFI report on the basis of results collected in the database
    build_report(config, toolconf, datamodel)
    if datamodel is not None:
        datamodel.SyncAndDisconnectDB()


# Script entry point when launched directly
if __name__ == "__main__":
    sys.stdin = open('/dev/tty')
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    # extract SBFI configuration from input XML
    tree = parse_xml_config(sys.argv[1]).getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    config.file = sys.argv[1]
    print (to_string(config, "Configuration: "))
    #fault_dict = FaultDict(os.path.join(config.call_dir, config.SBFI.fault_dictionary))
    # Prepare data model
    datamodel = None
    if config.platform == Platforms.Multicore or config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
        if not os.path.exists(config.report_dir):
            os.makedirs(config.report_dir)
        datamodel = DataModel()
        datamodel.ConnectDatabase(config.get_DBfilepath(False), config.get_DBfilepath(True))
        datamodel.RestoreHDLModels(config.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
        datamodel.SaveHdlModels()
    # Launch fault injection experiment
    RunSBFI(datamodel, config, toolconf)
    try:
        set_permissions(config.report_dir, 0o777)
    except OSError as e:
        print("Warning: Unable to set 777 permissions on {0}".format(config.report_dir))
    print("Experiment Completed, check SBFI report at: {0}".format(config.report_dir))
# user_dict = ast.literal_eval(tree.findall('DAVOS')[0].findall('ExperimentalDesign')[0].findall('generic')[0].get('custom_parameters'))
