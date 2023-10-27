# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Exports a design-space exploration report
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import lxml
import shutil
import glob
import string


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
        if row == None: row = self.rownum()-1
        if col == None: row = self.colnum()-1

        if( col < len(self.columns) ):
            if( row < len(self.columns[0]) ):
                self.columns[col][row] = data
            else:
                print("Table: "+self.name + " : put data: " + str(data) + " : Row index " + str(row) + " not defined")
        else:
            print("Table: "+self.name + " : put data: " + str(data) + " : Column index " + str(col) + " not defined")
            
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
        labels = self.snormalize(lines[1].rstrip(itemsep).split(itemsep))
        for l in labels:
            self.add_column(l)
        for i in range(2, len(lines), 1):
            c = self.snormalize(lines[i].rstrip(itemsep).split(itemsep))
            self.add_row(c)
    
    def to_html_table(self, tname):
        res = HtmlTable(self.rownum(), self.colnum(), tname)
        for c in range(0, len(self.labels),1):
            res.set_label(c, self.labels[c])
        for r in range(0,self.rownum(),1):
            for c in range(0,self.colnum(),1):
                res.put_data(r,c, self.get(r,c))
        return(res)
    
    
    def process_factor_setting(self, factor_label_prefix = 'X',factor_seperator=','):
        ptn = factor_label_prefix + '[0-9]+'+factor_seperator
        fcolumn_num = 0
        vect_len = 0
        #find the column with factors
        for i in range(0,len(self.labels),1):
            buf = re.findall(ptn, self.labels[i])
            vect_len = len(buf)
            if(vect_len > 0):
                fcolumn_num = i
                break        
        print 'Factor Column: ' + str(fcolumn_num) + ', Vect Len: ' + str(vect_len)
        v_ones =  [0] * vect_len
        v_zeros = [0] * vect_len
        v_dontcare = [0] * vect_len
        for i in range(0, self.rownum(), 1):
            f_vect = self.get(i, fcolumn_num).split(factor_seperator)
            #print f_vect
            for j in range(0,vect_len,1):
                if(f_vect[j].find('1') >= 0): v_ones[j]+=1
                elif(f_vect[j].find('0') >= 0): v_zeros[j]+=1
                elif(f_vect[j].find('-') >= 0): v_dontcare[j]+=1
        print v_ones
        print v_zeros
        content_ones = ''
        content_zeros = ''
        content_dontcare = ''
        for j in range(0,vect_len,1):
            amt = v_ones[j] + v_zeros[j] + v_dontcare[j]
            content_dontcare += str('%3s' % str(int(round(float(100.0*v_dontcare[j])/float(amt)))) ) + ','
            if(v_ones[j] + v_zeros[j] > 0):
                content_ones  += str('%3s' % str(int(round(float(100.0*v_ones[j])/float(amt)))) ) + ','
                content_zeros += str('%3s' % str(int(round(float(100.0*v_zeros[j])/float(amt)))) ) + ','
            else:
                content_ones  += '  -,'
                content_zeros += '  -,'
        print content_ones
        print content_zeros
        print content_dontcare
        for i in range(0, self.rownum(), 1):
            self.put(i,fcolumn_num,  '  ' + self.get(i,fcolumn_num))
        self.add_row()
        self.put(self.rownum()-1,fcolumn_num-1,'[%] 1: ')
        self.put(self.rownum()-1,fcolumn_num,content_ones)
        self.add_row()
        self.put(self.rownum()-1,fcolumn_num-1,'[%] 0: ')        
        self.put(self.rownum()-1,fcolumn_num,content_zeros)
        self.add_row()
        self.put(self.rownum()-1,fcolumn_num-1,'[%] -: ')        
        self.put(self.rownum()-1,fcolumn_num,content_dontcare)        
        return(content_zeros, content_ones, content_dontcare)
    
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
            
    def add_row(self):
        cnum = self.rows[0].get_size()
        self.rows.append(HtmlTableRow(cnum))
    
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
   
        
class HtmlPage:
    def __init__(self, title = ""):
        self.css_file = ""
        self.js_files = []
        self.data_items = []
        self.title = title
    
    def put_data(self, idata):
        self.data_items.append(idata)
        
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
    def __init__(self, href, text, a_class=''):
        self.href = href
        self.text = text
        self.a_class = a_class
        
    def to_string(self):
        res = "<a "
        if(self.a_class != ""):
            res += " class = \"" + self.a_class + "\" "
        res += "href=\"" + self.href + "\">" + self.text + "</a>"
        return( res )
    
        


