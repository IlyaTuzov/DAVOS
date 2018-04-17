# Server-side logic of interactive querying interface
# Parameters passed by Get/Post method 
# Results returned in XML/JSON format 
# Creates the cache of previosuly returned results
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

#!/Python27/python
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
import sqlite3
import subprocess
import random
from ast import literal_eval as make_tuple


MAX_RESPONCE_ITEMS = int(10000)
MODE = "fast"   #fast / robust


def get_selector(f, k_httpt, k_selector_alias, enquote = False):
    v = f.getvalue(k_httpt,'')
    if v == '': return('')
    elif v.find(':')>=0:
        s = v.split(':')
        v = k_selector_alias + '>' + s[0] + ' AND ' + k_selector_alias + '<' + s[1]
        return(v)
    else:
        if enquote: v = ' '.join(r'"{}"'.format(word) if word.lower() not in ['and','or','not'] else word for word in v.split())
        return(' '+k_selector_alias+'='+v)
    


def xml_markup(attrlist, valuelist, emptyfields=[]):
    if len(attrlist) != len(valuelist[0]):
        return('Error')
    res = ''
    n = len(valuelist) if len(valuelist) < MAX_RESPONCE_ITEMS else MAX_RESPONCE_ITEMS
    
    for v in range (0,n,1):
        res += '\n\n\t<QRItem'
        for i in range(0,len(attrlist),1):
            val = str(valuelist[v][i]) if not attrlist[i] in emptyfields else "" 
            res += '\n\t\t' + attrlist[i] + '=\"' + val + '\"'
        res += '/>'
    
    summarytag = '\n\n<Summary \nmessage=\"'
    summarytag += 'Selected ' + str(len(valuelist)) + ' items, showed ' + str(n) +  ' items\"' if n < len(valuelist) else '\"'
    if n < len(valuelist):
        if 'failuremode' in attrlist:
            ind = attrlist.index('failuremode')
            fmodes = dict()
            for v in valuelist:
                t = v[ind]
                if t in fmodes:
                    fmodes[t] += 1
                else:
                    fmodes[t] = 0
            total = 0
            for k, v  in fmodes.items():
                total += v
            for k, v  in fmodes.items():
                summarytag += '\n\t' + k + '=\"' + str('%.2f' % (v*100.0/total)) + '\"'            
    summarytag += ' />'
    
    return(summarytag + '\n\n' + res+'stop')


class DesignNode:
    def __init__(self, tname):
        self.name = tname
        self.fmc = {'c': 0, 's': 0, 'm': 0, 'l': 0}
        self.fmc_percentage = {'c': 0.0, 's': 0.0, 'm': 0.0, 'l': 0.0}
        self.children = []
    
    def append(self, pth, fm):
        cnode = pth.pop(0)
        xnode = None
        for c in self.children:
            if c.name == cnode:
                xnode = c
                break
        if xnode == None:
            xnode = DesignNode(cnode)
            self.children.append(xnode)    
        xnode.fmc[fm] += 1
        if len(pth) > 0:
            xnode.append(pth, fm)
    
    def normalize(self, relnode):
        total = relnode.fmc['c'] + relnode.fmc['s'] + relnode.fmc['m'] + relnode.fmc['l']
        self.fmc_percentage['c'] = (self.fmc['c'] * 100.0)/total
        self.fmc_percentage['s'] = (self.fmc['s'] * 100.0)/total
        self.fmc_percentage['m'] = (self.fmc['m'] * 100.0)/total
        self.fmc_percentage['l'] = (self.fmc['l'] * 100.0)/total
        for c in self.children:
            c.normalize(relnode)
        
    
            
    def to_JSON(self):
        res = '{\n\"name\": \"' + self.name + '\"' + ',\n\"m\": \"' + str(self.fmc['m']) + '\",\n' + '\"l\": \"' + str(self.fmc['l']) + '\",\n' + '\"s\": \"' + str(self.fmc['s']) + '\",\n' + '\"c\": \"' + str(self.fmc['c']) + '\"'
        res += ',\n\"c_p\": \"' + str('%.2f' % self.fmc_percentage['c']) + '\",\n\"s_p\": \"'+ str('%.2f' % self.fmc_percentage['s']) + '\",\n\"m_p\": \"'+ str('%.2f' % self.fmc_percentage['m']) + '\",\n\"l_p\": \"'+ str('%.2f' % self.fmc_percentage['l']) + '\"'
        if len(self.children) > 0:
            res += ',\n\"children\": ['
            for i in range(0,len(self.children),1):
                res += self.children[i].to_JSON()
                if i < len(self.children) - 1 :
                    res += ',\n'
            res += '\n]'
        res += '\n}'      
        return(res)



    def to_HTML(self, level=0):
        tab = ''
        for i in range(0, level, 1): tab += "    |"
        res = "\n<tr>" + "<td><pre>" + tab+ self.name + "</td></pre>"+ "<td><pre>" + str(self.fmc['m']) + "</td></pre>"+ "<td><pre>" + str(self.fmc['l']) + "</td></pre>"+ "<td><pre>" + str(self.fmc['s']) + "</td></pre>"+ "<td><pre>" + str(self.fmc['c']) + "</td></pre>"
        res += "<td><pre>" + str('%.2f' % self.fmc_percentage['m']) + "</td></pre>"+ "<td><pre>" + str('%.2f' % self.fmc_percentage['l']) + "</td></pre>"+ "<td><pre>" + str('%.2f' % self.fmc_percentage['s']) + "</td></pre>"+ "<td><pre>" + str('%.2f' % self.fmc_percentage['c']) + "</td></pre>"+"</tr>"
        for c in self.children:
            res += c.to_HTML(level+1)
        return(res)







