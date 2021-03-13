# Generic data structures andprocedures of SBFI tool
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
import errno
import traceback


#--------------------------------------------------
# Various generic functions
#-------------------------------------------------  

def remove_delimiters(iline, delimiters=('_','.','/','(',')',':','','[',']')):
    res = iline
    for d in delimiters:
        res = res.replace(d, '')
    return(res)


def copy_all_files(src, dst):
    src_path = os.listdir(src)
    for path in src_path:
         full_src_name = os.path.join(src, path)
         if (os.path.isfile(full_src_name)):
            shutil.copy(full_src_name, dst)
         elif not os.path.exists(os.path.join(dst, path)):
             shutil.copytree(full_src_name,os.path.join(dst, path))
              
             
class Dirstate:
    def __init__(self, i_dir):
        self.s_dir = i_dir
        self.sample_time = datetime.datetime.now().replace(microsecond=0)
        self.nfiles = nfiles = len(os.listdir(self.s_dir))
    
    def update(self):
        self.sample_time = datetime.datetime.now().replace(microsecond=0)
        self.nfiles = nfiles = len(os.listdir(self.s_dir))

    def time_difference_to_sec(self, prev_time):
        delta = self.sample_time - prev_time.sample_time
        ds = (delta.seconds + delta.days * 24 * 3600) 
        return(ds) 



def create_folder(rtdir, nestdir, prefix=''):
    targetpath = os.path.join(rtdir, nestdir)
    renamepath = os.path.join(rtdir, nestdir + "__" + prefix)
    if(not os.path.exists(targetpath)):
        os.mkdir(targetpath)
        print "Created: " + str(targetpath)
    else:
        if(os.listdir(targetpath)!=[] and prefix!=''):
            os.rename(targetpath, renamepath)
            print("RENAMING (non-empty folder): " + str(targetpath) + "  TO  " + str(renamepath))
            os.mkdir(targetpath)
            print "Created: " + str(targetpath)
    return(0)


def check_termination(config_file_path):
    iconfig = os.path.abspath(config_file_path)
    normconfig = iconfig.replace('.xml','_normalized.xml')
    normalize_xml(iconfig, normconfig)    
    tree = ET.parse(normconfig).getroot()
    genconf = tree.findall('fault_injection')[0].findall('task')[0]
    terminate_flag = genconf.get('runtime_terminate')
    if(terminate_flag == "on"):
        return True
    return False
    
def create_restricted_file(filename):
    if(not os.path.exists(filename)):
      f = open(filename, "w")
      f.close()
    os.chmod(filename, stat.S_IREAD)
    return(0)


def how_old_file(fname):
    if(not os.path.exists(fname)):
        print("how_old_file error: no file found" + str(fname))
        return(0)
    d = os.path.getmtime(fname)
    t = datetime.datetime.fromtimestamp(d)
    c = datetime.datetime.now()
    delta = c - t
    ds = (delta.microseconds + (delta.seconds + delta.days * 24 * 3600) * 10**6) / 10**6
    return(ds)


def remove_dir(targetpath):
    if(os.path.exists(targetpath)):
        print("Removing " + targetpath)
        shutil.rmtree(targetpath, ignore_errors=True)


def get_active_proc_number(proclist):
    res = 0
    for p in proclist:
        if(p.poll() is None):
            res += 1
    return(res)




def normalize_xml(infilename, outfilename):
    infile = open(infilename,'r')
    content = infile.read()
    infile.close()
    #append here normalization code
    content = re.sub(r'&', '&amp;',content)
    outfile = open(outfilename,'w')
    outfile.write(content)
    outfile.close()


def pure_node_name(nodename, num=2):
    res = nodename
    items = nodename.split('/')
    z = len(items)
    if (z-num >= 0):
        res = ""
        for i in range(z-num, z, 1):
            res += "_"+items[i]
    return(res)



#----------------------------------------------
# classes for logs and HTML reports
#----------------------------------------------            
class Table:
    def __init__(self, name):
        self.name = name
        self.columns = []
        self.labels = []
  
    def rownum(self):
        if(len(self.columns) > 0):
            return(len(self.columns[0]))
        else:
            return(0)
    
    def colnum(self):
        return(len(self.columns))

    def add_column(self, lbl):
        nrow = []
        for c in range(0, self.rownum(),1):
            nrow.append('')
        self.columns.append(nrow)
        self.labels.append(lbl)
        
    def add_row(self, idata=None):
        if(idata!=None):
            if(len(idata) >= self.colnum()):
                for c in range(0, len(self.columns), 1):
                    self.columns[c].append(idata[c])
            else:
                print "Warning: Building Table - line not complete at add_row(): " + str(len(idata)) + " <> " + str(self.colnum())
        else:
            for c in self.columns:
                c.append("")
                       
    def put(self, row, col, data):
        if( col < len(self.columns) ):
            if( row < len(self.columns[0]) ):
                self.columns[col][row] = data
            else:
                print("Table: "+self.name + " : put data: " + str(data) + " : Row index " + str(row) + " not defined")
        else:
            print("Table: "+self.name + " : put data: " + str(data) + " : Column index " + str(col) + " not defined")
            

    def put_to_last_row(self, col, data):
        self.put(self.rownum()-1, col, data)

    def get(self, row, col):
        if( col < len(self.columns) ):
            if( row < len(self.columns[col]) ):
                return(self.columns[col][row])
            else:
                print("Table: "+self.name + " : put data: " + str(data) + " : Row index " + str(row) + " not defined")
        else:
            print("Table: "+self.name + " : put data: " + str(data) + " : Column index " + str(col) + " not defined")
        return("")    
    
    
    def to_csv(self):
        res = "sep=;\n"
        for l in self.labels:
            res += l+";"
        nc = len(self.columns)
        nr = len(self.columns[0])
        for r in range(0, nr, 1):
            res+="\n"
            for c in range(0, nc, 1):
                res+=str(self.get(r,c))+";"
        return(res)
    
    def snormalize(self, ist):
        if(ist[-1]=="\r" or ist[-1]=="\n"):
            del ist[-1]
        return ist
    
    def build_from_csv(self, fname):
        fdesc = open(fname, 'r')
        content = fdesc.read()
        fdesc.close()
        lines = string.split(content,'\n')
        itemsep = re.findall("sep\s*?=\s*?([;,]+)", lines[0])[0]
        labels = self.snormalize(lines[1].split(itemsep))
        for l in labels:
            self.add_column(l)
        for i in range(2, len(lines), 1):
            c = self.snormalize(lines[i].split(itemsep))
            self.add_row(c)
    
    def to_html_table(self, tname):
        res = HtmlTable(self.rownum(), self.colnum(), tname)
        for c in range(0, len(self.labels),1):
            res.set_label(c, self.labels[c])
        for r in range(0,self.rownum(),1):
            for c in range(0,self.colnum(),1):
                res.put_data(r,c, self.get(r,c))
        return(res)
 


class HtmlTableCell:
    def __init__(self):
        self.hclass = ""
        self.hdata = ""
        
    def to_string(self):
        res = "<td><div class=\"" + self.hclass + "\"><pre>" + self.hdata + "</pre></div></td>"
        return (res)
    
    def set_class(self, nclass):
        self.hclass = nclass
        
    def put_data(self, ndata):
        self.hdata = ndata

class HtmlTableRow:
    def __init__(self, cell_number=1):
        self.cells = []
        for i in range(0, cell_number, 1):
            self.cells.append(HtmlTableCell())
            
    def get_cell(self, index):
        if(index < len(self.cells)):            
            return(self.cells[index])
        print "Incorrect index"
        return None
    
    def put_data(self, icell, idata):
        if(icell < len(self.cells)):
            self.cells[icell].put_data(idata)
    
    def set_class(self, icell, iclass):
        if(icell < len(self.cells)):
            self.cells[icell].set_class(iclass)
    
    def add_cell(self):
        self.cells.append(HtmlTableCell())
        
    def get_size(self):
        return(len(self.cells))
    
    def to_string(self):
        res = "<tr>"
        for c in self.cells:
            res += "\n" + c.to_string()
        res += "</tr>"
        return(res)
    
    
