#!/Python27/python
import sys
import xml.etree.ElementTree as ET
import re
import os
import datetime
import shutil
import time
import glob
import sqlite3

query = ''

with open(sys.argv[1],'r') as f:
    query = f.read()

connection = sqlite3.connect("Results_SQL.db")
cursor = connection.cursor()

try:
    cursor.execute(query)
    
except sqlite3.Error as er:
    with open('SQLlog.txt','a') as f:
        f.write('\nError: ' + str(er))
        
qres = cursor.fetchall()

with open(sys.argv[1], 'w') as f:
    for i in qres:
        f.write('\n' + str(i))
        
connection.close()