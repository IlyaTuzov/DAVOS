#!python
import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import shutil
import time
import glob
import cgi
import cgitb
import subprocess

FilterDumpVectorsByDelta = True

class RenameItem:
    def __init__(self, ifrom="", ito=""): 
        self.ifrom = ifrom
        self.ito = ito
    def to_string(self):
        return('From: ' + self.ifrom + ", To: " + self.ito)
#_________________________________________________________________________________

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
        self.script_items = []
    
    def put_data(self, idata):
        self.data_items.append(idata)
        
    def put_comment(self, idata):
        self.put_data("\n<div class = \"comment\">\n" + idata + "\n</div>")
    
    def put_script(self, iscript):
        self.script_items.append(iscript)
    

    def to_string(self):
        content = "<!DOCTYPE HTML>\n<html>\n<head>\n<meta charset=\"utf-8\">"
        content += "\n<title>" + self.title + "</title>"
        for s in self.js_files:
            content += "\n<script type=\"text/javascript\" src=\"" + s + "\"></script>"
        content += "\n<link rel=\"stylesheet\" type=\"text/css\" href=\"" + self.css_file + "\">"
        content += "\n</head>\n<body>"
        for c in self.data_items:
            content += "\n" + c
        content += "<script>"
        for c in self.script_items:
            content += '\n' + c
        content += "\n</script>\n</body>\n</html>"
        return(content)
            
            
    def write_to_file(self, fname):
        content = "<!DOCTYPE HTML>\n<html>\n<head>\n<meta charset=\"utf-8\">"
        content += "\n<title>" + self.title + "</title>"
        for s in self.js_files:
            content += "\n<script type=\"text/javascript\" src=\"" + s + "\"></script>"
        content += "\n<link rel=\"stylesheet\" type=\"text/css\" href=\"" + self.css_file + "\">"
        content += "\n</head>\n<body>"
        for c in self.data_items:
            content += "\n" + c
        content += "<script>"
        for c in self.script_items:
            content += '\n' + c
        content += "\n</script>\n</body>\n</html>"
        with open(fname, 'w') as hpage:
            hpage.write(content)
            
    
class HtmlRef:
    def __init__(self, href, text):
        self.href = href
        self.text = text
    def to_string(self):
        return( "\n<a href=\"" + self.href + "\">" + self.text + "</a>" )
    
    
val_pattern = re.compile("[0-9a-zA-Z\.\+\-\*]+")

def find_between( s, first, last ):
    try:
        start = s.index( first ) + len( first )
        end = s.index( last, start )
        return s[start:end]
    except ValueError:
        return ""