class HtmlTable:
    def __init__(self, nrow=1, ncol=1, icaption=""):
        self.rows = []
        self.labels = []
        self.caption = icaption
        for i in range(0, nrow, 1):
            self.rows.append(HtmlTableRow(ncol))
        for i in range(0, ncol, 1):
            self.labels.append("")
            
    def add_row(self, nrow):
        if(nrow != None):
            self.rows.append(nrow)
        else:
            cnum = self.rows[0].get_size()
            self.rows.append(HtmlTableRow(cnum))
    
    def get_row(self, rownum):
        return(self.rows[rownum])
    
    def add_column(self):
        for r in self.rows:
            r.add_cell()
        self.labels.append("")
    
    def put_data(self, irow, icol, idata):
        if(irow < len(self.rows)):
            self.rows[irow].put_data(icol, idata)
        else:
            print "put_data index error"              
    
    def set_class(self, irow, icol, iclass):
        if(irow < len(self.rows)):
            self.rows[irow].set_class(icol, iclass)
        else:
            print "set_class index error"
            
    def set_label(self, icol, ilabel):
        if(icol < len(self.labels)):
            self.labels[icol] = ilabel
        else:
            print "set_label index error"            
    
    def to_string(self):
        res = "<table border =\"1\">\n<caption>" + self.caption + "</caption><thead>\n<tr>"
        for c in self.labels:
            res += "\n<th><div class = \"title\">" + c + "</div></th>"
        res += "</tr></thead>\n<tbody>"
        for c in self.rows:
            res += "\n" + c.to_string()
        res += "</tbody>\n</table>"
        return(res)
    
    def to_string_no_header(self):
        res = "<table border =\"1\">\n<caption>" + self.caption + "</caption>\n<tbody>"
        for c in self.rows:
            res += "\n" + c.to_string()
        res += "</tbody>\n</table>"
        return(res)
    
        
class HtmlPage:
    def __init__(self, title = ""):
        self.css_file = ""
        self.js_files = []
        self.data_items = []
        self.title = title
    
    def put_data(self, idata):
        self.data_items.append(idata)
        
    def put_comment(self, idata):
        self.put_data("\n<div class = \"comment\">\n" + idata + "\n</div>")
        
    def write_to_file(self, fname):
        content = "<!DOCTYPE HTML>\n<html>\n<head>\n<meta charset=\"utf-8\">"
        content += "\n<title>" + self.title + "</title>"
        for s in self.js_files:
            content += "\n<script type=\"text/javascript\" src=\"" + s + "\"></script>"
        content += "\n<link rel=\"stylesheet\" type=\"text/css\" href=\"" + self.css_file + "\">"
        content += "\n</head>\n<body>"
        for c in self.data_items:
            content += "\n" + c
        content += "\n</body>\n</html>"
        with open(fname, 'w') as hpage:
            hpage.write(content)
            
    
class HtmlRef:
    def __init__(self, href, text):
        self.href = href
        self.text = text
    def to_string(self):
        return( "\n<a href=\"" + self.href + "\">" + self.text + "</a>" )

def resolve_path(root_path, dest_path):
    res = os.path.normpath(os.path.join(root_path, dest_path)) if dest_path.find(':') < 0 else os.path.normpath(dest_path)
    return(res)

def zip_folder(root_path, folder_name):
    os.chdir(root_path)
    print 'Entering folder: ' + root_path
    zip_script = 'zip -r -1 ' + folder_name+'.zip' + ' ' + folder_name + ' > zip.log'
    proc = subprocess.Popen(zip_script, shell=True)
    print 'Compressing folder: ' + zip_script
    proc.wait()


def robust_file_write(fname, content):
    for i in range(0, 100):
        try:
            with open(fname, "w") as fdesc:
                fdesc.write(content)
            statinfo = os.stat(fname)
            if(statinfo.st_size == 0):
                print "robust_file_write: zero-size file error: " + fname + ", retrying"
                continue
        except Exception as e:
            print 'robust_file_write exception ['+ str(e) +'] on file write: ' + fname + ', retrying [attempt ' + str(i) + ']'
            time.sleep(0.001)
            continue
        break

class GenConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.design_type = ""
            self.library_specification = ""
            self.compile_script = ""
            self.run_script = ""
            self.std_clk_period = float(0)
            self.std_rst_delay = int(0)
            self.std_init_time = int(0)
            self.std_workload_time = int(0)  
            self.finish_flag = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.design_type = xnode.get('design_type').lower()
        self.library_specification = xnode.get('library_specification')
        self.compile_script = xnode.get('compile_script')
        self.run_script = xnode.get('run_script')
        self.std_clk_period = float(xnode.get('std_clk_period'))
        self.std_rst_delay = int(xnode.get('std_rst_delay', '0'))
        self.std_init_time = int(xnode.get('std_init_time'))
        self.std_workload_time = int(xnode.get('std_workload_time'))    
        self.finish_flag = xnode.get('finish_flag', '')           
        return(0)

    def to_string(self):
        res = "Generic Config: "
        res+=  "\n\t design_type = " + self.design_type
        res+=  "\n\t library_specification = " + self.library_specification
        res+=  "\n\t compile_script = " + self.compile_script
        res+=  "\n\t run_script = " + self.run_script        
        res+=  "\n\t std_clk_period = " + str(self.std_clk_period)
        res+=  "\n\t std_rst_delay = " + str(self.std_rst_delay)        
        res+=  "\n\t std_init_time = " + str(self.std_init_time)
        res+=  "\n\t std_workload_time = " + str(self.std_workload_time)
        res+=  "\n\t finish_flag = " + str(self.finish_flag)
        return(res)
    
    
class ToolOptions:
    def __init__(self, xnode=None):
        if xnode is None:
            self.script_dir = "./iscripts"
            self.checkpoint_dir = "./icheckpoints"
            self.result_dir = "./iresults"
            self.log_dir = "./ilogs"
            self.code_dir = "./code"
            self.injnode_list = "./code/SimNodes.xml"
            self.list_init_file = "./code/simInitModel.do"
            self.par_lib_path = "./code/ISE_PAR"
            self.reference_file = "reference.lst"
            self.std_start_checkpoint = "startpoint.sim"
            self.archive_tool_script = "zip -r"
            self.rtl_parse_script = "dadse_rtl_nodes.do"
            self.finish_flag = "Sampling/FinishFlag"
        else:
            self.build_from_xml(xnode)            
     
    def build_from_xml(self, xnode):
        self.script_dir = xnode.get('script_dir', "./iscripts")
        self.checkpoint_dir = xnode.get('checkpoint_dir', "./icheckpoints")
        self.result_dir = xnode.get('result_dir', "./iresults")
        self.log_dir = xnode.get('log_dir', "./ilogs")
        self.code_dir = xnode.get('code_dir', "./code")
        self.injnode_list = xnode.get('injnode_list',"./code/SimNodes.xml")
        self.list_init_file = xnode.get('list_init_file', "./code/simInitModel.do")
        self.par_lib_path = xnode.get('par_lib_path',"./code/ISE_PAR")
        self.reference_file = xnode.get('reference_file', "reference.lst")
        self.std_start_checkpoint = xnode.get('std_start_checkpoint', "startpoint.sim")
        self.archive_tool_script = xnode.get('archive_tool_script', "zip -r")
        self.rtl_parse_script = xnode.get('rtl_parse_script', "dadse_rtl_nodes.do")
        self.finish_flag = xnode.get('finish_flag', "Sampling/FinishFlag")
        return(0)
    
    def to_string(self):
        res = "Tool Options:"
        res+=  "\n\t script_dir = " + self.script_dir
        res+=  "\n\t checkpoint_dir = " + self.checkpoint_dir
        res+=  "\n\t result_dir = " + self.result_dir
        res+=  "\n\t log_dir = " + self.log_dir
        res+=  "\n\t injnode_list = " + self.injnode_list
        res+=  "\n\t list_init_file = " + self.list_init_file
        res+=  "\n\t std_start_checkpoint = " + self.std_start_checkpoint
        res+=  "\n\t reference_file = " + self.reference_file
        res+=  "\n\t archive_tool_script = " + self.archive_tool_script
        res+=  "\n\t code_dir = " + self.code_dir
        res+=  "\n\t cpar_lib_path = " + self.par_lib_path
        return(res)
    
    
    
