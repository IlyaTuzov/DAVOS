import sys
import os
import xml.etree.ElementTree as ET
import re
import stat
import subprocess
import shutil
import datetime
import time
import random
import glob
import copy
import ast
from Davos_Generic import *
from Datamanager import *

regressionmodel_filename_patterns = re.compile("RegressionModel=\((.+?)\)\((.+?)\)[.]csv")
class Distributions:
    normal, poisson, inversegaussian, gamma = range(4)


class Term:
    def __init__(self):
        self.factors = []
        self.coefficient = float(0)

class RegressionModel:
    def __init__(self, varname, dist, csvfile):
        self.variable = varname
        self.distribution = None
        for k,v in Distributions.__dict__.iteritems():
            if type(dist) is str:
                if dist.lower() == k:
                    self.distribution = v
                    break
            elif type(dist) is int:
                if dist == v:
                    self.distribution = v
                    break
        if self.distribution == None: raw_input('Error on parsing regression model: distribution not defined: {0}'.format(dist))
        self.intercept = float(0)
        self.terms=[]
        self.build_from_csv(csvfile)

    
    def build_from_csv(self, csvfile):
        if not os.path.exists(csvfile): return
        t = Table(self.variable)
        t.build_from_csv(csvfile)
        for rowindex in range(t.rownum()):
            if (t.getByLabel('Row', rowindex)).find('Intercept') >= 0:
                self.intercept = float(t.getByLabel('Estimate', rowindex))
            else:
                c = Term()
                c.factors = (t.getByLabel('Row', rowindex)).replace('_1','').split(':')
                c.coefficient = float(t.getByLabel('Estimate', rowindex))
                self.terms.append(c)


class RegressionModelManager:
    def __init__(self, factorvector=[]):
        self.models = []
        self.ReferenceFactorVector = factorvector       

    def load_all(self, path):
        for f in os.listdir(path):
            p = os.path.join(path, f)
            if os.path.isfile(p):
                a = regressionmodel_filename_patterns.findall(p)
                if len(a) > 0:
                    for i in a:
                        self.models.append( RegressionModel(i[0],i[1],p) )

    def compile_estimator_script(self, ExportPath):
        FactorVectorIndexes = []
        for i in range(len(self.ReferenceFactorVector)):
            FactorVectorIndexes.append( ("X[{0}]".format(i), self.ReferenceFactorVector[i]) )
        comment = "\n#" + "\n#".join("%s -> %s" % tup for tup in FactorVectorIndexes)
        res = "import math\n\n{0}\ndef EvaluateRegression(X):\n\tres = dict()".format(comment)
        for m in self.models:
            expression = ''
            for t in m.terms:
                if t.coefficient >= 0:
                    expression += ' +{0}*'.format(t.coefficient)
                else:
                    expression += ' {0}*'.format(t.coefficient)
                expression += "*".join(t.factors)
            for x in FactorVectorIndexes:
                expression = expression.replace(x[1],x[0])
            expression = "{0} {1}".format(m.intercept, expression)
            if m.distribution == Distributions.poisson:
                expression = "math.exp({0})".format(expression)
            elif m.distribution == Distributions.gamma:
                expression = "1.0/({0})".format(expression)
            elif m.distribution == Distributions.inversegaussian:
                expression = "1.0/math.sqrt({0})".format(expression)               
            expression = "res[\'{0}\'] = {1}".format(m.variable, expression)
            res += '\n\t{0}'.format(expression)
        res += '\n\treturn(res)'
        with open(os.path.join(ExportPath, 'Estimators.py'),'w') as f:
            f.write(res)

        sys.path.insert(0, ExportPath)
        globals()['Estimators'] =__import__('Estimators')        
        return('Estimators.py')

        
    def evaluate_python(self, FactorSetting):
        return(Estimators.EvaluateRegression(FactorSetting))

    def evaluate_cuda(self, FactorSetting):
        pass







