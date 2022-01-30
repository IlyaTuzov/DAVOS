# Copyright (c) 2018 by Universitat Politecnica de Valencia.
# This file is a part of the DAVOS toolkit
# and is released under the "MIT license agreement".
# Please check the LICENSE.txt file (that is included as a part of this package) for the license details.
# ------------------------------------------------------------------------------------------------------
# Description:
#       A Vivado script to parse the layout of Xilinx FPGAs
#
# Author: Ilya Tuzov, Universitat Politecnica de Valencia
# ------------------------------------------------------------------------------------------------------


#Run example: 
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseLayout.do -tclargs C:/Projects/FFIMIC/FFIMIC.xpr "*" "*" C:/GitHub/DAVOS/FFI/DeviceSupport
#    vivado -mode batch -source C:/GitHub/DAVOS/SupportScripts/VivadoParseLayout.do -tclargs "*" "xc7a100tcsg324-1" "*" C:/GitHub/DAVOS/FFI/DeviceSupport
if {$argc < 4} {
    puts "not enough arguments"
    return
}

set proj        [lindex $argv 0]
set device      [lindex $argv 1]
set run         [lindex $argv 2]
set exportdir   [lindex $argv 3]
puts "proj=$proj, run=$run, exportdir=$exportdir"

if {$proj != "*"} {
    open_project $proj
    puts "Project opened: [current_project]"
} else {
    create_project project_1 $exportdir/project_1 -part $device
    set_property target_language VHDL [current_project]
    add_files -norecurse $exportdir/template.vhd
    update_compile_order -fileset sources_1
    launch_runs synth_1 -jobs 8
    wait_on_run -timeout 360 synth_1
    launch_runs impl_1 -jobs 8
    wait_on_run -timeout 360 impl_1
}


if {$run != "*" } {
    open_run [get_runs $run]
} else {
    open_run [get_runs -filter {CURRENT_STEP == route_design || CURRENT_STEP == write_bitstream}]
}
puts "Implementation opened: [current_run]"
set devicepart [lindex  [get_parts -of_objects [current_project]] 0]


set_property BITSTREAM.General.UnconstrainedPins {Allow} [current_design]
set_property BITSTREAM.GENERAL.PERFRAMECRC YES [current_design]
set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]
write_bitstream $exportdir/$devicepart.bit
puts "Debug Bitsream Generated"




set fout [open $exportdir/LAYOUT_$devicepart.xml w]
puts $fout "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
puts $fout "<DEVICE part=\"$devicepart\">"

foreach slr [get_slrs] {
    puts $fout [format "\t<SLR\n\t\tname=\"%s\"" [get_property NAME $slr]]
    puts $fout [format "\t\tslr_index=\"%s\"" [get_property SLR_INDEX $slr]]
    puts $fout [format "\t\tconfig_order_index=\"%s\">" [get_property CONFIG_ORDER_INDEX $slr]]
    
    
    foreach cr [get_clock_regions -of_objects $slr] {
        puts $fout [format "\n\t\t<CLOCK_REGION name=\"%s\">" [get_property NAME $cr]]
    
        puts "Processing Tiles in SRL: $slr, ClockRegion: $cr"
        set columndict [dict create]
        foreach tile [get_tiles -of_objects $cr -filter {TYPE==CLBLL_L || TYPE==CLBLL_R || TYPE==CLBLM_L || TYPE==CLBLM_R || TYPE==CLEL_R || TYPE==CLEM}] {
            lassign [regexp -all -inline X([0-9]+)Y([0-9]+) [get_property NAME $tile]] S X Y
            if { [dict exists $columndict $X] } { 
                set v [dict get $columndict $X] 
                if { $Y < [lindex $v 0] } { 
                    #puts "replace Min: $Y"
                    set v [lreplace $v 0 0 $Y]  
                }
                if { $Y > [lindex $v 1] } { 
                    #puts "replace Max: $Y"
                    set v [lreplace $v 1 1 $Y]
                }
                dict set columndict $X $v
            } else {
                #puts "Appending $X : $Y : $Y"
                set tiletype [get_property TYPE $tile]
                dict append columndict $X [list $Y $Y $tiletype]
            }
        }    

        dict for {key val} $columndict {
            puts $fout [format "\t\t\t<COLUMN type=\"%s\" X=\"%s\" MinY=\"%s\" MaxY=\"%s\"> </COLUMN>" [lindex $val 2] $key [lindex $val 0] [lindex $val 1]]
        }
        puts $fout "\n\t\t</CLOCK_REGION>"      
    }
    puts $fout "\n\t</SLR>"
    flush $fout
}
puts $fout "</DEVICE>"
close $fout