#________________________________________________________________________________
#cdiv_pattern = re.compile("\s+")
val_pattern = re.compile("[0-9a-zA-Z\.\+]+")

def find_between( s, first, last ):
    try:
        start = s.index( first ) + len( first )
        end = s.index( last, start )
        return s[start:end]
    except ValueError:
        return ""
    
    
class GenConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.impl_goals_config_file = ""
            self.matlab_summary_filename = ""
            self.mcdm_summary_filename = ""
            self.pareto_summary_filename = ""
            self.report_dir = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.impl_goals_config_file = xnode.get('impl_goals_config_file')
        self.matlab_summary_filename = xnode.get('matlab_summary_filename')
        self.mcdm_summary_filename = xnode.get('mcdm_summary_filename')
        self.report_dir = xnode.get('report_dir')
        self.pareto_summary_filename = xnode.get('pareto_summary_filename','')
        return(0)

    def to_string(self):
        res = "Generic Config: "
        res+="\nimpl_goals_config_file = " + self.impl_goals_config_file        
        res+="\nmatlab_summary_filename = " + self.matlab_summary_filename
        res+="\nmcdm_summary_filename = " + self.mcdm_summary_filename
        res+="\nreport_dir = " + self.report_dir
        res+="\npareto_summary_filename = " + self.pareto_summary_filename        
        return(res)    

class Config:
    def __init__(self, xnode):
        if xnode is None:
            self.label = ""
            self.path = ""
        else:
            self.build_from_xml(xnode)
            
    def build_from_xml(self, xnode):
        self.label = xnode.get('label')
        self.path = xnode.get('path')
        return(0)

    def to_string(self):
        return("Config [" +  self.label + "]: " + self.path)  


class ModelItem:
    def __init__(self, xnode):
        #from Matlab summary
        self.Config_Label = ""
        self.Variable = ""
        self.Distribution = ""
        self.Significant_Factors = ""
        self.Rsquared_Ordinary = ""
        #from analysis tool summary
        self.Min_Val = ""
        self.Max_Val = ""
        self.Config_Min = ""
        self.Config_Max = ""
        if xnode is not None:
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
        self.Variable = xnode.get('Variable')
        self.Distribution = xnode.get('Distribution')
        self.Significant_Factors = xnode.get('Significant_Factors')
        self.Rsquared_Ordinary = xnode.get('Rsquared_Ordinary')
        
    def to_string(self):
        res = "\n\nRegression Model, Config = " + self.Config_Label
        res += "\n\tVariable: " +  self.Variable
        res += "\n\tDistribution: " +  self.Distribution
        res += "\n\tSignificant_Factors: " +  self.Significant_Factors
        res += "\n\tRsquared_Ordinary: " +  self.Rsquared_Ordinary
        res += "\n\tVMin_Val: " +  self.Min_Val
        res += "\n\tMax_Val: " +  self.Max_Val
        res += "\n\tConfig_Min: " +  self.Config_Min
        res += "\n\tConfig_Max: " +  self.Config_Max
        return(res)

class GoalItemSolution:
    def __init__(self, ilabel, xnode):
        self.label = ilabel
        self.Score = ""
        self.Config = ""
        self.Variables = dict()
        if xnode is not None:
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
        self.Score = xnode.get('Score')
        self.Config = xnode.get('Config')
        for v in xnode.findall('Variable'):
            v_name = v.get('name')
            v_value = v.get('value')
            self.Variables[v_name] = v_value
    
    def to_string(self):
        res = "\n" + self.label 
        res += "\n\tScore: " + self.Score + "\n\tConfig: " + self.Config
        for k,v in self.Variables.items():
            res += "\n\t\tVariable: " + k + "\tValue: " + v
        return(res)
        

class GoalItem:
    def __init__(self, xnode):
        self.name = ""
        self.Best = None
        self.Worst = None
        self.label = ""     #circuit label: B_01, B_02...
        if xnode is not None:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.get('name')
        xnode_best = xnode.findall('Best')
        self.Best = GoalItemSolution('Best', xnode_best[0])
        xnode_worst = xnode.findall('Worst')
        self.Worst =  GoalItemSolution('Worst', xnode_worst[0])
    
    def to_string(self):
        res = "["+self.label + "]\tGoal: " + self.name
        res += self.Best.to_string()
        res += self.Worst.to_string()
        return(res)
        