class ParConfig:
    def __init__(self, xnode):
        self.report_dir = ""
        if xnode is None:
            self.relative_path = ""
            self.work_dir = ""
            self.label = ""
            self.compile_options = ""
            self.run_options = ""
            self.clk_period = float(0)
            self.start_from = int(0)
            self.stop_at = int(0)
            self.report_label = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.relative_path = xnode.get('relative_path','on')            
        self.work_dir = xnode.get('work_dir')     
        self.label = xnode.get('label')
        self.compile_options = xnode.get('compile_options', '')
        self.run_options = xnode.get('run_options', '')
        self.clk_period = float(xnode.get('clk_period'))
        buf = xnode.get('start_from', '')
        self.start_from = 0 if buf=='' else int(buf)
        buf = xnode.get('stop_at', '')        
        self.stop_at = 0 if buf=='' else int(buf)
        self.report_label = self.label
        
    def to_string(self):
        res = "Particular Config: "
        res+=  "\n\t relative_path = " + self.relative_path        
        res+=  "\n\t label = " + self.label
        res+=  "\n\t work_dir = " + self.work_dir
        res+=  "\n\t compile_options = " + self.compile_options
        res+=  "\n\t run_options = " + self.run_options
        res+=  "\n\t clk_period = " + str(self.clk_period)
        res+=  "\n\t start_from = " + str(self.start_from)
        res+=  "\n\t stop_at = " + str(self.stop_at)  
        res+=  "\n\t report_dir = " + str(self.report_dir)       
        return(res)
    


class FaultModelConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.model = ""
            self.target_logic = []
            self.profiling = None
            self.experiments_per_target = int(0)
            self.injections_per_experiment = int(0)
            self.time_mode = ""
            self.time_start = float(0)
            self.time_end = float(0)
            self.activity_time_start = float(0)
            self.activity_time_end = float(0)
            self.inactivity_time_start = float(0)
            self.inactivity_time_end = float(0)
            self.forced_value = ""
            self.rand_seed = int(0)
            self.duration = float(0)
            self.modifier = ''
            self.trigger_expression = ''
        else:
            self.build_from_xml(xnode)
                 
    def build_from_xml(self, xnode):
        self.model = xnode.get('model')
        self.target_logic = re.findall('[a-zA-Z0-9_]+', xnode.get('target_logic').lower())
        self.profiling = xnode.get('profiling', '')
        self.experiments_per_target = int(xnode.get('experiments_per_target', '1'))
        self.injections_per_experiment = int(xnode.get('injections_per_experiment', '1'))
        self.time_mode = xnode.get('time_mode', 'relative')
        self.rand_seed = int(xnode.get('rand_seed', '1'))
        self.forced_value = xnode.get('forced_value', '')
        self.duration = float(xnode.get('duration', '0'))
        self.modifier = xnode.get('modifier', '')
        self.trigger_expression = xnode.get('trigger_expression', '')
        self.time_start = float(xnode.get('injection_time_start', '0'))
        self.time_end = float(xnode.get('injection_time_end', '0'))
        self.activity_time_start = float(xnode.get('activity_time_start', '0'))
        self.activity_time_end = float(xnode.get('activity_time_end', '0'))
        self.inactivity_time_start = float(xnode.get('inactivity_time_start', '0'))
        self.inactivity_time_end = float(xnode.get('inactivity_time_end', '0'))
        return(0)
    
    def to_string(self):
        res = "Fault Model Item: "
        res+=  "\n\t model = " + self.model
        res+=  "\n\t target_logic = "
        for c in self.target_logic:
            res += c + ", "
        res+=  "\n\t experiments_per_target = " + str(self.experiments_per_target)
        res+=  "\n\t injections_per_experiment = " + str(self.injections_per_experiment)
        res+=  "\n\t time_mode = " + self.time_mode        
        res+=  "\n\t Injection time = " + str(self.time_start) + " To " + str(self.time_end)
        res+=  "\n\t Activity time = " + str(self.activity_time_start) + " To " + str(self.activity_time_end)
        res+=  "\n\t Inactivity_time_end time = " + str(self.inactivity_time_start) + " To " + str(self.inactivity_time_end)
        res+=  "\n\t forced_value = " + self.forced_value
        res+=  "\n\t rand_seed = " + str(self.rand_seed)
        res+=  "\n\t duration = " + str(self.duration)        
        return(res)


class InjectionTaskConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.maxproc = int(1)
            self.workload_split_factor = int(0)            
            self.campaign_label = "AFIT_"
            self.compile_project = "off"
            self.cleanup_folders = "off"
            self.create_scripts = "off"
            self.create_checkpoints = "off"
            self.create_precise_checkpoints = "off"
            self.create_injection_scripts = "off"
            self.run_faultinjection = "off"
            self.remove_par_lib_after_checkpoint_stored = "off"
            self.cancel_pending_tasks = "off"
            self.sim_time_checkpoints = ""
            self.sim_time_injections = ""
            self.work_label = ""
            self.wlf_remove_time = ""
            self.run_cleanup = ""
            self.monitoring_mode = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.maxproc = int(xnode.get('maxproc'))
        self.workload_split_factor = int(xnode.get('workload_split_factor'))        
        self.campaign_label = xnode.get('campaign_label')
        self.compile_project = xnode.get('compile_project')
        self.cleanup_folders = xnode.get('cleanup_folders')
        self.create_scripts = xnode.get('create_scripts')
        self.create_checkpoints = xnode.get('create_checkpoints')
        self.create_precise_checkpoints = xnode.get('create_precise_checkpoints')
        self.create_injection_scripts = xnode.get('create_injection_scripts')
        self.run_faultinjection = xnode.get('run_faultinjection')
        self.remove_par_lib_after_checkpoint_stored = xnode.get('remove_par_lib_after_checkpoint_stored')
        self.cancel_pending_tasks = xnode.get('cancel_pending_tasks','off')
        self.sim_time_checkpoints = xnode.get('sim_time_checkpoints')
        self.sim_time_injections = xnode.get('sim_time_injections')
        self.work_label = xnode.get('work_label')
        self.wlf_remove_time = int(xnode.get('wlf_remove_time'))
        self.run_cleanup = xnode.get('run_cleanup')
        self.monitoring_mode = xnode.get('monitoring_mode', '')
        return(0)
    
    def to_string(self):
        res = "Injection Task Config: "
        res += "\n\t maxproc: " + str(self.maxproc)
        res+=  "\n\t workload_split_factor = " + str(self.workload_split_factor)        
        res += "\n\t campaign_label: " + self.campaign_label
        res += "\n\t compile_project: " + self.compile_project
        res += "\n\t cleanup_folders: " + self.cleanup_folders
        res += "\n\t create_scripts: " + self.create_scripts
        res += "\n\t create_checkpoints: " + self.create_checkpoints
        res += "\n\t create_precise_checkpoints: " + self.create_precise_checkpoints
        res += "\n\t create_injection_scripts: " + self.create_injection_scripts
        res += "\n\t run_faultinjection: " + self.run_faultinjection
        res += "\n\t remove_par_lib_after_checkpoint_stored: " + self.remove_par_lib_after_checkpoint_stored
        res += "\n\t cancel_pending_tasks: " + self.cancel_pending_tasks        
        res += "\n\t sim_time_checkpoints: " + self.sim_time_checkpoints
        res += "\n\t sim_time_injections: " + self.sim_time_injections
        res += "\n\t work_label: " + self.work_label
        res += "\n\t wlf_remove_time: " + str(self.wlf_remove_time)
        res += "\n\t run_cleanup: " + self.run_cleanup
        return(res)



