# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A fault-load builder for the RT-level and implementation-level SBFI experiements.
#       Generates a set of fault simulation scripts (for the QuestaSim/ModelSim simulator)
#       using fault dictionaries from the ./FaultDictionaries folder.
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

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
from SBFI.SBFI_Profiler import *

class FaultloadModes:
    Sampling, Exhaustive, Mixed, Staggering = range(4)


def get_checkpoints(dir):
    """Looks for simulation checkpoints

    Checkpoint files should be labeled by simulation time instants.
    Example of valid checkpoint fname: checkpoint_1010.sim

    Args:
        dir (str): directory containing the checkpoints

    Returns:
        list: list of checkpoint instants sorted ascending
    """
    print('Checkpoints in dir: {0}'.format(dir))
    checkpointlist = []
    if not os.path.exists(dir):
        print 'Generate injection scripts: Checkpoints dir does not exist: ' + dir
        return checkpointlist
    os.chdir(dir)
    flist = glob.glob('*.sim')
    for i in flist:
        if i.startswith('checkpoint'):
            checkpointlist.append(int(re.findall("[0-9]+", i)[0]))
    checkpointlist.sort()
    print "Checkpoints: {0}".format("\n".join([str(i) for i in checkpointlist]))
    if len(checkpointlist) == 0:
        print 'Generate injection scripts: No checkpoints found at ' + dir
    return checkpointlist


def get_random_injection_time(h_start_time, h_end_time, time_mode, sample_size, scale_factor, clk_period, std_workload_time):
    """Generates a list of injection time instants

    Args:
        h_start_time (int): start of injection interval
        h_end_time (int):  end of injection interval
        time_mode (TimeModes): input units - absolute (ns), relative (% of workload duration), or clock cycle
        sample_size (int): number of injection instants to populate
        scale_factor (float): factor that scales all time instants wrt. reference clock period
        clk_period (float): reference clock period
        std_workload_time (int): reference workload duration

    Returns:
        list: list of injection instants (integers)
    """
    res = []
    # Injection Time to absolute units (ns)
    if time_mode == TimeModes.Relative:
        inj_start_time = float(std_workload_time) * h_start_time * scale_factor
        inj_stop_time = float(std_workload_time) * h_end_time * scale_factor
    elif time_mode == TimeModes.Absolute:
        inj_start_time = h_start_time * scale_factor
        inj_stop_time = h_end_time * scale_factor
    elif time_mode == TimeModes.ClockCycle:
        inj_start_time = h_start_time * clk_period
        inj_stop_time = h_end_time * clk_period
    # print "Start time: " + str(inj_start_time) + "\nStop time: " + str(inj_stop_time)
    nonrandom = (inj_stop_time == 0 or inj_stop_time <= inj_start_time)
    for t in range(sample_size):
        res.append(inj_start_time if nonrandom else random.randint(int(inj_start_time), int(inj_stop_time)))
    res.sort()
    return res


def generate_faultload(mode, config, modelconf, toolconf):
    os.chdir(os.path.join(modelconf.work_dir, toolconf.script_dir))
    flist = glob.glob('fault*.do')
    if len(flist) > 0 and os.path.exists(os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file)) and not config.SBFI.clean_run:
        print('{0}: using existing faultload'.format(modelconf.label))
        return len(flist)
    else:
        faultdict = FaultDict(os.path.join(config.call_dir, config.SBFI.fault_dictionary))
        if mode == FaultloadModes.Sampling:
            return sample_fault_generator(config, modelconf, toolconf, faultdict)
        elif mode == FaultloadModes.Mixed:
            return mixed_faultload_generator(config, modelconf, toolconf, faultdict)
        elif mode == FaultloadModes.Staggering:
            return stagger_faultload_generator(config, modelconf, toolconf, faultdict)
        else:
            raise ValueError("Requested faultload mode is not defined and/or not implemented")


def match_timepoint(points, base_point, left, right):
    for t in points:
        delta = base_point - t
        if left <= delta <= right:
            return t
def match_centered(points, base_point, left, right):
    res_t, res_delta = None, None
    mid = float(left+right)/2.0
    for t in points:
        delta = base_point - t
        if left <= delta <= right:
            if (res_delta is None) or (abs(delta-mid) < (res_delta-mid)):
                res_delta = delta
                res_t = t
    return res_t