failuremodes_alias = dict([('M', 'Masked_Fault'), ('L', 'Latent_Fault'), ('S', 'Signalled_Failure'), ('C', 'Silent_Data_Corruption')])

fields = [  ('M.Label', 'model', True), 
            ('I.ID', 'eind', False),
            ('T.NodeFullPath', 'target', True),
            ('T.Macrocell', 'instancetype', True) ,
            ('I.FaultModel', 'faultmodel', True),
            ('I.ForcedValue', 'forcedvalue', True),
            ('I.InjectionTime', 'injectiontime', False),
            ('I.InjectionDuration', 'injectionduration', False),
            ('I.ObservationTime', 'observationtime', False),
            ('I.FailureMode', 'failuremode', True),
            ('I.ErrorCount', 'errorcount', False),
            ('I.TrapCode', 'trapcode', True),
            ('I.FaultToFailureLatency', 'latencyfaultfailure', False),
            ('I.Dumpfile', 'dumpfile', True) ]

sql_fields = []
req_fields = []
fdict = dict()
for i in fields:
    sql_fields.append(i[0])
    req_fields.append(i[1])
    fdict[i[0]] = i[1]
    
    
try:
    log = open('log.txt','w')    
    form = cgi.FieldStorage()
    signature = ''
    for k in form.keys():
        if not k in ['action', 'cache']:
            signature +='_' + k + '=' + re.sub("[^a-zA-Z0-9_]","-",form.getvalue(k))
    if not os.path.exists(os.path.join(os.getcwd(), 'cache')):
        os.mkdir(os.path.join(os.getcwd(), 'cache'))    
    log.write(signature)
    
    
    
    if not os.path.exists(os.path.join(os.getcwd(), 'cache', signature)):
        os.mkdir(os.path.join(os.getcwd(), 'cache', signature))
        connection = sqlite3.connect(glob.glob('*.db')[0])
        cursor = connection.cursor()
        cursor.execute('SELECT COUNT(*) FROM Injections')
        c = cursor.fetchone()
        population_size = int(c[0])
        sampling_mode = (form.getvalue('samplesize','').replace(' ', '') != '')
        if sampling_mode:
            if 'randseed' in form.keys():
                if form.getvalue('randseed').isdigit():
                    random.seed(int(form.getvalue('randseed')))
            sample_indicies = random.sample(range(0,population_size), int(form.getvalue('samplesize')) )
            sample_indicies.sort(reverse=True)
            log.write('\nPopulation size: {0}\nSamples [{1}] = {2}'.format(population_size, len(sample_indicies), '\n'.join([str(i) for i in sample_indicies])))
        
        query = """ SELECT {0}
                    FROM Injections I
                    JOIN Models M ON I.ModelID = M.ID
                    JOIN Targets T ON I.TargetID = T.ID 
        """.format(', '.join(sql_fields))
        selector = ['I.Status != \"E\"']
        for i in fields:
            if form.has_key(i[1]):
                selector.append(get_selector(form, i[1], i[0] , i[2]))
        valid_sel_appended = 0
        for c in selector:
            if c != '':
                if valid_sel_appended == 0:
                    query += ' WHERE '
                else:
                    query += ' AND '
                query += c
                valid_sel_appended += 1
        log.write('\n\n'+query)
        log.flush()
        cursor.execute(query)

        #build list of first N rows to show and statistics
        i=0
        listed_ind = 0
        sampled_ind = 0
        listing_content = ''
        statistic_content = '\n\n<Summary '
        fmodes = dict()
        fmodefield_index = req_fields.index('failuremode')
        pathfield_index = req_fields.index('target')
        DesignTree = DesignNode('Root')
        pathsep = re.compile('[/_\.\(\)\[\]]')
        while True:
            rows = cursor.fetchmany(50000)
            if not rows:
                break            
            for c in rows:
                if i&0xFFFF == 0:
                    log.write('\nIndex = {0}'.format(str(i)))
                    log.flush()
                stat_flag = False
                list_flag = False
                #if sampling mode: list item and include into statistics IF it's index has been selected for sampling
                if sampling_mode:
                    if len(sample_indicies) > 0:
                        if i == sample_indicies[-1]:
                            list_flag = (listed_ind < MAX_RESPONCE_ITEMS)
                            stat_flag = True
                            sample_indicies.pop()
                #otherwise - list just first MAX_RESPONCE_ITEMS, but compute statistics for the whole set
                else:
                    stat_flag = True        
                    if i < MAX_RESPONCE_ITEMS:
                        list_flag = True
                
                if list_flag:                
                    listing_content += '\n\n\t<QRItem'
                    for j in range(0,len(req_fields),1):
                        listing_content += '\n\t\t{0} = \"{1}\"'.format(req_fields[j], str(c[j]))
                    listing_content += '/>'
                    listed_ind += 1
                
                if stat_flag:
                    t = c[fmodefield_index]
                    if t in fmodes:
                        fmodes[t] += 1
                    else:
                        fmodes[t] = 1
                    sampled_ind += 1
                    #Update the distribution tree
                    pth = []
                    for p in re.split(pathsep, c[pathfield_index].replace('{','').replace('}','')):
                        if p != '':
                            pth.append(p)
                    DesignTree.append(pth, t.lower())                    
                i+=1                                        
        statistic_content += '\nmessage=\"Items: Retrieved {0}, Sampled {1}, listed {2}, \"'.format(str(i), str(sampled_ind), str(listed_ind))
        total = 0
        for k, v  in fmodes.items():
            total += v
            log.write('\n k: {0} = v: {1}'.format(k, str(v)))
        for k, v  in fmodes.items():
            if k in failuremodes_alias:
                statistic_content += '\n\t' + failuremodes_alias[k] + '_abs=\"' + str(v) + '\"'                
                statistic_content += '\n\t' + failuremodes_alias[k] + '=\"' + str('%.2f' % (v*100.0/total)) + '\"'
        statistic_content += ' />'
        
        DesignTree.fmc = DesignTree.children[0].fmc
        DesignTree.normalize(DesignTree)        
        
        
        #result for action = search 
        with open(os.path.join(os.getcwd(), 'cache', signature,'search.xml'), 'w') as cachefile:
            cachefile.write('<?xml version="1.0" encoding="UTF-8"?>\n<data>' + statistic_content + '\n\n' + listing_content  + "\n\n</data>")
        with open(os.path.join(os.getcwd(), 'cache', signature,'distree.json'), 'w') as cachefile:
            cachefile.write('[' + DesignTree.to_JSON() + ']')
        with open(os.path.join(os.getcwd(), 'cache', signature,'distree.html'), 'w') as cachefile:
            cachefile.write("<table> <th><pre>Design Unit</pre></th> <th><pre>Masked, Abs</pre></th> <th><pre>Latent, Abs</pre> <th><pre>Signaled Failure, Abs</pre></th> <th><pre>SDC, Abs</pre> <th><pre>Masked, %</pre> <th><pre>Latent, %</pre> <th><pre>Signaled Failure, %</pre></th> <th><pre>SDC, %</pre>" + DesignTree.to_HTML() + "</table>")            
            
    
    #return result for requested action
    if form.getvalue('action','').find('search') >= 0:
        with open(os.path.join(os.getcwd(), 'cache', signature,'search.xml'), 'r') as f:
            result = f.read()
            
    elif form.getvalue('action','').find('gedistree') >= 0:
        if form.getvalue('action','').find('JSON') >= 0: 
            with open(os.path.join(os.getcwd(), 'cache', signature,'distree.json'), 'r') as f:
                result = f.read()
        else: 
            with open(os.path.join(os.getcwd(), 'cache', signature,'distree.html'), 'r') as f:
                result = f.read()            
    
    print "Status: 200 \r\n"
    print result    
            
except Exception as e:
    log.write(str(e))

finally:
    log.write('Finished')
    log.close()

