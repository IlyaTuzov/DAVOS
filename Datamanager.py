# Library defining data structes/classes and related logic, used by DAVOS modules
# Covers:
# 1. Configuration management (parsing/exporting of XML formatted confgirations),
# 2. Observation dumps (pasring, tracing, etc.)
# 3. Internal Data Model to manage fault injection and derived analysys metrics (SQLite reflection provided)
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
import sqlite3
import copy
import threading
import ast
from Davos_Generic import *
from SimDumpModel import *
from ConfigParser import *
__metaclass__ = type



#-------------------------------------------------------------#
# Internal datamodel reflected onto the database
#-------------------------------------------------------------#

class AnalyzerReferenceDesc:
    def __init__(self):
        self.reference_dump = None
        self.JnGrLst = None
        self.initial_internal_labels = None
        self.initial_output_labels = None


class DataDescriptors:
    HdlModel, InjTarget, Profiling, InjectionExp = range(4)

class DataModel:
    def __init__(self):
        self.HdlModel_lst = []
        #self.HdlModel_dict = dict() #key = label
        self.Target_lst = []
        self.Target_dict = dict() #key = {NodeFullPath,Macrocell,InjectionCase}
        self.Profiling_lst = []
        self.LaunchedInjExp_dict = dict()
        self.dbhelper = None
        self.lock = threading.RLock()
        self.reference = AnalyzerReferenceDesc()



    def ConnectDatabase(self, dbfile, backupfile):
        self.dbhelper = SqlHelper(dbfile, backupfile)

    def GetHdlModel(self, label):
        for m in self.HdlModel_lst:
            if m.Label == label:
                return(m)
        return(None)

    def RestoreHDLModels(self, externaldescriptor_lst):
        id_cnt = self.GetMaxKey(DataDescriptors.HdlModel) + 1
        self.HdlModel_lst = self.dbhelper.HdlModels_load()
        #self.HdlModel_dict = list_to_dict(self.HdlModel_lst, 'Label')
        if externaldescriptor_lst != None:
            for c in externaldescriptor_lst:
                if self.GetHdlModel(c.label) == None:
                    a = HDLModelDescriptor()
                    a.from_config_file(c)
                    a.ID = id_cnt
                    self.HdlModel_lst.append(a)
                    id_cnt += 1
            #self.HdlModel_dict = list_to_dict(self.HdlModel_lst, 'Label')


    def GetOrCreateHDLModel(self, FactorialConfig):
        #check whether already exists the model with the given configuration of factors
        for m in self.HdlModel_lst:
            if m.configuration_matches(FactorialConfig):
                return(m)
        res = HDLModelDescriptor()
        res.Factors = FactorialConfig
        res.ID = self.GetMaxKey(DataDescriptors.HdlModel) + 1
        self.HdlModel_lst.append(res)
        return(res)

    def HDLModelsToCsv(self):
        flist = [f.FactorName for f in self.HdlModel_lst[0].Factors]
        flist.sort()
        res = 'sep = ;\nLABEL;{0}'.format(';'.join(flist))
        for m in self.HdlModel_lst:
            res += '\n{0}'.format(m.Label)
            for f in m.Factors:
                res += ';{0}'.format((m.get_factor_by_name(f)).FactorVal)
        return(res)



    def RestoreEntity(self, EntityName):
        if EntityName == DataDescriptors.HdlModel:
            self.RestoreHDLModels(None)
        elif EntityName == DataDescriptors.InjTarget:
            self.Target_lst = self.dbhelper.Targets_load()
            for i in self.Target_lst:
                key = i.NodeFullPath + ',' + i.Macrocell + ',' + i.InjectionCase
                self.Target_dict[key] = i
        elif EntityName == DataDescriptors.Profiling:
            pass
        elif EntityName == DataDescriptors.InjectionExp:
            pass


    def GetOrAppendTarget(self, NodeFullPath, Macrocell, InjectionCase):
        with self.lock:
            res = None
            key = NodeFullPath + ',' + Macrocell + ',' + InjectionCase
            if key in self.Target_dict:
                res = self.Target_dict[key]
            else:
                res = InjectionTargetDescriptor()
                res.NodeFullPath = NodeFullPath
                res.Macrocell = Macrocell
                res.InjectionCase = InjectionCase
                if len(self.Target_lst) > 0: res.ID = max(node.ID for node in self.Target_lst) + 1
                else: res.ID = 0
                self.Target_lst.append(res)
                self.Target_dict[key] = res
        return(res)


    def AppendInjExpDesc(self, InjExpDesc):
        self.LaunchedInjExp_dict[InjExpDesc.ID] = InjExpDesc

    def SaveHdlModels(self):
        self.dbhelper.HdlModels_save(self.HdlModel_lst)

    def SaveTargets(self):
        self.dbhelper.Targets_save(self.Target_lst)

    def SaveInjections(self):
        injDesc_lst = self.LaunchedInjExp_dict.values()
        injDesc_lst.sort(key=lambda x: x.ID, reverse = False)
        self.dbhelper.InjectionDesc_save(injDesc_lst)

    def SyncAndDisconnectDB(self):
        self.dbhelper.connection.commit()
        self.dbhelper.connection.close()


    def GetMaxKey(self, EntityName):
        if EntityName == DataDescriptors.HdlModel:
            lst = self.dbhelper.get_primarykey_list('Models', True)  + [m.ID for m in self.HdlModel_lst]
        elif EntityName == DataDescriptors.InjTarget:
            lst =self.dbhelper.get_primarykey_list('Targets', True) + [m.ID for m in self.Target_lst]
        elif EntityName == DataDescriptors.Profiling:
            lst =self.dbhelper.get_primarykey_list('Profiling', True) + [m.ID for m in self.Profiling_lst]
        elif EntityName == DataDescriptors.InjectionExp:
            lst = self.dbhelper.get_primarykey_list('Injections', True)
        if len(lst) > 0:
            lst.sort()
            return(lst[-1])
        else:
            return(0)