#---------------------------------------
# classes for analysis of simulation dumps
#---------------------------------------
    
class RenameItem:
    def __init__(self, ifrom="", ito=""):
        self.ifrom = ifrom
        self.ito = ito
    def to_string(self):
        return('From: ' + self.ifrom + ", To: " + self.ito)


#cdiv_pattern = re.compile("\s+")
val_pattern = re.compile("[0-9a-zA-Z\.\+\-\*]+")

def find_between( s, first, last ):
    try:
        start = s.index( first ) + len( first )
        end = s.index( last, start )
        return s[start:end]
    except ValueError:
        return ""

class VectorField:
    internal, output = range(2)

class SimVector:
    def __init__(self, time=0.0, delta = 0):
       #time is supposed to be float %.2
       self.time = 0.0
       self.delta = 0
       self.internals = []
       self.outputs = []

    #field: VectorField.internal or VectorField.output
    def equals(self, v_cmp, field):
        if field == VectorField.internal:
            if len(self.internals) != len(v_cmp.internals):
                return(False)
            for i in range(0, len(self.internals), 1):
                if self.internals[i] != v_cmp.internals[i]:
                    return(False)
        elif field == VectorField.output:
            if len(self.outputs) != len(v_cmp.outputs):
                return(False)
            for i in range(0, len(self.outputs), 1):
                if self.outputs[i] != v_cmp.outputs[i]:
                    return(False)
        else:
            raw_input('Undefined Field specificator: ' + str(field))
        return(True)


    def build_from_string(self, intern_num, output_num, str_data):
        clm = re.findall(val_pattern, str_data)
        if(len(clm) < intern_num + output_num + 2):
            print "build_from_string err: line is not complete"
            return(None)
        self.time = float(clm[0])
        self.delta = int(clm[1])

        for ind in range(2, 2+intern_num, 1):
            self.internals.append(clm[ind]) 
        for ind in range(2+intern_num, 2+intern_num+output_num, 1):
            self.outputs.append(clm[ind])   
        return(self)       
    
    def to_csv(self):
        res = str(self.time) + ";" + str(self.delta) + ";"
        for c in self.internals:
            res += c + ";"
        for c in self.outputs:
            res += c + ";"
        return(res)
    
    def to_html(self):
        res = "<tr>" + "<td>" + str(self.time) + "</td><td>" + str(self.delta) + "</td>"
        for c in self.internals:
            res += "<td>" + c + "</td>"
        for c in self.outputs:
            res += "<td>" + c + "</td>"
        res +="</tr>"
        return(res)
        
class JoinGroup:
    def __init__(self, label=""):
        self.join_label = label
        self.src_labels = []
        self.src_indexes = []
        
    def to_str(self):
        res = "\tJOIN_GROUP: " + self.join_label + " :"
        for i in self.src_labels:
            res += "\n\t\t"+i
        return(res)

    def copy(self):
        res = JoinGroup(self.join_label)
        for i in self.src_labels:
            res.src_labels.append(i)
        return(res)
                

class JoinGroupList:
    def __init__(self):
        self.group_list = []
        
    def init_from_tag(self, tag):
        for c in tag.findall('group'):
            a = JoinGroup(c.get('label'))
            for i in c.findall('item'):
                a.src_labels.append(i.get('label'))
            self.group_list.append(a)

    def to_str(self):
        res = "JOIN_GROUPS: "
        for c in self.group_list:
            res += "\n" + c.to_str()
        return(res)
    
    def copy(self):
        res = JoinGroupList()
        for c in self.group_list:
            res.group_list.append(c.copy())
        return(res)
    
        
    
