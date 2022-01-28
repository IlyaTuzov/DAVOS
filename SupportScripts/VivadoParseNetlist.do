#NETLIST PARSE SCRIPT FOR VIVADO
#Run example: 
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseNetlist.do -tclargs C:/Projects/FFIMIC/FFIMIC.xpr * cells C:/Projects/FFIMIC/DavosGenerated 1 1

if {$argc < 3} {
    puts "not enough arguments"
    return
}

set proj        [lindex $argv 0]
set run         [lindex $argv 1]
set mode        [lindex $argv 2]   
set exportdir   [lindex $argv 3]
set ebc         [lindex $argv 4]
set ll          [lindex $argv 5]

puts "proj=$proj, run=$run, mode=$mode, exportdir=$exportdir"

open_project $proj
puts "Project opened: [current_project]"

if {$run != "*" } {
    open_run [get_runs $run]
} else {
    open_run [get_runs -filter {CURRENT_STEP == route_design || CURRENT_STEP == write_bitstream}]
}
puts "Implementation opened: [current_run]"


set fout [open $exportdir/CELLS.csv w]
puts $fout "sep=;\nNode;CellType;CellLocation;BEL;BellType;ClockRegion;Tile;INIT;CellConnections;"

if {$mode == "cells"} {
    #Export LUT descriptores only for netlist cells
    puts "Parsing CELLS"
    foreach cr [get_clock_regions] {
        foreach bel [get_bels -of_objects $cr -filter {IS_USED==True}] {
            set cell [get_cells -of_objects $bel]
            if {[llength $cell] > 0} {
                set tile [get_tiles -of_objects $bel]
                puts -nonewline $fout [format "%s;%s;%s;%s;%s;%s;%s;%s;" \
                    [get_property NAME $cell] \
                    [get_property PRIMITIVE_TYPE $cell] \
                    [get_property LOC $cell] \
                    [get_property BEL $cell] \
                    [get_property TYPE $bel]  \
                    [get_property NAME $cr]   \
                    [get_property NAME $tile] \
                    [get_property INIT $cell] \
                    ]                
                foreach pin [get_pins -of_objects $cell] { 
                    puts -nonewline $fout [format "{%s:%s}" [get_property REF_PIN_NAME $pin] [lindex [split [get_bel_pins -of_objects $pin] '/'] end] ] 
                }
                puts $fout ";"                           
            }
        }
    }
} elseif {$mode == "bels"} {

    #Export LUT descriptors for all used bells (either Cell, or Pass-through LUT, or Constant LUT)
    puts "Parsing BELS"
    foreach bel [get_bels -filter {TYPE==LUT5 || TYPE == LUT_OR_MEM5 || TYPE==LUT6 || TYPE == LUT_OR_MEM6 }] {
        set cell [get_cells -of_objects $bel]
        if {[llength $cell] > 0} {
            set tile [get_tiles -of_objects $bel] 
            set cr   [get_clock_regions -of_objects $tile] 
                        puts -nonewline $fout [format "%s;%s;%s;%s;%s;%s;%s;%s;" \
                            [get_property NAME $cell] \
                            [get_property PRIMITIVE_TYPE $cell] \
                            [get_property LOC $cell] \
                            [get_property BEL $cell] \
                            [get_property TYPE $bel]  \
                            [get_property NAME $cr]   \
                            [get_property NAME $tile] \
                            [get_property INIT $cell] \
                            ]
                        foreach pin [get_pins -of_objects $cell] { 
                            puts -nonewline $fout [format "{%s:%s}" [get_property REF_PIN_NAME $pin] [lindex [split [get_bel_pins -of_objects $pin] '/'] end] ] 
                        }
                        puts $fout ";"     
        } else {
            set cellpins [get_pins -of_objects [get_bel_pins -of_objects $bel]]
            if {[llength $cellpins] > 0} {
                set slice [get_sites -of_objects $bel]
                set tile [get_tiles -of_objects $bel]
                set cr [get_clock_regions -of_objects $tile]
                #Pass-through LUT (one of the inputs forwarded to output)
                puts -nonewline $fout [format "PASSTHROUGH;LUT1;%s;%s;%s;%s;%s;;" \
                    [get_property NAME $slice] \
                    [lindex [split [get_property NAME $bel] '/'] end] \
                    [get_property TYPE $bel] \
                    [get_property NAME $cr] \
                    [get_property NAME $tile] ]
                foreach pin $cellpins {
                    puts -nonewline $fout [format "{I0:%s}" [lindex [split [lindex [get_bel_pins -of_objects $pin -filter {NAME =~ *LUT*}] 0] '/'] end] ]
                }        
                puts $fout ";"
            } else {
                set eqn [get_property CONFIG.EQN $bel]
                if { [llength $eqn] > 0} {
                    set slice [get_sites -of_objects $bel]
                    set tile [get_tiles -of_objects $bel]
                    set cr [get_clock_regions -of_objects $tile]
                    #Constant on the output O6/O5 = 1/0
                    puts $fout [format "Constant;LUT0;%s;%s;%s;%s;%s;;;" \
                        [get_property NAME $slice] \
                        [lindex [split [get_property NAME $bel] '/'] end] \
                        [get_property TYPE $bel] \
                        [get_property NAME $cr] \
                        [get_property NAME $tile] ]
                }
            }
        }
    }

} else {
    puts "Unknown mode: $mode"
}
close $fout



# bit/bin/edc/ebd/ll: Write bitstream files
if {$ebc == 1} {
    set_property BITSTREAM.SEU.ESSENTIALBITS YES [current_design]
}
if {$ll == 1} {
    write_bitstream -force -logic_location_file $exportdir/Bitstream.bit
} else {
    write_bitstream -force $exportdir/Bitstream.bit
}
#write_cfgmem -force -format BIN -interface SMAPx32 -disablebitswap -loadbit  \"up 0x0 $exportdir/Bitstream.bit\" -file $exportdir/Bitstream.bin
#write_vhdl $exportdir/netlist.vhd


exit