class SerializationFormats:
    XML, JSON, PYTHON_DICT  = range(3)

class FactorSetting:
    def __init__(self):
        self.Phase = ''
        self.OptionName = ''
        self.OptionVal = ''
        self.FactorName = ''
        self.FactorVal = ''


    def serialize(self, format = SerializationFormats.XML, filename = None): 
        res = ''
        if format == SerializationFormats.PYTHON_DICT:
            res = '({0},{1},{2},{3},{4})'.format(self.Phase,self.OptionName,self.OptionVal,self.FactorName,str(self.FactorVal))
        elif format == SerializationFormats.XML:
            res = '<FactorSetting Phase="{0}" OptionName="{1}" OptionVal="{2}" FactorName="{3}" FactorVal="{4}" />'.format(self.Phase,self.OptionName,self.OptionVal,self.FactorName,self.FactorVal)
        if filename != None:
            with open(filename, 'w') as f:
                f.write(res)
        return(res)
    
    @staticmethod
    def deserialize(format, ipack):
        res = FactorSetting()
        if format == SerializationFormats.PYTHON_DICT:
            buf = ipack.replace(' ','').replace('(','').replace(')','').split(',')        
            if len(buf) > 0: res.Phase = str(buf[0])
            if len(buf) > 1: res.OptionName = str(buf[1])
            if len(buf) > 2: res.OptionVal = str(buf[2])
            if len(buf) > 3: res.FactorName = str(buf[3])
            if len(buf) > 4: res.FactorVal = int(str(buf[4])) if buf[4] != '' else ''
        elif format == SerializationFormats.XML:
            res.Phase     =ipack.get('Phase', '')
            res.OptionName=ipack.get('OptionName', '')
            res.OptionVal =ipack.get('OptionVal', '')
            res.FactorName=ipack.get('FactorName', '')
            res.FactorVal =ipack.get('FactorVal', '')
        return(res)




