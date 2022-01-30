# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Vendor-dependent functions, linked to handlers in phases of implementation flow (configuration file)
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import subprocess
import shutil
import string
import HDLSpecific
from sys import platform

        #GENERIC METHODS to support ImplementationFlow

#Returns options setting for given implementation phase  (dictionary)
#Replaces default setting for each option with actual value from factorial configuiration (input list)
def get_option_setting(phase, factorial_setting):
    res = dict()
    for c in phase.options:        
        res[c.name] = c.default
        for f in factorial_setting:
            if phase.name == f.Phase and c.name == f.OptionName:
                res[f.OptionName] = f.OptionVal
    res_min = []
    for f in factorial_setting:
        if phase.name == f.Phase:
            res_min.append([f.OptionName, f.OptionVal, f.FactorName])

    return(res, res_min)


def option_to_str(key, val):
    res = ''
    if val.find('!-') < 0:
        if key.replace(' ', '').replace('\t','') != "":
            res += " -" + key
            if val.find('!+') < 0: res += " " + val
        else:
            res += " " + val
    return(res)





    #FOLLOWING METHODS ARE DEFINED FOR PARTICULAR TOOLKIT       
    #XILINX ISE 

#phase -  instance of ImplementationPhase 
#config - instance of ExperiementalDesignConfiguration 
#model -  instance of HDLModelDescriptor 
def XilinxIseBuildScript(phase, config, model):
    customparam = config.design_genconf.custom_parameters
    setting = get_option_setting(phase, model.Factors)

    if phase.name == 'Synthesis':
        phase.resultfiles.append('{0}.ngc'.format(customparam['top_design_unit']))
        phase.reportfile = '{0}/{1}.syr'.format(config.design_genconf.log_dir, customparam['top_design_unit'])
        if not 'xst_file_name' in customparam: customparam['xst_file_name'] = '{0}.xst'.format(customparam['top_design_unit'])
        with open(os.path.normpath(os.path.join(model.ModelPath, customparam['xst_file_name'])), 'w') as f:
            f.write('\nrun')
            for k, v in setting.iteritems():                
                f.write('\n-{0} {1}'.format(k, v))       
            for k, v in { 'p': customparam['device'], 'ifn': customparam['ifn'], 'ofn': customparam['top_design_unit'], 'top': customparam['top_design_unit'] }.iteritems():
                f.write('\n-{0} {1}'.format(k, v))
        res = "xst -intstyle {0} -ifn \"./{1}\" -ofn \"{2}\" > {3}".format(
            customparam['intstyle'], 
            customparam['xst_file_name'], 
            phase.reportfile, 
            config.design_genconf.log_dir+'/'+phase.logfile)        

    elif phase.name == 'Translate':
        phase.resultfiles.append('{0}.ngd'.format(customparam['top_design_unit']))
        phase.reportfile = '{0}.bld'.format(customparam['top_design_unit'])
        res = "ngdbuild -intstyle {0} {1} {2} {3}.ngc {4}.ngd > {5}".format(
            customparam['intstyle'], 
            ' '.join([option_to_str(k,v) for k,v in setting.iteritems()]),  
            '' if (config.design_genconf.constraint_file==None or config.design_genconf.constraint_file == '') else '-uc ' + config.design_genconf.constraint_file, 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name == 'Map':
        phase.resultfiles.append('{0}_map.ncd'.format(customparam['top_design_unit']))
        phase.reportfile = '{0}_map.mrp'.format(customparam['top_design_unit'])
        if not 'ise_path' in customparam:
            tool = 'map'
        else:
            if platform == 'linux' or platform == 'linux2':
                tool = os.path.join(customparam['ise_path'], 'ISE/bin/lin64/map')
            elif platform == 'win32' or platform == 'win64' or platform =='cygwin':
                tool = os.path.join(customparam['ise_path'], 'ISE/bin/nt64/map.exe')
        res = tool + " -intstyle {0} {1} -o {2}_map.ncd {3}.ngd {4}.pcf > {5}".format(
            customparam['intstyle'], 
            ' '.join([option_to_str(k,v) for k,v in setting.iteritems()]), 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name == 'Par':
        phase.resultfiles.append('{0}.ncd'.format(customparam['top_design_unit']))
        phase.reportfile = '{0}.par'.format(customparam['top_design_unit'])
        if not 'ise_path' in customparam:
            tool = 'par'
        else:
            if platform == 'linux' or platform == 'linux2':
                tool = os.path.join(customparam['ise_path'], 'ISE/bin/lin64/par')
            elif platform == 'win32' or platform == 'win64' or platform =='cygwin':
                tool = os.path.join(customparam['ise_path'], 'ISE/bin/nt64/par.exe')
        res = "{0} -intstyle {1} {2} {3}_map.ncd {4}.ncd {5}.pcf > {6}".format( 
            tool + ' -w ', 
            customparam['intstyle'], 
            ' '.join([option_to_str(k,v) for k,v in setting.iteritems()]), 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name == 'Trace':
        phase.reportfile = config.design_genconf.log_dir+'/timing.twr'
        res = "trce -intstyle " + customparam['intstyle'] + " -v 3 -n 3 -s " + customparam['speed_grade'] + " -fastpaths -xml " + customparam['top_design_unit'] + ".twx " + customparam['top_design_unit'] + ".ncd -o " + phase.reportfile + " " + customparam['top_design_unit'] + ".pcf" + ('' if (config.design_genconf.constraint_file==None or config.design_genconf.constraint_file == '') else ' -ucf ' + config.design_genconf.constraint_file) + ' > ' + config.design_genconf.log_dir+'/'+phase.logfile      

    elif phase.name == 'BuildNetlist':
        phase.resultfiles.append(config.design_genconf.netlist_dir + '/par/_timesim.vhd')
        res = "netgen -intstyle {0} {1} -dir {2}/par -pcf {3}.pcf -tb  -insert_pp_buffers true -sim {4}.ncd {5} > {6}".format(
            customparam['intstyle'], 
            customparam['basic_netgen_options'], 
            config.design_genconf.netlist_dir, 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            '_timesim.vhd', 
            config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name== 'PowerAnalysisDefault':
        phase.reportfile = '{0}/estimated_power_{1}.pwr'.format(config.design_genconf.log_dir, customparam['top_design_unit'])
        res = "xpwr -intstyle {0} {1}.ncd {2}.pcf -o {3} > {4}".format(customparam['intstyle'], customparam['top_design_unit'], customparam['top_design_unit'], phase.reportfile, config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name == 'SimCompile':
        HDLSpecific.configure_testbench_vhdl(config, model)
        #Compile simulation file
        if platform == 'linux' or platform == 'linux2':
            customparam['simexecutable'] = '{0}_simexec'.format(customparam['top_design_unit'])
        elif platform == 'win32' or platform == 'win64' or platform =='cygwin':
            customparam['simexecutable'] = '{0}.exe'.format(customparam['top_design_unit'])
        res = "fuse -intstyle {0}  -mt off -incremental -lib simprims_ver -lib unisims_ver -lib unimacro_ver -lib xilinxcorelib_ver -lib secureip -o ./{1}  -prj ./{2}  work.{3} > {4}".format(
            customparam['intstyle'], 
            customparam['simexecutable'], 
            config.design_genconf.sim_project_file, 
            config.design_genconf.testbench_top_unit, 
            config.design_genconf.log_dir+'/'+phase.logfile)

    elif phase.name == 'SimulateSwitchingActivity':
        customparam['simsaif'] = '{0}.saif'.format(customparam['top_design_unit'])
        customparam['simcmd'] = '{0}.cmd'.format(customparam['top_design_unit'])
        #create workload batch script
        period = GetClockPeriod(config, model)
        scale_factor = float(config.design_genconf.std_clock_period) / period
        with open(customparam['simcmd'], 'w') as f:
            f.write("sdfanno -min " +  config.design_genconf.netlist_dir + "/par/_timesim.sdf" + " -root /" + config.design_genconf.testbench_top_unit + "/" + config.design_genconf.uut_root)
            f.write('\nonerror {resume}\nrun 0 ns\nrestart')
            f.write("\nrun " + str(int(scale_factor * config.design_genconf.std_start_time)) + " ns")
            f.write("\nsaif open -scope /{0}/{1} -file {2} -allnets".format(config.design_genconf.testbench_top_unit, config.design_genconf.uut_root, customparam['simsaif']))
            f.write("\nrun {0} ns".format(int(scale_factor * config.design_genconf.std_observation_time)))
            f.write("\nsaif close;\nexit\n")
        #create top script to run
        if platform == 'win32' or platform == 'win64':
            res = os.path.join(customparam['ise_path'], 'settings64.bat') + ' && ' + customparam['simexecutable'] + " -intstyle " + customparam['intstyle']
        else:
            res = "./"+customparam['simexecutable']+" -intstyle " + customparam['intstyle']
        if config.design_genconf.custom_parameters['isim_gui'] == "on":
            res += " -gui"
            if config.design_genconf.custom_parameters['waveform_file'] != "":
                res += " -view " + config.design_genconf.custom_parameters['waveform_file']
        res += " -tclbatch ./" + customparam['simcmd']        
        res += " -wdb {0}.wdb".format(model.Label)
        res += " > " +  config.design_genconf.log_dir+'/'+phase.logfile

    elif phase.name == 'PowerAnalysisSimulated':
        phase.reportfile = '{0}/simulated_power_{1}.pwr'.format(config.design_genconf.log_dir, customparam['top_design_unit'])
        res = "xpwr -v -intstyle {0} -ol std {1}.ncd {2}.pcf -s {3} -o {4} > {5}".format(
            customparam['intstyle'], 
            customparam['top_design_unit'], 
            customparam['top_design_unit'], 
            customparam['simsaif'],
            phase.reportfile, 
            config.design_genconf.log_dir+'/'+phase.logfile)

    return(res)



#Returns: True - if everything ok, False otherwise (retry/rerun the phase)
def XilinxCheckPostcondition(phase, config, model):
    #check that all expected result files were created
    for r in phase.resultfiles:
        if not os.path.exists(os.path.abspath(os.path.join(model.ModelPath, r))):
            return(False)
    #check report file for errors (number of errors expected to be zero)
    if phase.reportfile != '':
        if os.path.isfile(os.path.abspath(os.path.join(model.ModelPath, phase.reportfile))):
            with open(os.path.abspath(os.path.join(model.ModelPath, phase.reportfile)), 'r') as f:
                content = f.read()
                match = re.findall("Number of error messages.*?([0-9]+)", content) + re.findall("Number of errors.*?([0-9]+)", content)
                if len(match) > 0:
                    err_num = int(match[0])
                    if err_num > 0:
                        return(False)
        else:
            return(False)
    #check the log file for errors (ERROR: keyword)
    if os.path.isfile(os.path.abspath(os.path.join(config.design_genconf.log_dir, phase.logfile))):
        with open(os.path.abspath(os.path.join(config.design_genconf.log_dir, phase.logfile)), 'r') as f:
            content = f.read()
            if content.find('ERROR:') >= 0:
                return(False)
    return(True)
    
   



def XilinxCheckTimingSatisfied(phase, config, model):
    for p in config.flow.get_phase_chain():
        if p.name.lower() == 'trace':
            if os.path.isfile(phase.reportfile):
                with open(phase.reportfile, 'r') as f:
                    content = f.read()
                if content.find("All constraints were met") >= 0:
                    return(True)
                else:
                    return(False)
            else:
                return(False)


def VivadoCheckTimingSatisfied(phase, config, model):
    for p in config.flow.get_phase_chain():
        if p.name == 'Implementation':
            if os.path.isfile(phase.reportfile):
                with open(phase.reportfile, 'r') as f:
                    content = f.read()
                if content.find("All user specified timing constraints are met") >= 0:
                    return(True)
                else:
                    return(False)
            else:
                return(False)



def GetClockPeriod(config, model):
    for p in config.flow.get_phase_chain():
        if p.name.lower() == 'trace':
            with open(p.reportfile, 'r') as f:
                content = f.read()
            match = re.findall("Minimum period:.*?([0-9]+\.?[0-9]*)", content)
            if len(match) > 0: 
                return(float(match[0]))
    return(None)


def GetResultLabels():
    return(['FREQUENCY', 'CLK_PERIOD', 'POWER_DYNAMIC', 'POWER_PL', 'POWER_STATIC', 'UTIL_SLICE', 'UTIL_FF', 'UTIL_LUT', 'UTIL_RAMB', 'UTIL_DSP'])

#After completion of all phases this function should update at least two properties of the model:
#model.Metrics['Implprop'] --> ['ClockPeriod'], ['Frequency']
def XilinxIseRetrieveResults(phase, config, model):
    num_point_pattern = "[0-9]+\.?[0-9]*"
    num_comma_pattern = "[0-9]+\,?[0-9]*"   
    res = dict()
    if phase.reportfile != '' and os.path.isfile(phase.reportfile):
        with open(phase.reportfile, 'r') as f:
            content = f.read()
        try:
            if phase.name == 'Par':
                match = re.findall("Number of Slice LUTs:.*?%", content)[0]
                res['UTIL_LUT'] = int(re.findall(num_comma_pattern, match)[0].replace(',',''))
                match = re.findall("Number of Slice Registers:.*?%", content)[0]
                res['UTIL_FF'] = int(re.findall(num_comma_pattern, match)[0].replace(',',''))
                match = re.findall("Number of occupied Slices:.*?%", content)[0]
                res['UTIL_SLICE']  = int(re.findall(num_comma_pattern, match)[0].replace(',',''))    
                match = re.findall("Number of RAMB.*?:(.*?)%", content)
                res['UTIL_RAMB'] = 0
                for c in match:
                    res['UTIL_RAMB']  += int(re.findall(num_comma_pattern, c)[0].replace(',',''))
                match = re.findall("Number of DSP.*?:(.*?)%", content)
                res['UTIL_DSP'] = 0
                for c in match:
                    res['UTIL_DSP']  += int(re.findall(num_comma_pattern, c)[0].replace(',',''))

            elif phase.name == 'Trace':
                match = re.findall("Minimum period:.*?\{", content)[0]
                res['CLK_PERIOD'] = float(re.findall(num_point_pattern, match)[0])
                match = re.findall("\(Maximum frequency:.*?\)", content)[0]
                res['FREQUENCY'] = float(re.findall(num_point_pattern, match)[0])
                model.Metrics['ClockPeriod'] = res['CLK_PERIOD']
                model.Metrics['Frequency'] = res['FREQUENCY']

            elif phase.name == 'PowerAnalysisDefault' or phase.name == 'PowerAnalysisSimulated':
                match = re.findall("Supply Power \(mW\).+", content)[0]
                power_list = re.findall(num_point_pattern, match)
                res['POWER_DYNAMIC'] = float(power_list[1])
                res['POWER_STATIC']  = float(power_list[2])

        except IndexError:
            print 'File Parse Error (file incomplete): get_implementation_properties: ' + phase.resultfile
            return(res)
    return(res)





def VivadoBuildScript(phase, config, model):
    customparam = config.design_genconf.custom_parameters
    setting, setting_min = get_option_setting(phase, model.Factors)

    if phase.name == 'Synthesis':
        with open(os.path.join(config.design_genconf.design_dir, config.design_genconf.template_dir, config.design_genconf.custom_parameters['SynthesisScriptTemplate']), 'r') as f:
            script = f.read()
        script = script.replace(phase.constraints_to_export[0].placeholder, str(phase.constraints_to_export[0].current_value))
        options = []
        #for i in sorted(setting.keys()):
        #    options.append("set_property -name \"{0}\" -value \"{1}\" -objects $obj".format(str(i), str(setting[i])))
        for i in setting_min:
            options.append("catch {{set_property -name \"{0}\" -value \"{1}\" -objects $obj}} err".format(str(i[0]), str(i[1])))
        script = script.replace('#SETTING', '\n'.join(options))
        with open(config.design_genconf.custom_parameters['SynthesisScriptTemplate'], 'w') as f: 
            f.write(script)
        res = 'vivado -mode batch -source {0} > {1}'.format(config.design_genconf.custom_parameters['SynthesisScriptTemplate'], config.design_genconf.log_dir+'/'+phase.logfile)

    if phase.name == 'Implementation':
        phase.resultfiles.append('timing.log')
        phase.resultfiles.append('utilization.log')
        phase.resultfiles.append('powerconsumption.pwr')
        phase.reportfile = phase.resultfiles[0]
        with open(os.path.join(config.design_genconf.design_dir, config.design_genconf.template_dir, config.design_genconf.custom_parameters['ImplementationScriptTemplate']), 'r') as f:
            script = f.read()
        options = []
        #for i in sorted(setting.keys()):
        #    options.append("set_property -name \"{0}\" -value \"{1}\" -objects $obj".format(str(i), str(setting[i])))
        for i in setting_min:
            options.append("catch {{set_property -name \"{0}\" -value \"{1}\" -objects $obj}} err".format(str(i[0]), str(i[1])))
        script = script.replace('#SETTING', '\n'.join(options))
        script += '\nreport_timing_summary -file {0}'.format(phase.resultfiles[0])
        script += '\nreport_utilization -file {0}\n'.format(phase.resultfiles[1])
        script += '\nreport_power -file {0}\n'.format(phase.resultfiles[2])
        with open(config.design_genconf.custom_parameters['ImplementationScriptTemplate'], 'w') as f: 
            f.write(script)
        res = 'vivado -mode batch -source {0} > {1}'.format(config.design_genconf.custom_parameters['ImplementationScriptTemplate'], config.design_genconf.log_dir+'/'+phase.logfile)

    if phase.name == 'GenBitstream':
        with open(os.path.join(config.design_genconf.design_dir, config.design_genconf.template_dir, config.design_genconf.custom_parameters['GenBitstreamScriptTemplate']), 'r') as f:
            script = f.read()
        script = script.replace("#EXPORTDIR", str(model.ModelPath.replace('\\','/')))
        with open(config.design_genconf.custom_parameters['GenBitstreamScriptTemplate'], 'w') as f: 
            f.write(script)
        res = 'vivado -mode batch -source {0} > {1}'.format(config.design_genconf.custom_parameters['GenBitstreamScriptTemplate'], config.design_genconf.log_dir+'/'+phase.logfile)


    return(res)



def VivadoRetrieveResults(phase, config, model):
    res = dict()
    try:
        if phase.name == 'Implementation':
            if phase.resultfiles[0] != '' and os.path.isfile(phase.resultfiles[0]):
                with open(phase.resultfiles[0], 'r') as f:
                    content = f.read()
                    match = re.findall('Clock\s*Summary.*?{.*}\s*([0-9]+.?[0-9]*)\s*?([0-9]+.?[0-9]*)', content, re.DOTALL)[0]
                    res['CLK_PERIOD'] = float(match[0])
                    res['FREQUENCY'] = float(match[1])

            if phase.resultfiles[1] != '' and os.path.isfile(phase.resultfiles[1]):
                with open(phase.resultfiles[1], 'r') as f:
                    content = f.read()
                    res['UTIL_LUT'] = int(re.findall("Slice LUTs.*?([0-9]+)", content)[0])
                    res['UTIL_FF'] = int(re.findall("Slice Registers.*?([0-9]+)", content)[0])
                    res['UTIL_BRAM'] = float(re.findall("Block RAM Tile.*?([0-9]+\.?[0-9]*)", content)[0])
                    res['UTIL_DSP'] = float(re.findall("DSPs.*?([0-9]+)", content)[0])

            if phase.resultfiles[2] != '' and os.path.isfile(phase.resultfiles[2]):
                with open(phase.resultfiles[2], 'r') as f:
                    content = f.read()
                    res['POWER_DYNAMIC'] = float(re.findall("Dynamic \(W\).*?([0-9\.]+)", content)[0])
                    res['POWER_PL'] = float(re.findall(config.design_genconf.uut_root+".*?([0-9\.]+)", content)[0])

    except:
        print 'VivadoRetrieveResults error: ' + str(sys.exc_info())
        return(res)
    return(res)