class SimVector:
    def __init__(self, time=0.0, delta = 0):
       #time is supposed to be float %.2
       self.time = 0.0
       self.delta = 0
       self.internals = []
       self.outputs = []

    def build_from_string(self, intern_num, output_num, str_data):
        clm = re.findall(val_pattern, str_data)
        if(len(clm) < intern_num + output_num + 2):
            print "build_from_string err: line is not complete"
            key = input("Press any key to continue: ")
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
        
    
    def normalize_array_labels(self, dumpfilename):
        if not os.path.exists(dumpfilename):
            return(None)
        with open(dumpfilename, 'r') as dumpfile:
            lines = dumpfile.readlines()
        for l in lines:
            if re.match('^\s*?[0-9]+', l):
                clm = re.findall("[0-9a-zA-Z\.\+\-\*{}]+", l)
                data_ind = 2
                normalized_internal_labels = []
                for label_i in range(len(self.internal_labels)):
                    if (clm[data_ind]).find('{') >= 0 :
                        arr_max_ind = 0
                        while (clm[data_ind + arr_max_ind]).find('}') < 0:
                            arr_max_ind += 1
                        for c in range(0,arr_max_ind+1, 1):
                            normalized_internal_labels.append('{0}[{1}]'.format(self.internal_labels[label_i], str(c)))
                            data_ind += 1
                    else:
                        normalized_internal_labels.append(self.internal_labels[label_i])
                        data_ind += 1
                normalized_output_labels = []
                for label_i in range(len(self.output_labels)):
                    if (clm[data_ind]).find('{') >= 0 :
                        arr_max_ind = 0
                        while (clm[data_ind + arr_max_ind]).find('}') < 0:
                            arr_max_ind += 1
                        for c in range(0,arr_max_ind+1, 1):
                            normalized_output_labels.append('{0}.format({1})'.format(self.output_labels[label_i], str(c)))
                            data_ind += 1
                    else:
                        normalized_output_labels.append(self.output_labels[label_i])
                        data_ind += 1
                self.internal_labels = normalized_internal_labels
                self.output_labels = normalized_output_labels
                return   
            
             
    #input - dump file *.lst
    #result - self.vectors
    def build_vectors_from_file(self, fname):
        if not os.path.exists(fname):
            return(None)
        self.caption = fname
        with open(fname, 'r') as dumpfile:
            lines = dumpfile.readlines()
        for l in lines:
            if re.match('^\s*?[0-9]+', l.replace('{','').replace('}','')):
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
        
    def get_vector_by_time(self, itime, idelta):
        if FilterDumpVectorsByDelta == False:
            for v in self.vectors:
                if((v.time == itime) and (v.delta == idelta)):
                    return(v)
        else:
            for v in self.vectors:
                if v.time == itime:
                    return(v)
        return(None)
    
    def compare_to_html(self, refdump, req_args, fname=''):
        afrom = 0 if req_args['from'] < 0 else req_args['from']
        ato =   len(self.vectors) if req_args['to'] > len(self.vectors) else req_args['to']
        nrows = ato - afrom + 1 #len(self.vectors)
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
            
                    
        for i in range(afrom, ato, 1):
            itime = self.vectors[i].time
            idelta = self.vectors[i].delta
            htable.put_data(i-afrom, 0, str(itime))
            htable.put_data(i-afrom, 1, str(idelta))            
            refvector = refdump.get_vector_by_time(itime, idelta)
            for j in range(0, len_int, 1):
                htable.put_data(i-afrom,2+j, self.vectors[i].internals[j])
                htable.set_class(i-afrom,2+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].internals[j] == refvector.internals[j]):
                        htable.set_class(i-afrom,2+j,"pass")
                    else:
                        htable.set_class(i-afrom,2+j,"fail")
            for j in range(0, len_out, 1):
                htable.put_data(i-afrom,2+len_int+j, self.vectors[i].outputs[j])
                htable.set_class(i-afrom,2+len_int+j,"nomatch")
                if(refvector != None):
                    if(self.vectors[i].outputs[j] == refvector.outputs[j]):
                        htable.set_class(i-afrom,2+len_int+j,"pass")
                    else:
                        htable.set_class(i-afrom,2+len_int+j,"fail")                        
        hpage = HtmlPage(self.caption)
        hpage.css_file = "markupstyle.css"
        hpage.js_files.append('jquery-1.12.1.min.js')
        hpage.js_files.append('myscript.js')

        hpage.put_data('<input type = \"text\" id = \"xfrom\" value = \"' + str(afrom)  +'\" >')
        hpage.put_data('<input type = \"text\" id = \"xto\" value = \"'+ str(ato) +'\" >')
        hpage.put_data('<button onclick=\"update()\">View trace vectors</button><div>&nbsp;Max Index Range: 0 to ' + str(len(self.vectors)) + '</div>')
        
        
        req0 = '\nvar a = (document.getElementById(\"xfrom\").value).toString(); \nvar b = (document.getElementById(\"xto\").value).toString();'        
        req1 = '\nreq=\"dumptrace.py?config={}&dump={}\"'.format(req_args['config'], req_args['dump']) + '+ \"&from=\" + a + \"&to=\" + b;'        
        hpage.put_script('function update(){  ' + req0 + req1 + '\nwindow.location =req; }')
        
        
        hpage.put_data(htable.to_string())
        hpage.put_data(self.get_highlight_comment())
        if(fname != ''):
            hpage.write_to_file(fname)
        return(hpage.to_string())
    
    def get_highlight_comment(self):
        res = HtmlTable(1, 3, "Highlighting Options")
        res.put_data(0,0,"Match")
        res.set_class(0,0,"pass")
        res.put_data(0,1,"Mismatch (error/failure)")
        res.set_class(0,1,"fail")
        res.put_data(0,2,"Unexpected transition (time point not in reference)")
        res.set_class(0,2,"nomatch")
        return("<br><hr>"+res.to_string_no_header())
        
    
    def get_closest_forward(self, ivect):
        if FilterDumpVectorsByDelta == False:
            for v in self.vectors:
                if( (v.time + float(v.delta)/1000.0) >= (ivect.time + float(ivect.delta)/1000.0) ):
                    return(v)
        else:
            for v in self.vectors:
                if v.time  >= ivect.time:
                    return(v)
        return(None)
    
    def get_first_fail_vector(self, refdump):
        for v in self.vectors:
            vref = refdump.get_closest_forward(v)
            for i in range(0, len(v.outputs), 1):
                if(v.outputs[i] != vref.outputs[i]):
                    return(v)
        return(None)
    
    def get_forward_by_key(self, itime, idelta, ikey, ival):
        vname, c_index = self.get_index_by_label(ikey)
        if FilterDumpVectorsByDelta == False:
            for v in self.vectors:
                if( (v.time + float(v.delta)/1000.0) >= (itime + float(idelta)/1000.0) ):
                    if(v.internals[c_index] == ival):
                        return(v)
        else:
            for v in self.vectors:
                if v.time >= itime:
                    if(v.internals[c_index] == ival):
                        return(v)
        return(None)
    
    
    def get_first_mismatch(self, idump, inj_time):
        for v in self.vectors:
            if(v.time < inj_time):
                continue
            c = idump.get_vector_by_time(v.time, v.delta)
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
            new_output_label_list.append(jn.join_label)
            
        for v in self.vectors:
            new_outputs = []
            for jn in join_group_list.group_list:
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
            for i in range(0, len(self.vectors), 1):
                if(self.vectors[i].internals[c_index] == val):
                    return(self.vectors[i])
        if(vname == 'outputs'):
            for i in range(0, len(self.vectors), 1):
                if(self.vectors[i].outputs[c_index] == val):
                    return(self.vectors[i])        
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