class HDLModelDescriptor:
    std_dumpfile_name = "DAVOS_MODELSTAT.xml"

    def __init__(self):
        self.ID = int(0)
        self.TabIndex  = int(-1)
        self.Factors = []       #FactorSetting
        self.Label = ""
        self.ReportPath = ""
        self.ModelPath = ""
        self.Metrics = dict()

    def from_config_file(self, simconfig):
        self.Label = simconfig.label
        self.ReportPath = './'+simconfig.label
        self.Metrics['ClockPeriod'] = simconfig.clk_period
        self.Metrics['Frequency'] = float(1000000000)/float(simconfig.clk_period)


    def get_flattened_metric_dict(self):
        res = dict()
        for k, v in self.Metrics.iteritems():
            if isinstance(v, int) or isinstance(v, float) or isinstance(v, str):
                res[k] = v
            if isinstance(v, dict):
                for k1, v1 in v.iteritems():
                    if isinstance(v1, int) or isinstance(v1, float) or isinstance(v1, str):
                        res[k1] = v1
        return(res)

    #simplier than serialization - exports just implementation properties, object hierarchy not retained
    def log_xml(self, tagname = 'CONFIGURATION'):
        res = '<{0}\n\tLABEL="{1}"\n\tCONFIG_TABLE_INDEX="{2}"\n\tFACTOR_SETTING="{3}"{4}/>'.format(
            tagname, 
            self.Label, 
            self.TabIndex, 
            ' '.join([str(c.FactorVal) for c in self.Factors]),
            '' if not 'Implprop' in self.Metrics else ('' if not isinstance(self.Metrics['Implprop'], dict) else (''.join(['\n\t{0}="{1}"'.format(k, v) for k, v in self.Metrics['Implprop'].iteritems()]))) )
        return(res)

    def serialize(self, format = SerializationFormats.XML, filename = None):
        res = ''
        if format == SerializationFormats.XML:
            res = '<HDLModelDescriptor ID = "{0}" Label = "{1}" TabIndex = "{2}" ReportPath = "{3}" ModelPath = "{4}" >'.format(self.ID, self.Label, self.TabIndex, self.ReportPath, self.ModelPath)
            res += ''.join(['\n\t{0}'.format(c.serialize(format)) for c in self.Factors])
            res += '\n\t<Metrics {0}>'.format(''.join(['\n\t\t{0}="{1}"'.format(k,v) for k,v in self.Metrics.iteritems() if not isinstance(v, dict)]))
            #Max 2 levels of depth, i.e. self.Metrics['Implprop']['FREQUENCY']
            for k, v in self.Metrics.iteritems():
                if isinstance(v, dict):
                    res += '\n\t\t<{0}{1}/>'.format(k, ''.join(['\n\t\t\t{0}="{1}"'.format(prop, val) for prop, val in v.iteritems()]))                
            res += '\n\t</Metrics>'
            res += '\n</HDLModelDescriptor>'            
        if filename != None:
            with open(filename, 'w') as f:
                if format == SerializationFormats.XML:
                    f.write('<?xml version="1.0"?>\n'+res)
                else:
                    f.write(res)
        return(res)

    @staticmethod
    def deserialize(format, ipack):
        res = HDLModelDescriptor()
        if format == SerializationFormats.XML:
            res.ID = int(ipack.get('ID','0'))
            res.TabIndex = int(ipack.get('TabIndex','-1'))
            res.Label = ipack.get('Label','')
            res.ReportPath = ipack.get('ReportPath','')
            res.ModelPath = ipack.get('ModelPath','')
            for c in ipack.findall('FactorSetting'):
                res.Factors.append(FactorSetting.deserialize(SerializationFormats.XML, c))
            t = ipack.findall('Metrics')
            if len(t) > 0:
                for k, v in t[0].attrib.items():
                    res.Metrics[k] = typed(v)
                for child in t[0]:
                    d = dict()
                    res.Metrics[str(child.tag)] = d
                    for k, v in child.attrib.items():
                        d[k] = typed(v)
        return(res)


    def configuration_matches(self, ReferenceConfiguration):
        #match condition: all factors are present and all have the same setting
        if len(ReferenceConfiguration) != len(self.Factors): return(False)
        for r in ReferenceConfiguration:
            match = False
            for i in self.Factors:
                if r.FactorName == i.FactorName and r.FactorVal == i.FactorVal:
                    match = True
                    break
            if match == False:
                return(False)
        return(True)

    def get_implprop(self):
        if 'Implprop' not in self.Metrics:
            self.Metrics['Implprop'] = dict()
        return(self.Metrics['Implprop'])

    def get_factor_by_name(self, factor_name):
        for i in self.Factors:
            if i.FactorName == factor_name:
                return(i)
        return(None)
    
    def get_factor_by_option(self, phase, option_name):
        for i in self.Factors:
            if i.Phase == phase and i.OptionName == option_name:
                return(i)
        return(None)

    def get_setting_dict(self):
        res = dict()
        for i in self.Factors:
            res[i.FactorName]=i.FactorVal
        return(res)



class InjectionTargetDescriptor:
    def __init__(self):
        self.ID = None
        self.NodeFullPath = ""
        self.Macrocell = ""
        self.InjectionCase = ""

class ProfilingResultDescriptor:
    def __init__(self):
        self.ID = None
        self.TargetID = None
        self.ModelID = None
        self.TotalAcTime = float(0)
        self.lastAcTime = float(0)
        self.ValueTime = dict() #saved as string in DB ( str() <--> eval() )

