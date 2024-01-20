# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A library of generic data structures and procedures used by DAVOS modules for:
#           1. Management of Grid Jobs (submission, monitoring, etc.)
#           2. Processing and quierying of custom Tables with csv and html reflection
#           3. Auxiliary functions to manage multiprocessing jobs, robust filesystem IO, console interaction, etc.
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
import errno
import traceback
import commands
from sys import platform
import zipfile as ZF


# -----------------------------------------------------
#  Support Functions to interact with Sun Grid Engine
# -----------------------------------------------------
def run_qsub(itag, iscript, ipath, reqtime, reqmem, logdir=None, slots=1):
    sh_script = "#!/bin/sh"
    sh_script += "\n#$ -N " + itag
    sh_script += "\n#$ -l h_rt=" + reqtime + ",h_vmem=" + reqmem
    sh_script += "\n#$ -S /bin/sh"
    if logdir != None:
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        sh_script += "\n#$ -o {0}/out_{1}.txt".format(logdir, itag)
        sh_script += "\n#$ -e {0}/err_{1}.txt".format(logdir, itag)
    sh_script += "\necho $PATH"
    sh_script += "\ncd " + ipath
    sh_script += "\n" + iscript
    sh_fname = itag + "_sh.sh"
    os.chdir(ipath)
    robust_file_write(os.path.join(ipath, sh_fname), sh_script)
    val = commands.getoutput("chmod u+x " + sh_fname)
    #qscript = "qsub -q " + "general" + " -V -wd " + ipath + " " + sh_fname
    qscript = "qsub -V -wd " + ipath + " " + sh_fname

    res = ''
    while res.lower().find('submitted') < 0 or res.lower().find('error') >= 0:
        res = commands.getoutput(qscript)
        print res
        time.sleep(1.0)
    os.remove(os.path.join(ipath, sh_fname))
    return res


class JobDesc:
    def __init__(self, xnode=None):
        self.name = ""
        self.state = ""
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.find('JB_name').text
        self.state = xnode.get('state')


class QueueDesc:
    def __init__(self):
        self.running = []
        self.pending = []
        self.sample_time = datetime.datetime.now().replace(microsecond=0)

    def total_len(self):
        return (len(self.pending) + len(self.running))

    def time_difference_to_sec(self, prev_time):
        delta = self.sample_time - prev_time.sample_time
        ds = (delta.seconds + delta.days * 24 * 3600)
        return (ds)


def get_jobs_all():
    jobnamelist = []
    val = ""
    success = 0
    while (success == 0):
        try:
            val = commands.getoutput('qstat -xml')
            if (val != None):
                lroot = ET.fromstring(val)
                if (lroot != None):
                    qi = lroot.find('queue_info')
                    if (qi != None):
                        joblist = qi.findall('job_list')
                        if (len(joblist) > 0):
                            for t in joblist:
                                jobnamelist.append(JobDesc(t))
                    ji = lroot.find('job_info')
                    if (ji != None):
                        joblist = ji.findall('job_list')
                        if (len(joblist) > 0):
                            for t in joblist:
                                jobnamelist.append(JobDesc(t))
            success = 1
        except Exception:
            print "GET JOB NAMES (qstat) error. OUTPUT: " + val
            print "Retrying..."
            success = 0
            time.sleep(2)
    return jobnamelist


def get_queue_state_by_job_prefix(prefix):
    res = QueueDesc()
    jobnamelist = get_jobs_all()
    for c in jobnamelist:
        if (c.name.startswith(prefix)):
            if (c.state == 'running'):
                res.running.append(c)
            elif (c.state == 'pending'):
                res.pending.append(c)
    return (res)


def cancel_pending_jobs(joblist):
    for c in joblist.pending:
        val = commands.getoutput('qdel ' + c.name)
        print val + ' (cancelled job: ' + c.name + ')'
    joblist.pending = []


def get_job_names_prefix(prefix):
    jobnamelist = get_jobs_all()
    res = []
    for c in jobnamelist:
        if (c.name.startswith(prefix)):
            res.append(c.name)
    return (res)


def qsub_wait_threads(imax):
    time.sleep(2)
    while len(get_jobs_all()) > imax:
        time.sleep(2)
    return (0)


def qsub_wait_workpack(iname, imax):
    time.sleep(2)
    while len(get_job_names_prefix(iname)) > imax:
        time.sleep(2)
    return (0)


def monitor_sge_job(job_label, reporting_interval):
    """Periodically reports the state of SGE job, blocks current execution thread until SGE job completes

    Args:
        job_label (string): name of the job in GSE queue
        reporting_interval (int): seconds between consecutive queue checks

    Returns:
    """
    joblist = get_queue_state_by_job_prefix(job_label)
    while joblist.total_len() > 0:
        print("\rRunning: {0:5d}\tPending: {1:5d}".format(len(joblist.running), len(joblist.pending)))
        time.sleep(reporting_interval)
        joblist = get_queue_state_by_job_prefix(job_label)



# --------------------------------------------------
# Various generic functions
# -------------------------------------------------
def resolve_path(root_path, dest_path):
    res = os.path.normpath(os.path.join(root_path, dest_path)) if dest_path.find(':') < 0 else os.path.normpath(dest_path)
    return (res)


def get_relative_path(src, dst):
    dif = os.path.commonprefix([src, dst])
    res = dst
    if dif != '':
        if dst.startswith(dif):
            res = dst[len(dif):]
    return (res)


def cleanup_path(path):
    res = path.replace('\\', '/')
    res = re.sub('^[\\\\/]*', '', res)
    return (res)


def zip_folder(path, zipname):
    ziphandle = ZF.ZipFile(zipname, mode='a', compression=ZF.ZIP_DEFLATED, allowZip64=True)
    existing_files = ziphandle.namelist()
    print('Appending folder [{0}] to zip package [{1}]'.format(path, zipname))
    for root, dirs, files in os.walk(path):
        for fname in files:
            c = os.path.relpath(os.path.join(root, fname), os.path.join(path, '..'))
            if not c in existing_files:
                ziphandle.write(os.path.join(root, fname), c)
            else:
                print('zip_folder: skipping file (already exists): {0}'.format(c))
    ziphandle.close()