class simDump:
    def __init__(self, fname=""):
        self.vectors = []
        self.internal_labels = []
        self.output_labels = []
        self.caption = ""
        #subset of vectors where only inputs/outputs change their value
        self.v_out_filtered = []
        self.v_int_filtered = []
    
    #input - simInitModel.do
    #result - self.internal_labels, self.output_labels
    def build_labels_from_file(self, fname="", rename_list=None):
        initfile = open(fname,'r')
        fcontent = initfile.read()
        initfile.close()
        internals_content = find_between(fcontent, "#<INTERNALS>","#</INTERNALS>")
        outputs_content = find_between(fcontent, "#<OUTPUTS>","#</OUTPUTS>")
        self.internal_labels = re.findall("-label\s+?(.+?)\s+?", internals_content)
        self.output_labels = re.findall("-label\s+?(.+?)\s+?", outputs_content)
        if(rename_list != None):
            for c in rename_list:
                for i in range(0, len(self.internal_labels), 1):
                    if( self.internal_labels[i] == c.ifrom):
                        self.internal_labels[i] = c.ito
        return(0)
    
    def get_labels_copy(self):
        il = []
        ol = []
        for c in self.internal_labels:
            il.append(c)
        for c in self.output_labels:
            ol.append(c)
        return( (il, ol) )
        
    def set_labels_copy(self, il, ol):
        for c in il:
            self.internal_labels.append(c)
        for c in ol:
            self.output_labels.append(c)
        return(0)        
        
    
    #input - dump file *.lst
    #result - self.vectors
    def build_vectors_from_file(self, fname=""):
        self.caption = fname
        with open(fname, 'r') as dumpfile:
            lines = dumpfile.readlines()
        for l in lines:
            if re.match('^\s*?[0-9]+', l):
                v = SimVector()
                v.build_from_string(len(self.internal_labels), len(self.output_labels), l)
                self.vectors.append(v)
        if(len(self.vectors) == 0):
            with open('error_log.txt','a') as err_log:
                err_log.write('\nEmpty list file: '+ fname)
            return(None)
        else:
            self.normalize(True)            
            return(self)
    
    def remove_vector(self, index):
        del self.vectors[index]
    
    #For each vector remove all preceding vectors with the same timestamp (keep only last vector for each time instance)
    def normalize(self, RemoveDelta = True):
        vset = []
        vbuf = self.vectors[-1]
        vset.append(vbuf)
        for i in range(len(self.vectors)-1, -1, -1):
            v = self.vectors[i]
            if (v.time == vbuf.time) and (v.delta == vbuf.delta):
                continue
            elif RemoveDelta and (v.time == vbuf.time):
                continue
            else:
                vbuf = v
                vset.append(vbuf)
        vset.reverse()
        self.vectors = vset

    #Select two sequences of vectors: where inputs/outputs change their values
    def filter_vectors(self):
        if len(self.vectors) > 0:
            self.v_int_filtered.append(self.vectors[0])
            for v in self.vectors:
                if not (v.equals(self.v_int_filtered[-1], VectorField.internal)):
                    self.v_int_filtered.append(v)
            self.v_out_filtered.append(self.vectors[0])
            for v in self.vectors:
                if not (v.equals(self.v_out_filtered[-1], VectorField.output)):
                    self.v_out_filtered.append(v)
        
    
    def to_html(self, fname):
        content = "<!DOCTYPE HTML>\n<html><head>\n<meta charset=\"utf-8\"></head>\n<body>"
        table = "<table border=\"1\"><caption>" + self.caption + "</caption>"
        table += "\n<tr><th>TIME</th>"+"\n<th>DELTA</th>"
        for label in self.internal_labels:
            table += "<th>"+label+"</th>"
        for label in self.output_labels:
            table += "<th>"+label+"</th>"
        table+="</tr>"
        for v in self.vectors:
            table+=v.to_html()
        table += "</table>"
        content += table
        content += "</body></html>"
        hdump = open(fname, "w")
        hdump.write(content)
        hdump.close()
        
    def get_vector_by_time(self, itime, idelta=None):
        if idelta != None:
            for v in self.vectors:
                if((v.time == itime) and (v.delta == idelta)):
                    return(v)
        else:
            for v in self.vectors:
                if (v.time == itime):
                    return(v)
        return(None)
    
    def compare_to_html(self, refdump, fname):
        nrows = len(self.vectors)
        ncols = 2 + len(self.internal_labels) + len(self.output_labels)
        htable = HtmlTable(nrows, ncols, self.caption)
        htable.set_label(0, "Time")
        htable.set_label(1, "Delta")
        
        len_int = len(self.internal_labels)
        len_out = len(self.output_labels)
        for i in range(0, len_int, 1):
            htable.set_label(2+i, self.internal_labels[i])
        for i in range(0, len_out , 1):
            htable.set_label(2+len_int + i, self.output_labels[i])
        for i in range(0, len(self.vectors), 1):
            itime = self.vectors[i].time
            idelta = self.vectors[i].delta
            htable.put_data(i, 0, str(itime))
            htable.put_data(i, 1, str(idelta))            
            refvector = refdump.get_vector_by_time(itime, idelta)
            for j in range(0, len_int, 1):
                htable.put_data(i,2+j, self.vectors[i].internals[j])
                htable.set_class(i,2+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].internals[j] == refvector.internals[j]):
                        htable.set_class(i,2+j,"pass")
                    else:
                        htable.set_class(i,2+j,"fail")
            for j in range(0, len_out, 1):
                htable.put_data(i,2+len_int+j, self.vectors[i].outputs[j])
                htable.set_class(i,2+len_int+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].outputs[j] == refvector.outputs[j]):
                        htable.set_class(i,2+len_int+j,"pass")
                    else:
                        htable.set_class(i,2+len_int+j,"fail")                        
        hpage = HtmlPage(self.caption)
        hpage.css_file = "../../../../teststyle.css"
        hpage.js_files.append('../../../../jquery-1.12.1.min.js')
        hpage.js_files.append('../../../../myscript.js')        
        hpage.put_data(htable.to_string())
        hpage.put_data(self.get_highlight_comment())    
        hpage.write_to_file(fname)
    
    def get_highlight_comment(self):
        res = HtmlTable(1, 3, "Highlighting Options")
        res.put_data(0,0,"Match")
        res.set_class(0,0,"pass")
        res.put_data(0,1,"Mismatch (error/failure)")
        res.set_class(0,1,"fail")
        res.put_data(0,2,"Unexpected transition (time point not in reference)")
        res.set_class(0,2,"nomatch")
        return("<br><hr>"+res.to_string_no_header())
        



    # select next-time vector after ivect.time, field == None - from complete dump, VectorField.internal - from v_int_filtered, VectorField.output - from v_out_filtered,
    def get_closest_forward(self, itime, field = None):
        if field == None:
            vectlist = self.vectors
        elif field == VectorField.internal:
            vectlist =  self.v_int_filtered
        elif field == VectorField.output:
            vectlist = self.v_out_filtered
        for v in vectlist:
            if v.time >= itime:
                return(v)
        return(None)
    
    # select prev-time vector after ivect.time, field == None - from complete dump, VectorField.internal - from v_int_filtered, VectorField.output - from v_out_filtered,
    def get_closest_backward(self, itime, field = None):
        if field == None:
            vectlist = self.vectors[::-1]
        elif field == VectorField.internal:
            vectlist =  self.v_int_filtered[::-1]
        elif field == VectorField.output:
            vectlist = self.v_out_filtered[::-1]
        for v in vectlist:
            if v.time <= itime:
                return(v)
        return(None)




    #returns first vector in self which does not match some vector from cmpdump
    #if mathing rules for all vectors in self are satisfied - returns None (no failures)
    def get_first_fail_vector(self, cmpdump, neg_timegap=float(0), pos_timegap=float(0), check_duration_factor=float(0), start_time = float(0)):
        if self.v_out_filtered == []:    self.filter_vectors()
        if cmpdump.v_out_filtered == []: cmpdump.filter_vectors()
        if len(cmpdump.v_out_filtered) == 0:
            return(self.v_out_filtered[0])
        #Find match for each interval v[i] - v[i+1]
        for v in range(0, len(self.v_out_filtered), 1):
            if self.v_out_filtered[v].time < start_time:
                continue
            checkvalue = ','.join(self.v_out_filtered[v].outputs)
            match = False
            if check_duration_factor > float(0) and v < len(self.v_out_filtered)-1:
                for c in range(0, len(cmpdump.v_out_filtered)-1, 1):
                    #1st condition: CMP vector inside the timegap around SELF vector
                    if (cmpdump.v_out_filtered[c].time >= self.v_out_filtered[v].time - neg_timegap) and (cmpdump.v_out_filtered[c].time <= self.v_out_filtered[v].time + pos_timegap):
                        #2nd condition: outputs of CMP vector match outputs of SELF vector
                        if ','.join(cmpdump.v_out_filtered[c].outputs) == checkvalue:
                            #3rd condition: duration (stability interval) is not less than in reference (SELF) * check_duration_factor
                            if (cmpdump.v_out_filtered[c+1].time - cmpdump.v_out_filtered[c].time) >= (self.v_out_filtered[v+1].time - self.v_out_filtered[v].time)*check_duration_factor:
                                match = True
                                break
            else: #duration check disabled OR last vector in self.v_out_filtered
                for c in range(0, len(cmpdump.v_out_filtered), 1):
                    if (cmpdump.v_out_filtered[c].time >= self.v_out_filtered[v].time - neg_timegap) and (cmpdump.v_out_filtered[c].time <= self.v_out_filtered[v].time + pos_timegap):
                        if ','.join(cmpdump.v_out_filtered[c].outputs) == checkvalue:
                            match = True
                            break
            if not match: #return this vector because no match found in cmpdump
                return(self.v_out_filtered[v])
        return(None) #all vectors in SELF match some vectors in cmpdump

    
    def get_forward_by_key(self, itime, ikey, ival):
        vname, c_index = self.get_index_by_label(ikey)
        for v in self.vectors:
            if v.time  >= itime:
                if(v.internals[c_index] == ival):
                    return(v)
        return(None)
    
    
    def get_first_mismatch(self, idump, inj_time):
        for v in self.vectors:
            if(v.time < inj_time):
                continue
            c = idump.get_vector_by_time(v.time, None)
            if(c==None):
                return(v)
            else:
                for i in range(0, len(v.outputs), 1):
                    if(v.outputs[i] != c.outputs[i]):
                        return(v)
        return(None)
    
    def join_output_columns(self, join_group_list):
        if(len(join_group_list.group_list) == 0):
            return(1)
        new_output_label_list = []
        for jn in join_group_list.group_list:
            jn.src_indexes = []
            for i in jn.src_labels:
                #print "LABEL: " + i
                jn.src_indexes.append(self.output_labels.index(i))
            if(jn.join_label != '-'):
                new_output_label_list.append(jn.join_label)
            
        for v in self.vectors:
            new_outputs = []
            for jn in join_group_list.group_list:
                if(jn.join_label != '-'):
                    val = ""
                    for i in jn.src_indexes:
                        val += v.outputs[i]
                    new_outputs.append(val)
            v.outputs = new_outputs
        self.output_labels = new_output_label_list
        return(0)

    #returns tuple: (vector_name, index) for specified label
    def get_index_by_label(self, label):
        for ind in range(0, len(self.internal_labels), 1):
            if(label == self.internal_labels[ind]):
                return(('internals',ind))
        for ind in range(0, len(self.output_labels), 1):
            if(label == self.output_labels[ind]):
                return(('outputs',ind))
        return(('not_found', 0))

    def get_first_vector_by_key (self, key = "FinishFlag", val = "1"):
        vname, c_index = self.get_index_by_label(key)
        if(vname == 'internals'):
            try:
                for i in range(0, len(self.vectors), 1):
                    if(self.vectors[i].internals[c_index] == val):
                        return(self.vectors[i])
            except IndexError:
                print str(IndexError)
                return(None)
        if(vname == 'outputs'):
            try:
                for i in range(0, len(self.vectors), 1):
                    if(self.vectors[i].outputs[c_index] == val):
                        return(self.vectors[i])     
            except IndexError:
                print str(IndexError)
                return(None)                       
        return(None)
        
    def get_value_where(self, column_label = "", where_key = "", where_value = ""):
        vname, c_index = self.get_index_by_label(column_label)
        vect = self.get_first_vector_by_key(where_key, where_value)
        if(vname == 'internals'):
            return(vect.internals[c_index])
        elif(vname == 'outputs'):
            return(vect.outputs[c_index])
        else:
            return ""



