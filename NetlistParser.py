import subprocess
import serial.tools.list_ports
import re
import shutil



def ParseVivadoNetlist(VivadoProjectFile, ImplementationRun, targetDir):
    script = """
        open_project {0}
        open_run [get_runs {1}]
        set exportdir \"{2}\"

        set fout [open $exportdir/LUTMAP.csv w]
        puts $fout \"sep=;\nNode;CellType;CellLocation;BEL;BellType;ClockRegion;Tile;INIT;CellConnections;\"
        foreach cell [get_cells -hier -filter {{PRIMITIVE_GROUP==LUT}}] {{
            set bel [get_bels -of_objects $cell] 
            set tile [get_tiles -of_objects $bel] 
            set cr [get_clock_regions -of_objects $tile] 
                        puts -nonewline $fout [format \"%s;%s;%s;%s;%s;%s;%s;%s;\" \
                            [get_property NAME $cell] \
                            [get_property PRIMITIVE_TYPE $cell] \
                            [get_property LOC $cell] \
					        [get_property BEL $cell] \
                            [get_property TYPE $bel]  \
                            [get_property NAME $cr]   \
					        [get_property NAME $tile] \
					        [get_property INIT $cell] \
                            ]
                        foreach pin [get_pins -of_objects $cell] {{ 
                            puts -nonewline $fout [format \"{{%s:%s}}\" [get_property REF_PIN_NAME $pin] [lindex [split [get_bel_pins -of_objects $pin] '/'] end] ] 
                        }} 
                        puts $fout \";\" 
        }}
            
        close $fout


        # Bels.csv: Design Description File - Table containing location of each instantiated cell and it's source design node
        set fout [open $exportdir/Bels.csv w]
        puts $fout \"sep=;\nCellType;CellLocation;BellType;ClockRegion;Tile;Node;BEL\"
        foreach cell [get_cells -hier] {{foreach bel [get_bels -of_objects $cell] {{foreach tile [get_tiles -of_objects $bel] {{foreach cr [get_clock_regions -of_objects $tile] {{puts $fout [format "%s;%s;%s;%s;%s;%s;%s" [get_property PRIMITIVE_TYPE $cell] [get_property LOC $cell] [get_property TYPE $bel]  [get_property NAME $cr] [get_property NAME $tile] [get_property NAME $cell] [get_property BEL $cell] ]}} }} }} }}
        close $fout
        # bit/bin/edc/ebd/ll: Write bitstream files
        set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
        write_bitstream -force -logic_location_file $exportdir/Bitstream.bit 
        write_cfgmem -force -format BIN -interface SMAPx32 -disablebitswap -loadbit  \"up 0x0 $exportdir/Bitstream.bit\" -file $exportdir/Bitstream.bin
        write_vhdl $exportdir/netlist.vhd
    """.format(VivadoProjectFile, ImplementationRun, targetDir)

    with open('Parse.tcl','w') as f: f.write(script)

    proc = subprocess.Popen('vivado -mode tcl'.format(), stdin=subprocess.PIPE, stdout=subprocess.PIPE , shell=True)
    out, err = proc.communicate(script.replace('\\','/').encode())
    return(out, err)

