# Exports HTML-formatted fault injection reports
# Exports web-based interface to query and visualize fault injection results
# ---------------------------------------------------------------------------------------------
# Author: Ilya Tuzov, Universitat Politecnica de Valencia                                     |
# Licensed under the MIT license (https://github.com/IlyaTuzov/DAVOS/blob/master/LICENSE.txt) |
# ---------------------------------------------------------------------------------------------
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
import ast
from Davos_Generic import *
from Datamanager import *


failuremodes_alias = dict([('M', 'Masked_Fault'), ('L', 'Latent_Fault'), ('S', 'Signalled_Failure'), ('C', 'Silent_Data_Corruption')])
attach_css = ['markupstyle.css']
attach_script = ['../jquery.min.js', 'xscript.js']

def build_report(config, toolconf, datamodel):
    if datamodel == None:
        datamodel = DataModel()
        datamodel.ConnectDatabase( config.get_DBfilepath(False), config.get_DBfilepath(True) )
        datamodel.RestoreHDLModels(config.parconf)
        datamodel.RestoreEntity(DataDescriptors.InjTarget)
    if not os.path.exists(config.report_dir):
        os.makedirs(config.report_dir)
    copy_all_files(os.path.join(config.call_dir,'UserInterface/SBFI'), config.report_dir)
    copy_all_files(os.path.join(config.call_dir,'UserInterface/libs'), os.path.join(config.report_dir, 'libs'))
    shutil.copy(os.path.join(config.call_dir, config.file), os.path.join(config.report_dir, 'config.xml'))
    build_querypage(config, toolconf, datamodel)
    compute_stat(config, toolconf, datamodel)
    build_summary_page(config, toolconf, datamodel)


def build_querypage(config, toolconf, datamodel):    
    with open(os.path.join(config.report_dir,'query.html'),'r+') as f:
        content = f.read()
        f.seek(0)

        buf = ''
        for c in datamodel.dbhelper.get_distinct('Label', 'Models', True):
            buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
        content = content.replace('_#qmodel', buf + '\n\t<option value=\"\">ANY</option>')

        buf = ''
        for c in datamodel.dbhelper.get_distinct('FaultModel', 'Injections', True):
            buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
        content = content.replace('_#qfaultmodel', buf + '\n\t<option value=\"\">ANY</option>')

        buf = ''
        for c in datamodel.dbhelper.get_distinct('InjectionCase', 'Targets', True):
            buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
        content = content.replace('_#qinjectioncase', buf + '\n\t<option value=\"\">ANY</option>')

        buf = ''
        for c in datamodel.dbhelper.get_distinct('ForcedValue', 'Injections', True):
            buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
        content = content.replace('_#qforcedvalue', buf + '\n\t<option value=\"\">ANY</option>')

        buf = '\n\t<option value=\"\">ANY</option>'
        for c in [('M', 'Masked_Fault'), ('L', 'Latent_Fault'), ('S', 'Signalled_Failure'), ('C', 'Silent_Data_Corruption')]: buf += '\n\t<option value=\"' + str(c[1]) + '\">'+ str(c[1]) + '</option>'
        content = content.replace('_#qfailuremode', buf)

        buf = ''
        for c in datamodel.dbhelper.get_distinct('Macrocell', 'Targets', True):
            buf += '\n\t<option value=\"' + str(c) + '\">'+ str(c) + '</option>'
        content = content.replace('_#qinstancetype', '\n\t<option value=\"\">ANY</option>\n\t' + buf)

        eind = datamodel.dbhelper.get_distinct('ID', 'Injections', True)
        content = content.replace('_#qeind', str(eind[0]) + ' : ' + str(eind[-1]))
        content = content.replace('_#qmaxitems', str(len(eind)))

        f.write(content)
        f.truncate()


def compute_stat(config, toolconf, datamodel):
    faultmodels = datamodel.dbhelper.get_distinct('FaultModel', 'Injections', True)
    failuremodes = datamodel.dbhelper.get_distinct('FailureMode', 'Injections', True)
    macrocells = datamodel.dbhelper.get_distinct('Macrocell', 'Targets', True)
    if '' in failuremodes: failuremodes.remove('')
    for hm in datamodel.HdlModel_lst:
        injection_stat = dict()
        for mc in macrocells:
            for fault_model in faultmodels:
                fmodestat = dict()
                total = float(0)
                latency = float(0)
                for failure_mode in failuremodes:
                    query = """ SELECT COUNT(*), SUM(I.FaultToFailureLatency)
                                FROM Injections I
                                JOIN Models M ON I.ModelID = M.ID
                                JOIN Targets T ON I.TargetID = T.ID
                                WHERE I.Status != \"E\" AND M.Label = \"{0}\" AND T.Macrocell = \"{1}\" AND I.FaultModel = \"{2}\" AND I.FailureMode = \"{3}\" 
                            """.format(hm.Label, str(mc), str(fault_model), str(failure_mode))
                    val = datamodel.dbhelper.execute_for_result(query, None)
                    if val:
                        if int(val[0][0]) > 0:
                            fmodestat['Abs_'+str(failure_mode)] = int(val[0][0])
                            total += float(val[0][0])
                            latency += float(val[0][1])
                if len(fmodestat.keys()) > 0:
                    keys = fmodestat.keys()
                    abs_failures = 0
                    if 'Abs_C' in fmodestat: abs_failures += fmodestat['Abs_C']
                    if 'Abs_S' in fmodestat: abs_failures += fmodestat['Abs_S']
                    fmodestat['Latency'] = 0 if abs_failures == 0 else (latency / abs_failures)
                    fmodestat['Latency_Rel'] = fmodestat['Latency'] / hm.Metrics['ClockPeriod']
                    for k in keys:                        
                        fmodestat[k.replace('Abs','Rate')]=100.0*fmodestat[k]/total
                    if str(mc) in injection_stat:
                        stat_mc = injection_stat[str(mc)]
                    else:
                        stat_mc = dict()
                        injection_stat[str(mc)] = stat_mc
                    stat_mc[str(fault_model)] = fmodestat
                val = datamodel.dbhelper.execute_for_result("SELECT COUNT(*) FROM Injections I JOIN Models M ON I.ModelID = M.ID JOIN Targets T ON I.TargetID = T.ID WHERE I.Status = \"H\" AND M.Label = \"{0}\" AND T.Macrocell = \"{1}\" AND I.FaultModel = \"{2}\" ".format(hm.Label, str(mc), str(fault_model)), None)
                fmodestat['Model_Hang'] = int(val[0][0])
                val = datamodel.dbhelper.execute_for_result("SELECT COUNT(*) FROM Injections I JOIN Models M ON I.ModelID = M.ID JOIN Targets T ON I.TargetID = T.ID WHERE I.Status = \"E\" AND M.Label = \"{0}\" AND T.Macrocell = \"{1}\" AND I.FaultModel = \"{2}\" ".format(hm.Label, str(mc), str(fault_model)), None)
                fmodestat['Incomplete_Absent_Dumps'] = int(val[0][0])
        hm.Metrics['Injectionstat'] = injection_stat
    datamodel.SaveHdlModels()