def robust_file_write(fname, content):
    for i in range(0, 100):
        try:
            with open(fname, "w") as fdesc:
                fdesc.write(content)
            statinfo = os.stat(fname)
            if (statinfo.st_size == 0):
                print "robust_file_write: zero-size file error: " + fname + ", retrying"
                continue
            os.chmod(fname, stat.S_IRWXU)
        except Exception as e:
            print 'robust_file_write exception [' + str(e) + '] on file write: ' + fname + ', retrying [attempt ' + str(i) + ']'
            time.sleep(0.001)
            continue
        break


def remove_delimiters(iline, delimiters=('_', '.', '/', '(', ')', ':', '', '[', ']')):
    res = iline
    for d in delimiters:
        res = res.replace(d, '')
    return (res)


def copy_all_files(src, dst):
    src_path = os.listdir(src)
    if not os.path.exists(dst):
        os.makedirs(dst)
    for path in src_path:
        full_src_name = os.path.join(src, path)
        if (os.path.isfile(full_src_name)):
            shutil.copy(full_src_name, dst)
        elif not os.path.exists(os.path.join(dst, path)):
            shutil.copytree(full_src_name, os.path.join(dst, path))


class Dirstate:
    def __init__(self, i_dir):
        self.s_dir = i_dir
        self.sample_time = datetime.datetime.now().replace(microsecond=0)
        self.nfiles = nfiles = len(os.listdir(self.s_dir))

    def update(self):
        self.sample_time = datetime.datetime.now().replace(microsecond=0)
        self.nfiles = nfiles = len(os.listdir(self.s_dir))

    def time_difference_to_sec(self, prev_time):
        delta = self.sample_time - prev_time.sample_time
        ds = (delta.seconds + delta.days * 24 * 3600)
        return (ds)


def create_folder(rtdir, nestdir, prefix=''):
    targetpath = os.path.join(rtdir, nestdir)
    renamepath = os.path.join(rtdir, nestdir + "__" + prefix)
    if (not os.path.exists(targetpath)):
        os.mkdir(targetpath)
        print "Created: " + str(targetpath)
    else:
        if (os.listdir(targetpath) != [] and prefix != ''):
            os.rename(targetpath, renamepath)
            print("RENAMING (non-empty folder): " + str(targetpath) + "  TO  " + str(renamepath))
            os.mkdir(targetpath)
            print "Created: " + str(targetpath)
    return (0)



def check_termination(config_file_path):
    iconfig = os.path.abspath(config_file_path)
    normconfig = iconfig.replace('.xml', '_normalized.xml')
    normalize_xml(iconfig, normconfig)
    tree = ET.parse(normconfig).getroot()
    genconf = tree.findall('fault_injection')[0].findall('task')[0]
    terminate_flag = genconf.get('runtime_terminate')
    if (terminate_flag == "on"):
        return True
    return False


def create_restricted_file(filename):
    if (not os.path.exists(filename)):
        f = open(filename, "w")
        f.close()
    os.chmod(filename, stat.S_IREAD)
    return (0)


def time_to_seconds(itime):
    return (int((itime.microseconds + (itime.seconds + itime.days * 24 * 3600) * 10 ** 6) / 10 ** 6))


def how_old_file(fname):
    if (not os.path.exists(fname)):
        print("how_old_file error: no file found" + str(fname))
        return (0)
    d = os.path.getmtime(fname)
    t = datetime.datetime.fromtimestamp(d)
    c = datetime.datetime.now()
    delta = c - t
    ds = (delta.microseconds + (delta.seconds + delta.days * 24 * 3600) * 10 ** 6) / 10 ** 6
    return (ds)


def remove_dir(targetpath):
    if (os.path.exists(targetpath)):
        print("\nRemoving " + targetpath)
        shutil.rmtree(targetpath, ignore_errors=True)


def get_active_proc_number(proclist):
    res = 0
    for p in proclist:
        if (p.poll() is None):
            res += 1
    return (res)


def get_active_proc_indexes(proclist):
    res = []
    for i in range(0, len(proclist)):
        if (proclist[i].poll() is None):
            res.append(i)
    return (res)


def pure_node_name(nodename, num=2):
    res = nodename
    items = nodename.split('/')
    z = len(items)
    if (z - num >= 0):
        res = ""
        for i in range(z - num, z, 1):
            res += "_" + items[i]
    return (res)


def list_to_dict(ilist, key):
    res = dict()
    for c in ilist:
        a = getattr(c, key)
        res[a] = c
    return (res)


def list_difference(scr_lst, rmval_lst):
    res = scr_lst
    for i in rmval_lst:
        if i in scr_lst:
            res.remove(i)
    return (res)


# Auxiliary Functions
def to_string(obj, msg=''):
    res = '\n' + msg
    if str(type(obj)).find('str') >= 0 or str(type(obj)).find('int') >= 0 :
        return (res + str(obj))
    if isinstance(obj, dict):
        for key, val in obj.__dict__.items():
            if str(type(getattr(obj, key))).find('list') >= 0:
                a = getattr(obj, key)
                for i in range(0, len(a)):
                    res += to_string(a[i], '->' + str(key) + '[' + str(i) + '] = ')
            elif str(type(getattr(obj, key))).find('class') >= 0:
                res += to_string(getattr(obj, key), str('\n->' + key + ' = '))
            else:
                x = str("\n\t%s = %s" % (key, str(val)))
                if x.find('object at') < 0:
                    res += x
    elif isinstance(obj, list):
        res += str(obj)
    return (res)


def normalize_xml(infilename, outfilename):
    with open(infilename, 'r') as infile:
        content = infile.read()
    # append here normalization code
    content = re.sub(r'&', '&amp;', content)
    content = re.sub(r"'(.+?)'\s*?:\s*?'(.+?)'", r"&apos;\1&apos;:&apos;\2&apos;", content)
    with open(outfilename, 'w') as outfile:
        outfile.write(content)


def parse_xml_config(xml_file):
    normalized = xml_file.replace('.xml', '_normalized.xml')
    normalize_xml(os.path.join(os.getcwd(), xml_file), os.path.join(os.getcwd(), normalized))
    xml_conf = ET.parse(os.path.join(os.getcwd(), normalized))
    os.remove(normalized)
    return xml_conf


def set_permissions(path, mode):
    os.chmod(path, mode)
    for rt, dlist, flist in os.walk(path, topdown=False):
        for dn in [os.path.join(rt, d) for d in dlist]:
            os.chmod(dn, mode)
        for fn in [os.path.join(rt, f) for f in flist]:
            os.chmod(fn, mode)


