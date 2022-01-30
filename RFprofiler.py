# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Temporary module used for the profiling of RAMs and register files
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------

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
import threading
from threading import Thread
from Davos_Generic import *
from Datamanager import *

simulate, analyze = True, True


def hashkey(rnd_pattern, core_id):
    mask = [0b10101,
            0b01011,
            0b10110,
            0b01101]
    return rnd_pattern ^ mask[core_id]

def gen_hashkeys(cores):
    rnd_pattern = random.randint(0, 31)
    return {cores[id]: hashkey(rnd_pattern, id) for id in range(len(cores))}

def rf_mod(adr, key):
    if adr == 0 or adr == key:
        return adr
    else:
        return adr ^ key


# Script entry point when launched directly
if __name__ == "__main__":
    sys.stdin = open('/dev/tty')
    toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
    # extract SBFI configuration from input XML
    tree = parse_xml_config(sys.argv[1]).getroot()
    config = DavosConfiguration(tree.findall('DAVOS')[0])
    config.file = sys.argv[1]
    print (to_string(config, "Configuration: "))


    if simulate:
        for conf in config.parconf:
            random.seed(0)
            if os.path.exists(os.path.join(conf.work_dir, 'profiling/{0}'.format(conf.label))):
                shutil.rmtree(os.path.join(conf.work_dir, 'profiling/{0}'.format(conf.label)))
            os.makedirs(os.path.join(conf.work_dir, 'profiling/{0}'.format(conf.label)))
            print('Profiling: {0}'.format(conf.label))
            os.chdir(conf.work_dir)
            script = 'vsim -c -restore {0}/{1} -do \"do profiling.do {2} {3}\" > profiling/trace.log'.format(conf.work_dir, conf.checkpoint, conf.workload_time, conf.label)
            print(script)
            proc = subprocess.Popen(script, shell=True)
            proc.wait()





    cores = ['Core_0']
    categories = {'reads': ['r_1', 'r_2', 'r_3', 'r_4'], 'writes': ['w_1', 'w_2']}

    profile, ref, res = {}, {}, {}
    if analyze:
        for conf in config.parconf:
            for core in cores:
                for c in categories.keys():
                    profile['{0}:{1}:{2}'.format(conf.label, core, c)] = [0]*32
                    ref['{0}:{1}:{2}'.format(conf.label, core, c)] = [0] * 32
                    res['{0}:{1}:{2}'.format(conf.label, core, c)] = [0] * 32
                    for trace in categories[c]:
                        dump = simDump()
                        dump.internal_labels = ['adr', 'enable']
                        dump.build_vectors_from_file(os.path.join(conf.work_dir, 'profiling/{0}'.format(conf.label), '{0}_{1}.lst'.format(core, trace)))
                        for vect in dump.vectors:
                            if vect.internals[0] != 'X' and vect.internals[1] == '1':
                                adr = int(vect.internals[0])
                                profile['{0}:{1}:{2}'.format(conf.label, core, c)][adr] += 1
        random.seed(0)
        KeyTab = Table('HashKeys', ['Exp_id'] + cores)
        for test in range(1000):
            keys = gen_hashkeys(cores)
            KeyTab.add_row([test] + [keys[core] for core in cores])
            for conf in config.parconf:
                for core in cores:
                    for c in categories.keys():
                        for adr in range(32):
                            res['{0}:{1}:{2}'.format(conf.label, core, c)][ rf_mod(adr, keys[core]) ] += profile['{0}:{1}:{2}'.format(conf.label, core, c)][adr]
                            ref['{0}:{1}:{2}'.format(conf.label, core, c)][ adr ] += profile['{0}:{1}:{2}'.format(conf.label, core, c)][adr]
        KeyTab.to_csv(';', True, os.path.join(config.report_dir, '{0}.csv'.format('HashKeys')))

        labels = []
        for core in cores:
            for c in categories.keys():
                labels.append( '{0}:{1}'.format(core, c) )

        ref_summary, hashing_summary = {}, {}
        for l in labels:
            hashing_summary[l] = [0] * 32
            ref_summary[l] = [0] * 32
            for conf in config.parconf:
                for adr in range(32):
                    ref_summary[l][adr] += ref['{0}:{1}'.format(conf.label, l)][adr]
                    hashing_summary[l][adr] += res['{0}:{1}'.format(conf.label, l)][adr]



        for conf in config.parconf:
            RES = Table('Profiling', ['REGISTER'] + labels)
            for adr in range(32):
                RES.add_row([adr] + [res['{0}:{1}'.format(conf.label, i)][adr] for i in labels])
            RES.to_csv(';', True, os.path.join(config.report_dir, '{0}.csv'.format(conf.label)))


        for conf in config.parconf:
            RES = Table('Profiling_Ref', ['REGISTER'] + labels)
            for adr in range(32):
                RES.add_row([adr] + [ref['{0}:{1}'.format(conf.label, i)][adr] for i in labels])
            RES.to_csv(';', True, os.path.join(config.report_dir, 'REF_{0}.csv'.format(conf.label)))


        RES = Table('Summary_Reference', ['REGISTER'] + labels)
        for adr in range(32):
            RES.add_row([adr] + [ref_summary[i][adr] for i in labels])
        RES.to_csv(';', True, os.path.join(config.report_dir, '{0}.csv'.format('Summary_Reference')))



        RES = Table('Summary_Hashing', ['REGISTER'] + labels)
        for adr in range(32):
            RES.add_row([adr] + [hashing_summary[i][adr] for i in labels])
        RES.to_csv(';', True, os.path.join(config.report_dir, '{0}.csv'.format('Summary_Hashing')))