class ToolOptions:
    def __init__(self, xnode=None):
        if xnode is None:
            self.script_dir = "./iscripts"
            self.checkpoint_dir = "./icheckpoints"
            self.result_dir = "./irespack"
            self.log_dir = "./ilogs"
            self.code_dir = "./code"
            self.injnode_list = "./code/SimNodes.xml"
            self.list_init_file = "./code/simInitModel.do"
            self.par_lib_path = "./code/ISE_PAR"
            self.reference_file = "reference.lst"
            self.std_start_checkpoint = "startpoint.sim"
            self.archive_tool_script = "zip -r"
            self.rtl_parse_script = "simpy_rtl_nodes.do"
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
        self.rtl_parse_script = xnode.get('rtl_parse_script', "simpy_rtl_nodes.do")
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
    
    
cgitb.enable()
call_dir = os.getcwd()
print "Content-type:text/html\r\n\r\n"
tree = ET.parse(os.path.join(call_dir,'config.xml')).getroot()

toolconf = ToolOptions()


form = cgi.FieldStorage()
work_dir = os.path.join(call_dir, form.getvalue('config'))
dump_fname = os.path.join(work_dir, toolconf.result_dir, form.getvalue('dump'))
ref_fname = os.path.join(work_dir, toolconf.result_dir, toolconf.reference_file)
dumppack = "RESPACK_{0}.zip".format(form.getvalue('config')) #glob.glob('*{0}.zip'.format(form.getvalue('config')))[0]

#extract dumps from zip
if not os.path.exists(work_dir): os.mkdir(work_dir)
s = os.path.join(work_dir, toolconf.result_dir)
if(not os.path.exists(s)):
    os.mkdir(s)
z = os.getcwd()

unzip_script = 'unzip -o {0} -d {1} \"{2}/{3}\" \"{4}/{5}\" \"{6}\"> unzip.log'.format(dumppack, work_dir, toolconf.result_dir.replace('./',''), form.getvalue('dump'), toolconf.result_dir.replace('./',''), toolconf.reference_file, toolconf.list_init_file.replace('./','')) 
proc = subprocess.Popen(unzip_script, shell=True)
proc.wait()
os.chdir(z)


rename_list = []
renamelistnode = tree.findall('DAVOS')[0].findall('SBFI')[0].findall('Analyzer')[0].findall('rename_list')[0]
for c in renamelistnode.findall('item'):
    x = RenameItem(c.get('from'), c.get('to'))
    rename_list.append(x)

join_group_list = JoinGroupList()
join_group_list.init_from_tag(tree.findall('DAVOS')[0].findall('SBFI')[0].findall('Analyzer')[0].findall('join_groups')[0])

reference_dump = simDump()
reference_dump.build_labels_from_file(os.path.join(work_dir, toolconf.list_init_file), rename_list)
reference_dump.normalize_array_labels(ref_fname)
reference_dump.build_vectors_from_file(ref_fname)
initial_internal_labels, initial_output_labels = reference_dump.get_labels_copy()    
reference_dump.join_output_columns(join_group_list)

inj_dump = simDump()
inj_dump.set_labels_copy(initial_internal_labels, initial_output_labels)
inj_dump.build_vectors_from_file(dump_fname)
inj_dump.join_output_columns(join_group_list.copy())
inj_dump.caption = form.getvalue('dump')


req_args = dict()
req_args['config'] = form.getvalue('config')
req_args['dump'] = form.getvalue('dump')
req_args['from'] = int(form.getfirst('from', '0'))
req_args['to'] = int(form.getfirst('to', '100'))


content = inj_dump.compare_to_html(reference_dump, req_args)
print(content)