class VariableGoal:
    def __init__(self, xnode):
        self.name = ""
        self.goal = ""
        self.weight = ""
        if xnode is not None:
            self.build_from_xml(xnode)
 
    def build_from_xml(self, xnode):
        self.name = xnode.get('name')
        self.goal = xnode.get('goal')
        self.weight = xnode.get('weight')
    
    def to_string(self):
        return("Variable: " + self.name + "\tgoal: " + self.goal + "\tweight: " + self.weight)


class ImplGoalConfig:
    def __init__(self, xnode):
        self.name = ""
        self.Variables = []
        if xnode is not None:
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
        self.name = xnode.get('name')
        for c in xnode.findall('variable'):
            self.Variables.append(VariableGoal(c))
    
    def to_string(self):
        res = "\n\nGoal: " + self.name
        for c in self.Variables:
            res += "\n\t" + c.to_string()
        return(res)
    
        
class ParetoSet:
    def __init__(self, xnode):
        self.name = ""
        self.label = ""     #circuit label: B_01, B_02...        
        self.algorithm = ""
        self.csv_file = ""
        self.html_page_link = ""
        self.num_points = 0
        self.content_ones = ''
        self.content_zeros = ''
        self.content_dontcare = ''
        if xnode is not None:
            self.build_from_xml(xnode)
    
    def build_from_xml(self, xnode):
       self.algorithm = xnode.get('algorithm')
       self.csv_file = xnode.get('file')
       
    def to_string(self):
        return("\n\nParetoSet: "+ self.name + "\n\tAlgorithm: "+ self.algorithm + "\n\tCircuit: " + self.label + "\n\tcsv_file: " + self.csv_file + "\n\tHTML_page_link: " + self.html_page_link)


call_dir = os.getcwd()
config_file_path = os.path.join(os.getcwd(), sys.argv[1])
print "CONFIG PATH: " + config_file_path
#1. Parse configuration file
iconfig = sys.argv[1]
tree = ET.parse(iconfig).getroot()
genconf = GenConfig(tree.findall('generic')[0])
print genconf.to_string()
configlist = []
Full_Factor_Set = ""
for xnode in tree.findall('config'):
    configlist.append(Config(xnode))

#2. Parse summary files
ModelList = []
ImplList = []
GoalList = []
for c in configlist:
    print c.to_string()
    f_matlab_summary = os.path.join(call_dir, c.path,genconf.matlab_summary_filename)
    f_mcdm_summary = os.path.join(call_dir, c.path,genconf.mcdm_summary_filename)
    matlab_tree = ET.parse(f_matlab_summary).getroot()
    mcdm_tree = ET.parse(f_mcdm_summary).getroot()
    mcdm_items = mcdm_tree.findall('Model')
    Full_Factor_Set = mcdm_tree.get('Full_Factor_Set')
    #Parse MinMax for response variables
    for xnode in matlab_tree.findall('Model'):
        item = ModelItem(xnode)
        item.Config_Label = c.label
        for m in mcdm_items:
            if(m.get('Name') == item.Variable + '_' + item.Distribution):
                item.Min_Val = m.get('Min_Val')
                item.Max_Val = m.get('Max_Val')
                item.Config_Min = m.get('Config_Min')
                item.Config_Max = m.get('Config_Max')
                break
        if(item.Min_Val == ""):
            raw_input("Model "+item.Variable + '_' + item.Distribution+" Not Found in file: " + f_mcdm_summary)
        ModelList.append(item)
    #Parse ImplementationGoals
    for xnode in mcdm_tree.findall('Goal'):
        goal_item = GoalItem(xnode)
        goal_item.label = c.label
        ImplList.append(goal_item)
for m in ModelList:
    print m.to_string()
for m in ImplList:
    print m.to_string()

impl_goals_root = ET.parse(os.path.join(call_dir, genconf.impl_goals_config_file)).getroot()
for c in impl_goals_root.findall('goal'):
    GoalList.append(ImplGoalConfig(c))
for i in GoalList:
    print i.to_string()


#Create report dir
std_css_fname = "./interface/markupstyle.css"
pareto_dir = "./pareto"
if(not os.path.exists(os.path.join(call_dir,genconf.report_dir))):
    os.mkdir(os.path.join(call_dir,genconf.report_dir))
if(not os.path.exists(os.path.join(call_dir,genconf.report_dir, pareto_dir))):
    os.mkdir(os.path.join(call_dir,genconf.report_dir, pareto_dir))
shutil.copyfile(os.path.join(call_dir, std_css_fname), os.path.join(os.path.join(call_dir,genconf.report_dir,std_css_fname)))


