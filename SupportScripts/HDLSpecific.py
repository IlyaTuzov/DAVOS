# Fucntions and data structures specific for HDL models (VHDL/Verilog)
# Author: Ilya Tuzov, Universitat Politecnica de Valencia

import re
import os
import shutil
import glob
#Functions in this file use configuration of HDL model and generics
#But have no access to implementation flow

class SignalDim:
    def __init__(self, LeftD=int(0), RightD=int(0), Dir='downto'):
        self.LeftD=LeftD
        self.RightD=RightD
        self.Dir=Dir
    def to_string(self):
        return(str(self.LeftD) + "  " + self.Dir + "  " + str(self.RightD))      
    def get_width(self):
        return(abs(int(self.LeftD)-int(self.RightD) + 1))
    def get_max(self):
        if(int(self.LeftD) > int(self.RightD)):
            return(int(self.LeftD))
        else:
            return(int(self.RightD))
    def get_min(self):
        if(int(self.LeftD) < int(self.RightD)):
            return(int(self.LeftD))
        else:
            return(int(self.RightD))        

class PortT:
    def __init__(self, name='', direction='', basetype=''):
        self.name=name
        self.wire=None
        self.direction=direction
        self.basetype=basetype
        self.dimensions=[]
        self.used = 0
    def to_string(self):
        line = self.name + " " + self.direction + " " + self.basetype
        #line = line + "dim: " + str(len(self.dimensions))
        if len(self.dimensions) > 0:
            line += " ("
            for d in self.dimensions:
                if d != self.dimensions[-1]:
                    line = line + d.to_string() + ", "
                else:
                    line = line + d.to_string() + ")"
        return (line)

    def get_wire_definition(self, prefix = "tb_"):
        self.wire = prefix+self.name
        res = 'signal ' + self.wire + ' : ' + self.basetype
        if len(self.dimensions) > 0:
            res += " ("
            for d in self.dimensions:
                if d != self.dimensions[-1]:
                    res += d.to_string() + ", "
                else:
                    res += d.to_string() + ")"
        return(res)
    def get_width(self):
        res = int(1)
        for dim in self.dimensions:
            res = res*dim.get_width()
        return(res)
            
        
        
class EntityT:
    def __init__(self, name='none', file_content = ''):
        self.name = name
        self.file_content=file_content
        self.arch_name=''
        self.port_list_def=[]
        self.entity_definition=''
        self.port_list=[]
        self.architecture=''
        self.body=''
        self.port_map=[]
        self.expressions=[]
    def get_port_by_name(self, portname, match_case = "off"):
        for p in self.port_list:
            if(match_case == "off"):
                if(p.name.lower() == portname.lower()):
                    return(p)
            else:
                if(p.name == portname):
                    return(p)                
        return(None)



def build_testbench(config, model, testbench_template_content):
    result = testbench_template_content
    pure_port_name = "[a-zA-Z0-9_.]+"
    port_par_pattern = re.compile(pure_port_name)
    port_def_pattern = re.compile(pure_port_name+'.+?;')
    dimensions_def_pattern=re.compile("\(.+?\)")
    number_pattern = re.compile("[0-9]+")
    word_pattern = re.compile("[a-zA-Z]+")

    os.chdir(os.path.join(model.ModelPath))
    print("\n Target dir: " + os.getcwd())
    netlist_files = glob.glob(config.design_genconf.netlist_dir + "/par/" + "*.vhd")
    ent = None
    for ntf in netlist_files:
        f = open(ntf)
        content = f.read()
        f.close()
        match = re.findall("entity\s+"+ config.design_genconf.top_design_unit +"\s+is",content,re.DOTALL)
        if(len(match)>0):
            ent = EntityT(config.design_genconf.top_design_unit, content)
            break
    match = re.findall('entity\s+'+ent.name+'\s+is.+?end\s'+ent.name,content,re.DOTALL)
    ent.entity_definition = match[0]
    t = re.sub('\s*\)\s*;\s*end', ';\nend', ent.entity_definition)
    ent.port_list_def = port_def_pattern.findall(t)
    #parse port list -> list of PortT objects
    for p in ent.port_list_def:
        t = port_par_pattern.findall(p)
        port = PortT(t[0],t[1],t[2])
        dim = dimensions_def_pattern.findall(p)
        if len(dim) > 0:
            m=dim[0].split(',')
            for x in m:
                nm = number_pattern.findall(x)
                wd = word_pattern.findall(x)
                sdim = SignalDim(nm[0], nm[1], wd[0])
                port.dimensions.append(sdim)
        ent.port_list.append(port)
    
    #Signal definitions to use in port map
    sdef = "" 
    for p in ent.port_list:
        sdef += "\n\t" + p.get_wire_definition()
        assignment = ''
        if(p.direction =="in" and len(p.dimensions) == 0):
            assignment = " := \'0\'"
        if(p.name.lower() == config.design_genconf.rst_net.lower()):
            assignment = " := \'1\'"
        sdef += assignment + ";"
    result = result.replace('--#Signals', sdef)
    #UUT Instance port map
    uut_map = config.design_genconf.uut_root + " : entity work." + config.design_genconf.top_design_unit + " port map ("
    for i in range(0, len(ent.port_list), 1):
        uut_map += "\n\t" + ent.port_list[i].name + "\t=>\t" + ent.port_list[i].wire
        if(i != len(ent.port_list)-1):
            uut_map += ","
    uut_map +="\n\t);"
    result = result.replace('--#Instance', uut_map)
    #Clock
    clock_port = ent.get_port_by_name(config.design_genconf.clk_net)
    if(clock_port == None):
        print "clock signal [" + config.design_genconf.clk_net +"] not found in the netlist code"
    else:
        clk_proc = "\t\twait for 1 ns * " + config.design_genconf.clk_constant + "/2;\n\t\t" + clock_port.wire + " <= not " + clock_port.wire + ";"
        result = result.replace('--#Clock', clk_proc)
    #Reset
    reset_port = ent.get_port_by_name(config.design_genconf.rst_net)
    if(reset_port == None):
        print "Reset signal [" + config.design_genconf.rst_net +"] not found in the netlist code"
    else:
        rst_proc = "\t\twait for 10*" + config.design_genconf.clk_constant + ";\n\t\t" + reset_port.wire + " <= \'0\';"
        result = result.replace('--#Reset', rst_proc)
    #Random_vector
    inputs = []
    in_wid = 0
    for p in ent.port_list:
        if(p.direction == "in" and p.name.lower() != config.design_genconf.clk_net.lower() and p.name.lower() != config.design_genconf.rst_net.lower()):
            inputs.append(p)
            in_wid += p.get_width()
    if(in_wid < 16): in_wid = 16;
    vect = 'rand_input_vect'
    vect_def = "\t\tconstant RWID : integer := " +str(in_wid) + ";"
    vect_def += "\n\t\tvariable " + vect + " : std_logic_vector(RWID-1 downto 0);"
    result = result.replace('--#Random_vector', vect_def)        
    #Process
    v_i = in_wid-1
    proc = "\t\t\tset_random_value(" + vect + ");"
    for p in inputs:
        if len(p.dimensions) > 0:
            dmin = p.dimensions[0].get_min()
            dmax = p.dimensions[0].get_max()
            for i in range(dmax, dmin-1, -1):
                proc += "\n\t\t\t" + p.wire + "(" + str(i) + ")" + " <= " + vect + "(" + str(v_i) + ");"
                v_i -=1
        else:
            proc += "\n\t\t\t" + p.wire + " <= " + vect + "(" + str(v_i) + ");"
            v_i -= 1
    proc+="\n\t\t\twait until rising_edge(" + clock_port.wire + ");"
    result = result.replace('--#Process', proc) 
    print(result)
    f = open(config.design_genconf.testbench_file,'w')
    f.write(result)
    f.close()