def normalize_label(lbl):
    for k,v in failuremodes_alias.iteritems():
        if lbl.find('Abs_'+k) >= 0: return(lbl.replace('Abs_' + k, 'Abs_' + v))
        elif lbl.find('Rate_'+k) >= 0: return(lbl.replace('Rate_' + k, 'Rate_' + v + ' (%)'))
    return(lbl)


def build_summary_page(config, toolconf, datamodel):
    logpage = HtmlPage("summary.html")
    logpage.css_file = attach_css[0]
    for a in attach_script:
        logpage.js_files.append(a)
    faultmodels = datamodel.dbhelper.get_distinct('FaultModel', 'Injections', True)
    failuremodes = datamodel.dbhelper.get_distinct('FailureMode', 'Injections', True)    
    if '' in failuremodes: failuremodes.remove('')
    labels = []
    for fault_model in faultmodels:
        fm_stat = dict()
        for hm in datamodel.HdlModel_lst:
            injection_stat = dict()
            total = float(0)
            latency = float(0)
            for failure_mode in failuremodes:
                query = """ SELECT COUNT(*), SUM(I.FaultToFailureLatency)
                            FROM Injections I
                            JOIN Models M ON I.ModelID = M.ID
                            WHERE I.Status != \"E\" AND M.Label = \"{0}\"  AND I.FaultModel = \"{1}\" AND I.FailureMode = \"{2}\" 
                        """.format(hm.Label, str(fault_model), str(failure_mode))
                val = datamodel.dbhelper.execute_for_result(query, None)
                if int(val[0][0]) > 0:
                    injection_stat['Abs_'+str(failure_mode)] = int(val[0][0])
                    total += float(val[0][0])
                    latency += float(val[0][1])
            if len(injection_stat.keys()) > 0:
                keys = injection_stat.keys()
                abs_failures = 0
                if 'Abs_C' in injection_stat: abs_failures += injection_stat['Abs_C']
                if 'Abs_S' in injection_stat: abs_failures += injection_stat['Abs_S']
                injection_stat['Latency'] = 0 if abs_failures == 0 else (latency / abs_failures)
                injection_stat['Latency_Rel'] = injection_stat['Latency'] / hm.Metrics['ClockPeriod']
                for k in keys:                        
                    injection_stat[k.replace('Abs','Rate')]=100.0*injection_stat[k]/total
            val = datamodel.dbhelper.execute_for_result("SELECT COUNT(*) FROM Injections I JOIN Models M ON I.ModelID = M.ID  WHERE I.Status = \"H\" AND M.Label = \"{0}\" AND I.FaultModel = \"{1}\" ".format(hm.Label, str(fault_model)), None)
            injection_stat['Model_Hang'] = int(val[0][0])
            val = datamodel.dbhelper.execute_for_result("SELECT COUNT(*) FROM Injections I JOIN Models M ON I.ModelID = M.ID  WHERE I.Status = \"E\" AND M.Label = \"{0}\" AND I.FaultModel = \"{1}\" ".format(hm.Label, str(fault_model)), None)
            injection_stat['Incomplete_Absent_Dumps'] = int(val[0][0])
            fm_stat[hm.Label] = injection_stat
            if labels == []:
                labels = injection_stat.keys()
                labels.sort()
        stat_table = HtmlTable(len(fm_stat.keys()), len(labels)+1, str(fault_model) + " : Statistics")
        stat_table.set_label(0, 'HDL_Model')
        for l in range(len(labels)):
            stat_table.set_label(l+1, normalize_label(labels[l]))
        row = 0
        for k, stat in fm_stat.iteritems():
            stat_table.put_data(row, 0, str(k))
            for l in range(len(labels)):
                data = ("{0:.4f}".format(stat[labels[l]]) if type(stat[labels[l]]) is float else str(stat[labels[l]])) if (labels[l] in stat) else "0.0"
                stat_table.put_data(row, l+1, data)
            row += 1
        logpage.put_data(stat_table.to_string() + "<hr><br>")
    logpage.write_to_file(os.path.join(config.report_dir,'summary.html'))