def stagger_faultload_generator(config, modelconf, toolconf, faultdict):
    DescTable = Table('Faultlist', ['INDEX','DUMPFILE','TARGET','INSTANCE_TYPE','INJECTION_CASE','FAULT_MODEL',
                                    'FORCED_VALUE','DURATION','TIME_INSTANCE','OBSERVATION_TIME',
                                    'HEAD_TIME', 'INTERVAL', 'OFFSET',
                                    'SWITCH_INSTANT', "ACTIVE_NODES",
                                    'MAX_ACTIVITY_DURATION', 'PROFILED_VALUE','ON_TRIGGER'])
    checkpointlist = get_checkpoints(os.path.join(config.call_dir, modelconf.work_dir, toolconf.checkpoint_dir))
    os.chdir(os.path.join(modelconf.work_dir, toolconf.script_dir))
    for fconfig in config.SBFI.fault_model:
        random.seed(fconfig.rand_seed)
        nodetree = ET.parse(os.path.join(modelconf.work_dir, toolconf.injnode_list)).getroot()
        inj_nodes = ConfigNodes(modelconf.label, nodetree)
        nodelist = inj_nodes.get_all_by_typelist(fconfig.target_logic)
        activity_profile = estimate_RTL_switching_activity(modelconf, nodelist)
        for regname, val in activity_profile.items():
            start_time = val['sw_events'][0]
            for i in range(len(val['sw_events'])):
                val['sw_events'][i] -= start_time
            val['sw_events'].pop(0) #first event may be not due to switching, but simulator logging initial value

        #Export registers description table
        reg_id = {}
        reg_per_time = {}
        id = 0
        RegDesc = Table("registers", ["ID", "REGNAME", "SW_PER_CYCLE", "EFFECTIVE_SWITHES"])
        for regname, val in activity_profile.items():
            reg_id[regname] = id
            for t in val['sw_events']:
                if t not in reg_per_time:
                    reg_per_time[t] = set()
                reg_per_time[t].add(id)
            id += 1
            RegDesc.add_row([str(id), regname,
                             '{0:.2f}'.format(100 * float(len(val['sw_events'])) / (modelconf.workload_time / modelconf.clk_period)),
                             str(len(val['sw_events'])) ])
        RegDesc.to_csv(";", True, os.path.join(modelconf.work_dir, toolconf.result_dir, "registers.csv"))

        script_index = 0
        exp_dict = {}
        tested_nodes = set()
        SampleSizeGoal = fconfig.sample_size * len(fconfig.stagger_offsets)
        while DescTable.rownum() < SampleSizeGoal:
            #select random injection target and time instant
            while True:
                reg_name = random.choice(activity_profile.keys())
                reg = activity_profile[reg_name]
                c = InjectionNode()
                c.type = reg['type']
                c.name = reg_name if len(reg['indexes'])==0 else '{0:s}({1:s})'.format(reg_name, random.choice(reg['indexes']))
                if c.name not in tested_nodes:
                    break
            inj_time_base = get_random_injection_time(fconfig.time_start, fconfig.time_end, fconfig.time_mode, fconfig.multiplicity, 1.0, modelconf.clk_period, modelconf.workload_time)[0]
            head_time = -1
            for t in reg['sw_events']:
                if t > inj_time_base:
                    head_time = t
                    break
            if head_time <= 0:
                continue

            # Generate Head-trail pairs and corresponding SBFI scripts
            time_pairs = {0: (head_time, head_time)}
            for offset in fconfig.stagger_offsets:
                t = match_centered(reg['sw_events'], head_time, offset[0], offset[1])
                if t is not None:
                    time_pairs[offset[0]] = (t, head_time)
            for offset in fconfig.stagger_offsets:
                if offset[0] not in time_pairs:
                    for v in [k[0] for k in time_pairs.values()]:
                        t = match_centered(reg['sw_events'], v, offset[0], offset[1])
                        if (t is not None) and (t not in [k[0] for k in time_pairs.values()]):
                            time_pairs[offset[0]] = (t, v)
                            break
            if len(time_pairs) <= 1:
                continue
            tested_nodes.add(c.name)
            inj_code = get_injection_code_all(c, faultdict, fconfig, 1.0, None)[0]
            duration = random.uniform(fconfig.duration_min, fconfig.duration_max)
            delay = random.randrange(1, modelconf.clk_period)
            for offset in sorted(time_pairs.keys()):
                (t, head_time) = time_pairs[offset]

                head_time += delay
                inj_time = t + delay
                str_index = "{0:06d}".format(script_index)
                if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                    if config.platform in [Platforms.Grid, Platforms.GridLight]:
                        inj_script = "set PTH $::env(TMP)\ncatch {{ set WLFFilename ${{PTH}}/WLFSET_{0}.wlf }}\nset WLFDeleteOnQuit 1".format(str_index)
                        inj_script += "\ntranscript file ${{PTH}}/log_{0}_nodename.txt".format(str_index)
                    else:
                        inj_script = "catch {{ set WLFFilename {0}/WLFSET_{1}.wlf }}\nset WLFFileLock 0\nset WLFDeleteOnQuit 1".format(toolconf.dataset_dir, str_index)
                        inj_script += "\ntranscript file {0}/log_{1}_nodename.txt".format(toolconf.log_dir, str_index)
                    # select closest checkpoint
                    checkpoint_linked = 0
                    for ct in checkpointlist:
                        if ct < inj_time:
                            checkpoint_linked = ct

                    inj_script += "\nset ExecTime {0}ns".format(str(int(modelconf.workload_time) - int(checkpoint_linked)) if fconfig.trigger_expression == '' else str(int(modelconf.workload_time)))
                    for i in range(fconfig.multiplicity):
                        simcmd = inj_code[2].replace('#DURATION', '{0:0.5f}ns'.format(duration))
                        if fconfig.trigger_expression == '':  # time-driven injection
                            inj_script += "\n\twhen \"\\$now >= {0}ns\" {{\n\t\tputs \"Time: $::now: Injection of {1}\"\n\t{2}\n\t}}\n".format(str(int(inj_time) - int(checkpoint_linked)), fconfig.model, simcmd)
                            fname = "fault_" + str_index + "__checkpoint_" + str(checkpoint_linked) + ".do"
                        else:  # event-driven injection (on trigger expression)
                            inj_script += "\n\nwhen {0} {{\n\twhen \"\\$now >= {1}ns\" {{\n\t\tputs \"Time: $::now: Injection of {2}\"\n\t{3}\n\t}}\n}}".format(fconfig.trigger_expression, str(int(inj_time)), fconfig.model, simcmd)
                            fname = "fault_" + str_index + "__checkpoint_0" + ".do"
                    if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\n\ndo {0}".format(toolconf.list_init_file)
                    inj_script += "\nrun $ExecTime; config list -strobeperiod 1ns -strobestart [expr $now/1000] -usestrobe 1; run 1ns;"
                    dumpfilename = "dump_{0}_nodename.lst".format(str_index)
                    inj_script += "\nwrite list -events {0}/{1}".format(toolconf.result_dir, dumpfilename)
                    if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\nquit\n"
                    robust_file_write(fname, inj_script)
                    sys.stdout.write('Stored script: {0:06d}\r'.format(script_index))
                    sys.stdout.flush()

                    #s_h, s_t = reg_per_time[head_time], reg_per_time[t]
                    #activity_match_rate = 100.0*len(s_h.intersection(s_t)) / len(reg_id)
                    descriptor = [str(script_index),
                                  dumpfilename,
                                  inj_code[0],
                                  reg['type'],
                                  inj_code[1],
                                  fconfig.model + fconfig.modifier,
                                  fconfig.forced_value,
                                  str(duration),
                                  str(inj_time),
                                  str(int(modelconf.workload_time) - int(inj_time)),
                                  str(head_time),
                                  str(offset),
                                  str(head_time-inj_time),
                                  str(t),
                                  ":".join([str(i) for i in sorted(list(reg_per_time[t]))]),
                                  '',
                                  '',
                                  '']
                    DescTable.add_row(descriptor)
                script_index += 1
    DescTable.to_csv(';', True, os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file))


    #desctable = ExpDescTable(modelconf.label)
    #desctable.build_from_csv_file(os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file), "Other")
    #script_dict = {}
    #for i in desctable.items:
    #    script_dict[(i.target, i.injection_time)] = i.index
    #for i in desctable.items:
    #    i.head_index = script_dict[(i.target, i.head_time)]
    #print(modelconf.work_dir)





