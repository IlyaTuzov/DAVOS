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
import math

regressionmodel_filename_patterns = re.compile("RegressionModel=\((.+?)\)\((.+?)\)[.]csv")
class Distributions:
    normal, poisson, inversegaussian, gamma = range(4)

class ModelTypes:
    linear, interactions = range(2)

class OptimizationGoals:
    min, max = range(2)

class Term:
    def __init__(self):
        self.factors = []
        self.coefficient = float(0)

class RegressionModel:
    def __init__(self, varname, dist, csvfile, pValueThreshold = 1.0):
        self.variable = varname
        self.type = None
        self.distribution = None
        self.Rsquared = float(0)
        self.SignificantFactors = []
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
        self.build_from_csv(csvfile, pValueThreshold)

    
    def build_from_csv(self, csvfile, pValueThreshold):
        if not os.path.exists(csvfile): return
        t = Table(self.variable)
        t.build_from_csv(csvfile)
        for rowindex in range(t.rownum()):
            if (t.getByLabel('Row', rowindex)).find('Intercept') >= 0:
                self.intercept = float(t.getByLabel('Estimate', rowindex))
            else:
                pvalue = float(t.getByLabel('pValue', rowindex))
                if pvalue <= pValueThreshold:
                    c = Term()
                    buf = (t.getByLabel('Row', rowindex)).split(':')
                    for i in buf:
                        c.factors.append(i.split('_'))
                    c.coefficient = float(t.getByLabel('Estimate', rowindex))
                    if c.coefficient == 0: continue
                    self.terms.append(c)
        self.type = ModelTypes.linear
        for t in self.terms:
            if len(t.factors) > 1: 
                self.type = ModelTypes.interactions


    def get_factors_list(self):
        res = set()
        for i in self.terms:
            res.add(i.factors[0][0])
        return(sorted(list(res)))

    