#3. Process Pareto Sets
print "\n\n\t\tPareto Goals:\n\n"
ParetoList = []
SCircuits = set()
SParetoGoals= set()
SParetoAlgorithms = set()
if(genconf.pareto_summary_filename != ''):
    for c in configlist:
        print c.to_string()
        SCircuits.add(c.label)
        pareto_summary = os.path.join(call_dir, c.path, genconf.pareto_summary_filename)
        if(os.path.isfile(pareto_summary)):
            pareto_tree = ET.parse(pareto_summary).getroot()
            for xnode in pareto_tree.findall('Pareto_Config'):
                for setnode in xnode.findall('Pareto_Set'):
                    s = ParetoSet(setnode)
                    s.name = xnode.get('name')
                    s.label = c.label
                    SParetoGoals.add(s.name)
                    SParetoAlgorithms.add(s.algorithm)
                    s.html_page_link = os.path.join(pareto_dir,s.label+"_"+s.csv_file.replace('.csv','.html'))
                    ncsv = os.path.join(pareto_dir,s.label+"_"+s.csv_file)
                    shutil.copy2(os.path.join(call_dir, c.path,s.csv_file), os.path.join(call_dir,genconf.report_dir, ncsv))
                    s.csv_file = ncsv
                    #Convert csv to html
                    sh = Table(s.html_page_link)
                    sh.build_from_csv(os.path.join(call_dir,genconf.report_dir, ncsv))
                    s.num_points = sh.rownum()
                    (s.content_zeros, s.content_ones, s.content_dontcare) = sh.process_factor_setting()
                    stab = sh.to_html_table('Circuit: '+s.label+', Pareto Goal: ' + s.name + ", Algorithm: " + s.algorithm)
                    spage = HtmlPage('Circuit: '+s.label+', Pareto Goal: ' + s.name + ", Algorithm: " + s.algorithm)
                    spage.css_file = "../" + std_css_fname
                    spage.put_data(stab.to_string() + "<br>")
                    spage.write_to_file(os.path.join(call_dir,genconf.report_dir,s.html_page_link))
                    ParetoList.append(s)
    Circuits = list(SCircuits)
    ParetoGoals = list(SParetoGoals)
    Circuits.sort()
    for c in ParetoList:
        print c.to_string()
    raw_input('press any key...')
    for c in Circuits:
        print c
    for c in SParetoGoals:
        print c
    
    
            
    

                

#4. Build report page for MinMax response of variables
minmaxpage_fname = "MinMax.html"
reportpage = HtmlPage(minmaxpage_fname)
reportpage.css_file = std_css_fname

variable_set = set()
distribution_set = set()
for m in ModelList:
    variable_set.add(m.Variable)
    distribution_set.add(m.Distribution)
variable_list = list(variable_set)
distribution_list = list(distribution_set)
variable_list.sort()
distribution_list.sort()
for v in variable_list:
    for d in distribution_list:
        group = []
        for m in ModelList:
            if(m.Variable == v and m.Distribution == d):
                group.append(m)
        if(len(group)>0):
            #Create a Table - Min = "Variable_Distribution" {Config_Label, Rsquared_Ordinary, Min_Val, Config_Min}
            Min_Table = HtmlTable(len(group), 4, "[MIN] Response Variable: " + v + ", Distribution: " + d)
            Min_Table.set_label(0, "Circuit")
            Min_Table.set_label(1, "Rsquared_Ordinary")
            Min_Table.set_label(2, "Min_Val")
            Min_Table.set_label(3, Full_Factor_Set)
            for i in range(0, len(group), 1):
                Min_Table.put_data(i,0,group[i].Config_Label)
                Min_Table.put_data(i,1,group[i].Rsquared_Ordinary)
                Min_Table.put_data(i,2,group[i].Min_Val)
                Min_Table.put_data(i,3,group[i].Config_Min)
            reportpage.put_data(Min_Table.to_string() + "<br>")
            
            Max_Table = HtmlTable(len(group), 4, "[MAX] Response Variable: " + v + ", Distribution: " + d)
            Max_Table.set_label(0, "Circuit")
            Max_Table.set_label(1, "Rsquared_Ordinary")
            Max_Table.set_label(2, "Max_Val")
            Max_Table.set_label(3, Full_Factor_Set)
            for i in range(0, len(group), 1):
                Max_Table.put_data(i,0,group[i].Config_Label)
                Max_Table.put_data(i,1,group[i].Rsquared_Ordinary)
                Max_Table.put_data(i,2,group[i].Max_Val)
                Max_Table.put_data(i,3,group[i].Config_Max)
            reportpage.put_data(Max_Table.to_string() + "<br>")
            reportpage.put_data("<hr><br>")
            
            print("\n\t\tVariable: " + v + ", Distribution: " + d)
            for m in group:
                print(m.Config_Label + "\tMin_Val: " + m.Min_Val + "\t\tConfig_Min: " + m.Config_Min)
            print("\n\t\tVariable: " + v + ", Distribution: " + d)
            for m in group:
                print(m.Config_Label + "\tMax_Val: " + m.Max_Val + "\t\tConfig_Max: " + m.Config_Max)