def sample_fault_generator(config, modelconf, toolconf, faultdict):
    """Generates randomly sampled faultload

    Exports a set of TCL scripts for the ModelSim simulator.
    Each script corresponds to one (independent) injection run.

    Args:
        config (SBFIConfiguration): parameters of SBFI experiment (SBFI tag of input configuration XML)
        modelconf (ParConfig): parameters of particular model configuration under test (ModelConfig tag of input XML)
        toolconf (ToolOptions): generic parameters of SBFI tool (not model-related)
        faultdict (FaultDict): fault dictionary for target implementation technology

    Returns:
        int: number of exported fault injection scripts
    """
    checkpointlist = get_checkpoints(os.path.join(config.call_dir, modelconf.work_dir, toolconf.checkpoint_dir))
    os.chdir(os.path.join(modelconf.work_dir, toolconf.script_dir))
    fdesclog_content = "sep=;\nINDEX;DUMPFILE;TARGET;INSTANCE_TYPE;INJECTION_CASE;FAULT_MODEL;FORCED_VALUE;DURATION;TIME_INSTANCE;OBSERVATION_TIME;MAX_ACTIVITY_DURATION;EFFECTIVE_SWITHES;PROFILED_VALUE;ON_TRIGGER;"

    dT = []
    script_index = 0
    for fconfig in config.SBFI.fault_model:
        random.seed(fconfig.rand_seed)
        # Select macrocells(targets) of the types specified in the faultload configuration
        nodetree = ET.parse(os.path.join(modelconf.work_dir, toolconf.injnode_list)).getroot()
        inj_nodes = ConfigNodes(modelconf.label, nodetree)
        nodelist = inj_nodes.get_all_by_typelist(fconfig.target_logic)
        inj_code_items = []
        for instance in nodelist:
            inj_code_items = inj_code_items + get_injection_code_all(instance, faultdict, fconfig, 1.0, None)

        for local_index in range(fconfig.sample_size):
            c = random.sample(inj_code_items, fconfig.multiplicity)
            inj_time_base = get_random_injection_time(fconfig.time_start, fconfig.time_end, fconfig.time_mode, fconfig.multiplicity, 1.0, modelconf.clk_period, modelconf.workload_time)
            duration = random.uniform(fconfig.duration_min, fconfig.duration_max)

            if fconfig.simulataneous_faults:
                inj_time_base = [inj_time_base[0]] * fconfig.multiplicity
            offsets = [0, 10, 20, 30, 40, 50, 100, 200, 500, 1000, 2000, 5000]
            for offset in offsets:
                inj_time = [v - offset for v in inj_time_base]
                str_index = "{0:06d}".format(script_index)
                inj_script = ""
                if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                    if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
                        inj_script = "set PTH $::env(TMP)\ncatch {{ set WLFFilename ${{PTH}}/WLFSET_{0}.wlf }}\nset WLFDeleteOnQuit 1".format(str_index)
                        inj_script += "\ntranscript file ${{PTH}}/log_{0}_nodename.txt".format(str_index)
                    else:
                        inj_script = "catch {{ set WLFFilename {0}/WLFSET_{1}.wlf }}\nset WLFFileLock 0\nset WLFDeleteOnQuit 1".format(toolconf.dataset_dir, str_index)
                        inj_script += "\ntranscript file {0}/log_{1}_nodename.txt".format(toolconf.log_dir, str_index)

                    # select closest checkpoint
                    checkpoint_linked = 0
                    for ct in checkpointlist:
                        if ct < inj_time[0]:
                            checkpoint_linked = ct

                    dT.append(float(modelconf.workload_time) - checkpoint_linked)
                    inj_script += "\nset ExecTime {0}ns".format(str(int(modelconf.workload_time) - int(checkpoint_linked)) if fconfig.trigger_expression == '' else str(int(modelconf.workload_time)))
                    for i in range(fconfig.multiplicity):
                        injcode = c[i][2].replace('#DURATION', '{0:0.5f}ns'.format(duration))
                        if fconfig.trigger_expression == '':  # time-driven injection
                            inj_script += "\n\twhen \"\\$now >= {0}ns\" {{\n\t\tputs \"Time: $::now: Injection of {1}\"\n\t{2}\n\t}}\n".format(str(int(inj_time[i]) - int(checkpoint_linked)), fconfig.model, injcode)
                            fname = "fault_" + str_index + "__checkpoint_" + str(checkpoint_linked) + ".do"
                        else:  # event-driven injection (on trigger expression)
                            inj_script += "" + + "\n\nwhen {0} {{\n\twhen \"\\$now >= {1}ns\" {{\n\t\tputs \"Time: $::now: Injection of {2}\"\n\t{3}\n\t}}\n}}".format(fconfig.trigger_expression, str(int(inj_time[i])), fconfig.model, injcode)
                            fname = "fault_" + str_index + "__checkpoint_0" + ".do"
                    if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\n\ndo {0}".format(toolconf.list_init_file)
                    inj_script += "\nrun $ExecTime; config list -strobeperiod 1ns -strobestart [expr $now/1000] -usestrobe 1; run 1ns;"
                    dumpfilename = "dump_{0}_nodename.lst".format(str_index)
                    inj_script += "\nwrite list -events {0}/{1}".format(toolconf.result_dir, dumpfilename)
                    if config.SBFI.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\nquit\n"

                    robust_file_write(fname, inj_script)
                    sys.stdout.write('Stored script: {0:06d}\r'.format(script_index))
                    sys.stdout.flush()
                    fdesclog_content += "\n" + str(script_index) + ";" + dumpfilename + ";" + c[0][0] + ";" + instance.type + ";" + c[0][1] + ";" + fconfig.model + fconfig.modifier + ";" + fconfig.forced_value + ";" + str(duration) + ";" + str(inj_time[0]) + ";" + str(int(modelconf.workload_time) - int(inj_time[0]))
                    if c[0][3] is not None:
                        fdesclog_content += ';{0:.2f};{1:d};{2:s};'.format(c[0][3].total_time, c[0][3].effective_switches, c[0][3].profiled_value)
                    else:
                        fdesclog_content += ';None;None;None;'
                    script_index += 1
                    fdesclog_content += fconfig.trigger_expression.replace(';', ' ').replace('&apos', '') + ';'
    robust_file_write(os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file), fdesclog_content)

    checkpoint_speedup = len(dT) * float(modelconf.workload_time) / (sum(dT))
    print('CHECKPOINT SPEED-UP: {0:0.3f}'.format(checkpoint_speedup))
    return(script_index)