class InjectionDescriptor:
    def __init__(self):
        self.ID = None
        self.ModelID = None
        self.TargetID = None
        self.FaultModel = ""
        self.ForcedValue = ""
        self.InjectionTime = float(0)
        self.InjectionDuration = float(0)
        self.ObservationTime = float(0)
        self.Status = ""    #S - successfully simulated and analyzed, P - profiled, H - no finish vector (hang), E - analysis error (no sim dump, etc.)
        self.FailureMode = ""   #M - masked, L - latent, S - signalled failure, C  - silent data corruption
        self.ErrorCount = int(0)
        self.TrapCode = ""
        self.FaultToFailureLatency = float(0)
        self.Dumpfile = ""


#SqlHelper manages database operations : SQlite.db <--> datamodel
CreateDBquery = {
    "Injections" : """ 
        CREATE TABLE Injections (
            ID INTEGER PRIMARY KEY,
            ModelID  INTEGER,
            TargetID  INTEGER,
            FaultModel VARCHAR(32),
            ForcedValue  VARCHAR(64),
            InjectionTime  REAL,
            InjectionDuration REAL,
            ObservationTime REAL,
            Status CHARACTER(1),
            FailureMode CHARACTER(1),
            ErrorCount INTEGER,
            TrapCode VARCHAR(16),
            FaultToFailureLatency REAL,
            Dumpfile VARCHAR(128),
            FOREIGN KEY(ModelID) REFERENCES Models(ID),           
            FOREIGN KEY(TargetID) REFERENCES Targets(ID)
            ); """,

    "Targets" : """
        CREATE TABLE Targets (
            ID INTEGER PRIMARY KEY,
            NodeFullPath VARCHAR(1024),
            Macrocell VARCHAR(256),
            InjectionCase VARCHAR(256)
            );""",


    "Profiling" : """
        CREATE TABLE Profiling (
            ID INTEGER PRIMARY KEY,
            TargetID INTEGER,
            ModelID INTEGER,
            TotalAcTime REAL,
            lastAcTime REAL,
            ValueTime VARCHAR(128),
            FOREIGN KEY(TargetID) REFERENCES Targets(ID),
            FOREIGN KEY(ModelID) REFERENCES Models(ID) 
                            
            ); """,

    "Models" : """
        CREATE TABLE Models (
            ID INTEGER PRIMARY KEY,
            Label VARCHAR(255),
            ReportPath VARCHAR(255),
            FactorConfig VARCHAR(10000),
            Frequency REAL,
            ClockPeriod REAL
        ); """


    }