def configure_testbench_vhdl(config, model):
    #Adjust clock frequency in the testbench
    if not 'ClockPeriod' in model.Metrics: return
    period = model.Metrics['ClockPeriod']
    scale_factor = float(config.design_genconf.std_clock_period) / period
    with open(config.design_genconf.testbench_file, 'r') as f:
        content = f.read()
    content = re.sub(config.design_genconf.clk_constant + ".*:=\s*[0-9]+\.?[0-9]*\s*?", config.design_genconf.clk_constant + " : real := " + str("%.1f" % period), content)
    with open(config.design_genconf.testbench_file, 'w') as f:
        f.write(content)
    #Create/Modify sim_project_file
    content = ''
    if config.design_genconf.sim_project_file != "" and os.path.exists(config.design_genconf.sim_project_file):
        with open(config.design_genconf.sim_project_file, 'r') as f:
            content = f.read()
    netlist_files = glob.glob(config.design_genconf.netlist_dir + "/par/" + "*.vhd")
    content = '\n'.join(['vhdl work \"{0}\"'.format(c) for c in netlist_files]) + '\n' + content
    content += "\nvhdl work \"" + config.design_genconf.testbench_file + '\"'
    with open(config.design_genconf.sim_project_file, 'w') as f:
        f.write(content)
   #Check netlist for invalid identifiers, rename them
    rx_ptn = re.compile(r"\\.*\)\\")
    repl_ptn = re.compile("[a-zA-Z0-9_]+")
    for c in netlist_files:
        with open(c,'r') as ndesc:
            ncontent = ndesc.read()
        sdf = c.replace(".vhd", ".sdf")
        if(os.path.exists(sdf)):
            with open(sdf,'r') as sdf_desc:
                sdf_content = sdf_desc.read()
        nlines = ncontent.split('\n')
        print("Netlist file " + c + ", lines: " + str(len(nlines)))
        ident_list = set()
        for l in nlines:
            match = re.findall(rx_ptn, l)
            if(len(match)>0):
                ident_list.add(match[0])
        cnt = 0
        for ident in ident_list:
            tx = re.findall(repl_ptn, ident)
            if(len(tx) > 0):
                repl_id = tx[0] + "_FixSyntax_" + str(cnt)
            else:
                repl_id = "Identifier_FixSyntax_" + str(cnt)
            ncontent = ncontent.replace(ident, repl_id)
            x = ident.replace("\\","",1).replace(")\\","\\)")
            sdf_content = sdf_content.replace(x, repl_id)
            print("\n\t\tFixed Identifier Syntax: " + ident + " -> " + repl_id + " [" + x + "] -> " + repl_id)
            cnt += 1
        if(cnt > 0):
            print("\n\t\tREWRITING NETLIST: " + c)
            with open(c,'w') as ndesc:
                ncontent = ndesc.write(ncontent)
            if(os.path.exists(sdf)):
                print("\n\t\tREWRITING SDF: " + sdf)
                with open(sdf,'w') as sdf_desc:
                    sdf_desc.write(sdf_content)