reportpage.write_to_file(os.path.join(call_dir,genconf.report_dir,minmaxpage_fname))


index_goals_table = HtmlTable(len(GoalList),1+len(GoalList[0].Variables),"Implementation Goals")
index_goals_table.set_label(0,"Goal")
for i in range(0,len(GoalList[0].Variables),1):
    index_goals_table.set_label(1+i, GoalList[0].Variables[i].name)
for i in range(0,len(GoalList),1):
    for j in range(0,len(GoalList[0].Variables),1):
        index_goals_table.put_data(i, 1+j, GoalList[i].Variables[j].goal + "\t" + str('%.2f' % float(GoalList[i].Variables[j].weight)) )
        
        

summary_tbl =   Table( "Summary")
summary_tbl.add_column("Scenario")
summary_tbl.add_column("B/W")
summary_tbl.add_column("Score")
vlist = set()
for item in ImplList:
    for k, v in item.Best.Variables.items():
        vlist.add(k)
vlist = list(vlist)
vlist.sort()
for item in vlist:
    summary_tbl.add_column(item.replace('_gamma','').replace('_poisson','').replace('_normal','').replace('_inverse gaussian',''))
summary_tbl.add_column(Full_Factor_Set)

for ind in range(0, len(ImplList), 1):
    summary_tbl.add_row()
    summary_tbl.put(None, 0, ImplList[ind].label + '_' + ImplList[ind].name)
    summary_tbl.put(None, 1, 'Best')
    summary_tbl.put(None, 2, ImplList[ind].Best.Score)
    for item in range(0,len(vlist),1):
        if vlist[item] in ImplList[ind].Best.Variables:
            val = ImplList[ind].Best.Variables[vlist[item]]
            summary_tbl.put(None, 3+item, str('%.2e'%float(val)) if float(val) > float(20000.0) else str(val))
        else:
            summary_tbl.put(None, 3+item, '-')
    summary_tbl.put(None, 3+len(vlist), ImplList[ind].Best.Config)

    summary_tbl.add_row()
    summary_tbl.put(None, 0, '')
    summary_tbl.put(None, 1, 'Worst')
    summary_tbl.put(None, 2, ImplList[ind].Worst.Score)
    for item in range(0,len(vlist),1):
        if vlist[item] in ImplList[ind].Best.Variables:
            val = ImplList[ind].Worst.Variables[vlist[item]]
            summary_tbl.put(None, 3+item, str('%.2e'%float(val)) if float(val) > float(20000.0) else str(val))
        else:
            summary_tbl.put(None, 3+item, '-')
    summary_tbl.put(None, 3+len(vlist), ImplList[ind].Worst.Config)

gpage = HtmlPage('Summary')
gpage.css_file = std_css_fname
summary_tbl.process_factor_setting()
gpage.put_data(summary_tbl.to_html_table("Summary").to_string() +"<br>")
gpage.put_data("<hr><br>")
gpage.write_to_file(os.path.join(call_dir,genconf.report_dir,"Summary.html"))





           
              
        
        