# ----------------------------------------------
# classes for logs and HTML reports
# ----------------------------------------------
class Table:
    def __init__(self, name, ilabels=[]):
        self.name = name
        self.columns = []
        self.labels = ilabels[:]
        for i in ilabels: self.columns.append([])

    def rownum(self):
        if (len(self.columns) > 0):
            return (len(self.columns[0]))
        else:
            return (0)

    def colnum(self):
        return (len(self.columns))

    def add_column(self, lbl, data=[]):
        self.labels.append(lbl)
        self.columns.append(data if data != [] else [''] * self.rownum())

    def add_row(self, idata=None):
        if (idata != None):
            if (len(idata) >= self.colnum()):
                for c in range(0, len(self.columns), 1):
                    self.columns[c].append(idata[c])
            else:
                pass
                #print "Warning: Table.add_row(): data items less than labels" + str(len(idata)) + " <> " + str(self.colnum())
        else:
            for c in self.columns:
                c.append("")
    @staticmethod
    def merge(name, tables):
        res = Table(name, tables[0].labels)
        for t in tables:
            for row_index in range(t.rownum()):
                res.add_row(t.get_row(row_index))
        return(res)

    def put(self, row, col, data):
        try:
            self.columns[col][row] = data
        except Exception as e:
            print("Error: put({0:d},{1:d}) on Table: {2}: {3}".format(row, col, self.name, str(e)))

    def put_to_last_row(self, col, data):
        self.put(self.rownum() - 1, col, data)

    def get(self, row, col):
        try:
            return self.columns[col][row]
        except Exception as e:
            print("Error: get({0:d},{1:d}) on Table: {2}: {3}".format(row, col, self.name, str(e)))
            return ""

    def getByLabel(self, lbl, row):
        for l_i in range(len(self.labels)):
            if self.labels[l_i] == lbl:
                return (self.get(row, l_i))
        return (None)

    def to_csv(self, sep=';', exportheader=True, fname=None):
        res = ''
        if exportheader: res += "sep={0}\n".format(sep)
        res += sep.join([l for l in self.labels])
        nc = len(self.columns)
        nr = len(self.columns[0])
        if fname == None:
            for r in range(0, nr, 1):
                res += "\n{0}".format(sep.join([str(self.columns[c][r]) for c in range(0, nc, 1)]))
                if r % 1000 == 0: sys.stdout.write('Processed rows: {0:08d}\r'.format(r))
        else:
            with open(fname, 'w') as f:
                f.write(res)
                for r in range(0, nr, 1):
                    f.write("\n{0}".format(sep.join([str(self.columns[c][r]) for c in range(0, nc, 1)])))
                    if r % 1000 == 0: sys.stdout.write('Exported rows: {0:08d}\r'.format(r))
        return (res)

    def snormalize(self, ist):
        if (ist[-1] == "\r" or ist[-1] == "\n" or ist[-1] == ""):
            del ist[-1]
        return ist

    def build_from_csv(self, file):
        if isinstance(file, str):
            with open(file, 'r') as csv_file:
                content = csv_file.read()
        else:
            content = file.read()
        lines = content.split('\n')
        t = re.findall("sep\s*?=\s*?([;,]+)", lines[0])
        if len(t) == 0:
            itemsep = ','
            firstlineindex = 0
        else:
            itemsep = t[0]
            firstlineindex = 1
        labels = self.snormalize(lines[firstlineindex].split(itemsep))
        for i in range(len(labels)): labels[i] = labels[i].replace('\r', '')
        for l in labels:
            self.add_column(l)
        for i in range(firstlineindex + 1, len(lines), 1):
            c = self.snormalize(lines[i].split(itemsep))
            for v in range(len(c)): c[v] = c[v].replace('\r', '')
            self.add_row(c)

    def to_html_table(self, tname):
        res = HtmlTable(self.rownum(), self.colnum(), tname)
        for c in range(0, len(self.labels), 1):
            res.set_label(c, self.labels[c])
        for r in range(0, self.rownum(), 1):
            for c in range(0, self.colnum(), 1):
                res.put_data(r, c, self.get(r, c))
        return (res)

    def query(self, filter):
        res = []
        for row in range(self.rownum()):
            match = True
            for key in filter:
                val = self.getByLabel(key, row)
                if val.find(filter[key]) < 0:
                    match = False
                    break
            if match:
                d = dict()
                for l in self.labels:
                    d[l] = self.getByLabel(l, row)
                res.append(d)
        return (res)

    def delete_rows(self, indexes):
        for i in range(self.colnum()):
            c = self.columns[i]
            c = [c[v] for v in range(len(c)) if not v in indexes]
            self.columns[i] = c

    def get_row(self, row_index):
        return [self.columns[i][row_index] for i in range(self.colnum())]


    def delete_columns(self, indexes):
        self.columns = [self.columns[i] for i in range(len(self.columns)) if not i in indexes]
        self.labels = [self.labels[i] for i in range(len(self.labels)) if not i in indexes]

    def filter(self, lbl, val):
        marked_rows = []
        column_index = self.labels.index(lbl)
        for row_index in range(self.rownum()):
            if self.get(row_index, column_index) == val:
                marked_rows.append(row_index)
        self.delete_rows(marked_rows)
        self.delete_columns([column_index])

    def reorder_columns(self, labelsequence):
        try:
            order = [self.labels.index(l) for l in labelsequence]
            self.columns = [self.columns[i] for i in order]
            self.labels = [self.labels[i] for i in order]
        except:
            print('Error')

    def search_row(self, value_sequence, column_align=0):
        for row_index in range(self.rownum()):
            row = [self.columns[i][row_index] for i in range(self.colnum())]
            if row[column_align: column_align + len(value_sequence)] == value_sequence:
                return row_index, row

    def search_rows(self, value_sequence, column_align=0):
        res = []
        for row_index in range(self.rownum()):
            row = [self.columns[i][row_index] for i in range(self.colnum())]
            if row[column_align: column_align + len(value_sequence)] == value_sequence:
                res.append(row)
        return (res)

    def filter_copy(self, lbl, val, soft_match=True):
        res = Table(self.name, self.labels)
        column_index = self.labels.index(lbl)
        for row_index in range(self.rownum()):
            if val in self.get(row_index, column_index):
                res.add_row(self.get_row(row_index))
        return res

        


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
        if (index < len(self.cells)):
            return (self.cells[index])
        print "Incorrect index"
        return None

    def put_data(self, icell, idata):
        if (icell < len(self.cells)):
            self.cells[icell].put_data(idata)

    def set_class(self, icell, iclass):
        if (icell < len(self.cells)):
            self.cells[icell].set_class(iclass)

    def add_cell(self):
        self.cells.append(HtmlTableCell())

    def get_size(self):
        return (len(self.cells))

    def to_string(self):
        res = "<tr>"
        for c in self.cells:
            res += "\n" + c.to_string()
        res += "</tr>"
        return (res)


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
        if (nrow != None):
            self.rows.append(nrow)
        else:
            cnum = self.rows[0].get_size()
            self.rows.append(HtmlTableRow(cnum))

    def get_row(self, rownum):
        return (self.rows[rownum])

    def add_column(self):
        for r in self.rows:
            r.add_cell()
        self.labels.append("")

    def put_data(self, irow, icol, idata):
        if (irow < len(self.rows)):
            self.rows[irow].put_data(icol, idata)
        else:
            print "put_data index error"

    def set_class(self, irow, icol, iclass):
        if (irow < len(self.rows)):
            self.rows[irow].set_class(icol, iclass)
        else:
            print "set_class index error"

    def set_label(self, icol, ilabel):
        if (icol < len(self.labels)):
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
        return (res)

    def to_file(self, fname):
        f = open(fname, 'w')
        f.write("<table border =\"1\">\n<caption>" + self.caption + "</caption><thead>\n<tr>")
        for c in self.labels:
            f.write("\n<th><div class = \"title\">" + c + "</div></th>")
        f.write("</tr></thead>\n<tbody>")
        for c in self.rows:
            f.write("\n" + c.to_string())
        f.write("</tbody>\n</table>")
        f.close()

    def to_string_no_header(self):
        res = "<table border =\"1\">\n<caption>" + self.caption + "</caption>\n<tbody>"
        for c in self.rows:
            res += "\n" + c.to_string()
        res += "</tbody>\n</table>"
        return (res)