#---------------------------------------------------
# Model of fault injection targets (simNodes.xml)
#---------------------------------------------------
class InjectionNode:
    def __init__(self, xnode):
        if xnode is None:        
            self.type = ""
            self.name = ""
            self.group = ""
        else:
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
            self.type = xnode.get('type').lower()
            self.name = xnode.get('name')
            self.group = xnode.get('group','')
 
class ConfigNodes:
    def __init__(self, lbl="", xnode=None):
        self.config_label = lbl
        self.common_nodes = []
        self.pseudo_common_nodes = []
        self.specific_nodes = []
        if(xnode != None):  
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
        com_tag = xnode.findall('CommonNodes')
        ps_com_tag = xnode.findall('PseudoCommonNodes')
        spec_tag = xnode.findall('SpecificNodes')
        if(com_tag != [] and com_tag != None):
            for c in com_tag[0].findall('Node'):
                self.common_nodes.append(InjectionNode(c))
        if(ps_com_tag != [] and com_tag != None):        
            for c in ps_com_tag[0].findall('Node'):
                self.pseudo_common_nodes.append(InjectionNode(c))
        if(spec_tag != [] and com_tag != None):                        
            for c in spec_tag[0].findall('Node'):
                self.specific_nodes.append(InjectionNode(c))
    
    def get_all_by_typelist(self, typelist):
        res = []
        for c in self.common_nodes:
            if(c.type in typelist):
                res.append(c)
        for c in self.pseudo_common_nodes:
            if(c.type in typelist):
                res.append(c)
        for c in self.specific_nodes:
            if(c.type in typelist):
                res.append(c)
        return(res)
    
    def get_all(self):
        res = []
        for c in self.common_nodes:
            res.append(c)
        for c in self.pseudo_common_nodes:
            res.append(c)
        for c in self.specific_nodes:
            res.append(c)
        return(res)
    

#--------------------------------------------------
# Fault dictionary model
#-------------------------------------------------
class Macrocell:
    def __init__(self, type, source_file=''):
        self.type = type
        self.source_file = source_file
        self.configuration = ''
        self.instrumentation_checklist = []

#class ProfilingRule:
#    def __init__(self, xnode):
#        self.type = ''
#        self.profile_expression = ''
#        if(xnode!=None):
#            self.type = xnode.get('type')
#            self.profile_expression = xnode.get('profile_expression')


class NodeDimension:
    def __init__(self, low_index=0, high_index=0):
        self.low_index = low_index
        self.high_index  = high_index

class Node:
    def __init__(self, placeholder, nodename_pattern):
        self.placeholder = placeholder
        self.nodename_pattern = nodename_pattern

class NodeDimension:
    def __init__(self, low_index=0, high_index=0):
        self.low_index = low_index
        self.high_index  = high_index