class SqlHelper:
    def __init__(self, dbfile, dbbackup):
        self.dbfile = dbfile
        self.dbbackup = dbbackup
        self.connection = None
        self.cursor = None
        self.createdb()
        self.last_backup_time = datetime.datetime.now().replace(microsecond=0)


    def robust_db_exec(self, query, datatuple, immediate_commit = False):
        for i in range(0, 5):
            try:
                if datatuple == None:
                    self.cursor.execute(query)
                else:
                    self.cursor.execute(query, datatuple)
                if immediate_commit:
                    self.connection.commit()
            except Exception as e:                
                print 'DB execute error: ' + str(e) + '\nQuery: ' + str(query)
                #time.sleep(0.1)
                continue
            break
    
    def execute_for_result(self, query, datatuple):
        self.robust_db_exec(query, datatuple, False)
        return self.cursor.fetchall()

    def createdb(self):
        self.connection = sqlite3.connect(self.dbfile)
        os.chmod(self.dbfile, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
        self.cursor = self.connection.cursor()
        for tablename, sqlcode in CreateDBquery.items():
            query = 'SELECT name FROM sqlite_master WHERE type=\'table\' AND name=\'{0}\';'.format(tablename)
            self.robust_db_exec(query, None)
            if len(self.cursor.fetchall()) == 0:
                self.robust_db_exec(sqlcode, None, True)


    def BackupDB(self, Immediate = True):
        timestamp = datetime.datetime.now().replace(microsecond=0)
        if Immediate or (time_to_seconds(timestamp - self.last_backup_time) > 3600):
            print('....Doing database backup....')
            self.connection.commit()
            self.connection.close()
            shutil.copy(self.dbfile, self.dbbackup)
            self.connection = sqlite3.connect(self.dbfile)
            self.cursor = self.connection.cursor()
            self.last_backup_time = timestamp


    def close(self):
        self.connection.close()

    def HdlModels_load(self):
        model_lst = []
        self.robust_db_exec('SELECT * FROM Models', None)
        rows = self.cursor.fetchall()
        for c in rows:
            a = HDLModelDescriptor()
            names = [description[0] for description in self.cursor.description]
            a.Metrics = dict(zip(names, c))
            a.ID = a.Metrics['ID']
            del a.Metrics['ID']
            a.Label = a.Metrics['Label']
            del a.Metrics['Label']
            a.ReportPath = a.Metrics['ReportPath']
            del a.Metrics['ReportPath']
            a.Factors = [FactorSetting.deserialize(SerializationFormats.PYTHON_DICT, f) for f in a.Metrics['FactorConfig'].split(';')]
            del a.Metrics['FactorConfig']
            model_lst.append(a)
            for k, v in a.Metrics.items():
                if v==None: a.Metrics[k] = 0
                elif type(v) is float: a.Metrics[k] = v
                elif v =='': a.Metrics[k] = ''
                else:
                    try: 
                        a.Metrics[k] = ast.literal_eval(str(v))
                    except:
                        a.Metrics[k] = str(v)
        return(model_lst)


    def get_columnsintable(self, Tablename):
        columndesc = self.execute_for_result('PRAGMA table_info({0})'.format(Tablename), None)
        res = []
        for c in columndesc:
            res.append(str(c[1]))
        return(res)

    def HdlModels_save(self, HdlModel_lst):        
        for m in HdlModel_lst:
            coldesc = self.get_columnsintable('Models')
            for k,v in m.Metrics.iteritems():
                if not k in coldesc:
                    T = 'REAL' if type(v) is float else 'VARCHAR(10000)'
                    self.robust_db_exec('ALTER TABLE Models ADD COLUMN {0} {1}'.format(k, T), None, True)
            query = "\nINSERT OR REPLACE INTO Models (ID, Label, ReportPath, FactorConfig {0}) VALUES ({1}, \"{2}\", \"{3}\", \"{4}\" {5})".format(''.join([','+str(k) for k in m.Metrics.keys()]), m.ID, m.Label, m.ReportPath, ';'.join([c.serialize(SerializationFormats.PYTHON_DICT) for c in  m.Factors]), ''.join([',{0:.4f}'.format(x) if type(x) is float else ',\"{0}\"'.format(str(x)) for x in m.Metrics.values()]) )
            self.robust_db_exec(query, None)
        self.connection.commit()


    def Targets_load(self):
        target_lst = []
        self.robust_db_exec('SELECT ID, NodeFullPath, Macrocell, InjectionCase FROM Targets', None)
        rows = self.cursor.fetchall()
        for c in rows:
            a = InjectionTargetDescriptor()
            a.ID = int(c[0])
            a.NodeFullPath = str(c[1])
            a.Macrocell = str(c[2])
            a.InjectionCase = str(c[3])
            target_lst.append(a)
        return(target_lst)


    def Targets_save(self, Target_lst):
        for t in Target_lst:
            query = "\nINSERT OR REPLACE INTO Targets (ID, NodeFullPath, Macrocell, InjectionCase) VALUES(?,?,?,?)"
            self.robust_db_exec(query, (t.ID, t.NodeFullPath, t.Macrocell, t.InjectionCase))
        self.connection.commit()

    def InjectionDesc_save(self, InjDesc_lst):
        for i in InjDesc_lst:
            query = "\nINSERT INTO Injections (ID, ModelID, TargetID, FaultModel, ForcedValue, InjectionTime, InjectionDuration, ObservationTime, Status, FailureMode, ErrorCount, TrapCode, FaultToFailureLatency, Dumpfile) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            self.robust_db_exec(query, (i.ID, i.ModelID, i.TargetID, i.FaultModel, i.ForcedValue, i.InjectionTime, i.InjectionDuration, i.ObservationTime, i.Status, i.FailureMode, i.ErrorCount, i.TrapCode, i.FaultToFailureLatency, i.Dumpfile))
        self.connection.commit()


    def get_distinct(self, field, table, sortflag = False):
        res = []
        self.robust_db_exec('SELECT DISTINCT {0} FROM {1}'.format(field, table), None)
        for c in self.cursor.fetchall():
            res.append(c[0])
        if sortflag == True: res.sort()
        return(res)


    def get_primarykey_list(self, table, sortflag):
        return self.get_distinct('ID', table, sortflag)

