class HtmlPage:
    def __init__(self, title=""):
        self.css_file = ""
        self.js_files = []
        self.data_items = []
        self.title = title

    def put_data(self, idata):
        self.data_items.append(idata)

    def put_comment(self, idata):
        self.put_data("\n<div class = \"comment\">\n" + idata + "\n</div>")

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
    def __init__(self, href, text):
        self.href = href
        self.text = text

    def to_string(self):
        return ("\n<a href=\"" + self.href + "\">" + self.text + "</a>")


class IndexTypeTuple:
    def __init__(self, i_ind, i_type):
        self.index = int(i_ind)
        self.type = i_type


class Register:
    def __init__(self, name=""):
        self.name = name
        self.indexes = []
        self.single_bit_type = ''
        self.index_separator = '_'

    def sort(self):
        self.indexes.sort(key=lambda x: x.index, reverse=True)
        return (self)

    def to_string(self):
        res = self.name + " : ["
        for i in self.indexes:
            res += str(i.index) + ", "
        res += "]"
        return (res)

    def bus_concat(self, prim_dict, keep_range=1, index_separator='_'):
        if (len(self.indexes) < 1): return ("")
        if (keep_range == 1):
            res = "{ ((concat_range (" + str(self.indexes[0].index) + " downto " + str(self.indexes[-1].index) + "))("
        else:
            res = "{ ((concat_range (" + str(len(self.indexes) - 1) + " downto 0))("
        for i in self.indexes:
            res += self.name + index_separator + str(i.index) + '/' + prim_dict.get_macrocell_port(i.type)
            if (i != self.indexes[-1]): res += "& "
        res += "))}"
        return (res)

    def virtual_bus(self, prim_dict, keep_range=1, index_separator='_', unit_path=""):
        if (len(self.indexes) < 1): return ("", "")
        join_name = self.name + "_join"
        bus_def = "quietly virtual signal"
        if (unit_path != ""):
            bus_def += " -env " + unit_path + " -install " + unit_path
        bus_def += "  " + self.bus_concat(prim_dict, keep_range, index_separator) + "  " + join_name
        return (bus_def, join_name)


class RegisterList:
    def __init__(self):
        self.items = []

    def add(self, c):
        self.items.append(c)
        return (self)

    def find(self, name):
        for i in self.items:
            if (i.name == name):
                return (i)
        return (None)

    def sort(self):
        for i in self.items:
            i.sort()
        return (self)

    def to_string(self):
        res = ""
        for i in self.items:
            res += "\n" + i.to_string()
        return (res)


class InjectionTargetConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.entity_type_prefix = ""
            self.type = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.entity_type_prefix = xnode.get('entity_type_prefix')
        self.type = xnode.get('type')


class ScopeConfig:
    def __init__(self, xnode):
        if xnode is None:
            self.node_prefix = ""
            self.unit_path = ""
            self.label_prefix = ""
            self.sampling_options = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.node_prefix = xnode.get('node_prefix')
        self.unit_path = xnode.get('unit_path')
        if not self.unit_path.endswith('/'): self.unit_path += '/'
        self.label_prefix = xnode.get('label_prefix', '')
        self.sampling_options = xnode.get('sampling_options', '')


class DesignNode:
    def __init__(self):
        self.type = ""
        self.name = ""
        self.unit_path = ""
        self.node_prefix = ""
        self.group = ""


