# Generates a set of fault simulation scripts (currently for ModelSim)
# using fault dictionary and configuration of fault models from XML config file
# TODO: analysis of profiling metrics, including refactoring of existing ones from previous version
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



#---------------------------------------------------
# Builds the list of injection scripts (*.do files)
#---------------------------------------------------
def generate_injection_scripts(config, modelconf, toolconf, faultdict):
    #Build the list of checkpoints
    if(not os.path.exists(os.path.join(modelconf.work_dir, toolconf.checkpoint_dir))):
        print 'Generate injection scripts: Checkpoints dir does not exist: ' + os.path.join(modelconf.work_dir, toolconf.checkpoint_dir)
        return(0)
    os.chdir(os.path.join(modelconf.work_dir, toolconf.checkpoint_dir))
    checkpointlist = []
    flist = glob.glob('*.sim')
    for i in flist:
        if i.startswith('checkpoint'):
            checkpointlist.append( int(re.findall("[0-9]+", i)[0]) )
    checkpointlist.sort()
    print "Checkpoints: "
    for i in checkpointlist: print str(i)
    if(len(checkpointlist)==0):
        print 'Generate injection scripts: No checkpoints found at ' + os.path.join(modelconf.work_dir, toolconf.checkpoint_dir)
        return(0)

    script_index = 0
    fdesclog_content = "sep=;\nINDEX;DUMPFILE;TARGET;INSTANCE_TYPE;FAULT_MODEL;FORCED_VALUE;DURATION;TIME_INSTANCE;OBSERVATION_TIME;MAX_ACTIVITY_DURATION;EFFECTIVE_SWITHES;PROFILED_VALUE;ON_TRIGGER;"
    scale_factor = float(modelconf.clk_period) / float(config.genconf.std_clk_period)
    for fconfig in config.injector.fault_model:
        #Select macrocells(targets) of the types specified in the faultload configuration
        nodetree = ET.parse(os.path.join(modelconf.work_dir, toolconf.injnode_list)).getroot()
        inj_nodes = ConfigNodes(modelconf.label, nodetree)
        
        nodelist = inj_nodes.get_all_by_typelist(fconfig.target_logic)
        if fconfig.sample_size > 0:
            buf = []            
            for r in range(fconfig.sample_size):
                buf.append( nodelist[random.randint(0, len(nodelist)-1)] )
            nodelist = buf
        print("\n" + fconfig.model + ", " + str(fconfig.target_logic) + ", targets number: " + str(len(nodelist)))
                    


        #Generate scripts
        os.chdir(os.path.join(modelconf.work_dir, toolconf.script_dir))
        for i in range(0, fconfig.experiments_per_target, 1):
            random.seed(fconfig.rand_seed + i)
            
            h_start_time = fconfig.time_start + (fconfig.increment_time_step * i)
            h_end_time   = fconfig.time_end   + (fconfig.increment_time_step * i)
            #Injection Time to absolute units (ns)
            if fconfig.time_mode == TimeModes.Relative:
                inj_start_time = float(config.genconf.std_workload_time) * h_start_time * scale_factor
                inj_stop_time  = float(config.genconf.std_workload_time) * h_end_time * scale_factor
            elif fconfig.time_mode == TimeModes.Absolute:
                inj_start_time = h_start_time * scale_factor
                inj_stop_time  = h_end_time * scale_factor
            elif fconfig.time_mode == TimeModes.ClockCycle:
                inj_start_time = h_start_time * modelconf.clk_period
                inj_stop_time  = h_end_time * modelconf.clk_period
            print "Start time: " + str(inj_start_time) + "\nStop time: " + str(inj_stop_time)
            nonrandom = (inj_stop_time == 0 or inj_stop_time <= inj_start_time)


            prev_desc = ('', random.getstate())
            for instance in nodelist:
                #bypass empty items, maintaining the same rand sequence
                if(instance.type == '__'):
                    random.randint(inj_start_time, inj_stop_time)
                    continue
                #build the list of tuples (inj_case, inj_code, profiling_descriptor)
                inj_code_items = get_injection_code_all(instance, faultdict, fconfig, scale_factor, None)
                #for the instance from the same group as previous one: restore rand state to obtain the same random sequence 
                if(instance.group != '' and instance.group == prev_desc[0]):
                    random.setstate(prev_desc[1])
                else:
                    prev_desc = (instance.group, random.getstate())
                #Export Fault simulation scripts (*.do files)
                for c in inj_code_items:
                    str_index = str("%06d" % (script_index))
                    inj_script = ""
                    if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
                        if config.platform == Platforms.Grid or config.platform == Platforms.GridLight:
                            inj_script = "set PTH $::env(TMP)\nset WLFFilename ${{PTH}}/WLFSET_{0}.wlf\nset WLFDeleteOnQuit 1".format(str_index)
                            inj_script += "\ntranscript file ${{PTH}}/log_{0}_nodename.txt".format(str_index)
                        else:
                            inj_script = "set WLFFilename {0}/WLFSET_{1}.wlf\nset WLFFileLock 0\nset WLFDeleteOnQuit 1".format(toolconf.dataset_dir, str_index)
                            inj_script += "\ntranscript file " + toolconf.log_dir +"/log_" + str_index + "_nodename.txt"
                    inj_time = []
                    for t in range(fconfig.injections_per_experiment):
                        inj_time.append(inj_start_time if nonrandom else random.randint(int(inj_start_time), int(inj_stop_time)))
                    inj_time.sort()

                    if fconfig.trigger_expression == '':    #time-driven injection
                        #find closest checkpoint
                        checkpoint_linked = 0
                        for ct in checkpointlist:
                            if(ct < inj_time[0]):
                                checkpoint_linked = ct
                        inj_script += "\nset ExecTime " + str(int(config.genconf.std_workload_time*scale_factor)-int(checkpoint_linked)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                             inj_script += str(int(t)-int(checkpoint_linked)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nforeach i $InjTime {\n\twhen \"\\$now >= $i\" {\n\t\tputs \"Time: $::now: Injection of " + fconfig.model + " Into {0}".format(instance.name) + "\"\n\t\t" + c[1] + "\n\t}\n}"
                        fname = "fault_" + str_index + "__checkpoint_" + str(checkpoint_linked) + ".do"
                    else:       #event-driven injection (on trigger expression)
                        inj_script += "\nset ExecTime " + str(int(config.genconf.std_workload_time*scale_factor)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                             inj_script += str(int(t)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nwhen {" + fconfig.trigger_expression + "} {\n\tforeach i $InjTime {\n\t\twhen \"\\$now >= $i\" {\n\t\t\tputs \"Time: $::now: Injection of " + fconfig.model + " Into {0}".format(instance.name) +"\"\n\t\t\t" + c[1] + "\n\t\t}\n\t}\n}"
                        fname = "fault_" + str_index + "__checkpoint_0" + ".do"
                    inj_script += ("\nwhen \"\$now >= $ExecTime && {0}'event && {1} == 1\"".format(config.genconf.clk_signal, config.genconf.clk_signal)  if config.genconf.clk_signal != '' else "\nwhen \"\$now >= $ExecTime\"") + " { force -freeze "+ (toolconf.finish_flag if config.genconf.finish_flag == '' else config.genconf.finish_flag) + " 1 }"
                    if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
                        inj_script += "\n\ndo " + toolconf.list_init_file
                    inj_script +=  "\nrun [scaleTime $ExecTime 1.05]"
                    dumpfilename = "dump_" + str_index + "_nodename.lst"
                    inj_script += "\nwrite list " + toolconf.result_dir + '/' + dumpfilename
                    if config.injector.checkpont_mode == CheckpointModes.ColdRestore:
                        inj_script += "\nquit\n"                    

                    robust_file_write(fname, inj_script)
                    sys.stdout.write('Stored script: %6d\r' % (script_index))
                    sys.stdout.flush() 
                    fdesclog_content += "\n" + str(script_index) + ";" + dumpfilename + ";" + c[0] + ";" + instance.type + ";" + fconfig.model + fconfig.modifier + ";" + fconfig.forced_value + ";" + str(fconfig.duration) + ";" + str(inj_time[0]) + ";" + str(int(config.genconf.std_workload_time*scale_factor)-int(inj_time[0])) 
                    if c[2] != None:
                        fdesclog_content += ';{0:.2f};{1:d};{2:s};'.format(c[2].total_time, c[2].effective_switches, c[2].profiled_value)
                    else:
                        fdesclog_content += ';None;None;None;'
                    script_index += 1
                    fdesclog_content += fconfig.trigger_expression.replace(';',' ').replace('&apos','')+';'

    robust_file_write(os.path.join(modelconf.work_dir, toolconf.result_dir, toolconf.exp_desc_file), fdesclog_content)    
    return(script_index)





#----------------------------------------------------------------------------------------------------------------------------------
# Returns the list of fault injection scripts for each injection case in the dictionary applicable to tuple {INSTANCE, FCONFIG}
#-----------------------------------------------------------------------------------------------------------------------------------

def get_injection_code_all(instance, faultdict, fconfig, scale_factor, PresimRes = None):
    res = []
    duration = fconfig.duration * scale_factor
    faultdescriptor = faultdict.get_descriptor(fconfig.model, instance.type)
    if(faultdescriptor == None):
        raw_input('Error: no descriptor found in dictionary for fault model: ' + str(fconfig.model) + '::' + instance.type)
    else:
        for injection_rule in faultdescriptor.injection_rules:
            for injection_case in injection_rule.injection_cases:
                #check injection_case.condition
                #build list of indexes - one script per index, max 2 dimensions, index for high dimension may come from profiling
                indset = []
                if PresimRes != None:
                    for index_high in PresimRes.get(instance.type, instance.name, injection_case.label).address_descriptors:
                        if len(injection_case.dimensions) > 1:
                            for index_low in range(int(injection_case.dimensions[1].low_index), int(injection_case.dimensions[1].high_index)+1, 1):
                                indset.append( ('('+str(index_high.address)+')' + '('+str(index_low)+')' , index_high) )    
                        else:
                            indset.append( ('('+str(index_high.address)+')', index_high ))
                elif len(injection_case.dimensions) > 0:
                    for index_high in range(int(injection_case.dimensions[0].low_index), int(injection_case.dimensions[0].high_index)+1, 1):
                        if len(injection_case.dimensions) > 1:
                            for index_low in range(int(injection_case.dimensions[1].low_index), int(injection_case.dimensions[1].high_index)+1, 1):
                                indset.append( ('('+str(index_high.address)+')' + '('+str(index_low)+')', None) )
                        else:
                            indset.append( ('('+str(index_high.address)+')', None) )

                #replace placeholders
                inj_code = injection_rule.code_pattern.replace('#PATH', instance.name).replace('#FORCEDVALUE', fconfig.forced_value)
                for node in injection_case.nodes:
                    inj_code = inj_code.replace(node.placeholder, node.nodename_pattern)
                #
                if len(indset) == 0:
                    res.append((instance.name + "/" + injection_case.label, inj_code, None))
                else:
                    for index in indset:
                        res.append((instance.name + "/" + injection_case.label + index[0], inj_code.replace('#DIM', index[0]), index[1]))
    return(res)
