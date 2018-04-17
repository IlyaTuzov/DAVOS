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





form = cgi.FieldStorage()



if form.getvalue('action','').find('Pareto') >= 0:


    x = form.getvalue('x')
    y = form.getvalue('y')

    
    
    if os.path.exists('./pareto/'+x+'__'+y+'.json'): fname = './pareto/'+x+'__'+y+'.json'
    elif os.path.exists('./pareto/'+y+'__'+x+'.json'): fname = './pareto/'+y+'__'+x+'.json'
    
    
    if fname != None:
        with open(fname, 'r') as f:
            result = f.read()
            

print "Status: 200 \r\n"
print result