class ConfigInitNodes:
    def __init__(self, lbl=""):
        self.config_label = lbl
        self.export_folder = ''
        self.all_nodes = []
        self.pseudo_common_nodes = []
        self.specific_nodes = []
        # for search speed-up
        self.selected = []

    def find_node_by_type_and_name_and_unit(self, stype, sname, sunit):
        self.selected = []
        for c in self.all_nodes:
            if (c.type == stype and c.name == sname and c.unit_path == sunit):
                self.selected.append(c)
                return (c)
        return (None)

    def select_pseudo_common_items(self, reg_base_types, skey, sunit, mask_suffix='_BRB[0-9]+'):
        self.selected = []
        for c in self.all_nodes:
            if (c.unit_path == sunit) and (c.type in reg_base_types):
                if re.sub(mask_suffix, '', c.name) == skey:
                    c.group = skey
                    self.selected.append(c)
        return (self.selected)

    def remove_selected(self):
        for c in self.selected:
            self.all_nodes.remove(c)

    # group = [] (all_nodes, pseudo_common_nodes, specific_nodes)
    def get_nodes_by_type(self, group, stype):
        res = []
        for c in group:
            if (c.type == stype):
                res.append(c)
        return (res)

    def all_nodes_to_xml(self, parent_tag="CommonNodes"):
        res = "<" + parent_tag + ">"
        for c in self.all_nodes:
            res += "\n\t<Node type = \"" + c.type + "\"\tname = \"" + c.unit_path + c.name + "\" />"
        res += "\n</" + parent_tag + ">"
        return (res)

    def specific_nodes_to_xml(self, parent_tag="SpecificNodes"):
        res = "<" + parent_tag + ">"
        for c in self.specific_nodes:
            res += "\n\t<Node type = \"" + c.type + "\"\tname = \"" + c.unit_path + c.name + "\" />"
        res += "\n</" + parent_tag + ">"
        return (res)

    def pseudo_common_nodes_to_xml(self, parent_tag="PseudoCommonNodes"):
        res = "<" + parent_tag + ">"
        for c in self.pseudo_common_nodes:
            res += "\n\t<Node type = \"" + c.type + "\"\tname = \"" + c.unit_path + c.name + "\" group = \"" + c.group + "\" />"
        res += "\n</" + parent_tag + ">"
        return (res)

    def match_to_xml(self, matchlist):
        matching_groups = dict()
        not_matched = []
        for impl in matchlist:
            matchflag = False
            for rtl in self.all_nodes:
                if impl.ptn.replace('/', '_') == ('{0}'.format(rtl.unit_path + rtl.name)).replace('/', '_').replace('(', '_').replace(')', '').replace('.', '_'):  # rtl.unit_path.replace(rtl.group+'/','') + rtl.name:
                    if rtl not in matching_groups:
                        matching_groups[rtl] = []
                    matching_groups[rtl].append(impl)
                    matchflag = True
                    break
            if not matchflag:
                not_matched.append(impl)

        unique_match, multiple_match_rtl, multiple_match_impl = [], [], []
        for k, v in matching_groups.iteritems():
            if len(v) == 1:
                unique_match.append(k)
            elif len(v) > 1:
                multiple_match_rtl.append(k)
                multiple_match_impl += v
        res = "<CommonNodes>\n\t{0}\n</CommonNodes>".format('\n\t'.join(['<Node type=\"{0}\"\tname=\"{1}\" />'.format(c.type, c.unit_path + c.name) for c in unique_match]))
        res += "\n\n<ReplicatedNodes>\n\t{0}\n</ReplicatedNodes>".format('\n\t'.join(['<Node type=\"{0}\"\tname=\"{1}\" />'.format(c.type, c.unit_path + c.name) for c in multiple_match_rtl]))
        res += "\n\n<Replicas>\n\t{0}\n</Replicas>".format('\n\t'.join(['<Node type=\"{0}\"\tname=\"{1}\" />'.format(c.type, c.name) for c in multiple_match_impl]))
        res += "\n\n<Inferred>\n\t{0}\n</Inferred>".format('\n\t'.join(['<Node type=\"{0}\"\tname=\"{1}\" />'.format(c.type, c.name) for c in not_matched]))
        res += "\n\n<PseudoCommonNodes>\n</PseudoCommonNodes>"
        res += "\n\n<SpecificNodes>\n</SpecificNodes>"
        return (res, unique_match + multiple_match_rtl)


class ObservableMacrocellType:
    def __init__(self, xnode=None):
        self.name = ''
        self.port_names = []
        if (xnode != None): self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.get('name').lower()
        buf = xnode.findall('port')
        for c in buf:
            self.port_names.append(c.get('name'))


class ObservableMacrocellDict:
    def __init__(self, xnode=None):
        self.macrocells = []
        if (xnode != None): self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        for c in xnode.findall('macrocell'):
            self.macrocells.append(ObservableMacrocellType(c))

    def get_macrocells_names(self):
        res = []
        for c in self.macrocells:
            res.append(c.name)
        return (res)

    def get_macrocell_ports(self, prim_name):
        for c in self.macrocells:
            if (c.name == prim_name):
                return (c.port_names)


class RegisterReconstructionMacrocellType:
    def __init__(self, xnode=None):
        self.name = ''
        self.port_name = ''
        if (xnode != None): self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.name = xnode.get('name').lower()
        self.port_name = xnode.get('outport', '')


class RegisterReconstructionDict:
    def __init__(self, xnode=None):
        self.macrocells = []
        if (xnode != None): self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        for c in xnode.findall('macrocell'):
            self.macrocells.append(RegisterReconstructionMacrocellType(c))

    def get_macrocells_names(self):
        res = []
        for c in self.macrocells:
            res.append(c.name)
        return (res)

    def get_macrocell_port(self, prim_name):
        for c in self.macrocells:
            if (c.name == prim_name):
                return (c.port_name)


def rreplace(s, old, new, occurrence):
    li = s.rsplit(old, occurrence)
    return new.join(li)


# ---------------------------------------------------
# Model of fault injection targets (simNodes.xml)
# ---------------------------------------------------
class InjectionNode:
    def __init__(self, xnode=None):
        if xnode is None:
            self.type = ""
            self.name = ""
            self.group = ""
        else:
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.type = xnode.get('type').lower()
        self.name = xnode.get('name')
        self.group = xnode.get('group', '')


class ConfigNodes:
    def __init__(self, lbl="", xnode=None):
        self.config_label = lbl
        self.common_nodes = []
        self.pseudo_common_nodes = []
        self.specific_nodes = []
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        com_tag = xnode.findall('CommonNodes')
        ps_com_tag = xnode.findall('PseudoCommonNodes')
        spec_tag = xnode.findall('SpecificNodes')
        if (com_tag != [] and com_tag != None):
            for c in com_tag[0].findall('Node'):
                self.common_nodes.append(InjectionNode(c))
        if (ps_com_tag != [] and com_tag != None):
            for c in ps_com_tag[0].findall('Node'):
                self.pseudo_common_nodes.append(InjectionNode(c))
        if (spec_tag != [] and com_tag != None):
            for c in spec_tag[0].findall('Node'):
                self.specific_nodes.append(InjectionNode(c))

    def get_all_by_typelist(self, typelist):
        res = []
        for c in self.common_nodes:
            if (c.type in typelist):
                res.append(c)
        for c in self.pseudo_common_nodes:
            if (c.type in typelist):
                res.append(c)
        for c in self.specific_nodes:
            if (c.type in typelist):
                res.append(c)
        return (res)

    def get_all(self):
        res = []
        for c in self.common_nodes:
            res.append(c)
        for c in self.pseudo_common_nodes:
            res.append(c)
        for c in self.specific_nodes:
            res.append(c)
        return (res)