#5. Build HTML page for each implementation goal
for g in range(0,len(GoalList),1):
    c = GoalList[g]
    group = []
    for m in ImplList:
        if(m.name == c.name):
            group.append(m)
    gpage = HtmlPage(c.name)
    gpage.css_file = std_css_fname
    
    best_tbl =  Table( c.name + ": Best")
    worst_tbl = Table( c.name + ": Worst")
    best_tbl.add_column("Circuit")
    worst_tbl.add_column("Circuit")
    best_tbl.add_column("Best Score")
    worst_tbl.add_column("Worst Score")
    best_tbl.add_column(Full_Factor_Set)
    worst_tbl.add_column(Full_Factor_Set)
    
    for i in range(0,len(group),1):
        best_tbl.add_row()
        worst_tbl.add_row()
    for i in range(0, len(c.Variables),1):
        best_tbl.add_column(c.Variables[i].name)
        worst_tbl.add_column(c.Variables[i].name)
    for i in range(0, len(group), 1):
        best_tbl.put(i, 0, group[i].label)
        worst_tbl.put(i, 0, group[i].label)
        best_tbl.put(i, 1, group[i].Best.Score)
        worst_tbl.put(i, 1, group[i].Worst.Score)
        best_tbl.put(i, 2, group[i].Best.Config)
        worst_tbl.put(i, 2, group[i].Worst.Config)
        for j in range(0, len(c.Variables),1):
            best_tbl.put(i,3+j, str('%.2e'%float(group[i].Best.Variables[c.Variables[j].name])))
            worst_tbl.put(i,3+j, str('%.2e'%float(group[i].Worst.Variables[c.Variables[j].name])))
    
    best_tbl.process_factor_setting()
    worst_tbl.process_factor_setting()
    gpage.put_data(best_tbl.to_html_table(c.name + ": Best").to_string() +"<br>")
    gpage.put_data("<hr><br>")
    gpage.put_data(worst_tbl.to_html_table(c.name + ": Worst").to_string() +"<br>")
    gpage.write_to_file(os.path.join(call_dir,genconf.report_dir,c.name+".html"))
    index_goals_table.put_data(g,0, HtmlRef('./'+c.name+'.html', c.name).to_string() )




index_page = HtmlPage('index.html')
index_page.css_file = std_css_fname
index_page.put_data(index_goals_table.to_string())
index_page.put_data("<hr><br>")
index_page.put_data(HtmlRef('./'+minmaxpage_fname, "ANOVA & Linear Regression (click to observe)").to_string())
index_page.put_data("<hr><br>")
if(genconf.pareto_summary_filename != ''):
    for al in SParetoAlgorithms:
        T = HtmlTable(len(Circuits)+1, 1+len(ParetoGoals), 'Pareto Optimal: ' + al)
        T.set_label(0,'Circuit')
        for c in range(0,len(ParetoGoals),1):
            T.set_label(c+1, ParetoGoals[c])
        for r in range(0, len(Circuits), 1):
            T.put_data(r,0,Circuits[r])        
            for c in range(0, len(ParetoGoals), 1):
                for k in ParetoList:
                    if(k.algorithm == al and k.label == Circuits[r] and k.name == ParetoGoals[c]):
                        T.put_data(r,c+1, HtmlRef(k.html_page_link, str("%05d" % k.num_points)+" points (html)", "asimple").to_string() + "&nbsp|&nbsp" + HtmlRef(k.csv_file, "download *.CSV", "afile").to_string())
        #Build summary page
        for c in range(0,len(ParetoGoals),1):
            SummaryTable_zeros = HtmlTable(len(Circuits),2,'0 Percentage')
            SummaryTable_zeros.set_label(0,'Circuit')
            SummaryTable_zeros.set_label(1,Full_Factor_Set)
            SummaryTable_ones = HtmlTable(len(Circuits),2, '1 Percentage')
            SummaryTable_ones.set_label(0,'Circuit')
            SummaryTable_ones.set_label(1,Full_Factor_Set)
            
            for r in range(0, len(Circuits), 1):
                SummaryTable_zeros.put_data(r,0,Circuits[r])
                SummaryTable_ones.put_data(r,0,Circuits[r])
                for k in ParetoList:
                    if(k.algorithm == al and k.label == Circuits[r] and k.name == ParetoGoals[c]):
                        SummaryTable_zeros.put_data(r,1,k.content_zeros)
                        SummaryTable_ones.put_data(r,1,k.content_ones)
            summary_page_link = './Pareto_summary_'+al+'_'+ParetoGoals[c]+'.html'
            Summary_page = HtmlPage(summary_page_link)
            Summary_page.css_file = std_css_fname
            Summary_page.put_data(SummaryTable_ones.to_string() + "<hr><br>" + SummaryTable_zeros.to_string())
            Summary_page.write_to_file(os.path.join(call_dir,genconf.report_dir,summary_page_link))
            T.put_data(len(Circuits), c+1, HtmlRef(summary_page_link,'Summary').to_string())
        index_page.put_data(T.to_string())
        index_page.put_data("<hr><br>")
else:
    index_page.put_data('<div class =\"comment\">Pareto Set Not Computed</div><hr><br>')
index_page.write_to_file(os.path.join(call_dir,genconf.report_dir,"index.html"))