def mixed_faultload_generator(config, modelconf, toolconf, faultdict):
    """Generates a faultload in exhaustive or semi-random mode

    Exports a set of TCL scripts for the ModelSim simulator.
    Each script corresponds to one (independent) injection run.

    Args:
        config (SBFIConfiguration): parameters of SBFI experiment (SBFI tag of input configuration XML)
        modelconf (ParConfig): parameters of particular model configuration under test (ModelConfig tag of input XML)
        toolconf (ToolOptions): generic parameters of SBFI tool (not model-related)
        faultdict (FaultDict): fault dictionary for target implementation technology

    Returns:
        int: number of exported fault injection scripts
    """

    # Build the list of checkpoints
    checkpointlist = get_checkpoints(os.path.join(modelconf.work_dir, toolconf.checkpoint_dir))

    script_index = 0
    fdesclog_content = "sep=;\nINDEX;DUMPFILE;TARGET;INSTANCE_TYPE;INJECTION_CASE;FAULT_MODEL;FORCED_VALUE;DURATION;TIME_INSTANCE;OBSERVATION_TIME;MAX_ACTIVITY_DURATION;EFFECTIVE_SWITHES;PROFILED_VALUE;ON_TRIGGER;"
    scale_factor = float(modelconf.clk_period) / float(config.genconf.std_clk_period)
    for fconfig in config.injector.fault_model:
        # Select macrocells(targets) of the types specified in the faultload configuration
        nodetree = ET.parse(os.path.join(modelconf.work_dir, toolconf.injnode_list)).getroot()
        inj_nodes = ConfigNodes(modelconf.label, nodetree)

        nodelist = inj_nodes.get_all_by_typelist(fconfig.target_logic)
        if fconfig.sample_size > 0:
            buf = []
            for r in range(fconfig.sample_size):
                buf.append(nodelist[random.randint(0, len(nodelist) - 1)])
            nodelist = buf
        print("\n" + fconfig.model + ", " + str(fconfig.target_logic) + ", targets number: " + str(len(nodelist)))

        # Generate scripts
        os.chdir(os.path.join(modelconf.work_dir, toolconf.script_dir))
        for i in range(0, fconfig.experiments_per_target, 1):
            random.seed(fconfig.rand_seed + i)
            h_start_time = fconfig.time_start + (fconfig.increment_time_step * i)
            h_end_time = fconfig.time_end + (fconfig.increment_time_step * i)

            prev_desc = ('', random.getstate())
            for instance in nodelist:
                # bypass empty items, maintaining the same rand sequence (legacy feature to be removed)
                if instance.type == '__':
                    random.randint(h_start_time, h_end_time)
                    continue
                # build the list of tuples (inj_case, inj_code, profiling_descriptor)
                inj_code_items = get_injection_code_all(instance, faultdict, fconfig, scale_factor, None)

                if fconfig.sample_size > 0:
                    inj_code_items = random.sample(inj_code_items, 1)
                # for i in inj_code_items: raw_input(str(i))
                # for the instance from the same group as previous one: restore rand state to obtain the same random sequence
                if instance.group != '' and instance.group == prev_desc[0]:
                    random.setstate(prev_desc[1])
                else:
                    prev_desc = (instance.group, random.getstate())
                # Export Fault simulation scripts (*.do files)
                for c in inj_code_items:
                    str_index = str("%06d" % (script_index))
                    inj_script = ""
                    if config.injector.checkpoint_mode == CheckpointModes.ColdRestore:
                        if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
                            inj_script = "set PTH $::env(TMP)\nset WLFFilename ${{PTH}}/WLFSET_{0}.wlf\nset WLFDeleteOnQuit 1".format(str_index)
                            inj_script += "\ntranscript file ${{PTH}}/log_{0}_nodename.txt".format(str_index)
                        else:
                            inj_script = "set WLFFilename {0}/WLFSET_{1}.wlf\nset WLFFileLock 0\nset WLFDeleteOnQuit 1".format(toolconf.dataset_dir, str_index)
                            inj_script += "\ntranscript file " + toolconf.log_dir + "/log_" + str_index + "_nodename.txt"
                    inj_time = get_random_injection_time(h_start_time, h_end_time, fconfig.time_mode, fconfig.multiplicity, scale_factor, modelconf.clk_period, config.genconf.std_workload_time)

                    if fconfig.trigger_expression == '':  # time-driven injection
                        # find closest checkpoint
                        checkpoint_linked = 0
                        for ct in checkpointlist:
                            if ct < inj_time[0]:
                                checkpoint_linked = ct
                        inj_script += "\nset ExecTime " + str(int(config.genconf.std_workload_time * scale_factor) - int(checkpoint_linked)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                            inj_script += str(int(t) - int(checkpoint_linked)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nforeach i $InjTime {\n\twhen \"\\$now >= $i\" {\n\t\tputs \"Time: $::now: Injection of " + fconfig.model + "\"\n\t\t" + c[2] + "\n\t}\n}"
                        fname = "fault_" + str_index + "__checkpoint_" + str(checkpoint_linked) + ".do"
                    else:  # event-driven injection (on trigger expression)
                        inj_script += "\nset ExecTime " + str(int(config.genconf.std_workload_time * scale_factor)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                            inj_script += str(int(t)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nwhen {" + fconfig.trigger_expression + "} {\n\tforeach i $InjTime {\n\t\twhen \"\\$now >= $i\" {\n\t\t\tputs \"Time: $::now: Injection of " + fconfig.model + "\"\n\t\t\t" + c[2] + "\n\t\t}\n\t}\n}"
                        fname = "fault_" + str_index + "__checkpoint_0" + ".do"
                    inj_script += ("\nwhen \"\$now >= $ExecTime && {0}'event && {1} == 1\"".format(config.genconf.clk_signal, config.genconf.clk_signal) if config.genconf.clk_signal != '' else "\nwhen \"\$now >= $ExecTime\"") + " { force -freeze " + (toolconf.finish_flag if config.genconf.finish_flag == '' else config.genconf.finish_flag) + " 1 }"
                    if config.injector.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\n\ndo " + toolconf.list_init_file
                    inj_script += "\nrun [scaleTime $ExecTime 1.01]; config list -strobeperiod 1ns -strobestart [expr $now/1000] -usestrobe 1; run 1ns;"
                    dumpfilename = "dump_" + str_index + "_nodename.lst"
                    inj_script += "\nwrite list -events " + toolconf.result_dir + '/' + dumpfilename
                    if config.injector.checkpoint_mode == CheckpointModes.ColdRestore:
                        inj_script += "\nquit\n"

                    robust_file_write(fname, inj_script)
                    sys.stdout.write('Stored script {0}: {1:6d}\r'.format(c[1], script_index))
                    sys.stdout.flush()
                    fdesclog_content += "\n" + str(script_index) + ";" + dumpfilename + ";" + c[0] + ";" + instance.type + ";" + c[1] + ";" + fconfig.model + fconfig.modifier + ";" + fconfig.forced_value + ";" + str(fconfig.duration_max) + ";" + str(inj_time[0]) + ";" + str(int(config.genconf.std_workload_time * scale_factor) - int(inj_time[0]))
                    if c[3] is not None:
                        fdesclog_content += ';{0:.2f};{1:d};{2:s};'.format(c[3].total_time, c[3].effective_switches, c[3].profiled_value)
                    else:
                        fdesclog_content += ';None;None;None;'
                    script_index += 1
                    fdesclog_content += fconfig.trigger_expression.replace(';', ' ').replace('&apos', '') + ';'

    robust_file_write(os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file), fdesclog_content)
    return script_index


def get_injection_code_all(instance, faultdict, fconfig, scale_factor, PresimRes=None):
    """ Generates a list of fault injection scripts (sequence of ModelSim commands) for each injection case

    Injection case are retrieved from fault dictionary for tuples (instance, faultdict)

    Args:
        instance (InjectionNode): macrocell type from fault dictionary
        faultdict (FaultDict): fault dictionary for target implementation technology
        fconfig (FaultModelConfig): faultload configuration from input XML (fault_model tag)
        scale_factor (float): factor that scales time instants of selected model configuration wrt. reference values
        PresimRes: profiled switching activity (revision required!)

    Returns:
        list: list of tuples (targeted node/macrocell, injection case within the node, fault injection script, switching activity)
    """
    res = []
    faultdescriptor = faultdict.get_descriptor(fconfig.model, instance.type)
    if faultdescriptor == None:
        raw_input('Error: no descriptor found in dictionary for fault model: ' + str(fconfig.model) + '::' + instance.type)
    else:
        for injection_rule in faultdescriptor.injection_rules:
            for injection_case in injection_rule.injection_cases:
                # check injection_case.condition
                # build list of indexes - one script per index, max 2 dimensions, index for high dimension may come from profiling
                indset = []
                if PresimRes is not None:
                    for index_high in PresimRes.get(instance.type, instance.name, injection_case.label).address_descriptors:
                        if len(injection_case.dimensions) > 1:
                            for index_low in range(int(injection_case.dimensions[1].low_index), int(injection_case.dimensions[1].high_index) + 1, 1):
                                indset.append(('(' + str(index_high.address) + ')' + '(' + str(index_low) + ')', index_high))
                        else:
                            indset.append(('(' + str(index_high.address) + ')', index_high))
                elif len(injection_case.dimensions) > 0:
                    for index_high in range(int(injection_case.dimensions[0].low_index), int(injection_case.dimensions[0].high_index) + 1, 1):
                        if len(injection_case.dimensions) > 1:
                            for index_low in range(int(injection_case.dimensions[1].low_index), int(injection_case.dimensions[1].high_index) + 1, 1):
                                indset.append(('(' + str(index_high) + ')' + '(' + str(index_low) + ')', None))
                        else:
                            indset.append(('(' + str(index_high) + ')', None))

                # replace placeholders
                inj_code = injection_rule.code_pattern.replace('#PATH', instance.name).replace('#FORCEDVALUE', fconfig.forced_value)
                for node in injection_case.nodes:
                    inj_code = inj_code.replace(node.placeholder, node.nodename_pattern)

                if len(fconfig.CCF) > 0:
                    inj_code = '\n\n'.join([inj_code.replace(fconfig.CCF[0], fconfig.CCF[ind]) for ind in range(0, len(fconfig.CCF))])

                if len(indset) == 0:
                    res.append((instance.name, injection_case.label, inj_code, None))
                else:
                    for index in indset:
                        res.append((instance.name, injection_case.label + index[0], inj_code.replace('#DIM', index[0]), index[1]))
    return res