# --------------------------------------------------
# Fault dictionary model
# -------------------------------------------------
class Macrocell:
    def __init__(self, type, source_file=''):
        self.type = type
        self.source_file = source_file
        self.configuration = ''
        self.instrumentation_checklist = []


# class ProfilingRule:
#    def __init__(self, xnode):
#        self.type = ''
#        self.profile_expression = ''
#        if(xnode!=None):
#            self.type = xnode.get('type')
#            self.profile_expression = xnode.get('profile_expression')


class NodeDimension:
    def __init__(self, low_index=0, high_index=0):
        self.low_index = low_index
        self.high_index = high_index


class Node:
    def __init__(self, placeholder, nodename_pattern):
        self.placeholder = placeholder
        self.nodename_pattern = nodename_pattern


class NodeDimension:
    def __init__(self, low_index=0, high_index=0):
        self.low_index = low_index
        self.high_index = high_index


class InjectionCase:
    def __init__(self, xnode):
        self.label = ''
        self.condition = ''
        self.dimensions = []
        self.nodes = []  # from string separated by comma
        self.profile_switching_activity = ''
        self.profile_value = ''
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.label = xnode.get('label', '')
        self.condition = xnode.get('condition', '').replace(' ', '').lower()
        self.profile_switching_activity = xnode.get('profile_switching_activity')
        self.profile_value = xnode.get('profile_value')
        d = xnode.get('dimensions', '').replace(' ', '')
        if d != '':
            for c in d.split(','):
                t = c.split('-')
                self.dimensions.append(NodeDimension(int(t[0]), int(t[1])))
        d = xnode.get('nodes', '').replace(' ', '')
        if d != '':
            for c in d.split(','):
                t = c.split('=')
                self.nodes.append(Node(t[0], t[1]))
        else:
            self.nodes.append(Node('', ''))


class InjectionRule:
    def __init__(self, xnode):
        self.code_pattern = ''
        self.injection_cases = []
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.code_pattern = xnode.get('code_pattern').replace('#;', '\n')
        for c in xnode.findall('injectioncase'):
            self.injection_cases.append(InjectionCase(c))


class InstrumentationRuleBase:
    def __init__(self):
        pass


