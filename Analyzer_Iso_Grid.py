# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       Analyser of SBFI traces for SGE-based clusters
#       Input agruments:
#           (1) - configuration file (xml),
#           (2) - label of the configuration to be processed (if omitted - all configurations are processed)
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
import copy
from Davos_Generic import *
from Datamanager import *
from SBFI.SBFI_Analyzer import *

toolconf = ToolOptions(ET.parse('tool_config.xml').getroot().findall('ToolOptions')[0])
iconfig = os.path.join(os.getcwd(), sys.argv[1])

normconfig = iconfig.replace('.xml','_normalized.xml')
normalize_xml(iconfig, normconfig)
xml_conf = ET.parse(normconfig)
tree = xml_conf.getroot()
davosconf = DavosConfiguration(tree.findall('DAVOS')[0])
config = davosconf.SBFIConfig
config.parconf = davosconf.parconf
selected_conf = ''
if len(sys.argv) > 2: selected_conf = sys.argv[2]

src_dir = config.report_dir
tmp_dir = os.environ['TMP']

#copy from source to temp folder on the node
src_dbfile = config.get_DBfilepath(False)
config.report_dir = tmp_dir
dst_dbfile = config.get_DBfilepath(False)
print 'Copying from {0} to {1}'.format(src_dbfile, dst_dbfile)
if os.path.exists(src_dbfile):
    shutil.copy(src_dbfile, dst_dbfile)


datamodel = DataModel()
datamodel.ConnectDatabase(config.get_DBfilepath(False), config.get_DBfilepath(True))
datamodel.RestoreHDLModels(config.parconf)
datamodel.RestoreEntity(DataDescriptors.InjTarget)
datamodel.SaveHdlModels()
print 'model restored'

if selected_conf != '':
    for conf in config.parconf:
        if conf.label == selected_conf:
            process_dumps(config, toolconf,conf, datamodel)
            break
else:
    for conf in config.parconf:
        process_dumps(config, toolconf,conf, datamodel)               


datamodel.SyncAndDisconnectDB()
#copy back
if os.path.exists(dst_dbfile):
    shutil.copy(dst_dbfile, src_dbfile)
    