class InjectionCase:
    def __init__(self, xnode):
        self.label = ''
        self.condition = ''
        self.dimensions = []
        self.nodes = []	        #from string separated by comma
        self.profile_switching_activity = ''
        self.profile_value = ''
        if(xnode!=None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.label = xnode.get('label', '')
        self.condition = xnode.get('condition','').replace(' ','').lower()
        self.profile_switching_activity = xnode.get('profile_switching_activity')
        self.profile_value = xnode.get('profile_value')
        d = xnode.get('dimensions','').replace(' ','')
        if d != '':
            for c in d.split(','):
                t = c.split('-')
                self.dimensions.append(NodeDimension(int(t[0]), int(t[1])))
        d = xnode.get('nodes', '').replace(' ','')
        if d != '':
            for c in d.split(','):
                t=c.split('=')
                self.nodes.append(Node(t[0], t[1]))
        else:
            self.nodes.append(Node('', ''))


class InjectionRule:
    def __init__(self, xnode):
        self.code_pattern = ''
        self.injection_cases = []
        if(xnode!=None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.code_pattern = xnode.get('code_pattern').replace('#;','\n')
        for c in xnode.findall('injectioncase'):
            self.injection_cases.append(InjectionCase(c))



class InstrumentationRuleBase:
    def __init__(self):
        pass

class InjectableGeneric(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.src = ''
        self.dst = ''
        if(xnode!=None):
            self.src = xnode.get('src')
            self.dst = xnode.get('dst')

class EncloseInProcess(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.block_name = ''
        self.process_name = ''
        if(xnode!=None):
            self.block_name = xnode.get('block_name')
            self.process_name = xnode.get('process_name')
        

            
class RedefineNode(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.name = ''
        self.modifier_to = ''
        self.basetype_to = ''
        self.inline_to = ''
        if(xnode!=None):
            self.name = xnode.get('name')
            self.modifier_to = xnode.get('modifier_to')
            self.basetype_to = xnode.get('basetype_to')
            self.inline_to = xnode.get('inline_to')


class ExtendSensitivityList(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.process_name = ''
        self.nodes = []
        if(xnode!=None):
            self.process_name = xnode.get('process_name')
            self.nodes = xnode.get('nodes').split(',')

class InstrumentationRule:
    def __init__(self, xnode):
        self.items = []
        if(xnode!=None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        for c in xnode.findall('injectable_generic'):
            self.items.append(InjectableGeneric(c))
        for c in xnode.findall('enclose_inprocess'):
            self.items.append(EncloseInProcess(c))
        for c in xnode.findall('redefine_node'):
            self.items.append(RedefineNode(c))
        for c in xnode.findall('extend_sensitivity_list'):
            self.items.append(ExtendSensitivityList(c))




class FaultDescriptor:
    def __init__(self, xnode):
        self.fault_model = ''
        self.macrocells = []
        self.instrumentation_rule = None
        self.injection_rules = []
        if(xnode!=None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.fault_model = xnode.get('model')        
        self.macrocells = [x.lower() for x in re.findall('[a-zA-Z0-9_]+', xnode.get('macrocells'))]        
        for c in xnode.findall('instrumentation_rule'):
            self.instrumentation_rule = InstrumentationRule(c)
        for c in xnode.findall('injection_rule'):
            self.injection_rules.append(InjectionRule(c))

class FaultDict:
    def __init__(self, fname):
        self.dict_items = []
        self.macrocells = []
        if(fname!=''):
            self.update(fname)

    #update dictionary by appending items from xml specification (e.g. Lib_Spec_simprim.xml)
    def update(self, fname):
        tree = ET.parse(fname).getroot()
        for xnode in tree.findall('fdesc'):
            self.dict_items.append(FaultDescriptor(xnode))
        for m in self.get_prim_list():
            self.macrocells.append(Macrocell(m, ''))
    
    def get_prim_list(self):
        res = []
        for c in self.dict_items:
            for i in c.macrocells:
                if(not i in res):
                    res.append(i)
        return(res)
            
    def get_descriptor(self, faultmodel, macrocell):
        for desc in self.dict_items:
            if(desc.fault_model == faultmodel and macrocell in desc.macrocells):
                return(desc)
        return(None)

        
        


#----------------------------------------------
#        Profiling logic 
#----------------------------------------------

class ProfilingAddressDescriptor:
    def __init__(self, Iaddress):
        self.address = Iaddress
        self.rate = float(0)
        self.time_from = float(0)
        self.time_to = float(0)
        self.total_time = float(0)
        self.entries = int(0)
        self.effective_switches = int(0)
        self.profiled_value = ''
        
    def to_xml(self):
        return '<address val = \"{0:s}\" rate = \"{1:.4f}\" time_from = \"{2:.2f}\" time_to = \"{3:.2f}\" total_time = \"{4:.1f}\" entries = \"{5:d}\" effective_switches = \"{6:d}\"/>'.format(self.address, self.rate, self.time_from, self.time_to, self.total_time, self.entries, self.effective_switches)


class ProfilingDescriptor:
    def __init__(self, Iprim_type, Iprim_name, Icase):
        self.prim_type = Iprim_type
        self.prim_name = Iprim_name
        self.inj_case = Icase           #object from dictionary->injection_rule(prim_type, fault_model)->injection_case
        self.trace_descriptor = None
        self.address_descriptors = []
        self.indetermination = False
        self.indetermination_time = float(0)
        self.profiled_value = ''

    def to_xml(self):
        res = '\n\t<simdesc prim_type = \"' + self.prim_type + '\" prim_name = \"'+ self.prim_name + '\" inj_case = \"' + self.inj_case.label + '\" >'
        for i in self.address_descriptors:
            res += '\n\t\t' + i.to_xml()
        return(res + '\n\t</simdesc>')
    
    def get_by_adr(self, iadr):
        for i in self.address_descriptors:
            if i.address == str(iadr):
                return(i)
        return(None)

class ProfilingResult:
    def __init__(self, Iconfig, Ifaultmodel):
        self.config = Iconfig
        self.faultmodel = Ifaultmodel
        self.items = []
    
    def append(self, Iprim_type, Iprim_name, Icase):
        self.items.append(ProfilingDescriptor(Iprim_type, Iprim_name, Icase))

    def get(self, prim_type, prim_name, inj_case_label):
        for i in self.items:
            if(i.prim_type == prim_type and i.prim_name == prim_name and i.inj_case.label == inj_case_label):
                return(i)



#returns list of possible addresses by replacing X with 1/0
def resolve_indetermination(addr):
	res = []
	res.append(addr)
	cnt = 1
	while cnt > 0:
		cnt = 0
		for i in range(0, len(res), 1):
			if res[i].count('X') > 0:
				a = res[i]
				res.remove(a)
				res.append(a.replace('X','1',1))
				res.append(a.replace('X','0',1))
				cnt+=1
				break
	return(res)




#---------------------------------
# Builds the list of injection scripts (*.do files)
#---------------------------------
def generate_injection_scripts(conf, genconf, toolconf, fmlist, faultdict):
    #Build the list of checkpoints
    if(not os.path.exists(os.path.join(conf.work_dir, toolconf.checkpoint_dir))):
        print 'Generate injection scripts: Checkpoints dir does not exist: ' + os.path.join(conf.work_dir, toolconf.checkpoint_dir)
        return(0)
    os.chdir(os.path.join(conf.work_dir, toolconf.checkpoint_dir))
    checkpointlist = []
    flist = glob.glob('*.sim')
    for i in flist:
        if i.startswith('checkpoint'):
            checkpointlist.append( int(re.findall("[0-9]+", i)[0]) )
    checkpointlist.sort()
    print "Checkpoints: "
    for i in checkpointlist: print str(i)
    if(len(checkpointlist)==0):
        print 'Generate injection scripts: No checkpoints found at ' + os.path.join(conf.work_dir, toolconf.checkpoint_dir)
        return(0)

    script_index = 0
    fdesclog_content = "sep=;\nINDEX;TARGET;INSTANCE_TYPE;FAULT_MODEL;FORCED_VALUE;DURATION;TIME_INSTANCE;OBSERVATION_TIME;MAX_ACTIVITY_DURATION;EFFECTIVE_SWITHES;PROFILED_VALUE;ON_TRIGGER;"
    scale_factor = float(conf.clk_period) / float(genconf.std_clk_period)
    for fconfig in fmlist:
        #Select macrocells(targets) of the types specified in the faultload configuration
        nodetree = ET.parse(os.path.join(conf.work_dir, toolconf.injnode_list)).getroot()
        inj_nodes = ConfigNodes(conf.label, nodetree)
        nodelist = inj_nodes.get_all_by_typelist(fconfig.target_logic)
        print("\n" + fconfig.model + ", " + str(fconfig.target_logic) + ", targets number: " + str(len(nodelist)))

        #PHASE_1 (PROFILING) to inject faults only into active nodes, assuming no fault effect for inactive nodes (masked)
        PresimRes = None
        if(fconfig.profiling.lower() == 'on'):
            #PHASE_1.1 - Prepare data model and scripts
            PresimRes = ProfilingResult(conf, fconfig)
            for instance in nodelist:
                 faultdescriptor = faultdict.get_descriptor(fconfig.model, instance.type)
                 for inj_rule in faultdescriptor.injection_rules:
                     for inj_case in inj_rule.injection_cases:
                         if inj_case.profile_switching_activity == '': raw_input('Error: profile_switching_activity expression not defined for: ' + inj_case.label)
                         if inj_case.profile_value == '': raw_input('Error: profile_value expression not defined for: ' + inj_case.label)
                         PresimRes.append(instance.type, instance.name, inj_case)
            PresimScript = "#Profiling script: Fault model: " +  fconfig.model
            cnt = int(0)
            for i in PresimRes.items:
                i.trace_descriptor = "ITEM_"+str(cnt)
                PresimScript += "\nquietly virtual signal -env " + i.prim_name + " -install " + i.prim_name + " " + i.inj_case.profile_switching_activity + " " + i.trace_descriptor
                PresimScript += "\nset " + i.trace_descriptor + " [view list -new -title " + i.trace_descriptor + "]"
                PresimScript += "\nradix bin"
                PresimScript += "\nadd list " + i.prim_name + "/" + i.trace_descriptor + " -window $" + i.trace_descriptor
                PresimScript += "\nadd list " + i.prim_name + "/" + i.inj_case.profile_value + " -window $" + i.trace_descriptor
                cnt+=1
            PresimScript += "\nrun " + str(genconf.std_workload_time * scale_factor) + " ns"
            for i in PresimRes.items:
                PresimScript +=  "\nview list -window $" + i.trace_descriptor
                PresimScript += "\nwrite list -window $" + i.trace_descriptor + " " + toolconf.log_dir+"/"+i.trace_descriptor+".lst"
            PresimScript += "\nquit\n"
            os.chdir(conf.work_dir)
            with open('simtest.do', 'w') as ds: 
                ds.write(PresimScript)

            #PHASE_1.2 - run profling
            proc = subprocess.Popen("vsim -c -restore " + toolconf.checkpoint_dir + "/" + toolconf.std_start_checkpoint + " -do \"do " + 'simtest.do' + "\"", shell=True)
            print "Profiling: fault model: "  +  fconfig.model
            proc.wait()

            #PHASE_1.3 - analyze traces
            WorkloadTotal = genconf.std_workload_time * scale_factor
            MaxtimePoint = float(genconf.std_init_time + genconf.std_workload_time) * scale_factor
            item_cnt = 1
            for i in PresimRes.items:
                sys.stdout.write('processing node: %6d of %6d \r' % (item_cnt, len(PresimRes.items)))
                sys.stdout.flush() 
                item_cnt+=1
                dump = simDump()
                dump.internal_labels.append(i.prim_name + "/" + i.trace_descriptor)
                dump.internal_labels.append(i.prim_name + "/" + i.trace_descriptor+'_ProfiledValue')
                dump.build_vectors_from_file(toolconf.log_dir+"/"+i.trace_descriptor+".lst")
                D = dict()  # address -> address_descriptor
                i.profiled_value = dump.vectors[0].internals[1]
                for v_i in range(0, len(dump.vectors)):
                    addr_list = resolve_indetermination(dump.vectors[v_i].internals[0])
                    for a in addr_list:
                        addr = str(int(a, 2))   #convert bin to int
                        t_from = float(dump.vectors[v_i].time)
                        if(v_i < len(dump.vectors)-1):
                            t_to = float(dump.vectors[v_i+1].time)
                        else:
                            t_to = MaxtimePoint
                        t_delta = t_to - t_from
                        x = D.get(addr)
                        if(x==None):
                            x = ProfilingAddressDescriptor(addr)
                            D[addr] = x
                        if(x.time_to - x.time_from < t_delta):
                            x.time_to = t_to
                            x.time_from = t_from
                        if t_delta >= 0.2*float(conf.clk_period):
                            x.effective_switches += 1
                        x.total_time += t_delta
                        x.entries += 1
                for k, v in D.items():
                    i.address_descriptors.append(v)
                    v.rate = v.total_time / WorkloadTotal
                i.address_descriptors.sort(key=lambda c: c.rate, reverse=True)

            #Phase_1.4 - statistics and logs
            #Export complete Profiling statistics
            mean_items = 0
            for i in PresimRes.items:
                mean_items += len(i.address_descriptors)
            mean_items = mean_items/len(PresimRes.items)
            print '\nMean items [ALL]:' + str(mean_items)
            with open(toolconf.log_dir + '/profiling.xml', 'w') as fdesc:
                fdesc.write('<presimres config = \"' + str(PresimRes.config.label) + '\" fault_model = \"' + str(PresimRes.faultmodel.model) + '\" >')
                for i in PresimRes.items:
                    fdesc.write(i.to_xml())
                fdesc.write('</presimres>')

            #Log the Amount of items wrt. time coverage
            cov_threshold = float(0.99)
            while cov_threshold > float (0.7):
                cnt = float(0)
                for i in PresimRes.items:
                    lcov = float(0)
                    for v in i.address_descriptors:
                        lcov += v.rate
                        cnt += float(1.0)
                        if lcov >= cov_threshold: break
                print 'Coverage: {0:.2f}; Items: {1:.2f}'.format(cov_threshold, cnt/len(PresimRes.items))
                cov_threshold -= float(0.01)

            # For test purposes: append inactive nodes with effective_switches = -1
            # for i in PresimRes.items:
            #     for bit in range(int(i.node.low_index), int(i.node.high_index)+1, 1):
            #         if(i.get_by_adr(str(bit)) == None):
            #             z = ProfilingAddressDescriptor(bit)
            #             z.effective_switches = -1
            #             i.address_descriptors.append(z)                   

            #Select/Save profiled value for each vector item 
            for i in PresimRes.items:
                if i.profiled_value != '':
                    val = i.profiled_value[::-1]
                    for v in i.address_descriptors:
                        v.profiled_value = val[int(v.address)]

            #Print switching activity statistics
            switching_activity_stat = dict()
            for i in PresimRes.items:
                for v in i.address_descriptors:
                    if(switching_activity_stat.get(v.effective_switches)==None):
                        switching_activity_stat[v.effective_switches] = int(1)
                    else:
                         switching_activity_stat[v.effective_switches] += 1
            for k, v in switching_activity_stat.items():
                print 'swithes: ' + str('%5d' % k) + ' - items: ' + str('%5d' % v)
                    
        #PHASE_2 - Generate scripts
        inj_start_time = int(genconf.std_workload_time * fconfig.time_start * scale_factor)
        inj_stop_time  = int(genconf.std_workload_time * fconfig.time_end * scale_factor)
        print "Start time: " + str(inj_start_time) + "\nStop time: " + str(inj_stop_time)
        nonrandom = (inj_stop_time == 0 or inj_stop_time < inj_start_time)
        os.chdir(os.path.join(conf.work_dir, toolconf.script_dir))
        for i in range(0, fconfig.experiments_per_target, 1):
            random.seed(fconfig.rand_seed + i)
            prev_desc = ('', random.getstate())
            for instance in nodelist:
                #bypass empty items, maintaining the same rand sequence
                if(instance.type == '__'):
                    random.randint(inj_start_time, inj_stop_time)
                    continue
                #build the list of tuples (inj_case, inj_code, profiling_descriptor)
                inj_code_items = get_injection_code_all(instance, faultdict, fconfig, scale_factor, PresimRes)
                #for the instance from the same group as previous one: restore rand state to obtain the same random sequence 
                if(instance.group != '' and instance.group == prev_desc[0]):
                    random.setstate(prev_desc[1])
                else:
                    prev_desc = (instance.group, random.getstate())
                #Export Fault simulation scripts (*.do files)
                for c in inj_code_items:
                    str_index = str("%06d" % (script_index))
                    inj_script = "transcript file " + toolconf.log_dir +"/log_" + str_index + "_nodename.txt"
                    inj_time = []
                    for t in range(fconfig.multiplicity):
                        inj_time.append(inj_start_time if nonrandom else random.randint(inj_start_time, inj_stop_time))
                    inj_time.sort()

                    if fconfig.trigger_expression == '':    #time-driven injection
                        #find closest checkpoint
                        checkpoint_linked = 0
                        for ct in checkpointlist:
                            if(ct < inj_time[0]):
                                checkpoint_linked = ct
                        inj_script += "\nset ExecTime " + str(int(genconf.std_workload_time*scale_factor)-int(checkpoint_linked)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                             inj_script += str(int(t)-int(checkpoint_linked)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nforeach i $InjTime {\n\twhen \"\\$now >= $i\" {\n\t\tputs \"Time: $::now: Injection of " + fconfig.model + "\"\n\t\t" + c[1] + "\n\t}\n}"
                        fname = "fault_" + str_index + "_" + "nodename" + "__checkpoint_" + str(checkpoint_linked) + ".do"
                    else:       #event-driven injection (on trigger expression)
                        inj_script += "\nset ExecTime " + str(int(genconf.std_workload_time*scale_factor)) + "ns"
                        inj_script += "\nset InjTime {"
                        for t in inj_time:
                             inj_script += str(int(t)) + "ns "
                        inj_script += "}"
                        inj_script += "\n\nwhen {" + fconfig.trigger_expression + "} {\n\tforeach i $InjTime {\n\t\twhen \"\\$now >= $i\" {\n\t\t\tputs \"Time: $::now: Injection of " + fconfig.model + "\"\n\t\t\t" + c[1] + "\n\t\t}\n\t}\n}"
                        fname = "fault_" + str_index + "_" + "nodename" + "__checkpoint_0" + ".do"
                    inj_script += "\nwhen \"\$now >= $ExecTime\" { force -freeze "+ (toolconf.finish_flag if genconf.finish_flag == '' else genconf.finish_flag) + " 1 }"
                    inj_script += "\n\ndo " + toolconf.list_init_file
                    #inj_script += "\nrun $ExecTime" + "\nforce -freeze " + (toolconf.finish_flag if genconf.finish_flag == '' else genconf.finish_flag) + " 1" + "\nrun [scaleTime $ExecTime 0.05]"
                    inj_script +=  "\nrun [scaleTime $ExecTime 1.05]"
                    inj_script += "\nwrite list " + toolconf.result_dir + "/dump_" + str_index + "_nodename.lst"
                    inj_script += "\nquit\n"

                    robust_file_write(fname, inj_script)
                    sys.stdout.write('Stored script: %6d\r' % (script_index))
                    sys.stdout.flush() 
                    fdesclog_content += "\n" + str(script_index) + ";{" + c[0] + "};" + instance.type + ";" + fconfig.model + fconfig.modifier + ";" + fconfig.forced_value + ";" + str(fconfig.duration) + ";" + str(inj_time[0]) + ";" + str(int(genconf.std_workload_time*scale_factor)-int(inj_time[0])) 
                    if c[2] != None:
                        fdesclog_content += ';{0:.2f};{1:d};{2:s};'.format(c[2].total_time, c[2].effective_switches, c[2].profiled_value)
                    else:
                        fdesclog_content += ';None;None;None;'
                    script_index += 1
                    fdesclog_content += fconfig.trigger_expression.replace(';',' ').replace('&apos','')+';'

    robust_file_write(os.path.join(conf.work_dir, toolconf.result_dir, "_summary.csv"), fdesclog_content)    
    return(script_index)






#-------------------------
# Returns the list of fault injection scripts for each injection case in the dictionary applicable to tuple {INSTANCE, FCONFIG}
#-------------------------

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