class InjectableGeneric(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.src = ''
        self.dst = ''
        if (xnode != None):
            self.src = xnode.get('src')
            self.dst = xnode.get('dst')


class EncloseInProcess(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.block_name = ''
        self.process_name = ''
        if (xnode != None):
            self.block_name = xnode.get('block_name')
            self.process_name = xnode.get('process_name')


class RedefineNode(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.name = ''
        self.modifier_to = ''
        self.basetype_to = ''
        self.inline_to = ''
        if (xnode != None):
            self.name = xnode.get('name')
            self.modifier_to = xnode.get('modifier_to')
            self.basetype_to = xnode.get('basetype_to')
            self.inline_to = xnode.get('inline_to')


class ExtendSensitivityList(InstrumentationRuleBase):
    def __init__(self, xnode):
        InstrumentationRuleBase.__init__(self)
        self.process_name = ''
        self.nodes = []
        if (xnode != None):
            self.process_name = xnode.get('process_name')
            self.nodes = xnode.get('nodes').split(',')


class InstrumentationRule:
    def __init__(self, xnode):
        self.items = []
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        for c in xnode.findall('injectable_generic'):
            self.items.append(InjectableGeneric(c))
        for c in xnode.findall('enclose_inprocess'):
            self.items.append(EncloseInProcess(c))
        for c in xnode.findall('redefine_node'):
            self.items.append(RedefineNode(c))
        for c in xnode.findall('extend_sensitivity_list'):
            self.items.append(ExtendSensitivityList(c))


class FaultDescriptor:
    def __init__(self, xnode):
        self.fault_model = ''
        self.macrocells = []
        self.instrumentation_rule = None
        self.injection_rules = []
        if (xnode != None):
            self.build_from_xml(xnode)

    def build_from_xml(self, xnode):
        self.fault_model = xnode.get('model')
        self.macrocells = [x.lower() for x in re.findall('[a-zA-Z0-9_]+', xnode.get('macrocells'))]
        for c in xnode.findall('instrumentation_rule'):
            self.instrumentation_rule = InstrumentationRule(c)
        for c in xnode.findall('injection_rule'):
            self.injection_rules.append(InjectionRule(c))


class FaultDict:
    def __init__(self, fname):
        self.dict_items = []
        self.macrocells = []
        if (fname != ''):
            self.update(fname)

    # update dictionary by appending items from xml specification (e.g. Lib_Spec_simprim.xml)
    def update(self, fname):
        tree = ET.parse(fname).getroot()
        for xnode in tree.findall('fdesc'):
            self.dict_items.append(FaultDescriptor(xnode))
        for m in self.get_prim_list():
            self.macrocells.append(Macrocell(m, ''))

    def get_prim_list(self):
        res = []
        for c in self.dict_items:
            for i in c.macrocells:
                if (not i in res):
                    res.append(i)
        return (res)

    def get_descriptor(self, faultmodel, macrocell):
        for desc in self.dict_items:
            if (desc.fault_model == faultmodel and macrocell in desc.macrocells):
                return (desc)
        return (None)


def get_strcontains_index(ilist, ikey):
    for i in range(0, len(ilist), 1):
        if ilist[i].find(ikey) >= 0:
            return (i)
    return (None)


class ExpDescItem:
    def __init__(self):
        self.index = int(0);
        self.dumpfile = ""
        self.target = ""
        self.instance_type = ""
        self.fault_model = ""
        self.injection_case = ""
        self.forced_value = ""
        self.duration = float()
        self.injection_time = float(0)
        self.observation_time = float(0)
        self.generic_fault_model = None
        self.max_activity_duration = float(0)
        self.max_activity_relative_from = ''
        self.max_activity_relative_to = ''
        self.effective_switches = int(0)
        self.effective_switches_from = ''
        self.effective_switches_to = ''
        self.sw_per_cycle = float(0)
        self.logic_group = ''
        self.profiled_value = ''
        self.on_trigger = ''

    def build_from_csv_line(self, line, itemsep, ind):
        values = line.split(itemsep)
        if ind['INDEX'] != None: self.index = int(values[ind['INDEX']])
        if ind['DUMPFILE'] != None: self.dumpfile = str(values[ind['DUMPFILE']])
        if ind['TARGET'] != None: self.target = values[ind['TARGET']]
        if ind['INSTANCE_TYPE'] != None: self.instance_type = values[ind['INSTANCE_TYPE']]
        if ind['FAULT_MODEL'] != None: self.fault_model = values[ind['FAULT_MODEL']]
        if ind['FORCED_VALUE'] != None: self.forced_value = (values[ind['FORCED_VALUE']]).replace('*', 'x').replace('#', '')  # .replace('+','plus')
        if ind['DURATION'] != None: self.duration = float((values[ind['DURATION']]))
        if ind['TIME_INSTANCE'] != None:  self.injection_time = float(values[ind['TIME_INSTANCE']])
        if ind['OBSERVATION_TIME'] != None:  self.observation_time = float(values[ind['OBSERVATION_TIME']])
        if ind['INJECTION_CASE'] != None:  self.injection_case = values[ind['INJECTION_CASE']]
        if ind['HEAD_TIME'] != None:  self.head_time = float(values[ind['HEAD_TIME']])
        if ind['INTERVAL'] != None:  self.offset_interval = values[ind['INTERVAL']]
        if ind['OFFSET'] != None:  self.offset = float(values[ind['OFFSET']])
        if ind['MAX_ACTIVITY_DURATION'] != None:
            try:
                self.max_activity_duration = float(values[ind['MAX_ACTIVITY_DURATION']])
            except ValueError:
                self.max_activity_duration = float(0)
        if ind['EFFECTIVE_SWITHES'] != None:
            try:
                self.effective_switches = int(values[ind['EFFECTIVE_SWITHES']])
            except ValueError:
                self.effective_switches = int(0)
        if ind['SW_PER_CYCLE'] != None: self.sw_per_cycle = float(values[ind['SW_PER_CYCLE']])
        if ind['PROFILED_VALUE'] != None: self.profiled_value = values[ind['PROFILED_VALUE']]
        if ind['ON_TRIGGER'] != None: self.on_trigger = values[ind['ON_TRIGGER']]
        if ind['ACTIVE_NODES'] != None: self.active_nodes = set((values[ind['ACTIVE_NODES']]).split(':'))
        return (self)

    def to_string(self):
        return (str(self.index) + " | " + self.target + " | " + self.instance_type + " | " + self.fault_model + " | " + self.forced_value + " | " + str(self.injection_time) + " | " + str(self.observation_time))


class ExpDescTable:
    def __init__(self, label=""):
        self.label = label
        self.items = []

    def build_from_csv_file(self, file, default_logic_type='Other'):
        if isinstance(file, str):
            with open(file, 'r') as csv_file:
                lines = csv_file.readlines()
        else:
            lines = file.readlines()
        itemsep = re.findall("sep\s*?=\s*?([;,]+)", lines[0])[0]
        for i in lines:
            if i.find('INDEX') >= 0:
                headers = i.split(itemsep)
                break
        ind = dict()
        ind['INDEX'] = get_strcontains_index(headers, 'INDEX')
        ind['DUMPFILE'] = get_strcontains_index(headers, 'DUMPFILE')
        ind['TARGET'] = get_strcontains_index(headers, 'TARGET')
        ind['INSTANCE_TYPE'] = get_strcontains_index(headers, 'INSTANCE_TYPE')
        ind['FAULT_MODEL'] = get_strcontains_index(headers, 'FAULT_MODEL')
        ind['FORCED_VALUE'] = get_strcontains_index(headers, 'FORCED_VALUE')
        ind['DURATION'] = get_strcontains_index(headers, 'DURATION')
        ind['TIME_INSTANCE'] = get_strcontains_index(headers, 'TIME_INSTANCE')
        ind['OBSERVATION_TIME'] = get_strcontains_index(headers, 'OBSERVATION_TIME')
        ind['HEAD_TIME'] = get_strcontains_index(headers, 'HEAD_TIME')
        ind['INTERVAL'] = get_strcontains_index(headers, 'INTERVAL')
        ind['OFFSET'] = get_strcontains_index(headers, 'OFFSET')
        ind['MAX_ACTIVITY_DURATION'] = get_strcontains_index(headers, 'MAX_ACTIVITY_DURATION')
        ind['EFFECTIVE_SWITHES'] = get_strcontains_index(headers, 'EFFECTIVE_SWITHES')
        ind['SW_PER_CYCLE'] = get_strcontains_index(headers, 'SW_PER_CYCLE')
        ind['PROFILED_VALUE'] = get_strcontains_index(headers, 'PROFILED_VALUE')
        ind['ON_TRIGGER'] = get_strcontains_index(headers, 'ON_TRIGGER')
        ind['INJECTION_CASE'] = get_strcontains_index(headers, 'INJECTION_CASE')
        ind['ACTIVE_NODES'] = get_strcontains_index(headers, 'ACTIVE_NODES')
        for l in lines:
            if re.match('^\s*?[0-9]+', l):
                c = ExpDescItem()
                c.build_from_csv_line(l, itemsep, ind)
                if c.instance_type == "": c.instance_type = default_logic_type
                self.items.append(c)
        return (len(self.items))

    def get_by_index(self, index):
        for c in self.items:
            if (c.index == index):
                return (c)
        return (None)

    def normalize_targets(self):
        for c in self.items:
            c.target = c.target.replace('/O}', '}')
            c.target = c.target.replace('/', '_')

    def filter(self, key, value):
        if key == 'profiled_value':
            buf = []
            cnt = 0
            for i in self.items:
                if i.profiled_value == value:
                    buf.append(i)
                    cnt += 1
            self.items = buf
            print 'Filter Matched: Key = ' + key + ' Value = ' + str(value) + '  cnt = ' + str(cnt)


class TrapDescription:
    def __init__(self):
        self.name = ""
        self.description = ""
        self.priority = ""
        self.trap_type = "00"

    def to_string(self):
        return ("Trap: " + self.name + ", Description: " + self.description + ", Priority: " + self.priority + ", Trap type: " + self.trap_type)


class TrapDescriptionTable:
    def __init__(self):
        self.items = []

    def build_from_file(self, fname):
        if (fname != ""):
            tree = ET.parse(fname).getroot()
            for xnode in tree.findall('item'):
                name = xnode.get('trap')
                description = xnode.get('description')
                priority = xnode.get('priority')
                trap_type = xnode.get('tt')
                if (trap_type.find('-') == -1):
                    t_item = TrapDescription()
                    t_item.name = name
                    t_item.description = description
                    t_item.priority = priority
                    t_item.trap_type = trap_type
                    self.items.append(t_item)
                else:
                    vals = trap_type.split('-')
                    vlow = int(vals[0], 16)
                    vhigh = int(vals[1], 16)
                    for vind in range(vlow, vhigh + 1, 1):
                        t_item = TrapDescription()
                        t_item.name = name
                        t_item.description = description
                        t_item.priority = priority
                        t_item.trap_type = "%X" % vind
                        self.items.append(t_item)

    def to_string(self):
        res = ""
        for c in self.items:
            res += "\n" + c.to_string()
        return (res)

    def get_by_trap_type(self, tt):
        for c in self.items:
            if (c.trap_type == tt):
                return (c)
        return (None)


# Data structure to interact with nested process and to export the statistics to external user interface
class ProcStatus(object):
    def __init__(self, tag='Noname'):
        self.data = dict()
        self.tag = tag
        self.changed = True

    def copy(self, src):
        for key, value in list(src.data.items()):
            self.data[key] = value
        self.tag = src.tag
        self.changed = src.changed

    def update(self, key, message, descriptor):
        self.data[key] = (message, descriptor)
        self.changed = True

    def get(self, key):
        if key in self.data:
            return (self.data[key])
        return (None)

    def get_message_dict_by_descriptor(self, descriptor):
        res = dict()
        for key, value in self.data.iteritems():
            if len(value) > 1:
                if value[1] == descriptor:
                    res[key] = value[0]
        return (res)

    def set_mark(self, inmark):
        self.changed = inmark

    def get_mark(self):
        return (self.changed)

    def clear(self, keylist, message='-', descriptor=''):
        for key in keylist:
            self.update(key, message, descriptor)

    def to_str(self):
        res = ""
        for key, value in list(self.data.items()):
            res += str(key) + ' : ' + str(value) + ', '
        return (res)

    def to_xml(self):
        res = '<' + self.tag + ' '
        for key, value in list(self.data.items()):
            res += '\n\t' + str(key) + ' = \"'
            if len(value) > 1:
                res += '{0}${1}'.format(str(value[0]), str(value[1])) + '\" '
            else:
                res += '{0}'.format(str(value[0])) + '\" '
        res += ' >'
        res += '\n</' + self.tag + '>'
        return (res)

    def from_xml(self, xmlroot, tag, key, val):
        for i in xmlroot.findall(tag):
            if i.get(key, '').split('$')[0] == val:
                for aname, avalue in i.attrib.items():
                    c = avalue.split('$')
                    if len(c) > 1:
                        self.data[aname] = (c[0], c[1])
                    else:
                        self.data[aname] = (c[0], '')
                self.tag = tag
                break


def save_statistics(statlist, statfile):
    res = '<?xml version=\"1.0\"?>\n<data>'
    for i in statlist:
        res += '\n\n' + i.to_xml()
    res += '\n</data>'
    try:
        with open(statfile, 'w') as f:
            f.write(res)
        # minimized stat file - export only changed items
        res = '<?xml version=\"1.0\"?>\n<data>'
        for i in statlist:
            if i.get_mark():
                res += '\n\n' + i.to_xml()
                i.set_mark(False)
        res += '\n</data>'
        with open(statfile.replace('.xml', '_min.xml'), 'w') as f:
            f.write(res)
    except:
        print 'ERROR: save_statistics(): {}'.format(statfile)


def typed(istring):
    if istring.isdigit():
        return (int(istring))
    try:
        return (float(istring))
    except ValueError:
        return (str(istring))


def unixstyle_path(path):
    return (path.replace('\\', '/'))


class ConsoleColors:
    Green = '\x1b[7;30;42m'
    Default = '\x1b[0m'


def console_message(msgtxt, color=ConsoleColors.Default, clrflag=False):
    if platform in ['linux', 'linux2', 'cygwin']:
        msg = color + msgtxt + ConsoleColors.Default
    elif platform in ['win32', 'win64']:
        msg = msgtxt
    if clrflag: msg += '\r'
    sys.stdout.write(msg)
    sys.stdout.flush()


def console_complex_message(msgtxt_lst, color_lst=[], clrflag=False):
    msg = ''
    for i in range(len(msgtxt_lst)):
        if i < len(color_lst) and platform in ['linux', 'linux2', 'cygwin']:
            msg += color_lst[i] + msgtxt_lst[i] + ConsoleColors.Default
        else:
            msg += msgtxt_lst[i]
    if clrflag: msg += '\r'
    sys.stdout.write(msg)
    sys.stdout.flush()


# determines whether two intervals (A and B) intersect, and calculates the intersection length
def intersect_intervals(A_low, A_high, B_low, B_high):
    if B_high >= A_low and B_low <= A_high:
        return ((True, min(A_high, B_high) - max(A_low, B_low)))
    else:
        return ((False, 0))

    # returns list of possible addresses by replacing X with 1/0


def resolve_indetermination(addr):
    res = []
    res.append(addr.upper().replace('Z', 'X').replace('*', 'X').replace('U', 'X').replace('?', 'X'))
    cnt = 1
    while cnt > 0:
        cnt = 0
        for i in range(0, len(res), 1):
            if res[i].count('X') > 0:
                a = res[i]
                res.remove(a)
                res.append(a.replace('X', '1', 1))
                res.append(a.replace('X', '0', 1))
                cnt += 1
                break
    return (res)


def get_index_of_bit(data, bitval, width):
    for i in range(width):
        if (data >> i) & 0x1 == bitval:
            return i
    return -1