class RegressionModelManager:
    def __init__(self, factorvector=[]):
        self.models = []
        self.ReferenceFactorVector = factorvector       
        self.factor_levels = dict()
    

        
    def get_alternative_configurations(self, variable, iconfdict, goal=OptimizationGoals.min):
        res = []
        if len(self.ReferenceFactorVector) != len(iconfdict):
            print('Error: get_alternative_configurations len(ReferenceFactorVector) <> len(iconf): {} <> {}'.format(str(self.ReferenceFactorVector), str(iconf)))
            return(None)
        model = [x for x in self.models if x.variable == variable][0]
        for i in range(len(self.ReferenceFactorVector)):
            conf = [iconfdict[key] for key in self.ReferenceFactorVector]
            factor = self.ReferenceFactorVector[i]
            terms = [x for x in model.terms if x.factors[0][0] == factor]
            t0=Term(); t0.coefficient = 0.0; t0.factors=[[factor, '0']]
            terms.append(t0)
            if goal == OptimizationGoals.min:
                terms.sort(key=lambda x: x.coefficient, reverse = False)
            else:
                terms.sort(key=lambda x: x.coefficient, reverse = True)
            for term in terms:
                if int(term.factors[0][1]) != conf[i]:
                    conf[i] = int(term.factors[0][1])
                    break
            res.append(conf)
        return(res)



    def load_all(self, path):
        summarytag = ET.parse(os.path.join(path, 'Summary.xml')).getroot()
        desc = summarytag.findall('Model')
        for f in os.listdir(path):
            p = os.path.join(path, f)
            if os.path.isfile(p):
                a = regressionmodel_filename_patterns.findall(p)
                if len(a) > 0:
                    for i in a:
                        Z = RegressionModel(i[0],i[1],p)
                        for d in desc:
                            if d.get('Variable') == i[0] and d.get('Distribution') == i[1]:
                                Z.Rsquared = float(d.get('Rsquared_Ordinary', '0.0'))
                                Z.SignificantFactors = d.get('Significant_Factors', '').split(' ')
                        self.models.append( Z )


    def load_significant(self, path, threshold = 1.0):
        summarytag = ET.parse(os.path.join(path, 'Summary.xml')).getroot()
        desc = summarytag.findall('Model')
        for f in os.listdir(path):
            p = os.path.join(path, f)
            if os.path.isfile(p):
                a = regressionmodel_filename_patterns.findall(p)
                if len(a) > 0:
                    for i in a:
                        Z = RegressionModel(i[0],i[1],p, threshold)
                        for d in desc:
                            if d.get('Variable') == i[0] and d.get('Distribution') == i[1]:
                                Z.Rsquared = float(d.get('Rsquared_Ordinary', '0.0'))
                                Z.SignificantFactors = Z.get_factors_list()
                        self.models.append( Z )
        with open(os.path.join(path, 'Summary.log'), 'w') as f:
            for Z in self.models:
                f.write('{0} : {1:.5f} : {2}\n'.format(Z.variable, Z.Rsquared, ', '.join(Z.SignificantFactors)))




    def compile_estimator_script_binary(self, ExportPath):
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


    def get_min_max_terms(self):
        res = dict() #{'Varname' : [[factor, min, max], ...])
        for model in self.models:
            v = []
            for factor in model.SignificantFactors:
                terms = [x for x in model.terms if x.factors[0][0] == factor]
                t0=Term(); t0.coefficient = 0.0; t0.factors=[[factor, '0']]
                terms.append(t0)
                terms.sort(key=lambda x: x.coefficient, reverse = False)
                v.append([terms[0].factors[0][0], terms[0].coefficient, terms[-1].coefficient])
            res[model.variable] = v
        return(res)


    def compile_estimator_script_multilevel(self, ExportPath):
        FactorVectorIndexes = []
        for m in self.models:
            for t in m.terms:
                for j in t.factors:
                    if not j[0]  in self.factor_levels:
                        self.factor_levels[j[0]] = set()
                    if(len(j) > 1): self.factor_levels[j[0]].add(j[1])
        for i in range(len(self.ReferenceFactorVector)):
            FactorVectorIndexes.append( ("X[{0}]".format(i), self.ReferenceFactorVector[i]) )
        comment = "\n#" + "\n#".join("{} -> {},\tlevels = {}".format(tup[0], tup[1], "" if not tup[1] in self.factor_levels else str(sorted(list(self.factor_levels[tup[1]])))) for tup in FactorVectorIndexes) 
        res = "import math\n\n{0}\ndef EvaluateRegression(X):\n\tres = dict()".format(comment)
        for m in self.models:
            expression = ''
            for t in m.terms:
                #expression += ' +({0}*'.format(t.coefficient) + "*".join(i[0] for i in t.factors) + " if " + " and ".join([" {0} == {1}".format(i[0],i[1]) for i in t.factors]) + " else 0.0)"
                expression += ' +({0}'.format(t.coefficient)  + " if " + " and ".join([" {0} == {1}".format(i[0],i[1]) for i in t.factors]) + " else 0.0)"
            for x in FactorVectorIndexes:
                expression = expression.replace(x[1],x[0])
            expression = "{0} {1}".format(m.intercept, expression)
            if m.distribution == Distributions.poisson:
                expression = "int(math.exp({0}))".format(expression)
            elif m.distribution == Distributions.gamma:
                expression = "1.0/({0})".format(expression)
            elif m.distribution == Distributions.inversegaussian:
                expression = "1.0/math.sqrt({0})".format(expression)               
            expression = "res[\'{0}\'] = {1}".format(m.variable, expression)
            res += '\n\t{0}'.format(expression)
        res += '\n\treturn(res)'
        with open(os.path.join(ExportPath, 'Estimators.py'),'w') as f:
            f.write(res)

        if 'Estimators' in globals(): 
            #del Estimators
            sys.path[0] = ExportPath
            globals()['Estimators'] =reload(Estimators)        
        else:            
            sys.path.insert(0, ExportPath)
            globals()['Estimators'] =__import__('Estimators')        
        return('Estimators.py')


        
    def evaluate_python(self, FactorSetting):
        return(Estimators.EvaluateRegression(FactorSetting))


    def increment_setting(self, isetting, levels):
        isetting[0]+=1
        carry = 0
        for i in range(len(isetting)):
            isetting[i] += carry
            if isetting[i] >= levels[i]:
                isetting[i] = 0
                carry = 1
            else:
                carry = 0
                break
        out_of_range = True if carry>0 else False
        return(out_of_range, isetting)




    def get_min_max_linear(self, def_setting):
        if len(self.factor_levels)>0:
            res = dict()
            pattern = [def_setting[key] for key in self.ReferenceFactorVector]
            for model in self.models:
                setting_min = dict()
                setting_max = dict()
                for term in model.terms:
                    setting_min[term.factors[0][0]] = [0, 0.0]
                    setting_max[term.factors[0][0]] = [0, 0.0]
                factors = sorted(setting_min.keys(), reverse=False)
                adjust_indexes = []
                for i in factors:
                    if i in self.ReferenceFactorVector:
                        adjust_indexes.append(self.ReferenceFactorVector.index(i))
                #max term - max result
                if model.distribution in [Distributions.poisson, Distributions.normal]:
                    for term in model.terms:
                        if term.coefficient < setting_min[term.factors[0][0]][1]:
                            setting_min[term.factors[0][0]] = [ int(term.factors[0][1]), term.coefficient ]
                        if term.coefficient > setting_max[term.factors[0][0]][1]:
                            setting_max[term.factors[0][0]] = [ int(term.factors[0][1]), term.coefficient ]
                    min_val, max_val = model.intercept, model.intercept
                    min_conf, max_conf = [], []
                    for f in factors:
                        min_conf.append(setting_min[f][0])
                        min_val += setting_min[f][1]
                        max_conf.append(setting_max[f][0])
                        max_val += setting_max[f][1]
                    if model.distribution == Distributions.poisson:
                        min_val = int(math.exp(min_val))
                        max_val = int(math.exp(max_val))
                #max term - min result
                else:
                    pass
                min_conf_complete = pattern[:]
                max_conf_complete = pattern[:]
                for i in range(len(adjust_indexes)):
                    min_conf_complete[adjust_indexes[i]] = min_conf[i]
                    max_conf_complete[adjust_indexes[i]] = max_conf[i]
                res[model.variable] = [min_val, max_val, min_conf_complete, max_conf_complete]


            return(res)
        else:
            return(None)


    def get_min_max(self, def_setting):
        if len(self.factor_levels)>0:
            res = dict()
            fvect_names = sorted(self.factor_levels.keys(), reverse=False)
            fvect_levels = []
            for i in fvect_names:
                lvl = set(map(int,self.factor_levels[i]))
                fvect_levels.append(max(lvl)+1)
            Ntotal = reduce(lambda x, y: x * y, fvect_levels, 1)         
            adjust_indexes = []
            for i in fvect_names:
                if i in self.ReferenceFactorVector:
                    adjust_indexes.append(self.ReferenceFactorVector.index(i))
            pattern = [def_setting[key] for key in self.ReferenceFactorVector]
            setting = [0]*len(fvect_names)
            stop = False
            iter = 1
            step = Ntotal / 100
            while not stop:
                complete_setting = pattern[:]
                for i in range(len(adjust_indexes)):
                    complete_setting[adjust_indexes[i]] =  setting[i]
                resp = self.evaluate_python(complete_setting)
                for k,v in resp.iteritems():
                    if not k in res:
                        #           min max min_conf    max_conf   
                        res[k] = [  v,  v,  setting[:], setting[:] ]
                    else:
                        if v < res[k][0]:   #new min
                            res[k][0] = v
                            res[k][2] = setting[:]
                        if v > res[k][1]:   #new max
                            res[k][1] = v
                            res[k][3] = setting[:]                           
                if iter % step == 0:
                    print("{} : {}".format(str(complete_setting), str(resp)))
                stop, setting = self.increment_setting(setting, fvect_levels)
                iter += 1



            return(res)
        else:
            return(None)





    #def get_min_max(self):
    #    res = dict()
    #    for m in self.models:
    #        min_val, max_val = m.intercept, m.intercept
    #        min_conf, max_conf = {}, {}
    #        for i in m.SignificantFactors:
    #            min_conf[i] = (0, 0.0)  #setting, additive term
    #            max_conf[i] = (0, 0.0)
    #        if m.type == ModelTypes.linear:
    #            #select terms minimizing/maximizing the resulting responce

    #            for t in m.terms:
    #                if min_conf[t.factors]
    #        else:
    #            #iterate through all possible configurations of significant factors
    #            pass

    def evaluate_cuda(self, FactorSetting):
        pass







